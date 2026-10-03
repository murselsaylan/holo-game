"""Paid help in the endless climb (1.0.6): a death offers a revive, the revive is the slow-spin shielded one ("R2"),
a shield can be bought from the HUD, and the climb with its help is replayed by the (local copy of the) ranking server
to the same points. Also: the revive limit, and the campaign revive is R2 too.

    python tools/endless_help_test.py
"""
import os
import sys
import tempfile
import threading
import time

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["HOLO_SAVE_DIR"] = tempfile.mkdtemp(prefix="holo_help_")

from server import leaderboard_server as srv  # noqa: E402

httpd = srv.make_server(0, os.path.join(tempfile.mkdtemp(), "t.db"), "127.0.0.1")
threading.Thread(target=httpd.serve_forever, daemon=True).start()
os.environ["HOLO_SERVER"] = f"http://127.0.0.1:{httpd.server_address[1]}"

import holo  # noqa: E402
import endless as E  # noqa: E402
import ui  # noqa: E402
from sim import SIM_DT  # noqa: E402

ok = True


def check(name, cond, extra=""):
    global ok
    ok &= bool(cond)
    print(("PASS " if cond else "FAIL ") + name, extra)


g = holo.HoloGame(headless=True)
sm = g.save_mgr
sm.data.update(is_profile_set=True, player_name="HELPER", player_country="TR", diamonds=500)
sm.wallet = None                                   # local wallet: spends resolve at once
g.online.register()
for lv in range(1, 11):
    sm.stats[str(lv)] = {"stars": 3, "best_score": 1000}


def frames(n):
    for _ in range(n):
        g.update(SIM_DT, (450, 900))
        g.draw()


def die():
    """A real crash: tap every few steps (each tap flips the swing) until the pair hits something."""
    import random
    rng = random.Random(len(g.assists))
    nxt = 0
    for k in range(60 * 90):
        if g.state != "playing":
            break
        if k >= nxt:
            g.swap_pivot()
            nxt = k + rng.choice((6, 11, 23, 70, 95))
        frames(1)
    frames(60)                                      # the death animation


g.open_endless()
frames(30)
g.use_hud_shield()                                 # a shield from the HUD (stock or 10 diamonds)
check("a shield can be put on in the climb", g.sim.shields == 1 and g.assists and g.assists[-1][1] == "S", g.assists)
die()
check("death offers a revive", isinstance(g.failure_modal, ui.EndlessReviveModal), type(g.failure_modal).__name__)
before = sm.diamonds
g.revive_run()
frames(2)
s = g.sim
check("revive charged and resumed", g.state == "playing" and sm.diamonds == before - holo.REVIVE_COST, (g.state, sm.diamonds))
check("the revive is the slow-spin shielded one", g.assists[-1][1] == "R2" and s.guard and s.spin_ramp < 0.2,
      (g.assists[-1], s.guard, s.spin_ramp))
frames(90)
check("still shielded until a tap", s.guard and not s.dead)
check("spinning back up slowly (full speed after 2.5 s)", 0.25 < s.spin_ramp < 1.0, s.spin_ramp)
g.swap_pivot()
check("the tap ends the revive shield", not s.guard)
for k in range(E.MAX_REVIVES):
    die()
    if isinstance(g.failure_modal, ui.EndlessReviveModal) and k < E.MAX_REVIVES - 1:
        g.revive_run()
        frames(2)
check("after the last revive the climb just ends", isinstance(g.failure_modal, ui.EndlessResultModal),
      type(g.failure_modal).__name__)
run = g.endless_run
helps = [a for a in g.assists]
deadline = time.time() + 30
while time.time() < deadline and not (g.online.endless_result and "ok" in g.online.endless_result):
    frames(2)
res = g.online.endless_result or {}
check("the server replays the climb with its help", res.get("ok") and res.get("points") == run.points,
      (res.get("points"), run.points, helps))
check("at most MAX_REVIVES revives", sum(1 for a in helps if a[1] != "S") == E.MAX_REVIVES, helps)

# the campaign revive is R2 as well
g.load_and_play_level(5)
g.state = "playing"
die()
if g.state == "failed":
    g.revive_run()
    frames(2)
    check("campaign revive is R2", g.assists and g.assists[-1][1] == "R2" and g.sim.guard, g.assists)
else:
    check("campaign run died for the revive check", False, g.state)
print("ALL OK" if ok else "SOME FAILED")
os._exit(0 if ok else 1)
