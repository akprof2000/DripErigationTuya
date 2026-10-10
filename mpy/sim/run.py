"""Прогон прошивки в unix-порте MicroPython: python-часть без платы и без облака.

micropython mpy/sim/run.py [секунд]
Корень «флеша» — /tmp/drip-sim: туда кладутся app/dp.json, wifi.json, state.json.
"""
import os
import sys

ROOT = "/tmp/drip-sim"
sys.path.insert(0, "mpy/sim")
sys.path.insert(0, "mpy/lib")

for d in (ROOT, ROOT + "/app", ROOT + "/ota"):
    try:
        os.mkdir(d)
    except OSError:
        pass
with open("spec/dp.json", "rb") as src, open(ROOT + "/app/dp.json", "wb") as dst:
    dst.write(src.read())
with open(ROOT + "/wifi.json", "w") as f:
    f.write('{"ssid": "HomeNet", "pass": "x"}')
# лицензия ненастоящая: облако недоступно (в unix-порте нет TLS), но клиент создаётся,
# пробует подключиться, получает ошибку и копит отчёты в очередь — это и проверяем
with open(ROOT + "/tuya.json", "w") as f:
    f.write('{"pid": "0uo7msdnt2yn1lgp", "uuid": "uuid0000000000000000", "authkey": "key00000000000000000000000000000"}')

import wifi
wifi.CONF = ROOT + "/wifi.json"
import ota
ota.OTA_DIR, ota.PKG, ota.APPLY, ota.NEW_DIR = ROOT + "/ota", ROOT + "/ota/fw.mpk", ROOT + "/ota/apply.json", ROOT + "/app_new"
import app
app.ROOT = ROOT
app.MAX_TICKS = int(sys.argv[1]) if len(sys.argv) > 1 else 5

app.run()
print("sim: главный цикл отработал", app.MAX_TICKS, "тиков")
try:
    with open(ROOT + "/pending.jsonl") as f:
        lines = [ln for ln in f if ln.strip()]
except OSError:
    lines = []
print("sim: в очереди", len(lines), "отчётов; первый:", lines[0][:120] if lines else "-")
print("sim: ок")
