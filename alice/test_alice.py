"""Тесты навыка без сети: python -m unittest test_alice (из папки alice)."""
import base64
import json
import os
import unittest
import urllib.parse

os.environ.update({
    "TUYA_ACCESS_ID": "id", "TUYA_ACCESS_SECRET": "secret", "TUYA_DEVICE_ID": "dev1",
    "ALICE_PASSWORD": "pw", "ALICE_SECRET": "k" * 32, "ALICE_CLIENT_ID": "yandex",
    "ALICE_CLIENT_SECRET": "cs", "YANDEX_SKILL_ID": "skill", "YANDEX_OAUTH_TOKEN": "tok",
})

import dialog     # noqa: E402
import index      # noqa: E402
import mapping    # noqa: E402
from tuya_api import Tuya   # noqa: E402

STATUS = {"mode_%d" % i: "auto" for i in range(1, 9)}
STATUS.update({"humidity_%d" % i: 40 + i for i in range(1, 9)})
STATUS.update({"name_3": "Кабачки", "mode_8": "off", "humidity_8": 5, "rain": True, "drain": False,
               "fault": 0b1000})


class FakeTuya:
    def __init__(self):
        self.sent = []

    def status(self, dev):
        return dict(STATUS)

    def send(self, dev, cmds):
        self.sent.append(cmds)


def call(path, method="POST", body=None, token=True, query=None):
    ev = {"path": path, "httpMethod": method, "headers": {"X-Request-Id": "r1"},
          "body": json.dumps(body) if isinstance(body, dict) else (body or ""),
          "queryStringParameters": query or {}}
    if token:
        ev["headers"]["Authorization"] = "Bearer " + index.make_token("access", 60)
    r = index.handler(ev, None)
    return r, (json.loads(r["body"]) if r["headers"]["Content-Type"].startswith("application/json") and r["body"] else None)


class MappingTest(unittest.TestCase):
    def test_devices(self):
        devs = mapping.devices(STATUS)
        self.assertEqual([d["id"] for d in devs][:3], ["bed_1", "bed_1_auto", "bed_1_greenhouse"])
        by_id = {d["id"]: d["name"] for d in devs}
        self.assertEqual(by_id["bed_3"], "Кабачки")
        self.assertEqual(by_id["bed_3_greenhouse"], "Кабачки в парнике")
        self.assertEqual(by_id["bed_1_auto"], "Растение 1 автополив")
        self.assertEqual(by_id["all_auto"], "Автополив")
        self.assertEqual(len(devs), 29)
        self.assertTrue(all(len(d["name"]) <= mapping.NAME_MAX for d in devs))
        self.assertEqual(by_id["all_greenhouse"], "Полив в парнике")

    def test_mode_switches(self):
        st = lambda d: mapping.state(d, STATUS)["capabilities"][0]["state"]["value"]
        self.assertTrue(st("bed_1_auto"))
        self.assertFalse(st("bed_1_greenhouse"))
        self.assertFalse(st("all_auto"))   # грядка 8 выключена
        on = {"type": mapping.ON_OFF, "state": {"instance": "on", "value": True}}
        off = {"type": mapping.ON_OFF, "state": {"instance": "on", "value": False}}
        self.assertEqual(mapping.commands("bed_4_greenhouse", on), {"mode_4": "greenhouse"})
        self.assertEqual(mapping.commands("bed_4_auto", off), {"mode_4": "off"})
        self.assertEqual(mapping.commands("all_auto", on), {"mode_all": "auto"})

    def test_state(self):
        s = mapping.state("bed_8", STATUS)
        self.assertEqual(s["capabilities"][0]["state"]["value"], False)
        st = {p["state"]["instance"]: p["state"]["value"] for p in mapping.state("status", STATUS)["properties"]}
        self.assertEqual(st, {"water_level": "low", "water_leak": "dry", "open": "opened", "humidity": 41.0})

    def test_commands(self):
        self.assertEqual(mapping.commands("bed_2", {"type": mapping.ON_OFF, "state": {"instance": "on", "value": True}}),
                         {"mode_2": "on"})
        self.assertEqual(mapping.commands("drain", {"type": mapping.ON_OFF, "state": {"instance": "on", "value": True}}),
                         {"command": "drain"})
        with self.assertRaises(ValueError):
            mapping.commands("status", {"type": mapping.ON_OFF, "state": {"instance": "on", "value": True}})


class DialogTest(unittest.TestCase):
    def ask(self, text):
        return dialog.answer(text, STATUS)

    def test_find_bed(self):
        f = lambda t: dialog.find_bed(t, STATUS)
        self.assertEqual(f("какая влажность грядки 2"), 2)
        self.assertEqual(f("что растёт на пятой грядке"), 5)
        self.assertEqual(f("что растет на первой"), 1)
        self.assertEqual(f("какая влажность кабачков"), 3)
        self.assertIsNone(f("какая влажность сейчас"))

    def test_answers(self):
        self.assertEqual(self.ask("что растёт на грядке 3"), "На грядке 3 — Кабачки.")
        self.assertIn("влажность 43 %", self.ask("какая влажность кабачков"))
        self.assertIn("влажность 47 %", self.ask("какая влажность растения 7"))
        self.assertIn("выключена", self.ask("влажность грядки восемь"))
        all_h = self.ask("какая влажность сейчас")
        self.assertIn("Растение 1 41 %", all_h)
        self.assertIn("Растение 8 5 % (выключена)", all_h)
        self.assertIn("8 — Растение 8", self.ask("что где растёт"))

    def test_watering(self):
        st = dict(STATUS, valve_1="open_hum", valve_3="forced_open", valve_2="close_hum", valve_5="hyst")
        a = lambda q: dialog.answer(q, st)
        self.assertEqual(a("на каких грядках сейчас идёт полив"), "Сейчас поливаются: Растение 1, Кабачки.")
        self.assertEqual(a("что сейчас поливается"), "Сейчас поливаются: Растение 1, Кабачки.")
        self.assertEqual(a("поливаются ли кабачки"), "Кабачки: сейчас идёт полив.")
        self.assertEqual(a("идёт ли полив на грядке 2"), "Растение 2: сейчас полива нет.")
        q = "где идёт полив"
        self.assertEqual(dialog.answer(q, dict(STATUS, rain=True)),
                         "Сейчас полив нигде не идёт: идёт дождь, полив на улице выключен.")
        self.assertEqual(dialog.answer(q, dict(STATUS, rain=False, night=True)),
                         "Сейчас полив нигде не идёт: сейчас ночь, полив выключен до утра.")
        self.assertEqual(dialog.answer(q, dict(STATUS, rain=False)), "Сейчас полив нигде не идёт: земля достаточно влажная.")
        off = dict(STATUS, **{"mode_%d" % c: "off" for c in range(1, 9)})
        self.assertEqual(dialog.answer(q, off), "Сейчас полив нигде не идёт: все грядки выключены.")
        gh = dict(STATUS, rain=True, mode_2="greenhouse")
        self.assertIn("только грядки в парнике", dialog.answer(q, gh))
        self.assertIn("влажность 42 %", a("какая влажность грядки 2"))

    def test_protocol(self):
        index._tuya = FakeTuya()
        req ={"version": "1.0", "session": {"new": False}, "request": {"original_utterance": "что растёт на грядке 3"}}
        r, b = call("/dialog", body=req, token=False)
        self.assertEqual(r["statusCode"], 200)
        self.assertEqual(b["response"]["text"], "На грядке 3 — Кабачки.")


class ProtocolTest(unittest.TestCase):
    def setUp(self):
        index._tuya = FakeTuya()

    def test_unauthorized(self):
        r, _ = call("/v1.0/user/devices", "GET", token=False)
        self.assertEqual(r["statusCode"], 401)

    def test_ping(self):
        self.assertEqual(call("/v1.0", "HEAD", token=False)[0]["statusCode"], 200)

    def test_devices_and_query(self):
        _, b = call("/v1.0/user/devices", "GET")
        self.assertEqual(b["payload"]["user_id"], "owner")
        _, b = call("/v1.0/user/devices/query", body={"devices": [{"id": "bed_3"}, {"id": "drain"}]})
        self.assertEqual(b["payload"]["devices"][0]["properties"][0]["state"]["value"], 43.0)

    def test_action(self):
        body = {"payload": {"devices": [{"id": "bed_1", "capabilities": [
            {"type": mapping.ON_OFF, "state": {"instance": "on", "value": False}}]}]}}
        _, b = call("/v1.0/user/devices/action", body=body)
        self.assertEqual(b["payload"]["devices"][0]["capabilities"][0]["state"]["action_result"]["status"], "DONE")
        self.assertEqual(index._tuya.sent, [{"mode_1": "off"}])


class OAuthTest(unittest.TestCase):
    Q = {"redirect_uri": "https://social.yandex.net/broker/redirect", "client_id": "yandex",
         "state": "xyz", "response_type": "code"}

    def test_flow(self):
        r, _ = call("/oauth/authorize", "GET", token=False, query=self.Q)
        self.assertEqual(r["statusCode"], 200)
        self.assertIn("password", r["body"])
        form = urllib.parse.urlencode(dict(self.Q, password="bad"))
        r, _ = call("/oauth/authorize", "POST", body=form, token=False)
        self.assertIn("Неверный пароль", r["body"])
        form = urllib.parse.urlencode(dict(self.Q, password="pw"))
        r, _ = call("/oauth/authorize", "POST", body=form, token=False)
        self.assertEqual(r["statusCode"], 302)
        loc = urllib.parse.urlparse(r["headers"]["Location"])
        q = urllib.parse.parse_qs(loc.query)
        self.assertEqual(q["state"], ["xyz"])
        tok_form = urllib.parse.urlencode({"grant_type": "authorization_code", "code": q["code"][0],
                                           "client_id": "yandex", "client_secret": "cs"})
        r, b = call("/oauth/token", "POST", body=tok_form, token=False)
        self.assertEqual(r["statusCode"], 200)
        self.assertTrue(index.check_token(b["access_token"], "access"))

    def test_bad_redirect(self):
        r, _ = call("/oauth/authorize", "GET", token=False, query=dict(self.Q, redirect_uri="https://evil.example/"))
        self.assertEqual(r["statusCode"], 400)

    def test_basic_auth_client(self):
        code = index.make_token("code", 60)
        ev = {"path": "/oauth/token", "httpMethod": "POST",
              "headers": {"Authorization": "Basic " + base64.b64encode(b"yandex:cs").decode()},
              "body": urllib.parse.urlencode({"grant_type": "authorization_code", "code": code})}
        self.assertEqual(index.handler(ev, None)["statusCode"], 200)


class TuyaSignTest(unittest.TestCase):
    def test_sign_example(self):
        # пример из документации Tuya «Sign requests for cloud authorization» (token API)
        t = Tuya("1KAD46OrT9HafiKdsXeg", "4OHBOnWOqaEC1mWXOpVL3yV50s0qGSRC")
        s = t.sign("GET", "/v1.0/token?grant_type=1", b"", "1588925778000", "5138cc3a9033d69856923fd07b491173", False)
        self.assertEqual(len(s), 64)
        self.assertEqual(s, s.upper())

    def test_requests(self):
        calls = []

        def opener(method, url, headers, body):
            calls.append((method, url, headers.get("access_token")))
            if "/token" in url:
                return {"success": True, "result": {"access_token": "AT", "expire_time": 7200}}
            if url.endswith("/status"):
                return {"success": True, "result": [{"code": "rain", "value": False}]}
            return {"success": True, "result": True}

        t = Tuya("id", "secret", opener=opener)
        self.assertEqual(t.status("d"), {"rain": False})
        t.send("d", {"mode_1": "on"})
        self.assertEqual(calls[0][2], None)
        self.assertEqual(calls[1][2], "AT")
        self.assertEqual(len([c for c in calls if "/token" in c[1]]), 1)


if __name__ == "__main__":
    unittest.main()
