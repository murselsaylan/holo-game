"""Unsolved contact sheet of the planned campaign (fast): python levelgen/sheet.py 1 50 -> screenshots/plan_sheet_1_50.png"""
import os, sys
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import pygame
from sim import LevelData
from levelgen import gen as GEN, plan as P, preview as PV

lo, hi = int(sys.argv[1]), int(sys.argv[2])
pygame.init()
tiles = []
for i in range(lo, hi + 1):
    d, pl, ctx = GEN.build(i, P.difficulty(i))
    s = PV.draw_level(LevelData(d), scale=0.12)
    tiles.append((i, pl["family"], s))
cols = 10
th = max(t[2].get_height() for t in tiles) + 22
tw = tiles[0][2].get_width() + 8
rows = (len(tiles) + cols - 1) // cols
sheet = pygame.Surface((cols * tw, rows * th)); sheet.fill((8, 10, 18))
f = pygame.font.SysFont("arial", 12)
for k, (i, fam, s) in enumerate(tiles):
    x, y = (k % cols) * tw + 4, (k // cols) * th + 4
    sheet.blit(s, (x, y + 16)); sheet.blit(f.render(f"{i} {fam[:6]}", True, (200, 220, 255)), (x, y))
out = os.path.join(ROOT, "screenshots", f"plan_sheet_{lo}_{hi}.png")
pygame.image.save(sheet, out); print(out)
