// mqtt.cpp 📨 Минимальный MQTT 3.1.1 поверх TLS (порт mpy/lib/mqtt.py).
//
// Ровно то, что нужно Tuya: CONNECT с логином, SUBSCRIBE QoS 1, PUBLISH QoS 1 (PUBACK не ждём —
// облако подтверждает DP своим ответом), приём PUBLISH с ответным PUBACK, PINGREQ по keepalive.
// Один поток: loop() зовётся из главного цикла и не блокирует дольше timeoutMs (+ чтение
// уже начавшегося пакета, не дольше RX_TIMEOUT_MS).
#include "mqtt.h"

#include "log.h"

namespace {
enum : uint8_t { CONNECT = 1, CONNACK = 2, PUBLISH = 3, PUBACK = 4, SUBSCRIBE = 8, SUBACK = 9,
                 PINGREQ = 12, PINGRESP = 13, DISCONNECT = 14 };
constexpr uint32_t CONNECT_TIMEOUT_MS = 15000;
constexpr uint32_t RX_TIMEOUT_MS = 15000;     // остаток пакета после первого байта
constexpr size_t MAX_PACKET = 16384;          // кадры Tuya — сотни байт; защита от мусора
constexpr int MAX_PACKETS_PER_LOOP = 16;      // не держать главный цикл при шквале сообщений

// Строка MQTT: длина (2 байта BE) + байты
void putStr(uint8_t* out, size_t& pos, const String& s) {
  const size_t n = s.length();
  out[pos++] = (uint8_t)(n >> 8);
  out[pos++] = (uint8_t)n;
  memcpy(out + pos, s.c_str(), n);
  pos += n;
}

// Прочитать до n байт: > 0 — прочитано, 0 — таймаут, -1 — соединение закрыто
int readSome(WiFiClientSecure& c, uint8_t* buf, size_t n, uint32_t timeoutMs) {
  const uint32_t start = millis();
  for (;;) {
    if (c.available() > 0) {
      int got = c.read(buf, n);
      if (got > 0) return got;
    }
    if (!c.connected()) return -1;
    if (millis() - start >= timeoutMs) return 0;
    delay(1);
  }
}

bool readExact(WiFiClientSecure& c, uint8_t* buf, size_t n, uint32_t timeoutMs) {
  size_t got = 0;
  while (got < n) {
    int r = readSome(c, buf + got, n - got, timeoutMs);
    if (r <= 0) return false;
    got += r;
  }
  return true;
}
}  // namespace

uint16_t MqttClient::nextPid() {
  _pid = (uint16_t)(_pid % 65535 + 1);
  return _pid;
}

// Отправить пакет одним TLS-кадром: фиксированный заголовок + remaining length + тело
bool MqttClient::send(uint8_t type, uint8_t flags, const uint8_t* body, size_t len) {
  if (!_client.connected()) {
    _connected = false;
    _err = "нет соединения";
    return false;
  }
  uint8_t* pkt = (uint8_t*)malloc(len + 5);
  if (!pkt) {
    _err = "нет памяти";
    return false;
  }
  size_t pos = 0;
  pkt[pos++] = (uint8_t)((type << 4) | (flags & 0x0F));
  size_t n = len;
  do {
    uint8_t b = n % 128;
    n /= 128;
    pkt[pos++] = n ? (b | 0x80) : b;
  } while (n);
  if (len) memcpy(pkt + pos, body, len);
  pos += len;
  const bool ok = _client.write(pkt, pos) == pos;
  free(pkt);
  if (!ok) {
    _err = "ошибка записи";
    _connected = false;
    return false;
  }
  _lastTx = millis();
  return true;
}

// Ждать первый байт не дольше timeoutMs, затем дочитать пакет (RX_TIMEOUT_MS).
// data выделяется malloc (nullptr при len == 0) — освобождает вызывающий.
// false: нет пакета (connected() остаётся true) или обрыв (connected() == false).
bool MqttClient::readPacket(uint8_t& type, uint8_t& flags, uint8_t*& data, size_t& len, uint32_t timeoutMs) {
  data = nullptr;
  len = 0;
  uint8_t first;
  int r = readSome(_client, &first, 1, timeoutMs);
  if (r < 0) {
    _err = "соединение закрыто";
    _connected = false;
    return false;
  }
  if (r == 0) return false;   // тишина — это нормально
  type = first >> 4;
  flags = first & 0x0F;
  size_t n = 0, mult = 1;
  for (int i = 0; i < 4; i++) {
    uint8_t b;
    if (!readExact(_client, &b, 1, RX_TIMEOUT_MS)) {
      _err = "обрыв в заголовке";
      _connected = false;
      return false;
    }
    n += (size_t)(b & 0x7F) * mult;
    mult *= 128;
    if (!(b & 0x80)) break;
  }
  if (n > MAX_PACKET) {
    _err = "пакет слишком большой";
    _connected = false;
    return false;
  }
  if (n) {
    data = (uint8_t*)malloc(n);
    if (!data) {
      _err = "нет памяти под пакет";
      _connected = false;
      return false;
    }
    if (!readExact(_client, data, n, RX_TIMEOUT_MS)) {
      free(data);
      data = nullptr;
      _err = "обрыв в теле пакета";
      _connected = false;
      return false;
    }
  }
  len = n;
  return true;
}

bool MqttClient::connect(const String& host, uint16_t port, const String& clientId, const String& user,
                         const String& password, uint16_t keepaliveSec) {
  close();
  _keepalive = keepaliveSec;
  _err = "";
  _client.setInsecure();   // TODO: CA Tuya (см. http.h)
  _client.setHandshakeTimeout(CONNECT_TIMEOUT_MS / 1000);
  if (!_client.connect(host.c_str(), port, (int32_t)CONNECT_TIMEOUT_MS)) {
    _err = "TLS: нет соединения с " + host;
    return false;
  }
  _client.setTimeout(RX_TIMEOUT_MS / 1000);
  _connected = true;   // send() требует; при отказе CONNACK снимем
  _pingSent = 0;

  // CONNECT: "MQTT", уровень 4, флаги 0xC2 (user + pass + clean session), keepalive, строки
  const size_t bodyLen = 10 + 2 + clientId.length() + 2 + user.length() + 2 + password.length();
  uint8_t* body = (uint8_t*)malloc(bodyLen);
  if (!body) {
    _err = "нет памяти";
    close();
    return false;
  }
  size_t pos = 0;
  putStr(body, pos, "MQTT");
  body[pos++] = 4;
  body[pos++] = 0xC2;
  body[pos++] = (uint8_t)(keepaliveSec >> 8);
  body[pos++] = (uint8_t)keepaliveSec;
  putStr(body, pos, clientId);
  putStr(body, pos, user);
  putStr(body, pos, password);
  const bool sent = send(CONNECT, 0, body, pos);
  free(body);
  if (!sent) {
    close();
    return false;
  }

  uint8_t type, flags, *data;
  size_t len;
  if (!readPacket(type, flags, data, len, CONNECT_TIMEOUT_MS)) {
    if (_err.length() == 0) _err = "нет CONNACK";
    close();
    return false;
  }
  const bool ok = type == CONNACK && len >= 2 && data[1] == 0;
  if (!ok) _err = "CONNACK отказ: код " + String(len >= 2 ? data[1] : 255);
  free(data);
  if (!ok) {
    close();
    return false;
  }
  _lastTx = millis();
  LOG_D("mqtt: подключено к %s:%u", host.c_str(), port);
  return true;
}

bool MqttClient::subscribe(const String& topic, uint8_t qos) {
  if (!_connected) return false;
  const size_t n = 2 + 2 + topic.length() + 1;
  uint8_t* body = (uint8_t*)malloc(n);
  if (!body) return false;
  size_t pos = 0;
  const uint16_t pid = nextPid();
  body[pos++] = (uint8_t)(pid >> 8);
  body[pos++] = (uint8_t)pid;
  putStr(body, pos, topic);
  body[pos++] = qos;
  const bool ok = send(SUBSCRIBE, 2, body, pos);   // флаги 0010 обязательны для SUBSCRIBE
  free(body);
  return ok;
}

bool MqttClient::publish(const String& topic, const uint8_t* payload, size_t len, uint8_t qos) {
  if (!_connected) return false;
  const size_t n = 2 + topic.length() + (qos ? 2 : 0) + len;
  uint8_t* body = (uint8_t*)malloc(n);
  if (!body) return false;
  size_t pos = 0;
  putStr(body, pos, topic);
  if (qos) {
    const uint16_t pid = nextPid();
    body[pos++] = (uint8_t)(pid >> 8);
    body[pos++] = (uint8_t)pid;
  }
  if (len) memcpy(body + pos, payload, len);
  pos += len;
  const bool ok = send(PUBLISH, (uint8_t)(qos << 1), body, pos);
  free(body);
  return ok;
}

void MqttClient::handlePacket(uint8_t type, uint8_t flags, const uint8_t* data, size_t len) {
  if (type == PUBLISH) {
    if (len < 2) return;
    const size_t tlen = ((size_t)data[0] << 8) | data[1];
    if (2 + tlen > len) return;
    String topic((const char*)data + 2, tlen);
    size_t pos = 2 + tlen;
    if ((flags >> 1) & 3) {   // QoS 1/2: подтверждаем идентификатором пакета
      if (pos + 2 > len) return;
      send(PUBACK, 0, data + pos, 2);
      pos += 2;
    }
    if (onMessage) onMessage(topic, data + pos, len - pos);
  } else if (type == PINGRESP) {
    _pingSent = 0;
  }
  // PUBACK/SUBACK: не ждём и не проверяем (как в mqtt.py)
}

bool MqttClient::loop(uint32_t timeoutMs) {
  if (!_connected) return false;
  const uint32_t now = millis();
  if (_pingSent && now - _pingSent > (uint32_t)_keepalive * 1000) {
    _err = "нет PINGRESP";
    close();
    return false;
  }
  if (!_pingSent && now - _lastTx > (uint32_t)_keepalive * 500) {
    if (!send(PINGREQ, 0, nullptr, 0)) {
      close();
      return false;
    }
    _pingSent = now ? now : 1;   // 0 означает «не ждём ответа»
  }
  // Первый пакет ждём до timeoutMs, следующие берём только если уже пришли
  uint32_t wait = timeoutMs;
  for (int i = 0; i < MAX_PACKETS_PER_LOOP && _connected; i++) {
    uint8_t type, flags, *data;
    size_t len;
    if (!readPacket(type, flags, data, len, wait)) break;
    handlePacket(type, flags, data, len);
    free(data);
    wait = 0;
  }
  if (!_connected) close();   // обрыв: освободить сокет
  return _connected;
}

void MqttClient::close() {
  if (_connected && _client.connected()) send(DISCONNECT, 0, nullptr, 0);
  _client.stop();
  _connected = false;
  _pingSent = 0;
}
