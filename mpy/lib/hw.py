"""hw.py — железо контроллера для MicroPython на ESP32 DevKitC.

Реализует тот же интерфейс «мира», что и emulator/world.py, поэтому логика
device.py одна и та же на плате и в эмуляторе:
  adc(i)            АЦП датчика влажности i (0..7) через мультиплексор
  rain, night       датчик дождя (замкнут = дождь), датчик света (HIGH = ночь)
  open_valves[i]    клапан i (реле через PCF8574, активный LOW)
  pump_on, drain_on, fill_on   реле насоса, дренажа, заливки (GPIO, активный HIGH)
  take_pulses()     импульсы расходомера с прошлого вызова (прерывание на GPIO27)
  flow_lpm()        мгновенный поток, л/мин, по интервалу между импульсами
  faults()          аппаратные неисправности: {"valves"} если PCF8574 не отвечает

Пины — как в pins.h старой прошивки (та же несущая плата).
"""
import time

from machine import ADC, I2C, Pin

PIN_LED, PIN_BUTTON, PIN_LIGHT, PIN_RAIN = 2, 16, 4, 15
PIN_FILL, PIN_DRAIN, PIN_PUMP, PIN_FLOW = 17, 25, 26, 27
PIN_MUX = (12, 13, 14)          # адрес канала мультиплексора S0..S2
PIN_ADC = 33
PIN_SCL, PIN_SDA = 22, 21
PCF_ADDR = 0x20
PULSES_PER_LITER = 450          # YF-S201, как FLOW_PULSES_PER_LITER
FLOW_IDLE_MS = 5000             # нет импульса дольше → мгновенный поток 0


class _Relays:
    """Состояния клапанов как список; присваивание элемента сразу пишет в PCF8574.
    (Наследовать list в MicroPython нельзя — своя маленькая обёртка.)"""

    def __init__(self, hw, values):
        self._v = [bool(x) for x in values]
        self._hw = hw

    def __setitem__(self, i, on):
        self._v[i] = bool(on)
        self._hw._write_pcf()

    def __getitem__(self, i):
        return self._v[i]

    def __len__(self):
        return len(self._v)

    def __iter__(self):
        return iter(self._v)


class Hardware:
    def __init__(self, channels=8):
        self.n = channels
        self.led = Pin(PIN_LED, Pin.OUT, value=0)
        self.button = Pin(PIN_BUTTON, Pin.IN, Pin.PULL_DOWN)      # нажата = HIGH
        self._light = Pin(PIN_LIGHT, Pin.IN, Pin.PULL_DOWN)       # HIGH = темно
        self._rain = Pin(PIN_RAIN, Pin.IN, Pin.PULL_UP)           # LOW = дождь
        self._fill = Pin(PIN_FILL, Pin.OUT, value=0)
        self._drain = Pin(PIN_DRAIN, Pin.OUT, value=0)
        self._pump = Pin(PIN_PUMP, Pin.OUT, value=0)
        self._mux = [Pin(p, Pin.OUT, value=0) for p in PIN_MUX]
        self._adc = ADC(Pin(PIN_ADC))
        self._adc.atten(ADC.ATTN_11DB)                             # 0..3.3 В → 0..4095
        self.i2c = I2C(0, scl=Pin(PIN_SCL), sda=Pin(PIN_SDA), freq=100000)
        self._pcf_ok = False
        self._last_raw = [None] * channels
        self._valves = _Relays(self, [False] * channels)
        self.flow_sensor_ok = True
        self.step_minute = lambda minute: None                     # физики нет — это реальный мир

        # 💧 расходомер: счётчики правит прерывание, читаем атомарно (int)
        self._pulses = 0
        self._last_pulse_ms = 0
        self._gap_ms = 0
        self._taken = 0
        self._flow = Pin(PIN_FLOW, Pin.IN, Pin.PULL_UP)
        self._flow.irq(trigger=Pin.IRQ_FALLING, handler=self._on_pulse)

        self._write_pcf()

    # ---------------- реле
    def _write_pcf(self):
        """Клапаны через PCF8574: бит = 0 — открыть (реле активны LOW)."""
        byte = 0xFF
        for i, on in enumerate(self._valves):
            if on:
                byte &= ~(1 << i) & 0xFF
        try:
            self.i2c.writeto(PCF_ADDR, bytes([byte]))
            self._pcf_ok = True
        except OSError:
            self._pcf_ok = False

    @property
    def open_valves(self):
        return self._valves

    @open_valves.setter
    def open_valves(self, values):
        self._valves = _Relays(self, values)
        self._write_pcf()

    @property
    def pump_on(self):
        return bool(self._pump.value())

    @pump_on.setter
    def pump_on(self, on):
        self._pump.value(1 if on else 0)

    @property
    def drain_on(self):
        return bool(self._drain.value())

    @drain_on.setter
    def drain_on(self, on):
        self._drain.value(1 if on else 0)

    @property
    def fill_on(self):
        return bool(self._fill.value())

    @fill_on.setter
    def fill_on(self, on):
        self._fill.value(1 if on else 0)

    # ---------------- датчики
    @property
    def rain(self):
        return self._rain.value() == 0

    @property
    def night(self):
        return self._light.value() == 1

    def adc(self, ch):
        """Медиана из 9 отсчётов после переключения мультиплексора (sensors.cpp)."""
        for j, pin in enumerate(self._mux):
            pin.value((ch >> j) & 1)
        time.sleep_ms(20)
        s = []
        for _ in range(9):
            s.append(self._adc.read())
            time.sleep_us(200)
        s.sort()
        self._last_raw[ch] = s[4]
        return s[4]

    @property
    def sensors_ok(self):
        """Датчики, похоже, подключены: хоть один канал не упёрся в край шкалы АЦП."""
        return any(20 < v < 4075 for v in self._last_raw if v is not None)

    @property
    def pcf_ok(self):
        return self._pcf_ok

    def button_pressed(self):
        return self.button.value() == 1

    # ---------------- расходомер
    def _on_pulse(self, pin):
        now = time.ticks_ms()
        if self._last_pulse_ms:
            self._gap_ms = time.ticks_diff(now, self._last_pulse_ms)
        self._last_pulse_ms = now
        self._pulses += 1

    def take_pulses(self):
        total = self._pulses
        d = total - self._taken
        self._taken = total
        return d

    def flow_lpm(self):
        """Как flowInstantRate(): 60000 / (интервал_мс × имп/л); 0 — если импульсов давно нет."""
        last, gap = self._last_pulse_ms, self._gap_ms
        if not last or not gap or time.ticks_diff(time.ticks_ms(), last) > FLOW_IDLE_MS:
            return 0.0
        return 60000.0 / (gap * PULSES_PER_LITER)

    def ms_since_pulse(self):
        if not self._last_pulse_ms:
            return -1
        return time.ticks_diff(time.ticks_ms(), self._last_pulse_ms)

    # ---------------- диагностика
    def faults(self):
        f = set()
        if not self._pcf_ok:
            f.add("valves")
        return f

    def all_off(self):
        self.open_valves = [False] * self.n
        self.pump_on = self.drain_on = self.fill_on = False
