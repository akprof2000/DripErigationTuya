// tuya.h ☁️ Клиент облака Tuya по протоколу TuyaOpen 2.3 (порт mpy/lib/tuya.py).
//
// Состояния: wait (пауза перед попыткой) → bind (ждём привязку: MQTT acon_<uuid>, топик d/ai/<uuid>,
// по токену — активация thing.device.opensdk.active через ATOP) → online (MQTT devId,
// smart/device/in|out/<devId>). Любая ошибка сети → wait с экспоненциальной паузой 5…300 с.
// Состояние привязки (region, env, devId, secKey, localKey) — JSON в cfgFs(): /tuya_state.json.
// Все сетевые вызовы блокирующие (TLS ~2–3 с), поэтому loop() зовётся из главного цикла раз в секунду.
#pragma once
#include <Arduino.h>
#include <ArduinoJson.h>
#include <functional>
#include "mqtt.h"

class Tuya {
 public:
  Tuya(const String& pid, const String& uuid, const String& authkey, const String& version,
       const char* statePath);
  void begin();                                 // прочитать /tuya_state.json
  void loop();                                  // шаг автомата (вызывать каждую секунду)
  bool online() const { return _state == State::Online; }
  bool activated() const { return _st.devId.length() > 0; }
  const String& devId() const { return _st.devId; }
  String qrUrl() const;                         // ссылка для QR привязки
  void setPaused(bool paused);                  // Wi-Fi пропал: рвём соединение, не переподключаемся

  // Отчёт DP: dps — {"101": true, ...} (ключи — id), t — unix (0 = сейчас). Протокол 4 (push) с t,
  // иначе 5 (dps). false при сбое (вызывающий кладёт в очередь).
  bool push(JsonObjectConst dps, uint32_t t = 0);
  // Произвольное сообщение облаку: протокол + data (OTA-прогресс 16 и т. п.)
  bool publish(int protocol, JsonObjectConst data);
  // ATOP-вызов от имени устройства (tuya.device.upgrade.get и т. п.). result — поле result ответа.
  bool atopDev(const char* api, const char* ver, JsonObjectConst data, JsonDocument& result, String& err);

  std::function<void()> onConnected;                                // подключились как устройство
  std::function<void(JsonObjectConst dps)> onDps;                    // команда из облака (протокол 5)
  std::function<void()> onReset;                                     // устройство удалили из приложения (11)
  std::function<void(const String& url)> onQrcode;                   // показать QR привязки
  std::function<void(int protocol, JsonObjectConst data)> onProtocol; // прочие протоколы (15 — OTA)

 private:
  enum class State { Wait, Bind, Online };
  struct Stored { String region, env = "pro", devId, secKey, localKey; };
  String _pid, _uuid, _authkey, _version, _statePath;
  Stored _st;
  State _state = State::Wait;
  MqttClient _mq;
  bool _paused = false;
  uint32_t _retryAt = 0;      // millis
  uint32_t _backoff = 5;      // секунд
  uint32_t _seq = 0;
  String _mqttHost, _atopUrl;
  uint16_t _mqttPort = 8883;

  void loadState();
  void saveState() const;
  bool endpoints();                                       // h1.iot-dns.com → mqtt/atop адреса
  void start();                                           // подключение bind/online
  void fail(const String& why);
  void onBindMessage(const String& topic, const uint8_t* p, size_t n);
  void onDeviceMessage(const String& topic, const uint8_t* p, size_t n);
  bool activate(const String& token, const String& region, const String& env);
  bool atop(const String& api, const String& ver, const String& bodyJson, const String& devIdOrUuid,
            const String& key, JsonDocument& result, String& err);   // общий ATOP (et=3, GCM)
  bool packSend(const String& topic, const uint8_t key[16], const String& json);   // кадр 2.3 GCM
  bool unpack(const uint8_t key[16], const uint8_t* p, size_t n, String& json);     // 2.3 GCM / 2.2 ECB
  void deviceKey(uint8_t out[16]) const;                  // ключ кадров online: localKey
};
