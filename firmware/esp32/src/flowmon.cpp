// flowmon.cpp 🧽 Контроль засора фильтра — перенос fm* из objects.cpp 1:1
#include "flowmon.h"
#include "hw.h"
#include "log.h"

float FlowMonitor::rateOf(uint32_t pulses, uint32_t ms) {
  if (ms == 0) return 0;
  return pulses / PULSES_PER_LITER * 60000.0f / ms;
}

void FlowMonitor::recalibrate() {
  _cfg.cleanFlowPerValve = 0;
  _cfg.cleanFlowDrain = 0;
  _alert = false;
  _badWindows = 0;
  _candidate = -1;
  _dirty = true;
  LOG_I("fm: эталон фильтра сброшен — калибровка на чистом фильтре");
}

void FlowMonitor::startWindow(uint32_t nowMs, uint32_t pulses, bool boost) {
  _measuring = true;
  _measureStartMs = nowMs;
  _measureStartPulses = pulses;
  _boostTainted = boost;
}

FlowMonitor::Event FlowMonitor::process(uint8_t cnt, bool draining, float rate, uint32_t nowMs) {
  _rate = rate;
  float perValve = _cfg.cleanFlowPerValve;

  // 📈 авто-обучение эталона «на клапан»: всплеск живёт кандидатом, фиксируется минимум за 5 мин
  if (!draining) {
    float measured = rate / cnt;
    if (measured <= perValve) {
      _candidate = -1;
    } else {
      bool rollback = _candidate >= 0 && measured < _candidate - SPIKE_TOLERANCE_L;
      if (_candidate < 0 || rollback) {
        _candidate = measured;
        _candidateStartMs = nowMs;
      } else if (measured < _candidate) {
        _candidate = measured;
      }
      if (nowMs - _candidateStartMs >= SPIKE_CONFIRM_MS) {
        _cfg.cleanFlowPerValve = _candidate;
        _dirty = true;
        _badWindows = 0;
        _candidate = -1;
        LOG_I("fm: эталон на клапан %.2f л/мин", _cfg.cleanFlowPerValve);
      }
      return Event::None;   // поток выше эталона — засора точно нет
    }
  } else if (perValve > 0) {   // дренаж: учим добавку сверх потока клапанов
    float extra = rate - perValve * cnt;
    if (extra < 0) extra = 0;
    if (extra > _cfg.cleanFlowDrain) {
      _cfg.cleanFlowDrain = extra;
      _dirty = true;
      _badWindows = 0;
      return Event::None;
    }
  }

  if (perValve <= 0) return Event::None;
  if (draining && _cfg.cleanFlowDrain <= 0) return Event::None;
  float expected = perValve * cnt + (draining ? _cfg.cleanFlowDrain : 0);
  if (expected <= 0) return Event::None;
  float ratioPct = rate / expected * 100.0f;

  if (ratioPct < _cfg.clogThreshold) {
    if (_badWindows < 255) _badWindows++;
    LOG_W("fm: низкий поток %.2f л/мин (%d%% от нормы), окно %d/%d", rate, (int)ratioPct, _badWindows, BAD_WINDOWS);
    if (_badWindows >= BAD_WINDOWS && (!_alert || nowMs - _lastAlertMs > ALERT_REPEAT_MS)) {
      _alert = true;
      _lastAlertMs = nowMs;
      eventRate = rate;
      eventExpected = expected;
      return Event::Clog;
    }
  } else {
    _badWindows = 0;
    if (_alert) {
      _alert = false;
      eventRate = rate;
      eventExpected = expected;
      return Event::ClogEnd;
    }
  }
  return Event::None;
}

FlowMonitor::Event FlowMonitor::tick(uint32_t nowMs, uint32_t pulses, uint8_t cnt, bool draining, bool boost,
                                     bool filling) {
  if (!_cfg.flowMonitor) { _count = 0; _measuring = false; return Event::None; }
  bool qualified = cnt > 0 && !filling;
  if (!qualified) { _count = 0; _measuring = false; return Event::None; }

  // 🔄 сменилась конфигурация — рестарт окна и ожидания стабилизации
  if (cnt != _count || draining != _draining) {
    _count = cnt;
    _draining = draining;
    _measuring = false;
    _phaseStartMs = nowMs;
    _boostTainted = boost;
    _subStartMs = nowMs;
    _subStartPulses = pulses;
    _prevSubRate = -1;
    _stableCount = 0;
    _candidate = -1;
    return Event::None;
  }

  if (!_measuring) {   // ⏳ фаза выхода на режим
    if (boost) _boostTainted = true;
    if (nowMs - _phaseStartMs >= SETTLE_CAP_MS) { startWindow(nowMs, pulses, boost); return Event::None; }
    if (nowMs - _subStartMs < SUBSAMPLE_MS) return Event::None;
    float sub = rateOf(pulses - _subStartPulses, nowMs - _subStartMs);
    _rate = sub;
    bool pastMinimum = nowMs - _phaseStartMs >= SETTLE_MIN_MS;
    if (pastMinimum && _prevSubRate >= 0) {
      bool stillFalling = sub < _prevSubRate * (1.0f - SETTLE_STABLE_PCT / 100.0f);
      _stableCount = stillFalling ? 0 : _stableCount + 1;
    } else {
      _stableCount = 0;
    }
    _prevSubRate = sub;
    _subStartMs = nowMs;
    _subStartPulses = pulses;
    if (pastMinimum && _stableCount >= STABLE_NEEDED) startWindow(nowMs, pulses, boost);
    return Event::None;
  }

  if (boost) _boostTainted = true;
  if (nowMs - _measureStartMs < WINDOW_MS) return Event::None;

  uint32_t dPulses = pulses - _measureStartPulses;
  uint32_t dt = nowMs - _measureStartMs;
  _measureStartMs = nowMs;
  _measureStartPulses = pulses;
  bool tainted = _boostTainted;
  _boostTainted = boost;
  _rate = rateOf(dPulses, dt);
  if (dPulses < MIN_PULSES) return Event::None;   // пустой бак / сухой ход — не засор
  if (tainted) return Event::None;                // окно с пусковым насосом
  return process(cnt, _draining, _rate, nowMs);
}
