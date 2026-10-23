// device.h 🌱💧 Логика контроллера полива — та же, что в эмуляторе (mpy/lib/device.py),
// перенесённая со старой прошивки (DripIrrigation.ino, valves.cpp, sensors.cpp, irrigation.cpp).
//
// Раз в секунду tick(): таймеры (заливка, дренаж, пусковой насос), расходомер, контроль засора;
// раз в минуту — опрос датчиков, авто-калибровка границ, погода, решение по клапанам.
// Уведомления бота стали событиями: DP event = JSON {"t":код,...} (текст подставляет панель).
#pragma once
#include <Arduino.h>
#include <ArduinoJson.h>
#include <FS.h>
#include "config.h"
#include "flowmon.h"
#include "hw.h"

#ifndef FW_VERSION
#define FW_VERSION "1.1.0"
#endif

// ⏱️ константы (timing.h / device.py)
constexpr uint32_t FILLING_WAIT_MS = 3000, DRAIN_TIMEOUT_MS = 12000, PUMP_TIMEOUT_MS = 30000;
constexpr uint32_t TIMEOUT_WAIT_S = 18000;     // «всё закрыто» дольше → первое открытие делает пролив
constexpr uint8_t HUM_AUTOCAL_CONFIRM = 3;
constexpr int SEARCH_DELTA = 300, CALIB_MIN_SPAN = 100;
constexpr uint8_t FLOW_SILENCE_MIN = 2;

// 🚰 состояния клапана — строки enum DP valve_N
namespace VState {
constexpr const char* Init = "init";
constexpr const char* OpenHum = "open_hum";
constexpr const char* CloseHum = "close_hum";
constexpr const char* Hyst = "hyst";
constexpr const char* ForcedOpen = "forced_open";
constexpr const char* ForcedClose = "forced_close";
}

// 🩺 блокирующие аварии (биты как labels DP fault: rtc, sd, valves)
enum : uint8_t { FAULT_RTC = 1, FAULT_SD = 2, FAULT_VALVES = 4 };

class Device {
 public:
  Device(Hardware& hw, Config& cfg, fs::FS& fs, const char* statePath);
  void begin();                                   // RAM-состояние из cfg
  void tick(uint32_t nowMs, uint32_t unix);       // раз в секунду
  void setFaults(uint8_t mask);                   // rtc|sd|valves — полив останавливается
  uint8_t faults() const { return _faults; }

  // ☁️ команда из облака: code (уже проверенный dp::decode) и значение
  bool applyDp(const char* code, double number, bool flag, const String& text, uint32_t nowMs, uint32_t unix,
               String& err);
  void command(const String& cmd, uint32_t nowMs, uint32_t unix);
  bool restartRequested() const { return _restart; }

  // 📊 отчёты: полный снимок / изменения с прошлого отчёта (ключи — коды DP, значения — формат Tuya)
  void snapshot(JsonObject out);
  bool report(JsonObject changed, bool full);
  bool popEvent(String& json);                    // события по одному (DP event)
  String sysInfo(uint32_t unix, JsonObjectConst extra);

  void loadsOff();
  void save();
  bool clogged() const { return _fm.alert(); }
  const char* pumpState() const;
  float flowRate() const { return _flowRate; }
  uint32_t pulses() const { return _pulses; }
  uint32_t lastPulseAt() const { return _lastPulseAt; }

 private:
  Hardware& _hw;
  Config& _cfg;
  fs::FS& _fs;
  String _statePath;
  FlowMonitor _fm;
  uint8_t _faults = 0;
  bool _faultShutdownDone = false;
  bool _restart = false;

  // sensors
  int _low[NUM_CHANNELS], _high[NUM_CHANNELS], _curr[NUM_CHANNELS];
  uint8_t _loCnt[NUM_CHANNELS], _hiCnt[NUM_CHANNELS];
  int _loCand[NUM_CHANNELS], _hiCand[NUM_CHANNELS];
  // valves
  const char* _oldMode[NUM_CHANNELS];
  bool _isClose[NUM_CHANNELS];
  bool _isOpenFlag = false;
  bool _pump = false;
  bool _pumpStarting = false;
  uint32_t _pumpStartMs = 0;
  bool _drainActive = false, _fillActive = false;
  uint32_t _drainStartMs = 0, _fillStartMs = 0;
  bool _recheck = false;   // пересчитать клапаны на ближайшем тике, не ждать минуты
  // 🔔 «грядка пересохла»: текст в DP alert на ALERT_HOLD_MS, затем «-»; повтор после намокания
  String _alert = "-";
  uint32_t _alertSinceMs = 0;
  bool _dryAlerted[NUM_CHANNELS] = {};
  void dryAlerts(uint32_t nowMs);
  bool _rainNow = false, _nightNow = false, _oldRMode = false, _oldNMode = false;
  // flow
  float _flowSession = 0, _flowRate = 0;
  uint32_t _pulses = 0, _lastPulseAt = 0;
  bool _flowSilent = false;
  uint8_t _silentMin = 0;
  uint32_t _bootUnix = 0;
  int32_t _lastMinute = -1;
  // wizard / events / отчёты
  JsonDocument _wizard;
  int _searchSnapshot[NUM_CHANNELS];
  static constexpr size_t MAX_EVENTS = 24;
  String _events[MAX_EVENTS];
  size_t _evHead = 0, _evCount = 0;
  JsonDocument _lastReport;

  void event(const char* code, JsonObjectConst fields = JsonObjectConst());
  void eventSimple(const char* code);
  int percent(uint8_t i) const;
  void readAll();
  void setLowHigh(uint8_t i, int lo, int hi);
  bool autoExtend(uint8_t i, uint8_t confirm);
  bool calibrationInProgress();
  void autoCalibrateBounds();
  uint8_t countOpen() const;
  void setPump(bool on);
  void stopPumpIfNeed();
  void valveOpen(uint8_t i, uint32_t nowMs, uint32_t unix);
  void valveClose(uint8_t i, uint32_t unix);
  void spillage(uint32_t nowMs);
  void spillageTick(uint32_t nowMs);
  void checkValve(uint8_t i, uint32_t nowMs, uint32_t unix);
  void startTankFill(uint32_t nowMs);
  void checkWeather(uint32_t nowMs, bool& blocked, bool& nightBlock, bool& rainBlock);
  void controlValves(bool blocked, bool nightBlock, bool rainBlock, uint32_t nowMs, uint32_t unix);
  void flowSilenceMinute(uint32_t unix);
  void wizard(const String& text);
  void setWizard(JsonDocument& state);
  void resetSettings();
  void rebootState();
};
