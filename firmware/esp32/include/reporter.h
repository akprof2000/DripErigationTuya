// reporter.h 🚦 Фильтр отчётов: Tuya советует ≤ 3500 отчётов DP в сутки.
// Порт mpy/lib/reporter.py: «шумные» DP (humidity_N, adc_raw, flow_rate,
// flow_session, filter_baseline) уходят только при заметном изменении
// или не чаще раза в N секунд; остальные — сразу при изменении.
#pragma once
#include <Arduino.h>
#include <ArduinoJson.h>

class Reporter {
 public:
  // packet: {code: value (формат Tuya)}; now — монотонные секунды.
  // full=true — полный снимок (после подключения): проходит всё.
  // Возвращает отфильтрованный пакет в out (может быть пустым).
  void filter(JsonObjectConst packet, uint32_t now, bool full, JsonObject out);

 private:
  struct Last { String code; double value; String text; uint32_t at; bool valid; };  // text — строки/bool
  static constexpr size_t MAX_TRACKED = 64;   // всех DP в таблице 58
  Last _last[MAX_TRACKED];
  Last* find(const char* code, bool create);
};
