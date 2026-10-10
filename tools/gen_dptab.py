"""gen_dptab.py — mpy/lib/dptab.py из spec/dp.json (запускать после каждой правки спецификации).

На плате описание DP лежит в замороженном модуле (кортежи во флеше), а не
разбирается из dp.json в ОЗУ: на ESP32 без PSRAM это ~15 КБ кучи.
Эмулятор и тесты продолжают читать spec/dp.json напрямую (spec.Spec(path)).
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "mpy" / "lib"))

from spec import ROW, row_from_json  # noqa: E402

OUT = ROOT / "mpy" / "lib" / "dptab.py"


def render(path=ROOT / "spec" / "dp.json"):
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
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


def main():
    src = render()
    if OUT.exists() and OUT.read_text(encoding="utf-8") == src:
        print("dptab.py актуален")
        return
    OUT.write_text(src, encoding="utf-8", newline="\n")
    print("записан", OUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
