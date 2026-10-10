// reporter.cpp 🚦 Фильтр отчётов DP (порт mpy/lib/reporter.py).
// «Шумные» DP уходят при изменении на delta единиц Tuya либо раз в maxAge секунд;
// остальные — когда значение отличается от последнего отправленного; event — всегда.
#include "reporter.h"
#include <ctype.h>
#include <math.h>
#include <string.h>
#include "log.h"

namespace {

struct Rule {
  const char* base;    // код без суффикса _N
  int delta;           // минимальное изменение в единицах DP; 0 — только по времени
  uint32_t maxAge;     // максимум секунд между отчётами
};

// Значения — уже в формате Tuya (целые со scale), числа как в reporter.py NOISY
const Rule NOISY[] = {
    {"humidity", 2, 600},          // 2 % или раз в 10 мин
    {"adc_raw", 0, 600},           // только раз в 10 мин (меняется каждую минуту)
    {"flow_rate", 20, 300},        // 0.02 л/мин (scale 3) или раз в 5 мин
    {"flow_session", 10, 300},     // 0.1 л (scale 2) или раз в 5 мин
    {"filter_baseline", 5, 600},
};

// Правило по коду: канальный суффикс _N отбрасывается
const Rule* ruleOf(const char* code) {
  size_t len = strlen(code);
  size_t base = len;
  if (len && isdigit((unsigned char)code[len - 1])) {
    const char* us = strrchr(code, '_');
    if (us) base = us - code;
  }
  for (const Rule& r : NOISY)
    if (strlen(r.base) == base && strncmp(r.base, code, base) == 0) return &r;
  return nullptr;
}

// Строковое представление не-числа (строка, bool, null) для сравнения «изменилось ли»
String textOf(JsonVariantConst v) {
  if (v.is<bool>()) return v.as<bool>() ? "true" : "false";
  if (v.is<const char*>()) return v.as<const char*>();
  if (v.isNull()) return "";
  String s;
  serializeJson(v, s);   // объекты/массивы — редкость, сравним сериализацию
  return s;
}

}  // namespace

Reporter::Last* Reporter::find(const char* code, bool create) {
  Last* free = nullptr;
  for (Last& l : _last) {
    if (l.valid) {
      if (l.code == code) return &l;
    } else if (!free) {
      free = &l;
    }
  }
  if (!create) return nullptr;
  if (!free) {
    LOG_W("reporter: таблица переполнена (%u), %s без фильтра", (unsigned)MAX_TRACKED, code);
    return nullptr;
  }
  free->code = code;
  free->valid = true;
  free->value = 0;
  free->text = "";
  free->at = 0;
  return free;
}

void Reporter::filter(JsonObjectConst packet, uint32_t now, bool full, JsonObject out) {
  for (JsonPairConst kv : packet) {
    const char* code = kv.key().c_str();
    JsonVariantConst v = kv.value();
    bool numeric = v.is<double>();        // целые и дробные; bool — нет
    double num = numeric ? v.as<double>() : 0;
    String text = numeric ? String() : textOf(v);

    const Rule* rule = ruleOf(code);
    Last* prev = find(code, false);
    bool send = full || !prev || strcmp(code, "event") == 0;
    if (!send) {
      if (rule) {
        if (now - prev->at >= rule->maxAge) send = true;
        else if (rule->delta && numeric && fabs(num - prev->value) >= rule->delta) send = true;
      } else {
        // остальные DP — при любом отличии от последнего отправленного
        send = numeric ? (num != prev->value) : (text != prev->text);
      }
    }
    if (!send) continue;
    out[kv.key()].set(v);
    Last* l = prev ? prev : find(code, true);
    if (l) {
      l->value = num;
      l->text = text;
      l->at = now;
    }
  }
}
