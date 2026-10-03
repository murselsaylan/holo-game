"""Account recovery end to end: real HTTP server + real OnlineClient + SaveManager.

Device A plays, gets its cloud copy uploaded and asks for a recovery code; device B (a fresh install) restores with
that code and must become the same pilot with the same progress. An old account without a cloud copy is rebuilt
from its verified leaderboard bests.

    python tools/recovery_test.py
"""
import json
import os
import sys
import tempfile
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["HOLO_SAVE_DIR"] = tempfile.mkdtemp(prefix="holo_rec_")

from server import leaderboard_server as srv  # noqa: E402
import save_manager as smod  # noqa: E402
from online import OnlineClient  # noqa: E402

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
    """A save of its own (in memory, never written to the shared test dir)."""
    sm = smod.SaveManager.__new__(smod.SaveManager)
    sm._lock = threading.RLock()
    sm.cloud_dirty = False
    sm.data = smod._default_save()
    sm.data.update(player_name=name, player_country="TR", is_profile_set=True)
    sm.save = lambda: None
    return sm


lv1 = json.load(open(os.path.join(ROOT, "levels", "level1.json"), encoding="utf-8"))

# ---- device A: plays, uploads its save, gets a code
a = device("ALPHA")
a.data["diamonds"] = 777
a.data["level_stats"] = {"1": {"stars": 3, "best_score": 12345}}
a.data["campaign_level"] = 2
ca = OnlineClient(a, base)
ca.register()
ca.submit(1, lv1["ref_taps"])
check("A: level 1 accepted", wait(ca, lambda: ca.last_submit and ca.last_submit.get("ok")))
ca.cloud_save(a.export_cloud())
ca.request_code()
check("A: recovery code", wait(ca, lambda: (ca.recovery or {}).get("state") == "ok"), ca.recovery)
code = (ca.recovery or {}).get("code", "")

# ---- device B: a fresh install restores with the code
b = device("NEWBIE")
old_id = b.player_id
cb = OnlineClient(b, base)
cb.restore(code.lower())
check("B: restore found the account", wait(cb, lambda: (cb.restore_state or {}).get("state") in ("ok", "fail")) and
      cb.restore_state["state"] == "ok", cb.restore_state and cb.restore_state.get("reason"))
if cb.restore_state and cb.restore_state.get("state") == "ok":
    b.import_cloud(cb.restore_state["payload"])
check("B: became pilot ALPHA", b.player_id == a.player_id and b.player_secret == a.player_secret and b.player_name == "ALPHA"
      and b.player_id != old_id)
check("B: got A's progress", b.data.get("diamonds") == 777 and b.data.get("campaign_level") == 2 and "1" in b.stats)
check("B: nothing of the throwaway identity left", not b.data.get("pending_runs") and b.is_profile_set)

# the restored device can keep playing as ALPHA
cb.submit(1, lv1["ref_taps"])
check("B: submits as ALPHA", wait(cb, lambda: cb.last_submit and cb.last_submit.get("ok")), cb.last_submit)

# ---- an old account (no cloud copy): progress rebuilt from its leaderboard bests
c = device("OLDIE")
cc = OnlineClient(c, base)
cc.register()
cc.submit(1, lv1["ref_taps"])
check("C: level 1 accepted", wait(cc, lambda: cc.last_submit and cc.last_submit.get("ok")))
cc.request_code()
check("C: code", wait(cc, lambda: (cc.recovery or {}).get("state") == "ok"))
d = device("OTHER")
cd = OnlineClient(d, base)
cd.restore(cc.recovery["code"])
check("D: restore without a cloud copy", wait(cd, lambda: (cd.restore_state or {}).get("state") == "ok"))
d.import_cloud(cd.restore_state["payload"])
check("D: campaign rebuilt from bests", d.player_id == c.player_id and d.stats.get("1", {}).get("stars") == 3
      and d.data["campaign_level"] == 2, d.stats)

# ---- wrong codes
e = device("GUESS")
ce = OnlineClient(e, base)
ce.restore("AAAA-BBBB-CCCC")
check("wrong code -> unknown", wait(ce, lambda: (ce.restore_state or {}).get("state") == "fail") and
      ce.restore_state["reason"] == "unknown", ce.restore_state)

print("ALL OK" if ok else "SOME FAILED")
os._exit(0 if ok else 1)
