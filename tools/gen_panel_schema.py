"""gen_panel_schema.py — panel/src/devices/schema.ts из spec/dp.json.

Формат совпадает со схемой DP, которую Tuya отдаёт панели (getDpSchema), так что
SmartDeviceModel получает точные типы для useProps/useActions. Запускать после
каждой правки спецификации.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "emulator"))
from spec import Spec  # noqa: E402


def prop(d):
    if d.type == "bool":
        return {"type": "bool"}
    if d.type == "value":
        return {"type": "value", "min": d.min, "max": d.max, "scale": d.scale, "step": 1, "unit": d.unit}
    if d.type == "enum":
        return {"type": "enum", "range": d.range}
    if d.type == "string":
        return {"type": "string", "maxlen": d.maxlen}
    if d.type == "raw":
        return {"type": "raw", "maxlen": 128}
    if d.type in ("bitmap", "fault"):
        return {"type": "bitmap", "label": d.labels, "maxlen": len(d.labels)}
    raise ValueError(d.type)


def main():
    s = Spec()
    items = [{"attr": 0, "canTrigger": d.mode != "wr", "code": d.code, "defaultRecommend": False,
              "editPermission": False, "executable": d.mode != "ro", "extContent": "", "iconname": "",
              "id": d.id, "mode": d.mode, "name": d.code, "property": prop(d), "type": "obj"}
             for d in s.dps]
    out = ROOT / "panel" / "src" / "devices" / "schema.ts"
    out.write_text(
        "// Сгенерировано tools/gen_panel_schema.py из spec/dp.json. Руками не править.\n"
        f"export const defaultSchema = {json.dumps(items, ensure_ascii=False, indent=2)} as const;\n",
        encoding="utf-8")
    print(f"{out}: {len(items)} DP")


if __name__ == "__main__":
    main()
