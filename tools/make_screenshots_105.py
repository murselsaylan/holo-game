"""Play Store phone screenshots for 1.0.5 (Turkish UI), rendered headlessly from the real game.

    python tools/make_screenshots_105.py [lang]

Writes 1080x1920 PNGs to store_assets/screenshots_105/<lang>/: menu, a campaign level, the endless climb (stars,
height lines, the record banner), its result card, the Star Hunter skins, the featured shop and a victory.
"""
import os
import sys
import tempfile
import time

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
os.environ["HOLO_SAVE_DIR"] = tempfile.mkdtemp(prefix="holo_shots105_")
os.environ["HOLO_SERVER"] = "http://127.0.0.1:1"

import pygame  # noqa: E402
import holo  # noqa: E402
import locales  # noqa: E402
import shop as shop_mod  # noqa: E402
import skin_catalog as C  # noqa: E402
import endless as E  # noqa: E402
import endless_qa as Q  # noqa: E402

LANG = sys.argv[1] if len(sys.argv) > 1 else "tr"
OUT = os.path.join(ROOT, "store_assets", "screenshots_105", LANG)
os.makedirs(OUT, exist_ok=True)

g = holo.HoloGame(headless=True)
sm = g.save_mgr


class _StoreReadyBilling(shop_mod.Billing):
    name = "android"

    def available(self):
        return True

    def price(self, product_id, default=""):
        return default


g.shop.billing = _StoreReadyBilling()
sm.data.update(is_profile_set=True, player_name="NOVA", player_country="TR", howto_seen=True)
sm.language = LANG
locales.set_language(LANG)
g.on_language_change()
for lvl in range(1, 25):
    sm.stats[str(lvl)] = {"stars": 3 if lvl % 4 else 2, "best_score": 4200 + lvl * 1370, "best_time": 12.4,
                          "best_swaps": 6, "rank": "S"}
sm.data["campaign_level"] = 25
sm.data["diamonds"] = 640
sm.data["star_coins"] = 260
sm.endless.update(v=2, best_m=40, best_all=1500)
sm.unlock_skin("cosmic_void")
sm.equipped_skin = "cosmic_void"
g.toasts = []


def frames(n=3):
    for _ in range(n):
        g.update(1 / 60.0, (450, 900))
        g.draw()


def save(name):
    g.toasts = []
    img = pygame.transform.smoothscale(g.frame, (1080, 1944))
    out = pygame.Surface((1080, 1920))
    out.blit(img, (0, -12))
    path = os.path.join(OUT, name)
    pygame.image.save(out, path)
    print("saved", path)


# 1) menu
g.state = "menu"
g.menu_ui.build()
frames(5)
save("01_menu.png")

# 2) the endless climb, played by the QA bot: stars, the height lines, then the record banner
g.open_endless()
best, taps = Q.climb_bot(E.seed_of(g.endless_week, g.endless_nonce), 3, time.time() + 120)
taps = sorted(taps)
i = 0
shot_play = shot_banner = False
for f in range(60 * 90):
    while i < len(taps) and taps[i] <= g.sim.n:
        g.swap_pivot()
        i += 1
    g.update(1 / 60.0, (450, 900))
    g.draw()
    if g.state != "playing":
        break
    if not shot_play and f > 200 and g.sim.stars and not all(g.sim.stars[:2]):
        save("02_endless.png")
        shot_play = True
    b = g.endless_banner
    if not shot_banner and b and b[0] == locales.t("endless_banner_record") and b[3] < b[4] - 0.25:
        save("03_endless_record.png")
        shot_banner = True
    if shot_play and shot_banner and g.endless_run.stage >= 1 and f % 30 == 0 and g.endless_banner is None:
        save("04_endless_climb.png")
        break
# 3) the result card
g._endless_over()
g.online.endless_result = {"ok": True, "added": 1, "rank": 7, "total": 184, "next_gem": 120}
frames(40)
save("05_endless_result.png")

# 4) Star Hunter skins
g._open_star_skins()
frames(5)
save("06_star_skins.png")

# 5) a campaign level in play
g.load_and_play_level(22)
g.state = "playing"
ref = sorted(g.level.data.raw.get("ref_taps", []))
i = 0
for _ in range(420):
    while i < len(ref) and ref[i] <= g.sim.n:
        g.swap_pivot()
        i += 1
    g.update(1 / 60.0, (450, 900))
g.draw()
save("07_gameplay.png")

# 6) the featured shop
g.open_featured()
frames(5)
save("08_featured.png")
print("done", OUT)
