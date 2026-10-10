"""wifi.py — Wi-Fi контроллера: подключение к сохранённой сети, иначе портал.

Как SimplePortal в старой прошивке: если сети нет в /wifi.json (или зажата
кнопка при старте), поднимается точка доступа «DripIrrigation-XXXX» со
страницей, где вводят SSID и пароль. Страница сохраняет их и перезагружает
плату. Переподключение к сети — неблокирующее, из главного цикла (tick()).
"""
import json
import socket
import time

import network

CONF = "/wifi.json"
HDR = b"HTTP/1.0 200 OK\r\nContent-Type: text/html; charset=utf-8\r\n\r\n"
AP_PASSWORD = "irrigation"      # пароль точки доступа настройки
RECONNECT_SEC = 20

PAGE = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Drip Irrigation — Wi-Fi</title>
<style>body{font-family:sans-serif;max-width:360px;margin:40px auto;padding:0 16px}
input{width:100%%;padding:10px;margin:6px 0 14px;font-size:16px;box-sizing:border-box}
button{width:100%%;padding:12px;font-size:16px;background:#1989fa;color:#fff;border:0;border-radius:8px}</style></head>
<body><h2>Капельный полив</h2><p>Подключение к Wi-Fi</p>
<form method="post"><label>Сеть (SSID)</label><input name="ssid" value="%s" required>
<label>Пароль</label><input name="pass" type="password"><button>Сохранить</button></form>
<p style="color:#888">Сети рядом: %s</p></body></html>"""


def load():
    try:
        with open(CONF) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def save(ssid, password):
    with open(CONF, "w") as f:
        json.dump({"ssid": ssid, "pass": password}, f)


class Wifi:
    def __init__(self, log=print):
        self.log = log
        self.sta = network.WLAN(network.STA_IF)
        self.sta.active(True)
        self.conf = load()
        self._tried_at = None
        self._was_up = False

    def connect(self):
        if not self.conf:
            return False
        self.log("wifi: подключение к %s" % self.conf["ssid"])
        self.sta.connect(self.conf["ssid"], self.conf.get("pass", ""))
        self._tried_at = time.time()
        return True

    def tick(self):
        """Вызывать из главного цикла. Возвращает True, если сеть есть."""
        up = self.sta.isconnected()
        if up != self._was_up:
            self._was_up = up
            self.log("wifi: %s" % ("подключено, IP " + self.sta.ifconfig()[0] if up else "потеряно"))
        if not up and self.conf and (self._tried_at is None or time.time() - self._tried_at > RECONNECT_SEC):
            self.connect()
        return up

    def rssi(self):
        try:
            return self.sta.status("rssi") if self.sta.isconnected() else 0
        except Exception:
            return 0

    # ---------------- портал настройки
    def portal(self, hw=None):
        """Точка доступа и HTTP-форма; возвращается после сохранения (плата перезагружается снаружи)."""
        ap = network.WLAN(network.AP_IF)
        ap.active(True)
        mac = ap.config("mac")
        ssid = "DripIrrigation-%02X%02X" % (mac[4], mac[5])
        ap.config(essid=ssid, password=AP_PASSWORD, authmode=network.AUTH_WPA_WPA2_PSK)
        self.log("wifi: портал %s / %s, адрес http://%s" % (ssid, AP_PASSWORD, ap.ifconfig()[0]))
        try:
            nets = sorted({n[0].decode() for n in self.sta.scan() if n[0]})
        except Exception:
            nets = []
        srv = socket.socket()
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("0.0.0.0", 80))
        srv.listen(2)
        srv.settimeout(1)
        current = (self.conf or {}).get("ssid", "")
        blink = 0
        while True:
            if hw:
                blink ^= 1
                hw.led.value(blink)
            try:
                cl, _ = srv.accept()
            except OSError:
                continue
            try:
                cl.settimeout(5)
                req = cl.recv(2048)
                if req.startswith(b"POST"):
                    body = req.split(b"\r\n\r\n", 1)[1] if b"\r\n\r\n" in req else b""
                    form = _parse_form(body.decode())
                    if form.get("ssid"):
                        save(form["ssid"], form.get("pass", ""))
                        cl.send(HDR + "<meta charset=utf-8><h2>Сохранено. Контроллер перезагружается…</h2>".encode())
                        cl.close()
                        srv.close()
                        ap.active(False)
                        return True
                html = PAGE % (current, ", ".join(nets) or "—")
                cl.send(HDR + html.encode())
            except OSError:
                pass
            finally:
                try:
                    cl.close()
                except OSError:
                    pass


def _unquote(s):
    s = s.replace("+", " ")
    out = bytearray()
    i = 0
    while i < len(s):
        if s[i] == "%" and i + 2 < len(s):
            out.append(int(s[i + 1:i + 3], 16))
            i += 3
        else:
            out.extend(s[i].encode())
            i += 1
    return out.decode()


def _parse_form(body):
    form = {}
    for pair in body.split("&"):
        if "=" in pair:
            k, v = pair.split("=", 1)
            form[_unquote(k)] = _unquote(v)
    return form
