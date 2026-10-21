"""End-to-end check of the friends feature: the real game client (online.py) against the real server code
(supabase/functions/scores/handler.ts + friends.ts on an in-memory store, served by Deno).

    python tools/friends_e2e.py          (needs deno: pip install deno)
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

fails = []


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


deno = shutil.which("deno")
if not deno:
    print("deno not found")
    sys.exit(2)
srv = subprocess.Popen([deno, "run", "-A", "--no-check", "tests/serve_mem.ts", str(PORT)],
                       cwd=os.path.join(ROOT, "supabase", "functions", "scores"), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
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

    def make(name):
        sm = save_manager.SaveManager()
        sm.data["player_id"] = secrets.token_hex(16)
        sm.data["player_secret"] = secrets.token_hex(24)
        sm.data["player_name"] = name
        sm.data["player_country"] = "TR"
        sm.data["is_profile_set"] = True
        oc = online.OnlineClient(sm)
        sm.wallet = oc
        return sm, oc

    def wait(cond, oc_list, secs=15):
        t = time.time()
        while time.time() - t < secs:
            for o in oc_list:
                o.poll()
            if cond():
                return True
            time.sleep(0.05)
        return False

    smA, A = make("ALICE")
    smB, B = make("BOB")
    both = [A, B]
    for o in both:
        o.register()
        o.wallet_sync()
    check("both wallets open", wait(lambda: smA.data.get("wallet_synced") or True, both) and
          wait(lambda: A._wallet_open and B._wallet_open, both))

    A.friends_refresh()
    check("A gets an invite code", wait(lambda: A.friends and A.friends.get("code"), both))
    code = A.friends["code"]
    res = {}
    B.friends_op("add", code, lambda r: res.update(add=r))
    check("B adds A by code", wait(lambda: "add" in res, both) and res["add"].get("state") == "pending")
    A.friends_refresh()
    check("A sees the request", wait(lambda: A.friends and any(f["status"] == "incoming" for f in A.friends["friends"]), both))
    bid = smB.player_id
    A.friends_op("accept", bid, lambda r: res.update(acc=r))
    check("A accepts", wait(lambda: "acc" in res, both) and res["acc"].get("ok"))
    check("both lists show a friend", wait(lambda: A.friend_rows() and (B.friends_refresh() or True) and wait(lambda: B.friend_rows(), both), both))

    # gift: A -> B, B claims; the sender's wallet does not change
    balA = smA.diamonds
    A.friends_op("gift", bid, lambda r: res.update(gift=r))
    check("A sends a gift", wait(lambda: "gift" in res, both) and res["gift"].get("ok"))
    A.friends_op("gift", bid, lambda r: res.update(gift2=r))
    check("a second gift today is refused", wait(lambda: "gift2" in res, both) and res["gift2"].get("error") == "already sent today")
    B.friends_refresh()
    check("B sees the gift in the inbox", wait(lambda: B.friends and B.friends.get("inbox"), both))
    msg = B.friends["inbox"][0]
    before = smB.diamonds
    B.friends_op("claim", str(msg["id"]), lambda r: res.update(claim=r))
    check("B claims it", wait(lambda: "claim" in res, both) and res["claim"].get("ok"))
    check("diamond gift: +5 on B, nothing from A" if msg["item"] == "diamond" else "shield gift: credit on B",
          (msg["item"] == "diamond" and res["claim"]["added"] == 5 and smB.diamonds == before + 5 and smA.diamonds == balA)
          or (msg["item"] == "shield" and wait(lambda: B.credits["shield"] == 1, both)))

    # help request: B is stuck, A sends help
    B.friends_op("help_ask", "7", lambda r: res.update(ask=r))
    check("B asks for help on level 7", wait(lambda: "ask" in res, both) and res["ask"].get("ok"))
    A.friends_refresh()
    check("A sees the request", wait(lambda: A.friends and A.friends.get("help"), both))
    hid = A.friends["help"][0]["id"]
    balA = smA.diamonds
    A.friends_op("help_send", str(hid), lambda r: res.update(help=r))
    check("A sends the help (+5 for A)", wait(lambda: "help" in res, both) and res["help"].get("added") == 5 and smA.diamonds == balA + 5)
    B.wallet_sync()
    check("B received one free shield or revive", wait(lambda: B.credits["shield"] + B.credits["revive"] >= 1, both))
    item = "revive" if B.credits["revive"] else "shield"
    smB.data["diamonds"] = 0                      # the local number only: the server's balance is what counts
    out = []
    smB.spend(item, 20, lambda ok, why: out.append((ok, why)))
    check("B uses it with 0 local diamonds", wait(lambda: out, both) and out[0][0] is True)
    server_bal = smB.diamonds                      # the server's answer to the free spend
    out.clear()
    B.wallet_sync()
    wait(lambda: B.credits[item] == 0, both)
    check("... the credit is gone and no diamonds were charged", B.credits[item] == 0 and smB.diamonds == server_bal)

    # friend ghost: A clears level 3, B races A's run
    raw = json.load(open(os.path.join(ROOT, "levels", "level3.json")))
    import sim  # noqa: E402
    ref, dg = raw["ref_taps"], sim.LevelData(raw).digest      # the game sends the digest of the level version it plays
    A.submit(3, ref, dg)
    check("A's level-3 run is verified", wait(lambda: (A.last_submit or {}).get("ok"), both, 30))
    B.fetch_friend_ghost(3, dg)
    check("B gets A's run as the friend ghost", wait(lambda: B.friend_ghosts.get(3) is not None, both, 30)
          and (B.friend_ghosts.get(3) or {}).get("id") == smA.player_id and len(B.friend_ghosts[3]["taps"]) == len(ref))
    g = B.friend_ghosts.get(3) or {}
    print("friend ghost:", g.get("name"), g.get("score"), len(g.get("taps", [])), "taps")
finally:
    srv.terminate()

print("\nFAILED:" if fails else "\nALL OK", fails or "")
sys.exit(1 if fails else 0)
