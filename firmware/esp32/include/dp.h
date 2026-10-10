// dp.h 📋 Таблица DP (из spec/dp.json, генерируется tools/gen_dptab.py → include/dptab.h)
// и кодирование значений в формат Tuya.
//
// Формат значений в JSON-пакетах (как в spec.py / Tuya):
//   bool → true/false; value → целое со сдвигом scale (1.23 л/мин при scale 2 → 123);
//   enum → строка; string → строка (обрезка до maxlen байт UTF-8, не рвём символ);
//   bitmap/fault → целое; raw → строка base64.
// Пакет DP — JsonObject, ключи: коды ("humidity_3") до encodeIds(), id ("133") после.
#pragma once
#include <Arduino.h>
#include <ArduinoJson.h>

enum class DpType : uint8_t { Bool, Value, Enum, String, Raw, Bitmap, Fault };
enum class DpMode : uint8_t { RO, RW, WR };

struct DpInfo {
  uint16_t id;
  const char* code;
  DpType type;
  DpMode mode;
  int32_t min;
  int32_t max;
  uint8_t scale;
  const char* const* range;   // enum: допустимые значения (nullptr, если не enum)
  uint8_t rangeLen;
  const char* const* labels;  // bitmap/fault: имена битов
  uint8_t labelsLen;
  uint16_t maxlen;            // string: байт UTF-8
  uint8_t channel;            // 1..8 для канальных DP, 0 — глобальный
};

namespace dp {
constexpr uint8_t CHANNELS = 8;

const DpInfo* byCode(const char* code);
const DpInfo* byId(uint16_t id);
size_t count();
const DpInfo* at(size_t i);

// Кодирование «человеческого» значения в формат Tuya (в out[code]).
// value: double для value (lround с округлением половины от нуля, clamp min..max), bool, строки.
void putNumber(JsonObject out, const char* code, double value);
void putBool(JsonObject out, const char* code, bool value);
void putEnum(JsonObject out, const char* code, const char* value);     // не из range → не пишется, LOG_W
void putString(JsonObject out, const char* code, const String& value);  // с обрезкой до maxlen
void putRaw(JsonObject out, const char* code, const uint8_t* data, size_t len);  // base64
void putBitmap(JsonObject out, const char* code, const char* const* flags, size_t n);  // имена → биты
uint32_t bitmapOf(const char* code, const char* const* flags, size_t n);

// Ключи code → id (строкой). Возвращает число перекодированных; неизвестные коды пропускает.
size_t encodeIds(JsonObjectConst in, JsonObject out);

// Декодирование из облака: id + значение → код и нормализованное значение (value / 10^scale).
// false + err, если DP неизвестен, только для чтения или значение вне диапазона/типа.
struct Decoded {
  const DpInfo* info = nullptr;
  double number = 0;      // value (уже со сдвигом scale)
  bool flag = false;      // bool
  String text;            // enum / string
};
bool decode(uint16_t id, JsonVariantConst value, Decoded& out, String& err);

// Обрезка строки до maxlen байт UTF-8, не разрывая символ
String utf8Cut(const String& s, size_t maxlen);
}  // namespace dp
