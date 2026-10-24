// app.h 🔁 Главный цикл контроллера (порт mpy/lib/app.py): железо, часы, Wi-Fi, логика полива,
// фильтр и очередь отчётов, облако Tuya, OTA, кнопка, светодиод. Полив не зависит от сети.
#pragma once
#include <Arduino.h>
#include <ArduinoJson.h>
#include "clock.h"
#include "config.h"
#include "device.h"
#include "hw.h"
#include "ota.h"
#include "outbox.h"
#include "reporter.h"
#include "tuya.h"
#include "wifi_portal.h"

class App {
 public:
  static constexpr uint32_t TICK_MS = 1000, SYS_INFO_EVERY_S = 60, BUTTON_PORTAL_MS = 5000,
                            STATE_OK_AFTER_S = 60, WDT_TIMEOUT_S = 120;
  void setup();
  void loop();

 private:
  Hardware _hw;
  Config _cfg;
  Clock _clock;
  WifiLink _wifi;
  Device* _dev = nullptr;
  Outbox* _outbox = nullptr;
  Reporter _reporter;
  Tuya* _tuya = nullptr;
  Ota* _ota = nullptr;

  uint32_t _lastTick = 0;
  uint32_t _upSec = 0;             // монотонные секунды работы
  uint32_t _sysAt = 0;
  bool _ntpStarted = false;
  bool _wasOnline = false;
  uint32_t _onlineSince = 0;       // _upSec, когда вышли в облако (0 = офлайн)
  bool _bootConfirmed = false;
  uint32_t _buttonSince = 0;
  uint32_t _restartAt = 0;
  bool _ledOn = false;

  bool loadCreds(String& pid, String& uuid, String& authkey);
  void onConnected();
  void onDps(JsonObjectConst dps);
  void queue(JsonObjectConst packet, bool full);   // packet: code → value (формат Tuya)
  void sendEvents();
  void sysInfo();
  void shutdown();
  void tickButton();
  void tickLed(bool wifiUp);
  void tickSerial();
  void relayTest();
  String _cmd;
};
