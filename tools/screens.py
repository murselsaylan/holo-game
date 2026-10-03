"""Render every screen headlessly to screenshots/ui_*.png"""
import os, sys, tempfile, random
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["HOLO_SAVE_DIR"] = tempfile.mkdtemp(prefix="holo_shots_")
os.environ["HOLO_SERVER"] = "http://127.0.0.1:1"
import pygame
import holo
from sim import SIM_DT, compute_result

SH = os.path.join(ROOT, "screenshots")
os.makedirs(SH, exist_ok=True)

def shot(game, name):
    for _ in range(3):
        game.update(1 / 60.0, (450, 800))
    game.draw()
    pygame.image.save(game.frame, os.path.join(SH, f"ui_{name}.png"))

g = holo.HoloGame(headless=True)
sm = g.save_mgr
sm.data["player_name"] = "KRONOS"; sm.data["player_country"] = "TR"; sm.data["is_profile_set"] = True
# fake progress
for i in range(1, 24):
    sm.stats[str(i)] = {"stars": 3 if i % 3 else 2, "best_score": 20000 + i * 900, "best_time": 12.0 + i, "best_swaps": 10 + i, "rank": "A"}
sm.data["campaign_level"] = 24
sm._check_skin_unlocks()
g.online.status = "ok"
rows = []
names = ["NEO", "CYBER", "PULSE", "VORTEX", "ECHO", "SPARK", "NOVA", "KRONOS", "ZED", "MIRA", "ATLAS", "IVY"]
ccs = ["TR", "JP", "US", "DE", "GB", "KR", "GX", "TR", "FR", "BR", "CA", "SE"]
for i, (n, c) in enumerate(zip(names, ccs)):
    rows.append({"rank": i + 1, "id": "x%d" % i if n != "KRONOS" else sm.player_id, "name": n, "country": c, "levels": 60 - i * 4, "score": 3_000_000 - i * 180_000, "stars": 150 - i * 9})
g.online.boards["global"] = {"rows": rows, "me": {"rank": 8, "country_rank": 2}}
g.online.rank_info = {"rank": 8, "country_rank": 2}

g.profile_modal = None; g.state = "menu"; g.menu_ui.build()
shot(g, "menu")
g.open_level_select(); shot(g, "levels")
g.level_select_ui.scroll.y = 2200; shot(g, "levels_scrolled")
g.open_leaderboard(); g.online.status = "ok"; g.online.boards["global"] = {"rows": rows, "me": {"rank": 8}}; shot(g, "leaderboard")
g.open_skins(); shot(g, "skins")
g.open_shop(); shot(g, "shop")
g.open_settings("menu"); shot(g, "settings")
g.close_settings()
g.open_profile("menu"); shot(g, "profile")
g.close_profile()
for lid in (3, 30):
    g.attempts = 1
    g.load_and_play_level(lid)
    for _ in range(140):
        g.update_gameplay(SIM_DT); g._update_camera(SIM_DT)
    if lid == 3:
        g.swap_pivot()
    shot(g, f"play{lid}")
g.state = "paused"; shot(g, "pause")
g.state = "playing"
# force a death for the failure modal
s = g.sim
s.orbs[0].x = -50
for _ in range(400):
    g.update_gameplay(SIM_DT)
    if g.state != "playing": break
for _ in range(60):
    g.update(1/60.0, (450, 800))
shot(g, "failed")
# victory
g.load_and_play_level(8)
taps = sorted(g.level.data.raw["ref_taps"]); ti = 0
while g.state == "playing":
    while ti < len(taps) and taps[ti] <= g.sim.n:
        g.swap_pivot(); ti += 1
    g.update_gameplay(SIM_DT); g._update_camera(SIM_DT)
for _ in range(90):
    g.update(1/60.0, (450, 800))
g.online.last_submit = {"ok": True, "world_rank": 1234, "country_rank": 56}
shot(g, "victory")
print("screens done")
