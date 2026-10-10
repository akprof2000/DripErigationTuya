// clock.cpp 🕐 DS3231 (регистры 0x00..0x06, BCD) + SNTP ядра ESP32
#include "clock.h"
#include <Wire.h>
#include <sys/time.h>
#include <time.h>
#include <esp_sntp.h>
#include "hw.h"
#include "log.h"

static volatile bool s_ntpEvent = false;

static uint8_t bcd2bin(uint8_t v) { return (v >> 4) * 10 + (v & 0x0F); }
static uint8_t bin2bcd(uint8_t v) { return ((v / 10) << 4) | (v % 10); }

bool Clock::rtcRead(struct tm& out) {
  Wire.beginTransmission(pins::RTC_ADDR);
  Wire.write(0x00);
  if (Wire.endTransmission() != 0) return false;
  if (Wire.requestFrom((int)pins::RTC_ADDR, 7) != 7) return false;
  uint8_t r[7];
  for (int i = 0; i < 7; i++) r[i] = Wire.read();
  out = {};
  out.tm_sec = bcd2bin(r[0] & 0x7F);
  out.tm_min = bcd2bin(r[1] & 0x7F);
  out.tm_hour = bcd2bin(r[2] & 0x3F);
  out.tm_mday = bcd2bin(r[4] & 0x3F);
  out.tm_mon = bcd2bin(r[5] & 0x1F) - 1;
  out.tm_year = 2000 + bcd2bin(r[6]) - 1900;
  // 🛡️ пустой модуль показывает 2000 год — такое время не принимаем
  return out.tm_year + 1900 >= 2024 && out.tm_mon >= 0 && out.tm_mon < 12 && out.tm_mday >= 1;
}

bool Clock::rtcWrite(const struct tm& t) {
  Wire.beginTransmission(pins::RTC_ADDR);
  Wire.write(0x00);
  Wire.write(bin2bcd(t.tm_sec));
  Wire.write(bin2bcd(t.tm_min));
  Wire.write(bin2bcd(t.tm_hour));
  Wire.write(bin2bcd(t.tm_wday + 1));
  Wire.write(bin2bcd(t.tm_mday));
  Wire.write(bin2bcd(t.tm_mon + 1));
  Wire.write(bin2bcd((t.tm_year + 1900) % 100));
  return Wire.endTransmission() == 0;
}

void Clock::begin() {
  setenv("TZ", "UTC0", 1);   // всё в UTC: unix-время — единственная валюта
  tzset();
  struct tm t;
  _rtcOk = rtcRead(t);
  if (_rtcOk) {
    time_t u = mktime(&t);
    struct timeval tv = {.tv_sec = u, .tv_usec = 0};
    settimeofday(&tv, nullptr);
    LOG_I("clock: время из DS3231 %04d-%02d-%02d %02d:%02d", t.tm_year + 1900, t.tm_mon + 1, t.tm_mday,
          t.tm_hour, t.tm_min);
  } else {
    // ✅ модуль отвечает, но время пустое — всё равно считаем его подключённым
    Wire.beginTransmission(pins::RTC_ADDR);
    bool present = Wire.endTransmission() == 0;
    _rtcOk = present;
    LOG_W("clock: DS3231 %s", present ? "без времени" : "не найден");
  }
}

void Clock::ntpCallback(struct timeval*) { s_ntpEvent = true; }

void Clock::startNtp() {
  sntp_set_time_sync_notification_cb(ntpCallback);
  configTime(0, 0, "pool.ntp.org", "time.google.com");   // SNTP ядра: повтор раз в час
}

void Clock::tick() {
  if (!s_ntpEvent) return;
  s_ntpEvent = false;
  _ntpSynced = true;
  LOG_I("clock: NTP ок");
  if (_rtcOk) {
    time_t u = time(nullptr);
    struct tm t;
    gmtime_r(&u, &t);
    if (!rtcWrite(t)) LOG_W("clock: не записать DS3231");
  }
}

uint32_t Clock::unix() const {
  time_t t = time(nullptr);
  return t > 1700000000 ? (uint32_t)t : 0;
}
