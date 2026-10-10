// wifi_portal.h 📡 Wi-Fi контроллера: подключение к сохранённой сети и портал настройки.
//
// Сеть хранится в cfgFs(): /wifi.json {"ssid":..,"pass":..}. Портал — точка доступа
// «DripIrrigation-XXXX» (без пароля) с captive DNS (любое имя → адрес платы, чужие пути →
// редирект на «/»), на странице список сетей 2,4 ГГц с уровнем сигнала, поле ручного ввода и пароль.
// Портал неблокирующий: работает параллельно с попытками подключения к сохранённой сети и с
// поливом. Поднимается, когда сети нет в настройках, по кнопке и сам — если сохранённая сеть
// не поднялась PORTAL_AFTER_SEC. После сохранения сети плата перезагружается (portalSaved()).
#pragma once
#include <Arduino.h>

class DNSServer;
class WebServer;

class WifiLink {
 public:
  static constexpr const char* AP_PASSWORD = nullptr;   // открытая точка доступа: портал живёт только при настройке
  static constexpr uint32_t RECONNECT_SEC = 20;
  static constexpr uint32_t PORTAL_AFTER_SEC = 180;   // без связи столько секунд → портал сам

  void begin();                     // прочитать /wifi.json, перейти в STA
  bool hasConfig() const { return _ssid.length() > 0; }
  bool connect();                   // начать подключение (неблокирующе)
  bool tick();                      // из главного цикла раз в секунду: true, если сеть есть
  bool connected() const;
  int rssi() const;
  String ip() const;
  const String& ssid() const { return _ssid; }

  void startPortal();               // поднять точку доступа и страницу (если ещё не подняты)
  void stopPortal();
  bool portalActive() const { return _srv != nullptr; }
  bool portalSaved() const { return _saved; }   // сеть сохранена — пора перезагружаться
  const char* apName() const { return _apName; }

 private:
  String _ssid, _pass;
  uint32_t _triedAt = 0;
  uint32_t _downSince = 0;          // millis начала периода без связи (0 = связь есть)
  bool _wasUp = false;
  bool _started = false;
  bool _saved = false;
  char _apName[24] = "";
  DNSServer* _dns = nullptr;
  WebServer* _srv = nullptr;
  String _opts;                     // <option> списка сетей
  bool save(const String& ssid, const String& pass);
  String scanOptions();
  void sendPage();
};
