"""plants.py — справочник растений (порт firmware/esp32/src/plants.cpp).

Файл plants.ini рядом с настройками, строки «Томаты=60». При первом запуске
создаётся со стандартной таблицей; старый файл дополняется новыми растениями
(хвост DEFAULTS после версии файла), удалённые пользователем не возвращаются.
В облако уходит постранично (DP plants, ≤ 255 байт): «стр/всего|Имя=60;Имя=65».
Команды из панели (DP plant_cmd): «list:N[:метка]», «add:Имя=60», «del:Имя», «reset».
"""
PATH = "plants.ini"
PAGE_BYTES = 240   # запас до лимита строки DP Tuya (255)

# 🌱 стандартная таблица: влажность почвы по датчику, ниже которой пора поливать
DEFAULTS = [
    ("Томаты", 60), ("Огурцы", 70), ("Кабачки", 65), ("Баклажаны", 65),
    ("Перец", 65), ("Клубника", 65), ("Картофель", 60), ("Морковь", 60),
    ("Свёкла", 60), ("Капуста", 70), ("Салат", 70), ("Зелень", 70),
    ("Редис", 70), ("Укроп", 60), ("Петрушка", 60), ("Лук", 55),
    ("Чеснок", 50), ("Горох", 60), ("Фасоль", 60), ("Тыква", 60),
    ("Арбуз", 50), ("Дыня", 50), ("Малина", 60), ("Смородина", 60),
    ("Цветы", 55),
    # DEFAULTS_VER 2
    ("Патиссоны", 65), ("Кукуруза", 60), ("Базилик", 65), ("Шпинат", 70), ("Сельдерей", 70),
]
DEFAULTS_VER = 2
DEFAULTS_BY_VER = (0, 25, 30)   # сколько строк DEFAULTS было в версии N


def cxx_int(s):
    """Как String::toInt() в Arduino: ведущие цифры со знаком, мусор → 0."""
    s = s.lstrip()
    sign = 1
    if s[:1] in ("+", "-"):
        sign = -1 if s[0] == "-" else 1
        s = s[1:]
    n = 0
    for ch in s:
        if not ch.isdigit():
            break
        n = n * 10 + int(ch)
    return sign * n


def clean(name):
    for ch in ";=|":
        name = name.replace(ch, " ")
    return name.strip()[:32]


class Plants:
    def __init__(self, path=None):
        self.path = path       # None — только в памяти (тесты без файлов)
        self.items = []
        self._page = ""
        self._page_no = 0
        self._ver = 0

    def begin(self):
        if self.path:
            try:
                with open(self.path, encoding="utf-8") as f:
                    self.parse(f.read())
            except (OSError, ValueError):
                pass
        if self.items and self._ver < DEFAULTS_VER:
            frm = DEFAULTS_BY_VER[self._ver if self._ver >= 1 else 1]
            for name, b in DEFAULTS[frm:]:
                if self.border(name) < 0:
                    self.items.append([name, b])
            self._ver = DEFAULTS_VER
            self.save()
        if not self.items:
            self.load_defaults()
            self.save()
        self._page_no = 0
        self.build_page()

    def load_defaults(self):
        self.items = [[n, b] for n, b in DEFAULTS]
        self._ver = DEFAULTS_VER

    def parse(self, text):
        self.items = []
        self._ver = 1   # файл без отметки — таблица первой версии
        for line in text.split("\n"):
            line = line.strip()
            if line.startswith("; defaults="):
                self._ver = cxx_int(line[11:])
                continue
            if not line or line[0] in ";#[":
                continue
            eq = line.find("=")
            if eq <= 0:
                continue
            name = clean(line[:eq])
            b = cxx_int(line[eq + 1:])
            if name and 0 <= b <= 100 and self.border(name) < 0:
                self.items.append([name, b])

    def save(self):
        if not self.path:
            return False
        out = ("; Справочник растений: имя=порог влажности почвы, %\n"
               "; ниже порога (минус delta_hum) грядка поливается\n"
               "; defaults=%d\n[plants]\n" % self._ver)
        for name, b in self.items:
            out += "%s=%d\n" % (name, b)
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                f.write(out)
            return True
        except OSError:
            return False

    def border(self, name):
        for n, b in self.items:
            if n.lower() == name.lower():
                return b
        return -1

    def size(self):
        return len(self.items)

    # 📄 страница: «номер/всего|Имя=60;Имя=65», не длиннее PAGE_BYTES
    def build_page(self):
        pages = []
        cur = ""
        for name, b in self.items:
            e = "%s=%d" % (name, b)
            if cur and len(cur) + 1 + len(e) > PAGE_BYTES - 8:
                pages.append(cur)
                cur = ""
            cur = cur + ";" + e if cur else e
        pages.append(cur)
        if self._page_no >= len(pages):
            self._page_no = len(pages) - 1
        self._page = "%d/%d|%s" % (self._page_no, len(pages), pages[self._page_no])

    def page(self):
        return self._page

    def command(self, cmd):
        op, _, arg = cmd.partition(":")
        if op == "list":
            self._page_no = cxx_int(arg)
        elif op == "add":
            eq = arg.find("=")
            if eq <= 0:
                return False
            name = clean(arg[:eq])
            b = cxx_int(arg[eq + 1:])
            if not name or not 0 <= b <= 100:
                return False
            for item in self.items:
                if item[0].lower() == name.lower():
                    item[1] = b
                    break
            else:
                self.items.append([name, b])
            self.save()
            self._page_no = 0
        elif op == "del":
            name = clean(arg)
            for i, item in enumerate(self.items):
                if item[0].lower() == name.lower():
                    self.items.pop(i)
                    break
            self.save()
            self._page_no = 0
        elif op == "reset":
            self.load_defaults()
            self.save()
            self._page_no = 0
        else:
            return False
        self.build_page()
        return True
