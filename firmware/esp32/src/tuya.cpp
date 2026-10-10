// tuya.cpp ☁️ Клиент облака Tuya по протоколу TuyaOpen 2.3 (порт mpy/lib/tuya.py).
//
// Лицензии TuyaOpen (UUID + AuthKey) облако принимает только от «OpenSDK»: активация
// thing.device.opensdk.active и протокол 2.3 (AES-128-GCM); со старым потоком (tuya.device.active,
// AES-ECB) приходит ACTIVE_OPEN_SDK_NOT_MATCHED. Форматы — из TuyaOpen:
// src/tuya_cloud_service/cloud/{atop_base,atop_service,mqtt_service}.c и protocol/tuya_protocol.c.
//
// Кадр MQTT 2.3: "2.3" | seq (4, BE) | from=1 (4, BE) | 0x00 | nonce (12) | GCM(JSON) | tag (16);
// AAD — первые 12 байт, ключ — первые 16 байт localKey (онлайн) или AuthKey (привязка).
// ATOP (et=3): подпись md5 по параметрам запроса + ключ, тело data=HEX(nonce|GCM(JSON)|tag),
// ответ — обычно base64(nonce|GCM(JSON)|tag) в поле result.
#include "tuya.h"

#include <time.h>

#include "http.h"
#include "log.h"
#include "storage.h"
#include "tuya_crypto.h"

namespace {
constexpr const char* PV = "2.3";
constexpr const char* BASELINE_VER = "40.07";   // TUYA_BSV
constexpr uint32_t DEV_ATTRIBUTE = 1u << 11;    // ATTRIBUTE_OTA: устройство поддерживает OTA
constexpr int MQ_DPS_PUSH = 4, MQ_DPS_ON = 5, MQ_RESET = 11, MQ_TOKEN = 46;
constexpr const char* IOTDNS = "https://h1.iot-dns.com/v1/url_config";
constexpr uint32_t BACKOFF_MAX = 300;
constexpr size_t FRAME_OVERHEAD = 12 + 12 + 16;   // заголовок + nonce + tag

uint32_t unixTime() { return (uint32_t)time(nullptr); }

uint32_t be32(const uint8_t* p) {
  return ((uint32_t)p[0] << 24) | ((uint32_t)p[1] << 16) | ((uint32_t)p[2] << 8) | p[3];
}

void putBe32(uint8_t* p, uint32_t v) {
  p[0] = (uint8_t)(v >> 24);
  p[1] = (uint8_t)(v >> 16);
  p[2] = (uint8_t)(v >> 8);
  p[3] = (uint8_t)v;
}

// Первые 16 байт строкового ключа (AuthKey 32 символа, secKey/localKey — 16), остаток нулями
void key16(const String& s, uint8_t out[16]) {
  memset(out, 0, 16);
  memcpy(out, s.c_str(), s.length() < 16 ? s.length() : 16);
}

// seq из заголовка кадра любой версии (2.3: смещение 3, 2.2: после crc — 7)
uint32_t frameSeq(const uint8_t* p, size_t n) {
  if (n >= 11 && memcmp(p, "2.2", 3) == 0) return be32(p + 7);
  if (n >= 7) return be32(p + 3);
  return 0;
}

const char* stateName(int s) { return s == 0 ? "wait" : s == 1 ? "bind" : "online"; }
}  // namespace

Tuya::Tuya(const String& pid, const String& uuid, const String& authkey, const String& version,
           const char* statePath)
    : _pid(pid), _uuid(uuid), _authkey(authkey), _version(version), _statePath(statePath) {}

void Tuya::begin() {
  loadState();
  _retryAt = millis();
  _backoff = 5;
  LOG_I("tuya: %s", activated() ? ("устройство активировано, devId " + _st.devId).c_str()
                                : "устройство не привязано, ждём QR");
}

String Tuya::qrUrl() const {
  return "https://smartapp.tuya.com/s/p?p=" + _pid + "&uuid=" + _uuid + "&v=2.0";
}

// ---------------------------------------------------------------- хранилище
void Tuya::loadState() {
  _st = Stored();
  const String data = readFile(cfgFs(), _statePath.c_str());
  if (data.length() == 0) return;
  JsonDocument doc;
  if (deserializeJson(doc, data)) {
    LOG_W("tuya: %s повреждён, считаем устройство непривязанным", _statePath.c_str());
    return;
  }
  _st.region = doc["region"] | "";
  _st.env = doc["env"] | "pro";
  _st.devId = doc["devId"] | "";
  _st.secKey = doc["secKey"] | "";
  _st.localKey = doc["localKey"] | "";
  if (_st.devId.length() && (_st.secKey.length() == 0 || _st.localKey.length() == 0)) {
    LOG_W("tuya: в %s нет ключей устройства, привязка сброшена", _statePath.c_str());
    _st.devId = "";
  }
}

void Tuya::saveState() const {
  JsonDocument doc;
  if (_st.region.length()) {
    doc["region"] = _st.region;
    doc["env"] = _st.env;
  }
  if (_st.devId.length()) {   // ключи — только у активированного устройства (как pop() в tuya.py)
    doc["devId"] = _st.devId;
    doc["secKey"] = _st.secKey;
    doc["localKey"] = _st.localKey;
  }
  String out;
  serializeJson(doc, out);
  if (!writeFile(cfgFs(), _statePath.c_str(), out)) LOG_E("tuya: не удалось записать %s", _statePath.c_str());
}

// ---------------------------------------------------------------- главный шаг
void Tuya::setPaused(bool paused) {
  _paused = paused;
  if (paused) {
    if (_state != State::Wait || _mq.connected()) {
      _mq.close();
      _state = State::Wait;
      LOG_I("tuya: сеть пропала, соединение закрыто");
    }
  } else {
    _retryAt = millis();
    _backoff = 5;
  }
}

void Tuya::loop() {
  if (_paused) return;
  if (_state == State::Wait) {
    if ((int32_t)(millis() - _retryAt) >= 0) start();
    return;
  }
  // Обратные вызовы внутри _mq.loop() могут сами закрыть соединение и перевести автомат в Wait
  // (активация, сброс, fail) — тогда это не ошибка
  if (!_mq.loop() && _state != State::Wait) fail(_mq.lastError());
}

void Tuya::fail(const String& why) {
  LOG_W("tuya: %s: %s → повтор через %u с", stateName((int)_state), why.c_str(), (unsigned)_backoff);
  _mq.close();
  _state = State::Wait;
  _retryAt = millis() + _backoff * 1000;
  _backoff = _backoff * 2 > BACKOFF_MAX ? BACKOFF_MAX : _backoff * 2;
}

// h1.iot-dns.com → адреса брокера и ATOP для региона (без региона — для привязки)
bool Tuya::endpoints() {
  JsonDocument cfg;
  JsonArray arr = cfg["config"].to<JsonArray>();
  JsonObject a = arr.add<JsonObject>();
  a["key"] = "httpsUrl";
  a["need_ca"] = false;
  JsonObject b = arr.add<JsonObject>();
  b["key"] = "mqttsUrl";
  b["need_ca"] = false;
  if (_st.region.length()) {
    cfg["region"] = _st.region;
    cfg["env"] = _st.env;
  }
  String body;
  serializeJson(cfg, body);
  JsonDocument r;
  String err;
  if (!httpPostJson(IOTDNS, body, "application/json", r, err)) {
    LOG_W("tuya: iot-dns: %s", err.c_str());
    return false;
  }
  const char* mq = r["mqttsUrl"]["addr"] | (const char*)nullptr;
  const char* at = r["httpsUrl"]["addr"] | (const char*)nullptr;
  if (!mq || !at) {
    LOG_W("tuya: iot-dns: нет адресов в ответе");
    return false;
  }
  String addr(mq);
  int colon = addr.indexOf(':');
  _mqttHost = colon < 0 ? addr : addr.substring(0, colon);
  _mqttPort = colon < 0 ? 8883 : (uint16_t)addr.substring(colon + 1).toInt();
  _atopUrl = at;
  return _mqttHost.length() > 0 && _atopUrl.length() > 0;
}

void Tuya::start() {
  LOG_I("tuya: подключение к облаку… (свободно %u байт)", (unsigned)ESP.getFreeHeap());
  if (!endpoints()) {
    fail("iot-dns");
    return;
  }
  LOG_I("tuya: брокер %s:%u", _mqttHost.c_str(), _mqttPort);
  if (!activated()) {
    // Привязка: клиент acon_<uuid>, логин с |pv=2.3 (иначе облако шлёт кадры 2.2), пароль из AuthKey
    const String clientId = "acon_" + _uuid;
    _mq.onMessage = [this](const String& t, const uint8_t* p, size_t n) { onBindMessage(t, p, n); };
    if (!_mq.connect(_mqttHost, _mqttPort, clientId, clientId + "|pv=" + PV,
                     tcrypto::md5Hex(_authkey).substring(8, 24))) {
      fail(_mq.lastError());
      return;
    }
    if (!_mq.subscribe("d/ai/" + _uuid)) {
      fail("subscribe");
      return;
    }
    _state = State::Bind;
    LOG_I("tuya: ждём привязку (QR передан в onQrcode)");
    if (onQrcode) onQrcode(qrUrl());
  } else {
    const String& dev = _st.devId;
    _mq.onMessage = [this](const String& t, const uint8_t* p, size_t n) { onDeviceMessage(t, p, n); };
    if (!_mq.connect(_mqttHost, _mqttPort, dev, dev, tcrypto::md5Hex(_st.secKey).substring(8, 24))) {
      fail(_mq.lastError());
      return;
    }
    if (!_mq.subscribe("smart/device/in/" + dev)) {
      fail("subscribe");
      return;
    }
    _state = State::Online;
    _backoff = 5;
    LOG_I("tuya: онлайн, devId %s", dev.c_str());
    if (onConnected) onConnected();
  }
}

// ---------------------------------------------------------------- привязка
void Tuya::onBindMessage(const String& topic, const uint8_t* p, size_t n) {
  (void)topic;
  uint8_t key[16];
  key16(_authkey, key);
  String json;
  if (!unpack(key, p, n, json)) {
    LOG_W("tuya: кадр привязки не расшифрован (%u байт)", (unsigned)n);
    return;
  }
  JsonDocument doc;
  if (deserializeJson(doc, json)) {
    LOG_W("tuya: кадр привязки — не JSON");
    return;
  }
  if ((doc["protocol"] | -1) != MQ_TOKEN) return;
  JsonObjectConst d = doc["data"].as<JsonObjectConst>();
  const String token = d["token"] | "";
  const String region = d["region"] | "";
  const String env = d["regist"] | "pro";
  if (token.length() == 0) {
    LOG_W("tuya: сообщение привязки без токена");
    return;
  }
  LOG_I("tuya: токен получен, регион %s", region.c_str());
  _st.region = region;
  _st.env = env;
  if (!endpoints()) {   // адреса региона устройства
    fail("iot-dns региона");
    return;
  }
  if (!activate(token, region, env)) {
    fail("активация");
    return;
  }
  saveState();
  LOG_I("tuya: активировано, devId %s", _st.devId.c_str());
  _mq.close();
  _state = State::Wait;   // сразу переподключаемся уже как devId
  _retryAt = millis();
  _backoff = 5;
}

bool Tuya::activate(const String& token, const String& region, const String& env) {
  (void)region;
  (void)env;
  JsonDocument d;
  d["token"] = token;
  d["softVer"] = _version;
  d["productKey"] = _pid;
  d["protocolVer"] = PV;
  d["baselineVer"] = BASELINE_VER;
  d["options"] = "{\"otaChannel\":0, \"isFK\":false}";
  d["devAttribute"] = DEV_ATTRIBUTE;
  d["cadVer"] = "1.0.3";
  d["cdVer"] = "1.0.0";
  String body;
  serializeJson(d, body);
  JsonDocument res;
  String err;
  if (!atop("thing.device.opensdk.active", "1.0", body, _uuid, _authkey, res, err)) {
    LOG_E("tuya: %s", err.c_str());
    return false;
  }
  const String devId = res["devId"] | "";
  const String secKey = res["secKey"] | "";
  const String localKey = res["localKey"] | "";
  if (devId.length() == 0 || secKey.length() == 0 || localKey.length() == 0) {
    LOG_E("tuya: в ответе активации нет devId/secKey/localKey");
    return false;
  }
  _st.devId = devId;
  _st.secKey = secKey;
  _st.localKey = localKey;
  return true;
}

// ---------------------------------------------------------------- ATOP
// Запрос к ATOP (et=3): параметры a, [devId], et, t, [uuid], v подписываются md5("k=v||…" + key),
// тело — data=HEX(nonce|GCM(JSON + t)|tag). devIdOrUuid == uuid → параметр uuid (активация),
// иначе devId. result — поле result ответа; false + err, если success=false или сбой сети.
bool Tuya::atop(const String& api, const String& ver, const String& bodyJson, const String& devIdOrUuid,
                const String& key, JsonDocument& result, String& err) {
  if (_atopUrl.length() == 0) {
    err = "ATOP: адрес неизвестен";
    return false;
  }
  const uint32_t t = unixTime();
  const bool byUuid = devIdOrUuid == _uuid;
  String signed_, query;
  auto param = [&](const char* k, const String& v) {
    signed_ += k;
    signed_ += '=';
    signed_ += v;
    signed_ += "||";
    query += k;
    query += '=';
    query += v;
    query += '&';
  };
  param("a", api);
  if (!byUuid) param("devId", devIdOrUuid);
  param("et", "3");
  param("t", String(t));
  if (byUuid) param("uuid", devIdOrUuid);
  param("v", ver);
  signed_ += key;
  query += "sign=" + tcrypto::md5Hex(signed_);

  // data["t"] = t — вставляем в сериализованный объект перед закрывающей скобкой
  String data = bodyJson;
  data.trim();
  if (data.length() < 2 || data[0] != '{' || data[data.length() - 1] != '}') {
    err = "ATOP: тело не объект JSON";
    return false;
  }
  data.remove(data.length() - 1);
  data.trim();
  data += data.length() > 1 ? ",\"t\":" : "\"t\":";
  data += t;
  data += '}';

  uint8_t k16[16];
  key16(key, k16);
  const size_t n = data.length();
  uint8_t* raw = (uint8_t*)malloc(12 + n + 16);
  if (!raw) {
    err = "ATOP: нет памяти";
    return false;
  }
  tcrypto::randomBytes(raw, 12);
  if (!tcrypto::gcmEncrypt(k16, raw, nullptr, 0, (const uint8_t*)data.c_str(), n, raw + 12, raw + 12 + n)) {
    free(raw);
    err = "ATOP: GCM";
    return false;
  }
  String body = tcrypto::hexEncode(raw, 12 + n + 16);
  free(raw);
  body.toUpperCase();   // hex в верхнем регистре, как у TuyaOpen
  body = "data=" + body;

  JsonDocument r;
  if (!httpPostJson(_atopUrl + "?" + query, body, "application/x-www-form-urlencoded;charset=UTF-8", r, err)) {
    err = "ATOP " + api + ": " + err;
    return false;
  }
  if (r["result"].is<const char*>()) {   // обычно весь ответ зашифрован в result (base64)
    const String enc = r["result"].as<String>();
    const size_t max = enc.length() * 3 / 4 + 4;
    uint8_t* buf = (uint8_t*)malloc(max);
    if (!buf) {
      err = "ATOP: нет памяти";
      return false;
    }
    const size_t len = tcrypto::base64Decode(enc, buf, max);
    if (len < 28) {
      free(buf);
      err = "ATOP " + api + ": повреждённый result";
      return false;
    }
    const size_t ptLen = len - 28;
    uint8_t* pt = (uint8_t*)malloc(ptLen + 1);
    if (!pt) {
      free(buf);
      err = "ATOP: нет памяти";
      return false;
    }
    const bool ok = tcrypto::gcmDecrypt(k16, buf, nullptr, 0, buf + 12, ptLen, buf + len - 16, pt);
    free(buf);
    if (!ok) {
      free(pt);
      err = "ATOP " + api + ": тег GCM не сошёлся (чужой ключ?)";
      return false;
    }
    pt[ptLen] = 0;
    r.clear();
    DeserializationError e = deserializeJson(r, (const char*)pt);
    free(pt);
    if (e) {
      err = "ATOP " + api + ": ответ не JSON";
      return false;
    }
  }
  if (!(r["success"] | false)) {
    String code = r["errorCode"] | "";
    if (code.length() == 0) serializeJson(r, code);
    err = "ATOP " + api + ": " + code;
    return false;
  }
  result.clear();
  result.set(r["result"]);
  return true;
}

bool Tuya::atopDev(const char* api, const char* ver, JsonObjectConst data, JsonDocument& result, String& err) {
  if (!activated()) {
    err = "ATOP: устройство не активировано";
    return false;
  }
  String body;
  serializeJson(data, body);
  if (body.length() == 0 || body == "null") body = "{}";
  return atop(api, ver, body, _st.devId, _st.secKey, result, err);
}

// ---------------------------------------------------------------- кадры MQTT
void Tuya::deviceKey(uint8_t out[16]) const { key16(_st.localKey, out); }

bool Tuya::packSend(const String& topic, const uint8_t key[16], const String& json) {
  const size_t n = json.length();
  uint8_t* f = (uint8_t*)malloc(FRAME_OVERHEAD + n);
  if (!f) {
    LOG_E("tuya: нет памяти под кадр (%u байт)", (unsigned)n);
    return false;
  }
  memcpy(f, PV, 3);
  putBe32(f + 3, _seq);
  putBe32(f + 7, 1);   // from = 1 (устройство)
  f[11] = 0;           // резерв
  tcrypto::randomBytes(f + 12, 12);
  bool ok = tcrypto::gcmEncrypt(key, f + 12, f, 12, (const uint8_t*)json.c_str(), n, f + 24, f + 24 + n);
  if (ok) ok = _mq.publish(topic, f, FRAME_OVERHEAD + n, 1);
  free(f);
  return ok;
}

bool Tuya::unpack(const uint8_t key[16], const uint8_t* p, size_t n, String& json) {
  if (n >= 3 && memcmp(p, "2.3", 3) == 0) {
    if (n < FRAME_OVERHEAD || p[11] != 0) {
      LOG_W("tuya: кадр 2.3 повреждён");
      return false;
    }
    const size_t len = n - FRAME_OVERHEAD;
    uint8_t* pt = (uint8_t*)malloc(len + 1);
    if (!pt) return false;
    const bool ok = tcrypto::gcmDecrypt(key, p + 12, p, 12, p + 24, len, p + n - 16, pt);
    if (ok) {
      pt[len] = 0;
      json = (const char*)pt;
    } else {
      LOG_W("tuya: тег кадра 2.3 не сошёлся (чужой ключ или битые данные)");
    }
    free(pt);
    return ok;
  }
  if (n >= 3 && memcmp(p, "2.2", 3) == 0) {   // так облако отвечает клиенту, назвавшемуся без |pv=2.3
    if (n < 16 || (n - 15) % 16 != 0) {
      LOG_W("tuya: кадр 2.2 повреждён");
      return false;
    }
    if (tcrypto::crc32(p + 7, n - 7) != be32(p + 3)) {
      LOG_W("tuya: кадр 2.2: CRC");
      return false;
    }
    uint8_t* pt = (uint8_t*)malloc(n - 15 + 1);
    if (!pt) return false;
    const size_t len = tcrypto::aesEcbDecrypt(key, p + 15, n - 15, pt);
    if (len) {
      pt[len] = 0;
      json = (const char*)pt;
    } else {
      LOG_W("tuya: кадр 2.2: набивка (чужой ключ?)");
    }
    free(pt);
    return len > 0;
  }
  LOG_W("tuya: неизвестная версия кадра (%u байт)", (unsigned)n);
  return false;
}

// ---------------------------------------------------------------- работа
void Tuya::onDeviceMessage(const String& topic, const uint8_t* p, size_t n) {
  (void)topic;
  uint8_t key[16];
  deviceKey(key);
  String json;
  if (!unpack(key, p, n, json)) return;
  const uint32_t seq = frameSeq(p, n);
  if (seq > _seq) _seq = seq;
  JsonDocument doc;
  if (deserializeJson(doc, json)) {
    LOG_W("tuya: сообщение облака — не JSON");
    return;
  }
  const int proto = doc["protocol"] | -1;
  LOG_D("tuya: протокол %d, seq %u", proto, (unsigned)seq);
  if (proto == MQ_DPS_ON) {
    if (onDps) onDps(doc["data"]["dps"].as<JsonObjectConst>());
  } else if (proto == MQ_RESET) {
    LOG_I("tuya: устройство удалено из приложения");
    _st.devId = "";
    _st.secKey = "";
    _st.localKey = "";
    saveState();
    _mq.close();
    _state = State::Wait;
    _retryAt = millis();
    if (onReset) onReset();
  } else if (onProtocol) {
    onProtocol(proto, doc["data"].as<JsonObjectConst>());
  }
}

bool Tuya::publish(int protocol, JsonObjectConst data) {
  if (!online()) return false;
  JsonDocument doc;
  doc["protocol"] = protocol;
  doc["t"] = unixTime();
  doc["data"] = data;
  String json;
  serializeJson(doc, json);
  _seq++;
  uint8_t key[16];
  deviceKey(key);
  if (!packSend("smart/device/out/" + _st.devId, key, json)) {
    fail(_mq.connected() ? String("publish") : _mq.lastError());
    return false;
  }
  return true;
}

bool Tuya::push(JsonObjectConst dps, uint32_t t) {
  if (!online()) return false;
  JsonDocument doc;
  doc["protocol"] = MQ_DPS_PUSH;
  doc["t"] = unixTime();
  JsonObject d = doc["data"].to<JsonObject>();
  d["devId"] = _st.devId;
  d["dps"] = dps;
  if (t) d["t"] = t;   // отчёт задним числом (как tuya_iot_dp_report_json_with_time в TuyaOpen)
  String json;
  serializeJson(doc, json);
  _seq++;
  uint8_t key[16];
  deviceKey(key);
  if (!packSend("smart/device/out/" + _st.devId, key, json)) {
    fail(_mq.connected() ? String("push") : _mq.lastError());
    return false;
  }
  return true;
}
