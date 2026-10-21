"""Preview sheets of the new levels (101-140).

    python tools/preview_new_levels.py            # -> screenshots/new_levels_overview_*.png (+ before/after sheet)

* overview sheets: 10 levels per sheet, every level as a tall strip with title, margin, taps, hazard counts.
  Colours: violet ring = slow field, orange ring = long-tether field, teal ring = short-tether field, red = mines,
  pink = spinners, orange outline = pistons, red line = lasers, white dots = stars, line = the reference route.
* before/after: raw generator output (levelgen/new_levels_raw) next to the finished level.
"""
import os
import sys
import json

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import pygame  # noqa: E402
from sim import LevelData  # noqa: E402
from levelgen import preview as PV  # noqa: E402

SCALE = 0.2
OUT = os.path.join(ROOT, "screenshots")
os.makedirs(OUT, exist_ok=True)
pygame.init()
font = pygame.font.Font(None, 22)
small = pygame.font.Font(None, 18)


def load(i, raw=False):
    p = os.path.join(ROOT, "levelgen", "new_levels_raw", f"level{i}.json") if raw else os.path.join(ROOT, "levels", f"level{i}.json")
    if not os.path.exists(p):
        return None
    return json.load(open(p, encoding="utf-8"))


def tile(d):
    lvl = LevelData(d)
    img = PV.draw_level(lvl, scale=SCALE)
    return lvl, img


def caption(surf, x, y, d, lvl, tag=""):
    dd = d.get("difficulty", {})
    n = lambda k: len(d.get(k, []))
    line1 = f"{d['id']} {d['title'][:20]} {tag}"
    line2 = f"W{dd.get('corridor', '-')} m{dd.get('margin', '-')} taps{dd.get('swaps', '-')} {dd.get('ref_time', '-')}s"
    line3 = f"slow{n('slow_zones')} str{n('stretch_zones')} mv{n('moving_walls')} L{n('lasers')} sp{n('spinners')} mi{n('circles')}"
    surf.blit(font.render(line1, True, (230, 240, 255)), (x, y))
    surf.blit(small.render(line2, True, (170, 200, 235)), (x, y + 18))
    surf.blit(small.render(line3, True, (170, 200, 235)), (x, y + 34))


def sheet(ids, name, raw=False, pair=False):
    items = []
    for i in ids:
        d = load(i)
        if d is None:
            continue
        a = tile(d)
        b = tile(load(i, True)) if pair and load(i, True) else None
        items.append((d, a, b))
    if not items:
        return None
    w1 = items[0][1][1].get_width()
    cell_w = (w1 + 8) * (2 if pair else 1) + 8
    cell_h = max(it[1][1].get_height() for it in items) + 60
    surf = pygame.Surface((cell_w * len(items), cell_h))
    surf.fill((8, 10, 16))
    for k, (d, (lvl, img), b) in enumerate(items):
        x = k * cell_w + 6
        if pair:
            if b:
                surf.blit(b[1], (x, 56))
                surf.blit(font.render("BEFORE", True, (255, 170, 120)), (x, 38))
            surf.blit(img, (x + w1 + 8, 56))
            surf.blit(font.render("AFTER", True, (140, 255, 170)), (x + w1 + 8, 38))
            caption(surf, x, 2, d, lvl)
        else:
            surf.blit(img, (x, 56))
            caption(surf, x, 2, d, lvl)
    path = os.path.join(OUT, name)
    pygame.image.save(surf, path)
    return path, surf.get_size()


if __name__ == "__main__":
    out = []
    for lo in range(101, 141, 10):
        out.append(sheet(range(lo, lo + 10), f"new_levels_overview_{lo}_{lo + 9}.png"))
    # tutorials + bosses, before/after
    out.append(sheet([101, 121, 124, 120, 140], "new_levels_tutorials_before_after.png", pair=True))
    for o in out:
        print(o)
