// wifi_portal.h 📡 Wi-Fi контроллера: подключение к сохранённой сети, иначе портал настройки.
//
// Сеть хранится в cfgFs(): /wifi.json {"ssid":..,"pass":..}. Без неё (или при зажатой кнопке
// на старте) поднимается точка доступа «DripIrrigation-XXXX» (пароль irrigation), captive
// portal: свой DNS отвечает адресом платы на любое имя, чужие пути → редирект на «/»,
// поэтому телефон сам предлагает «войти в сеть». На странице — выпадающий список сетей
// с уровнем сигнала, поле для ручного ввода, пароль. После сохранения плата перезагружается.
#pragma once
#include <Arduino.h>

class WifiLink {
 public:
  static constexpr const char* AP_PASSWORD = "irrigation";
  static constexpr uint32_t RECONNECT_SEC = 20;

  void begin();                     // прочитать /wifi.json, перейти в STA
  bool hasConfig() const { return _ssid.length() > 0; }
  bool connect();                   // начать подключение (неблокирующе)
  bool tick();                      // из главного цикла: true, если сеть есть; переподключение раз в 20 с
  bool connected() const;
  int rssi() const;
  String ip() const;
  const String& ssid() const { return _ssid; }

  // Портал настройки: блокирующий, возвращается после сохранения сети (дальше — ESP.restart()).
  // ledBlink — мигать светодиодом, пока открыт портал.
  void portal(void (*ledBlink)(bool) = nullptr);

 private:
  String _ssid, _pass;
  uint32_t _triedAt = 0;
  bool _wasUp = false;
  bool _started = false;
  bool save(const String& ssid, const String& pass);
};
