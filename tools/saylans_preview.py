from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "social" / "saylans"
FONT_REGULAR = ROOT / "assets" / "fonts" / "Rajdhani-Medium.ttf"
FONT_BOLD = ROOT / "assets" / "fonts" / "Rajdhani-Bold.ttf"

W, H = 450, 810
FPS = 24
FRAME_COUNT = 48


def clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def ease_out_cubic(value: float) -> float:
    value = clamp(value)
    return 1.0 - (1.0 - value) ** 3


def ease_in_out(value: float) -> float:
    value = clamp(value)
    return value * value * (3.0 - 2.0 * value)


def alpha_at(t: float) -> float:
    return clamp(t / 0.20) * clamp((2.0 - t) / 0.24)


def centered_text(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str,
                  font: ImageFont.FreeTypeFont, fill: tuple[int, int, int, int]) -> None:
    box = draw.textbbox((0, 0), text, font=font)
    x = xy[0] - (box[2] - box[0]) // 2
    draw.text((x, xy[1]), text, font=font, fill=fill)


def render_frame(index: int) -> Image.Image:
    t = index / FPS
    fade = alpha_at(t)

    image = Image.new("RGBA", (W, H), (2, 5, 13, 255))
    background = ImageDraw.Draw(image, "RGBA")

    # Very restrained radial glow keeps the mark readable without looking like a game HUD.
    glow_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    glow = ImageDraw.Draw(glow_layer, "RGBA")
    radius = 170 + 8 * math.sin(t * math.pi)
    for step in range(12, 0, -1):
        rr = radius * step / 12
        a = int(3.2 * step * fade)
        glow.ellipse((W / 2 - rr, H * .40 - rr, W / 2 + rr, H * .40 + rr),
                     fill=(0, 202, 255, a))
    image = Image.alpha_composite(image, glow_layer.filter(ImageFilter.GaussianBlur(26)))

    # A pair of interrupted orbits forms an abstract S.
    mark_progress = ease_out_cubic((t - 0.12) / 0.62)
    mark = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    md = ImageDraw.Draw(mark, "RGBA")
    cx, cy = W // 2, int(H * .38)
    path_a = [(cx - 72, cy - 8), (cx - 34, cy - 48), (cx + 50, cy - 48),
              (cx + 76, cy - 22), (cx + 20, cy + 30)]
    path_b = [(cx + 72, cy + 8), (cx + 34, cy + 48), (cx - 50, cy + 48),
              (cx - 76, cy + 22), (cx - 20, cy - 30)]

    def partial_path(points: list[tuple[int, int]], progress: float) -> list[tuple[int, int]]:
        lengths = [math.dist(a, b) for a, b in zip(points, points[1:])]
        target = sum(lengths) * progress
        result = [points[0]]
        for a, b, segment in zip(points, points[1:], lengths):
            if target >= segment:
                result.append(b)
                target -= segment
                continue
            if target > 0:
                f = target / segment
                result.append((int(a[0] + (b[0] - a[0]) * f),
                               int(a[1] + (b[1] - a[1]) * f)))
            break
        return result

    cyan = (24, 220, 255, int(245 * fade))
    for path in (path_a, path_b):
        section = partial_path(path, mark_progress)
        if len(section) > 1:
            md.line(section, fill=cyan, width=5, joint="curve")
            end = section[-1]
            md.ellipse((end[0] - 4, end[1] - 4, end[0] + 4, end[1] + 4),
                       fill=(240, 253, 255, int(255 * fade)))

    aura = mark.filter(ImageFilter.GaussianBlur(13))
    image = Image.alpha_composite(image, aura)
    image = Image.alpha_composite(image, mark)

    text_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(text_layer, "RGBA")
    title_font = ImageFont.truetype(str(FONT_BOLD), 44)
    sub_font = ImageFont.truetype(str(FONT_REGULAR), 14)

    title_progress = ease_in_out((t - 0.56) / 0.46)
    title_alpha = int(255 * fade * title_progress)
    title_y = int(H * .53 + (1 - title_progress) * 10)
    centered_text(draw, (W // 2, title_y), "S A Y L A N S", title_font,
                  (238, 250, 255, title_alpha))

    sub_progress = ease_in_out((t - 0.84) / 0.38)
    sub_alpha = int(150 * fade * sub_progress)
    centered_text(draw, (W // 2, int(H * .61)), "P R E S E N T S", sub_font,
                  (98, 211, 237, sub_alpha))

    # A fine pulse hints at the transition to the game.
    pulse = ease_in_out((t - 1.17) / 0.42)
    half_line = int(86 * pulse)
    draw.line((W // 2 - half_line, int(H * .655), W // 2 + half_line, int(H * .655)),
              fill=(31, 194, 224, int(90 * fade)), width=1)
    image = Image.alpha_composite(image, text_layer)

    if t > 1.68:
        veil = clamp((t - 1.68) / .30)
        image = Image.blend(image, Image.new("RGBA", (W, H), (2, 5, 13, 255)), veil)
    return image.convert("RGB")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    frames = [render_frame(i) for i in range(FRAME_COUNT)]
    gif_path = OUT / "saylans-yayinci-animasyonu.gif"
    frames[0].save(
        gif_path,
        save_all=True,
        append_images=frames[1:],
        duration=1000 // FPS,
        loop=0,
        optimize=True,
    )

    preview_indices = [4, 11, 18, 25, 32, 39]
    contact = Image.new("RGB", (W * 3, H * 2), (2, 5, 13))
    for slot, frame_index in enumerate(preview_indices):
        contact.paste(frames[frame_index], ((slot % 3) * W, (slot // 3) * H))
    contact.save(OUT / "saylans-kareler.jpg", quality=90, optimize=True)
    frames[28].save(OUT / "saylans-kapak.png", optimize=True)
    print(gif_path)


if __name__ == "__main__":
    main()
