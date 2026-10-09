"""tuya.py — подключение устройства к облаку Tuya по MQTT (протокол 2.2).

Порт tuyalinksdk 0.0.3 (официальный Python SDK Tuya) без зависимостей: работает
в MicroPython на ESP32 и в CPython (эмулятор). Лицензия — UUID + AuthKey
(TuyaOpen License из консоли), продукт — PID.

Жизненный цикл (всё внутри loop(), главный цикл полива не блокируется дольше
одного сетевого шага):
  bind    — устройство не активировано: MQTT под acon_<uuid>, ждём токен,
            который облако присылает после сканирования QR в Smart Life;
            токен → HTTPS tuya.device.active → devId/secKey/localKey во флеш
  online  — MQTT под devId: принимаем DP (протокол 5), отправляем DP (4)
  wait    — связь потеряна: повтор через backoff (5 с … 5 мин)
"""
import binascii
import json
import struct

from compat import (aes_encrypt, aes_decrypt, md5_hex, crc32, b64encode, b64decode,
                    http_post, unix_time, ticks_ms, ticks_add, ticks_diff)
from mqtt import MQTT

PV = b"2.2"
MQ_DPS_PUSH, MQ_DPS_ON, MQ_RESET, MQ_TOKEN = 4, 5, 11, 46
IOTDNS = "https://h1.iot-dns.com/v1/url_config"


def _dumps(obj):
    try:
        return json.dumps(obj, separators=(",", ":"))
    except TypeError:
        return json.dumps(obj)


# ---------------------------------------------------------------- кадр MQTT 2.2
def pack(key, seq, payload):
    """'2.2' | crc32(seq,src,data) | seq | src=1 | AES-ECB(JSON)."""
    data = aes_encrypt(key, _dumps(payload).encode())
    ss = struct.pack("!II", seq, 1)
    return PV + struct.pack("!I", crc32(ss + data) & 0xFFFFFFFF) + ss + data


def unpack(key, frame):
    """Кадр → (seq, dict). ValueError на чужой версии, битом CRC или ключе."""
    if frame[:3] != PV:
        raise ValueError("версия кадра %r" % frame[:3])
    crc, seq = struct.unpack("!II", frame[3:11])
    body = frame[7:]
    if crc32(body) & 0xFFFFFFFF != crc:
        raise ValueError("CRC")
    data = frame[15:]
    if len(data) % 16:
        raise ValueError("длина")
    return seq, json.loads(aes_decrypt(key, data))


# ---------------------------------------------------------------- HTTPS (ATOP)
def atop(url, api, ver, key, data, uuid=None, dev_id=None):
    """Запрос к ATOP: подпись md5 по параметрам, тело — AES(JSON) в hex."""
    t = unix_time()
    params = [("a", api)]
    if dev_id:
        params.append(("devId", dev_id))
    params += [("et", "1"), ("t", str(t))]
    if uuid:
        params.append(("uuid", uuid))
    params.append(("v", ver))
    sign = md5_hex(("||".join("%s=%s" % p for p in params) + "||" + key).encode())
    q = "&".join("%s=%s" % p for p in params) + "&sign=" + sign
    data["t"] = t
    body = b"data=" + _hex_upper(aes_encrypt(key.encode(), _dumps(data).encode()))
    r = http_post(url + "?" + q, body, {
        "User-Agent": "TUYA_IOT_SDK",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"})
    if not r.get("success"):
        raise OSError("ATOP %s: %s" % (api, r.get("errorCode") or r))
    res = r.get("result")
    if isinstance(res, str):
        res = json.loads(aes_decrypt(key.encode(), b64decode(res)))
    return res


def _hex_upper(b):
    return binascii.hexlify(b).upper()


def endpoints(region=None, env="pro"):
    cfg = {"config": [{"key": "httpsUrl", "need_ca": False}, {"key": "mqttsUrl", "need_ca": False}]}
    if region:
        cfg["region"], cfg["env"] = region, env
    r = http_post(IOTDNS, _dumps(cfg).encode(), {"Content-Type": "application/json"})
    host, port = r["mqttsUrl"]["addr"].split(":")
    return {"mqtt": host, "port": int(port), "atop": r["httpsUrl"]["addr"]}


# ---------------------------------------------------------------- клиент
class Tuya:
    def __init__(self, pid, uuid, authkey, version="1.0.0", storage="tuya_state.json", log=print):
        self.pid, self.uuid, self.authkey, self.version = pid, uuid, authkey, version
        self.storage = storage
        self.log = log
        self.st = self._load()          # region, env, devId, secKey, localKey
        self.mq = None
        self.state = "wait"
        self.seq = 0
        self._retry_at = ticks_ms()
        self._backoff = 5
        self.on_dps = None              # f(dict id->value)
        self.on_connected = None        # f() — пора отправить полный снимок DP
        self.on_qrcode = None           # f(url) — показать QR привязки
        self.on_reset = None            # f() — устройство удалили из приложения

    # ---------------- хранилище
    def _load(self):
        try:
            with open(self.storage) as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}

    def _save(self):
        with open(self.storage, "w") as f:
            f.write(_dumps(self.st))

    @property
    def activated(self):
        return "devId" in self.st

    @property
    def online(self):
        return self.state == "online"

    def qr_url(self):
        return "https://smartapp.tuya.com/s/p?p=%s&uuid=%s&v=2.0" % (self.pid, self.uuid)

    # ---------------- главный шаг
    def loop(self):
        try:
            if self.state == "wait":
                if ticks_diff(ticks_ms(), self._retry_at) >= 0:
                    self._start()
            elif self.mq:
                self.mq.loop()
        except Exception as e:   # сеть, TLS, облако — всё это повод переподключиться, а не упасть
            self._fail(e)

    def _fail(self, e):
        self.log("tuya: %s: %s → повтор через %d с" % (self.state, e, self._backoff))
        if self.mq:
            self.mq.close()
            self.mq = None
        self.state = "wait"
        self._retry_at = ticks_add(ticks_ms(), self._backoff * 1000)
        self._backoff = min(300, self._backoff * 2)

    def _start(self):
        ep = endpoints(self.st.get("region"), self.st.get("env", "pro"))
        self.ep = ep
        if not self.activated:
            self.mq = MQTT(ep["mqtt"], ep["port"], "acon_" + self.uuid, "acon_" + self.uuid,
                           md5_hex(self.authkey.encode())[8:24])
            self.mq.on_message = self._on_bind_msg
            self.mq.connect()
            self.mq.subscribe("d/ai/" + self.uuid)
            self.state = "bind"
            self.log("tuya: ждём привязку, QR: " + self.qr_url())
            if self.on_qrcode:
                self.on_qrcode(self.qr_url())
        else:
            dev = self.st["devId"]
            self.mq = MQTT(ep["mqtt"], ep["port"], dev, dev, md5_hex(self.st["secKey"].encode())[8:24])
            self.mq.on_message = self._on_msg
            self.mq.connect()
            self.mq.subscribe("smart/device/in/" + dev)
            self.state = "online"
            self._backoff = 5
            self.log("tuya: онлайн, devId " + dev)
            if self.on_connected:
                self.on_connected()

    # ---------------- привязка
    def _on_bind_msg(self, topic, payload):
        _, msg = unpack(self.authkey.encode(), payload)
        if msg.get("protocol") != MQ_TOKEN:
            return
        d = msg["data"]
        self.log("tuya: токен получен, регион " + str(d.get("region")))
        self.st["region"], self.st["env"] = d.get("region"), d.get("regist", "pro")
        ep = endpoints(self.st["region"], self.st["env"])
        res = atop(ep["atop"], "tuya.device.active", "4.3", self.authkey, {
            "token": d["token"], "productKey": self.pid, "softVer": self.version,
            "protocolVer": PV.decode(), "baselineVer": "40.00", "options": '{"isFK":false}',
            "cadVer": "1.0.3", "cdVer": "1.0.0"}, uuid=self.uuid)
        for k in ("devId", "secKey", "localKey"):
            self.st[k] = res[k]
        self._save()
        self.mq.close()
        self.mq = None
        self.state = "wait"            # сразу переподключаемся уже как devId
        self._retry_at = ticks_ms()
        self._backoff = 5

    # ---------------- работа
    def _on_msg(self, topic, payload):
        seq, msg = unpack(self.st["localKey"].encode(), payload)
        self.seq = max(self.seq, seq)
        proto = msg.get("protocol")
        if proto == MQ_DPS_ON and self.on_dps:
            self.on_dps(msg.get("data", {}).get("dps", {}))
        elif proto == MQ_RESET:
            self.log("tuya: устройство удалено из приложения")
            for k in ("devId", "secKey", "localKey"):
                self.st.pop(k, None)
            self._save()
            self.mq.close()
            self.mq = None
            self.state = "wait"
            self._retry_at = ticks_ms()
            if self.on_reset:
                self.on_reset()

    def push(self, dps):
        """dps: {id: value}; bytes (raw-DP) уходят в base64. False, если не онлайн."""
        if not self.online:
            return False
        out = {}
        for k, v in dps.items():
            out[str(k)] = b64encode(v) if isinstance(v, (bytes, bytearray)) else v
        self.seq += 1
        frame = pack(self.st["localKey"].encode(), self.seq, {
            "protocol": MQ_DPS_PUSH, "t": unix_time(),
            "data": {"devId": self.st["devId"], "dps": out}})
        try:
            self.mq.publish("smart/device/out/" + self.st["devId"], frame)
        except Exception as e:
            self._fail(e)
            return False
        return True
