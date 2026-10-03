"""Re-solve existing levels after a physics change (keeps the geometry, redoes solution / stars / par values).

    python levelgen/resolve.py            # all levels
    python levelgen/resolve.py 5 9 12     # only these

If a level is not solvable with the new hidden speed-up at a decent safety margin, its `ramp` is reduced step by step.
"""
import os
import sys
import json
import time
import multiprocessing as mp

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from sim import LevelData, replay, LEVELS_DIR  # noqa: E402
from levelgen import plan as P, solver as S  # noqa: E402
from levelgen.gen import pick  # noqa: E402


def work(i):
    t0 = time.time()
    path = os.path.join(LEVELS_DIR, f"level{i}.json")
    d = json.load(open(path, encoding="utf-8"))
    m_rec = float(d.get("difficulty", {}).get("margin", 10.0))
    floor = max(5.0, 0.7 * P.margin_target(i) * 0.6)
    n_shields = len(d.get("shields", []))
    d["shields"] = []          # solve without shields (a shield pop at margin>0 would change the dynamics), re-place afterwards
    sol = None
    used = None
    for scale in (1.0, 0.75, 0.5, 0.3, 0.12):
        d["ramp"] = round(P.ramp_of(i) * scale, 3)
        lvl = LevelData(d)
        for frac in (0.8, 0.55, 0.35, 0.2, 0.0):
            m = min(50.0, m_rec * frac)
            if 0 < m < 3.0:
                m = 0.0
            r = S.solve(lvl, margin=m, beam=96, max_layers=320)
            if r.solved:
                sol, used = r, m
                break
        if sol:
            break
    if not sol:
        return i, {"error": "unsolvable", "secs": round(time.time() - t0)}
    lvl = LevelData(d)
    pts, _ = S.trajectory(lvl, sol.taps, margin=0.0)
    stars = []
    for prog in (0.24, 0.52, 0.80):
        p = pick(pts, prog, 0.07, avoid=stars)
        if p is None:
            return i, {"error": "star placement", "secs": round(time.time() - t0)}
        stars.append((round(p["x"]), round(p["y"])))
    d["stars"] = [list(s_) for s_ in stars]
    shields = []
    for prog in ([0.30] if n_shields == 1 else ([0.28, 0.62] if n_shields > 1 else [])):
        p = pick(pts, prog, 0.06, min_clear=24.0, prefer_low=False, avoid=stars + shields)
        if p:
            shields.append((round(p["x"]), round(p["y"])))
    d["shields"] = [list(s_) for s_ in shields]
    d["par_time"] = round(sol.time_s * 1.15, 1)
    d["par_swaps"] = int(sol.swaps * 1.15) + 1
    d["ref_taps"] = list(sol.taps)
    dd = d.setdefault("difficulty", {})
    dd.update({"margin": round(used, 1), "swaps": sol.swaps, "ref_time": round(sol.time_s, 1), "ramp": d["ramp"],
               "speed": d.get("speed")})
    sim, res = replay(LevelData(d), sol.taps)
    if res is None or res["stars"] < 3:
        return i, {"error": f"replay failed {res and res['stars']}", "secs": round(time.time() - t0)}
    json.dump(d, open(path, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    return i, {"ok": True, "ramp": d["ramp"], "margin": round(used, 1), "was": m_rec, "swaps": sol.swaps,
               "time": round(sol.time_s, 1), "secs": round(time.time() - t0)}


if __name__ == "__main__":
    mp.freeze_support()
    ids = [int(a) for a in sys.argv[1:]] or list(range(1, 101))
    t0 = time.time()
    bad = []
    with mp.Pool(14) as pool:
        for i, r in pool.imap_unordered(work, ids):
            print(f"L{i:3d} {r}", flush=True)
            if not r.get("ok"):
                bad.append(i)
    print("FAILED:", bad)
    print("done in", round(time.time() - t0), "s")
