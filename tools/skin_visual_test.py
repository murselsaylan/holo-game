"""Small regression check for distinctive skin art and cached UI thumbnails."""
import os
import sys
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame

from skins import SKINS, draw_orb, draw_tether
from ui import _SKIN_THUMB_CACHE, skin_thumbnail


pygame.init()
skin = SKINS["cyber_matrix"]
assert skin["orb_style"] == "gear"
assert skin["tether_type"] == "chain"

preview = pygame.Surface((900, 520))
preview.fill((6, 10, 18))
p1, p2 = (285, 250), (615, 250)
draw_tether(preview, p1, p2, skin, 1.1)
draw_orb(preview, p1, 78, skin["color1"], skin["glow1"], False, skin, 1.1)
draw_orb(preview, p2, 78, skin["color2"], skin["glow2"], True, skin, 1.1)
output = os.path.join(os.path.dirname(os.path.dirname(__file__)), "screenshots", "cyber_matrix_gear_chain.png")
os.makedirs(os.path.dirname(output), exist_ok=True)
pygame.image.save(preview, output)

_SKIN_THUMB_CACHE.clear()
started = time.perf_counter()
for skin_id in SKINS:
    skin_thumbnail(skin_id)
cold_ms = (time.perf_counter() - started) * 1000
assert len(_SKIN_THUMB_CACHE) == len(SKINS)

started = time.perf_counter()
for _ in range(200):
    for skin_id in SKINS:
        skin_thumbnail(skin_id)
lookup_ms = (time.perf_counter() - started) * 1000 / (200 * len(SKINS))
print(f"PASS gear + chain preview: {output}")
print(f"PASS {len(SKINS)} cached thumbnails: cold={cold_ms:.2f}ms lookup={lookup_ms:.5f}ms")
