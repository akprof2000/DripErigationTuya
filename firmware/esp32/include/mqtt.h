// mqtt.h 📨 Минимальный клиент MQTT 3.1.1 поверх TLS (порт mpy/lib/mqtt.py).
// Только то, что нужно Tuya: CONNECT с логином/паролем, SUBSCRIBE qos1, PUBLISH qos0/1,
// PINGREQ по keepalive, приём PUBLISH. Без TLS-проверки сертификата (см. http.h).
#pragma once
#include <Arduino.h>
#include <WiFiClientSecure.h>
#include <functional>

class MqttClient {
 public:
  using MessageCb = std::function<void(const String& topic, const uint8_t* payload, size_t len)>;

  MqttClient() {}
  // Подключиться (TLS + CONNECT, ждёт CONNACK до 15 с). false + lastError при отказе.
  bool connect(const String& host, uint16_t port, const String& clientId, const String& user,
               const String& password, uint16_t keepaliveSec = 60);
  bool subscribe(const String& topic, uint8_t qos = 1);
  bool publish(const String& topic, const uint8_t* payload, size_t len, uint8_t qos = 1);
  // Обработать входящие пакеты (не дольше timeoutMs) и поддержать keepalive.
  // false, если соединение потеряно (тогда connected() == false).
  bool loop(uint32_t timeoutMs = 50);
  bool connected() const { return _connected; }
  void close();
  const String& lastError() const { return _err; }
  MessageCb onMessage;

 private:
  WiFiClientSecure _client;
  bool _connected = false;
  uint16_t _keepalive = 60;
  uint16_t _pid = 0;
  uint32_t _lastTx = 0;
  uint32_t _pingSent = 0;   // 0 = PINGREQ не ждёт ответа
  String _err;
  bool send(uint8_t type, uint8_t flags, const uint8_t* body, size_t len);
  bool readPacket(uint8_t& type, uint8_t& flags, uint8_t*& data, size_t& len, uint32_t timeoutMs);
  void handlePacket(uint8_t type, uint8_t flags, const uint8_t* data, size_t len);
  uint16_t nextPid();
};
