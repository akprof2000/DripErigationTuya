"""clock.py — время на плате: DS3231 по I2C + NTP, когда есть сеть.

При старте часы ESP32 ставятся из DS3231 (если он есть), при появлении сети —
по NTP, и тогда же DS3231 подводится. unix() всегда отдаёт UTC-секунды; если
ни DS3231, ни NTP ещё не было, время считается неизвестным (ok == False) —
device.py тогда не делает выводов, зависящих от календаря.
"""
import time

from compat import unix_time

DS3231_ADDR = 0x68


def _bcd2int(b):
    return (b >> 4) * 10 + (b & 0x0F)


def _int2bcd(v):
    return ((v // 10) << 4) | (v % 10)


class DS3231:
    def __init__(self, i2c):
        self.i2c = i2c

    def read(self):
        """→ (год, месяц, день, час, мин, сек) или None, если микросхема не отвечает."""
        try:
            r = self.i2c.readfrom_mem(DS3231_ADDR, 0x00, 7)
        except OSError:
            return None
        sec, mn, hr = _bcd2int(r[0] & 0x7F), _bcd2int(r[1]), _bcd2int(r[2] & 0x3F)
        day, mon, yr = _bcd2int(r[4]), _bcd2int(r[5] & 0x1F), 2000 + _bcd2int(r[6])
        if not (1 <= mon <= 12 and 1 <= day <= 31 and yr >= 2024):
            return None            # батарейка села — мусор вместо даты
        return (yr, mon, day, hr, mn, sec)

    def write(self, t):
        yr, mon, day, hr, mn, sec = t[:6]
        wd = t[6] + 1 if len(t) > 6 else 1
        data = bytes([_int2bcd(sec), _int2bcd(mn), _int2bcd(hr), wd,
                      _int2bcd(day), _int2bcd(mon), _int2bcd(yr - 2000)])
        try:
            self.i2c.writeto_mem(DS3231_ADDR, 0x00, data)
            return True
        except OSError:
            return False


class Clock:
    NTP_RETRY = 60          # с — повтор после неудачи
    NTP_EVERY = 3600          # с — как NTP_SYNC_INTERVAL

    def __init__(self, i2c=None, log=print):
        self.rtc = DS3231(i2c) if i2c else None
        self.log = log
        self.ok = False               # время известно
        self.rtc_ok = False           # DS3231 отвечает
        self._ntp_at = None
        self._from_rtc()

    def _from_rtc(self):
        if not self.rtc:
            return
        t = self.rtc.read()
        self.rtc_ok = t is not None
        if t:
            try:
                import machine
                machine.RTC().datetime((t[0], t[1], t[2], 0, t[3], t[4], t[5], 0))
                self.ok = True
                self.log("clock: время из DS3231 %04d-%02d-%02d %02d:%02d" % t[:5])
            except Exception as e:
                self.log("clock: RTC ESP32: %s" % e)

    def sync_ntp(self, force=False):
        """Синхронизация по NTP не чаще раза в час. Вызывать, когда есть сеть."""
        now = time.time()
        if not force and self._ntp_at is not None and now - self._ntp_at < self.NTP_EVERY:
            return False
        try:
            import ntptime
            ntptime.settime()
        except Exception as e:
            self.log("clock: NTP: %s" % e)
            self._ntp_at = now - self.NTP_EVERY + self.NTP_RETRY   # не долбить сеть каждую секунду
            return False
        self._ntp_at = time.time()
        self.ok = True
        if self.rtc:
            tm = time.gmtime()
            self.rtc_ok = self.rtc.write((tm[0], tm[1], tm[2], tm[3], tm[4], tm[5], tm[6]))
        self.log("clock: NTP ок")
        return True

    def unix(self):
        return unix_time()

    def faults(self):
        return set() if (self.rtc is None or self.rtc_ok) else {"rtc"}
