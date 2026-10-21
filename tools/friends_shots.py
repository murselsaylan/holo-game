"""Preview images of the friends screens (headless): python tools/friends_shots.py [out_dir] [lang]"""
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
import ui  # noqa: E402

out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "store_assets", "friends_ui")
lang = sys.argv[2] if len(sys.argv) > 2 else "tr"
os.makedirs(out, exist_ok=True)
g = holo.HoloGame(headless=True)
sm = g.save_mgr
sm.data["is_profile_set"] = True
sm.data["player_name"] = "MÜRSEL"
sm.data["level_stats"] = {str(n): {"stars": 3, "best_score": 4000 * n, "best_time": 1.0, "best_swaps": 1, "rank": "A"} for n in range(1, 9)}
locales.set_language(lang) if hasattr(locales, "set_language") else None
g.on_language_change() if hasattr(g, "on_language_change") else None
g.online.friends_op = lambda *a, **k: None
g.online.friends = {
    "ok": True, "code": "K7QM-3XPD", "max": 30, "credits": {"shield": 1, "revive": 1}, "asked_today": 0,
    "friends": [
        {"id": "f" * 32, "name": "BOB", "country": "TR", "levels": 24, "score": 91234, "stars": 60, "status": "friend", "sent": ["poke"]},
        {"id": "e" * 32, "name": "CARA", "country": "DE", "levels": 12, "score": 40111, "stars": 30, "status": "friend", "sent": []},
        {"id": "b" * 32, "name": "EMRE", "country": "TR", "levels": 5, "score": 9000, "stars": 14, "status": "friend", "sent": []},
        {"id": "d" * 32, "name": "DENIZ", "country": "TR", "levels": 1, "score": 1, "stars": 0, "status": "incoming", "sent": []},
        {"id": "c" * 32, "name": "EVE", "country": "TR", "levels": 1, "score": 1, "stars": 0, "status": "outgoing", "sent": []}],
    "inbox": [{"id": 11, "from": "f" * 32, "from_name": "BOB", "kind": "gift", "item": "diamond", "amount": 5, "level": 0},
              {"id": 12, "from": "e" * 32, "from_name": "CARA", "kind": "gift", "item": "shield", "amount": 1, "level": 0},
              {"id": 13, "from": "f" * 32, "from_name": "BOB", "kind": "challenge", "item": "", "amount": 5, "level": 10}],
    "help": [{"id": 21, "from": "e" * 32, "from_name": "CARA", "kind": "help", "item": "shield", "amount": 1, "level": 9}]}
g.online.friends_status = "ok"
g.online.credits = {"shield": 1, "revive": 1}


def frames(n=3):
    for _ in range(n):
        g.update(1 / 60.0, (450, 800))
        g.draw()


def shot(name):
    frames(3)
    pygame.image.save(g.frame, os.path.join(out, f"{name}_{lang}.png"))
    print("saved", name)


g.state = "leaderboard"
g.leaderboard_ui.set_scope("friends")
shot("1_friends_tab")
g.leaderboard_ui.country_only = True
shot("2_friends_tab_country")
g.leaderboard_ui.country_only = False
g.leaderboard_ui._open_row(g.leaderboard_ui._rows()[1])
shot("3_friend_actions")
g.leaderboard_ui.sel = None
g.leaderboard_ui.set_scope("global")
shot("4_world_with_country_button")
g.open_friends()
shot("5_friends_window")
g.close_friends()
g.attempts = 4
g.load_and_play_level(9)
frames(2)
g.online.friends_op = lambda *a, **k: None
s = g.sim
s.dead = True
g.failure_modal = ui.FailureModal(9, 45, 1, 1, 4, lambda: None, lambda: None, lambda: None, save_mgr=sm, shop=g.shop,
                                  on_revive=lambda: None, on_endless=lambda: None)
g.failure_modal.on_help = lambda: None
g.failure_modal.help_probe = lambda: (True, False)
g.state = "failed"
shot("6_failure_help_button")
