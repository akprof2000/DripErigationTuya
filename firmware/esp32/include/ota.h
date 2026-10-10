// ota.h 🔄 Обновление прошивки через облако Tuya (порт mpy/lib/ota.py) на OTA-разделы ESP32.
//
//  1. MQTT протокол 15 (PRO_UPGD_REQ) с firmwareType → tick() спрашивает tuya.device.upgrade.get
//     (httpsUrl, size, md5, version), шлёт статус 2 «обновляюсь» (tuya.device.upgrade.status.update);
//  2. образ качается потоком в Update (ArduinoOTA Update.h), прогресс — протокол 16
//     {"progress":"50","firmwareType":N}, md5 проверяется Update.setMD5;
//  3. записывается /ota/apply.json {version,type}, вызывается onBeforeReboot, ESP.restart();
//  4. новая прошивка после подключения: статус 3 «готово», tuya.device.versions.update
//     ([{otaChannel:0, protocolVer:"2.3", baselineVer:"40.07", softVer}]), tuya.device.upgrade.silent.get
//     (тихое обновление, назначенное пока устройство было выключено).
// Откат: загрузчик ESP-IDF ждёт confirm() (esp_ota_mark_app_valid_cancel_rollback) —
// app даёт его, побыв минуту онлайн; если прошивка перезагрузилась раньше — откат автоматически.
#pragma once
#include <Arduino.h>
#include <ArduinoJson.h>
#include <functional>
#include "tuya.h"

class Ota {
 public:
  Ota(Tuya& tuya, const String& version) : _tuya(tuya), _version(version) {}
  void onProtocol(int protocol, JsonObjectConst data);   // подписать на tuya.onProtocol
  void onConnected();                                    // подписать на tuya.onConnected (после отчёта DP)
  void tick();                                           // из главного цикла, когда online
  bool busy() const { return _busy; }
  std::function<void()> onBeforeReboot;                  // погасить нагрузки, сохранить состояние

  static void confirm();                                 // текущая прошивка рабочая (отменить откат)

 private:
  Tuya& _tuya;
  String _version;
  int _channel = -1;        // ждёт выполнения задание на обновление
  bool _busy = false;
  void run(JsonObjectConst info);
  bool download(const String& url, size_t size, const String& md5, int ch, String& err);
  void status(int ch, int st);
  void progress(int ch, int pct);
};
