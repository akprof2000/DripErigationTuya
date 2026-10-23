// config.h ⚙️ Настройки полива (аналог struct Config старой прошивки / Config в device.py).
// Хранится JSON-файлом /state.json на dataFs() (SD или LittleFS), поля как в device.py:
// run_on_rain, run_on_night, delta_calib, delta_hum, boost_pump_valves, utime_all_closed,
// flow_session, flow_total, clean_flow_per_valve, clean_flow_drain, clog_threshold,
// flow_monitor, autocal_no_delay, channels[8]{name, border, mode, min_val, max_val}.
// Запись атомарная (.tmp + rename): сбой питания не губит настройки.
#pragma once
#include <Arduino.h>
#include <FS.h>

constexpr uint8_t NUM_CHANNELS = 8;

// Режимы канала — строки enum DP mode_N (spec/dp.json)
namespace Mode {
constexpr const char* Auto = "auto";
constexpr const char* On = "on";
constexpr const char* Off = "off";
constexpr const char* Greenhouse = "greenhouse";
}

// Ёмкостный датчик v1.2 от 3,3 В на этой плате (замер 2026-10-23): в воде ~1015, на воздухе ~3240.
// Автокалибровка дальше расширяет границы по реальным показаниям.
constexpr uint16_t SOIL_ADC_WET = 1015;
constexpr uint16_t SOIL_ADC_DRY = 3240;
constexpr int CALIB_DEFAULTS_VERSION = 1;   // поднять, чтобы разово переписать границы всех каналов

struct ChannelCfg {
  String name = "🌱 Растение";   // только для консоли: названия грядок живут в облаке (панель)
  uint8_t border = 60;           // порог влажности, %
  String mode = Mode::Auto;
  uint16_t minVal = SOIL_ADC_WET;   // АЦП «вода»
  uint16_t maxVal = SOIL_ADC_DRY;   // АЦП «сухо»
};

struct Config {
  bool runOnRain = true;
  bool runOnNight = false;
  int deltaCalib = 15;
  int deltaHum = 5;
  uint8_t boostPumpValves = 9;   // 1..8 — держать насос при ≥N открытых клапанах, 9 = никогда
  ChannelCfg channels[NUM_CHANNELS];
  int calibDefaults = CALIB_DEFAULTS_VERSION;   // какие умолчания границ уже применены
  uint32_t utimeAllClosed = 0;
  float flowSession = 0;
  float flowTotal = 0;
  float cleanFlowPerValve = 0;
  float cleanFlowDrain = 0;
  uint8_t clogThreshold = 50;
  uint16_t pumpStartSec = 30;    // пусковое окно насоса после открытия клапана, 0 — не включать
  bool flowMonitor = true;
  bool autocalNoDelay = false;

  bool load(fs::FS& fs, const char* path);   // false → остались значения по умолчанию
  bool save(fs::FS& fs, const char* path) const;
};
