"""Заглушка machine для прогона прошивки в unix-порте MicroPython (tools/sim_fw.sh).

Железа нет: пины помнят уровни, АЦП отдаёт правдоподобный шум, I2C «видит»
PCF8574 и DS3231, SD-карты нет. Так проверяется, что app.py, hw.py, clock.py и
wifi.py вообще запускаются и крутят главный цикл на настоящем MicroPython.
"""
import time

_levels = {}
_mem = {}


class Pin:
    OUT, IN, PULL_UP, PULL_DOWN, IRQ_FALLING = 1, 0, 2, 3, 4

    def __init__(self, n, mode=None, pull=None, value=None):
        self.n = n
        if value is not None:
            _levels[n] = value
        if n not in _levels:
            _levels[n] = 1 if pull == Pin.PULL_UP else 0
        self.handler = None

    def value(self, v=None):
        if v is None:
            return _levels[self.n]
        _levels[self.n] = int(v)

    def irq(self, trigger=None, handler=None):
        self.handler = handler


class ADC:
    ATTN_11DB = 3
    _i = 0

    def __init__(self, pin):
        pass

    def atten(self, a):
        pass

    def read(self):
        ADC._i += 1
        return 1800 + (ADC._i * 37) % 23


class I2C:
    def __init__(self, *a, **k):
        pass

    def writeto(self, addr, data):
        if addr != 0x20:
            raise OSError("ENODEV")

    def writeto_mem(self, addr, reg, data):
        _mem[(addr, reg)] = bytes(data)

    def readfrom_mem(self, addr, reg, n):
        if addr == 0x68 and (addr, reg) not in _mem:
            # 2026-10-10 12:00:00
            return bytes([0x00, 0x00, 0x12, 0x06, 0x10, 0x10, 0x26])
        if (addr, reg) not in _mem:
            raise OSError("ENODEV")
        return _mem[(addr, reg)]


class SDCard:
    def __init__(self, **k):
        raise OSError("no SD in sim")


class WDT:
    def __init__(self, timeout=0):
        pass

    def feed(self):
        pass


class RTC:
    def datetime(self, t=None):
        return t


def reset():
    print("machine.reset() — в симуляции выходим")
    raise SystemExit(0)
