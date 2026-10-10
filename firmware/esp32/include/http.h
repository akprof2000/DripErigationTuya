// http.h 🌐 HTTPS-запросы к облаку Tuya (порт http_open/http_post из mpy/lib/compat.py).
// Свой HTTP/1.1 поверх WiFiClientSecure (без проверки сертификата — как в MicroPython-версии,
// TODO: CA Tuya). Обязательно HTTP/1.1 + Connection: close: iot-dns Tuya отвечает на HTTP/1.0
// кодом 426. Ответ ожидается с Content-Length (Accept-Encoding: identity); chunked не нужен.
#pragma once
#include <Arduino.h>
#include <ArduinoJson.h>
#include <WiFiClientSecure.h>

struct HttpResponse {
  int status = 0;
  int32_t length = -1;          // Content-Length или -1
  WiFiClientSecure client;      // открытое соединение: тело читать из client (после заголовков)
  bool ok() const { return status == 200; }
};

// Открыть запрос; тело ответа остаётся в resp.client (для потокового чтения, OTA).
// Возвращает false, если соединиться/получить заголовки не удалось.
bool httpOpen(const char* method, const String& url, const uint8_t* body, size_t bodyLen,
              const char* contentType, HttpResponse& resp, uint32_t timeoutMs = 15000);

// POST с JSON-ответом (сразу читает тело и закрывает). false при ошибке сети / HTTP ≠ 200 / не JSON.
bool httpPostJson(const String& url, const String& body, const char* contentType, JsonDocument& result,
                  String& err, uint32_t timeoutMs = 15000);

// Разбор URL: https://host[:port]/path → host, port, path, tls
bool parseUrl(const String& url, String& host, uint16_t& port, String& path, bool& tls);
