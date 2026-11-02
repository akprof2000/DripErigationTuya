"""Тесты возможностей прошивки 1.1.x: pump_start_sec, имена грядок, справочник
растений, уведомления (alert), flow_silence без насоса, _recheck."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "mpy" / "lib"))

from device import Device, FW_VERSION, FLOW_SILENCE_MIN  # noqa: E402
from spec import Spec  # noqa: E402
from world import World, ADC_WET, ADC_DRY  # noqa: E402

SPEC = Spec()


def make():
    w = World(8, seed=1)
    w.noise = 0
    w.auto_daynight = False
    d = Device(w, spec=SPEC)
    for i in range(8):
        d.set_low_high(i, ADC_WET, ADC_DRY)
        d.cfg.channels[i].min_val, d.cfg.channels[i].max_val = ADC_WET, ADC_DRY
    return w, d


class Clock:
    def __init__(self, d):
        self.d, self.now, self.unix = d, 400.0, 1_700_000_000.0   # now > 5 мин: alert не в «тихом» окне

    def run(self, seconds, dt=1.0):
        t = 0
        while t < seconds:
            self.now += dt
            self.unix += dt
            self.d.tick(self.now, self.unix, dt)
            t += dt


def events(d):
    out = []
    while d.events:
        out.append(json.loads(d.events.pop(0)))
    return out


class PumpStartTest(unittest.TestCase):
    def test_default_window(self):
        w, d = make()
        w.soil = [0.05] + [0.95] * 7
        c = Clock(d)
        c.run(2)
        self.assertEqual(d.pump_state(), "start")          # окно по умолчанию 30 с
        c.run(d.cfg.pump_start_sec + 2)
        self.assertEqual(d.pump_state(), "off")

    def test_disabled_window(self):
        w, d = make()
        d.cfg.pump_start_sec = 0                           # 0 = без пускового окна
        w.soil = [0.05] + [0.95] * 7
        c = Clock(d)
        c.run(2)
        self.assertTrue(d.world.open_valves[0])            # клапан открыт
        self.assertFalse(d.pump)                           # а насос не включался (порог 9 клапанов)

    def test_apply_dp(self):
        w, d = make()
        d.apply_dp("pump_start_sec", 120, 0, 1_700_000_000)
        self.assertEqual(d.cfg.pump_start_sec, 120)
        self.assertEqual(d.dp_snapshot()["pump_start_sec"], 120)


class NamesTest(unittest.TestCase):
    def test_name_dp(self):
        w, d = make()
        snap = d.dp_snapshot()
        self.assertEqual(snap["name_3"], "Растение 3")     # имя по умолчанию
        d.apply_dp("name_3", "Кабачки у забора и дальше по тексту обрезаем", 0, 1_700_000_000)
        self.assertEqual(d.cfg.channels[2].name, "Кабачки у забора и дальше по тексту обрезаем"[:32])
        # в облако имя уходит, урезанное по maxlen DP (spec.encode)
        self.assertEqual(d.dp_snapshot()["name_3"], SPEC.encode("name_3", d.cfg.channels[2].name))

    def test_bad_channel(self):
        w, d = make()
        with self.assertRaises(ValueError):
            d.apply_dp("name_9", "Лишняя", 0, 1_700_000_000)


class PlantsTest(unittest.TestCase):
    def test_defaults_and_page(self):
        w, d = make()
        page = d.plants.page()
        self.assertTrue(page.startswith("0/"))
        self.assertIn("Томаты=60", page)
        self.assertEqual(d.plants.size(), 30)

    def test_add_del_via_dp(self):
        w, d = make()
        d.apply_dp("plant_cmd", "add:Алоэ=45", 0, 1_700_000_000)
        self.assertEqual(d.plants.border("алОЭ"), 45)      # регистр не важен
        d.apply_dp("plant_cmd", "add:Алоэ=50", 0, 1_700_000_000)
        self.assertEqual(d.plants.border("Алоэ"), 50)      # обновление, не дубль
        self.assertEqual(d.plants.size(), 31)
        d.apply_dp("plant_cmd", "del:алоэ", 0, 1_700_000_000)
        self.assertEqual(d.plants.border("Алоэ"), -1)
        with self.assertRaises(ValueError):
            d.apply_dp("plant_cmd", "bogus", 0, 1_700_000_000)

    def test_list_pages(self):
        w, d = make()
        d.apply_dp("plant_cmd", "list:1:1699999999", 0, 1_700_000_000)  # как шлёт панель
        self.assertTrue(d.plants.page().startswith("1/"))


class AlertTest(unittest.TestCase):
    def test_dry_alert(self):
        w, d = make()
        w.soil = [0.05] + [0.95] * 7                        # грядка 1 почти сухая → < 20 %
        d.cfg.channels[0].name = "Томаты"
        c = Clock(d)
        seen = None
        for _ in range(90):                                 # alert живёт 10 с — ловим по тикам
            c.run(1)
            if d._alert != "-":
                seen = d._alert
                break
        self.assertIsNotNone(seen)
        self.assertIn("Томаты", seen)
        self.assertIn("пересохла", seen)
        c.run(11)
        self.assertEqual(d._alert, "-")                     # alert живёт ALERT_HOLD секунд

    def test_dry_alert_skips_off(self):
        w, d = make()
        w.soil = [0.05] + [0.95] * 7
        d.cfg.channels[0].mode = "off"                      # выключенная грядка не «пересыхает»
        c = Clock(d)
        c.run(65)
        self.assertEqual(d._alert, "-")

    def test_flow_silence_alert_ratelimit(self):
        w, d = make()
        w.soil = [0.05] + [0.95] * 7
        w.flow_sensor_ok = False                            # расходомер «умер»
        c = Clock(d)
        seen = None
        for _ in range(FLOW_SILENCE_MIN * 60 + 120):        # первым может прийти alert «пересохла»
            c.run(1)
            if "Нет потока" in d._alert:
                seen = d._alert
                break
        self.assertIsNotNone(seen)
        self.assertIn("Нет потока воды", seen)
        evs = events(d)
        self.assertIn("flow_silent", [e["t"] for e in evs])


class RecheckTest(unittest.TestCase):
    def test_mode_change_applies_next_tick(self):
        w, d = make()
        w.soil = [0.9] * 8                                  # ~90 % > порога 60+5: клапаны закрыты
        c = Clock(d)
        c.run(65)
        self.assertFalse(d.world.open_valves[0])
        d.apply_dp("mode_1", "on", c.now, c.unix)           # «всегда вкл» между минутами
        c.run(2)                                            # _recheck: применяется на следующем тике
        self.assertTrue(d.world.open_valves[0])

    def test_rain_resume_when_allowed(self):
        w, d = make()
        w.rain = True
        d.cfg.run_on_rain = False
        c = Clock(d)
        c.run(65)
        self.assertIn("rain_block", [e["t"] for e in events(d)])
        d.apply_dp("run_on_rain", True, c.now, c.unix)      # разрешили полив в дождь
        c.run(2)
        self.assertIn("rain_resume", [e["t"] for e in events(d)])


class VersionTest(unittest.TestCase):
    def test_fw_version(self):
        self.assertEqual(FW_VERSION, "1.1.11")


if __name__ == "__main__":
    unittest.main()
