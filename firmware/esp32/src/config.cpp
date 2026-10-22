// config.cpp ⚙️ Настройки полива: JSON-файл /state.json, поля как в mpy/lib/device.py Config.
#include "config.h"
#include <ArduinoJson.h>
#include "log.h"
#include "storage.h"

namespace {

// Нет ключа или не тот тип — поле остаётся со значением по умолчанию (как Config.load в device.py)
template <typename T>
void pick(JsonObjectConst o, const char* key, T& field) {
  JsonVariantConst v = o[key];
  if (v.is<T>()) field = v.as<T>();
}

void pickStr(JsonObjectConst o, const char* key, String& field) {
  JsonVariantConst v = o[key];
  if (v.is<const char*>()) field = v.as<const char*>();
}

}  // namespace

bool Config::load(fs::FS& fs, const char* path) {
  *this = Config();
  String text = readFile(fs, path);
  if (text.isEmpty()) {
    LOG_W("config: %s нет — умолчания", path);
    return false;
  }
  JsonDocument doc;
  DeserializationError e = deserializeJson(doc, text);
  if (e || !doc.is<JsonObjectConst>()) {
    LOG_E("config: %s не разобран (%s) — умолчания", path, e.c_str());
    return false;
  }
  JsonObjectConst d = doc.as<JsonObjectConst>();
  pick(d, "run_on_rain", runOnRain);
  pick(d, "run_on_night", runOnNight);
  pick(d, "delta_calib", deltaCalib);
  pick(d, "delta_hum", deltaHum);
  pick(d, "boost_pump_valves", boostPumpValves);
  pick(d, "utime_all_closed", utimeAllClosed);
  pick(d, "flow_session", flowSession);
  pick(d, "flow_total", flowTotal);
  pick(d, "clean_flow_per_valve", cleanFlowPerValve);
  pick(d, "clean_flow_drain", cleanFlowDrain);
  pick(d, "clog_threshold", clogThreshold);
  pick(d, "flow_monitor", flowMonitor);
  pick(d, "autocal_no_delay", autocalNoDelay);
  JsonArrayConst chs = d["channels"].as<JsonArrayConst>();
  size_t i = 0;
  for (JsonObjectConst c : chs) {
    if (i >= NUM_CHANNELS) break;
    ChannelCfg& ch = channels[i++];
    pickStr(c, "name", ch.name);
    pick(c, "border", ch.border);
    pickStr(c, "mode", ch.mode);
    pick(c, "min_val", ch.minVal);
    pick(c, "max_val", ch.maxVal);
  }
  int calibV = 0;
  pick(d, "calib_defaults", calibV);
  if (calibV < CALIB_DEFAULTS_VERSION) {   // разово: новые границы датчиков вместо старых 1024/1024 и шума
    for (ChannelCfg& ch : channels) {
      ch.minVal = SOIL_ADC_WET;
      ch.maxVal = SOIL_ADC_DRY;
    }
    LOG_I("config: границы датчиков по умолчанию [%d; %d]", SOIL_ADC_WET, SOIL_ADC_DRY);
  }
  calibDefaults = CALIB_DEFAULTS_VERSION;
  LOG_I("config: %s загружен", path);
  return true;
}

bool Config::save(fs::FS& fs, const char* path) const {
  JsonDocument doc;
  doc["run_on_rain"] = runOnRain;
  doc["run_on_night"] = runOnNight;
  doc["delta_calib"] = deltaCalib;
  doc["delta_hum"] = deltaHum;
  doc["boost_pump_valves"] = boostPumpValves;
  doc["utime_all_closed"] = utimeAllClosed;
  doc["flow_session"] = flowSession;
  doc["flow_total"] = flowTotal;
  doc["clean_flow_per_valve"] = cleanFlowPerValve;
  doc["clean_flow_drain"] = cleanFlowDrain;
  doc["clog_threshold"] = clogThreshold;
  doc["flow_monitor"] = flowMonitor;
  doc["autocal_no_delay"] = autocalNoDelay;
  doc["calib_defaults"] = calibDefaults;
  JsonArray chs = doc["channels"].to<JsonArray>();
  for (uint8_t i = 0; i < NUM_CHANNELS; i++) {
    const ChannelCfg& ch = channels[i];
    JsonObject c = chs.add<JsonObject>();
    c["name"] = ch.name;
    c["border"] = ch.border;
    c["mode"] = ch.mode;
    c["min_val"] = ch.minVal;
    c["max_val"] = ch.maxVal;
  }
  if (doc.overflowed()) {
    LOG_E("config: нет памяти под JSON");
    return false;
  }
  String text;
  serializeJson(doc, text);
  if (!writeFile(fs, path, text)) {
    LOG_E("config: не сохранён %s", path);
    return false;
  }
  LOG_D("config: сохранён %s (%u байт)", path, (unsigned)text.length());
  return true;
}
