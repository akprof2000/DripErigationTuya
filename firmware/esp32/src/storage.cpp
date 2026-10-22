// storage.cpp 💾 LittleFS во флеше (настройки, лицензия) и SD-карта (данные), если вставлена.
#include "storage.h"
#include <LittleFS.h>
#include <SD.h>
#include <SPI.h>
#include "log.h"

namespace {
#ifndef SD_FORMAT_IF_EMPTY
#define SD_FORMAT_IF_EMPTY false     // разовая сборка с -DSD_FORMAT_IF_EMPTY=true форматирует карту без FAT
#endif
constexpr int SD_CS = 5;            // VSPI: SCK 18, MISO 19, MOSI 23, CS 5
constexpr int SD_TRIES = 3;
constexpr uint32_t SD_PAUSE_MS = 300;
bool s_sd = false;
}  // namespace

bool storageBegin() {
  if (!LittleFS.begin(true)) {      // true — форматировать при первом запуске
    LOG_E("storage: LittleFS не смонтирован");
    return false;
  }
  LOG_I("storage: LittleFS %u/%u КБ", (unsigned)(LittleFS.usedBytes() / 1024),
        (unsigned)(LittleFS.totalBytes() / 1024));
  s_sd = false;
  for (int i = 1; i <= SD_TRIES && !s_sd; i++) {
    if (SD.begin(SD_CS, SPI, 4000000, "/sd", 5, SD_FORMAT_IF_EMPTY) && SD.cardType() != CARD_NONE) {
      s_sd = true;
      LOG_I("storage: SD %u МБ", (unsigned)(SD.cardSize() / (1024 * 1024)));
    } else {
      SD.end();
      if (i < SD_TRIES) delay(SD_PAUSE_MS);
    }
  }
  if (!s_sd) LOG_W("storage: SD-карты нет, данные во флеше");
  return true;
}

fs::FS& cfgFs() { return LittleFS; }

fs::FS& dataFs() {
  if (s_sd) return SD;
  return LittleFS;
}

bool sdPresent() { return s_sd; }

String readFile(fs::FS& fs, const char* path) {
  String out;
  File f = fs.open(path, FILE_READ);
  if (!f || f.isDirectory()) return out;
  size_t size = f.size();
  if (size && !out.reserve(size)) {
    LOG_E("storage: нет памяти под %s (%u байт)", path, (unsigned)size);
    f.close();
    return out;
  }
  uint8_t buf[128];
  while (true) {
    int n = f.read(buf, sizeof(buf));
    if (n <= 0) break;
    out.concat((const char*)buf, n);
  }
  f.close();
  return out;
}

bool writeFile(fs::FS& fs, const char* path, const String& data) {
  String tmp = String(path) + ".tmp";
  File f = fs.open(tmp.c_str(), FILE_WRITE);
  if (!f) {
    LOG_E("storage: не открыть %s", tmp.c_str());
    return false;
  }
  size_t n = f.write((const uint8_t*)data.c_str(), data.length());
  f.close();
  if (n != data.length()) {
    LOG_E("storage: записано %u из %u в %s", (unsigned)n, (unsigned)data.length(), tmp.c_str());
    fs.remove(tmp.c_str());
    return false;
  }
  // rename поверх существующего файла не везде работает (LittleFS/FAT) — сначала удаляем
  if (fs.exists(path)) fs.remove(path);
  if (!fs.rename(tmp.c_str(), path)) {
    LOG_E("storage: не переименовать %s -> %s", tmp.c_str(), path);
    return false;
  }
  return true;
}

bool ensureDir(fs::FS& fs, const char* path) {
  File d = fs.open(path);
  if (d) {
    bool isDir = d.isDirectory();
    d.close();
    if (isDir) return true;
    LOG_E("storage: %s — файл, а не каталог", path);
    return false;
  }
  if (!fs.mkdir(path)) {
    LOG_E("storage: не создать каталог %s", path);
    return false;
  }
  return true;
}
