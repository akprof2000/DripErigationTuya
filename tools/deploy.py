"""Заливка прошивки на плату через mpremote (pip install mpremote).

python tools/deploy.py --port COM5              # boot.py, main.py, /app/*, dp.json
python tools/deploy.py --port COM5 --creds      # + emulator/tuya.json → /tuya.json (лицензия)
python tools/deploy.py --port COM5 --wifi SSID PASS
python tools/deploy.py --port COM5 --repl       # после заливки открыть консоль платы

MicroPython на плате уже должен стоять (docs/firmware.md, раздел «Первая заливка»).
"""
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def mp(port, *args, check=True):
    cmd = [sys.executable, "-m", "mpremote", "connect", port, *args]
    print("$", " ".join(cmd[3:]))
    return subprocess.run(cmd, check=check)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", required=True, help="COM-порт платы, например COM5")
    ap.add_argument("--creds", action="store_true", help="залить emulator/tuya.json как /tuya.json")
    ap.add_argument("--wifi", nargs=2, metavar=("SSID", "PASS"), help="сразу записать /wifi.json")
    ap.add_argument("--repl", action="store_true", help="открыть консоль после заливки")
    a = ap.parse_args()

    mp(a.port, "cp", str(ROOT / "mpy" / "boot.py"), str(ROOT / "mpy" / "main.py"), ":")
    mp(a.port, "mkdir", ":app", check=False)
    files = [str(p) for p in sorted((ROOT / "mpy" / "lib").glob("*.py"))]
    mp(a.port, "cp", *files, ":app/")
    mp(a.port, "cp", str(ROOT / "spec" / "dp.json"), ":app/dp.json")
    if a.creds:
        mp(a.port, "cp", str(ROOT / "emulator" / "tuya.json"), ":tuya.json")
    if a.wifi:
        tmp = Path(tempfile.mkdtemp()) / "wifi.json"
        tmp.write_text(json.dumps({"ssid": a.wifi[0], "pass": a.wifi[1]}), encoding="utf-8")
        mp(a.port, "cp", str(tmp), ":wifi.json")
    mp(a.port, "reset", check=False)
    print("готово: плата перезагружена")
    if a.repl:
        mp(a.port, "repl", check=False)


if __name__ == "__main__":
    main()
