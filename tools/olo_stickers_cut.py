"""Cut an AI-made Olo sticker sheet (white background, grid of stickers) into transparent PNGs.

    python tools/olo_stickers_cut.py <sheet.png> <cols> <rows> [out_dir]

The background is removed by flooding the near-white pixels from the top, left and right edges only; many doodles
leave the body outline open at the bottom, so the bottom row is closed between the lowest ink on either side first.
"""
import os
import sys
from collections import deque

import numpy as np
from PIL import Image


def splits(proj, n):
    L = len(proj)
    idx = []
    for k in range(1, n):
        c = int(L * k / n)
        lo, hi = c - L // (n * 3), c + L // (n * 3)
        idx.append(lo + int(np.argmin(proj[lo:hi])))
    return [0] + idx + [L]


def cut(src, cols, rows, out, labels=False, first=0):
    """cols: one number, or one per row ("5,5,5,6" when the last row is longer). Files are numbered from `first`."""
    a = np.asarray(Image.open(src).convert("RGB")).astype(int).copy()
    ink = a.min(axis=2) < 200
    per_row = [int(c) for c in str(cols).split(",")] if "," in str(cols) else [int(cols)] * rows
    cy = splits(ink.sum(axis=1), rows)
    cxs = [splits(ink[cy[r]:cy[r + 1]].sum(axis=0), per_row[r]) for r in range(rows)]
    if labels:                     # numbered sheets: the number in each even grid cell's top-left corner is a set of
        from scipy import ndimage  # small separate ink blobs there - erased; the character's own lines are not
        H, W = a.shape[:2]
        lab, n = ndimage.label(ink, structure=np.ones((3, 3)))
        boxes = ndimage.find_objects(lab)
        for r in range(rows):
            gh, gw = H / rows, W / per_row[r]
            for c in range(per_row[r]):
                zx0, zy0 = int(c * gw), int(r * gh)
                zx1, zy1 = zx0 + int(gw * 0.26), zy0 + int(gh * 0.24)
                for i, bx in enumerate(boxes):
                    if bx is None:
                        continue
                    ys, xs = bx
                    if xs.start >= zx0 and xs.stop <= zx1 and ys.start >= zy0 and ys.stop <= zy1:
                        a[lab == i + 1] = 255
        ink = a.min(axis=2) < 200
        cy = splits(ink.sum(axis=1), rows)
        cxs = [splits(ink[cy[r]:cy[r + 1]].sum(axis=0), per_row[r]) for r in range(rows)]
    os.makedirs(out, exist_ok=True)
    n = first
    for r in range(rows):
        cx = cxs[r]
        for c in range(per_row[r]):
            x0, x1, y0, y1 = cx[c], cx[c + 1], cy[r], cy[r + 1]
            m = ink[y0:y1, x0:x1]
            ys, xs = np.nonzero(m)
            if len(xs) == 0:
                continue
            bx0, bx1 = max(0, xs.min() - 6), min(x1 - x0, xs.max() + 7)
            by0, by1 = max(0, ys.min() - 6), min(y1 - y0, ys.max() + 7)
            crop = a[y0:y1, x0:x1][by0:by1, bx0:bx1]
            h, w = crop.shape[:2]
            white = crop.min(axis=2) >= 225
            # an outline left open at the bottom is closed along the crop's last row (between the lowest ink on
            # the left and on the right), so the flood below cannot run into the body
            wall = ~white
            band = h - 18                                      # only the bottom strip: side lines that stop short
            for d in range(1, 12):                             # are extended down to the bottom row
                wall[band + d:] |= ~white[band:h - d]
            xs_b = np.nonzero(wall[-3:].any(axis=0))[0]
            if len(xs_b):
                wall[-1, xs_b.min():xs_b.max() + 1] = True
            orig_white = white.copy()
            white = white & ~wall
            outside = np.zeros((h, w), bool)
            dq = deque()
            seeds = [(0, x) for x in range(w)] + [(y, 0) for y in range(h)] + [(y, w - 1) for y in range(h)]
            for y, x in seeds:
                if white[y, x] and not outside[y, x]:
                    outside[y, x] = True
                    dq.append((y, x))
            while dq:
                y, x = dq.popleft()
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w and white[ny, nx] and not outside[ny, nx]:
                        outside[ny, nx] = True
                        dq.append((ny, nx))
            # the helper wall itself is not part of the picture: wall pixels next to the outside go transparent too
            helper = orig_white & ~white
            for _ in range(14):
                grow = np.zeros_like(outside)
                grow[1:] |= outside[:-1]
                grow[:-1] |= outside[1:]
                grow[:, 1:] |= outside[:, :-1]
                grow[:, :-1] |= outside[:, 1:]
                new = grow & helper & ~outside
                if not new.any():
                    break
                outside |= new
            alpha = np.where(outside, 0, 255).astype(np.uint8)
            Image.fromarray(np.dstack([crop.astype(np.uint8), alpha])).save(os.path.join(out, f"p{n:03d}.png"))
            n += 1
    return n - first


if __name__ == "__main__":
    out = sys.argv[4] if len(sys.argv) > 4 and not sys.argv[4].startswith("--") else os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                                              "store_assets", "olo_stickers")
    first = next((int(x[8:]) for x in sys.argv if x.startswith("--first=")), 0)
    print("stickers", cut(sys.argv[1], sys.argv[2], int(sys.argv[3]), out, labels="--labels" in sys.argv, first=first))
