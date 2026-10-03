"""The endless climb inside the real game loop, against a local copy of the ranking server.

    python tools/endless_game_test.py

Locked before level 10; opens from the menu; plays (the world window moves, stages are rendered in slices, the camera
follows); a death opens the result card; the climb is submitted and the server's height equals the game's; the weekly
board lists it; "again" starts a NEW map (another nonce); the menu leaves the mode.
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
sys.path.insert(0, os.path.join(ROOT, "tools"))
os.environ["HOLO_SAVE_DIR"] = tempfile.mkdtemp(prefix="holo_endless_")

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
sm.data.update(is_profile_set=True, player_name="CLIMBER", player_country="TR")
g.online.register()


def frames(n):
    for _ in range(n):
        g.update(SIM_DT, (450, 900))
        g.draw()


check("locked before level 10", g.open_endless() is False and g.endless_run is None)
for lv in range(1, 11):
    sm.stats[str(lv)] = {"stars": 3, "best_score": 1000}
g.menu_ui.build()
check("unlocked after level 10", sm.endless_unlocked and any(b.text == ui.t("endless_btn") for b in g.menu_ui.buttons))
check("opens", g.open_endless() and g.state == "playing" and isinstance(g.level, holo.EndlessLevel))
first_nonce = g.endless_nonce

# play with the bot's taps for a while: the window must move and the renderer keep up
import endless_qa as Q  # noqa: E402
best, taps = Q.climb_bot(E.seed_of(g.endless_week, g.endless_nonce), 2, time.time() + 60)
taps = sorted(taps)
run = g.endless_run
ti = 0
t0 = time.time()
worst = 0.0
for _ in range(60 * 150):
    if g.state != "playing":
        break
    while ti < len(taps) and taps[ti] <= run.n:
        g.sim.swap()
        g.taps.append(run.n)
        ti += 1
    a = time.perf_counter()
    g.update(SIM_DT, (450, 900))
    g.draw()
    worst = max(worst, time.perf_counter() - a)
    if ti >= len(taps) and run.n > taps[-1] + 30 and not run.dead:
        run.sim.dead = True                       # end the climb here (the bot's run is done)
        run.sim._ev("die", run.sim.pivot.x, run.sim.pivot.y)
check("the world window moved on", run.w0 >= 1 or run.stage >= 1, f"w0={run.w0} stage={run.stage} m={run.metres}")
check("frames stay light while stages are prepared", worst < 0.25, f"worst frame {worst * 1000:.1f} ms")
frames(90)
check("death offers a paid revive first", g.state == "failed" and isinstance(g.failure_modal, ui.EndlessReviveModal))
g.failure_modal.on_finish()                       # "finish the climb"
frames(3)
check("finishing opens the result card", g.state == "failed" and isinstance(g.failure_modal, ui.EndlessResultModal))
metres, points, stars = run.metres, run.points, run.stars
deadline = time.time() + 30
while time.time() < deadline and not (g.online.endless_result and g.online.endless_result.get("ok")):
    frames(2)
res = g.online.endless_result or {}
check("the server ranked the climb", res.get("ok") and res.get("rank") == 1, res)
check("server height == game height", res.get("metres") == metres, f"{res.get('metres')} vs {metres}")
check("server points == game points (height + stars)", res.get("points") == points, f"{res.get('points')} vs {points} ({stars} stars)")
check("week best stored (points)", sm.endless_week_best(g.endless_week) == points)
check("the climb's stars went to the star wallet", sm.star_coins == stars, f"{sm.star_coins} vs {stars}")
g.failure_modal.draw(g.frame)

g.open_leaderboard("endless")
deadline = time.time() + 20
while time.time() < deadline and not (g.online.boards.get("endless") or {}).get("rows"):
    frames(2)
rows = (g.online.boards.get("endless") or {}).get("rows") or []
check("weekly board lists the climb", rows and rows[0]["name"] == "CLIMBER" and rows[0]["points"] == points, rows[:1])
frames(3)

g.open_endless()
check("again = a new map", g.endless_nonce != first_nonce and g.endless_run.world.ids[:3] != [] )
frames(30)
g.open_menu()
check("menu leaves the endless mode", g.endless_run is None and g.state == "menu")

print("ALL OK" if ok else "SOME FAILED")
os._exit(0 if ok else 1)
