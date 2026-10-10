"""app.py — главный цикл контроллера на ESP32.

Собирает всё вместе: железо (hw.py), часы, Wi-Fi, логику полива (device.py —
та же, что в эмуляторе), очередь отчётов на время без связи, клиент Tuya и
OTA. Полив не зависит от сети: цикл идёт каждую секунду, облако — когда есть.
"""
import gc
import json
import os
import time

from device import Device, FW_VERSION
from outbox import Outbox
from reporter import Reporter
from spec import Spec

ROOT = ""                     # корень файловой системы ("" на плате; симуляция подменяет)
MAX_TICKS = None              # ограничение числа тиков (только для симуляции)
TICK_MS = 1000
SYS_INFO_EVERY = 600          # с
BUTTON_PORTAL_SEC = 5         # удерживать кнопку — портал Wi-Fi
STATE_OK_AFTER = 60           # с онлайн → считаем новую прошивку рабочей (OTA)


def log(msg):
    t = time.localtime()
    print("%02d:%02d:%02d %s" % (t[3], t[4], t[5], msg))


def _mount_sd():
    """SD-карта на VSPI (CS 5). → '/sd' или None."""
    try:
        from machine import SDCard
        sd = SDCard(slot=2, sck=18, mosi=23, miso=19, cs=5)
        os.mount(sd, "/sd")
        return "/sd"
    except Exception as e:
        log("sd: нет карты (%s)" % e)
        return None


class App:
    def __init__(self):
        from hw import Hardware
        from clock import Clock
        from wifi import Wifi
        from tuya import Tuya
        from ota import Ota

        self.hw = Hardware()
        self.clock = Clock(self.hw.i2c, log)
        self.wifi = Wifi(log)
        self.sd = _mount_sd()
        store = self.sd or ROOT
        self.spec = Spec(ROOT + "/app/dp.json")
        self.dev = Device(self.hw, state_path=store + "/state.json", spec=self.spec)
        self.outbox = Outbox(store + "/pending.jsonl")
        self.reporter = Reporter()

        creds = self._creds()
        self.tuya = Tuya(creds["pid"], creds["uuid"], creds["authkey"], version=FW_VERSION,
                         storage=ROOT + "/tuya_state.json", log=log) if creds else None
        self.ota = None
        if self.tuya:
            self.tuya.on_connected = self._on_connected
            self.tuya.on_dps = self._on_dps
            self.tuya.on_reset = lambda: log("tuya: устройство удалено из приложения, ждём новую привязку")
            self.tuya.on_qrcode = lambda url: log("tuya: привязка — QR " + url)
            self.ota = Ota(self.tuya, FW_VERSION, log, on_before_reboot=self._shutdown)
            self.tuya.on_protocol = self.ota.on_protocol

        self.now = 0.0            # монотонные секунды (без переполнения ticks)
        self._last_ms = time.ticks_ms()
        self._sys_at = -SYS_INFO_EVERY
        self._online_since = None
        self._button_since = None
        self._gc_at = 0

    @staticmethod
    def _creds():
        try:
            with open(ROOT + "/tuya.json") as f:
                c = json.load(f)
            return c if c.get("uuid") and c.get("authkey") else None
        except (OSError, ValueError):
            log("tuya: нет /tuya.json (pid, uuid, authkey) — работаем без облака")
            return None

    # ---------------- облако
    def _on_connected(self):
        log("облако: подключено")
        self.outbox.flush(self.tuya.push, now=self.clock.unix())
        for p in self.dev.report(full=True):
            self._queue(p, full=True)
        self._sys_at = -SYS_INFO_EVERY
        self._online_since = self.now
        if self.ota:
            self.ota.on_connected()

    def _on_dps(self, dps):
        for dp_id, value in dps.items():
            try:
                code, v = self.spec.decode(dp_id, value)
                self.dev.apply_dp(code, v, self.now, self.clock.unix())
            except (ValueError, KeyError) as e:
                log("DP %s=%r отклонён: %s" % (dp_id, value, e))
        for p in self.dev.report():
            self._queue(p)

    def _queue(self, packet, full=False):
        allowed = self.reporter.filter(packet, self.now, full=full)
        if allowed and self.tuya:
            self.outbox.put({self.spec.by_code[c].id: v for c, v in allowed.items()}, self.clock.unix())

    def _sys_info(self):
        extra = {"heap": gc.mem_free(), "rssi": self.wifi.rssi(), "sd": 1 if self.sd else 0,
                 "pending": self.outbox.count}
        self._queue({"sys_info": self.dev.sys_info(self.clock.unix(), extra)}, full=True)
        self._sys_at = self.now

    def _shutdown(self):
        """Перед перезагрузкой: всё выключить, настройки сохранить."""
        self.dev.loads_off()
        self.dev.save()
        self.hw.all_off()

    # ---------------- кнопка и индикация
    def _button(self):
        if self.hw.button_pressed():
            if self._button_since is None:
                self._button_since = self.now
            elif self.now - self._button_since >= BUTTON_PORTAL_SEC:
                log("кнопка: портал настройки Wi-Fi")
                self._shutdown()
                self.wifi.portal(self.hw)
                import machine
                machine.reset()
        else:
            self._button_since = None

    def _led(self, up):
        online = self.tuya is not None and self.tuya.online
        if online:
            self.hw.led.value(1)
        elif up:
            self.hw.led.value(int(self.now) % 2)        # мигает: сеть есть, облака нет
        else:
            self.hw.led.value(int(self.now * 4) % 4 == 0)  # частое мигание: нет Wi-Fi

    # ---------------- главный цикл
    def run(self):
        from machine import WDT
        wdt = WDT(timeout=120000)
        if not self.wifi.conf or self.hw.button_pressed():
            self.wifi.portal(self.hw)
            import machine
            machine.reset()
        self.wifi.connect()
        log("Drip Irrigation %s запущен" % FW_VERSION)

        ticks = 0
        while MAX_TICKS is None or ticks < MAX_TICKS:
            ticks += 1
            wdt.feed()
            ms = time.ticks_ms()
            dt = time.ticks_diff(ms, self._last_ms) / 1000.0
            self._last_ms = ms
            self.now += dt

            up = self.wifi.tick()
            if up:
                self.clock.sync_ntp()
                if self.tuya:
                    self.tuya.loop()
                    if self.tuya.online and self.outbox.count:
                        self.outbox.flush(self.tuya.push, now=self.clock.unix())
                    if self.ota:
                        self.ota.tick()
            elif self.tuya and self.tuya.online:
                self.tuya.set_paused(True)      # Wi-Fi пропал — не ждём таймаута MQTT
                self.tuya.set_paused(False)

            faults = self.hw.faults() | self.clock.faults()
            if self.dev.hw_faults != faults:
                self.dev.hw_faults = set(faults)
            self.dev.tick(self.now, self.clock.unix(), dt)
            for p in self.dev.report():
                self._queue(p)
            if self.now - self._sys_at >= SYS_INFO_EVERY:
                self._sys_info()

            self._button()
            self._led(up)

            # 🔁 новая прошивка после OTA считается удачной, если побыла онлайн минуту
            if self._online_since is not None and self.now - self._online_since > STATE_OK_AFTER:
                self._online_since = None
                _mark_boot_ok()

            if self.now - self._gc_at > 30:
                gc.collect()
                self._gc_at = self.now
            spent = time.ticks_diff(time.ticks_ms(), ms)
            if spent < TICK_MS:
                time.sleep_ms(TICK_MS - spent)


def _mark_boot_ok():
    try:
        os.remove(ROOT + "/ota/boots")
    except OSError:
        pass
    try:
        import ota
        ota._rmtree(ROOT + "/app_prev")
    except Exception:
        pass


def run():
    App().run()
