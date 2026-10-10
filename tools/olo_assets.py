"""Copies the chosen Olo stickers (cut by tools/olo_stickers_cut.py, fixed by tools/olo_sticker_fixes.py) into the
game's assets/olo/ with meaningful names, dropping stray bits from neighbouring cells and sheet numbers.

    python tools/olo_assets.py
"""
import os

import numpy as np
from PIL import Image
from scipy import ndimage

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
S30 = os.path.join(ROOT, "store_assets", "olo_stickers")
S100 = os.path.join(ROOT, "store_assets", "olo_stickers100")
OUT = os.path.join(ROOT, "assets", "olo")

# name: (sheet, file); new poses arrive in small batches from the user - add them here (the 100-sheet is not used)
PICK = {
    "smug": (S30, "s00"), "laugh_point": (S30, "s01"), "film": (S30, "s02"), "shock": (S30, "s03"),
    "sleep": (S30, "s05"), "devil": (S30, "s06"), "dead": (S30, "s07"), "clap": (S30, "s08"),
    "cry_tissue": (S30, "s09"), "thumbs_up": (S30, "s10"), "thumbs_down": (S30, "s11"), "think": (S30, "s12"),
    "angry": (S30, "s14"), "hooray": (S30, "s15"), "sad_knees": (S30, "s16"), "ramen": (S30, "s17"),
    "coffee": (S30, "s18"), "finger_guns": (S30, "s21"), "run": (S30, "s22"), "money": (S30, "s23"),
    "stress": (S30, "s24"), "idea": (S30, "s25"), "selfie": (S30, "s27"), "shrug": (S30, "s28"), "cheer": (S30, "s29"),
}


def clean(a):
    """Keeps the character: the biggest blob plus the bits close to it (tears, ?!, zzz); drops pieces of the
    neighbouring stickers and sheet numbers that the grid cut caught at the edges."""
    solid = a[..., 3] > 0
    lab, n = ndimage.label(solid, structure=np.ones((3, 3)))
    if n <= 1:
        return a
    sizes = ndimage.sum(solid, lab, range(1, n + 1))
    main = 1 + int(np.argmax(sizes))
    ys, xs = np.nonzero(lab == main)
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    h, w = solid.shape
    reach = 0.22 * max(x1 - x0, y1 - y0)
    keep = np.zeros_like(solid)
    for i in range(1, n + 1):
        cy, cx = np.nonzero(lab == i)
        if i == main:
            keep |= lab == i
            continue
        dx = max(0, x0 - cx.max(), cx.min() - x1)
        dy = max(0, y0 - cy.max(), cy.min() - y1)
        at_edge = cx.min() == 0 or cy.min() == 0 or cx.max() == w - 1 or cy.max() == h - 1
        if max(dx, dy) <= reach and not (at_edge and sizes[i - 1] < 0.04 * sizes.sum()):
            keep |= lab == i
    a = a.copy()
    a[~keep, 3] = 0
    ys, xs = np.nonzero(a[..., 3] > 0)
    return a[max(0, ys.min() - 4):ys.max() + 5, max(0, xs.min() - 4):xs.max() + 5]


def main():
    os.makedirs(OUT, exist_ok=True)
    for name, (folder, f) in PICK.items():
        a = np.array(Image.open(os.path.join(folder, f + ".png")).convert("RGBA"))
        a = clean(a)
        Image.fromarray(a).save(os.path.join(OUT, name + ".png"), optimize=True)
    print(len(PICK), "stickers ->", OUT)


if __name__ == "__main__":
    main()
