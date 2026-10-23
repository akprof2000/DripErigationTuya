"""Тесты логики эмулятора: python -m unittest discover -s tests (из папки emulator)."""
import json
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "mpy" / "lib"))

from device import Device, decide_valve, arduino_map, PUMP_TIMEOUT  # noqa: E402
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
        self.d, self.now, self.unix = d, 0.0, 1_700_000_000.0

    def run(self, seconds, dt=1.0):
        t = 0
        while t < seconds:
            self.now += dt
            self.unix += dt
            self.d.tick(self.now, self.unix, dt)
            t += dt


class SpecTest(unittest.TestCase):
    def test_expand_channels(self):
        self.assertEqual(SPEC.by_code["humidity_1"].id, 131)
        self.assertEqual(SPEC.by_code["border_8"].id, 168)
        self.assertEqual(len(SPEC.dps), 67)            # как в консоли Tuya
        self.assertEqual(SPEC.by_id[158].code, "mode_8")

    def test_value_scale(self):
        self.assertEqual(SPEC.encode("flow_rate", 0.0625), 63)
        self.assertEqual(SPEC.decode(113, 7), ("delta_hum", 7))

    def test_reject_ro_and_range(self):
        with self.assertRaises(ValueError):
            SPEC.decode(131, 50)            # humidity — только чтение
        with self.assertRaises(ValueError):
            SPEC.decode(161, 101)           # порог > 100
        with self.assertRaises(ValueError):
            SPEC.decode(151, "turbo")       # нет такого режима


class DecideValveTest(unittest.TestCase):
    def test_auto(self):
        self.assertEqual(decide_valve("auto", 40, 60, 5, "init"), ("open", "open_hum", True))
        self.assertEqual(decide_valve("auto", 70, 60, 5, "open_hum"), ("close", "close_hum", True))
        self.assertEqual(decide_valve("auto", 60, 60, 5, "open_hum"), ("hold", "hyst", False))
        self.assertEqual(decide_valve("auto", 60, 60, 5, "init"), ("hold", "hyst", True))

    def test_forced(self):
        self.assertEqual(decide_valve("on", 99, 60, 5, "forced_open"), ("open", "forced_open", False))
        self.assertEqual(decide_valve("off", 0, 60, 5, "init"), ("close", "forced_close", True))

    def test_arduino_map_truncates(self):
        self.assertEqual(arduino_map(2000, 2915, 1235, 0, 100), 54)


class DeviceTest(unittest.TestCase):
    def test_dry_bed_opens_valve_and_pump(self):
        w, d = make()
        w.soil = [0.05] + [0.95] * 7
        c = Clock(d)
        c.run(2)                            # первый минутный цикл — сразу на старте
        self.assertEqual(d.old_mode[0], "open_hum")
        self.assertTrue(w.open_valves[0])
        self.assertTrue(d.pump)             # пусковое окно насоса
        self.assertEqual(d.old_mode[1], "close_hum")

    def test_pump_stops_after_start_window(self):
        w, d = make()
        w.soil = [0.05] + [0.95] * 7
        c = Clock(d)
        c.run(PUMP_TIMEOUT + 5)
        self.assertFalse(d.pump)          # boost_pump_valves = 9 → насос только в пусковом окне
        d.cfg.boost_pump_valves = 1
        d.stop_pump_if_need()
        self.assertTrue(d.pump)

    def test_night_blocks_greenhouse_too(self):
        w, d = make()
        w.soil = [0.05] * 8
        w.night = True
        d.cfg.channels[0].mode = "greenhouse"
        Clock(d).run(61)
        self.assertFalse(any(w.open_valves))
        self.assertEqual(d.old_mode[0], "forced_close")

    def test_rain_allows_greenhouse(self):
        w, d = make()
        w.soil = [0.05] * 8
        w.rain = True
        d.cfg.run_on_rain = False
        d.cfg.channels[0].mode = "greenhouse"
        Clock(d).run(61)
        self.assertTrue(w.open_valves[0])
        self.assertFalse(w.open_valves[1])

    def test_hw_fault_shuts_everything(self):
        w, d = make()
        w.soil = [0.05] * 8
        c = Clock(d)
        c.run(61)
        d.hw_faults.add("sd")
        c.run(2)
        self.assertFalse(any(w.open_valves))
        self.assertFalse(d.pump)
        snap = d.dp_snapshot()
        self.assertEqual(snap["fault"], 0b10)

    def test_calibration_wizard(self):
        w, d = make()
        c = Clock(d)
        c.run(61)
        d.apply_dp("wizard", json.dumps({"op": "calib", "ch": 3, "step": "start"}), c.now, c.unix)
        self.assertEqual(d.wizard["step"], "wet")
        w.place[2] = "water"
        d.apply_dp("wizard", '{"op":"calib","step":"next"}', c.now, c.unix)
        self.assertEqual(d.wizard["step"], "dry")
        c.run(180)                          # 3 минуты в воде — авто-калибровка не должна сработать
        self.assertEqual(d.cfg.channels[2].min_val, ADC_WET)
        w.place[2] = "air"
        d.apply_dp("wizard", '{"op":"calib","step":"next"}', c.now, c.unix)
        d.apply_dp("wizard", '{"op":"calib","step":"finish"}', c.now, c.unix)
        self.assertTrue(d.wizard["ok"])
        self.assertEqual((d.cfg.channels[2].min_val, d.cfg.channels[2].max_val), (ADC_WET, ADC_DRY))

    def test_calibration_too_small_span(self):
        w, d = make()
        c = Clock(d)
        d.apply_dp("wizard", '{"op":"calib","ch":1,"step":"start"}', c.now, c.unix)
        d.apply_dp("wizard", '{"op":"calib","step":"next"}', c.now, c.unix)
        d.apply_dp("wizard", '{"op":"calib","step":"next"}', c.now, c.unix)
        d.apply_dp("wizard", '{"op":"calib","step":"finish"}', c.now, c.unix)
        self.assertFalse(d.wizard["ok"])
        self.assertEqual(d.low[0], ADC_WET)  # границы вернулись к сохранённым

    def test_search_wizard(self):
        w, d = make()
        c = Clock(d)
        d.apply_dp("wizard", '{"op":"search","step":"start"}', c.now, c.unix)
        w.place[5] = "water"
        d.apply_dp("wizard", '{"op":"search","step":"next"}', c.now, c.unix)
        w.place[5] = "air"
        d.apply_dp("wizard", '{"op":"search","step":"next"}', c.now, c.unix)
        self.assertEqual(d.wizard["found"], 6)

    def test_filter_clog_alarm(self):
        # алгоритм objects.cpp: ≥10 мин стабилизации, окна по 2 мин, эталон
        # подтверждается 5 мин, засор — 3 плохих окна подряд
        w, d = make()
        w.soil = [0.05] + [0.95] * 7
        w.dry_rate = 0.0                     # грядка не «высыхает» и не «намокает» — клапан держит
        w.wet_rate = 0.0
        w.valve_lpm = 0.5                    # 0.5 л/мин ≈ 3.75 имп/с — хватает на MIN_PULSES за окно
        d.cfg.boost_pump_valves = 1          # насос держит поток, пока открыт клапан
        c = Clock(d)
        c.run(25 * 60)
        self.assertAlmostEqual(d.cfg.clean_flow_per_valve, 0.5, delta=0.05)
        self.assertFalse(d.clogged)
        w.clog = 0.3                         # поток 30 % от нормы (порог 50 %)
        c.run(8 * 60)
        self.assertTrue(d.clogged)
        self.assertIn("clog", [json.loads(e)["t"] for e in d.events])
        w.clog = 1.0
        c.run(5 * 60)
        self.assertFalse(d.clogged)          # поток вернулся — тревога снята
        self.assertIn("clog_end", [json.loads(e)["t"] for e in d.events])
        w.clog = 0.3
        c.run(8 * 60)
        self.assertTrue(d.clogged)
        d.apply_dp("command", "filter_cleaned", c.now, c.unix)
        self.assertFalse(d.clogged)
        self.assertEqual(d.cfg.clean_flow_per_valve, 0.0)

    def test_report_diff_and_events(self):
        w, d = make()
        first = d.report(full=True)
        self.assertIn("humidity_1", first[0])
        self.assertEqual(d.report(), [])
        d.apply_dp("mode_2", "off", 0, 0)
        pk = d.report()
        self.assertEqual(pk, [{"mode_2": "off"}])
        d.event("valve", ch=3, s="open_hum", h=41)
        self.assertEqual(d.report(), [{"event": '{"t":"valve","ch":3,"s":"open_hum","h":41}'}])

    def test_adc_raw_layout(self):
        w, d = make()
        d.read_all()
        raw = d.dp_snapshot()["adc_raw"]
        vals = struct.unpack(">24H", raw)
        self.assertEqual(vals[1:3], (ADC_WET, ADC_DRY))


if __name__ == "__main__":
    unittest.main()
