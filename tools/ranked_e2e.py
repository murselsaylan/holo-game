"""End-to-end check of the star wallet and daily level: the real game client (online.py + ranked_online.py)
against the real server code (supabase/functions/scores/handler.ts + ranked.ts on an in-memory store, served by Deno).

    python tools/ranked_e2e.py          (needs deno: pip install deno)

SCORES_DIR overrides the folder the server runs from (a copy of supabase/functions/scores).
"""
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
with socket.socket() as so:
    so.bind(("127.0.0.1", 0))
    PORT = so.getsockname()[1]
os.environ["HOLO_SAVE_DIR"] = tempfile.mkdtemp(prefix="holo_e2e_")
os.environ["HOLO_SERVER"] = f"http://127.0.0.1:{PORT}"
os.environ["SDL_VIDEODRIVER"] = "dummy"

import secrets  # noqa: E402

import online  # noqa: E402
import save_manager  # noqa: E402
import sim  # noqa: E402
import star_road  # noqa: E402

fails = []


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


deno = shutil.which("deno")
if not deno:
    print("deno not found")
    sys.exit(2)
cwd = os.environ.get("SCORES_DIR") or os.path.join(ROOT, "supabase", "functions", "scores")
srv = subprocess.Popen([deno, "run", "-A", "--no-check", "tests/serve_ranked.ts", str(PORT)], cwd=cwd,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
try:
    t0 = time.time()
    while time.time() - t0 < 60:
        try:
            socket.create_connection(("127.0.0.1", PORT), timeout=0.5).close()
            break
        except OSError:
            time.sleep(0.3)
    else:
        raise SystemExit("server did not start")

    sm = save_manager.SaveManager()
    sm.data["player_id"] = secrets.token_hex(16)
    sm.data["player_secret"] = secrets.token_hex(24)
    sm.data["player_name"] = "ALICE"
    sm.data["player_country"] = "TR"
    sm.data["is_profile_set"] = True
    oc = online.OnlineClient(sm)
    sm.wallet = oc
    rk = oc.ranked

    def wait(cond, secs=15):
        t = time.time()
        while time.time() - t < secs:
            oc.poll()
            rk.poll()
            if cond():
                return True
            time.sleep(0.05)
        return False

    oc.register()
    oc.wallet_sync()
    check("wallet open", wait(lambda: oc._wallet_open))

    # --- star wallet: a verified clear brings its stars
    raw = json.load(open(os.path.join(ROOT, "levels", "level3.json")))
    ref, dg = raw["ref_taps"], sim.LevelData(raw).digest
    oc.submit(3, ref, dg)
    wait(lambda: oc.last_submit is not None or True, 3)
    time.sleep(1.0)
    rk.refresh("stars")
    check("stars reply arrives", wait(lambda: rk.stars is not None))
    n = rk.stars["stars"]
    check(f"the clear's stars are in the wallet ({n})", 1 <= n <= 3 and sm.star_coins == n)
    check("no star road in the reply any more", "road" not in rk.stars and "chests" not in rk.stars)

    # --- no league any more
    check("the client has no league state", not hasattr(rk, "league"))

    # --- daily level: start (one try), too-fast submit refused, second start is not first
    rk.refresh("daily")
    check("daily reply", wait(lambda: rk.daily is not None))
    lvl = rk.daily["level"]
    check("daily level in range", star_road.DAILY_FIRST <= lvl <= star_road.DAILY_LAST)
    res = {}
    rk.daily_start(lambda r: res.update(s1=r))
    check("daily start grants the try", wait(lambda: "s1" in res) and res["s1"].get("first") is True)
    rk.daily_start(lambda r: res.update(s2=r))
    check("a second start is not a new try", wait(lambda: "s2" in res) and res["s2"].get("first") is False)
    raw = json.load(open(os.path.join(ROOT, "levels", f"level{lvl}.json")))
    rk.daily_submit(raw["ref_taps"], sim.LevelData(raw).digest, lambda r: res.update(sub=r))
    check("an instant clear is refused as too fast", wait(lambda: "sub" in res) and res["sub"].get("code") == 422)
    # the honest submit: the server wants the level's real play time to have passed since the start (real clock here)
    ok = None
    for _ in range(24):
        res.pop("sub", None)
        rk.daily_submit(raw["ref_taps"], sim.LevelData(raw).digest, lambda r: res.update(sub=r))
        wait(lambda: "sub" in res)
        if res["sub"].get("ok"):
            ok = res["sub"]
            break
        time.sleep(5)
    check("the honest clear is accepted once the play time has passed", ok is not None and ok.get("state") == "done")
    if ok:
        bal = sm.diamonds
        check("reward paid once (+%d..%d diamonds)" % (star_road.DAILY_REWARD, star_road.DAILY_REWARD + star_road.DAILY_REWARD_3STAR),
              star_road.DAILY_REWARD <= ok["added"] <= star_road.DAILY_REWARD + star_road.DAILY_REWARD_3STAR)
        check("rank 1 of 1 on the daily board", ok["rank"] == 1 and ok["total"] == 1 and ok["board"][0]["me"])
        res.clear()
        rk.daily_submit(raw["ref_taps"], sim.LevelData(raw).digest, lambda r: res.update(again=r))
        check("a second submit changes nothing (dup)", wait(lambda: "again" in res) and res["again"].get("dup") is True
              and sm.diamonds == bal)
    print("ALL RANKED E2E CHECKS DONE" if not fails else f"FAILED: {fails}")
finally:
    srv.terminate()
sys.exit(1 if fails else 0)
