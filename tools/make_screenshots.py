"""Render real Play Store phone screenshots headlessly (no display needed).

    python tools/make_screenshots.py

Writes 1080x1944 PNGs (2x the game's 900x1620 logical canvas) to store_assets/screenshots/.
"""
import os
import sys
import tempfile

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["HOLO_SAVE_DIR"] = tempfile.mkdtemp(prefix="holo_shots_")
os.environ["HOLO_SERVER"] = "http://127.0.0.1:1"

import pygame  # noqa: E402
import holo  # noqa: E402
import shop as shop_mod  # noqa: E402

OUT = os.path.join(ROOT, "store_assets", "screenshots")
os.makedirs(OUT, exist_ok=True)

g = holo.HoloGame(headless=True)
sm = g.save_mgr


class _StoreReadyBilling(shop_mod.Billing):
    """Fake billing so the shop screenshot shows real prices, not 'opening soon' / 'TEST MODE' banners."""
    name = "android"

    def available(self):
        return True

    def price(self, product_id, default=""):
        return default


g.shop.billing = _StoreReadyBilling()
sm.data["is_profile_set"] = True
sm.data["player_name"] = "NOVA"
sm.data["player_country"] = "TR"
# fake progress so menu/level-select/shop show a lived-in profile
for lvl, stars in ((1, 3), (2, 3), (3, 3), (4, 2), (5, 3), (10, 3), (15, 2), (18, 3)):
    sm.stats[str(lvl)] = {"stars": stars, "best_score": 4200 + lvl * 137, "best_time": 12.4, "best_swaps": 6, "rank": "A"}
sm.data["campaign_level"] = 19
sm.data["diamonds"] = 640
sm.unlock_skin("cosmic_void")
sm.equipped_skin = "cosmic_void"


def frames(n=3):
    for _ in range(n):
        g.update(1 / 60.0, (450, 900))
        g.draw()


def save(name):
    g.toasts = []
    g.draw()
    scaled = pygame.transform.smoothscale(g.frame, (g.frame.get_width() * 2, g.frame.get_height() * 2))
    path = os.path.join(OUT, name)
    pygame.image.save(scaled, path)
    print("saved", path, scaled.get_size())


# 1) main menu
g.state = "menu"
g.menu_ui.build()
frames(5)
save("01_menu.png")

# 2) mid-gameplay on a lively mid-difficulty level
g.load_and_play_level(19)
g.state = "playing"
for _ in range(240):
    g.update(1 / 60.0, (450, 900))
if g.sim and g.sim.dead:
    g.restart_level()
    for _ in range(180):
        g.update(1 / 60.0, (450, 900))
g.draw()
save("02_gameplay.png")

# 3) victory screen - replay the level's recorded reference solution for a genuine, good-looking clear
g.load_and_play_level(5)
s = g.sim
ref = g.level.data.raw.get("ref_taps", [])
ap_i = 0
won = False
for _ in range(20000):
    while ap_i < len(ref) and ref[ap_i] <= s.n:
        s.swap()
        ap_i += 1
    s.step()
    if any(e[0] == "win" for e in s.events):
        won = True
        break
    if s.dead:
        break
    s.events.clear()
if won:
    g._on_win()
frames(100)  # let the staggered 3-star reveal animation (delay = 18*(i+1) frames) fully settle
save("03_victory.png")

# 4) shop
g.open_shop()
frames(5)
save("04_shop.png")

# 5) skins
g.open_skins()
frames(5)
save("05_skins.png")

# 6) level select (shows real progress, locked levels hidden)
g.open_level_select()
frames(3)
save("06_levels.png")

print("\nAll screenshots written to", OUT)
