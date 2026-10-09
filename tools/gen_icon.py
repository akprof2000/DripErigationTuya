"""Иконка устройства для консоли Tuya: капля воды с ростком на зелёном фоне.

python tools/gen_icon.py  →  assets/icon.png (512×512) и assets/icon-256.png
Рисуется с 4-кратным запасом и уменьшается — так края получаются гладкими.
"""
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets"
S = 2048                      # рабочий размер; результат — 512
GREEN_TOP = (76, 175, 80)
GREEN_BOTTOM = (46, 125, 50)
WATER = (255, 255, 255)
LEAF = (139, 195, 74)
LEAF_DARK = (85, 139, 47)


def gradient_bg(size):
    bg = Image.new("RGB", (size, size))
    d = ImageDraw.Draw(bg)
    for y in range(size):
        t = y / (size - 1)
        d.line([(0, y), (size, y)], fill=tuple(int(a + (b - a) * t) for a, b in zip(GREEN_TOP, GREEN_BOTTOM)))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, size - 1, size - 1], radius=size // 5, fill=255)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(bg, (0, 0), mask)
    return out


def drop(d, cx, cy, r, fill):
    """Капля: круг снизу + треугольник-остриё сверху."""
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=fill)
    tip = cy - int(r * 2.1)
    # касательные из острия к кругу, чтобы стык был гладким
    d.polygon([(cx, tip), (cx - int(r * 0.87), cy - int(r * 0.5)), (cx + int(r * 0.87), cy - int(r * 0.5))], fill=fill)


def leaf(d, x0, y0, x1, y1, fill):
    d.ellipse([x0, y0, x1, y1], fill=fill)


def main():
    img = gradient_bg(S)
    d = ImageDraw.Draw(img)

    # большая белая капля
    cx, cy, r = S // 2, int(S * 0.60), int(S * 0.24)
    drop(d, cx, cy, r, WATER)

    # росток внутри капли: стебель и два листа
    stem_w = int(S * 0.022)
    d.rounded_rectangle([cx - stem_w // 2, int(S * 0.50), cx + stem_w // 2, int(S * 0.74)],
                        radius=stem_w // 2, fill=LEAF_DARK)
    leaf(d, cx - int(S * 0.16), int(S * 0.47), cx + int(S * 0.01), int(S * 0.57), LEAF)
    leaf(d, cx - int(S * 0.01), int(S * 0.41), cx + int(S * 0.17), int(S * 0.51), LEAF_DARK)

    # три маленькие капли — «капельный» полив
    for dx in (-0.30, 0.0, 0.30):
        drop(d, int(cx + dx * S * 0.55), int(S * 0.90), int(S * 0.028), (200, 230, 201))

    OUT.mkdir(exist_ok=True)
    big = img.resize((512, 512), Image.LANCZOS)
    big.save(OUT / "icon.png")
    big.resize((256, 256), Image.LANCZOS).save(OUT / "icon-256.png")
    print(OUT / "icon.png")


if __name__ == "__main__":
    main()
