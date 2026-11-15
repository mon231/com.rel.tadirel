"""Regenerate assets/icon.ico from the same AC-unit glyph used by
desktop/web/icon.svg and the Android adaptive icon, so all three platforms
show one consistent mark. Run manually when the design changes:

    python assets/make_icon.py
"""

from PIL import Image, ImageDraw

BG = (15, 20, 32, 255)       # #0F1420
ACCENT = (79, 209, 197, 255)  # #4FD1C5
SIZE = 256


def build_icon() -> Image.Image:
    img = Image.new("RGBA", (SIZE, SIZE), BG)
    draw = ImageDraw.Draw(img)
    cx, cy = SIZE / 2, SIZE * 0.44
    s = SIZE / 108  # scale factor from the 108x108 design grid

    def pt(x, y):
        return (cx + x * s, cy + y * s)

    # AC unit body (rounded rect)
    body = [pt(-32, -16), pt(32, 10)]
    draw.rounded_rectangle(body, radius=6 * s, fill=ACCENT)

    # louvers
    draw.line([pt(-24, -6), pt(24, -6)], fill=BG, width=max(1, int(3 * s)))
    draw.line([pt(-24, 0), pt(24, 0)], fill=BG, width=max(1, int(3 * s)))

    # status LED
    draw.ellipse([pt(27 - 2.6, -10 - 2.6), pt(27 + 2.6, -10 + 2.6)], fill=BG)

    # airflow arcs (approximate the SVG's quadratic curves with polylines)
    def airflow(y_offset):
        pts = [
            pt(-20, 14 + y_offset),
            pt(-10, 22 + y_offset),
            pt(0, 14 + y_offset),
            pt(10, 22 + y_offset),
            pt(20, 14 + y_offset),
        ]
        draw.line(pts, fill=ACCENT, width=max(1, int(4.5 * s)), joint="curve")

    airflow(0)
    airflow(10)

    return img


if __name__ == "__main__":
    icon = build_icon()
    icon.save("assets/icon.ico", sizes=[(16, 16), (32, 32), (48, 48), (128, 128), (256, 256)])
    icon.save("assets/icon.png")
    print("wrote assets/icon.ico and assets/icon.png")
