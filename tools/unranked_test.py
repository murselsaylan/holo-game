"""Clears the ranking never verified: assisted bests keep their replay and are re-sent with their paid help; clears
with no replay at all are listed as unranked (leaderboard note) instead of silently making the totals disagree.

    python tools/unranked_test.py
"""
import os
import sys
import tempfile

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["HOLO_SAVE_DIR"] = tempfile.mkdtemp(prefix="holo_unranked_")
os.environ["HOLO_SERVER"] = "http://127.0.0.1:1"

import holo  # noqa: E402
import ui  # noqa: E402

ok = True


def check(name, cond, extra=""):
    global ok
    ok &= bool(cond)
    print(("PASS " if cond else "FAIL ") + name, extra)


g = holo.HoloGame(headless=True)
sm = g.save_mgr
sm.data.update(is_profile_set=True, player_name="NOVA", player_country="TR")
res = {"level_total": 30000, "stars": 3, "rank": "S", "time": 20.0, "swaps": 10}
sm.record_level_clear(5, res, [100, 200, 300], [[150, "R"]])
check("assisted best keeps its replay", sm.get_best_taps(5) == [100, 200, 300] and sm.get_best_assists(5) == [[150, "R"]])
sm.record_level_clear(6, dict(res, level_total=20000), [90, 190])
check("clean best has no help", sm.get_best_assists(6) == [])
sm.data["level_stats"]["7"] = {"stars": 3, "best_score": 25000, "rank": "S"}        # an old clear without a replay
sm.data["pending_runs"] = []
n = sm.sync_bests([{"level": 6, "score": 20000, "stars": 3, "rank": "S"}])
q = {r["level"]: r for r in sm.data["pending_runs"]}
check("assisted best is re-sent with its help", 5 in q and q[5].get("assists") == [[150, "R"]], q.get(5))
check("verified level not re-sent", 6 not in q)
check("clear without replay is listed as unranked", sm.unranked_levels == [7], sm.unranked_levels)
sm.sync_bests([{"level": 6, "score": 20000, "stars": 3}, {"level": 7, "score": 24000, "stars": 3}])
check("unranked clears once the server has it", sm.unranked_levels == [])

# the ghost race is opt-in (settings), off by default
g.load_and_play_level(6)
check("no ghost while the setting is off", getattr(g, "ghost", None) is None)
g.settings["ghost_race"] = True
# ghost skips an assisted best
g.load_and_play_level(5)
check("no ghost from an assisted run", getattr(g, "ghost", None) is None)
g.load_and_play_level(6)
check("ghost from a clean run", getattr(g, "ghost", None) is not None)

# leaderboard shows the ranking's own totals and the note
sm.data["unranked"] = [30, 33]
g.open_leaderboard()
g.online.boards["global"] = {"rows": [{"rank": 1, "id": sm.player_id, "name": "NOVA", "country": "TR", "levels": 6,
                                       "score": 50000, "stars": 6}], "me": {"rank": 1, "levels": 6, "score": 50000}}
for _ in range(2):
    g.update(1 / 60.0, (450, 900))
    g.draw()
check("leaderboard draws with the note", True)

# a collected shield is not carried into a restart (the server could not replay it)
g.load_and_play_level(8)
g.sim.shields = 1
g.run_bought = 0
g.restart_level()
check("collected shield not carried", g.sim.shields == 0 and g.assists == [])
print("ALL OK" if ok else "SOME FAILED")
os._exit(0 if ok else 1)
