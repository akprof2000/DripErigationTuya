// app.cpp 🔁 Главный цикл контроллера — перенос mpy/lib/app.py
#include "app.h"
#include <esp_task_wdt.h>
#include "dp.h"
#include "log.h"
#include "storage.h"

static const char* CREDS = "/tuya.json";
static const char* TUYA_STATE = "/tuya_state.json";
static const char* STATE = "/state.json";
static const char* PENDING_PATH = "/pending.jsonl";

static App* s_app = nullptr;

bool App::loadCreds(String& pid, String& uuid, String& authkey) {
  JsonDocument doc;
  String raw = readFile(cfgFs(), CREDS);
  if (raw.isEmpty() || deserializeJson(doc, raw)) return false;
  pid = doc["pid"] | "";
  uuid = doc["uuid"] | "";
  authkey = doc["authkey"] | "";
  return uuid.length() && authkey.length();
}

void App::setup() {
  s_app = this;
  Serial.begin(115200);
  delay(300);
  _hw.begin();                                   // первым делом реле в «выключено»
  storageBegin();
  LOG_I("Drip Irrigation %s запущен, SD: %s", FW_VERSION, sdPresent() ? "есть" : "нет");
  _clock.begin();
  _wifi.begin();

  // 📡 без сохранённой сети или с зажатой кнопкой — портал настройки (полив при этом работает)
  if (!_wifi.hasConfig() || _hw.buttonPressed()) _wifi.startPortal();
  _wifi.connect();

  _cfg.load(dataFs(), STATE);
  _dev = new Device(_hw, _cfg, dataFs(), STATE);
  _dev->begin();
  _outbox = new Outbox(dataFs(), PENDING_PATH);
  _outbox->begin();

  String pid, uuid, authkey;
  if (loadCreds(pid, uuid, authkey)) {
    _tuya = new Tuya(pid, uuid, authkey, FW_VERSION, TUYA_STATE);
    _tuya->begin();
    _tuya->onConnected = [this]() { onConnected(); };
    _tuya->onDps = [this](JsonObjectConst dps) { onDps(dps); };
    _tuya->onReset = []() { LOG_W("tuya: устройство удалено из приложения, ждём новую привязку"); };
    _tuya->onQrcode = [](const String& url) { LOG_I("tuya: привязка — QR %s", url.c_str()); };
    _wifi.setQrUrl(_tuya->qrUrl());   // QR привязки — на странице портала
    _ota = new Ota(*_tuya, FW_VERSION);
    _ota->onBeforeReboot = [this]() { shutdown(); };
    _tuya->onProtocol = [this](int p, JsonObjectConst d) { _ota->onProtocol(p, d); };
  } else {
    LOG_W("tuya: нет /tuya.json (pid, uuid, authkey) — работаем без облака");
  }

  esp_task_wdt_init(WDT_TIMEOUT_S, true);
  esp_task_wdt_add(nullptr);
  _lastTick = millis();
}

void App::loop() {
  esp_task_wdt_reset();
  uint32_t ms = millis();
  if (ms - _lastTick < TICK_MS) { delay(5); return; }
  _lastTick += TICK_MS;
  if (ms - _lastTick > 5 * TICK_MS) _lastTick = ms;   // долгий сетевой вызов — не догоняем тики
  _upSec++;

  bool up = _wifi.tick();
  if (_wifi.portalSaved()) {   // в портале сохранили сеть — перезагружаемся на неё
    LOG_I("wifi: сеть сохранена, перезагрузка");
    delay(500);
    shutdown();
    ESP.restart();
  }
  if (up) {
    if (!_ntpStarted) { _ntpStarted = true; _clock.startNtp(); }
    _clock.tick();
    if (_tuya) {
      _tuya->loop();
      if (_tuya->online() && _outbox->count())
        _outbox->flush([this](JsonObjectConst d, uint32_t t) { return _tuya->push(d, t); }, _clock.unix());
      if (_ota) _ota->tick();
    }
  } else if (_tuya && _tuya->online()) {
    _tuya->setPaused(true);    // Wi-Fi пропал — не ждём таймаута MQTT
    _tuya->setPaused(false);
  }
  bool online = _tuya && _tuya->online();
  if (online != _wasOnline) {
    _wasOnline = online;
    _onlineSince = online ? _upSec : 0;
  }

  // 🩺 блокирующие аварии: клапаны (PCF8574) и время (ни DS3231, ни NTP)
  uint8_t faults = (_hw.faultValves() ? FAULT_VALVES : 0) | (_clock.faultRtc() ? FAULT_RTC : 0);
  if (faults != _dev->faults()) {
    _dev->setFaults(faults);
    LOG_W("Аварии: %s%s", (faults & FAULT_VALVES) ? "клапаны " : "", (faults & FAULT_RTC) ? "время " : "");
  }
  _dev->tick(ms, _clock.unix());

  JsonDocument changed;
  JsonObject ch = changed.to<JsonObject>();
  if (_dev->report(ch, false)) queue(ch, false);
  sendEvents();
  if (_upSec - _sysAt >= SYS_INFO_EVERY_S || _sysAt == 0) sysInfo();

  tickButton();
  tickLed(up);

  if (_dev->restartRequested() && _restartAt == 0) {
    _restartAt = _upSec + 3;   // дать облаку получить ответ
    LOG_I("перезагрузка по команде из приложения");
  }
  if (_restartAt && _upSec >= _restartAt) { shutdown(); ESP.restart(); }

  // 🔁 новая прошивка после OTA считается удачной, если побыла онлайн минуту
  if (!_bootConfirmed && _onlineSince && _upSec - _onlineSince > STATE_OK_AFTER_S) {
    _bootConfirmed = true;
    Ota::confirm();
  }
}

// ---------------------------------------------------------------- облако
void App::onConnected() {
  size_t pending = _outbox->count();
  _outbox->flush([this](JsonObjectConst d, uint32_t t) { return _tuya->push(d, t); }, _clock.unix());
  JsonDocument full;
  JsonObject o = full.to<JsonObject>();
  _dev->report(o, true);
  queue(o, true);
  sysInfo();
  LOG_I("облако: подключено, из очереди отправлено %u, свободно %u байт", (unsigned)pending,
        (unsigned)ESP.getFreeHeap());
  if (_ota) _ota->onConnected();
}

void App::onDps(JsonObjectConst dps) {
  bool applied = false;
  for (JsonPairConst kv : dps) {
    uint16_t id = atoi(kv.key().c_str());
    dp::Decoded d;
    String err;
    if (!dp::decode(id, kv.value(), d, err)) { LOG_W("dp %u: %s", id, err.c_str()); continue; }
    if (_dev->applyDp(d.info->code, d.number, d.flag, d.text, millis(), _clock.unix(), err)) {
      LOG_I("dp %s ← %s", d.info->code, kv.value().as<String>().c_str());
      applied = true;
    } else {
      LOG_W("dp %s: %s", d.info->code, err.c_str());
    }
  }
  if (applied) {   // сразу отчитаться, чтобы панель увидела новое состояние
    JsonDocument changed;
    JsonObject ch = changed.to<JsonObject>();
    if (_dev->report(ch, false)) queue(ch, false);
    sendEvents();
  }
}

void App::queue(JsonObjectConst packet, bool full) {
  JsonDocument filtered;
  JsonObject f = filtered.to<JsonObject>();
  _reporter.filter(packet, _upSec, full, f);
  if (f.size() == 0) return;
  JsonDocument byId;
  JsonObject ids = byId.to<JsonObject>();
  if (dp::encodeIds(f, ids) == 0) return;
  uint32_t unix = _clock.unix();
  if (_tuya && _tuya->online() && _outbox->count() == 0) {
    if (_tuya->push(ids, 0)) return;
  }
  _outbox->put(ids, unix);   // нет связи (или очередь не пуста — порядок важен)
}

void App::sendEvents() {
  String ev;
  while (_dev->popEvent(ev)) {
    JsonDocument p;
    JsonObject o = p.to<JsonObject>();
    dp::putString(o, "event", ev);
    queue(o, true);
  }
}

void App::sysInfo() {
  _sysAt = _upSec ? _upSec : 1;
  JsonDocument extra;
  extra["heap"] = ESP.getFreeHeap();
  extra["rssi"] = _wifi.rssi();
  extra["sd"] = sdPresent() ? 1 : 0;
  extra["pending"] = _outbox->count();
  extra["rtc"] = _clock.rtcPresent() ? 1 : 0;
  extra["valves"] = _hw.pcfOk() ? 1 : 0;
  extra["sensors"] = _hw.sensorsOk() ? 1 : 0;
  JsonDocument p;
  JsonObject o = p.to<JsonObject>();
  dp::putString(o, "sys_info", _dev->sysInfo(_clock.unix(), extra.as<JsonObjectConst>()));
  queue(o, true);
  LOG_I("sys_info: свободно %u байт, rssi %d, очередь %u", (unsigned)ESP.getFreeHeap(), _wifi.rssi(),
        (unsigned)_outbox->count());
}

void App::shutdown() {
  _dev->loadsOff();
  _dev->save();
}

void App::tickButton() {
  if (_hw.buttonPressed()) {
    if (_buttonSince == 0) _buttonSince = millis();
    else if (millis() - _buttonSince > BUTTON_PORTAL_MS && !_wifi.portalActive()) {
      LOG_I("кнопка: портал настройки Wi-Fi");
      _wifi.startPortal();
    }
  } else {
    _buttonSince = 0;
  }
}

// 💡 горит — на связи с облаком; мигает раз в секунду — Wi-Fi есть, облака нет; частое — нет Wi-Fi
void App::tickLed(bool wifiUp) {
  bool online = _tuya && _tuya->online();
  if (_wifi.portalActive()) _ledOn = (_upSec % 4) < 2;   // портал: длинные вспышки
  else if (online) _ledOn = true;
  else if (wifiUp) _ledOn = !_ledOn;
  else _ledOn = (_upSec % 2) == 0;
  _hw.led(_ledOn);
}
