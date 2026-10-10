"""outbox.py — очередь отчётов DP на время без связи.

Контроллер работает автономно: полив идёт по датчикам, а всё, что должно уйти
в облако (влажность, события, расход), складывается сюда с меткой времени.
Когда связь появляется, записи отправляются по порядку с полем t — облако
кладёт их в журнал задним числом, и графики за время офлайна не теряются.
После успешной отправки файл очищается.

Хранилище — файл JSON Lines (одна запись на строку): на ESP32 это SD-карта или
флеш, в эмуляторе — файл рядом. Больше MAX_BYTES не копим: при переполнении
теряем самые старые записи (новые важнее для графиков «что сейчас»).
"""
import json
import os

MAX_BYTES = 512 * 1024       # ~ неделя отчётов раз в минуту по 8 каналам
TRIM_TO = MAX_BYTES // 2


def _dumps(obj):
    try:
        return json.dumps(obj, separators=(",", ":"))
    except TypeError:
        return json.dumps(obj)


def _size(path):
    try:
        return os.stat(path)[6]
    except OSError:
        return 0


class Outbox:
    def __init__(self, path):
        self.path = path
        self.count = self._count()

    def _count(self):
        n = 0
        try:
            with open(self.path) as f:
                for line in f:
                    if line.strip():
                        n += 1
        except OSError:
            pass
        return n

    def put(self, dps, t):
        """dps: {id: value} (bytes — в hex, чтобы влезло в JSON), t — unix."""
        rec = {"t": int(t), "dps": {}}
        for k, v in dps.items():
            if isinstance(v, (bytes, bytearray)):
                rec["dps"][str(k)] = {"hex": _hex(v)}
            else:
                rec["dps"][str(k)] = v
        if _size(self.path) > MAX_BYTES:
            self._trim()
        with open(self.path, "a") as f:
            f.write(_dumps(rec) + "\n")
        self.count += 1

    def flush(self, push, now=None, fresh_sec=60):
        """push(dps, t) → bool. Отправляет записи по порядку; при первом отказе
        останавливается, неотправленное остаётся. Возвращает число отправленных.

        Свежие записи (моложе fresh_sec относительно now) уходят без метки
        времени — облако само ставит точное время приёма; метка нужна только
        тому, что пролежало в очереди."""
        sent = 0
        rest = []
        try:
            with open(self.path) as f:
                lines = [ln for ln in f if ln.strip()]
        except OSError:
            return 0
        failed = False
        for ln in lines:
            if failed:
                rest.append(ln)
                continue
            try:
                rec = json.loads(ln)
                dps = {}
                for k, v in rec["dps"].items():
                    dps[k] = _unhex(v["hex"]) if isinstance(v, dict) and "hex" in v else v
                t = rec["t"]
                if now is not None and now - t < fresh_sec:
                    t = None
                ok = push(dps, t)
            except (ValueError, KeyError, TypeError):
                ok = True          # битая строка — выбрасываем
            if ok:
                sent += 1
            else:
                failed = True
                rest.append(ln)
        self._rewrite(rest)
        self.count = len(rest)
        return sent

    def _trim(self):
        try:
            with open(self.path) as f:
                lines = [ln for ln in f if ln.strip()]
        except OSError:
            return
        total = sum(len(ln) for ln in lines)
        while lines and total > TRIM_TO:
            total -= len(lines.pop(0))
        self._rewrite(lines)
        self.count = len(lines)

    def _rewrite(self, lines):
        tmp = self.path + ".tmp"
        with open(tmp, "w") as f:
            for ln in lines:
                f.write(ln if ln.endswith("\n") else ln + "\n")
        try:
            os.remove(self.path)
        except OSError:
            pass
        os.rename(tmp, self.path)


def _hex(b):
    return "".join("%02x" % x for x in b)


def _unhex(s):
    return bytes(int(s[i:i + 2], 16) for i in range(0, len(s), 2))
