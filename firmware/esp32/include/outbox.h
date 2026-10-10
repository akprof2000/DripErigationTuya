// outbox.h 📬 Очередь отчётов на время без связи (порт mpy/lib/outbox.py).
// Файл JSON Lines на dataFs(): каждая строка {"dps":{"101":true,...},"t":1760000000}.
// При подключении flush() отправляет записи по порядку: свежие (моложе freshSec)
// без t, старые — с t, чтобы облако положило их в журнал на исходное время.
// Файл больше MAX_BYTES обрезается с начала (старые записи теряются).
#pragma once
#include <Arduino.h>
#include <ArduinoJson.h>
#include <FS.h>
#include <functional>

class Outbox {
 public:
  static constexpr size_t MAX_BYTES = 512 * 1024;

  Outbox(fs::FS& fs, const char* path);
  void begin();                                   // посчитать записи в файле
  bool put(JsonObjectConst dpsById, uint32_t unix);   // добавить запись (dps с ключами-id)
  size_t count() const { return _count; }

  // Отправить всё. push(dps, t) возвращает false при сбое — тогда flush прерывается,
  // неотправленные записи остаются. now — unix сейчас (0 = время неизвестно: всё без t).
  // Возвращает число отправленных.
  size_t flush(std::function<bool(JsonObjectConst dps, uint32_t t)> push, uint32_t now, uint32_t freshSec = 60);

 private:
  fs::FS& _fs;
  String _path;
  size_t _count = 0;
  void trimIfNeeded();
};
