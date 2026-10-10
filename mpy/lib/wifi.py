"""wifi.py — Wi-Fi контроллера: подключение к сохранённой сети, иначе портал.

Как SimplePortal в старой прошивке: если сети нет в /wifi.json (или зажата
кнопка при старте), поднимается точка доступа «DripIrrigation-XXXX» со
страницей, где выбирают сеть из списка (или вводят вручную) и пароль.
Страница сохраняет их и перезагружает плату. Портал — captive: свой DNS
отвечает адресом платы на любое имя, чужие пути → редирект на «/», поэтому
телефон сам предлагает «войти в сеть». Переподключение к сети —
неблокирующее, из главного цикла (tick()).
"""
import json
import socket
import time

import network

CONF = "/wifi.json"
HDR = b"HTTP/1.0 200 OK\r\nContent-Type: text/html; charset=utf-8\r\nConnection: close\r\n\r\n"
REDIR = b"HTTP/1.0 302 Found\r\nLocation: http://192.168.4.1/\r\nConnection: close\r\n\r\n"
AP_PASSWORD = "irrigation"      # пароль точки доступа настройки
AP_IP = "192.168.4.1"
RECONNECT_SEC = 20

PAGE = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Drip Irrigation — Wi-Fi</title>
<style>body{font-family:sans-serif;max-width:360px;margin:40px auto;padding:0 16px}
input,select{width:100%%;padding:10px;margin:6px 0 14px;font-size:16px;box-sizing:border-box}
button{width:100%%;padding:12px;font-size:16px;background:#1989fa;color:#fff;border:0;border-radius:8px}
a{color:#1989fa}</style></head>
<body><h2>Капельный полив</h2><p>Подключение к Wi-Fi</p>
<form method="post" action="/"><label>Сеть</label>
<select name="net" onchange="document.getElementById('s').value=this.value">
<option value="">— выбрать из списка —</option>%s</select>
<label>или ввести имя сети (SSID)</label><input id="s" name="ssid" value="%s">
<label>Пароль</label><input name="pass" type="password"><button>Сохранить</button></form>
<p><a href="/?scan=1">Обновить список сетей</a></p></body></html>"""


def load():
    try:
        with open(CONF) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def save(ssid, password):
    with open(CONF, "w") as f:
        json.dump({"ssid": ssid, "pass": password}, f)


def _esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


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
    def scan(self):
        """Список сетей рядом: [(ssid, rssi)], сильные первыми, без дублей."""
        best = {}
        try:
            for n in self.sta.scan():
                ssid = n[0].decode("utf-8", "ignore") if isinstance(n[0], bytes) else n[0]
                if ssid and best.get(ssid, -999) < n[3]:
                    best[ssid] = n[3]
        except Exception as e:
            self.log("wifi: сканирование: %r" % e)
        return sorted(best.items(), key=lambda x: -x[1])

    def _page(self, nets, current):
        opts = "".join('<option value="%s"%s>%s (%d dBm)</option>' % (
            _esc(s), " selected" if s == current else "", _esc(s), r) for s, r in nets)
        return PAGE % (opts, _esc(current))

    def portal(self, hw=None):
        """Точка доступа, DNS и HTTP-форма; возвращается после сохранения (плата перезагружается снаружи)."""
        ap = network.WLAN(network.AP_IF)
        ap.active(True)
        mac = ap.config("mac")
        ssid = "DripIrrigation-%02X%02X" % (mac[4], mac[5])
        try:
            ap.config(ssid=ssid, password=AP_PASSWORD, authmode=network.AUTH_WPA_WPA2_PSK)
        except (ValueError, TypeError):      # старые сборки: essid вместо ssid
            ap.config(essid=ssid, password=AP_PASSWORD, authmode=network.AUTH_WPA_WPA2_PSK)
        self.log("wifi: портал %s / %s, адрес http://%s" % (ssid, AP_PASSWORD, ap.ifconfig()[0]))
        nets = self.scan()
        self.log("wifi: сетей рядом: %d" % len(nets))

        srv = socket.socket()
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("0.0.0.0", 80))
        srv.listen(2)
        srv.settimeout(0.2)
        dns = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        dns.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        dns.bind(("0.0.0.0", 53))
        dns.settimeout(0)
        current = (self.conf or {}).get("ssid", "")
        blink = 0
        last_blink = time.time()
        try:
            while True:
                if hw and time.time() != last_blink:
                    last_blink = time.time()
                    blink ^= 1
                    hw.led.value(blink)
                _dns_serve(dns)
                try:
                    cl, addr = srv.accept()
                except OSError:
                    continue
                try:
                    cl.settimeout(5)
                    req = cl.recv(2048)
                    line = req.split(b"\r\n", 1)[0][:80].decode("utf-8", "ignore")
                    self.log("wifi: %s ← %s" % (addr[0], line))
                    parts = line.split(" ")
                    method, path = (parts[0], parts[1]) if len(parts) > 1 else ("", "/")
                    if method == "POST":
                        body = req.split(b"\r\n\r\n", 1)[1] if b"\r\n\r\n" in req else b""
                        form = _parse_form(body.decode("utf-8", "ignore"))
                        chosen = form.get("ssid") or form.get("net")
                        if chosen:
                            save(chosen, form.get("pass", ""))
                            cl.send(HDR + "<meta charset=utf-8><h2>Сохранено. Контроллер перезагружается…</h2>".encode())
                            cl.close()
                            return True
                        current = ""
                    if path.startswith("/?scan"):
                        nets = self.scan()
                    if path.split("?")[0] != "/":      # пробы captive-portal и всё чужое → на главную
                        cl.send(REDIR)
                    else:
                        cl.send(HDR + self._page(nets, current).encode())
                except OSError as e:
                    self.log("wifi: портал: %r" % e)
                finally:
                    try:
                        cl.close()
                    except OSError:
                        pass
        finally:
            srv.close()
            dns.close()
            ap.active(False)


def _dns_serve(dns):
    """Captive DNS: на любой запрос A — адрес платы."""
    try:
        q, addr = dns.recvfrom(512)
    except OSError:
        return
    if len(q) < 12:
        return
    try:
        # заголовок: id, флаги «ответ, рекурсия есть», 1 вопрос, 1 ответ
        resp = q[:2] + b"\x81\x80" + q[4:6] + q[4:6] + b"\x00\x00\x00\x00"
        # вопрос копируем целиком (имя до нуля + тип/класс)
        i = 12
        while i < len(q) and q[i]:
            i += q[i] + 1
        i += 5
        resp += q[12:i]
        # ответ: указатель на имя, A, IN, TTL 60, 4 байта адреса
        resp += b"\xc0\x0c\x00\x01\x00\x01\x00\x00\x00\x3c\x00\x04" + bytes(int(x) for x in AP_IP.split("."))
        dns.sendto(resp, addr)
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
