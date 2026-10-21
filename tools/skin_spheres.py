"""Render the spherical catalogue in themed pages and check its body masks."""
import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pygame
import skins
import skin_catalog as catalog
from skin_surface_art import PRESERVED_ART, SURFACE_ART, _build

pygame.init()
pygame.display.set_mode((1, 1))
font = pygame.font.SysFont("Arial", 17)
small = pygame.font.SysFont("Arial", 13)
out = ROOT / "screenshots"
out.mkdir(exist_ok=True)
assert set(SURFACE_ART) == set(skins.SKINS) - PRESERVED_ART
for sid in ("neon_pulse", "solar_wind", "twinkle_orb"):
    assert skins.SKINS[sid]["orb_style"] == "ring"
assert skins.SKINS["neon_pulse"]["color1"] == (0, 240, 255)
assert skins.SKINS["neon_pulse"]["color2"] == (255, 40, 160)
assert skins.SKINS["neon_pulse"]["tether_type"] == "laser"

# Compare confusing relatives with the SAME palette and rarity: the drawing,
# rather than colour or an outer rarity ornament, must distinguish them.
for left, right in (
    ("bronze_prestige", "monochrome_zen"), ("streak_spark", "monochrome_zen"),
    ("streak_nova", "solar_nova"), ("pixel_heart", "pixel_retro"),
    ("arcade_king", "pixel_retro"), ("moon_dust", "ice_moon"),
    ("stargazer", "starry_pastel"), ("frost_crystal", "quantum_lattice"),
    ("mint_blob", "gummy_pop"), ("alien_slime", "gummy_pop"),
    ("comet_angel", "angel_halo"), ("rainbow_unicorn", "cloud_bunny"),
    ("sugar_puppy", "berry_kitty"), ("mochi_pal", "cloud_bunny"),
):
    a, b = [_build(22, (170, 170, 170), SURFACE_ART[s], 0, 3, s) for s in (left, right)]
    difference = sum(abs(a.get_at((x, y))[k] - b.get_at((x, y))[k])
                     for y in range(46) for x in range(46) for k in range(3)) / (46 * 46 * 3)
    assert difference > 12, (left, right, "pattern too similar", difference)
print("PASS 14 look-alike pairs remain distinct with identical colour and rarity")

renders = 0
for sid, style in SURFACE_ART.items():
    sk = skins.SKINS[sid]
    for r in (4, 14, 22, 48):
        for t in (0, .7, 2.4):
            art = _build(r, sk["color1"], style, t, catalog.tier(sid), sid)
            c = r + 1
            # Patterns must fill the sphere and never escape its silhouette.
            for y in range(art.get_height()):
                for x in range(art.get_width()):
                    d = (x - c) ** 2 + (y - c) ** 2
                    alpha = art.get_at((x, y)).a
                    if d < (r - 1) ** 2:
                        assert alpha == 255, (sid, r, x, y, "body hole")
                    if d > (r + 1) ** 2:
                        assert alpha == 0, (sid, r, x, y, "escaped body")
            renders += 1

for page in range(3):
    sheet = pygame.Surface((1250, 1200))
    sheet.fill((8, 12, 22))
    for row, (tr, en, ids) in enumerate(catalog.THEMES[page * 6:page * 6 + 6]):
        y = row * 200
        sheet.blit(font.render(en, True, (205, 218, 240)), (14, y + 5))
        for col, sid in enumerate(ids):
            x = col * 250
            sk = skins.SKINS[sid]
            tier = catalog.tier(sid)
            pygame.draw.rect(sheet, (17, 23, 37), (x + 6, y + 31, 238, 164), border_radius=12)
            skins.draw_tether(sheet, (x + 75, y + 95), (x + 177, y + 95), sk, 1.2)
            for xx, radius, pivot in ((75, 37, False), (177, 30, True)):
                key = "2" if pivot else "1"
                skins.draw_orb(sheet, (x + xx, y + 95), radius, sk["color" + key], sk["glow" + key], pivot, sk, 1.2)
            skins.draw_orb(sheet, (x + 125, y + 146), 12, sk["color1"], sk["glow1"], False, sk, 1.2)
            label = font.render(sk["name"], True, (233, 239, 250))
            if label.get_width() > 220:
                label = pygame.transform.smoothscale(label, (220, label.get_height()))
            sheet.blit(label, (x + 15, y + 162))
            sheet.blit(small.render(catalog.tier_name(tier, "en"), True, catalog.TIERS[tier]["color"]), (x + 15, y + 181))
    path = out / f"skin_spheres_catalog_{page + 1}.png"
    pygame.image.save(sheet, str(path))
    print(path)
print(f"PASS {renders} material renders: opaque spherical bodies, clipped patterns, all 90 IDs covered")
