"""End-to-end test: real HTTP server thread + real OnlineClient + replay verification.  python tools/server_test.py"""
import os, sys, json, time, tempfile, threading, urllib.request, urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["HOLO_SAVE_DIR"] = tempfile.mkdtemp(prefix="holo_srv_")
os.environ["SDL_VIDEODRIVER"] = "dummy"

from server import leaderboard_server as srv
from save_manager import SaveManager
from online import OnlineClient, _sign
from sim import LevelData

db = os.path.join(tempfile.mkdtemp(), "t.db")
httpd = srv.make_server(0, db, "127.0.0.1")
port = httpd.server_address[1]
threading.Thread(target=httpd.serve_forever, daemon=True).start()
base = f"http://127.0.0.1:{port}"


def post(path, body):
    req = urllib.request.Request(base + path, data=json.dumps(body).encode(), method="POST", headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())


def get(path):
    with urllib.request.urlopen(base + path, timeout=10) as r:
        return json.loads(r.read().decode())


def wait(cond, sec=15):
    t0 = time.time()
    while time.time() - t0 < sec:
        if cond():
            return True
        time.sleep(0.05)
    return False


ok = True
def check(name, cond, extra=""):
    global ok
    ok &= bool(cond)
    print(("PASS " if cond else "FAIL ") + name, extra)

print("health:", get("/api/health"))
sm = SaveManager()
sm.data.update(player_name="TESTER", player_country="TR", is_profile_set=True)
cl = OnlineClient(sm, base)
cl.register()
lv1 = json.load(open(os.path.join(ROOT, "levels", "level1.json"), encoding="utf-8"))
lv2 = json.load(open(os.path.join(ROOT, "levels", "level2.json"), encoding="utf-8"))

cl.submit(1, lv1["ref_taps"])
check("submit level 1 accepted", wait(lambda: (cl.poll() or True) and cl.last_submit and cl.last_submit.get("ok")), cl.last_submit)
check("rank #1 after first clear", cl.last_submit and cl.last_submit["world_rank"] == 1)
s1 = cl.last_submit["score"]
cl.last_submit = None
cl.submit(2, lv2["ref_taps"])
check("submit level 2 accepted", wait(lambda: (cl.poll() or True) and cl.last_submit and cl.last_submit.get("ok")))
check("score is sum of bests and 2 levels", cl.last_submit["levels"] == 2 and cl.last_submit["score"] > s1, cl.last_submit)

# second player, only 1 level -> ranked below
sm2 = SaveManager.__new__(SaveManager)
sm2._lock = threading.RLock()
import save_manager as _sm
sm2.data = _sm._default_save(); sm2.data.update(player_name="ROOKIE", player_country="JP", is_profile_set=True)
cl2 = OnlineClient(sm2, base)
cl2.register(); cl2.submit(1, lv1["ref_taps"])
check("2nd player accepted", wait(lambda: (cl2.poll() or True) and cl2.last_submit and cl2.last_submit.get("ok")))
check("2nd player ranked #2", cl2.last_submit["world_rank"] == 2, cl2.last_submit)

cl.fetch("global")
check("leaderboard fetched", wait(lambda: (cl.poll() or True) and cl.boards.get("global")))
rows = cl.boards["global"]["rows"]
check("leaderboard order (levels desc)", [r["name"] for r in rows] == ["TESTER", "ROOKIE"], [(r["rank"], r["name"], r["levels"], r["score"]) for r in rows])
cl.fetch("country"); wait(lambda: (cl.poll() or True) and cl.boards.get("country"))
check("country board only TR", all(r["country"] == "TR" for r in cl.boards["country"]["rows"]))
cl.fetch("around"); wait(lambda: (cl.poll() or True) and cl.boards.get("around"))
check("around board has me", any(r["id"] == sm.player_id for r in cl.boards["around"]["rows"]))

# ---- attacks
pid, sec = sm.player_id, sm.player_secret
ts = int(time.time())
def signed(level, taps, secret=sec, t=ts):
    return {"player_id": pid, "level": level, "ts": t, "taps": taps, "sig": _sign(secret, pid, level, t, taps)}
code, r = post("/api/submit", signed(3, [10, 20, 30]))
check("garbage taps rejected (replay fails)", code == 422, (code, r))
code, r = post("/api/submit", signed(1, lv1["ref_taps"], secret="0" * 48))
check("bad signature rejected", code == 403, (code, r))
tampered = signed(1, lv1["ref_taps"]); tampered["taps"] = tampered["taps"][:-1] + [tampered["taps"][-1] + 500]
code, r = post("/api/submit", tampered)
check("tampered taps rejected (signature)", code == 403, (code, r))
code, r = post("/api/submit", signed(1, [5, 6, 7]))
check("superhuman tap rate rejected", code == 422, (code, r))
code, r = post("/api/submit", signed(1, lv1["ref_taps"], t=ts - 4000))
check("stale timestamp rejected", code == 400, (code, r))
code, r = post("/api/register", {"player_id": pid, "secret": "f" * 48, "name": "HIJACK", "country": "US"})
check("identity hijack rejected", code == 403, (code, r))
code, r = post("/api/submit", signed(101, lv1["ref_taps"]))
check("level out of range rejected", code == 400, (code, r))

bad = signed(1, lv1["ref_taps"]); bad["lvl"] = "deadbeef00"
code, r = post("/api/submit", bad)
check("stale level version rejected (409)", code == 409, (code, r))
good = signed(1, lv1["ref_taps"]); good["lvl"] = LevelData(lv1).digest
code, r = post("/api/submit", good)
check("matching level digest accepted", code == 200, (code, r))

print("ALL OK" if ok else "SOME FAILED")
sys.exit(0 if ok else 1)
