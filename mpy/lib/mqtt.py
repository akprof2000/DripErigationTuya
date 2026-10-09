"""mqtt.py — минимальный клиент MQTT 3.1.1 поверх compat.Conn (TLS).

Ровно то, что нужно Tuya: CONNECT с логином, SUBSCRIBE QoS 1, PUBLISH QoS 1
(PUBACK не ждём — облако подтверждает DP своим ответом), приём PUBLISH с
ответным PUBACK, PINGREQ по keepalive. Один поток, без блокировок дольше
timeout: loop() вызывается из главного цикла программы.
"""
import struct

from compat import Conn, ticks_ms, ticks_diff

CONNECT, CONNACK, PUBLISH, PUBACK, SUBSCRIBE, SUBACK, PINGREQ, PINGRESP, DISCONNECT = (
    1, 2, 3, 4, 8, 9, 12, 13, 14)


def _str(s):
    b = s.encode() if isinstance(s, str) else s
    return struct.pack("!H", len(b)) + b


def _remaining_len(n):
    out = bytearray()
    while True:
        b = n % 128
        n //= 128
        out.append(b | 0x80 if n else b)
        if not n:
            return bytes(out)


class MQTTError(OSError):
    pass


class MQTT:
    def __init__(self, host, port, client_id, user, password, keepalive=60):
        self.host, self.port = host, port
        self.client_id, self.user, self.password = client_id, user, password
        self.keepalive = keepalive
        self.conn = None
        self.pid = 0
        self.on_message = None      # f(topic: str, payload: bytes)
        self._last_tx = 0
        self._ping_sent = None

    # ---------------------------------------------------------------- пакеты
    def _send(self, ptype, flags, body):
        self.conn.write(bytes([(ptype << 4) | flags]) + _remaining_len(len(body)) + body)
        self._last_tx = ticks_ms()

    def _recv(self, first):
        n, mult = 0, 1
        while True:
            b = self.conn.read_exact(1)[0]
            n += (b & 0x7F) * mult
            mult *= 128
            if not b & 0x80:
                break
        return first >> 4, first & 0x0F, self.conn.read_exact(n) if n else b""

    def _next_pid(self):
        self.pid = self.pid % 65535 + 1
        return self.pid

    # ---------------------------------------------------------------- API
    def connect(self):
        self.close()
        self.conn = Conn(self.host, self.port)
        body = _str("MQTT") + bytes([4, 0xC2]) + struct.pack("!H", self.keepalive)  # 0xC2: user+pass, clean
        body += _str(self.client_id) + _str(self.user) + _str(self.password)
        self._send(CONNECT, 0, body)
        first = self.conn.poll_byte(15)
        if first is None:
            raise MQTTError("нет CONNACK")
        ptype, _, data = self._recv(first)
        if ptype != CONNACK or len(data) < 2 or data[1] != 0:
            raise MQTTError("CONNACK отказ: %r" % (data,))
        self._ping_sent = None

    def subscribe(self, topic, qos=1):
        self._send(SUBSCRIBE, 2, struct.pack("!H", self._next_pid()) + _str(topic) + bytes([qos]))

    def publish(self, topic, payload, qos=1):
        body = _str(topic)
        if qos:
            body += struct.pack("!H", self._next_pid())
        self._send(PUBLISH, qos << 1, body + payload)

    def loop(self, timeout=0.05):
        """Обработать один входящий пакет (если есть) и поддержать keepalive."""
        now = ticks_ms()
        if self._ping_sent is not None and ticks_diff(now, self._ping_sent) > self.keepalive * 1000:
            raise MQTTError("нет PINGRESP")
        if ticks_diff(now, self._last_tx) > self.keepalive * 500 and self._ping_sent is None:
            self._send(PINGREQ, 0, b"")
            self._ping_sent = now
        first = self.conn.poll_byte(timeout)
        if first is None:
            return False
        ptype, flags, data = self._recv(first)
        if ptype == PUBLISH:
            tlen = struct.unpack("!H", data[:2])[0]
            topic = data[2:2 + tlen].decode()
            pos = 2 + tlen
            if (flags >> 1) & 3:
                pid = data[pos:pos + 2]
                pos += 2
                self._send(PUBACK, 0, pid)
            if self.on_message:
                self.on_message(topic, data[pos:])
        elif ptype == PINGRESP:
            self._ping_sent = None
        return True

    def close(self):
        if self.conn:
            try:
                self._send(DISCONNECT, 0, b"")
            except OSError:
                pass
            self.conn.close()
            self.conn = None
