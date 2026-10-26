"""Облачный API Tuya (OpenAPI): токен, состояние устройства, команды.

Подпись — «новый» алгоритм Tuya (HMAC-SHA256 от client_id + access_token + t + nonce + stringToSign).
Только стандартная библиотека: функция в Яндекс Облаке запускается без зависимостей.
"""
import hashlib
import hmac
import json
import time
import urllib.request
import uuid

EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()


class TuyaError(Exception):
    pass


class Tuya:
    def __init__(self, access_id, access_secret, endpoint="https://openapi.tuyaeu.com", opener=None):
        self.access_id = access_id
        self.secret = access_secret.encode()
        self.endpoint = endpoint.rstrip("/")
        self._token = None
        self._token_until = 0
        self._open = opener or self._urlopen

    # ------------------------------------------------------------------ подпись
    def sign(self, method, path, body, t, nonce, with_token):
        body_hash = hashlib.sha256(body).hexdigest() if body else EMPTY_SHA256
        string_to_sign = "\n".join([method, body_hash, "", path])
        msg = self.access_id + (self._token if with_token else "") + t + nonce + string_to_sign
        return hmac.new(self.secret, msg.encode(), hashlib.sha256).hexdigest().upper()

    def _request(self, method, path, payload=None, with_token=True):
        body = json.dumps(payload, separators=(",", ":")).encode() if payload is not None else b""
        t = str(int(time.time() * 1000))
        nonce = uuid.uuid4().hex
        headers = {
            "client_id": self.access_id,
            "t": t,
            "nonce": nonce,
            "sign_method": "HMAC-SHA256",
            "sign": self.sign(method, path, body, t, nonce, with_token),
            "Content-Type": "application/json",
        }
        if with_token:
            headers["access_token"] = self._token
        data = self._open(method, self.endpoint + path, headers, body or None)
        if not data.get("success"):
            raise TuyaError("%s %s: %s %s" % (method, path, data.get("code"), data.get("msg")))
        return data.get("result")

    @staticmethod
    def _urlopen(method, url, headers, body):
        req = urllib.request.Request(url, data=body, method=method, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())

    # ------------------------------------------------------------------ API
    def token(self):
        if self._token and time.time() < self._token_until - 60:
            return self._token
        res = self._request("GET", "/v1.0/token?grant_type=1", with_token=False)
        self._token = res["access_token"]
        self._token_until = time.time() + int(res.get("expire_time", 7200))
        return self._token

    def status(self, device_id):
        """{code: value} — текущие значения DP устройства."""
        self.token()
        res = self._request("GET", "/v1.0/iot-03/devices/%s/status" % device_id)
        return {item["code"]: item["value"] for item in res or []}

    def online(self, device_id):
        self.token()
        res = self._request("GET", "/v1.0/iot-03/devices/%s" % device_id)
        # в iot-03 поле называется is_online, в старом /v1.0/devices — online
        return bool(res and (res.get("is_online") if "is_online" in res else res.get("online")))

    def send(self, device_id, commands):
        """commands: {code: value}."""
        self.token()
        payload = {"commands": [{"code": c, "value": v} for c, v in commands.items()]}
        path = "/v1.0/iot-03/devices/%s/commands" % device_id
        for attempt in range(3):   # облако отклоняет частые команды подряд — повторить через паузу
            try:
                return self._request("POST", path, payload)
            except TuyaError:
                if attempt == 2:
                    raise
                time.sleep(1.0 + attempt)
