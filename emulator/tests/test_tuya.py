"""Проверка mpy/lib/tuya.py и compat.py против независимой реализации (pycryptodome).

Форматы — как в TuyaOpen (protocol/tuya_protocol.c, cloud/atop_base.c): кадр MQTT 2.3
и запрос ATOP с et=3 шифруются AES-128-GCM.
"""
import json
import os
import struct
import sys
import unittest
from base64 import b64encode
from pathlib import Path
from unittest import mock
from urllib.parse import urlsplit, parse_qsl

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "mpy" / "lib"))

import compat  # noqa: E402
import tuya  # noqa: E402
from Crypto.Cipher import AES  # noqa: E402
from hashlib import md5  # noqa: E402

KEY = b"0123456789abcdefXYZ"   # как localKey/AuthKey: в шифр идут первые 16 байт


def ref_gcm(key, nonce, data, aad=b""):
    c = AES.new(key[:16], AES.MODE_GCM, nonce=nonce)
    c.update(aad)
    return c.encrypt_and_digest(data)


class GcmTest(unittest.TestCase):
    def test_matches_pycryptodome(self):
        for n in (0, 1, 15, 16, 17, 255, 1000):
            k, iv, pt, aad = os.urandom(16), os.urandom(12), os.urandom(n), os.urandom(12)
            self.assertEqual(compat.gcm_encrypt(k, iv, pt, aad), ref_gcm(k, iv, pt, aad))
            ct, tag = ref_gcm(k, iv, pt, aad)
            self.assertEqual(compat.gcm_decrypt(k, iv, ct, tag, aad), pt)

    def test_bad_tag(self):
        ct, tag = compat.gcm_encrypt(KEY[:16], bytes(12), b"hello")
        with self.assertRaises(ValueError):
            compat.gcm_decrypt(KEY[:16], bytes(12), ct, bytes(16))


class FrameTest(unittest.TestCase):
    payload = {"protocol": 4, "t": 1700000000, "data": {"devId": "d1", "dps": {"101": True}}}

    def test_pack_layout(self):
        f = tuya.pack(KEY, 7, self.payload)
        self.assertEqual(f[:3], b"2.3")
        self.assertEqual(struct.unpack(">II", f[3:11]), (7, 1))
        self.assertEqual(f[11], 0)
        c = AES.new(KEY[:16], AES.MODE_GCM, nonce=f[12:24])
        c.update(f[:12])
        self.assertEqual(json.loads(c.decrypt_and_verify(f[24:-16], f[-16:])), self.payload)

    def test_unpack_cloud_frame(self):
        head = b"2.3" + struct.pack(">II", 42, 1) + b"\x00"
        nonce = os.urandom(12)
        ct, tag = ref_gcm(KEY, nonce, json.dumps(self.payload).encode(), head)
        self.assertEqual(tuya.unpack(KEY, head + nonce + ct + tag), (42, self.payload))

    def test_unpack_rejects_corruption(self):
        f = bytearray(tuya.pack(KEY, 1, {"protocol": 5}))
        f[-1] ^= 1
        with self.assertRaises(ValueError):
            tuya.unpack(KEY, bytes(f))
        with self.assertRaises(ValueError):
            tuya.unpack(KEY, b"9.9" + bytes(f[3:]))

    def test_unpack_legacy_22(self):
        # облако шлёт 2.2 клиенту, который не назвался |pv=2.3 — такой кадр тоже понимаем
        from tuyalinksdk.mqtt_builder import TuyaMQTT
        self.assertEqual(tuya.unpack(KEY, bytes(TuyaMQTT.encode(KEY, 3, 1, self.payload))), (3, self.payload))


class AtopTest(unittest.TestCase):
    AUTH = "authkeyAUTHKEY1234abcdefghijklmn"   # 32 символа, как настоящий AuthKey

    def call(self, response):
        seen = {}

        def fake_post(url, body, headers):
            seen["url"], seen["body"] = url, body
            return response

        with mock.patch.object(tuya, "http_post", fake_post), \
                mock.patch.object(tuya, "unix_time", lambda: 1700000000):
            res = tuya.atop("https://a1.tuyaeu.com/d.json", "thing.device.opensdk.active", "1.0",
                            self.AUTH, {"token": "x"}, uuid="uuid1")
        return res, seen

    def test_request_format(self):
        ok = self.encrypt_response({"success": True, "result": {"devId": "D"}, "t": 1})
        res, seen = self.call(ok)
        self.assertEqual(res, {"devId": "D"})
        url = urlsplit(seen["url"])
        params = parse_qsl(url.query)
        self.assertEqual([k for k, _ in params], ["a", "et", "t", "uuid", "v", "sign"])
        self.assertEqual(dict(params)["et"], "3")
        signed = "".join("%s=%s||" % p for p in params[:-1]) + self.AUTH
        self.assertEqual(dict(params)["sign"], md5(signed.encode()).hexdigest())
        raw = bytes.fromhex(seen["body"][5:].decode())
        c = AES.new(self.AUTH.encode()[:16], AES.MODE_GCM, nonce=raw[:12])
        self.assertEqual(json.loads(c.decrypt_and_verify(raw[12:-16], raw[-16:])), {"token": "x", "t": 1700000000})

    def test_error_raises(self):
        with self.assertRaises(OSError) as e:
            self.call(self.encrypt_response({"success": False, "errorCode": "ACTIVE_OPEN_SDK_NOT_MATCHED"}))
        self.assertIn("ACTIVE_OPEN_SDK_NOT_MATCHED", str(e.exception))

    def encrypt_response(self, obj):
        nonce = os.urandom(12)
        ct, tag = ref_gcm(self.AUTH.encode(), nonce, json.dumps(obj).encode())
        return {"result": b64encode(nonce + ct + tag).decode(), "t": 1}


if __name__ == "__main__":
    unittest.main()
