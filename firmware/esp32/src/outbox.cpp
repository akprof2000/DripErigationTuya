// outbox.cpp 📬 Очередь отчётов DP на время без связи (порт mpy/lib/outbox.py).
// Файл JSON Lines; читаем построчно — на ESP32 без PSRAM файл в 512 КБ в ОЗУ не влезет.
#include "outbox.h"
#include <ctype.h>
#include "log.h"

namespace {
constexpr size_t TRIM_TO = Outbox::MAX_BYTES / 2;

// Строка из файла без завершающих \r\n; false — конец файла
bool readLine(File& f, String& line) {
  line = "";
  bool any = false;
  while (f.available()) {
    int c = f.read();
    if (c < 0) break;
    any = true;
    if (c == '\n') break;
    line += (char)c;
  }
  while (line.endsWith("\r")) line.remove(line.length() - 1);
  return any;
}

bool blank(const String& s) {
  for (size_t i = 0; i < s.length(); i++)
    if (!isspace((unsigned char)s[i])) return false;
  return true;
}

size_t fileSize(fs::FS& fs, const char* path) {
  File f = fs.open(path, FILE_READ);
  if (!f) return 0;
  size_t n = f.isDirectory() ? 0 : f.size();
  f.close();
  return n;
}

// Заменить файл path содержимым tmp (rename поверх существующего не везде работает)
bool replaceWith(fs::FS& fs, const String& path, const String& tmp) {
  if (fs.exists(path.c_str())) fs.remove(path.c_str());
  if (!fs.rename(tmp.c_str(), path.c_str())) {
    LOG_E("outbox: не переименовать %s", tmp.c_str());
    return false;
  }
  return true;
}
}  // namespace

Outbox::Outbox(fs::FS& fs, const char* path) : _fs(fs), _path(path) {}

void Outbox::begin() {
  _count = 0;
  File f = _fs.open(_path.c_str(), FILE_READ);
  if (!f || f.isDirectory()) return;
  String line;
  while (readLine(f, line))
    if (!blank(line)) _count++;
  f.close();
  if (_count) LOG_I("outbox: %u записей в %s", (unsigned)_count, _path.c_str());
}

bool Outbox::put(JsonObjectConst dpsById, uint32_t unix) {
  if (fileSize(_fs, _path.c_str()) > MAX_BYTES) trimIfNeeded();
  JsonDocument doc;
  doc["dps"].set(dpsById);
  doc["t"] = unix;
  if (doc.overflowed()) {
    LOG_E("outbox: нет памяти под запись");
    return false;
  }
  File f = _fs.open(_path.c_str(), FILE_APPEND);
  if (!f) {
    LOG_E("outbox: не открыть %s", _path.c_str());
    return false;
  }
  size_t n = serializeJson(doc, f);
  n += f.print('\n');
  f.close();
  if (n < 2) {
    LOG_E("outbox: запись в %s не удалась", _path.c_str());
    return false;
  }
  _count++;
  return true;
}

size_t Outbox::flush(std::function<bool(JsonObjectConst dps, uint32_t t)> push, uint32_t now, uint32_t freshSec) {
  File f = _fs.open(_path.c_str(), FILE_READ);
  if (!f || f.isDirectory()) return 0;
  String tmp = _path + ".tmp";
  File rest;                     // открываем только при первом сбое: туда идёт неотправленное
  size_t sent = 0, kept = 0;
  bool failed = false;
  String line;
  while (readLine(f, line)) {
    if (blank(line)) continue;
    if (!failed) {
      bool ok = true;            // битая строка — выбрасываем
      JsonDocument doc;
      if (!deserializeJson(doc, line) && doc["dps"].is<JsonObjectConst>()) {
        uint32_t t = doc["t"].as<uint32_t>();
        if (now && (int64_t)now - (int64_t)t < (int64_t)freshSec) t = 0;   // свежее — без метки времени
        ok = push(doc["dps"].as<JsonObjectConst>(), t);
      }
      if (ok) {
        sent++;
        continue;
      }
      failed = true;
      rest = _fs.open(tmp.c_str(), FILE_WRITE);
      if (!rest) {
        LOG_E("outbox: не открыть %s", tmp.c_str());
        break;
      }
    }
    rest.print(line);
    rest.print('\n');
    kept++;
  }
  f.close();
  if (failed && rest) {
    rest.close();
    if (!replaceWith(_fs, _path, tmp)) kept = _count > sent ? _count - sent : 0;
  } else if (failed) {
    kept = _count > sent ? _count - sent : 0;   // файл не переписан: всё осталось на месте
  } else {
    _fs.remove(_path.c_str());
    kept = 0;
  }
  _count = kept;
  if (sent) LOG_I("outbox: отправлено %u, осталось %u", (unsigned)sent, (unsigned)kept);
  return sent;
}

void Outbox::trimIfNeeded() {
  // Проход 1: суммарная длина непустых строк; проход 2: пропускаем старые, пока не влезем в TRIM_TO
  File f = _fs.open(_path.c_str(), FILE_READ);
  if (!f || f.isDirectory()) return;
  size_t total = 0;
  String line;
  while (readLine(f, line))
    if (!blank(line)) total += line.length() + 1;
  f.close();
  if (total <= TRIM_TO) return;

  String tmp = _path + ".tmp";
  File out = _fs.open(tmp.c_str(), FILE_WRITE);
  f = _fs.open(_path.c_str(), FILE_READ);
  if (!out || !f) {
    LOG_E("outbox: не открыть файлы для обрезки");
    return;
  }
  size_t kept = 0, dropped = 0;
  while (readLine(f, line)) {
    if (blank(line)) continue;
    if (total > TRIM_TO) {
      total -= line.length() + 1;
      dropped++;
      continue;
    }
    out.print(line);
    out.print('\n');
    kept++;
  }
  f.close();
  out.close();
  if (replaceWith(_fs, _path, tmp)) {
    _count = kept;
    LOG_W("outbox: переполнение, выброшено %u старых записей", (unsigned)dropped);
  }
}
