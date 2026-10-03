"""Check a deployed leaderboard server from the outside.

    python tools/check_server.py https://KULLANICI.pythonanywhere.com          # read-only checks (safe)
    python tools/check_server.py https://KULLANICI.pythonanywhere.com --full   # also registers a throw-away 'SELFTEST' player
                                                                                 and submits level 1 (it stays on the board)
"""
import os
import sys
import json
import time
import secrets
import uuid
import urllib.request
import urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from online import _sign, _SSL  # noqa: E402
from sim import LevelData  # noqa: E402


def call(base, method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base + path, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60, context=_SSL) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, {}


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    base = sys.argv[1].rstrip("/")
    ok = True

    def check(name, cond, extra=""):
        nonlocal ok
        ok &= bool(cond)
        print(("PASS " if cond else "FAIL ") + name, extra)

    t0 = time.time()
    code, r = call(base, "GET", "/api/health")
    check("health (may take ~60 s on a cold start)", code == 200 and r.get("ok"), f"{r} in {time.time()-t0:.1f}s")
    check("server sim version equals the game's", r.get("sim") == __import__("sim").SIM_VERSION, f"server={r.get('sim')}")
    code, r = call(base, "GET", "/api/leaderboard?scope=global&limit=5")
    check("leaderboard readable", code == 200 and "rows" in r, f"{len(r.get('rows', []))} rows")
    pid, sec = uuid.uuid4().hex, secrets.token_hex(24)
    code, r = call(base, "POST", "/api/submit", {"player_id": pid, "level": 1, "ts": int(time.time()), "taps": [10, 30],
                                                  "sig": _sign(sec, pid, 1, int(time.time()), [10, 30])})
    check("unknown player is refused (403)", code == 403, (code, r))

    if "--full" in sys.argv:
        lvl = LevelData.load(1)
        code, r = call(base, "POST", "/api/register", {"player_id": pid, "secret": sec, "name": "SELFTEST", "country": "GX"})
        check("register", code == 200, r)
        ts = int(time.time())
        taps = lvl.raw["ref_taps"]
        code, r = call(base, "POST", "/api/submit", {"player_id": pid, "level": 1, "ts": ts, "taps": taps,
                                                      "lvl": lvl.digest, "sig": _sign(sec, pid, 1, ts, taps)})
        check("level 1 replay accepted (level files match the game)", code == 200 and r.get("ok"), (code, r))
    print("ALL OK" if ok else "SOME CHECKS FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
