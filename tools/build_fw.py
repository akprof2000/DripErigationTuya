"""Сборка прошивки контроллера: образ MicroPython с замороженным mpy/lib (в WSL Ubuntu).

python tools/build_fw.py
  → firmware/dist/drip_<версия>.bin       образ приложения — его грузят в консоль Tuya как версию прошивки (OTA)
  → firmware/dist/drip_<версия>_full.bin  полный образ (загрузчик + таблица разделов + приложение) для esptool

Версия берётся из mpy/lib/device.py (FW_VERSION). Перед сборкой обновляется mpy/lib/dptab.py.
Как настроить WSL — docs/firmware.md, раздел «Сборка прошивки».
"""
import hashlib
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "firmware" / "dist"
DISTRO = "Ubuntu"


def version():
    m = re.search(r'^FW_VERSION\s*=\s*"([^"]+)"', (ROOT / "mpy" / "lib" / "device.py").read_text(encoding="utf-8"), re.M)
    return m.group(1)


def wsl_path(p):
    p = Path(p).resolve()
    return "/mnt/%s%s" % (p.drive[0].lower(), p.as_posix()[2:])


def main():
    subprocess.run([sys.executable, str(ROOT / "tools" / "gen_dptab.py")], check=True)
    ver = version()
    print("сборка прошивки", ver)
    script = wsl_path(ROOT / "firmware" / "mpy-board" / "build.sh")
    r = subprocess.run(["wsl", "-d", DISTRO, "bash", script], capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = r.stdout + r.stderr
    print("\n".join(ln for ln in out.splitlines() if "localhost" not in ln and ln.strip()))
    if r.returncode != 0:
        sys.exit("сборка не удалась")
    build_dir = re.search(r"BUILD_DIR=(\S+)", out).group(1)
    DIST.mkdir(parents=True, exist_ok=True)
    for src, dst in (("micropython.bin", "drip_%s.bin" % ver), ("firmware.bin", "drip_%s_full.bin" % ver),
                     ("ota_data_initial.bin", "ota_data_initial.bin")):
        target = DIST / dst
        subprocess.run(["wsl", "-d", DISTRO, "cp", "%s/%s" % (build_dir, src), wsl_path(target)], check=True)
        data = target.read_bytes()
        print("%-28s %8d байт  md5 %s" % (target.relative_to(ROOT), len(data), hashlib.md5(data).hexdigest()))
    print("OTA-образ в консоль Tuya: firmware/dist/drip_%s.bin" % ver)


if __name__ == "__main__":
    main()
