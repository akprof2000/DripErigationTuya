// http.cpp 🌐 Свой HTTP/1.1-клиент поверх WiFiClientSecure (порт http_open/http_post из compat.py).
//
// Почему не HTTPClient из Arduino: iot-dns Tuya отвечает 426 на HTTP/1.0 и нам нужен доступ
// к открытому соединению для потокового чтения образа OTA. Читаем заголовки побайтно
// (их ~300 байт), поэтому «лишние» байты тела в буфере не остаются — тело читается из client.
//
// WiFiClientSecure::read() не блокирует: возвращает -1, если в TLS-буфере пусто. Поэтому все
// чтения идут через readSome() с опросом available() до истечения таймаута.
#include "http.h"

#include "log.h"

static const char* UA = "TUYA_IOT_SDK";   // как в TuyaOpen; iot-dns и ATOP на него не ругаются

bool parseUrl(const String& url, String& host, uint16_t& port, String& path, bool& tls) {
  int p = url.indexOf("://");
  if (p < 0) return false;
  const String scheme = url.substring(0, p);
  if (scheme == "https") {
    tls = true;
  } else if (scheme == "http") {
    tls = false;
  } else {
    return false;
  }
  const String rest = url.substring(p + 3);
  int slash = rest.indexOf('/');
  String hostPort = slash < 0 ? rest : rest.substring(0, slash);
  path = slash < 0 ? String("/") : rest.substring(slash);
  int colon = hostPort.indexOf(':');
  if (colon >= 0) {
    port = (uint16_t)hostPort.substring(colon + 1).toInt();
    host = hostPort.substring(0, colon);
  } else {
    port = tls ? 443 : 80;
    host = hostPort;
  }
  return host.length() > 0 && port != 0;
}

// Прочитать до n байт. > 0 — прочитано, 0 — таймаут, -1 — соединение закрыто.
static int readSome(WiFiClientSecure& c, uint8_t* buf, size_t n, uint32_t timeoutMs) {
  const uint32_t start = millis();
  for (;;) {
    int avail = c.available();
    if (avail > 0) {
      int got = c.read(buf, n);
      if (got > 0) return got;
    }
    if (!c.connected()) return -1;
    if (millis() - start >= timeoutMs) return 0;
    delay(1);
  }
}

bool httpOpen(const char* method, const String& url, const uint8_t* body, size_t bodyLen,
              const char* contentType, HttpResponse& resp, uint32_t timeoutMs) {
  String host, path;
  uint16_t port;
  bool tls;
  resp.status = 0;
  resp.length = -1;
  if (!parseUrl(url, host, port, path, tls)) {
    LOG_E("http: плохой URL");
    return false;
  }
  if (!tls) {   // облако Tuya всегда https; WiFiClientSecure не умеет открытый TCP
    LOG_E("http: поддерживается только https (%s)", host.c_str());
    return false;
  }
  WiFiClientSecure& c = resp.client;
  c.stop();
  c.setInsecure();   // TODO: CA Tuya во флеш
  c.setHandshakeTimeout(timeoutMs / 1000 > 0 ? timeoutMs / 1000 : 1);
  if (!c.connect(host.c_str(), port, (int32_t)timeoutMs)) {
    char eb[96] = "";
    int ec = c.lastError(eb, sizeof(eb));   // -1 обычно DNS/TCP, иначе код mbedtls рукопожатия
    LOG_W("http: нет соединения с %s:%u (%d %s)", host.c_str(), port, ec, eb);
    return false;
  }
  c.setTimeout(timeoutMs / 1000 > 0 ? timeoutMs / 1000 : 1);

  // Заголовки запроса — ровно как в compat.http_open: HTTP/1.1, Connection: close, identity
  String req;
  req.reserve(256 + path.length());
  req += method;
  req += ' ';
  req += path;
  req += " HTTP/1.1\r\nHost: ";
  req += host;
  req += "\r\nConnection: close\r\nAccept-Encoding: identity\r\nUser-Agent: ";
  req += UA;
  req += "\r\n";
  if (body) {
    req += "Content-Length: ";
    req += bodyLen;
    req += "\r\n";
    if (contentType) {
      req += "Content-Type: ";
      req += contentType;
      req += "\r\n";
    }
  }
  req += "\r\n";
  if (c.write((const uint8_t*)req.c_str(), req.length()) != req.length() ||
      (body && bodyLen && c.write(body, bodyLen) != bodyLen)) {
    LOG_W("http: не удалось отправить запрос");
    c.stop();
    return false;
  }

  // Заголовки ответа: читаем побайтно до пустой строки (тело остаётся в client)
  String line;
  line.reserve(128);
  bool first = true;
  uint8_t ch;
  size_t total = 0;
  for (;;) {
    int r = readSome(c, &ch, 1, timeoutMs);
    if (r <= 0) {
      LOG_W("http: обрыв до конца заголовков (%s)", r == 0 ? "таймаут" : "закрыто");
      c.stop();
      return false;
    }
    if (++total > 8192) {
      LOG_W("http: заголовки слишком длинные");
      c.stop();
      return false;
    }
    if (ch == '\r') continue;
    if (ch != '\n') {
      line += (char)ch;
      continue;
    }
    if (line.length() == 0) break;   // пустая строка — конец заголовков
    if (first) {                       // "HTTP/1.1 200 OK"
      first = false;
      int sp = line.indexOf(' ');
      resp.status = sp < 0 ? 0 : line.substring(sp + 1).toInt();
    } else {
      int colon = line.indexOf(':');
      if (colon > 0) {
        String name = line.substring(0, colon);
        name.trim();
        name.toLowerCase();
        if (name == "content-length") {
          String v = line.substring(colon + 1);
          v.trim();
          resp.length = v.toInt();
        }
      }
    }
    line = "";
  }
  if (first) {
    LOG_W("http: нет строки статуса");
    c.stop();
    return false;
  }
  LOG_D("http: %s %s → %d, длина %d", method, host.c_str(), resp.status, (int)resp.length);
  return true;
}

bool httpPostJson(const String& url, const String& body, const char* contentType, JsonDocument& result,
                  String& err, uint32_t timeoutMs) {
  HttpResponse resp;
  if (!httpOpen("POST", url, (const uint8_t*)body.c_str(), body.length(), contentType, resp, timeoutMs)) {
    err = "нет связи";
    return false;
  }
  // Тело целиком: Content-Length или до закрытия (ответы облака — сотни байт, предел 16 КБ)
  const size_t limit = 16384;
  const size_t want = resp.length >= 0 ? (size_t)resp.length : limit;
  if (want > limit) {
    err = "ответ слишком большой";
    resp.client.stop();
    return false;
  }
  String data;
  data.reserve(want);
  uint8_t buf[256];
  while (data.length() < want) {
    size_t chunk = want - data.length();
    if (chunk > sizeof(buf)) chunk = sizeof(buf);
    int r = readSome(resp.client, buf, chunk, timeoutMs);
    if (r < 0) break;   // закрыто
    if (r == 0) {
      err = "таймаут чтения тела";
      resp.client.stop();
      return false;
    }
    data.concat((const char*)buf, r);
  }
  resp.client.stop();
  if (resp.length >= 0 && data.length() < want) {
    err = "тело оборвано";
    return false;
  }
  if (resp.status != 200) {
    err = "HTTP " + String(resp.status) + ": " + data.substring(0, 80);
    return false;
  }
  DeserializationError e = deserializeJson(result, data);
  if (e) {
    err = String("не JSON: ") + e.c_str();
    return false;
  }
  return true;
}
