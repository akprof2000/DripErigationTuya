"""Сборка пакета прошивки .mpk для OTA через Tuya и для заливки на плату.

python tools/build_fw.py            →  firmware/dist/drip_mpy_<версия>.mpk
python tools/build_fw.py --version 1.0.1   (иначе берётся FW_VERSION из device.py)

В пакет входят mpy/lib/*.py (на плате это /app) и spec/dp.json. Формат — см.
mpy/lib/ota.py. Печатает md5 и размер: их показывает консоль Tuya при загрузке
версии прошивки (тип «Firmware Updates», UG-файл).
"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIB = ROOT / "mpy" / "lib"
OUT = ROOT / "firmware" / "dist"

sys.path.insert(0, str(LIB))


def version_from_device():
    m = re.search(r'^FW_VERSION = "([^"]+)"', (LIB / "device.py").read_text(encoding="utf-8"), re.M)
    return m.group(1)


def build(version, out_path):
    files = []
    blobs = []
    for p in sorted(LIB.glob("*.py")):
        data = p.read_bytes()
        files.append({"path": p.name, "size": len(data), "sha256": hashlib.sha256(data).hexdigest()})
        blobs.append(data)
    dp = (ROOT / "spec" / "dp.json").read_bytes()
    files.append({"path": "dp.json", "size": len(dp), "sha256": hashlib.sha256(dp).hexdigest()})
    blobs.append(dp)
    header = json.dumps({"version": version, "files": files}, separators=(",", ":"))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "wb") as f:
        f.write(b"MPK1\n")
        f.write(header.encode() + b"\n")
        for b in blobs:
            f.write(b)
    return out_path


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", default=None)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    version = a.version or version_from_device()
    out = Path(a.out) if a.out else OUT / ("drip_mpy_%s.mpk" % version)
    build(version, out)
    data = out.read_bytes()
    print(out)
    print("version", version, "size", len(data), "md5", hashlib.md5(data).hexdigest())


if __name__ == "__main__":
    main()
