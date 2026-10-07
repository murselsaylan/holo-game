"""App Store iPhone screenshots (6.7"/6.9" slot, 1290x2796), rendered headlessly from the real game.

    python tools/make_screenshots_ios.py [lang]

Same scenes as the Play set (tools/make_screenshots_105.py), but in the phone's tall layout (the game is started as
on an iPhone 15 Pro Max: 1290x2796 panel, no money prices - iOS sells nothing for real money yet).
Writes store_assets/ios_screens/<lang>/.
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
PANEL = (1290, 2796)

import pygame  # noqa: E402
import paths  # noqa: E402
import safe_area  # noqa: E402

paths.is_mobile = lambda: True                       # the phone layout: frame as tall as the panel's aspect
paths.is_ios = lambda: True                          # and the iOS shop (diamonds only)
safe_area.insets_px = lambda h: (0, 0)
pygame.init()
_info = pygame.display.Info


class _Panel:
    current_w, current_h = PANEL


pygame.display.Info = lambda: _Panel()
import holo  # noqa: E402
import locales  # noqa: E402
import shop as shop_mod  # noqa: E402
import skin_catalog as C  # noqa: E402
import endless as E  # noqa: E402
import endless_qa as Q  # noqa: E402

LANG = sys.argv[1] if len(sys.argv) > 1 else "tr"
OUT = os.path.join(ROOT, "store_assets", "ios_screens", LANG)
os.makedirs(OUT, exist_ok=True)

g = holo.HoloGame(headless=True)
sm = g.save_mgr


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
    f = g.frame
    h = int(round(f.get_height() * PANEL[0] / f.get_width()))
    out = pygame.Surface(PANEL)
    out.fill((10, 12, 18))
    out.blit(pygame.transform.smoothscale(f, (PANEL[0], h)), (0, (PANEL[1] - h) // 2))
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

# 6) the shop
g.open_shop(top=True)
frames(5)
save("08_shop.png")
print("done", OUT)
