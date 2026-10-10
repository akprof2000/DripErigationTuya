"""Заглушка network: Wi-Fi «подключается» через 2 секунды после connect()."""
import time

STA_IF, AP_IF = 0, 1
AUTH_WPA_WPA2_PSK = 3


class WLAN:
    _since = None

    def __init__(self, kind):
        self.kind = kind

    def active(self, on=None):
        return True

    def connect(self, ssid, password):
        WLAN._since = time.time()

    def isconnected(self):
        return WLAN._since is not None and time.time() - WLAN._since >= 2

    def ifconfig(self):
        return ("192.168.1.50", "255.255.255.0", "192.168.1.1", "8.8.8.8")

    def status(self, what=None):
        return -55

    def config(self, *a, **k):
        if a and a[0] == "mac":
            return b"\x24\x6f\x28\xab\xcd\xef"

    def scan(self):
        return [(b"HomeNet", b"", 1, -50, 3, False)]
