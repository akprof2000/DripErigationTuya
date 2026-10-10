// flowmon.h 🧽 Контроль засора фильтра по скорости потока (objects.cpp старой прошивки, fm*).
//
// Модель: ожидаемый_поток = эталон_на_клапан × открытых + (дренаж ? эталон_дренажа : 0).
// Эталоны набираются авто-максимумом на чистом фильтре (всплеск подтверждается минимумом за
// 5 мин), сбрасываются командой «фильтр прочищен». Засор = поток < clog_threshold % от нормы
// три окна подряд. Окно замера начинается после стабилизации потока (≥10 мин после открытия
// клапана, потом подынтервалы по 60 с, пока поток не перестанет падать).
#pragma once
#include <Arduino.h>
#include "config.h"

class FlowMonitor {
 public:
  // ⏱️ параметры (timing.h)
  static constexpr uint32_t SETTLE_MIN_MS = 600000, SUBSAMPLE_MS = 60000, SETTLE_CAP_MS = 900000,
                            WINDOW_MS = 120000, ALERT_REPEAT_MS = 86400000UL, SPIKE_CONFIRM_MS = 300000;
  static constexpr uint8_t SETTLE_STABLE_PCT = 10, STABLE_NEEDED = 2, BAD_WINDOWS = 3;
  static constexpr uint32_t MIN_PULSES = 10;
  static constexpr float SPIKE_TOLERANCE_L = 1.0f;

  enum class Event : uint8_t { None, Clog, ClogEnd };

  explicit FlowMonitor(Config& cfg) : _cfg(cfg) {}
  // Тик (каждый loop): nowMs, импульсов всего, открытых клапанов, идёт ли дренаж,
  // активен ли пусковой насос, идёт ли заливка бака. → событие (rate/expected заполняются).
  Event tick(uint32_t nowMs, uint32_t pulses, uint8_t openCount, bool draining, bool boost, bool filling);
  void recalibrate();                 // «фильтр прочищен»: эталоны в 0, тревога снята
  float lastRate() const { return _rate; }
  bool alert() const { return _alert; }
  bool dirty() { bool d = _dirty; _dirty = false; return d; }   // эталон изменился — сохранить cfg
  float eventRate = 0, eventExpected = 0;   // данные последнего события

 private:
  Config& _cfg;
  uint8_t _count = 0;
  bool _draining = false, _boostTainted = false, _measuring = false;
  uint32_t _phaseStartMs = 0, _measureStartMs = 0, _measureStartPulses = 0;
  uint32_t _subStartMs = 0, _subStartPulses = 0;
  float _prevSubRate = -1;
  uint8_t _stableCount = 0, _badWindows = 0;
  bool _alert = false, _dirty = false;
  uint32_t _lastAlertMs = 0;
  float _rate = 0;
  float _candidate = -1;
  uint32_t _candidateStartMs = 0;
  Event process(uint8_t cnt, bool draining, float rate, uint32_t nowMs);
  void startWindow(uint32_t nowMs, uint32_t pulses, bool boost);
  static float rateOf(uint32_t pulses, uint32_t ms);
};
