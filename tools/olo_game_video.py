"""Records the real game (headless, phone size) with Olo on, everywhere he shows up: the menu hello, a cleared level,
the endless climb's crash and end, and a few failure screens - to see the mascot exactly as players will.

    python tools/olo_game_video.py [lang]   -> store_assets/olo_game_<lang>.mp4
"""
import os
import random
import sys
import tempfile

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["HOLO_OLO"] = "1"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["HOLO_SAVE_DIR"] = tempfile.mkdtemp(prefix="holo_ologame_")
os.environ["HOLO_SERVER"] = "http://127.0.0.1:1"
PANEL = (1080, 2340)

import numpy as np  # noqa: E402
import pygame  # noqa: E402
import paths  # noqa: E402
import safe_area  # noqa: E402

paths.is_mobile = lambda: True
safe_area.insets_px = lambda h: (0, 0)
pygame.init()


class _Panel:
    current_w, current_h = PANEL


pygame.display.Info = lambda: _Panel()
import holo  # noqa: E402
import locales  # noqa: E402

LANG = sys.argv[1] if len(sys.argv) > 1 else "tr"
random.seed(int(os.environ.get("OLO_SEED", "11")))
FPS = 30

g = holo.HoloGame(headless=True)
sm = g.save_mgr
sm.data.update(is_profile_set=True, player_name="NOVA", player_country="TR", howto_seen=True)
sm.language = LANG
locales.set_language(LANG)
g.on_language_change()
for lvl in range(1, 5):
    sm.stats[str(lvl)] = {"stars": 3, "best_score": 5000, "best_time": 12.0, "best_swaps": 6, "rank": "S"}
sm.data["campaign_level"] = 5
type(sm).endless_unlocked = property(lambda self: True)
g._maybe_login_popup = lambda: None                 # the daily reward popup would cover the menu


def main():
    import imageio_ffmpeg
    out = os.path.join(ROOT, "store_assets", f"olo_game_{LANG}.mp4")
    ow, oh = 540, 1170
    wr = imageio_ffmpeg.write_frames(out, (ow, oh), fps=FPS, quality=8, macro_block_size=2)
    wr.send(None)

    def shoot(seconds):
        for _ in range(int(seconds * FPS)):
            g.update(1 / FPS, (450, 900))
            g.toasts = []
            g.draw()
            fr = pygame.transform.smoothscale(g.frame, (ow, oh))
            wr.send(np.ascontiguousarray(pygame.surfarray.array3d(fr).swapaxes(0, 1)))

    def crash(tries, prog, alive, hold):
        g.load_and_play_level(5)
        g.attempts = tries
        shoot(0.6)
        g.sim.n, g.sim.max_progress, g.sim.dead = int(alive * 60), prog, True
        g.state, g.death_timer = "dying", 0.35
        shoot(0.5 + hold)

    # 1. the menu: first meeting (three poses), then sinks away
    g._olo_menu_done = False
    g.open_menu()
    shoot(12.0)
    # 2. a level cleared after a fight
    g.load_and_play_level(5)
    shoot(0.8)
    g.attempts = 6
    g._on_win()
    shoot(6.5)
    # 3. failure screens
    crash(1, 0.03, 1.0, 4.5)
    crash(2, 0.88, 9.0, 4.5)
    # 4. the endless climb: a crash with the revive offer, then the end
    g.open_endless()
    shoot(1.0)
    g.sim.dead = True
    g.state, g.death_timer = "dying", 0.3
    shoot(5.0)
    g._endless_over()
    shoot(5.0)
    # 5. the menu again, another day
    g._olo_menu_done = False
    sm.data["olo_seen"] = sm.data.get("olo_seen", 0) - 86400
    g.open_menu()
    shoot(7.0)
    wr.close()
    print("saved", out)


main()
