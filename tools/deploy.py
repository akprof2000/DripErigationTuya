"""Сборка и заливка прошивки C++ (PlatformIO, firmware/esp32) и файлов на плату.

python tools/deploy.py --build                      # собрать (firmware/esp32/.pio/build/esp32dev/firmware.bin)
python tools/deploy.py --port COM8 --upload         # собрать и прошить приложение (настройки на плате остаются)
python tools/deploy.py --port COM8 --fs --creds --wifi SSID PASS [--state]
        # записать образ LittleFS: /tuya.json (лицензия из emulator/tuya.json), /wifi.json,
        # --state: /tuya_state.json из emulator/tuya_storage.json (та же привязка, что у эмулятора).
        # ⚠️ образ заменяет всю LittleFS: без SD-карты пропадут /state.json и очередь отчётов.
python tools/deploy.py --port COM8 --monitor        # консоль платы (115200)

Плата без схемы автопрограммирования: перед --upload/--fs зажать BOOT и нажать EN.
Образ приложения для OTA в консоли Tuya: firmware/dist/drip_<версия>.bin (копируется при --build).
"""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PIO_DIR = ROOT / "firmware" / "esp32"
DATA = PIO_DIR / "data"
DIST = ROOT / "firmware" / "dist"


def version():
    m = re.search(r'FW_VERSION=\\"([^"\\]+)\\"', (PIO_DIR / "platformio.ini").read_text(encoding="utf-8"))
    if m:
        return m.group(1)
    m = re.search(r'#define FW_VERSION "([^"]+)"', (PIO_DIR / "include" / "device.h").read_text(encoding="utf-8"))
    return m.group(1)


def pio(*args, check=True):
    cmd = [sys.executable, "-m", "platformio", *args, "-d", str(PIO_DIR)]
    print("$", " ".join(cmd[3:]))
    return subprocess.run(cmd, check=check)


def build():
    pio("run")
    src = PIO_DIR / ".pio" / "build" / "esp32dev" / "firmware.bin"
    DIST.mkdir(parents=True, exist_ok=True)
    dst = DIST / ("drip_%s.bin" % version())
    shutil.copy(src, dst)
    data = dst.read_bytes()
    print("%s  %d байт  md5 %s" % (dst.relative_to(ROOT), len(data), hashlib.md5(data).hexdigest()))


def prepare_fs(a):
    shutil.rmtree(DATA, ignore_errors=True)
    DATA.mkdir(parents=True)
    if a.creds:
        shutil.copy(ROOT / "emulator" / "tuya.json", DATA / "tuya.json")
    if a.wifi:
        (DATA / "wifi.json").write_text(json.dumps({"ssid": a.wifi[0], "pass": a.wifi[1]}), encoding="utf-8")
    if a.wifi_file:
        shutil.copy(a.wifi_file, DATA / "wifi.json")
    if a.state:
        shutil.copy(ROOT / "emulator" / "tuya_storage.json", DATA / "tuya_state.json")
    print("файлы для LittleFS:", ", ".join(p.name for p in DATA.iterdir()) or "—")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", help="COM-порт платы, например COM8")
    ap.add_argument("--build", action="store_true", help="собрать прошивку")
    ap.add_argument("--upload", action="store_true", help="собрать и прошить приложение")
    ap.add_argument("--fs", action="store_true", help="записать образ LittleFS из --creds/--wifi/--state")
    ap.add_argument("--creds", action="store_true", help="в образ: emulator/tuya.json → /tuya.json")
    ap.add_argument("--wifi", nargs=2, metavar=("SSID", "PASS"), help="в образ: /wifi.json")
    ap.add_argument("--wifi-file", metavar="PATH", help="в образ: готовый wifi.json")
    ap.add_argument("--state", action="store_true", help="в образ: emulator/tuya_storage.json → /tuya_state.json")
    ap.add_argument("--monitor", action="store_true", help="открыть консоль платы")
    a = ap.parse_args()
    if (a.upload or a.fs or a.monitor) and not a.port:
        sys.exit("нужен --port")
    if a.build or a.upload:
        build()
    if a.upload:
        pio("run", "-t", "upload", "--upload-port", a.port)
    if a.fs:
        prepare_fs(a)
        pio("run", "-t", "uploadfs", "--upload-port", a.port)
        shutil.rmtree(DATA, ignore_errors=True)   # секреты не держим на диске дольше необходимого
    if a.monitor:
        pio("device", "monitor", "-p", a.port, "-b", "115200", check=False)


if __name__ == "__main__":
    main()
