"""Сверка mpy/lib/tuya.py с официальным tuyalinksdk: кадры MQTT 2.2 и подпись ATOP."""
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "mpy" / "lib"))

import tuya  # noqa: E402
from tuyalinksdk.mqtt_builder import TuyaMQTT  # noqa: E402
from tuyalinksdk.atop import ATOPBase  # noqa: E402

KEY = b"0123456789abcdefXYZ"


class FrameTest(unittest.TestCase):
    def test_pack_matches_sdk(self):
        payload = {"protocol": 4, "t": 1700000000, "data": {"devId": "d1", "dps": {"101": True}}}
        ours = tuya.pack(KEY, 7, payload)
        sdk = TuyaMQTT.encode(KEY, 7, 1, payload)
        # JSON-разделители у нас компактные, у SDK — с пробелами: сверяем через расшифровку
        self.assertEqual(TuyaMQTT.decode(KEY, bytes(ours)), [7, 1, payload])
        self.assertEqual(tuya.unpack(KEY, bytes(sdk)), (7, payload))

    def test_unpack_rejects_corruption(self):
        frame = bytearray(tuya.pack(KEY, 1, {"protocol": 5}))
        frame[-1] ^= 1
        with self.assertRaises(ValueError):
            tuya.unpack(KEY, bytes(frame))
        with self.assertRaises(ValueError):
            tuya.unpack(KEY, b"2.3" + bytes(frame[3:]))


class AtopTest(unittest.TestCase):
    def test_signed_url_matches_sdk(self):
        seen = {}

        def fake_post(url, body, headers):
            seen["url"], seen["body"] = url, body
            return {"success": True, "result": None}

        with mock.patch.object(tuya, "http_post", fake_post), mock.patch.object(tuya, "unix_time", lambda: 1700000000):
            tuya.atop("https://a1.tuyaeu.com/d.json", "tuya.device.active", "4.3", "authkeyAUTHKEY1234",
                      {"token": "x"}, uuid="uuid1")
        sdk = ATOPBase("https://a1.tuyaeu.com/d.json", "uuid1", "authkeyAUTHKEY1234")
        expected = sdk.url_encode({"a": "tuya.device.active", "v": "4.3", "uuid": "uuid1", "et": "1",
                                   "t": "1700000000"})
        # SDK оставляет «&» перед sign и тот же порядок параметров
        self.assertEqual(seen["url"], expected)
        enc = bytes.fromhex(seen["body"][5:].decode())
        self.assertEqual(ATOPBase.decrypt("authkeyAUTHKEY1234", enc), {"token": "x", "t": 1700000000})

    def test_result_decrypted(self):
        from base64 import b64encode
        res = b64encode(ATOPBase.encrypt("k" * 16, json.dumps({"devId": "D"}))).decode()
        with mock.patch.object(tuya, "http_post", lambda *a: {"success": True, "result": res}):
            self.assertEqual(tuya.atop("u", "a", "1", "k" * 16, {}), {"devId": "D"})


if __name__ == "__main__":
    unittest.main()
