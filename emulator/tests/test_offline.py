"""Причина работы насоса, ручной дренаж, тишина расходомера, sys_info и очередь офлайн."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "mpy" / "lib"))

from device import Device, PUMP_TIMEOUT, DRAIN_TIMEOUT, FW_VERSION  # noqa: E402
from outbox import Outbox  # noqa: E402
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


def events(d):
    return [json.loads(e)["t"] for e in d.events]


class PumpStateTest(unittest.TestCase):
    def test_reasons(self):
        w, d = make()
        c = Clock(d)
        self.assertEqual(d.pump_state(), "off")
        w.soil[0] = 0.1                       # грядка 1 сухая → клапан откроется на первом же цикле
        c.run(2)
        self.assertEqual(d.pump_state(), "start")
        c.run(PUMP_TIMEOUT + 2)
        self.assertEqual(d.pump_state(), "off")   # порог 9 = насос по клапанам не нужен
        d.cfg.boost_pump_valves = 1
        d.stop_pump_if_need()
        self.assertEqual(d.pump_state(), "valves")
        d.apply_dp("command", "drain", c.now, c.unix)
        self.assertEqual(d.pump_state(), "drain")
        self.assertIn("drain_start", events(d))
        c.run(DRAIN_TIMEOUT + 2)
        self.assertIn("drain_end", events(d))
        self.assertEqual(d.dp_snapshot()["pump_state"], "valves")


class FlowSensorTest(unittest.TestCase):
    def test_silent_and_recovered(self):
        w, d = make()
        c = Clock(d)
        d.cfg.boost_pump_valves = 1           # насос держится, пока открыт хоть один клапан
        w.soil[0] = 0.1
        c.run(61)
        self.assertGreater(d.flow_pulses, 0)
        w.flow_sensor_ok = False
        c.run(60 * 3)
        self.assertIn("flow_silent", events(d))
        self.assertTrue(d.flow_silent)
        w.flow_sensor_ok = True
        c.run(60 * 2)
        self.assertIn("flow_ok", events(d))
        info = json.loads(d.sys_info(c.unix, {"heap": 1, "pending": 2}))
        self.assertEqual(info["fw"], FW_VERSION)
        self.assertGreater(info["up"], 0)
        self.assertEqual(info["pending"], 2)
        self.assertGreaterEqual(info["last_pulse"], 0)
        self.assertLessEqual(len(d.sys_info(c.unix)), 255)


class OutboxTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.path = os.path.join(self.tmp, "pending.jsonl")

    def test_put_flush_in_order_with_time(self):
        ob = Outbox(self.path)
        ob.put({131: 40}, 1000)
        ob.put({123: b"\x01\x02"}, 1001)
        ob.put({124: '{"t":"rain_start"}'}, 1002)
        self.assertEqual(Outbox(self.path).count, 3)   # переживает перезапуск
        sent = []
        self.assertEqual(ob.flush(lambda dps, t: sent.append((dps, t)) or True, now=1030), 3)
        self.assertEqual([t for _, t in sent], [None, None, None])   # всё свежее — без метки
        self.assertEqual(sent[1][0]["123"], b"\x01\x02")
        self.assertEqual(ob.count, 0)
        sent.clear()
        ob.put({131: 41}, 1000)
        ob.put({131: 42}, 2000)
        ob.flush(lambda dps, t: sent.append((dps, t)) or True, now=2030)
        self.assertEqual([t for _, t in sent], [1000, None])         # старое — с меткой

    def test_partial_failure_keeps_rest(self):
        ob = Outbox(self.path)
        for i in range(5):
            ob.put({131: i}, 1000 + i)
        calls = []

        def push(dps, t):
            calls.append(t)
            return len(calls) <= 2        # после двух отправок «связь пропала»
        self.assertEqual(ob.flush(push), 2)
        self.assertEqual(ob.count, 3)
        self.assertEqual(ob.flush(lambda dps, t: True), 3)

    def test_trim_drops_oldest(self):
        import outbox
        old = outbox.MAX_BYTES, outbox.TRIM_TO
        outbox.MAX_BYTES, outbox.TRIM_TO = 200, 100
        try:
            ob = Outbox(self.path)
            for i in range(50):
                ob.put({131: i}, 1000 + i)
            sent = []
            ob.flush(lambda dps, t: sent.append(t) or True)
            self.assertLess(len(sent), 50)
            self.assertEqual(sent[-1], 1049)           # новейшие сохранены
        finally:
            outbox.MAX_BYTES, outbox.TRIM_TO = old


if __name__ == "__main__":
    unittest.main()
