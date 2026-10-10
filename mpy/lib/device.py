"""device.py — логика контроллера полива, перенесённая из прошивки ESP32.

Источник: DripIrrigation-Cloud/DripIrrigation (irrigation.cpp, DripIrrigation.ino,
valves.cpp, sensors.h/.cpp, objects.cpp, telegram.cpp). Где поведение повторено
1:1, в комментарии указана исходная функция. Контроль засора фильтра —
flowmon.py (порт objects.cpp, fm*).

Уведомления, которые прошивка слала в Telegram, здесь становятся событиями
(DP event, JSON с кодом — см. docs/dp.md). Диалоги бота (калибровка, поиск датчика) стали «мастерами»:
команда приходит JSON-строкой в DP wizard, состояние уходит в wizard_state.
"""
import json
import struct

from flowmon import FlowMonitor
from spec import Spec


def dumps(obj):
    """Компактный JSON; в MicroPython нет ensure_ascii/indent, separators есть не везде."""
    try:
        return json.dumps(obj, separators=(",", ":"))
    except TypeError:
        return json.dumps(obj)


def merge(d, **kw):
    """{**d, **kw} — в MicroPython распаковки словаря в литерале нет."""
    out = dict(d)
    out.update(kw)
    return out


# ---- константы из прошивки (objects.h / timing.h) ----
FW_VERSION = "1.0.1"    # версия прошивки — уходит в sys_info и в активацию Tuya (softVer)
MODE_AUTO, MODE_ON, MODE_OFF, MODE_GREENHOUSE = "auto", "on", "off", "greenhouse"
V_INIT, V_OPEN_HUM, V_CLOSE_HUM, V_HYST, V_FORCED_OPEN, V_FORCED_CLOSE = (
    "init", "open_hum", "close_hum", "hyst", "forced_open", "forced_close")

FILLING_WAIT = 3        # с — импульс заливки бака
DRAIN_TIMEOUT = 12      # с — пролив дренажа
PUMP_TIMEOUT = 30       # с — пусковой режим насоса
PULSES_PER_LITER = 450  # имп./л — как FLOW_PULSES_PER_LITER в прошивке
TIMEOUT_WAIT = 18000    # с — после стольких секунд «всё закрыто» первое открытие делает пролив
HUM_AUTOCAL_CONFIRM = 3
SEARCH_DELTA = 300      # АЦП — порог «этот датчик вынули из воды» (telegram.cpp, SearchDetect)
CALIB_MIN_SPAN = 100    # АЦП — минимальный размах калибровки (telegram.cpp, CalibFinish)

FLOW_SILENCE_MIN = 2    # мин — насос работает, клапаны открыты, импульсов нет → «расходомер молчит»


CHANNEL_FIELDS = ("name", "border", "mode", "min_val", "max_val")
CONFIG_FIELDS = ("run_on_rain", "run_on_night", "delta_calib", "delta_hum", "boost_pump_valves",
                 "utime_all_closed", "flow_session", "flow_total", "clean_flow_per_valve",
                 "clean_flow_drain", "clog_threshold", "flow_monitor", "autocal_no_delay")


class Channel:
    def __init__(self, name="🌱 Растение", border=60, mode=MODE_AUTO, min_val=1024, max_val=1024):
        # название грядки живёт в облачных свойствах устройства (его хранит панель);
        # здесь — только для консоли эмулятора
        self.name = name
        self.border = border
        self.mode = mode
        self.min_val = min_val
        self.max_val = max_val


class Config:
    """Аналог struct Config (objects.h) — то, что прошивка хранит на SD/флеше."""

    def __init__(self):
        self.run_on_rain = True
        self.run_on_night = False
        self.delta_calib = 15
        self.delta_hum = 5
        self.boost_pump_valves = 9
        self.channels = [Channel() for _ in range(8)]
        self.utime_all_closed = 0
        self.flow_session = 0.0
        self.flow_total = 0.0
        self.clean_flow_per_valve = 0.0
        self.clean_flow_drain = 0.0
        self.clog_threshold = 50
        self.flow_monitor = True
        self.autocal_no_delay = False

    def to_dict(self):
        d = {k: getattr(self, k) for k in CONFIG_FIELDS}
        d["channels"] = [{k: getattr(c, k) for k in CHANNEL_FIELDS} for c in self.channels]
        return d

    @staticmethod
    def load(path):
        cfg = Config()
        try:
            with open(path, encoding="utf-8") as f:
                d = json.load(f)
            for k in CONFIG_FIELDS:
                if k in d:
                    setattr(cfg, k, d[k])
            for c, dc in zip(cfg.channels, d.get("channels", [])):
                for k in CHANNEL_FIELDS:
                    if k in dc:
                        setattr(c, k, dc[k])
        except (OSError, ValueError, TypeError, KeyError):
            return Config()
        return cfg

    def save(self, path):
        # сначала во временный файл: сбой питания посреди записи не убьёт настройки
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(dumps(self.to_dict()))
        try:
            import os
            try:
                os.remove(path)
            except OSError:
                pass
            os.rename(tmp, path)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# 🧠 irrigation.cpp: decideValve — чистое решение по каналу
# ---------------------------------------------------------------------------
def decide_valve(mode, humidity, border, delta_hum, prev):
    """Возвращает (action, new_state, notify); action: open | close | hold."""
    if mode in (MODE_AUTO, MODE_GREENHOUSE):
        if humidity < border - delta_hum:
            return "open", V_OPEN_HUM, prev != V_OPEN_HUM
        if humidity > border + delta_hum:
            return "close", V_CLOSE_HUM, prev != V_CLOSE_HUM
        return "hold", V_HYST, prev not in (V_OPEN_HUM, V_CLOSE_HUM, V_HYST)
    if mode == MODE_ON:
        return "open", V_FORCED_OPEN, prev != V_FORCED_OPEN
    return "close", V_FORCED_CLOSE, prev != V_FORCED_CLOSE


def arduino_map(x, in_min, in_max, out_min, out_max):
    # Arduino map(): целочисленное деление с усечением к нулю
    num = (x - in_min) * (out_max - out_min)
    den = in_max - in_min
    q = abs(num) // abs(den)
    if (num < 0) != (den < 0):
        q = -q
    return q + out_min


class Device:
    def __init__(self, world, state_path=None, spec=None):
        self.spec = spec or Spec()
        self.n = self.spec.channels
        self.world = world
        self.state_path = state_path
        self.cfg = Config.load(state_path) if state_path else Config()
        self.events = []
        self.hw_faults = set()          # rtc | sd | valves — как faults.h
        self._last_report = {}
        self.reboot(initial=True)

    # =====================================================================
    # Запуск / перезагрузка (systemInit + RAM-состояние)
    # =====================================================================
    def reboot(self, initial=False):
        self.low = [c.min_val for c in self.cfg.channels]
        self.high = [c.max_val for c in self.cfg.channels]
        self.curr = [0] * self.n
        self.lo_cnt = [0] * self.n
        self.hi_cnt = [0] * self.n
        self.lo_cand = [0] * self.n
        self.hi_cand = [0] * self.n
        self.old_mode = [V_INIT] * self.n
        self.is_close = [True] * self.n
        self.is_open_flag = False
        self.pump = False
        self.pump_start = None
        self.drain_active = False
        self.drain_start = 0.0
        self.fill_active = False
        self.fill_start = 0.0
        self.rain_now = self.night_now = False
        self.old_rmode = self.old_nmode = False
        self.flow_session = self.cfg.flow_session
        self.flow_rate = 0.0
        self.fm = FlowMonitor(self.cfg)
        self.flow_pulses = 0
        self._pulse_frac = 0.0             # импульсов расходомера с включения
        self.last_pulse_at = None        # unix последнего импульса
        self.flow_silent = False         # тревога «расходомер молчит»
        self._silent_min = 0
        self.boot_unix = None
        self.fault_shutdown_done = False
        self.wizard = {"op": "idle"}
        self.search_snapshot = None
        self.last_minute = None
        self.world.open_valves = [False] * self.n
        self.world.drain_on = False
        self.world.pump_on = False
        self.world.fill_on = False
        if not initial:
            self.event("reboot")

    @property
    def clogged(self):
        return self.fm.alert

    def save(self):
        self.cfg.flow_session = self.flow_session
        if self.state_path:
            self.cfg.save(self.state_path)

    def event(self, code, **fields):
        """Событие для DP event: JSON с кодом, без текста. Текст, названия грядок
        и перевод подставляет панель — так событие всегда влезает в 255 байт."""
        self.events.append(dumps(merge({"t": code}, **fields)))

    # =====================================================================
    # sensors.cpp / sensors.h
    # =====================================================================
    def percent(self, i):
        frm = self.high[i] + self.cfg.delta_calib   # сухо → 0 %
        to = self.low[i] - self.cfg.delta_calib     # вода → 100 %
        if frm == to:
            return 0
        return max(0, min(100, arduino_map(self.curr[i], frm, to, 0, 100)))

    def read_all(self):
        self.curr = [self.world.adc(i) for i in range(self.n)]

    def set_low_high(self, i, lo, hi):
        self.low[i], self.high[i] = lo, hi
        self.lo_cnt[i] = self.hi_cnt[i] = 0

    def auto_extend(self, i, confirm):
        confirm = max(1, confirm)
        changed = False
        val = self.curr[i]
        if val < self.low[i]:
            if self.lo_cnt[i] == 0 or val > self.lo_cand[i]:
                self.lo_cand[i] = val
            self.lo_cnt[i] = min(255, self.lo_cnt[i] + 1)
            if self.lo_cnt[i] >= confirm:
                self.low[i] = max(0, self.lo_cand[i] - self.cfg.delta_calib)
                self.lo_cnt[i] = 0
                changed = True
        else:
            self.lo_cnt[i] = 0
        if val > self.high[i]:
            if self.hi_cnt[i] == 0 or val < self.hi_cand[i]:
                self.hi_cand[i] = val
            self.hi_cnt[i] = min(255, self.hi_cnt[i] + 1)
            if self.hi_cnt[i] >= confirm:
                self.high[i] = min(4095, self.hi_cand[i] + self.cfg.delta_calib)
                self.hi_cnt[i] = 0
                changed = True
        else:
            self.hi_cnt[i] = 0
        return changed

    def calibration_in_progress(self):
        return self.wizard.get("op") in ("calib", "search") and self.wizard.get("step") not in ("done", None)

    def auto_calibrate_bounds(self):
        if self.calibration_in_progress():
            return
        confirm = 1 if self.cfg.autocal_no_delay else HUM_AUTOCAL_CONFIRM
        for i in range(self.n):
            if self.auto_extend(i, confirm):
                self.cfg.channels[i].min_val = self.low[i]
                self.cfg.channels[i].max_val = self.high[i]
                self.save()

    # =====================================================================
    # valves.cpp
    # =====================================================================
    def count_open(self):
        return sum(not c for c in self.is_close)

    def _set_pump(self, on):
        if on != self.pump:
            self.pump = on
            self.world.pump_on = on          # реле насоса (на плате — GPIO)

    def pump_state(self):
        """DP pump_state: off | start (пусковые 30 с) | valves (по порогу) | drain (пролив)."""
        if not self.pump:
            return "off"
        if self.drain_active:
            return "drain"
        if self.pump_start is not None:
            return "start"
        return "valves"

    def stop_pump_if_need(self):
        if self.drain_active:
            return
        if self.pump_start is not None:
            self._set_pump(True)
            return
        n = self.cfg.boost_pump_valves
        self._set_pump(1 <= n <= self.n and self.count_open() >= n)

    def valve_open(self, i, now, unix):
        self.world.open_valves[i] = True
        self.is_open_flag = True
        if self.is_close[i]:
            self._set_pump(True)
            self.pump_start = now
            if self.count_open() == 0:
                self.flow_session = 0.0          # flowResetSession
        self.is_close[i] = False
        if self.cfg.utime_all_closed:
            if unix > self.cfg.utime_all_closed and unix - self.cfg.utime_all_closed > TIMEOUT_WAIT:
                self.spillage(now)
            self.cfg.utime_all_closed = 0
            self.save()

    def valve_close(self, i, unix):
        self.world.open_valves[i] = False
        self.is_close[i] = True
        self.stop_pump_if_need()
        if all(self.is_close) and self.cfg.utime_all_closed == 0:
            self.cfg.utime_all_closed = unix
            self.cfg.flow_total += self.flow_session     # flowAddToTotal
            self.save()

    def spillage(self, now):
        if self.drain_active:
            return
        self.event("drain_start")
        self.world.drain_on = True
        self._set_pump(True)
        self.drain_start = now
        self.drain_active = True

    def spillage_tick(self, now):
        if self.drain_active and now - self.drain_start >= DRAIN_TIMEOUT:
            self.world.drain_on = False
            self.drain_active = False
            self.stop_pump_if_need()
            self.event("drain_end")

    def loads_off(self):
        self.pump_start = None
        for i in range(self.n):
            self.world.open_valves[i] = False
            self.is_close[i] = True
        self.world.drain_on = False
        self.world.fill_on = False
        self.drain_active = self.fill_active = False
        self._set_pump(False)

    # =====================================================================
    # DripIrrigation.ino
    # =====================================================================
    def check_valve(self, i, now, unix):
        p = self.percent(i)
        ch = self.cfg.channels[i]
        action, new_state, notify = decide_valve(ch.mode, p, ch.border, self.cfg.delta_hum, self.old_mode[i])
        if action == "open":
            self.valve_open(i, now, unix)
        elif action == "close":
            self.valve_close(i, unix)
        if notify:
            self.old_mode[i] = new_state
            self.event("valve", ch=i + 1, s=new_state, h=p)

    def start_tank_fill(self, now):
        if self.fill_active:
            return
        self.fill_active = True
        self.fill_start = now
        self.world.fill_on = True
        self.event("tank_fill")

    def check_weather(self, now):
        blocked = night_block = rain_block = False
        if self.world.rain:
            if not self.rain_now:
                self.event("rain_start")
                self.rain_now = True
            if not self.cfg.run_on_rain:
                blocked = rain_block = True
                if not self.old_rmode:
                    self.old_rmode = True
                    self.event("rain_block")
        else:
            if self.rain_now:
                self.rain_now = False
                self.event("rain_end")
            if self.old_rmode:
                self.old_rmode = False
                self.event("rain_resume")
        if self.world.night:
            if not self.night_now:
                self.night_now = True
                self.event("night_start")
            if not self.cfg.run_on_night:
                blocked = night_block = True
                if not self.old_nmode:
                    self.old_nmode = True
                    self.event("night_block")
                    if self.is_open_flag:            # valveOpened() со сбросом
                        self.is_open_flag = False
                        self.start_tank_fill(now)
        else:
            if self.night_now:
                self.night_now = False
                self.event("day_start")
            if self.old_nmode:
                self.old_nmode = False
                self.event("night_resume")
                if self.rain_now and not self.cfg.run_on_rain:
                    self.event("rain_still")
        return blocked, night_block, rain_block

    def control_valves(self, weather, now, unix):
        blocked, night_block, rain_block = weather
        for i in range(self.n):
            mode = self.cfg.channels[i].mode
            if not blocked or (not night_block and rain_block and mode in (MODE_GREENHOUSE, MODE_ON)):
                self.check_valve(i, now, unix)
            else:
                self.valve_close(i, unix)
                if self.old_mode[i] != V_FORCED_CLOSE:
                    self.old_mode[i] = V_FORCED_CLOSE
                    self.event("valve", ch=i + 1, s=V_FORCED_CLOSE, w=1)

    def _flow_silence_minute(self, unix):
        """Насос работает, клапаны открыты, а импульсов нет FLOW_SILENCE_MIN минут —
        датчик залип или забит. Событие один раз, второе — когда импульсы вернулись."""
        expect = self.pump and self.count_open() > 0 and not self.drain_active
        silent = expect and (self.last_pulse_at is None or unix - self.last_pulse_at >= 60)
        self._silent_min = self._silent_min + 1 if silent else 0
        if self._silent_min >= FLOW_SILENCE_MIN and not self.flow_silent:
            self.flow_silent = True
            self.event("flow_silent")
        elif self.flow_silent and not silent and self.last_pulse_at is not None:
            self.flow_silent = False
            self.event("flow_ok")

    # =====================================================================
    # loop(): now — секунды эмулятора (аналог millis), unix — время суток
    # =====================================================================
    def tick(self, now, unix, dt):
        if self.hw_faults:
            if not self.fault_shutdown_done:
                self.fault_shutdown_done = True
                self.loads_off()
                self.event("hw_fault", f=sorted(self.hw_faults))
            return
        self.fault_shutdown_done = False

        # ⏱️ неблокирующие таймеры
        if self.fill_active and now - self.fill_start >= FILLING_WAIT:
            self.fill_active = False
            self.world.fill_on = False
        self.spillage_tick(now)
        if self.pump_start is not None and now - self.pump_start > PUMP_TIMEOUT:
            self.pump_start = None
            self.stop_pump_if_need()

        if self.boot_unix is None:
            self.boot_unix = unix

        # 💧 расходомер. На плате (hw.py) импульсы считает прерывание: take_pulses()
        #    отдаёт накопленное с прошлого тика, flow_lpm() — мгновенную скорость.
        #    В эмуляторе импульсов нет — их даёт модель мира из скорости потока.
        take = getattr(self.world, "take_pulses", None)
        if take is not None:
            pulses = take()
            self.flow_rate = self.world.flow_lpm()
            self.flow_session += pulses / PULSES_PER_LITER
        else:
            self.flow_rate = self.world.flow_lpm() if self.pump else 0.0
            self.flow_session += self.flow_rate * dt / 60.0
            self._pulse_frac += self.flow_rate * dt / 60.0 * PULSES_PER_LITER
            pulses = int(self._pulse_frac)
            self._pulse_frac -= pulses
            if not getattr(self.world, "flow_sensor_ok", True):
                pulses = 0
        if pulses > 0:
            self.flow_pulses += pulses
            self.last_pulse_at = unix

        # 🧽 контроль засора фильтра — каждую секунду, по счётчику импульсов
        for ev in self.fm.tick(now, self.flow_pulses, self.count_open(), self.drain_active,
                               self.pump_start is not None, self.fill_active):
            if ev[0] == "clog":
                self.event("clog", r=round(ev[1], 3), e=round(ev[2], 3))
            else:
                self.event("clog_end", r=round(ev[1], 3))
        if self.fm.dirty:
            self.fm.dirty = False
            self.save()

        minute = int(unix // 60)
        if minute != self.last_minute:
            self.last_minute = minute
            self.world.step_minute(minute % 1440)
            self.read_all()
            self.auto_calibrate_bounds()
            self.control_valves(self.check_weather(now), now, unix)
            self._flow_silence_minute(unix)
            self.cfg.flow_session = self.flow_session

    # =====================================================================
    # Команды из облака (вместо newMsg/FSM бота)
    # =====================================================================
    def apply_dp(self, code, value, now, unix):
        ch_cfg = None
        base, _, num = code.rpartition("_")
        if num.isdigit() and base in ("mode", "border"):
            ch_cfg = self.cfg.channels[int(num) - 1]
        if ch_cfg is not None:
            if base == "mode":
                ch_cfg.mode = value
            else:
                ch_cfg.border = value
            self.save()
            return
        if code in ("run_on_rain", "run_on_night", "delta_hum", "boost_pump_valves",
                    "clog_threshold", "flow_monitor", "autocal_no_delay", "delta_calib"):
            setattr(self.cfg, code, value)
            if code == "boost_pump_valves":
                self.stop_pump_if_need()
            self.save()
        elif code == "mode_all":
            for c in self.cfg.channels:
                c.mode = value
            self.save()
        elif code == "command":
            self._command(value, now, unix)
        elif code == "wizard":
            self._wizard(value)
        else:
            raise ValueError("DP %s не обрабатывается" % code)

    def _command(self, cmd, now, unix):
        if cmd == "restart":
            self.loads_off()
            self.save()
            self.reboot()
        elif cmd == "reset_settings":
            # telegram.cpp, Dlg::Reset — те же значения по умолчанию
            keep = (self.cfg.flow_total, self.cfg.flow_session, self.cfg.utime_all_closed)
            self.cfg = Config()
            self.fm = FlowMonitor(self.cfg)
            self.cfg.flow_total, self.cfg.flow_session, self.cfg.utime_all_closed = keep
            for i in range(self.n):
                self.set_low_high(i, 1024, 1024)
            self.save()
            self.event("reset_settings")
        elif cmd == "clear_flow":
            self.flow_session = 0.0
            self.cfg.flow_total = 0.0
            self.save()
            self.event("clear_flow")
        elif cmd == "filter_cleaned":
            self.fm.recalibrate()
            self.fm.dirty = False
            self.save()
            self.event("filter_cleaned")
        elif cmd == "drain":
            self.spillage(now)      # /Spillage бота: ручной пролив дренажа

    # ---- мастера калибровки и поиска (telegram.cpp, Dlg::Calib*/Search*/CalibManual) ----
    def _wizard(self, text):
        try:
            cmd = json.loads(text)
            op = cmd["op"]
        except (ValueError, KeyError, TypeError):
            self._wz({"op": "error", "err": "bad_json"})
            return
        step = cmd.get("step")
        # ошибка прошлой команды (bad_step) не должна тянуться в следующее состояние
        w = {k: v for k, v in self.wizard.items() if k != "err"}

        if op == "manual":
            ch, lo, hi = int(cmd["ch"]) - 1, int(cmd["min"]), int(cmd["max"])
            if not (0 <= ch < self.n and 0 <= lo <= 4096 and 0 <= hi <= 4096):
                self._wz({"op": "manual", "step": "done", "ok": False, "err": "range"})
                return
            self.set_low_high(ch, lo, hi)
            self.cfg.channels[ch].min_val, self.cfg.channels[ch].max_val = lo, hi
            self.save()
            self._wz({"op": "manual", "ch": ch + 1, "step": "done", "ok": True, "min": lo, "max": hi})
            return

        if step == "cancel":
            if w.get("op") == "calib":
                i = w["ch"] - 1
                self.set_low_high(i, self.cfg.channels[i].min_val, self.cfg.channels[i].max_val)
            self._wz({"op": w.get("op", op), "ch": w.get("ch"), "step": "done", "ok": False, "err": "cancelled"})
            return

        if op == "calib":
            if step == "start":
                ch = int(cmd.get("ch", 0))
                if not 1 <= ch <= self.n:
                    self._wz({"op": "calib", "step": "done", "ok": False, "err": "bad_channel"})
                    return
                self._wz({"op": "calib", "ch": ch, "step": "wet"})
            elif w.get("op") == "calib" and step == "next" and w["step"] == "wet":
                i = w["ch"] - 1
                self.read_all()
                self.low[i] = self.curr[i]
                self._wz(merge(w, step="dry", wet=self.low[i]))
            elif w.get("op") == "calib" and step == "next" and w["step"] == "dry":
                i = w["ch"] - 1
                self.read_all()
                self.high[i] = self.curr[i]
                self._wz(merge(w, step="finish", dry=self.high[i]))
            elif w.get("op") == "calib" and step == "finish" and w["step"] == "finish":
                i = w["ch"] - 1
                if abs(self.high[i] - self.low[i]) < CALIB_MIN_SPAN:
                    self.set_low_high(i, self.cfg.channels[i].min_val, self.cfg.channels[i].max_val)
                    self._wz({"op": "calib", "ch": w["ch"], "step": "done", "ok": False, "err": "span"})
                else:
                    self.cfg.channels[i].min_val, self.cfg.channels[i].max_val = self.low[i], self.high[i]
                    self.save()
                    self._wz({"op": "calib", "ch": w["ch"], "step": "done", "ok": True,
                              "min": self.low[i], "max": self.high[i]})
            else:
                self._wz(merge(w, err="bad_step"))
            return

        if op == "search":
            if step == "start":
                self._wz({"op": "search", "step": "wet"})
            elif w.get("op") == "search" and step == "next" and w["step"] == "wet":
                self.read_all()
                self.search_snapshot = list(self.curr)
                self._wz({"op": "search", "step": "dry"})
            elif w.get("op") == "search" and step == "next" and w["step"] == "dry":
                self.read_all()
                found = next((i for i in range(self.n)
                              if abs(self.search_snapshot[i] - self.curr[i]) > SEARCH_DELTA), -1)
                if found < 0:
                    self._wz({"op": "search", "step": "done", "ok": False, "err": "not_found"})
                else:
                    self._wz({"op": "search", "step": "done", "ok": True, "found": found + 1})
            else:
                self._wz(merge(w, err="bad_step"))
            return

        self._wz({"op": "error", "err": "unknown_op"})

    def _wz(self, state):
        # 📏 только коды, без текста: тексты (и перевод) — забота панели,
        #    а JSON гарантированно влезает в 255 байт строкового DP
        self.wizard = {k: v for k, v in state.items() if v is not None}

    # =====================================================================
    # Снимок DP и отчёт об изменениях
    # =====================================================================
    def sys_info(self, unix, extra=None):
        """DP sys_info — то, что бот показывал в /status и /WaterFlow как диагностику.
        extra — что знает только платформа: heap, rssi, sd, pending (очередь офлайн)."""
        info = {
            "fw": FW_VERSION,
            "up": int(unix - self.boot_unix) if self.boot_unix is not None else 0,
            "t": int(unix),
            "rtc": 0 if "rtc" in self.hw_faults else 1,
            "pulses": self.flow_pulses,
            "last_pulse": int(unix - self.last_pulse_at) if self.last_pulse_at is not None else -1,
        }
        if extra:
            info.update(extra)
        return dumps(info)

    def dp_snapshot(self):
        s = self.spec
        out = {
            "rain": self.rain_now, "night": self.night_now, "pump": self.pump,
            "pump_state": self.pump_state(),
            "drain": self.drain_active, "fill": self.fill_active,
            "flow_rate": self.flow_rate, "flow_session": self.flow_session,
            "flow_total": self.cfg.flow_total,
            "fault": s.bitmap("fault", self.hw_faults | ({"filter_clog"} if self.fm.alert else set())),
            "filter_baseline": self.cfg.clean_flow_per_valve,
            "run_on_rain": self.cfg.run_on_rain, "run_on_night": self.cfg.run_on_night,
            "delta_hum": self.cfg.delta_hum, "delta_calib": self.cfg.delta_calib,
            "boost_pump_valves": self.cfg.boost_pump_valves,
            "clog_threshold": self.cfg.clog_threshold, "flow_monitor": self.cfg.flow_monitor,
            "autocal_no_delay": self.cfg.autocal_no_delay,
            "wizard_state": dumps(self.wizard),
            "adc_raw": struct.pack(">" + "H" * (3 * self.n),
                                   *[v for i in range(self.n) for v in (self.curr[i], self.low[i], self.high[i])]),
        }
        for i in range(self.n):
            n = i + 1
            c = self.cfg.channels[i]
            out["humidity_%d" % n] = self.percent(i)
            out["valve_%d" % n] = self.old_mode[i]
            out["mode_%d" % n] = c.mode
            out["border_%d" % n] = c.border
        return {k: s.encode(k, v) for k, v in out.items()}

    def report(self, full=False):
        """DP, изменившиеся с прошлого отчёта, плюс по одному DP event на каждое событие.

        Возвращает список пакетов {code: value}: сначала изменения состояния,
        затем события (каждое отдельным пакетом — так облако сохранит их все).
        """
        snap = self.dp_snapshot()
        changed = {k: v for k, v in snap.items() if full or self._last_report.get(k) != v}
        self._last_report = snap
        packets = [changed] if changed else []
        while self.events:
            packets.append({"event": self.spec.encode("event", self.events.pop(0))})
        return packets
