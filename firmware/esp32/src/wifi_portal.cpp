// wifi_portal.cpp 📡 Подключение к Wi-Fi и captive-портал настройки (порт mpy/lib/wifi.py)
#include "wifi_portal.h"
#include <ArduinoJson.h>
#include <DNSServer.h>
#include <WebServer.h>
#include <WiFi.h>
#include "log.h"
#include "storage.h"

static const char* CONF = "/wifi.json";

static const char PAGE_HEAD[] PROGMEM = R"HTML(<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Drip Irrigation — Wi-Fi</title>
<style>body{font-family:sans-serif;max-width:360px;margin:40px auto;padding:0 16px}
input,select{width:100%;padding:10px;margin:6px 0 14px;font-size:16px;box-sizing:border-box}
button{width:100%;padding:12px;font-size:16px;background:#1989fa;color:#fff;border:0;border-radius:8px}
a{color:#1989fa}</style></head>
<body><h2>Капельный полив</h2><p>Подключение к Wi-Fi</p>
<form method="post" action="/"><label>Сеть</label>
<select name="net" onchange="document.getElementById('s').value=this.value">
<option value="">— выбрать из списка —</option>)HTML";
static const char PAGE_TAIL[] PROGMEM = R"HTML(</select>
<label>или ввести имя сети (SSID)</label><input id="s" name="ssid" value="%CUR%">
<label>Пароль</label><input name="pass" type="password"><button>Сохранить</button></form>
<p><a href="/?scan=1">Обновить список сетей</a></p></body></html>)HTML";

static String htmlEsc(const String& s) {
  String o;
  for (char c : s) {
    if (c == '&') o += "&amp;"; else if (c == '<') o += "&lt;"; else if (c == '>') o += "&gt;";
    else if (c == '"') o += "&quot;"; else o += c;
  }
  return o;
}

void WifiLink::begin() {
  JsonDocument doc;
  String raw = readFile(cfgFs(), CONF);
  if (raw.length() && !deserializeJson(doc, raw)) {
    _ssid = doc["ssid"] | "";
    _pass = doc["pass"] | "";
  }
  WiFi.mode(WIFI_STA);
  WiFi.setHostname("DripIrrigation");
  WiFi.setAutoReconnect(false);   // переподключаемся сами, по таймеру
  WiFi.setSleep(false);
}

bool WifiLink::save(const String& ssid, const String& pass) {
  JsonDocument doc;
  doc["ssid"] = ssid;
  doc["pass"] = pass;
  String out;
  serializeJson(doc, out);
  return writeFile(cfgFs(), CONF, out);
}

bool WifiLink::connect() {
  if (!hasConfig()) return false;
  LOG_I("wifi: подключение к %s", _ssid.c_str());
  if (_started) WiFi.disconnect(false, false);
  WiFi.begin(_ssid.c_str(), _pass.c_str());
  _started = true;
  _triedAt = millis();
  return true;
}

bool WifiLink::connected() const { return WiFi.status() == WL_CONNECTED; }
int WifiLink::rssi() const { return connected() ? WiFi.RSSI() : 0; }
String WifiLink::ip() const { return WiFi.localIP().toString(); }

bool WifiLink::tick() {
  bool up = connected();
  if (up != _wasUp) {
    _wasUp = up;
    if (up) LOG_I("wifi: подключено, IP %s, RSSI %d", ip().c_str(), WiFi.RSSI());
    else LOG_W("wifi: потеряно");
  }
  if (!up && hasConfig() && (_triedAt == 0 || millis() - _triedAt > RECONNECT_SEC * 1000)) connect();
  return up;
}

// ---------------- портал настройки
static String scanOptions(const String& current) {
  int n = WiFi.scanNetworks();
  String opts;
  // сильные первыми, без дублей (несколько точек одной сети)
  for (int pass = 0; pass < n; pass++) {
    int best = -1;
    for (int i = 0; i < n; i++) {
      if (WiFi.SSID(i).isEmpty()) continue;
      bool used = false;
      for (int j = 0; j < i; j++) if (WiFi.SSID(j) == WiFi.SSID(i)) { used = true; break; }   // дубль
      if (used) continue;
      bool done = opts.indexOf("value=\"" + htmlEsc(WiFi.SSID(i)) + "\"") >= 0;
      if (done) continue;
      if (best < 0 || WiFi.RSSI(i) > WiFi.RSSI(best)) best = i;
    }
    if (best < 0) break;
    String s = htmlEsc(WiFi.SSID(best));
    opts += "<option value=\"" + s + "\"" + (WiFi.SSID(best) == current ? " selected" : "") + ">" + s +
            " (" + String(WiFi.RSSI(best)) + " dBm)</option>";
  }
  WiFi.scanDelete();
  return opts;
}

void WifiLink::portal(void (*ledBlink)(bool)) {
  uint8_t mac[6];
  WiFi.macAddress(mac);
  char ssid[32];
  snprintf(ssid, sizeof(ssid), "DripIrrigation-%02X%02X", mac[4], mac[5]);
  WiFi.mode(WIFI_AP_STA);
  WiFi.softAP(ssid, AP_PASSWORD);
  IPAddress ip = WiFi.softAPIP();
  LOG_I("wifi: портал %s / %s, адрес http://%s", ssid, AP_PASSWORD, ip.toString().c_str());

  String opts = scanOptions(_ssid);
  DNSServer dns;
  dns.start(53, "*", ip);           // captive DNS: любое имя → плата
  WebServer srv(80);
  bool saved = false;
  String current = _ssid;

  auto page = [&]() {
    String html = FPSTR(PAGE_HEAD);
    html += opts;
    String tail = FPSTR(PAGE_TAIL);
    tail.replace("%CUR%", htmlEsc(current));
    html += tail;
    srv.send(200, "text/html; charset=utf-8", html);
  };
  srv.on("/", HTTP_GET, [&]() {
    LOG_I("wifi: %s ← GET /", srv.client().remoteIP().toString().c_str());
    if (srv.hasArg("scan")) opts = scanOptions(current);
    page();
  });
  srv.on("/", HTTP_POST, [&]() {
    String chosen = srv.arg("ssid");
    if (chosen.isEmpty()) chosen = srv.arg("net");
    LOG_I("wifi: %s ← POST / (%s)", srv.client().remoteIP().toString().c_str(), chosen.c_str());
    if (chosen.length()) {
      save(chosen, srv.arg("pass"));
      srv.send(200, "text/html; charset=utf-8", "<meta charset=utf-8><h2>Сохранено. Контроллер перезагружается…</h2>");
      saved = true;
    } else {
      page();
    }
  });
  srv.onNotFound([&]() {   // пробы captive-portal (generate_204, hotspot-detect…) и всё чужое → на главную
    LOG_D("wifi: %s ← %s", srv.client().remoteIP().toString().c_str(), srv.uri().c_str());
    srv.sendHeader("Location", "http://" + ip.toString() + "/", true);
    srv.send(302, "text/plain", "");
  });
  srv.begin();

  uint32_t lastBlink = 0;
  bool on = false;
  while (!saved) {
    dns.processNextRequest();
    srv.handleClient();
    if (ledBlink && millis() - lastBlink > 500) { lastBlink = millis(); on = !on; ledBlink(on); }
    delay(2);
  }
  delay(500);   // отдать ответ клиенту
  srv.stop();
  dns.stop();
  WiFi.softAPdisconnect(true);
}
