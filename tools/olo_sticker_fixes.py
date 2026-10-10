"""Hand fixes on the cut Olo stickers (tools/olo_stickers_cut.py): drawing mistakes of the AI sheet, brand logos and
alcohol (store age ratings). Run after cutting; each fix names the sticker it touches.

    python tools/olo_sticker_fixes.py
"""
import os

import numpy as np
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
S30 = os.path.join(ROOT, "store_assets", "olo_stickers")
S100 = os.path.join(ROOT, "store_assets", "olo_stickers100")


def load(folder, name):
    p = os.path.join(folder, name + ".png")
    return p, np.array(Image.open(p).convert("RGBA"))


def save(p, a):
    Image.fromarray(a).save(p)
    print("fixed", os.path.relpath(p, ROOT))


def fill_body(a, close=6):
    """Fills the inside of a body whose outline has small gaps (the cut left it transparent): the ink is closed
    morphologically, its holes filled, and every transparent pixel in there becomes white."""
    from scipy import ndimage
    ink = (a[..., 3] > 0) & (a[..., :3].astype(int).max(axis=2) < 90)
    closed = ndimage.binary_closing(ink, structure=np.ones((3, 3)), iterations=close)
    inside = ndimage.binary_fill_holes(closed) & ~closed
    lab, n = ndimage.label(inside)
    if n > 1:                                      # only the body: the biggest enclosed area (not gaps in letters)
        sizes = ndimage.sum(inside, lab, range(1, n + 1))
        inside = lab == (1 + int(np.argmax(sizes)))
    inside = ndimage.binary_dilation(inside, iterations=close) & ~ink
    hole = inside & (a[..., 3] == 0)
    a[hole, :3] = 255
    a[hole, 3] = 255
    return int(hole.sum())


def erase_inside(a, box):
    """Paint a box white (inside the body): removes a stray stroke without touching the outline around it."""
    x0, y0, x1, y1 = box
    a[y0:y1, x0:x1, :3] = 255
    a[y0:y1, x0:x1, 3] = 255


def holo_logo(a, box, lid):
    """Replaces a laptop's brand logo with HOLO's own mark: two orbs and their tether."""
    x0, y0, x1, y1 = box
    a[y0:y1, x0:x1, :3] = lid
    im = Image.fromarray(a)
    d = ImageDraw.Draw(im)
    cx, cy, w = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0)
    r = max(2, w * 0.16)
    d.line([(cx - w * 0.28, cy + w * 0.08), (cx + w * 0.28, cy - w * 0.08)], fill=(235, 245, 255, 255), width=max(1, int(w * 0.06)))
    for ox, oy, col in ((-0.28, 0.08, (0, 214, 255)), (0.28, -0.08, (255, 120, 210))):
        d.ellipse([cx + ox * w - r, cy + oy * w - r, cx + ox * w + r, cy + oy * w + r], fill=col + (255,))
    a[:] = np.array(im)


def recolor_green(a, to=(255, 140, 30)):
    """Green glass (a beer bottle) becomes an orange soda bottle; the ink outline stays."""
    rgb = a[..., :3].astype(int)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    green = (g > r + 25) & (g > b + 15) & (a[..., 3] > 0)
    shade = (rgb[..., 1] / 255.0)[green]
    a[green, 0] = np.clip(to[0] * (0.55 + 0.6 * shade), 0, 255)
    a[green, 1] = np.clip(to[1] * (0.55 + 0.6 * shade), 0, 255)
    a[green, 2] = np.clip(to[2] * (0.55 + 0.6 * shade), 0, 255)
    return int(green.sum())


def red_to_ink(a, box):
    """A red smear on the outline (laughing sticker) drawn black like the rest of the line."""
    x0, y0, x1, y1 = box
    sub = a[y0:y1, x0:x1]
    rgb = sub[..., :3].astype(int)
    red = (rgb[..., 0] > 150) & (rgb[..., 1] < 110) & (rgb[..., 2] < 110)
    sub[red, :3] = (20, 20, 22)


def main():
    if os.path.isdir(S30):
        p, a = load(S30, "s08")                     # slow clap: the cut left the body empty (both arms are fine)
        print("s08 body px", fill_body(a, close=6))
        save(p, a)
        p, a = load(S30, "s01")                     # laughing: red smear on the left outline
        red_to_ink(a, (0, 80, 70, 130))
        save(p, a)
        p, a = load(S30, "s19")                     # laptop: brand logo -> HOLO's two orbs
        holo_logo(a, (160, 82, 196, 114), (161, 161, 161))
        save(p, a)
    if os.path.isdir(S100):
        for n in ("s61", "s94"):                    # #62 drinking, #95 bottle: beer -> orange soda
            p, a = load(S100, n)
            print(n, "green px", recolor_green(a))
            save(p, a)


if __name__ == "__main__":
    main()
