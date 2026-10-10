"""Screenshots of the real game with Olo on the failure screen, several kinds of crash, as one grid image.

    python tools/olo_shots.py [lang] [count]   -> store_assets/olo_shots_<lang>.png
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
os.environ["HOLO_SAVE_DIR"] = tempfile.mkdtemp(prefix="holo_oloshots_")
os.environ["HOLO_SERVER"] = "http://127.0.0.1:1"
PANEL = (1080, 2340)

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
COUNT = int(sys.argv[2]) if len(sys.argv) > 2 else 12
random.seed(int(os.environ.get("OLO_SEED", "3")))
# (tries on the level, progress, seconds alive) - cycles through the kinds of crash
KINDS = [(1, 0.03, 1.0), (2, 0.86, 9.0), (4, 0.40, 5.0), (7, 0.35, 5.0), (1, 0.30, 4.0), (1, 0.45, 6.0)]

g = holo.HoloGame(headless=True)
sm = g.save_mgr
sm.data.update(is_profile_set=True, player_name="NOVA", player_country="TR", howto_seen=True)
sm.language = LANG
locales.set_language(LANG)
g.on_language_change()
for lvl in range(1, 5):
    sm.stats[str(lvl)] = {"stars": 3, "best_score": 5000, "best_time": 12.0, "best_swaps": 6, "rank": "S"}
sm.data["campaign_level"] = 5


def step(seconds, fps=30):
    for _ in range(int(seconds * fps)):
        g.update(1 / fps, (450, 900))
    g.toasts = []
    g.draw()


def main():
    shots = []
    for k in range(COUNT):
        tries, prog, alive = KINDS[k % len(KINDS)]
        g.load_and_play_level(5)
        g.attempts = tries
        step(0.4)
        g.sim.n, g.sim.max_progress, g.sim.dead = int(alive * 60), prog, True
        g.state, g.death_timer = "dying", 0.3
        beat = k // len(KINDS) % 2                                 # some shots show the second pose
        step(0.3 + 0.3 + 2.4 + beat * 3.0)
        top = g.failure_modal.top
        shots.append(g.frame.subsurface(pygame.Rect(0, max(0, top - 420), g.frame.get_width(), 760)).copy())
    w, h = shots[0].get_size()
    cols = 4
    rows = (len(shots) + cols - 1) // cols
    sheet = pygame.Surface((w * cols, h * rows))
    for i, s in enumerate(shots):
        sheet.blit(s, ((i % cols) * w, (i // cols) * h))
    sheet = pygame.transform.smoothscale(sheet, (sheet.get_width() // 2, sheet.get_height() // 2))
    out = os.path.join(ROOT, "store_assets", f"olo_shots_{LANG}.png")
    pygame.image.save(sheet, out)
    print("saved", out)


main()
