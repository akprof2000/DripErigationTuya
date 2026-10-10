// dp.cpp 📋 Таблица DP и кодирование значений в формат Tuya (порт mpy/lib/spec.py).
// Таблица — include/dptab.h (генерируется tools/gen_dptab.py из spec/dp.json).
#include "dp.h"
#include <math.h>
#include <string.h>
#include <mbedtls/base64.h>
#include <memory>
#include "dptab.h"
#include "log.h"

namespace {

// 10^scale (в dp.json scale не больше 3)
double pow10i(uint8_t scale) {
  double p = 1;
  while (scale--) p *= 10;
  return p;
}

// Поиск строки в массиве (enum range / labels); -1, если нет
int indexOf(const char* const* arr, size_t n, const char* s) {
  if (!arr || !s) return -1;
  for (size_t i = 0; i < n; i++)
    if (strcmp(arr[i], s) == 0) return (int)i;
  return -1;
}

// DP по коду с проверкой типа; nullptr + LOG_W, если не подходит
const DpInfo* need(const char* code, DpType t1, DpType t2, const char* what) {
  const DpInfo* d = dp::byCode(code);
  if (!d) {
    LOG_W("dp: неизвестный код %s", code ? code : "(null)");
    return nullptr;
  }
  if (d->type != t1 && d->type != t2) {
    LOG_W("dp: %s не %s", code, what);
    return nullptr;
  }
  return d;
}

}  // namespace

namespace dp {

const DpInfo* byCode(const char* code) {
  if (!code) return nullptr;
  for (size_t i = 0; i < DP_COUNT; i++)
    if (strcmp(DP_TABLE[i].code, code) == 0) return &DP_TABLE[i];
  return nullptr;
}

const DpInfo* byId(uint16_t id) {
  for (size_t i = 0; i < DP_COUNT; i++)
    if (DP_TABLE[i].id == id) return &DP_TABLE[i];
  return nullptr;
}

size_t count() { return DP_COUNT; }

const DpInfo* at(size_t i) { return i < DP_COUNT ? &DP_TABLE[i] : nullptr; }

// ---------- кодирование «человеческое значение» → формат Tuya ----------

void putNumber(JsonObject out, const char* code, double value) {
  const DpInfo* d = need(code, DpType::Value, DpType::Bitmap, "число");
  if (!d) return;
  if (d->type == DpType::Value) {
    // как lround(): половина — от нуля, затем clamp min..max
    double x = value * pow10i(d->scale);
    if (isnan(x)) x = 0;
    double r = floor(fabs(x) + 0.5);
    if (x < 0) r = -r;
    if (r < d->min) r = d->min;
    if (r > d->max) r = d->max;
    out[d->code] = (int32_t)r;
  } else {
    out[d->code] = (uint32_t)llround(value);   // bitmap: целое как есть
  }
}

void putBool(JsonObject out, const char* code, bool value) {
  const DpInfo* d = need(code, DpType::Bool, DpType::Bool, "bool");
  if (!d) return;
  out[d->code] = value;
}

void putEnum(JsonObject out, const char* code, const char* value) {
  const DpInfo* d = need(code, DpType::Enum, DpType::Enum, "enum");
  if (!d) return;
  int i = indexOf(d->range, d->rangeLen, value);
  if (i < 0) {
    LOG_W("dp: %s: '%s' нет в диапазоне", code, value ? value : "(null)");
    return;
  }
  out[d->code] = d->range[i];   // указатель на литерал из таблицы — без копии
}

void putString(JsonObject out, const char* code, const String& value) {
  const DpInfo* d = need(code, DpType::String, DpType::String, "string");
  if (!d) return;
  out[d->code] = utf8Cut(value, d->maxlen);
}

void putRaw(JsonObject out, const char* code, const uint8_t* data, size_t len) {
  const DpInfo* d = need(code, DpType::Raw, DpType::Raw, "raw");
  if (!d) return;
  size_t cap = ((len + 2) / 3) * 4 + 1;
  std::unique_ptr<unsigned char[]> buf(new (std::nothrow) unsigned char[cap]);
  if (!buf) {
    LOG_E("dp: %s: нет памяти под base64 (%u байт)", code, (unsigned)cap);
    return;
  }
  size_t olen = 0;
  const uint8_t* src = data ? data : (const uint8_t*)"";
  if (mbedtls_base64_encode(buf.get(), cap, &olen, src, data ? len : 0) != 0) {
    LOG_W("dp: %s: ошибка base64", code);
    return;
  }
  buf[olen] = 0;
  out[d->code] = String((const char*)buf.get());   // копия: буфер временный
}

uint32_t bitmapOf(const char* code, const char* const* flags, size_t n) {
  const DpInfo* d = need(code, DpType::Bitmap, DpType::Fault, "bitmap");
  if (!d) return 0;
  uint32_t bits = 0;
  for (size_t i = 0; i < n && flags; i++) {
    int bit = indexOf(d->labels, d->labelsLen, flags[i]);
    if (bit >= 0) bits |= 1u << bit;
    else LOG_W("dp: %s: неизвестный флаг '%s'", code, flags[i] ? flags[i] : "(null)");
  }
  return bits;
}

void putBitmap(JsonObject out, const char* code, const char* const* flags, size_t n) {
  const DpInfo* d = need(code, DpType::Bitmap, DpType::Fault, "bitmap");
  if (!d) return;
  out[d->code] = bitmapOf(code, flags, n);
}

size_t encodeIds(JsonObjectConst in, JsonObject out) {
  size_t n = 0;
  for (JsonPairConst kv : in) {
    const DpInfo* d = byCode(kv.key().c_str());
    if (!d) {
      LOG_W("dp: пропущен неизвестный код %s", kv.key().c_str());
      continue;
    }
    out[String(d->id)].set(kv.value());
    n++;
  }
  return n;
}

// ---------- формат Tuya → «человеческое значение» с проверкой ----------

bool decode(uint16_t id, JsonVariantConst value, Decoded& out, String& err) {
  const DpInfo* d = byId(id);
  if (!d) {
    err = "неизвестный DP " + String(id);
    return false;
  }
  out.info = d;
  if (d->mode == DpMode::RO) {
    err = String("DP ") + d->code + " только для чтения";
    return false;
  }
  switch (d->type) {
    case DpType::Bool:
      if (!value.is<bool>()) {
        err = String(d->code) + ": ожидался bool";
        return false;
      }
      out.flag = value.as<bool>();
      return true;
    case DpType::Value: {
      // is<long long> ложно для bool и дробных — как в spec.py
      if (!value.is<long long>()) {
        err = String(d->code) + ": ожидалось целое " + String(d->min) + ".." + String(d->max);
        return false;
      }
      long long v = value.as<long long>();
      if (v < d->min || v > d->max) {
        err = String(d->code) + ": ожидалось целое " + String(d->min) + ".." + String(d->max);
        return false;
      }
      out.number = d->scale ? (double)v / pow10i(d->scale) : (double)v;
      return true;
    }
    case DpType::Enum: {
      const char* s = value.is<const char*>() ? value.as<const char*>() : nullptr;
      if (indexOf(d->range, d->rangeLen, s) < 0) {
        err = String(d->code) + ": '" + (s ? s : "") + "' нет в диапазоне";
        return false;
      }
      out.text = s;
      return true;
    }
    case DpType::String: {
      const char* s = value.is<const char*>() ? value.as<const char*>() : nullptr;
      if (!s || strlen(s) > d->maxlen) {
        err = String(d->code) + ": строка длиннее " + String(d->maxlen) + " байт";
        return false;
      }
      out.text = s;
      return true;
    }
    default:
      err = String(d->code) + ": запись этого типа не поддерживается";
      return false;
  }
}

String utf8Cut(const String& s, size_t maxlen) {
  if (s.length() <= maxlen) return s;
  size_t n = maxlen;
  const char* b = s.c_str();
  while (n > 0 && ((uint8_t)b[n] & 0xC0) == 0x80) n--;   // байт-продолжение многобайтного символа
  return s.substring(0, n);
}

}  // namespace dp
