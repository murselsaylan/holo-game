"""Contact sheets of generated levels (headless).   python levelgen/preview.py [first] [last]"""
import os
import sys
import math

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import pygame  # noqa: E402
from sim import LevelData, ARENA_W, ARENA_H  # noqa: E402


def draw_level(lvl, scale=0.36, path=True):
    W, H = int(ARENA_W * scale), int(lvl.height * scale)
    s = pygame.Surface((W, H))
    s.fill((16, 20, 34))
    k = lambda v: int(v * scale)
    for (x, y, w, h) in lvl.walls:
        pygame.draw.rect(s, (58, 72, 110), (k(x), k(y), max(1, k(w)), max(1, k(h))))
    for (x, y, w, h) in lvl.reverse_walls:
        pygame.draw.rect(s, (40, 255, 160), (k(x), k(y), max(2, k(w)), max(2, k(h))))
    for m in lvl.moving_walls:
        for tt in (0.0, math.pi):
            x, y, w, h = lvl.moving_rect(m, (tt - m[7]) / max(0.1, m[6]))
            pygame.draw.rect(s, (255, 150, 30), (k(x), k(y), max(2, k(w)), max(2, k(h))), 1)
    for l in lvl.lasers:
        pygame.draw.line(s, (255, 60, 100), (k(l[0]), k(l[1])), (k(l[2]), k(l[3])), 2)
    for sp in lvl.spinners:
        pygame.draw.circle(s, (255, 90, 200), (k(sp[0]), k(sp[1])), max(2, k(sp[2])), 1)
    for (x, y, r) in lvl.circles:
        pygame.draw.circle(s, (255, 70, 70), (k(x), k(y)), max(2, k(r)))
    for z in lvl.growth:
        pygame.draw.circle(s, (50, 255, 120), (k(z[0]), k(z[1])), max(3, k(z[2])), 1)
    for z in lvl.shrink:
        pygame.draw.circle(s, (80, 200, 255), (k(z[0]), k(z[1])), max(3, k(z[2])), 1)
    for z in lvl.boost:
        pygame.draw.circle(s, (255, 220, 60), (k(z[0]), k(z[1])), max(3, k(z[2])), 1)
    for z in getattr(lvl, 'slow', []):                          # slow field: violet ring + filled dot
        pygame.draw.circle(s, (170, 120, 255), (k(z[0]), k(z[1])), max(3, k(z[2])), 1)
        pygame.draw.circle(s, (170, 120, 255), (k(z[0]), k(z[1])), 2)
    for z in getattr(lvl, 'stretch', []):                       # stretch field: orange (long, +) / teal (short, -) ring
        col = (255, 150, 40) if z[3] > 0 else (40, 230, 200)
        pygame.draw.circle(s, col, (k(z[0]), k(z[1])), max(3, k(z[2])), 1)
        pygame.draw.line(s, col, (k(z[0]) - 3, k(z[1])), (k(z[0]) + 3, k(z[1])), 1)
        if z[3] > 0:
            pygame.draw.line(s, col, (k(z[0]), k(z[1]) - 3), (k(z[0]), k(z[1]) + 3), 1)
    for z in lvl.shields:
        pygame.draw.circle(s, (0, 220, 255), (k(z[0]), k(z[1])), 5)
    if path and len(lvl.waypoints) > 1:
        pygame.draw.lines(s, (90, 110, 150), False, [(k(x), k(y)) for x, y in lvl.waypoints], 1)
    for (x, y) in lvl.stars:
        pygame.draw.circle(s, (255, 230, 60), (k(x), k(y)), 4)
    pygame.draw.circle(s, (60, 255, 120), (k(lvl.start[0]), k(lvl.start[1])), 5)
    pygame.draw.circle(s, (80, 160, 255), (k(lvl.end[0]), k(lvl.end[1])), 6)
    return s


def sheet(first, last, cols=5, scale=0.36, out=None):
    pygame.font.init()
    font = pygame.font.Font(None, 22)
    ids = list(range(first, last + 1))
    lv = [LevelData.load(i) for i in ids]
    hmax = max((l.height for l in lv if l), default=ARENA_H)
    cw, ch = int(ARENA_W * scale) + 10, int(hmax * scale) + 30
    rows = (len(ids) + cols - 1) // cols
    surf = pygame.Surface((cols * cw, rows * ch))
    surf.fill((8, 10, 16))
    for n, lid in enumerate(ids):
        lvl = LevelData.load(lid)
        if not lvl:
            continue
        img = draw_level(lvl, scale)
        x, y = (n % cols) * cw + 5, (n // cols) * ch + 24
        surf.blit(img, (x, y))
        d = lvl.raw.get("difficulty", {})
        label = f"{lid} {lvl.title[:16]}  W{d.get('corridor','-')} m{d.get('margin','-')} s{d.get('swaps','-')}"
        surf.blit(font.render(label, True, (220, 230, 255)), (x, y - 20))
    out = out or os.path.join(ROOT, "screenshots", f"sheet_{first}_{last}.png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    pygame.image.save(surf, out)
    return out


if __name__ == "__main__":
    a = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    b = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    print(sheet(a, b))
