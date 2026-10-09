"""Превью панели 750×1334 для «IoT Platform Display Setting» MiniApp в консоли Tuya.

python tools/gen_preview.py  →  assets/preview-{ru,en,zh}.png
Это макет главного экрана (вкладка «Грядки») с правдоподобными данными,
а не скриншот: в IDE симулятор слишком мелкий для 750×1334.
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets"
W, H = 750, 1334
FONTS = {   # (обычный, жирный); для китайского — Microsoft YaHei
    "latin": ("C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/segoeuib.ttf"),
    "zh": ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc"),
}

BG = (244, 246, 248)
CARD = (255, 255, 255)
TEXT = (30, 30, 30)
MUTED = (140, 140, 140)
ACCENT = (25, 137, 250)       # @accent панели = --app-M1 темы Smart Life (синий #1989fa)
OK = (76, 175, 80)
WATER = (33, 150, 243)

TEXTS = {
    "ru": {"title": "Капельный полив", "bed": "Грядка", "tabs": ["Грядки", "Вода", "События", "Настройки"],
           "chips": ["День", "Сухо", "0.06 л/мин"], "open": "полив · ниже порога", "close": "закрыт · влажно"},
    "en": {"title": "Drip Irrigation", "bed": "Bed", "tabs": ["Beds", "Water", "Events", "Settings"],
           "chips": ["Day", "Dry", "0.06 L/min"], "open": "watering · below threshold",
           "close": "closed · moist enough"},
    "zh": {"title": "滴灌控制器", "bed": "花床", "tabs": ["花床", "用水", "事件", "设置"],
           "chips": ["白天", "干燥", "0.06 升/分"], "open": "浇水中 · 低于阈值", "close": "已关闭 · 湿度足够"},
}
HUM = [63, 48, 66, 57, 61, 52, 59, 64]
BORDER = 55


LANG = "latin"


def font(size, bold=False):
    return ImageFont.truetype(FONTS[LANG][1 if bold else 0], size)


def render(lang):
    global LANG
    LANG = "zh" if lang == "zh" else "latin"
    t = TEXTS[lang]
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    d.text((W // 2, 120), t["title"], font=font(40, True), fill=TEXT, anchor="mm")
    x = 32
    for i, c in enumerate(t["chips"]):
        f = font(24)
        w = d.textlength(c, font=f) + 36
        col = (227, 242, 253) if i == 2 else (232, 245, 233)
        d.rounded_rectangle([x, 175, x + w, 223], radius=24, fill=col)
        d.text((x + w / 2, 199), c, font=f, fill=WATER if i == 2 else OK, anchor="mm")
        x += w + 14

    cw, ch, gap, top = (W - 32 * 2 - 20) // 2, 210, 20, 250
    for i, h in enumerate(HUM):
        col, row = i % 2, i // 2
        x0 = 32 + col * (cw + gap)
        y0 = top + row * (ch + gap)
        d.rounded_rectangle([x0, y0, x0 + cw, y0 + ch], radius=24, fill=CARD)
        d.text((x0 + 26, y0 + 24), "%s %d" % (t["bed"], i + 1), font=font(28), fill=TEXT)
        watering = h < BORDER - 5
        d.ellipse([x0 + cw - 40, y0 + 32, x0 + cw - 24, y0 + 48], fill=ACCENT if watering else OK)
        d.text((x0 + 26, y0 + 64), "%d%%" % h, font=font(54, True), fill=TEXT)
        bar_y = y0 + 142
        d.rounded_rectangle([x0 + 26, bar_y, x0 + cw - 26, bar_y + 10], radius=5, fill=(235, 235, 235))
        d.rounded_rectangle([x0 + 26, bar_y, x0 + 26 + (cw - 52) * h // 100, bar_y + 10], radius=5, fill=ACCENT)
        mx = x0 + 26 + (cw - 52) * BORDER // 100
        d.rectangle([mx - 2, bar_y - 8, mx + 2, bar_y + 18], fill=(80, 80, 80))
        d.text((x0 + 26, y0 + 168), t["open"] if watering else t["close"], font=font(21), fill=MUTED)

    d.rectangle([0, H - 120, W, H], fill=CARD)
    for i, tab in enumerate(t["tabs"]):
        cx = W * (2 * i + 1) // 8
        d.text((cx, H - 60), tab, font=font(26, i == 0), fill=ACCENT if i == 0 else MUTED, anchor="mm")
    return img


def main():
    OUT.mkdir(exist_ok=True)
    for lang in ("ru", "en", "zh"):
        render(lang).save(OUT / ("preview-%s.png" % lang))
        print(OUT / ("preview-%s.png" % lang))


if __name__ == "__main__":
    main()
