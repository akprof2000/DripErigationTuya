// storage.h 💾 Файловые системы контроллера.
//
// cfgFs()  — LittleFS во флеше ESP32: всегда есть. Здесь /tuya.json (лицензия),
//            /wifi.json, /tuya_state.json (привязка), /ota/apply.json.
// dataFs() — SD-карта (VSPI, CS 5), если вставлена, иначе та же LittleFS.
//            Здесь /state.json (настройки полива) и /pending.jsonl (очередь отчётов).
#pragma once
#include <Arduino.h>
#include <FS.h>

bool storageBegin();          // смонтировать LittleFS (форматируя при первом запуске) и попробовать SD
fs::FS& cfgFs();
fs::FS& dataFs();
bool sdPresent();             // карта смонтирована

// 📄 Прочитать файл целиком (пусто, если нет) / записать атомарно (через .tmp + rename)
String readFile(fs::FS& fs, const char* path);
bool writeFile(fs::FS& fs, const char* path, const String& data);
bool ensureDir(fs::FS& fs, const char* path);   // создать каталог, если нет
