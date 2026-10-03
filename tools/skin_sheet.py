"""Render every skin (orb pair + tether + trail/explosion kind) at in-game size -> screenshots/skin_sheet.png; fails on any drawing error."""
import os, sys, math
os.environ.setdefault("SDL_VIDEODRIVER", "dummy"); os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import pygame
pygame.init(); pygame.display.set_mode((100, 100))
import skins
from particles import draw_shape
from fonts import get_font

ids = list(skins.SKINS)
cols = 6
cw, ch = 240, 130
rows = (len(ids) + cols - 1) // cols
sheet = pygame.Surface((cols * cw, rows * ch)); sheet.fill((10, 12, 22))
f = get_font(16, False)
bad = []
for k, sid in enumerate(ids):
    sk = skins.SKINS[sid]
    x0, y0 = (k % cols) * cw, (k // cols) * ch
    try:
        for tv in (0.7,):
            skins.draw_tether(sheet, (x0 + 70, y0 + 50), (x0 + 170, y0 + 50), sk, tv)
            skins.draw_orb(sheet, (x0 + 70, y0 + 50), 22, sk["color1"], sk["glow1"], False, sk, tv)
            skins.draw_orb(sheet, (x0 + 170, y0 + 50), 22, sk["color2"], sk["glow2"], True, sk, tv)
        kind = skins.trail_kind(sk)
        for j in range(5):
            draw_shape(sheet, kind, x0 + 30 + j * 24, y0 + 100, 5, sk["color2"])
    except Exception as e:                       # noqa
        bad.append((sid, repr(e)))
    sheet.blit(f.render(f"{sid} [{sk.get('orb_style','round')}]", True, (190, 210, 240)), (x0 + 6, y0 + 4))
out = os.path.join(ROOT, "screenshots", "skin_sheet.png")
pygame.image.save(sheet, out)
print(out, len(ids), "skins;", "ERRORS:" if bad else "no drawing errors", bad)
sys.exit(1 if bad else 0)
