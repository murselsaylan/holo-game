"""After a between-levels ad the next level starts with the 3-2-1 countdown: the pair holds still until it ends and
touches queued for the ad are dropped (1.0.8 report: the pair was already crashing when the game came back)."""
import os
import sys
import tempfile

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ.setdefault("HOLO_SERVER", "http://127.0.0.1:1")
os.environ.setdefault("HOLO_SAVE_DIR", tempfile.mkdtemp(prefix="holo_test_"))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
import pygame  # noqa: E402
import holo  # noqa: E402
from sim import SIM_DT  # noqa: E402

fails = 0


def check(name, ok):
    global fails
    fails += not ok
    print(("PASS " if ok else "FAIL ") + name)


g = holo.HoloGame(headless=True)
g._present = lambda: None
shown = []
g.ads.available = lambda slot: True
g.ads.show = lambda slot, on_reward=None, on_close=None: shown.append((slot, on_close)) or True
g._ad_due = True
g.load_and_play_level(5)
taps = sorted(g.level.data.raw.get("ref_taps", []))
ti = 0
while g.state == "playing":
    while ti < len(taps) and taps[ti] <= g.sim.n:
        g.swap_pivot()
        ti += 1
    g.update_gameplay(SIM_DT)
check("level 5 won", g.state == "victory")
g._ad_due = True
g.victory_modal.btn_next.callback()
check("the ad was shown instead of starting level 6", len(shown) == 1 and g.state == "victory")
pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(450, 900), button=1))   # a touch meant for the ad
shown[0][1]()                                                                             # the ad closes
check("level 6 is playing", g.state == "playing" and g.level_id == 6)
check("countdown armed", abs(g.resume_timer - 1.2) < 1e-9)
check("touch for the ad dropped", not pygame.event.peek(pygame.MOUSEBUTTONDOWN))
n0 = g.sim.n
for _ in range(60):                      # 1.0 s of frames: still counting down
    g.update(1 / 60, (0, 0))
check("pair holds still during the countdown", g.sim.n == n0)
g.swap_pivot()
check("no swap during the countdown", not g.taps)
for _ in range(30):
    g.update(1 / 60, (0, 0))
check("the level runs after the countdown", g.sim.n > n0)
g.state = "victory"
done = []
g._ad_due = False
g._after_ad(lambda: done.append(1))
check("without an ad owed the action runs at once", done == [1] and len(shown) == 1)
print("ALL OK" if not fails else f"{fails} FAILED")
sys.exit(1 if fails else 0)
