// wifi_portal.cpp 📡 Подключение к Wi-Fi и неблокирующий captive-портал настройки
#include "wifi_portal.h"
#include <ArduinoJson.h>
#include <DNSServer.h>
#include <WebServer.h>
#include <WiFi.h>
#include <qrcode.h>
#include "log.h"
#include "storage.h"

static const char* CONF = "/wifi.json";

static const char PAGE_HEAD[] PROGMEM = R"HTML(<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Капельный полив — Wi-Fi</title>
<style>
:root{--b:#1989fa;--t:#1f2329;--m:#8a9099;--bg:#eef3f8}
*{box-sizing:border-box}body{margin:0;background:var(--bg);font:16px/1.45 -apple-system,Segoe UI,Roboto,sans-serif;color:var(--t)}
.wrap{max-width:420px;margin:0 auto;padding:24px 16px 40px}
.logo{display:flex;align-items:center;gap:12px;margin-bottom:20px}
.logo svg{width:44px;height:44px;flex:none}.logo h1{font-size:20px;margin:0;line-height:1.2}.logo p{margin:2px 0 0;color:var(--m);font-size:13px}
.card{background:#fff;border-radius:16px;padding:20px;box-shadow:0 4px 16px rgba(20,40,80,.08)}
label{display:block;font-size:13px;color:var(--m);margin:14px 0 6px}label:first-child{margin-top:0}
select,input{width:100%;padding:12px 14px;font-size:16px;border:1px solid #d9dee5;border-radius:10px;background:#fafbfc;color:var(--t);appearance:none;-webkit-appearance:none}
select{background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='8'%3E%3Cpath d='M1 1l5 5 5-5' fill='none' stroke='%238a9099' stroke-width='2'/%3E%3C/svg%3E");background-repeat:no-repeat;background-position:right 14px center;padding-right:36px}
select:focus,input:focus{outline:none;border-color:var(--b);background:#fff}
.row{position:relative}.row button{position:absolute;right:6px;top:6px;bottom:6px;width:auto;padding:0 12px;background:none;color:var(--b);font-size:13px;border:0;border-radius:8px}
.btn{width:100%;margin-top:22px;padding:14px;font-size:16px;font-weight:600;color:#fff;background:var(--b);border:0;border-radius:12px;cursor:pointer}
.btn:active{opacity:.85}.link{display:block;text-align:center;margin-top:14px;color:var(--b);text-decoration:none;font-size:14px}
.hint{color:var(--m);font-size:13px;margin:16px 0 0}.ok{text-align:center;padding:40px 0}.ok h2{margin:12px 0 6px}
</style></head><body><div class="wrap">
<div class="logo"><svg viewBox="0 0 48 48" fill="none"><circle cx="24" cy="24" r="22" fill="#1989fa"/><path d="M24 11c-5 7-9 11.5-9 16.5A9 9 0 0 0 33 27.5C33 22.5 29 18 24 11z" fill="#fff"/><path d="M20 28.5a4 4 0 0 0 4 4" stroke="#1989fa" stroke-width="2" stroke-linecap="round"/></svg>
<div><h1>Капельный полив</h1><p>Подключение контроллера к Wi-Fi</p></div></div>
<div class="card"><form method="post" action="/">
<label for="n">Сеть Wi-Fi (2,4 ГГц)</label>
<select id="n" name="net" onchange="document.getElementById('s').value=this.value">
<option value="">— выбрать из списка —</option>)HTML";
static const char PAGE_TAIL[] PROGMEM = R"HTML(</select>
<label for="s">Имя сети вручную, если её нет в списке</label>
<input id="s" name="ssid" value="%CUR%" autocomplete="off" autocapitalize="none">
<label for="p">Пароль</label>
<div class="row"><input id="p" name="pass" type="password" autocomplete="off">
<button type="button" onclick="var p=document.getElementById('p');p.type=p.type=='password'?'text':'password';this.textContent=p.type=='password'?'показать':'скрыть'">показать</button></div>
<button class="btn" type="submit">Сохранить и подключить</button>
</form><a class="link" href="/?scan=1">Обновить список сетей</a>
<p class="hint">Контроллер видит только сети 2,4 ГГц. После сохранения он перезагрузится и подключится к выбранной сети, а эта точка доступа исчезнет.</p>
</div>%QR%</div></body></html>)HTML";
static const char PAGE_QR[] PROGMEM = R"HTML(<div class="card" style="margin-top:16px;text-align:center">
<h3 style="margin:0 0 4px;font-size:16px">Привязка к приложению Smart Life</h3>
<p class="hint" style="margin:0 0 12px">Smart Life → «+» → сканировать код. Если устройство уже добавлено, ничего делать не нужно.</p>
%SVG%<p class="hint" style="word-break:break-all;margin-top:10px">%URL%</p></div>)HTML";
static const char PAGE_SAVED[] PROGMEM = R"HTML(<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Сохранено</title>
<style>body{margin:0;background:#eef3f8;font:16px/1.45 -apple-system,Segoe UI,Roboto,sans-serif;color:#1f2329}
.wrap{max-width:420px;margin:0 auto;padding:60px 16px;text-align:center}.card{background:#fff;border-radius:16px;padding:32px 20px;box-shadow:0 4px 16px rgba(20,40,80,.08)}
h2{margin:12px 0 6px}p{color:#8a9099;margin:0}</style></head><body><div class="wrap"><div class="card">
<svg width="56" height="56" viewBox="0 0 48 48"><circle cx="24" cy="24" r="22" fill="#07c160"/><path d="M14 25l7 7 13-14" fill="none" stroke="#fff" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/></svg>
<h2>Сеть сохранена</h2><p>Контроллер перезагружается и подключается к сети <b>%SSID%</b>. Это окно можно закрыть.</p>
</div></div></body></html>)HTML";

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
  uint8_t mac[6];
  WiFi.macAddress(mac);
  snprintf(_apName, sizeof(_apName), "DripIrrigation-%02X%02X", mac[4], mac[5]);
  WiFi.mode(WIFI_STA);
  WiFi.setHostname("DripIrrigation");
  WiFi.setAutoReconnect(false);   // переподключаемся сами, по таймеру
  WiFi.setSleep(false);
  _downSince = millis() ? millis() : 1;
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
    _downSince = up ? 0 : (millis() ? millis() : 1);
  }
  if (!up && hasConfig() && (_triedAt == 0 || millis() - _triedAt > RECONNECT_SEC * 1000)) connect();
  // 🆘 сохранённая сеть не поднимается — поднимаем портал сами (подключение продолжаем пробовать)
  if (!up && !portalActive() && _downSince && millis() - _downSince > PORTAL_AFTER_SEC * 1000) {
    LOG_W("wifi: нет связи %lu с — портал настройки", (unsigned long)PORTAL_AFTER_SEC);
    startPortal();
  }
  if (portalActive()) {
    _dns->processNextRequest();
    _srv->handleClient();
    if (up && !_saved) stopPortal();   // сеть появилась — портал больше не нужен
  }
  return up;
}

// ---------------- портал настройки
String WifiLink::scanOptions() {
  int n = WiFi.scanNetworks();
  String opts;
  for (int pass = 0; pass < n; pass++) {   // сильные первыми, без дублей
    int best = -1;
    for (int i = 0; i < n; i++) {
      if (WiFi.SSID(i).isEmpty()) continue;
      if (opts.indexOf("value=\"" + htmlEsc(WiFi.SSID(i)) + "\"") >= 0) continue;
      if (best < 0 || WiFi.RSSI(i) > WiFi.RSSI(best)) best = i;
    }
    if (best < 0) break;
    String s = htmlEsc(WiFi.SSID(best));
    opts += "<option value=\"" + s + "\"" + (WiFi.SSID(best) == _ssid ? " selected" : "") + ">" + s +
            " (" + String(WiFi.RSSI(best)) + " dBm)</option>";
  }
  WiFi.scanDelete();
  return opts;
}

void WifiLink::sendPage() {
  String html = FPSTR(PAGE_HEAD);
  html += _opts;
  String tail = FPSTR(PAGE_TAIL);
  tail.replace("%CUR%", htmlEsc(_ssid));
  String qr;
  if (_qrUrl.length()) {
    qr = FPSTR(PAGE_QR);
    qr.replace("%SVG%", qrSvg());
    qr.replace("%URL%", htmlEsc(_qrUrl));
  }
  tail.replace("%QR%", qr);
  html += tail;
  _srv->send(200, "text/html; charset=utf-8", html);
}

void WifiLink::startPortal() {
  if (portalActive()) return;
  // 🔍 сканируем до запуска точки доступа: сканирование в режиме AP+STA гасит маяки AP
  _opts = scanOptions();
  WiFi.mode(WIFI_AP_STA);
  delay(100);
  bool apOk = WiFi.softAP(_apName, AP_PASSWORD, 1, 0, 4);
  delay(200);
  IPAddress ip = WiFi.softAPIP();
  LOG_I("wifi: портал %s (без пароля), адрес http://%s (AP %s)", _apName, ip.toString().c_str(),
        apOk ? "поднята" : "НЕ ПОДНЯЛАСЬ");
  _dns = new DNSServer();
  _dns->start(53, "*", ip);
  _srv = new WebServer(80);
  _srv->on("/", HTTP_GET, [this]() {
    LOG_I("wifi: %s ← GET /", _srv->client().remoteIP().toString().c_str());
    if (_srv->hasArg("scan")) { _opts = scanOptions(); WiFi.softAP(_apName, AP_PASSWORD, 1, 0, 4); }
    sendPage();
  });
  _srv->on("/", HTTP_POST, [this]() {
    String chosen = _srv->arg("ssid");
    if (chosen.isEmpty()) chosen = _srv->arg("net");
    LOG_I("wifi: %s ← POST / (%s)", _srv->client().remoteIP().toString().c_str(), chosen.c_str());
    if (chosen.length()) {
      save(chosen, _srv->arg("pass"));
      String html = FPSTR(PAGE_SAVED);
      html.replace("%SSID%", htmlEsc(chosen));
      _srv->send(200, "text/html; charset=utf-8", html);
      _saved = true;
    } else {
      sendPage();
    }
  });
  IPAddress apIp = ip;
  _srv->onNotFound([this, apIp]() {   // пробы captive-portal и всё чужое → на главную
    _srv->sendHeader("Location", "http://" + apIp.toString() + "/", true);
    _srv->send(302, "text/plain", "");
  });
  _srv->begin();
}

void WifiLink::stopPortal() {
  if (!portalActive()) return;
  _srv->stop();
  delete _srv;
  _srv = nullptr;
  _dns->stop();
  delete _dns;
  _dns = nullptr;
  WiFi.softAPdisconnect(true);
  WiFi.mode(WIFI_STA);
  LOG_I("wifi: портал закрыт");
}

// 🔳 QR-код ссылки привязки как inline-SVG (версия 6: до 134 байт, ссылка ~75)
String WifiLink::qrSvg() const {
  QRCode qr;
  uint8_t buf[qrcode_getBufferSize(6)];
  if (qrcode_initText(&qr, buf, 6, ECC_LOW, _qrUrl.c_str()) != 0) return "";
  const int q = 4;   // тихая зона
  String svg;
  svg.reserve(6000);
  svg += "<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 " + String(qr.size + 2 * q) + " " +
         String(qr.size + 2 * q) + "\" width=\"220\" height=\"220\" shape-rendering=\"crispEdges\"><rect width=\"100%\" height=\"100%\" fill=\"#fff\"/><path fill=\"#000\" d=\"";
  for (uint8_t y = 0; y < qr.size; y++) {
    int runStart = -1;
    for (uint8_t x = 0; x <= qr.size; x++) {   // объединяем соседние модули в одну полосу
      bool on = x < qr.size && qrcode_getModule(&qr, x, y);
      if (on && runStart < 0) runStart = x;
      if (!on && runStart >= 0) {
        svg += "M" + String(runStart + q) + " " + String(y + q) + "h" + String(x - runStart) + "v1h-" + String(x - runStart) + "z";
        runStart = -1;
      }
    }
  }
  svg += "\"/></svg>";
  return svg;
}
