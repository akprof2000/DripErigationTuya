"""Заливка на плату: прошивка целиком (esptool) и файлы настроек (mpremote).

python tools/deploy.py --port COM5 --flash                 # стереть флеш и прошить firmware/dist/drip_<ver>_full.bin
python tools/deploy.py --port COM5 --app                   # перешить только приложение (раздел ota_0), файлы на плате остаются
python tools/deploy.py --port COM5 --creds                 # emulator/tuya.json → /tuya.json (лицензия TuyaOpen)
python tools/deploy.py --port COM5 --wifi SSID PASS        # записать /wifi.json
python tools/deploy.py --port COM5 --dev                   # mpy/lib/*.py → /app (перекрывают замороженные; отладка)
python tools/deploy.py --port COM5 --clean                 # удалить /app — снова работают замороженные модули
python tools/deploy.py --port COM5 --repl                  # в конце открыть консоль платы

Код прошивки заморожен в образе (tools/build_fw.py); --dev нужен только чтобы
попробовать правку без пересборки — в ОЗУ такие модули стоят дорого.
"""
import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def version():
    m = re.search(r'^FW_VERSION\s*=\s*"([^"]+)"', (ROOT / "mpy" / "lib" / "device.py").read_text(encoding="utf-8"), re.M)
    return m.group(1)


def mp(port, *args, check=True):
    cmd = [sys.executable, "-m", "mpremote", "connect", port, *args]
    print("$", " ".join(cmd[3:]))
    return subprocess.run(cmd, check=check)


def flash(port, app_only=False):
    """Полный образ (со стиранием) или только приложение в ota_0 (+ сброс otadata, чтобы грузился именно он)."""
    dist = ROOT / "firmware" / "dist"
    img = dist / ("drip_%s%s.bin" % (version(), "" if app_only else "_full"))
    if not img.exists():
        sys.exit("нет %s — сначала python tools/build_fw.py" % img)
    base = [sys.executable, "-m", "esptool", "--chip", "esp32", "--port", port]
    if app_only:
        args = ["0x10000", str(img)]
        otadata = dist / "ota_data_initial.bin"
        if otadata.exists():
            args += ["0xd000", str(otadata)]
    else:
        subprocess.run(base + ["erase_flash"], check=True)
        args = ["0x1000", str(img)]
    subprocess.run(base + ["--baud", "460800", "write_flash", "-z", *args], check=True)
    print("прошито:", img.name)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", required=True, help="COM-порт платы, например COM5")
    ap.add_argument("--flash", action="store_true", help="стереть флеш и прошить полный образ")
    ap.add_argument("--app", action="store_true", help="перешить только приложение (ota_0), файлы остаются")
    ap.add_argument("--creds", action="store_true", help="залить emulator/tuya.json как /tuya.json")
    ap.add_argument("--wifi", nargs=2, metavar=("SSID", "PASS"), help="сразу записать /wifi.json")
    ap.add_argument("--dev", action="store_true", help="mpy/lib/*.py → /app (отладка без пересборки)")
    ap.add_argument("--clean", action="store_true", help="удалить /app")
    ap.add_argument("--repl", action="store_true", help="открыть консоль после заливки")
    a = ap.parse_args()

    if a.flash:
        flash(a.port)
    elif a.app:
        flash(a.port, app_only=True)
    if a.clean:
        mp(a.port, "rm", "-r", ":app", check=False)
    if a.dev:
        mp(a.port, "mkdir", ":app", check=False)
        files = [str(p) for p in sorted((ROOT / "mpy" / "lib").glob("*.py"))]
        mp(a.port, "cp", *files, ":app/")
    if a.creds:
        mp(a.port, "cp", str(ROOT / "emulator" / "tuya.json"), ":tuya.json")
    if a.wifi:
        tmp = Path(tempfile.mkdtemp()) / "wifi.json"
        tmp.write_text(json.dumps({"ssid": a.wifi[0], "pass": a.wifi[1]}), encoding="utf-8")
        mp(a.port, "cp", str(tmp), ":wifi.json")
    if a.clean or a.dev or a.creds or a.wifi:
        mp(a.port, "reset", check=False)
        print("готово: плата перезагружена")
    if a.repl:
        mp(a.port, "repl", check=False)


if __name__ == "__main__":
    main()
