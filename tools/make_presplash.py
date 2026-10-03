"""Android loading splash (assets/presplash.png): shown by python-for-android while Python starts.

    python tools/make_presplash.py

It is the exact first frame of the start-up intro (holo.HoloGame._draw_intro at t = 0): flat BG_DARK, the logo
80 px above the screen centre and the three loading dots 187 px below the logo - so when the game takes over, the
logo simply starts gliding and the orbs spin up, with no jump. Android fits the image inside the screen (centred)
and fills the rest with android.presplash_color, which is BG_DARK too. The image is drawn in the game's virtual
units (900 wide) and saved 1.2x, the scale a 1080 px wide phone shows the game at.
"""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import pygame  # noqa: E402

pygame.init()
pygame.display.set_mode((1, 1))
import ui  # noqa: E402
from theme import BG_DARK  # noqa: E402

W, H = 900, 1600
surf = pygame.Surface((W, H)).convert()
surf.fill(BG_DARK)

cx, sy = W // 2, H // 2 - 80                       # same spot as _draw_intro's `sy`
menu = ui.MainMenu.__new__(ui.MainMenu)             # only for its logo sprite
spr, tw, th = ui.MainMenu._title_sprite(menu)
rect = pygame.Rect(0, 0, tw, th)
rect.center = (cx, sy)
surf.blit(spr, rect.topleft, special_flags=pygame.BLEND_PREMULTIPLIED)
for i, c in enumerate(((0, 230, 255), (0, 150, 190), (0, 80, 110))):
    pygame.draw.circle(surf, c, (cx + (i - 1) * 40, sy + 187), 9)

out = pygame.transform.smoothscale(surf, (1080, 1920))
path = os.path.join(ROOT, "assets", "presplash.png")
pygame.image.save(out, path)
print("written", path)
