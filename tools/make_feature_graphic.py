"""Render the Play Store feature graphic (1024x500) using the game's own art/fonts.

    python tools/make_feature_graphic.py
"""
import os
import sys
import math

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import pygame  # noqa: E402
import space_art  # noqa: E402
from ui import draw_text  # noqa: E402
from skins import draw_tether, draw_orb, get_skin  # noqa: E402
from theme import ACCENT_CYAN  # noqa: E402

pygame.init()
pygame.display.set_mode((1, 1))

W, H = 1024, 500
OUT = os.path.join(ROOT, "store_assets", "feature_graphic.png")

f = space_art.make_menu_backdrop(W, H, seed=11).convert()

skin = get_skin("neon_pulse")
p1 = (150, 175)
p2 = (330, 300)
draw_tether(f, p1, p2, skin, 1.4)
draw_orb(f, p1, 34, skin["color1"], skin["glow1"], False, skin, 1.4)
draw_orb(f, p2, 34, skin["color2"], skin["glow2"], True, skin, 1.4)

# title lockup, right of the orbs
tx, ty = 470, 215
draw_text(f, "HOLO", 150, (0, 130, 200), (tx + 4, ty + 8), anchor="midleft")
draw_text(f, "HOLO", 150, (255, 255, 255), (tx, ty), anchor="midleft")
draw_text(f, "TWO ORBS  •  ONE PULSE  •  100 LEVELS", 30, ACCENT_CYAN, (tx + 6, ty + 108), anchor="midleft")

os.makedirs(os.path.dirname(OUT), exist_ok=True)
pygame.image.save(f, OUT)
print("saved", OUT, f.get_size())
