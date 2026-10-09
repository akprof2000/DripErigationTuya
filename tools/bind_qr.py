"""QR привязки устройства для Smart Life → PNG.

python tools/bind_qr.py [emulator/tuya.json] [bind_qr.png]
"""
import json
import sys
from pathlib import Path

import qrcode

ROOT = Path(__file__).resolve().parent.parent
creds = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "emulator" / "tuya.json"
out = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "emulator" / "bind_qr.png"

c = json.loads(creds.read_text(encoding="utf-8"))
url = "https://smartapp.tuya.com/s/p?p=%s&uuid=%s&v=2.0" % (c["pid"], c["uuid"])
qrcode.make(url, box_size=8, border=3).save(out)
print(out)
