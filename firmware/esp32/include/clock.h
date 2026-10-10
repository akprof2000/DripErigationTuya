// clock.h 🕐 Время контроллера: DS3231 по I2C + NTP (SNTP ядра, автоматически раз в час).
// При старте системное время берётся из DS3231 (если есть); при каждой синхронизации NTP
// часы DS3231 подводятся. ok() — время известно (из любого источника).
#pragma once
#include <Arduino.h>

class Clock {
 public:
  void begin();                  // прочитать DS3231 → системное время
  void startNtp();               // вызывать, когда появился Wi-Fi (configTime + колбэк синхронизации)
  void tick();                   // обслуживание: после NTP-синхронизации записать DS3231
  uint32_t unix() const;         // 0, если время неизвестно
  bool ok() const { return unix() != 0; }
  bool rtcPresent() const { return _rtcOk; }
  bool ntpSynced() const { return _ntpSynced; }
  bool faultRtc() const { return !ok(); }   // блокирующая авария «rtc» — только когда времени нет совсем

 private:
  bool _rtcOk = false;
  bool _ntpSynced = false;
  bool _writePending = false;
  bool rtcRead(struct tm& out);
  bool rtcWrite(const struct tm& t);
  static void ntpCallback(struct timeval* tv);
};
