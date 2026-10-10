// ota.cpp 🔄 Обновление прошивки через облако Tuya (порт mpy/lib/ota.py) на OTA-разделы ESP32.
//
// Образ качается потоком из HttpResponse.client в Update (Update.h): Update.begin(size),
// Update.setMD5(md5), Update.write() блоками по 4 КБ, Update.end(true) — библиотека сама
// пишет во второй OTA-раздел, сверяет md5 и назначает раздел загрузочным.
// Прогресс — протокол 16 {"progress":"50","firmwareType":N} раз в 10 %.
#include "ota.h"

#include <Update.h>
#include <esp_ota_ops.h>

#include "http.h"
#include "log.h"
#include "storage.h"

namespace {
constexpr const char* OTA_DIR = "/ota";
constexpr const char* APPLY = "/ota/apply.json";
constexpr size_t BLOCK = 4096;                 // блок OTA-раздела
constexpr uint32_t DOWNLOAD_TIMEOUT_MS = 30000;

// статусы tuya.device.upgrade.status.update (tuya_ota.h)
constexpr int ST_UPGRADING = 2, ST_DONE = 3, ST_FAILED = 4;
constexpr int ST_DOWNLOAD_START = 10, ST_DOWNLOAD_DONE = 11, ST_DOWNLOAD_ERROR = 40;

// Облако отдаёт size как число или строку — принимаем оба варианта
long numField(JsonObjectConst o, const char* key) {
  JsonVariantConst v = o[key];
  if (v.is<const char*>()) return atol(v.as<const char*>());
  return v.as<long>();
}
}  // namespace

// Ядро Arduino по умолчанию подтверждает новую прошивку сразу в initArduino(); с этой функцией
// оно оставляет её «на проверке» (ESP_OTA_IMG_PENDING_VERIFY), и откат отменяет только confirm()
// после минуты онлайн — как задумано в ota.h. Любая перезагрузка до confirm() → откат загрузчиком.
extern "C" bool verifyRollbackLater() { return true; }

void Ota::confirm() {
  esp_err_t e = esp_ota_mark_app_valid_cancel_rollback();
  if (e != ESP_OK) LOG_W("ota: confirm: %s", esp_err_to_name(e));   // не «ждёт подтверждения» — норма
}

// ---------------------------------------------------------------- события облака
void Ota::onProtocol(int protocol, JsonObjectConst data) {
  if (protocol != 15) return;   // PRO_UPGD_REQ
  _channel = data["firmwareType"] | 0;
  LOG_I("ota: облако просит обновиться (канал %d)", _channel);
}

// После подключения: доложить версию, завершить прошлое обновление, спросить тихое
void Ota::onConnected() {
  JsonDocument res;
  String err;
  const String applied = readFile(cfgFs(), APPLY);
  if (applied.length()) {
    JsonDocument a;
    if (deserializeJson(a, applied) == DeserializationError::Ok) {
      JsonDocument d;
      d["type"] = a["type"] | 0;
      d["upgradeStatus"] = ST_DONE;
      if (!_tuya.atopDev("tuya.device.upgrade.status.update", "4.1", d.as<JsonObjectConst>(), res, err)) {
        LOG_W("ota: on_connected: %s", err.c_str());
        return;
      }
      LOG_I("ota: обновление до %s завершено", a["version"] | "?");
    }
    cfgFs().remove(APPLY);
  }
  {
    JsonDocument v;
    JsonObject e = v.to<JsonArray>().add<JsonObject>();
    e["otaChannel"] = 0;
    e["protocolVer"] = "2.3";
    e["baselineVer"] = "40.07";
    e["softVer"] = _version;
    String versions;
    serializeJson(v, versions);
    JsonDocument d;
    d["versions"] = versions;   // облако ждёт строку JSON, а не массив
    if (!_tuya.atopDev("tuya.device.versions.update", "4.1", d.as<JsonObjectConst>(), res, err)) {
      LOG_W("ota: on_connected: %s", err.c_str());
      return;
    }
  }
  JsonDocument d;
  d["type"] = 0;
  if (!_tuya.atopDev("tuya.device.upgrade.silent.get", "4.4", d.as<JsonObjectConst>(), res, err)) {
    LOG_W("ota: on_connected: %s", err.c_str());
    return;
  }
  JsonObjectConst info = res.as<JsonObjectConst>();
  if (info["httpsUrl"].is<const char*>()) {
    LOG_I("ota: есть тихое обновление до %s", info["version"] | "?");
    run(info);
  } else {
    LOG_I("ota: версия %s доложена, обновлений нет", _version.c_str());
  }
}

void Ota::tick() {
  if (_channel < 0 || _busy || !_tuya.online()) return;
  const int ch = _channel;
  _channel = -1;
  JsonDocument d, res;
  d["type"] = ch;
  String err;
  if (!_tuya.atopDev("tuya.device.upgrade.get", "4.4", d.as<JsonObjectConst>(), res, err)) {
    LOG_W("ota: upgrade.get: %s", err.c_str());
    return;
  }
  JsonObjectConst info = res.as<JsonObjectConst>();
  if (!info["httpsUrl"].is<const char*>()) {
    LOG_I("ota: обновления нет");
    return;
  }
  run(info);
}

// ---------------------------------------------------------------- само обновление
void Ota::status(int ch, int st) {
  JsonDocument d, res;
  d["type"] = ch;
  d["upgradeStatus"] = st;
  String err;
  if (!_tuya.atopDev("tuya.device.upgrade.status.update", "4.1", d.as<JsonObjectConst>(), res, err)) {
    LOG_W("ota: status %d: %s", st, err.c_str());
  }
}

void Ota::progress(int ch, int pct) {
  JsonDocument d;
  d["progress"] = String(pct);
  d["firmwareType"] = ch;
  _tuya.publish(16, d.as<JsonObjectConst>());
}

void Ota::run(JsonObjectConst info) {
  _busy = true;
  const int ch = (int)numField(info, "type");
  const long size = numField(info, "size");
  const String url = info["httpsUrl"] | "";
  String md5 = info["md5"] | "";
  md5.toLowerCase();
  const String version = info["version"] | "?";
  String err;
  LOG_I("ota: %s → %s, %ld байт", _version.c_str(), version.c_str(), size);
  if (size <= 0 || url.length() == 0) {
    err = "в задании нет size/httpsUrl";
  } else {
    status(ch, ST_UPGRADING);
    status(ch, ST_DOWNLOAD_START);
    download(url, (size_t)size, md5, ch, err);
  }
  if (err.length()) {
    LOG_E("ota: ошибка: %s", err.c_str());
    status(ch, ST_DOWNLOAD_ERROR);
    status(ch, ST_FAILED);
    _busy = false;
    return;
  }
  status(ch, ST_DOWNLOAD_DONE);
  ensureDir(cfgFs(), OTA_DIR);
  JsonDocument a;
  a["version"] = version;
  a["type"] = ch;
  String out;
  serializeJson(a, out);
  if (!writeFile(cfgFs(), APPLY, out)) LOG_W("ota: не удалось записать %s", APPLY);
  progress(ch, 100);
  LOG_I("ota: образ записан, перезагрузка");
  if (onBeforeReboot) onBeforeReboot();
  delay(200);   // дать уйти последним пакетам
  ESP.restart();
  _busy = false;   // недостижимо, для порядка
}

// Скачать образ потоком в Update. false + err при любой ошибке (Update уже отменён).
bool Ota::download(const String& url, size_t size, const String& md5, int ch, String& err) {
  HttpResponse resp;
  if (!httpOpen("GET", url, nullptr, 0, nullptr, resp, DOWNLOAD_TIMEOUT_MS)) {
    err = "нет связи с сервером образа";
    return false;
  }
  if (resp.status != 200) {
    err = "HTTP " + String(resp.status);
    resp.client.stop();
    return false;
  }
  if (resp.length >= 0 && (size_t)resp.length != size) {
    LOG_W("ota: Content-Length %d ≠ size %u из задания", (int)resp.length, (unsigned)size);
  }
  if (!Update.begin(size)) {   // сам проверяет, что образ влезает в свободный OTA-раздел
    err = String("Update.begin: ") + Update.errorString();
    resp.client.stop();
    return false;
  }
  if (md5.length() && !Update.setMD5(md5.c_str())) {
    err = "плохой md5 в задании";
    Update.abort();
    resp.client.stop();
    return false;
  }
  uint8_t* buf = (uint8_t*)malloc(BLOCK);
  if (!buf) {
    err = "нет памяти под буфер";
    Update.abort();
    resp.client.stop();
    return false;
  }
  WiFiClientSecure& c = resp.client;
  size_t got = 0;
  int lastPct = -1;
  bool ok = true;
  while (got < size) {
    size_t want = size - got;
    if (want > BLOCK) want = BLOCK;
    // Набрать блок: read() не блокирует, ждём данных до DOWNLOAD_TIMEOUT_MS
    const uint32_t start = millis();
    int n = 0;
    while (n == 0) {
      if (c.available() > 0) {
        n = c.read(buf, want);
        if (n > 0) break;
        n = 0;
      }
      if (!c.connected()) {
        err = "скачано " + String(got) + " из " + String(size) + " байт";
        ok = false;
        break;
      }
      if (millis() - start >= DOWNLOAD_TIMEOUT_MS) {
        err = "таймаут загрузки на " + String(got) + " байт";
        ok = false;
        break;
      }
      delay(1);
    }
    if (!ok) break;
    if (Update.write(buf, n) != (size_t)n) {
      err = String("Update.write: ") + Update.errorString();
      ok = false;
      break;
    }
    got += n;
    const int pct = (int)((uint64_t)got * 100 / size);
    if (pct - lastPct >= 10) {
      lastPct = pct;
      progress(ch, pct < 99 ? pct : 99);
    }
  }
  free(buf);
  c.stop();
  if (!ok) {
    Update.abort();
    return false;
  }
  if (!Update.end(true)) {   // здесь же сверка md5
    err = String("Update.end: ") + Update.errorString();
    Update.abort();
    return false;
  }
  LOG_I("ota: md5 образа сошёлся, %u байт", (unsigned)got);
  return true;
}
