"""reporter.py — какие отчёты DP стоит отправлять в облако, а какие подождут.

Tuya советует не больше ~3500 отчётов в сутки на устройство. Влажность
меняется медленно, а шум АЦП даёт дрожание ±1 %: без фильтра восемь каналов
легко шлют десятки тысяч отчётов. Правило для «шумных» DP: отправлять, если
значение ушло от последнего отправленного на min_delta, либо прошло max_age
секунд. Всё остальное (события, состояния клапанов, настройки, мастер) —
сразу. Снимок «всё целиком» (после подключения) не фильтруется.

Значения — уже в формате Tuya (целые со scale), как отдаёт Device.report().
"""

# код → (минимальное изменение в единицах DP, максимум секунд между отчётами)
NOISY = {
    "humidity": (2, 600),          # 2 % или раз в 10 мин
    "adc_raw": (None, 600),        # только раз в 10 мин (меняется каждую минуту)
    "flow_rate": (20, 300),        # 0.02 л/мин (scale 3) или раз в 5 мин
    "flow_session": (10, 300),     # 0.1 л (scale 2) или раз в 5 мин
    "filter_baseline": (5, 600),
}


def _rule(code):
    base = code.rsplit("_", 1)[0] if code[-1:].isdigit() else code
    return NOISY.get(base)


class Reporter:
    def __init__(self):
        self.last = {}      # code → (value, time)

    def filter(self, packet, now, full=False):
        """packet {code: value} → то, что действительно надо отправить."""
        out = {}
        for code, v in packet.items():
            rule = _rule(code)
            prev = self.last.get(code)
            send = full or rule is None or prev is None
            if not send:
                delta, max_age = rule
                pv, pt = prev
                if now - pt >= max_age:
                    send = True
                elif delta is not None and isinstance(v, (int, float)) and abs(v - pv) >= delta:
                    send = True
            if send:
                out[code] = v
                self.last[code] = (v, now)
        return out
