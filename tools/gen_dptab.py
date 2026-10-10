"""gen_dptab.py — таблицы DP из spec/dp.json (запускать после каждой правки спецификации).

Генерирует два файла:
  mpy/lib/dptab.py           — MicroPython: замороженный модуль (кортежи во флеше),
                               на ESP32 без PSRAM разбор dp.json в ОЗУ стоил бы ~15 КБ кучи;
  firmware/esp32/include/dptab.h — C++: static const DpInfo DP_TABLE[] для include/dp.h,
                               канальные DP уже раскрыты в 8 записей (id = base + N, code_N).
Эмулятор и тесты продолжают читать spec/dp.json напрямую (spec.Spec(path)).
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "mpy" / "lib"))

from spec import ROW, row_from_json  # noqa: E402

OUT = ROOT / "mpy" / "lib" / "dptab.py"
OUT_H = ROOT / "firmware" / "esp32" / "include" / "dptab.h"

# type / mode из dp.json → перечисления C++ (include/dp.h)
C_TYPE = {"bool": "Bool", "value": "Value", "enum": "Enum", "string": "String",
          "raw": "Raw", "bitmap": "Bitmap", "fault": "Fault"}
C_MODE = {"ro": "RO", "rw": "RW", "wr": "WR"}


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def render(path=ROOT / "spec" / "dp.json"):
    raw = _load(path)
    enums = {k: tuple(v) for k, v in raw["enums"].items()}
    lines = [
        '"""dptab.py — таблица DP из spec/dp.json. Сгенерировано tools/gen_dptab.py, руками не править."""',
        "CHANNELS = %d" % raw["product"]["channels"],
        "ENUMS = %r" % (enums,),
        "# поля строки: " + ", ".join(ROW),
        "DPS = (",
    ]
    for d in raw["dps"]:
        lines.append("    %r," % (row_from_json(d),))
    lines.append(")")
    return "\n".join(lines) + "\n"


def _cstr(s):
    """Строковый литерал C: коды и имена enum — ASCII, но экранируем на всякий случай."""
    out = s.replace("\\", "\\\\").replace('"', '\\"')
    return '"%s"' % out


def render_h(path=ROOT / "spec" / "dp.json"):
    raw = _load(path)
    channels = raw["product"]["channels"]
    enums = {k: tuple(v) for k, v in raw["enums"].items()}
    lines = [
        "// dptab.h 📋 Таблица DP из spec/dp.json. Сгенерировано tools/gen_dptab.py, руками не править.",
        "// Канальные DP раскрыты: id = base + N, code = code_N, channel = N (N = 1..%d)." % channels,
        "#pragma once",
        '#include "dp.h"',
        "",
        "// Допустимые значения enum (по имени диапазона из dp.json)",
    ]
    for name, vals in enums.items():
        lines.append("static const char* const DP_ENUM_%s[] = {%s};" % (name, ", ".join(_cstr(v) for v in vals)))
    lines.append("")
    lines.append("// Имена битов bitmap/fault (по коду DP)")
    rows = [row_from_json(d) for d in raw["dps"]]
    for r in rows:
        if r[8]:
            lines.append("static const char* const DP_LABELS_%s[] = {%s};" % (r[1], ", ".join(_cstr(v) for v in r[8])))
    lines.append("")
    lines.append("// id, code, type, mode, min, max, scale, range, rangeLen, labels, labelsLen, maxlen, channel")
    lines.append("static const DpInfo DP_TABLE[] = {")
    n_rows = 0
    for r in rows:
        dp_id, code, typ, mode, mn, mx, scale, rng, labels, maxlen, per_channel, name, unit, _default = r
        if rng:
            range_c, range_n = "DP_ENUM_" + rng, len(enums[rng])
        else:
            range_c, range_n = "nullptr", 0
        if labels:
            labels_c, labels_n = "DP_LABELS_" + code, len(labels)
        else:
            labels_c, labels_n = "nullptr", 0
        chans = range(1, channels + 1) if per_channel else (0,)
        for ch in chans:
            full_code = "%s_%d" % (code, ch) if ch else code
            lines.append("  {%d, %s, DpType::%s, DpMode::%s, %d, %d, %d, %s, %d, %s, %d, %d, %d},  // %s%s" % (
                dp_id + ch, _cstr(full_code), C_TYPE[typ], C_MODE[mode], mn, mx, scale,
                range_c, range_n, labels_c, labels_n, maxlen, ch,
                name, (" %d" % ch if ch else "") + (" [%s]" % unit if unit else "")))
            n_rows += 1
    lines.append("};")
    lines.append("static const size_t DP_COUNT = sizeof(DP_TABLE) / sizeof(DP_TABLE[0]);  // %d" % n_rows)
    return "\n".join(lines) + "\n"


def _write(out, src):
    if out.exists() and out.read_text(encoding="utf-8") == src:
        print(out.name, "актуален")
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(src, encoding="utf-8", newline="\n")
    print("записан", out.relative_to(ROOT))


def main():
    _write(OUT, render())
    _write(OUT_H, render_h())


if __name__ == "__main__":
    main()
