"""Verify all 100 levels: file present, reference solution wins with 3 stars, geometry sane, renders.

    python tools/verify_all.py
"""
import os
import sys
import json
import time

os.environ["SDL_VIDEODRIVER"] = "dummy"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import pygame  # noqa: E402
from sim import LevelData, replay, ARENA_W  # noqa: E402

pygame.init()
pygame.display.set_mode((100, 100))
from level_manager import Level  # noqa: E402

bad = []
rows = []
t0 = time.time()
for i in range(1, 101):
    lvl = LevelData.load(i)
    if lvl is None:
        bad.append((i, "missing file"))
        continue
    raw = lvl.raw
    # geometry sanity
    sx, sy = lvl.start
    ex, ey = lvl.end
    if not (0 < sx < ARENA_W and 0 < sy < lvl.height and 0 < ex < ARENA_W and 0 < ey < lvl.height):
        bad.append((i, "start/end outside arena"))
    for (x, y, w, h) in lvl.walls:
        if w <= 0 or h <= 0:
            bad.append((i, "degenerate wall"))
            break
    if len(lvl.stars) != 3:
        bad.append((i, f"{len(lvl.stars)} stars"))
    # proof of solvability on the real simulation
    sim, res = replay(lvl, raw.get("ref_taps", []))
    if res is None:
        bad.append((i, "reference solution does not win"))
        continue
    if res["stars"] != 3:
        bad.append((i, f"reference collects {res['stars']} stars"))
    # renders without error
    try:
        L = Level(i)
        assert L.load()
        surf = pygame.Surface((ARENA_W, 600))
        L.draw(surf, 1.0, None, 0)
    except Exception as e:  # pragma: no cover
        bad.append((i, f"render error {e!r}"))
    d = raw.get("difficulty", {})
    rows.append((i, lvl.height, lvl.speed, d.get("corridor"), d.get("margin"), res["swaps"], res["time"], res["rank"]))

print("lvl  height speed  W    margin swaps time  rank")
for r in rows:
    if r[0] % 5 == 1 or r[0] >= 96:
        print(f"{r[0]:3d} {r[1]:6.0f} {r[2]:5.2f} {r[3]!s:>4} {r[4]!s:>6} {r[5]:5d} {r[6]:6.1f} {r[7]}")
print(f"\nchecked {len(rows)} levels in {time.time()-t0:.0f}s; problems: {len(bad)}")
for b in bad:
    print("  ", b)
sys.exit(1 if bad else 0)
