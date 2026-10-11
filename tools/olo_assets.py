"""Olo's game stickers: the developer's numbered sheets (cut into store_assets/olo_set/pNNN.png by
tools/olo_stickers_cut.py) -> assets/olo/<name>.png, cleaned and fixed.

    python tools/olo_assets.py

Fixes: bodies the cut left empty are filled, brand logos on laptops become HOLO's two orbs, bottles become orange
soda. Left out: 54 (middle finger), 61 (smoking), 62 (alcohol), 38 / 45 (vomiting) and duplicates.
"""
import os
import sys

import numpy as np
from PIL import Image
from scipy import ndimage

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "store_assets", "olo_set")
OUT = os.path.join(ROOT, "assets", "olo")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from olo_sticker_fixes import holo_logo, recolor_green  # noqa: E402

PICK = {
    0: "smug", 1: "laugh_point", 2: "film", 3: "shock", 4: "facepalm", 5: "sleep", 6: "devil", 7: "dead", 8: "clap",
    9: "cry_tissue", 10: "think", 11: "love", 12: "angry", 13: "hooray", 14: "thumbs_up", 15: "thumbs_down",
    16: "coffee", 17: "laptop", 18: "gamer", 19: "finger_guns", 20: "shrug_q", 22: "run", 23: "money", 24: "shrug",
    25: "idea", 26: "sad_knees", 27: "shy", 28: "selfie", 29: "flowers", 30: "dance", 31: "ramen", 32: "blanket_phone",
    33: "peek", 34: "think_q", 35: "soda", 36: "flex", 37: "chef", 39: "shower", 40: "nap", 41: "sob", 42: "cook_angry",
    44: "dizzy", 46: "ghost", 48: "megaphone", 51: "sit_sad", 52: "blanket_blue", 53: "tryhard", 55: "heart_eyes",
    56: "cry_hands", 57: "meditate", 58: "burger", 59: "flat", 60: "rain", 63: "phone_love", 64: "nervous",
    65: "cry_quiet", 66: "party", 69: "rage_chair", 70: "flat_floor", 71: "scream", 72: "dance_hop",
    73: "on_fire", 74: "cat_hug", 75: "confused", 76: "watermelon", 77: "sick", 79: "heart_hug", 81: "bed_phone",
    82: "pizza", 83: "toilet_phone", 84: "headphones", 85: "laptop_stress", 86: "hand_face", 88: "lying_phone",
    89: "sob_puddle", 91: "sip", 93: "confetti", 94: "gift", 95: "flat_dizzy", 96: "thought", 97: "laptop_angry",
    98: "cat_love", 99: "confused_shrug",
}
LOGO = {17, 85, 97}
LOGO_BOX = {17: (192, 96, 230, 140)}          # where the automatic search only finds part of the logo
WIDE_GAPS = {8, 67, 100}                       # outlines with bigger gaps: close harder before filling
BOTTLE = set()          # the champagne (100) did not survive the cut cleanly - left out
MOUTH = {86: (138, 120, 15)}   # drawn without a mouth under the hand (read as faceless): a small frown, in final coords


def fill_if_empty(a, close=6):
    """A body the cut left transparent (its outline had a gap) is filled white: close the ink, fill its holes,
    and if most of the biggest enclosed area is transparent, paint it in."""
    ink = (a[..., 3] > 0) & (a[..., :3].astype(int).max(axis=2) < 90)
    closed = ndimage.binary_closing(ink, structure=np.ones((3, 3)), iterations=close)
    inside = ndimage.binary_fill_holes(closed) & ~closed
    lab, n = ndimage.label(inside)
    if n == 0:
        return False
    sizes = ndimage.sum(inside, lab, range(1, n + 1))
    body = lab == (1 + int(np.argmax(sizes)))
    if (a[..., 3][body] == 0).mean() < 0.25:
        return False
    body = ndimage.binary_dilation(body, iterations=close) & ~ink
    hole = body & (a[..., 3] == 0)
    a[hole, :3] = 255
    a[hole, 3] = 255
    return True


def clean(a):
    """Keeps the character and the bits near it (tears, ?!, zzz); drops stray pieces at the cell edges."""
    solid = a[..., 3] > 0
    lab, n = ndimage.label(solid, structure=np.ones((3, 3)))
    if n > 1:
        sizes = ndimage.sum(solid, lab, range(1, n + 1))
        main = 1 + int(np.argmax(sizes))
        ys, xs = np.nonzero(lab == main)
        x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
        reach = 0.22 * max(x1 - x0, y1 - y0)
        keep = lab == main
        for i in range(1, n + 1):
            if i == main:
                continue
            cy, cx = np.nonzero(lab == i)
            dx = max(0, x0 - cx.max(), cx.min() - x1)
            dy = max(0, y0 - cy.max(), cy.min() - y1)
            h, w = solid.shape
            dark = a[..., :3][lab == i].astype(int).max(axis=1).mean() < 110
            corner = cx.max() < w * 0.32 and cy.max() < h * 0.28        # leftover bits of the sheet's number
            if corner and dark and sizes[i - 1] < 0.02 * sizes.sum():
                continue
            if max(dx, dy) <= reach and sizes[i - 1] > 12:
                keep |= lab == i
        a = a.copy()
        a[~keep, 3] = 0
    ys, xs = np.nonzero(a[..., 3] > 0)
    return a[max(0, ys.min() - 4):ys.max() + 5, max(0, xs.min() - 4):xs.max() + 5]


def add_mouth(a, cx, cy, w):
    """A small frown drawn at 4x and scaled down, so its edge is as soft as the sheet's ink."""
    from PIL import ImageDraw
    im = Image.fromarray(a)
    big = im.resize((im.width * 4, im.height * 4), Image.LANCZOS)
    ImageDraw.Draw(big).arc(((cx - w) * 4, cy * 4, (cx + w) * 4, (cy + 16) * 4), 200, 340, fill=(12, 12, 12, 255), width=20)
    return np.array(big.resize(im.size, Image.LANCZOS))


def logo_box(a):
    """The brand logo on a laptop lid: pixels clearly off the lid's grey, well inside the lid."""
    rgb = a[..., :3].astype(int)
    grey = (np.ptp(rgb, axis=2) < 14) & (rgb.mean(axis=2) > 55) & (rgb.mean(axis=2) < 215) & (a[..., 3] > 0)
    lab, n = ndimage.label(grey)
    if not n:
        return None
    lid = lab == (1 + int(np.argmax(ndimage.sum(grey, lab, range(1, n + 1)))))
    ys, xs = np.nonzero(lid)
    tone = np.median(rgb[lid], axis=0)
    filled = ndimage.binary_fill_holes(lid)
    odd = filled & ~lid & (a[..., 3] > 0)
    lab2, n2 = ndimage.label(odd)
    if not n2:
        return None
    big = lab2 == (1 + int(np.argmax(ndimage.sum(odd, lab2, range(1, n2 + 1)))))
    ys, xs = np.nonzero(big)
    pad = 3
    return (xs.min() - pad, ys.min() - pad, xs.max() + pad + 1, ys.max() + pad + 1), tuple(int(v) for v in tone)


def main():
    os.makedirs(OUT, exist_ok=True)
    for f in os.listdir(OUT):
        if f.endswith(".png"):
            os.remove(os.path.join(OUT, f))
    for num, name in PICK.items():
        a = np.array(Image.open(os.path.join(SRC, f"p{num:03d}.png")).convert("RGBA"))
        if fill_if_empty(a, close=10 if num in WIDE_GAPS else 6):
            print("filled", num, name)
        if num in LOGO:
            got = (LOGO_BOX[num], tuple(int(v) for v in np.median(a[LOGO_BOX[num][1] - 6, LOGO_BOX[num][0]:LOGO_BOX[num][2], :3], axis=0)))                 if num in LOGO_BOX else logo_box(a)
            if got:
                holo_logo(a, *got)
                print("logo", num, name, got)
        if num in BOTTLE:
            print("soda", num, recolor_green(a))
        a = clean(a)
        if num in MOUTH:
            a = add_mouth(a, *MOUTH[num])
        Image.fromarray(a).save(os.path.join(OUT, name + ".png"), optimize=True)
    print(len(PICK), "stickers ->", OUT)


if __name__ == "__main__":
    main()
