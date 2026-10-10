"""Records the real game (headless, phone size) with Olo on: a few crashes of different kinds, each failure screen
for a few seconds - to see the mascot exactly as players will.

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
random.seed(7)
FPS = 30
# (attempts on the level, progress reached, seconds alive, seconds on the failure screen)
SCENES = [(1, 0.03, 1.0, 6.5), (2, 0.86, 9.0, 6.5), (4, 0.40, 5.0, 6.5), (7, 0.35, 5.0, 6.5), (1, 0.30, 4.0, 6.5)]
DEBUG = "--debug" in sys.argv

g = holo.HoloGame(headless=True)
sm = g.save_mgr
sm.data.update(is_profile_set=True, player_name="NOVA", player_country="TR", howto_seen=True)
sm.language = LANG
locales.set_language(LANG)
g.on_language_change()
for lvl in range(1, 5):
    sm.stats[str(lvl)] = {"stars": 3, "best_score": 5000, "best_time": 12.0, "best_swaps": 6, "rank": "S"}
sm.data["campaign_level"] = 5


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

    for tries, prog, alive, hold in SCENES:
        g.load_and_play_level(5)
        g.attempts = tries
        shoot(0.6)
        g.sim.n = int(alive * 60)
        g.sim.max_progress = prog
        g.sim.dead = True
        g.state, g.death_timer = "dying", 0.35
        shoot(0.5 + hold)
        if DEBUG:
            print("scene", tries, g.state, g.olo.active, round(g.olo.t, 2), g.olo.beats[:1])
    wr.close()
    print("saved", out)


main()
