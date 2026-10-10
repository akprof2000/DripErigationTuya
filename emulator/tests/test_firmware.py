"""Прошивочные модули без платы: фильтр отчётов, таблица DP, драйверы на заглушках machine."""
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "mpy" / "lib"))
sys.path.insert(0, str(ROOT / "tools"))

from reporter import Reporter  # noqa: E402
import gen_dptab  # noqa: E402
import spec  # noqa: E402


class ReporterTest(unittest.TestCase):
    def test_noisy_dps_are_throttled(self):
        r = Reporter()
        self.assertEqual(r.filter({"humidity_1": 50, "valve_1": "open_hum"}, 0), {"humidity_1": 50, "valve_1": "open_hum"})
        self.assertEqual(r.filter({"humidity_1": 51}, 60), {})            # дрожание на 1 % — молчим
        self.assertEqual(r.filter({"humidity_1": 52}, 120), {"humidity_1": 52})
        self.assertEqual(r.filter({"humidity_1": 52}, 120 + 599), {})
        self.assertEqual(r.filter({"humidity_1": 52}, 120 + 600), {"humidity_1": 52})   # раз в 10 мин — всё равно
        self.assertEqual(r.filter({"valve_1": "close_hum"}, 130), {"valve_1": "close_hum"})  # состояния — сразу
        self.assertEqual(r.filter({"event": "{}"}, 131), {"event": "{}"})

    def test_full_snapshot_passes(self):
        r = Reporter()
        r.filter({"humidity_1": 50}, 0)
        self.assertEqual(r.filter({"humidity_1": 50}, 1, full=True), {"humidity_1": 50})

    def test_adc_raw_only_by_time(self):
        r = Reporter()
        r.filter({"adc_raw": b"\x01"}, 0)
        self.assertEqual(r.filter({"adc_raw": b"\x02"}, 10), {})
        self.assertEqual(r.filter({"adc_raw": b"\x03"}, 600), {"adc_raw": b"\x03"})


class DpTableTest(unittest.TestCase):
    def test_frozen_table_matches_json(self):
        """dptab.py (на плате) описывает те же DP, что spec/dp.json (эмулятор), и не устарел."""
        src = gen_dptab.render()
        self.assertEqual((ROOT / "mpy" / "lib" / "dptab.py").read_text(encoding="utf-8"), src,
                         "запустите python tools/gen_dptab.py")
        ns = {}
        exec(src, ns)
        tab = types.SimpleNamespace(CHANNELS=ns["CHANNELS"], ENUMS=ns["ENUMS"], DPS=ns["DPS"])
        a = spec.Spec(str(ROOT / "spec" / "dp.json"))
        b = spec.Spec(table=tab)
        self.assertEqual(sorted(a.by_code), sorted(b.by_code))
        for code, dp in a.by_code.items():
            for f in spec.Dp.__slots__:
                self.assertEqual(getattr(dp, f), getattr(b.by_code[code], f), "%s.%s" % (code, f))
        self.assertEqual(b.encode("humidity_3", 42.6), 43)
        self.assertEqual(b.decode(119, "drain"), ("command", "drain"))


# ---------------- заглушка machine для hw.py / clock.py
class FakePin:
    OUT, IN, PULL_UP, PULL_DOWN, IRQ_FALLING = 1, 0, 2, 3, 4
    levels = {}

    def __init__(self, n, mode=None, pull=None, value=None):
        self.n = n
        if value is not None:
            FakePin.levels[n] = value
        FakePin.levels.setdefault(n, 0)
        self.handler = None

    def value(self, v=None):
        if v is None:
            return FakePin.levels[self.n]
        FakePin.levels[self.n] = int(v)

    def irq(self, trigger=None, handler=None):
        self.handler = handler


class FakeADC:
    ATTN_11DB = 3
    samples = [1500, 1490, 1510, 1505, 1495, 4000, 1500, 1500, 1499]   # один выброс

    def __init__(self, pin):
        self.i = 0

    def atten(self, a):
        pass

    def read(self):
        v = self.samples[self.i % len(self.samples)]
        self.i += 1
        return v


class FakeI2C:
    def __init__(self, *a, **k):
        self.written = []
        self.mem = {}
        self.fail = False

    def writeto(self, addr, data):
        if self.fail:
            raise OSError("ENODEV")
        self.written.append((addr, bytes(data)))

    def writeto_mem(self, addr, reg, data):
        self.mem[(addr, reg)] = bytes(data)

    def readfrom_mem(self, addr, reg, n):
        if (addr, reg) not in self.mem:
            raise OSError("ENODEV")
        return self.mem[(addr, reg)]


def install_fake_machine():
    m = types.ModuleType("machine")
    m.Pin, m.ADC, m.I2C = FakePin, FakeADC, FakeI2C
    sys.modules["machine"] = m
    t = sys.modules["time"]
    if not hasattr(t, "ticks_ms"):
        import time as _t
        t.ticks_ms = lambda: int(_t.monotonic() * 1000)
        t.ticks_diff = lambda a, b: a - b
        t.sleep_ms = lambda ms: None
        t.sleep_us = lambda us: None


class HardwareTest(unittest.TestCase):
    def setUp(self):
        install_fake_machine()
        for k in ("hw", "clock"):
            sys.modules.pop(k, None)

    def test_valves_pcf_active_low_and_gpio_relays(self):
        import hw
        h = hw.Hardware()
        self.assertEqual(h.i2c.written[-1], (0x20, b"\xff"))      # все закрыты
        h.open_valves[0] = True
        h.open_valves[7] = True
        self.assertEqual(h.i2c.written[-1], (0x20, bytes([0xFF & ~0x81])))
        h.open_valves = [False] * 8
        self.assertEqual(h.i2c.written[-1], (0x20, b"\xff"))
        h.pump_on = True
        self.assertEqual(FakePin.levels[hw.PIN_PUMP], 1)
        h.drain_on = True
        h.fill_on = True
        h.all_off()
        self.assertEqual((FakePin.levels[hw.PIN_PUMP], FakePin.levels[hw.PIN_DRAIN], FakePin.levels[hw.PIN_FILL]), (0, 0, 0))
        self.assertEqual(h.faults(), set())
        h.i2c.fail = True
        h.open_valves[1] = True
        self.assertEqual(h.faults(), {"valves"})

    def test_adc_median_and_weather_inputs(self):
        import hw
        h = hw.Hardware()
        self.assertEqual(h.adc(3), 1500)                  # медиана, выброс 4000 отброшен
        self.assertEqual([p.value() for p in h._mux], [1, 1, 0])
        FakePin.levels[hw.PIN_RAIN] = 0
        FakePin.levels[hw.PIN_LIGHT] = 1
        self.assertTrue(h.rain)
        self.assertTrue(h.night)

    def test_flow_pulses(self):
        import hw
        h = hw.Hardware()
        for _ in range(5):
            h._on_pulse(None)
        self.assertEqual(h.take_pulses(), 5)
        self.assertEqual(h.take_pulses(), 0)

    def test_ds3231_roundtrip(self):
        import clock
        i2c = FakeI2C()
        rtc = clock.DS3231(i2c)
        self.assertIsNone(rtc.read())
        self.assertTrue(rtc.write((2026, 10, 10, 13, 45, 7, 5)))
        self.assertEqual(rtc.read(), (2026, 10, 10, 13, 45, 7))


class WifiFormTest(unittest.TestCase):
    def test_parse_form(self):
        sys.modules["network"] = types.ModuleType("network")
        sys.modules.pop("wifi", None)
        import wifi
        self.assertEqual(wifi._parse_form("ssid=My+Net&pass=p%40ss%2F1"), {"ssid": "My Net", "pass": "p@ss/1"})


if __name__ == "__main__":
    unittest.main()
