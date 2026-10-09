"""spec.py — загрузка spec/dp.json и кодирование значений DP.

Работает и в CPython (эмулятор, тесты), и в MicroPython (ESP32): без dataclasses
и pathlib. На плате dp.json лежит в корне файловой системы.

Канальные DP раскрываются в 8 штук: id = base + N, code = code_N (N = 1..8).
Значения в устройстве хранятся «по-человечески» (литры, проценты), а в облако
уходят в формате Tuya: value — целое со сдвигом scale, enum — строка,
bitmap/fault — целое, raw — bytes (транспорт сам переводит в base64).
"""
import json
import math


def default_path():
    try:
        import os.path as p   # CPython: репозиторий, spec/dp.json
        return p.join(p.dirname(p.dirname(p.dirname(p.abspath(__file__)))), "spec", "dp.json")
    except ImportError:       # MicroPython: файл в корне платы
        return "/dp.json"


def utf8_cut(s, maxlen):
    """Обрезка строки до maxlen байт UTF-8, не разрывая символ."""
    b = str(s).encode("utf-8")
    if len(b) <= maxlen:
        return str(s)
    n = maxlen
    while n > 0 and (b[n] & 0xC0) == 0x80:   # байт-продолжение многобайтного символа
        n -= 1
    return b[:n].decode("utf-8")


class Dp:
    __slots__ = ("id", "code", "type", "mode", "name", "channel", "min", "max",
                 "scale", "unit", "range", "labels", "maxlen", "default")

    def __init__(self, d, dp_id, code, ch, enums):
        self.id = dp_id
        self.code = code
        self.type = d["type"]          # bool | value | enum | string | raw | bitmap | fault
        self.mode = d["mode"]          # ro | rw | wr
        self.name = d["name"] + (" %d" % ch if ch else "")
        self.channel = ch              # 1..8 для канальных DP, 0 — глобальный
        self.min = d.get("min", 0)
        self.max = d.get("max", 0)
        self.scale = d.get("scale", 0)
        self.unit = d.get("unit", "")
        self.range = enums.get(d.get("range"), [])
        self.labels = d.get("labels", [])
        self.maxlen = d.get("maxlen", 255)
        self.default = d.get("default")


class Spec:
    def __init__(self, path=None):
        with open(path or default_path(), encoding="utf-8") as f:
            raw = json.load(f)
        self.channels = raw["product"]["channels"]
        self.enums = raw["enums"]
        self.dps = []
        for d in raw["dps"]:
            if d.get("per_channel"):
                for n in range(1, self.channels + 1):
                    self.dps.append(Dp(d, d["id"] + n, "%s_%d" % (d["code"], n), n, self.enums))
            else:
                self.dps.append(Dp(d, d["id"], d["code"], 0, self.enums))
        self.by_id = {d.id: d for d in self.dps}
        self.by_code = {d.code: d for d in self.dps}
        assert len(self.by_id) == len(self.dps), "повтор DP id в spec/dp.json"
        assert len(self.by_code) == len(self.dps), "повтор DP code в spec/dp.json"

    # ---------- кодирование «человеческое значение» → формат Tuya ----------
    def encode(self, code, value):
        dp = self.by_code[code]
        if dp.type == "bool":
            return bool(value)
        if dp.type == "value":
            # как lround() в прошивке: половина — от нуля (round() в Python — к чётному)
            x = value * 10 ** dp.scale
            v = int(math.floor(abs(x) + 0.5))
            v = -v if x < 0 else v
            return max(dp.min, min(dp.max, v))
        if dp.type == "enum":
            assert value in dp.range, "%s: %r нет в %r" % (code, value, dp.range)
            return value
        if dp.type in ("bitmap", "fault"):
            return int(value)
        if dp.type == "string":
            return utf8_cut(value, dp.maxlen)
        if dp.type == "raw":
            return bytes(value)
        raise ValueError(dp.type)

    # ---------- формат Tuya → «человеческое значение» с проверкой ----------
    def decode(self, dp_id, value):
        """Возвращает (code, значение). Бросает ValueError на мусор из облака."""
        dp = self.by_id.get(int(dp_id))
        if dp is None:
            raise ValueError("неизвестный DP %s" % dp_id)
        if dp.mode == "ro":
            raise ValueError("DP %s только для чтения" % dp.code)
        if dp.type == "bool":
            if not isinstance(value, bool):
                raise ValueError("%s: ожидался bool" % dp.code)
            return dp.code, value
        if dp.type == "value":
            if isinstance(value, bool) or not isinstance(value, int) or not dp.min <= value <= dp.max:
                raise ValueError("%s: ожидалось целое %d..%d" % (dp.code, dp.min, dp.max))
            return dp.code, value / 10 ** dp.scale if dp.scale else value
        if dp.type == "enum":
            if value not in dp.range:
                raise ValueError("%s: %r нет в %r" % (dp.code, value, dp.range))
            return dp.code, value
        if dp.type == "string":
            if not isinstance(value, str) or len(value.encode("utf-8")) > dp.maxlen:
                raise ValueError("%s: строка длиннее %d байт" % (dp.code, dp.maxlen))
            return dp.code, value
        raise ValueError("%s: запись типа %s не поддерживается" % (dp.code, dp.type))

    def bitmap(self, code, flags):
        """Набор имён битов → целое по labels."""
        dp = self.by_code[code]
        return sum(1 << i for i, name in enumerate(dp.labels) if name in flags)
