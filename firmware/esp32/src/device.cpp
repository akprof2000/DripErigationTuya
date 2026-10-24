// device.cpp 🌱💧 Логика полива — перенос mpy/lib/device.py (и старой прошивки) на C++
#include "device.h"
#include "dp.h"
#include "log.h"

static int arduinoMap(long x, long inMin, long inMax, long outMin, long outMax) {
  return (int)((x - inMin) * (outMax - outMin) / (inMax - inMin) + outMin);
}

Device::Device(Hardware& hw, Config& cfg, fs::FS& fs, const char* statePath)
    : _hw(hw), _cfg(cfg), _fs(fs), _statePath(statePath), _fm(cfg) {}

void Device::begin() { rebootState(); }

// ---------------------------------------------------------------- старт / перезагрузка
void Device::rebootState() {
  for (uint8_t i = 0; i < NUM_CHANNELS; i++) {
    _low[i] = _cfg.channels[i].minVal;
    _high[i] = _cfg.channels[i].maxVal;
    _curr[i] = 0;
    _loCnt[i] = _hiCnt[i] = 0;
    _loCand[i] = _hiCand[i] = 0;
    _oldMode[i] = VState::Init;
    _isClose[i] = true;
    _searchSnapshot[i] = 0;
  }
  _isOpenFlag = false;
  _pump = false;
  _pumpStarting = false;
  _drainActive = _fillActive = false;
  _rainNow = _nightNow = _oldRMode = _oldNMode = false;
  _flowSession = _cfg.flowSession;
  _flowRate = 0;
  _flowSilent = false;
  _silentMin = 0;
  _lastMinute = -1;
  _wizard.clear();
  _wizard["op"] = "idle";
  _hw.allOff();
}

void Device::save() {
  _cfg.flowSession = _flowSession;
  if (!_cfg.save(_fs, _statePath.c_str())) LOG_E("cfg: не сохранить %s", _statePath.c_str());
}

void Device::setFaults(uint8_t mask) { _faults = mask; }

// ---------------------------------------------------------------- события
void Device::event(const char* code, JsonObjectConst fields) {
  JsonDocument d;
  d["t"] = code;
  for (JsonPairConst kv : fields) d[kv.key()] = kv.value();
  String s;
  serializeJson(d, s);
  if (_evCount == MAX_EVENTS) {   // переполнение: теряем самое старое
    _evHead = (_evHead + 1) % MAX_EVENTS;
    _evCount--;
  }
  _events[(_evHead + _evCount) % MAX_EVENTS] = s;
  _evCount++;
}

void Device::eventSimple(const char* code) { event(code, JsonObjectConst()); }

bool Device::popEvent(String& json) {
  if (_evCount == 0) return false;
  json = _events[_evHead];
  _events[_evHead] = String();
  _evHead = (_evHead + 1) % MAX_EVENTS;
  _evCount--;
  return true;
}

// ---------------------------------------------------------------- датчики (sensors.cpp)
int Device::percent(uint8_t i) const {
  int from = _high[i] + _cfg.deltaCalib;   // сухо → 0 %
  int to = _low[i] - _cfg.deltaCalib;      // вода → 100 %
  if (from == to) return 0;
  int p = arduinoMap(_curr[i], from, to, 0, 100);
  return p < 0 ? 0 : (p > 100 ? 100 : p);
}

void Device::readAll() {
  for (uint8_t i = 0; i < NUM_CHANNELS; i++) _curr[i] = _hw.adc(i);
}

void Device::setLowHigh(uint8_t i, int lo, int hi) {
  _low[i] = lo;
  _high[i] = hi;
  _loCnt[i] = _hiCnt[i] = 0;
}

bool Device::autoExtend(uint8_t i, uint8_t confirm) {
  if (confirm < 1) confirm = 1;
  bool changed = false;
  int val = _curr[i];
  if (val < _low[i]) {
    if (_loCnt[i] == 0 || val > _loCand[i]) _loCand[i] = val;
    if (_loCnt[i] < 255) _loCnt[i]++;
    if (_loCnt[i] >= confirm) {
      int nl = _loCand[i] - _cfg.deltaCalib;
      _low[i] = nl < 0 ? 0 : nl;
      _loCnt[i] = 0;
      changed = true;
    }
  } else {
    _loCnt[i] = 0;
  }
  if (val > _high[i]) {
    if (_hiCnt[i] == 0 || val < _hiCand[i]) _hiCand[i] = val;
    if (_hiCnt[i] < 255) _hiCnt[i]++;
    if (_hiCnt[i] >= confirm) {
      int nh = _hiCand[i] + _cfg.deltaCalib;
      _high[i] = nh > 4095 ? 4095 : nh;
      _hiCnt[i] = 0;
      changed = true;
    }
  } else {
    _hiCnt[i] = 0;
  }
  return changed;
}

bool Device::calibrationInProgress() {
  const char* op = _wizard["op"] | "idle";
  const char* step = _wizard["step"] | "";
  bool active = strcmp(op, "calib") == 0 || strcmp(op, "search") == 0;
  return active && strcmp(step, "done") != 0 && step[0] != '\0';
}

void Device::autoCalibrateBounds() {
  if (calibrationInProgress()) return;
  uint8_t confirm = _cfg.autocalNoDelay ? 1 : HUM_AUTOCAL_CONFIRM;
  bool dirty = false;
  for (uint8_t i = 0; i < NUM_CHANNELS; i++) {
    if (autoExtend(i, confirm)) {
      _cfg.channels[i].minVal = _low[i];
      _cfg.channels[i].maxVal = _high[i];
      dirty = true;
      LOG_I("Канал %d: границы расширены до [%d; %d] (АЦП %d)", i + 1, _low[i], _high[i], _curr[i]);
    }
  }
  if (dirty) save();
}

// ---------------------------------------------------------------- клапаны (valves.cpp)
uint8_t Device::countOpen() const {
  uint8_t n = 0;
  for (bool c : _isClose) if (!c) n++;
  return n;
}

void Device::setPump(bool on) {
  if (on != _pump) {
    _pump = on;
    _hw.setPump(on);
    LOG_D("Насос: %s", on ? "ВКЛ" : "ВЫКЛ");
  }
}

const char* Device::pumpState() const {
  if (!_pump) return "off";
  if (_drainActive) return "drain";
  if (_pumpStarting) return "start";
  return "valves";
}

void Device::stopPumpIfNeed() {
  if (_drainActive) return;
  if (_pumpStarting) { setPump(true); return; }
  uint8_t n = _cfg.boostPumpValves;
  setPump(n >= 1 && n <= NUM_CHANNELS && countOpen() >= n);
}

void Device::valveOpen(uint8_t i, uint32_t nowMs, uint32_t unix) {
  _hw.setValve(i, true);
  _isOpenFlag = true;
  if (_isClose[i]) {
    if (_cfg.pumpStartSec) {   // пусковое окно: насос на pump_start_sec после открытия клапана
      setPump(true);
      _pumpStarting = true;
      _pumpStartMs = nowMs;
    } else {
      stopPumpIfNeed();   // без пускового окна — только по порогу boost_pump_valves
    }
    if (countOpen() == 0) _flowSession = 0;   // flowResetSession
  }
  _isClose[i] = false;
  if (_cfg.utimeAllClosed) {
    if (unix > _cfg.utimeAllClosed && unix - _cfg.utimeAllClosed > TIMEOUT_WAIT_S) spillage(nowMs);
    _cfg.utimeAllClosed = 0;
    save();
  }
}

void Device::valveClose(uint8_t i, uint32_t unix) {
  _hw.setValve(i, false);
  _isClose[i] = true;
  stopPumpIfNeed();
  if (countOpen() == 0 && _cfg.utimeAllClosed == 0) {
    _cfg.utimeAllClosed = unix;
    _cfg.flowTotal += _flowSession;   // flowAddToTotal
    save();
  }
}

void Device::spillage(uint32_t nowMs) {
  if (_drainActive) return;
  eventSimple("drain_start");
  _hw.setDrain(true);
  setPump(true);
  _drainStartMs = nowMs;
  _drainActive = true;
}

void Device::spillageTick(uint32_t nowMs) {
  if (_drainActive && nowMs - _drainStartMs >= DRAIN_TIMEOUT_MS) {
    _hw.setDrain(false);
    _drainActive = false;
    stopPumpIfNeed();
    eventSimple("drain_end");
  }
}

void Device::loadsOff() {
  _pumpStarting = false;
  for (uint8_t i = 0; i < NUM_CHANNELS; i++) _isClose[i] = true;
  _drainActive = _fillActive = false;
  _pump = false;
  _hw.allOff();
}

// ---------------------------------------------------------------- главный цикл (DripIrrigation.ino)
void Device::checkValve(uint8_t i, uint32_t nowMs, uint32_t unix) {
  int p = percent(i);
  const ChannelCfg& ch = _cfg.channels[i];
  const char* prev = _oldMode[i];
  const char* newState;
  bool notify;
  int action;   // 1 open, -1 close, 0 hold
  if (ch.mode == Mode::Auto || ch.mode == Mode::Greenhouse) {
    if (p < ch.border - _cfg.deltaHum) {
      action = 1; newState = VState::OpenHum; notify = prev != VState::OpenHum;
    } else if (p > ch.border + _cfg.deltaHum) {
      action = -1; newState = VState::CloseHum; notify = prev != VState::CloseHum;
    } else {
      action = 0; newState = VState::Hyst;
      notify = prev != VState::OpenHum && prev != VState::CloseHum && prev != VState::Hyst;
    }
  } else if (ch.mode == Mode::On) {
    action = 1; newState = VState::ForcedOpen; notify = prev != VState::ForcedOpen;
  } else {
    action = -1; newState = VState::ForcedClose; notify = prev != VState::ForcedClose;
  }
  if (action > 0) valveOpen(i, nowMs, unix);
  else if (action < 0) valveClose(i, unix);
  if (notify) {
    _oldMode[i] = newState;
    JsonDocument f;
    f["ch"] = i + 1;
    f["s"] = newState;
    f["h"] = p;
    event("valve", f.as<JsonObjectConst>());
  }
}

void Device::startTankFill(uint32_t nowMs) {
  if (_fillActive) return;
  _fillActive = true;
  _fillStartMs = nowMs;
  _hw.setFill(true);
  eventSimple("tank_fill");
}

void Device::checkWeather(uint32_t nowMs, bool& blocked, bool& nightBlock, bool& rainBlock) {
  blocked = nightBlock = rainBlock = false;
  if (_hw.rain()) {
    if (!_rainNow) { eventSimple("rain_start"); _rainNow = true; }
    if (!_cfg.runOnRain) {
      blocked = rainBlock = true;
      if (!_oldRMode) { _oldRMode = true; eventSimple("rain_block"); }
    } else if (_oldRMode) {   // дождь, но работу в дождь разрешили из приложения
      _oldRMode = false;
      eventSimple("rain_resume");
    }
  } else {
    if (_rainNow) { _rainNow = false; eventSimple("rain_end"); }
    if (_oldRMode) { _oldRMode = false; eventSimple("rain_resume"); }
  }
  if (_hw.night()) {
    if (!_nightNow) { _nightNow = true; eventSimple("night_start"); }
    if (!_cfg.runOnNight) {
      blocked = nightBlock = true;
      if (!_oldNMode) {
        _oldNMode = true;
        eventSimple("night_block");
        if (_isOpenFlag) { _isOpenFlag = false; startTankFill(nowMs); }
      }
    } else if (_oldNMode) {   // ночь, но работу ночью разрешили из приложения
      _oldNMode = false;
      eventSimple("night_resume");
    }
  } else {
    if (_nightNow) { _nightNow = false; eventSimple("day_start"); }
    if (_oldNMode) {
      _oldNMode = false;
      eventSimple("night_resume");
      if (_rainNow && !_cfg.runOnRain) eventSimple("rain_still");
    }
  }
}

void Device::controlValves(bool blocked, bool nightBlock, bool rainBlock, uint32_t nowMs, uint32_t unix) {
  for (uint8_t i = 0; i < NUM_CHANNELS; i++) {
    const String& mode = _cfg.channels[i].mode;
    bool allowed = !blocked || (!nightBlock && rainBlock && (mode == Mode::Greenhouse || mode == Mode::On));
    if (allowed) {
      checkValve(i, nowMs, unix);
    } else {
      valveClose(i, unix);
      if (_oldMode[i] != VState::ForcedClose) {
        _oldMode[i] = VState::ForcedClose;
        JsonDocument f;
        f["ch"] = i + 1;
        f["s"] = VState::ForcedClose;
        f["w"] = 1;
        event("valve", f.as<JsonObjectConst>());
      }
    }
  }
}

constexpr uint32_t NO_FLOW_ALERT_GAP_MS = 6UL * 3600 * 1000;

void Device::flowSilenceMinute(uint32_t unix) {
  bool expect = countOpen() > 0 && !_drainActive;   // клапан открыт — вода должна идти (с насосом или без)
  bool silent = expect && (_lastPulseAt == 0 || unix - _lastPulseAt >= 60);
  _silentMin = silent ? (_silentMin < 255 ? _silentMin + 1 : 255) : 0;
  if (_silentMin >= FLOW_SILENCE_MIN && !_flowSilent) {
    _flowSilent = true;
    eventSimple("flow_silent");
    // не чаще раза в 6 ч: при пустом баке клапаны открываются каждый цикл
    uint32_t now = millis();
    if (_noFlowAlertMs == 0 || now - _noFlowAlertMs >= NO_FLOW_ALERT_GAP_MS) {
      _noFlowAlertMs = now ? now : 1;
      _alert = String("Нет потока воды: клапаны открыты ") + FLOW_SILENCE_MIN + " мин, а вода не идёт";
      _alertSinceMs = now;
      LOG_I("уведомление: %s", _alert.c_str());
    }
  } else if (_flowSilent && !silent && _lastPulseAt != 0) {
    _flowSilent = false;
    eventSimple("flow_ok");
  }
}

constexpr int DRY_ALERT_PCT = 20, DRY_REARM_PCT = 25;
constexpr uint32_t ALERT_HOLD_MS = 10000, ALERT_QUIET_AFTER_BOOT_MS = 5UL * 60 * 1000;

// Пересохшие грядки (кроме режима «Выкл») — одна фраза на все сразу; повтор по грядке после намокания
void Device::dryAlerts(uint32_t nowMs) {
  String list;
  int n = 0;
  for (uint8_t i = 0; i < NUM_CHANNELS; i++) {
    int p = percent(i);
    if (p > DRY_REARM_PCT) _dryAlerted[i] = false;
    if (_dryAlerted[i] || p >= DRY_ALERT_PCT || _cfg.channels[i].mode == Mode::Off) continue;
    _dryAlerted[i] = true;
    if (nowMs < ALERT_QUIET_AFTER_BOOT_MS) continue;   // сухая уже до перезагрузки — не повторять
    const String& nm = _cfg.channels[i].name;
    String name = nm.length() ? nm : String("Растение ") + (i + 1);
    if (n++) list += ", ";
    list += name + " (" + p + " %)";
    if (n == 1) _alert = "Грядка " + name + " пересохла: " + p + " %";
  }
  if (n > 1) _alert = "Пересохли грядки: " + list;
  if (n) {
    _alertSinceMs = nowMs;
    LOG_I("уведомление: %s", _alert.c_str());
  }
}

void Device::tick(uint32_t nowMs, uint32_t unix) {
  if (_alert != "-" && nowMs - _alertSinceMs >= ALERT_HOLD_MS) _alert = "-";
  if (_faults) {
    if (!_faultShutdownDone) {
      _faultShutdownDone = true;
      loadsOff();
      JsonDocument f;
      JsonArray a = f["f"].to<JsonArray>();
      if (_faults & FAULT_RTC) a.add("rtc");
      if (_faults & FAULT_SD) a.add("sd");
      if (_faults & FAULT_VALVES) a.add("valves");
      event("hw_fault", f.as<JsonObjectConst>());
    }
    return;
  }
  _faultShutdownDone = false;

  // ⏱️ неблокирующие таймеры
  if (_fillActive && nowMs - _fillStartMs >= FILLING_WAIT_MS) { _fillActive = false; _hw.setFill(false); }
  spillageTick(nowMs);
  if (_pumpStarting && nowMs - _pumpStartMs > (uint32_t)_cfg.pumpStartSec * 1000UL) { _pumpStarting = false; stopPumpIfNeed(); }
  if (_bootUnix == 0 && unix) _bootUnix = unix;

  // 💧 расходомер
  uint32_t pulses = _hw.takePulses();
  _flowRate = _hw.flowLpm();
  _flowSession += pulses / PULSES_PER_LITER;
  if (pulses > 0) { _pulses += pulses; _lastPulseAt = unix; }

  // 🧽 контроль засора
  FlowMonitor::Event ev = _fm.tick(nowMs, _pulses, countOpen(), _drainActive, _pumpStarting, _fillActive);
  if (ev != FlowMonitor::Event::None) {
    JsonDocument f;
    f["r"] = roundf(_fm.eventRate * 1000) / 1000;
    if (ev == FlowMonitor::Event::Clog) f["e"] = roundf(_fm.eventExpected * 1000) / 1000;
    event(ev == FlowMonitor::Event::Clog ? "clog" : "clog_end", f.as<JsonObjectConst>());
  }
  if (_fm.dirty()) save();

  // 📅 раз в минуту (по unix, если известно, иначе по millis)
  int32_t minute = unix ? (int32_t)(unix / 60) : (int32_t)(nowMs / 60000);
  if (minute != _lastMinute || _recheck) {   // _recheck: режим/порог изменили из приложения
    _lastMinute = minute;
    _recheck = false;
    readAll();
    autoCalibrateBounds();
    dryAlerts(nowMs);
    bool blocked, nightBlock, rainBlock;
    checkWeather(nowMs, blocked, nightBlock, rainBlock);
    controlValves(blocked, nightBlock, rainBlock, nowMs, unix);
    flowSilenceMinute(unix);
    _cfg.flowSession = _flowSession;
  }
}

// ---------------------------------------------------------------- команды из облака
bool Device::applyDp(const char* code, double number, bool flag, const String& text, uint32_t nowMs,
                     uint32_t unix, String& err) {
  String c(code);
  int us = c.lastIndexOf('_');
  String base = us > 0 ? c.substring(0, us) : c;
  String num = us > 0 ? c.substring(us + 1) : "";
  if (num.length() && isDigit(num[0]) && (base == "mode" || base == "border" || base == "name")) {   // mode_all — не канал
    int ch = num.toInt();
    if (ch < 1 || ch > NUM_CHANNELS) { err = "bad channel"; return false; }
    if (base == "mode") _cfg.channels[ch - 1].mode = text;
    else if (base == "name") _cfg.channels[ch - 1].name = text.substring(0, 32);
    else _cfg.channels[ch - 1].border = (uint8_t)number;
    _recheck = true;
    save();
    return true;
  }
  if (c == "run_on_rain") { _cfg.runOnRain = flag; _recheck = true; }
  else if (c == "run_on_night") { _cfg.runOnNight = flag; _recheck = true; }
  else if (c == "delta_hum") _cfg.deltaHum = (int)number;
  else if (c == "delta_calib") _cfg.deltaCalib = (int)number;
  else if (c == "boost_pump_valves") { _cfg.boostPumpValves = (uint8_t)number; stopPumpIfNeed(); }
  else if (c == "clog_threshold") _cfg.clogThreshold = (uint8_t)number;
  else if (c == "pump_start_sec") _cfg.pumpStartSec = (uint16_t)number;
  else if (c == "flow_monitor") _cfg.flowMonitor = flag;
  else if (c == "autocal_no_delay") _cfg.autocalNoDelay = flag;
  else if (c == "mode_all") { for (auto& ch : _cfg.channels) ch.mode = text; _recheck = true; }
  else if (c == "command") { command(text, nowMs, unix); return true; }
  else if (c == "wizard") { wizard(text); return true; }
  else { err = "DP не обрабатывается"; return false; }
  save();
  return true;
}

void Device::resetSettings() {
  // telegram.cpp, Dlg::Reset — те же значения по умолчанию, счётчики воды сохраняем
  float total = _cfg.flowTotal, session = _cfg.flowSession;
  uint32_t allClosed = _cfg.utimeAllClosed;
  _cfg = Config();
  _cfg.flowTotal = total;
  _cfg.flowSession = session;
  _cfg.utimeAllClosed = allClosed;
  _fm.recalibrate();
  _fm.dirty();
  for (uint8_t i = 0; i < NUM_CHANNELS; i++) setLowHigh(i, SOIL_ADC_WET, SOIL_ADC_DRY);
}

void Device::command(const String& cmd, uint32_t nowMs, uint32_t unix) {
  if (cmd == "restart") {
    loadsOff();
    save();
    _restart = true;
  } else if (cmd == "reset_settings") {
    resetSettings();
    save();
    eventSimple("reset_settings");
  } else if (cmd == "clear_flow") {
    _flowSession = 0;
    _cfg.flowTotal = 0;
    save();
    eventSimple("clear_flow");
  } else if (cmd == "filter_cleaned") {
    _fm.recalibrate();
    _fm.dirty();
    save();
    eventSimple("filter_cleaned");
  } else if (cmd == "drain") {
    spillage(nowMs);
  }
}

// ---------------------------------------------------------------- мастера калибровки и поиска
void Device::setWizard(JsonDocument& state) {
  _wizard.clear();
  for (JsonPair kv : state.as<JsonObject>()) if (!kv.value().isNull()) _wizard[kv.key()] = kv.value();
}

void Device::wizard(const String& text) {
  JsonDocument cmd;
  JsonDocument st;
  if (deserializeJson(cmd, text) || !cmd["op"].is<const char*>()) {
    st["op"] = "error"; st["err"] = "bad_json"; setWizard(st); return;
  }
  String op = cmd["op"].as<String>();
  String step = cmd["step"] | "";
  String wop = _wizard["op"] | "";
  String wstep = _wizard["step"] | "";
  int wch = _wizard["ch"] | 0;

  if (op == "manual") {
    int ch = (int)(cmd["ch"] | 0) - 1, lo = cmd["min"] | -1, hi = cmd["max"] | -1;
    if (ch < 0 || ch >= NUM_CHANNELS || lo < 0 || lo > 4096 || hi < 0 || hi > 4096) {
      st["op"] = "manual"; st["step"] = "done"; st["ok"] = false; st["err"] = "range"; setWizard(st); return;
    }
    setLowHigh(ch, lo, hi);
    _cfg.channels[ch].minVal = lo;
    _cfg.channels[ch].maxVal = hi;
    save();
    st["op"] = "manual"; st["ch"] = ch + 1; st["step"] = "done"; st["ok"] = true; st["min"] = lo; st["max"] = hi;
    setWizard(st);
    return;
  }
  if (step == "cancel") {
    if (wop == "calib" && wch >= 1) {
      int i = wch - 1;
      setLowHigh(i, _cfg.channels[i].minVal, _cfg.channels[i].maxVal);
    }
    st["op"] = wop.length() ? wop : op;
    if (wch) st["ch"] = wch;
    st["step"] = "done"; st["ok"] = false; st["err"] = "cancelled";
    setWizard(st);
    return;
  }
  if (op == "calib") {
    if (step == "start") {
      int ch = cmd["ch"] | 0;
      if (ch < 1 || ch > NUM_CHANNELS) { st["op"] = "calib"; st["step"] = "done"; st["ok"] = false; st["err"] = "bad_channel"; }
      else { st["op"] = "calib"; st["ch"] = ch; st["step"] = "wet"; }
    } else if (wop == "calib" && step == "next" && wstep == "wet") {
      int i = wch - 1;
      readAll();
      _low[i] = _curr[i];
      st["op"] = "calib"; st["ch"] = wch; st["step"] = "dry"; st["wet"] = _low[i];
    } else if (wop == "calib" && step == "next" && wstep == "dry") {
      int i = wch - 1;
      readAll();
      _high[i] = _curr[i];
      st["op"] = "calib"; st["ch"] = wch; st["step"] = "finish"; st["wet"] = _wizard["wet"]; st["dry"] = _high[i];
    } else if (wop == "calib" && step == "finish" && wstep == "finish") {
      int i = wch - 1;
      if (abs(_high[i] - _low[i]) < CALIB_MIN_SPAN) {
        setLowHigh(i, _cfg.channels[i].minVal, _cfg.channels[i].maxVal);
        st["op"] = "calib"; st["ch"] = wch; st["step"] = "done"; st["ok"] = false; st["err"] = "span";
      } else {
        _cfg.channels[i].minVal = _low[i];
        _cfg.channels[i].maxVal = _high[i];
        save();
        st["op"] = "calib"; st["ch"] = wch; st["step"] = "done"; st["ok"] = true; st["min"] = _low[i]; st["max"] = _high[i];
      }
    } else {
      st.set(_wizard); st["err"] = "bad_step";
    }
    setWizard(st);
    return;
  }
  if (op == "search") {
    if (step == "start") {
      st["op"] = "search"; st["step"] = "wet";
    } else if (wop == "search" && step == "next" && wstep == "wet") {
      readAll();
      for (uint8_t i = 0; i < NUM_CHANNELS; i++) _searchSnapshot[i] = _curr[i];
      st["op"] = "search"; st["step"] = "dry";
    } else if (wop == "search" && step == "next" && wstep == "dry") {
      readAll();
      int found = -1;
      for (uint8_t i = 0; i < NUM_CHANNELS && found < 0; i++)
        if (abs(_searchSnapshot[i] - _curr[i]) > SEARCH_DELTA) found = i;
      st["op"] = "search"; st["step"] = "done";
      if (found < 0) { st["ok"] = false; st["err"] = "not_found"; }
      else { st["ok"] = true; st["found"] = found + 1; }
    } else {
      st.set(_wizard); st["err"] = "bad_step";
    }
    setWizard(st);
    return;
  }
  st["op"] = "error"; st["err"] = "unknown_op";
  setWizard(st);
}

// ---------------------------------------------------------------- снимок DP и отчёт
String Device::sysInfo(uint32_t unix, JsonObjectConst extra) {
  JsonDocument d;
  d["fw"] = FW_VERSION;
  d["up"] = _bootUnix && unix ? (int)(unix - _bootUnix) : (int)(millis() / 1000);
  d["t"] = unix;
  d["rtc"] = (_faults & FAULT_RTC) ? 0 : 1;
  d["pulses"] = _pulses;
  d["last_pulse"] = _lastPulseAt ? (int)(unix - _lastPulseAt) : -1;
  for (JsonPairConst kv : extra) d[kv.key()] = kv.value();
  String s;
  serializeJson(d, s);
  return s;
}

void Device::snapshot(JsonObject out) {
  dp::putBool(out, "rain", _rainNow);
  dp::putBool(out, "night", _nightNow);
  dp::putBool(out, "pump", _pump);
  dp::putEnum(out, "pump_state", pumpState());
  dp::putBool(out, "drain", _drainActive);
  dp::putBool(out, "fill", _fillActive);
  dp::putNumber(out, "flow_rate", _flowRate);
  dp::putNumber(out, "flow_session", _flowSession);
  dp::putNumber(out, "flow_total", _cfg.flowTotal);
  const char* flags[4];
  size_t nf = 0;
  if (_faults & FAULT_RTC) flags[nf++] = "rtc";
  if (_faults & FAULT_SD) flags[nf++] = "sd";
  if (_faults & FAULT_VALVES) flags[nf++] = "valves";
  if (_fm.alert()) flags[nf++] = "filter_clog";
  dp::putBitmap(out, "fault", flags, nf);
  dp::putNumber(out, "filter_baseline", _cfg.cleanFlowPerValve);
  dp::putBool(out, "run_on_rain", _cfg.runOnRain);
  dp::putBool(out, "run_on_night", _cfg.runOnNight);
  dp::putNumber(out, "delta_hum", _cfg.deltaHum);
  dp::putNumber(out, "delta_calib", _cfg.deltaCalib);
  dp::putNumber(out, "boost_pump_valves", _cfg.boostPumpValves);
  dp::putNumber(out, "clog_threshold", _cfg.clogThreshold);
  dp::putNumber(out, "pump_start_sec", _cfg.pumpStartSec);
  dp::putBool(out, "flow_monitor", _cfg.flowMonitor);
  dp::putBool(out, "autocal_no_delay", _cfg.autocalNoDelay);
  String wz;
  serializeJson(_wizard, wz);
  dp::putString(out, "wizard_state", wz);
  dp::putString(out, "alert", _alert);
  uint8_t raw[NUM_CHANNELS * 6];
  for (uint8_t i = 0; i < NUM_CHANNELS; i++) {
    uint16_t v[3] = {(uint16_t)_curr[i], (uint16_t)_low[i], (uint16_t)_high[i]};
    for (int k = 0; k < 3; k++) { raw[i * 6 + k * 2] = v[k] >> 8; raw[i * 6 + k * 2 + 1] = v[k] & 0xFF; }
  }
  dp::putRaw(out, "adc_raw", raw, sizeof(raw));
  char code[24];
  for (uint8_t i = 0; i < NUM_CHANNELS; i++) {
    const ChannelCfg& c = _cfg.channels[i];
    snprintf(code, sizeof(code), "humidity_%d", i + 1); dp::putNumber(out, code, percent(i));
    snprintf(code, sizeof(code), "valve_%d", i + 1);    dp::putEnum(out, code, _oldMode[i]);
    snprintf(code, sizeof(code), "mode_%d", i + 1);     dp::putEnum(out, code, c.mode.c_str());
    snprintf(code, sizeof(code), "border_%d", i + 1);   dp::putNumber(out, code, c.border);
    snprintf(code, sizeof(code), "name_%d", i + 1);
    dp::putString(out, code, c.name.length() ? c.name : String("Растение ") + (i + 1));
  }
}

bool Device::report(JsonObject changed, bool full) {
  JsonDocument snap;
  JsonObject s = snap.to<JsonObject>();
  snapshot(s);
  bool any = false;
  for (JsonPair kv : s) {
    JsonVariant prev = _lastReport[kv.key()];
    if (full || prev.isNull() || prev != kv.value()) {
      changed[kv.key()] = kv.value();
      any = true;
    }
  }
  _lastReport.set(snap);
  return any;
}
