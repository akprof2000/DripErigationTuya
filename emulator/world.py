"""world.py — модель физического мира вокруг контроллера.

Здесь нет логики прошивки, только «датчики и вода»: влажность почвы в грядках,
куда воткнут датчик (почва / вода / воздух), дождь, ночь, расход через
фильтр. Логика устройства (device.py) читает отсюда так же, как прошивка
читает АЦП и пины, и командует клапанами через open_valves.

Всем можно управлять из консоли эмулятора, чтобы проверять панель в любых
ситуациях: «засушить» грядку, включить дождь, засорить фильтр.
"""
import random

ADC_WET = 1250     # 📟 АЦП датчика в воде (типичный ёмкостный датчик)
ADC_DRY = 2900     # 📟 АЦП датчика на воздухе


class World:
    def __init__(self, channels=8, seed=None):
        self.rnd = random.Random(seed)
        self.channels = channels
        # 🌱 истинная влажность почвы, 0..1
        self.soil = [self.rnd.uniform(0.35, 0.75) for _ in range(channels)]
        # 📍 где датчик: soil | water | air
        self.place = ["soil"] * channels
        self.open_valves = [False] * channels
        self.drain_on = False
        self.rain = False
        self.night = False
        self.auto_daynight = True   # 🌗 смена дня и ночи по часам эмулятора
        self.clog = 1.0             # 🧽 пропускная способность фильтра (1 = чистый)
        self.flow_sensor_ok = True  # 📟 расходомер даёт импульсы (False — залип: воды нет «по датчику»)
        self.noise = 8              # 📟 шум АЦП, отсчёты
        self.valve_lpm = 0.06       # 💧 капельная ветка, л/мин на клапан
        self.drain_lpm = 2.0        # 🗑️ пролив дренажа, л/мин
        self.dry_rate = 0.004       # 🌵 высыхание за минуту днём
        self.wet_rate = 0.02        # 💧 намокание за минуту при открытом клапане

    # ---------------- «датчики» ----------------
    def adc(self, ch):
        place = self.place[ch]
        if place == "water":
            base = ADC_WET
        elif place == "air":
            base = ADC_DRY
        else:
            # почва никогда не бывает «как вода» или «как воздух» целиком
            m = 0.08 + 0.84 * self.soil[ch]
            base = ADC_DRY - (ADC_DRY - ADC_WET) * m
        return max(0, min(4095, int(base + self.rnd.gauss(0, self.noise))))

    def flow_lpm(self):
        q = sum(self.open_valves) * self.valve_lpm + (self.drain_lpm if self.drain_on else 0.0)
        return q * self.clog

    # ---------------- шаг модели (1 минута) ----------------
    def step_minute(self, minute_of_day):
        if self.auto_daynight:
            self.night = not (6 * 60 <= minute_of_day < 21 * 60)
        dry = self.dry_rate * (0.3 if self.night else 1.0)
        for i in range(self.channels):
            s = self.soil[i] - dry
            if self.open_valves[i]:
                s += self.wet_rate * self.clog
            if self.rain:
                s += 0.01
            self.soil[i] = max(0.0, min(1.0, s))
