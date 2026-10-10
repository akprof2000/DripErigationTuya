// log.cpp 📝 Печать строки лога: чч:мм:сс <уровень> сообщение (до синхронизации времени — аптайм)
#include "log.h"
#include <stdarg.h>
#include <time.h>

void logPrintf(char level, const char* fmt, ...) {
  char buf[256];
  va_list ap;
  va_start(ap, fmt);
  vsnprintf(buf, sizeof(buf), fmt, ap);
  va_end(ap);
  time_t t = time(nullptr);
  if (t > 1700000000) {
    struct tm tm;
    localtime_r(&t, &tm);
    Serial.printf("%02d:%02d:%02d %c %s\n", tm.tm_hour, tm.tm_min, tm.tm_sec, level, buf);
  } else {
    uint32_t s = millis() / 1000;
    Serial.printf("%02lu:%02lu:%02lu %c %s\n", (unsigned long)(s / 3600), (unsigned long)(s / 60 % 60),
                  (unsigned long)(s % 60), level, buf);
  }
}
