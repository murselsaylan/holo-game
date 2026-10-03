"""Lost level bests are sent again: real HTTP server + real OnlineClient + SaveManager.

A clear the server refused while it ran another level version (409) stays on the phone with its replay; the next
bests sync queues it again (as a background run the victory screen ignores) and the server records it. A run the
server refuses again is not re-sent forever. Also: input faster than MIN_TAP_GAP never reaches a recorded run.

    python tools/resync_test.py
"""
import json
import os
import sys
import tempfile
import threading
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["HOLO_SAVE_DIR"] = tempfile.mkdtemp(prefix="holo_resync_")

from server import leaderboard_server as srv  # noqa: E402
import save_manager as smod  # noqa: E402
from online import OnlineClient  # noqa: E402
from sim import LevelData, replay, MIN_TAP_GAP  # noqa: E402

httpd = srv.make_server(0, os.path.join(tempfile.mkdtemp(), "t.db"), "127.0.0.1")
threading.Thread(target=httpd.serve_forever, daemon=True).start()
base = f"http://127.0.0.1:{httpd.server_address[1]}"

ok = True


def check(name, cond, extra=""):
    global ok
    ok &= bool(cond)
    print(("PASS " if cond else "FAIL ") + name, extra)


def wait(client, cond, sec=20):
    t0 = time.time()
    while time.time() - t0 < sec:
        client.poll()
        if cond():
            return True
        time.sleep(0.05)
    return False


def device(name):
    sm = smod.SaveManager.__new__(smod.SaveManager)
    sm._lock = threading.RLock()
    sm.cloud_dirty = False
    sm.data = smod._default_save()
    sm.data.update(player_name=name, player_country="TR", is_profile_set=True)
    sm.save = lambda: None
    return sm


def ref(level):
    return json.load(open(os.path.join(ROOT, "levels", f"level{level}.json"), encoding="utf-8"))["ref_taps"]


a = device("RESYNC")
ca = OnlineClient(a, base)
ca.register()
check("registered", wait(ca, lambda: ca._registered))

# level 1: accepted normally
res1 = replay(LevelData.load(1), ref(1))[1]
a.record_level_clear(1, res1, ref(1))
ca.submit(1, ref(1), LevelData.load(1).digest)
check("level 1 accepted", wait(ca, lambda: ca.last_submit and ca.last_submit.get("ok")))

# level 2: cleared while "the server had another level version" -> 409, dropped, but kept locally with its replay
res2 = replay(LevelData.load(2), ref(2))[1]
a.record_level_clear(2, res2, ref(2))
ca.submit(2, ref(2), "deadbeef00")
check("level 2 refused (409) and reported as rejected",
      wait(ca, lambda: ca.last_submit and ca.last_submit.get("rejected")), ca.last_submit)
check("rejected run left the queue", not a.data.get("pending_runs"))

# level 3: a replay the server will never accept (not a clear) must be tried once only
a.stats["3"] = {"stars": 3, "best_score": 99999, "best_taps": [300, 600]}

# next start: register -> bests sync -> the missing levels are queued again in the background
ca.last_submit = None
ca._registered = False
ca.register()
wait(ca, lambda: False, sec=4)
check("background re-sends never touch the victory screen", ca.last_submit is None, ca.last_submit)
check("level 2 recorded after the re-send", a.stats["2"].get("best_score") == res2["level_total"] and
      a.data.get("resync_tried", {}).get("2") == LevelData.load(2).digest, a.stats.get("2"))
tried_before = dict(a.data.get("resync_tried", {}))
check("the bad level 3 replay was tried once", "3" in tried_before)
ca._registered = False
ca.register()
wait(ca, lambda: False, sec=3)
check("and is not queued again", not any(r["level"] == 3 for r in a.data.get("pending_runs", [])))

# the server now really has level 2: a fresh device of the same account sees it in its bests
b = device("RESYNC")
b.data["player_id"], b.data["player_secret"] = a.player_id, a.player_secret
cb = OnlineClient(b, base)
cb.register()
check("server holds levels 1 and 2", wait(cb, lambda: {"1", "2"} <= set(b.stats)), sorted(b.stats))

# MIN_TAP_GAP: holo refuses a swap sooner than MIN_TAP_GAP ticks after the last one
import holo  # noqa: E402
g = holo.HoloGame(headless=True)
g.load_and_play_level(1)
g.state = "playing"
for _ in range(10):
    g.sim.step()
g.swap_pivot()
g.sim.step()
g.swap_pivot()                                   # a bounced touch one tick later
for _ in range(MIN_TAP_GAP):
    g.sim.step()
g.swap_pivot()
gaps = [b2 - a2 for a2, b2 in zip(g.taps, g.taps[1:])]
check("bounced touch ignored, next real tap kept", len(g.taps) == 2 and min(gaps) >= MIN_TAP_GAP, g.taps)

print("ALL OK" if ok else "SOME FAILED")
os._exit(0 if ok else 1)
