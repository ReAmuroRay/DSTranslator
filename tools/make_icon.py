"""生成 DSTranslator 的多尺寸 .ico(蓝底圆角方块 + 白色"译")。"""
import os

from PIL import Image, ImageDraw, ImageFont

FONTS = [
    r"C:/Windows/Fonts/msyh.ttc",
    r"C:/Windows/Fonts/msyhbd.ttc",
    r"C:/Windows/Fonts/simhei.ttf",
]


def _find_font():
    for p in FONTS:
        if os.path.exists(p):
            return p
    return None


def make_icon(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    radius = int(size * 0.22)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=(47, 111, 237, 255))
    font_path = _find_font()
    if font_path:
        font = ImageFont.truetype(font_path, int(size * 0.62))
    else:
        font = ImageFont.load_default()
    text = "译"
    bbox = d.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    x = (size - tw) / 2 - bbox[0]
    y = (size - th) / 2 - bbox[1]
    d.text((x, y), text, font=font, fill=(255, 255, 255, 255))
    return img


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    out = os.path.join(here, "..", "dstl.ico")
    font_used = _find_font()
    icon = make_icon(256)
    icon.save(out, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print(f"icon saved -> {os.path.abspath(out)} (font: {font_used})")
