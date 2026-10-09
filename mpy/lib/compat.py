"""compat.py — то, что в CPython и MicroPython называется по-разному.

Tuya-клиенту нужны AES-128-ECB, MD5, CRC32, base64, HTTPS POST и TLS-сокет.
В MicroPython (ESP32) это cryptolib, hashlib (md5 есть при включённом SSL),
binascii, requests и ssl.SSLContext; в CPython — pycryptodome (если есть) или
встроенная реализация AES ниже, urllib и ssl.
"""
import binascii
import hashlib
import json
import socket
import ssl
import time

try:
    from cryptolib import aes as _mp_aes   # MicroPython
except ImportError:
    _mp_aes = None

MICROPYTHON = _mp_aes is not None


# ------------------------------------------------------------------ AES-ECB
def _pad(data):
    n = 16 - len(data) % 16
    return data + bytes([n]) * n


def _unpad(data):
    n = data[-1]
    if not 1 <= n <= 16 or data[-n:] != bytes([n]) * n:
        raise ValueError("bad padding")
    return data[:-n]


if MICROPYTHON:
    def aes_encrypt(key, data):
        return _mp_aes(key[:16], 1).encrypt(_pad(data))   # 1 = MODE_ECB

    def aes_decrypt(key, data):
        return _unpad(_mp_aes(key[:16], 1).decrypt(data))
else:
    from Crypto.Cipher import AES   # pycryptodome — уже стоит в .venv эмулятора

    def aes_encrypt(key, data):
        return AES.new(key[:16], AES.MODE_ECB).encrypt(_pad(data))

    def aes_decrypt(key, data):
        return _unpad(AES.new(key[:16], AES.MODE_ECB).decrypt(data))


# ------------------------------------------------------------------ хеши, base64
def md5_hex(data):
    return binascii.hexlify(hashlib.md5(data).digest()).decode()


try:
    crc32 = binascii.crc32
except AttributeError:   # сборка MicroPython без crc32
    def crc32(data, crc=0):
        crc ^= 0xFFFFFFFF
        for b in data:
            crc ^= b
            for _ in range(8):
                crc = (crc >> 1) ^ (0xEDB88320 & -(crc & 1))
        return crc ^ 0xFFFFFFFF


def b64encode(data):
    return binascii.b2a_base64(data).strip().decode()


def b64decode(text):
    return binascii.a2b_base64(text)


# ------------------------------------------------------------------ время
_EPOCH_SHIFT = 946684800 if time.gmtime(0)[0] == 2000 else 0   # старые порты: эпоха 2000 г.


def unix_time():
    return int(time.time()) + _EPOCH_SHIFT


def ticks_ms():
    try:
        return time.ticks_ms()
    except AttributeError:
        return int(time.monotonic() * 1000)


def ticks_add(t, ms):
    try:
        return time.ticks_add(t, ms)
    except AttributeError:
        return t + ms


def ticks_diff(a, b):
    try:
        return time.ticks_diff(a, b)
    except AttributeError:
        return a - b


# ------------------------------------------------------------------ HTTPS
def http_post(url, body, headers):
    """POST → разобранный JSON-ответ."""
    if MICROPYTHON:
        import requests
        r = requests.post(url, data=body, headers=headers)
        try:
            return r.json()
        finally:
            r.close()
    import urllib.request
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode("utf-8"))


# ------------------------------------------------------------------ TLS-сокет
class Conn:
    """TLS-соединение с одинаковым API: write(bytes), read(n) → bytes | None (нет данных)."""

    def __init__(self, host, port, timeout=15):
        addr = socket.getaddrinfo(host, port, 0, socket.SOCK_STREAM)[0][-1]
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect(addr)
        if MICROPYTHON:
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            ctx.verify_mode = ssl.CERT_NONE   # TODO: CA Tuya во флеш, когда хватит памяти
            self.s = ctx.wrap_socket(s, server_hostname=host)
        else:
            self.s = ssl.create_default_context().wrap_socket(s, server_hostname=host)
        self.s.settimeout(timeout)

    def write(self, data):
        if MICROPYTHON:
            mv = memoryview(data)
            while mv:
                n = self.s.write(mv)
                mv = mv[n:]
        else:
            self.s.sendall(data)

    def read_exact(self, n):
        buf = b""
        while len(buf) < n:
            chunk = self.s.read(n - len(buf)) if MICROPYTHON else self.s.recv(n - len(buf))
            if not chunk:
                raise OSError("соединение закрыто")
            buf += chunk
        return buf

    def poll_byte(self, timeout):
        """Первый байт пакета, если он пришёл за timeout секунд; иначе None."""
        self.s.settimeout(timeout)
        try:
            b = self.s.read(1) if MICROPYTHON else self.s.recv(1)
        except OSError as e:   # socket.timeout — подкласс OSError; в MicroPython ETIMEDOUT/EAGAIN
            if _is_timeout(e):
                return None
            raise
        finally:
            self.s.settimeout(15)
        if not b:
            if MICROPYTHON and b is None:
                return None
            raise OSError("соединение закрыто")
        return b[0]

    def close(self):
        try:
            self.s.close()
        except OSError:
            pass


def _is_timeout(e):
    if isinstance(e, getattr(socket, "timeout", ())):
        return True
    code = e.args[0] if e.args else None
    return code in (11, 110, 116, "timed out")   # EAGAIN, ETIMEDOUT (lwIP 116)
