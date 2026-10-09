"""spec.py — загрузка spec/dp.json и кодирование значений DP.

Канальные DP раскрываются в 8 штук: id = base + N, code = code_N (N = 1..8).
Значения в устройстве хранятся «по-человечески» (литры, проценты), а в облако
уходят в формате Tuya: value — целое со сдвигом scale, enum — строка,
bitmap/fault — целое, raw — bytes (транспорт сам переводит в base64).
"""
import json
import math
from dataclasses import dataclass, field
from pathlib import Path

SPEC_PATH = Path(__file__).resolve().parent.parent / "spec" / "dp.json"


@dataclass
class Dp:
    id: int
    code: str
    type: str          # bool | value | enum | string | raw | bitmap | fault
    mode: str          # ro | rw | wr
    name: str
    channel: int = 0   # 1..8 для канальных DP, 0 — глобальный
    min: int = 0
    max: int = 0
    scale: int = 0
    unit: str = ""
    range: list = field(default_factory=list)
    labels: list = field(default_factory=list)
    maxlen: int = 255
    default: object = None


class Spec:
    def __init__(self, path=SPEC_PATH):
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        self.channels = raw["product"]["channels"]
        self.enums = raw["enums"]
        self.dps = []
        for d in raw["dps"]:
            if d.get("per_channel"):
                for n in range(1, self.channels + 1):
                    self.dps.append(self._make(d, d["id"] + n, f'{d["code"]}_{n}', n))
            else:
                self.dps.append(self._make(d, d["id"], d["code"], 0))
        self.by_id = {d.id: d for d in self.dps}
        self.by_code = {d.code: d for d in self.dps}
        assert len(self.by_id) == len(self.dps), "повтор DP id в spec/dp.json"
        assert len(self.by_code) == len(self.dps), "повтор DP code в spec/dp.json"

    def _make(self, d, dp_id, code, ch):
        return Dp(id=dp_id, code=code, type=d["type"], mode=d["mode"],
                  name=d["name"] + (f" {ch}" if ch else ""), channel=ch,
                  min=d.get("min", 0), max=d.get("max", 0), scale=d.get("scale", 0),
                  unit=d.get("unit", ""), range=self.enums.get(d.get("range"), []),
                  labels=d.get("labels", []), maxlen=d.get("maxlen", 255),
                  default=d.get("default"))

    # ---------- кодирование «человеческое значение» → формат Tuya ----------
    def encode(self, code, value):
        dp = self.by_code[code]
        if dp.type == "bool":
            return bool(value)
        if dp.type == "value":
            # как lround() в прошивке: половина — от нуля (round() в Python — к чётному)
            x = value * 10 ** dp.scale
            v = int(math.copysign(math.floor(abs(x) + 0.5), x))
            return max(dp.min, min(dp.max, v))
        if dp.type == "enum":
            assert value in dp.range, f"{code}: {value!r} нет в {dp.range}"
            return value
        if dp.type in ("bitmap", "fault"):
            return int(value)
        if dp.type == "string":
            b = str(value).encode("utf-8")[: dp.maxlen]
            return b.decode("utf-8", errors="ignore")
        if dp.type == "raw":
            return bytes(value)
        raise ValueError(dp.type)

    # ---------- формат Tuya → «человеческое значение» с проверкой ----------
    def decode(self, dp_id, value):
        """Возвращает (code, значение). Бросает ValueError на мусор из облака."""
        dp = self.by_id.get(int(dp_id))
        if dp is None:
            raise ValueError(f"неизвестный DP {dp_id}")
        if dp.mode == "ro":
            raise ValueError(f"DP {dp.code} только для чтения")
        if dp.type == "bool":
            if not isinstance(value, bool):
                raise ValueError(f"{dp.code}: ожидался bool")
            return dp.code, value
        if dp.type == "value":
            if not isinstance(value, int) or not dp.min <= value <= dp.max:
                raise ValueError(f"{dp.code}: ожидалось целое {dp.min}..{dp.max}")
            return dp.code, value / 10 ** dp.scale if dp.scale else value
        if dp.type == "enum":
            if value not in dp.range:
                raise ValueError(f"{dp.code}: {value!r} нет в {dp.range}")
            return dp.code, value
        if dp.type == "string":
            if not isinstance(value, str) or len(value.encode("utf-8")) > dp.maxlen:
                raise ValueError(f"{dp.code}: строка длиннее {dp.maxlen} байт")
            return dp.code, value
        raise ValueError(f"{dp.code}: запись типа {dp.type} не поддерживается")

    def bitmap(self, code, flags):
        """Набор имён битов → целое по labels."""
        dp = self.by_code[code]
        return sum(1 << i for i, name in enumerate(dp.labels) if name in flags)
