"""Previews: the menu, the ranking tabs (general + league card + world/country switch, endless, friends) and the daily screen sections (missions, daily level, team goal), 900x1620,
headless with fake server data: python tools/tab_shots.py [out_dir] [lang]"""
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
import locales  # noqa: E402
import time  # noqa: E402

out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "screenshots")
lang = sys.argv[2] if len(sys.argv) > 2 else "tr"
os.makedirs(out, exist_ok=True)
g = holo.HoloGame(headless=True)
sm = g.save_mgr
sm.data["is_profile_set"] = True
sm.data["player_name"] = "MÜRSEL"
sm.data["level_stats"] = {str(n): {"stars": 3, "best_score": 4000 * n, "best_time": 1.0, "best_swaps": 1, "rank": "A"} for n in range(1, 9)}
locales.set_language(lang) if hasattr(locales, "set_language") else None
g.on_language_change() if hasattr(g, "on_language_change") else None

rk = g.online.ranked
rk.stars = {"ok": True, "stars": 62, "earned": 90, "shield_cost": 12, "shields_left": 5,
            "campaign_cap": 300, "campaign": 80}
rk.daily = {"ok": True, "day": 20000, "level": 37, "ends": int(time.time()) + 3 * 86400 + 5 * 3600, "reward": 10, "reward_3": 5, "state": "open", "claimed": False,
            "run": None, "rank": 0, "total": 3,
            "board": [{"rank": i + 1, "name": n, "country": c, "score": 52000 - i * 700, "stars": 3, "time": 21.5 + i, "me": False}
                      for i, (n, c) in enumerate([("ACE", "DE"), ("LYNX", "TR"), ("KAI", "JP")])]}
for k in ("stars", "daily"):
    rk.state[k] = "ok"
    rk.fetched[k] = 9e18
rk.refresh = lambda *a, **k: None


g.online.status = "ok"
cw = g.online.crowd
cw.refresh = lambda *a, **k: None
cw.data = {"ok": True, "week": "2026-W43", "goal": 3000, "total": 1710, "contributors": 214, "mine": 18, "min_contrib": 3,
           "ends": int(time.time()) + 3 * 86400 + 5 * 3600,
           "tiers": [{"tier": 1, "pct": 33, "need": 990, "reward": 10, "reached": True, "claimed": False, "claimable": True},
                     {"tier": 2, "pct": 66, "need": 1980, "reward": 20, "reached": False, "claimed": False, "claimable": False},
                     {"tier": 3, "pct": 100, "need": 3000, "reward": 40, "reached": False, "claimed": False, "claimable": False}],
           "wlevel": {"level": 3, "pct": 40.0, "cleared": False, "claimed": False, "reward": 15}}
cw.state = "ok"
names = ["NEO", "CYBER", "PULSE", "VORTEX", "ECHO", "SPARK", "NOVA", "MÜRSEL", "ZED", "MIRA"]
rows = [{"rank": i + 1, "id": "x%d" % i if n != "MÜRSEL" else sm.player_id, "name": n, "country": "TR", "levels": 60 - i * 4,
         "score": 3_000_000 - i * 180_000, "stars": 150 - i * 9} for i, n in enumerate(names)]
g.online.boards["global"] = {"rows": rows, "me": {"rank": 8}}
g.online.boards["endless"] = {"rows": [dict(r, metres=900 - i * 50, points=900 - i * 50) for i, r in enumerate(rows)], "me": {"rank": 8}, "week": "W43"}
g.online.friends = {"friends": [], "inbox": [], "help": []}
g.online.friends_status = "ok"
g.online.friends_refresh = lambda *a, **k: None
g.online.fetch = lambda *a, **k: None


def frames(n=3):
    for _ in range(n):
        g.update(1 / 60.0, (450, 800))
        g.draw()


def shot(name):
    g.toasts.clear()
    frames(3)
    pygame.image.save(g.frame, os.path.join(out, f"pg_{name}_{lang}.png"))
    print(os.path.join(out, f"pg_{name}_{lang}.png"), g.frame.get_size())


g.state = "menu"
g.menu_ui.set_enter(1.0)
shot("0_menu")
lb = g.leaderboard_ui
for i, sc in enumerate(("global", "endless", "friends")):
    g.state = "menu"
    g.open_leaderboard(sc)
    lb.show_world()
    shot(f"1{i}_rank_{sc}")
g.open_leaderboard("global")
lb.show_country()
shot("16_rank_global_country")
lb.show_world()
for i, sc in enumerate(("missions", "daily", "crowd")):
    g.state = "menu"
    g._open_daily_missions(sc)
    shot(f"2{i}_daily_{sc}")
g.open_ranked("daily")
g.daily_ui._panel()._ask_daily()
shot("23_daily_confirm")
g.daily_ui._panel().confirm = False
