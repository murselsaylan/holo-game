"""Finishing pass for freshly generated levels (101+):
   1. hazards closer than 200 px to the start / the goal are removed (removing an obstacle cannot break a solution)
   2. empty stretches of the reference line (> 600 px with nothing in reach) are filled with plain-wall hazards
      (sector_fix.fill_gaps), then the level is re-solved (respeed path: new reference line, stars, 3-star replay)
   3. the result is accepted only when the 3-star replay wins and the longest empty stretch is <= LIMIT

    python levelgen/finish_new.py 101 140          # all
    python levelgen/finish_new.py --only=105,107   # some
"""
import os
import sys
import json
import math
import re
import time
import multiprocessing as mp

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from sim import LevelData, replay  # noqa: E402
from levelgen import sector_fix as SF  # noqa: E402

LIMIT = 650.0          # the rule says ~600 px; a little slack for the measure's granularity


def strip_ends(d, dist=200.0):
    sx, sy = d["start"]
    ex, ey = d["end"]
    removed = 0

    def far(x, y, r=0.0):
        return math.hypot(x - sx, y - sy) - r >= dist and math.hypot(x - ex, y - ey) - r >= dist

    def keep_rect(m):
        # distance from the centre of the swept area (the piston's whole travel) to the ends
        cx, cy = m[0] + m[2] / 2.0, m[1] + m[3] / 2.0
        reach = max(m[4], m[5]) + max(m[2], m[3]) / 2.0
        return far(cx, cy, reach)

    for key, test in (("moving_walls", keep_rect),
                      ("lasers", lambda l: far((l[0] + l[2]) / 2.0, (l[1] + l[3]) / 2.0, math.hypot(l[2] - l[0], l[3] - l[1]) / 2.0)),
                      ("spinners", lambda s: far(s[0], s[1], s[2])),
                      ("circles", lambda c: far(c[0], c[1], c[2]))):
        old = d.get(key, [])
        new = [h for h in old if test(h)]
        removed += len(old) - len(new)
        d[key] = new
    return removed


MIN_MARGIN = float(os.environ.get("FINISH_MIN_MARGIN", "6.0"))
RAW = os.path.join(ROOT, "levelgen", "new_levels_raw")
RECIPES = [(False, 0), (True, 0), (True, 1), (True, 2), (False, 1), (False, 2), (True, 3)]     # (soft hazards, seed)


def attempt(i, d0, soft, seed):
    d = json.loads(json.dumps(d0))
    log = [f"recipe soft={soft} seed={seed}"]
    removed = strip_ends(d)
    if removed:
        log.append(f"removed {removed} near ends")
    margin = None
    for p_ in range(4):
        longest = SF.emptiness(d)[0]
        if longest <= LIMIT:
            break
        added = SF.fill_gaps(d, seed=seed * 10 + p_, max_empty=550.0, soft=soft, limit=(6 if soft else 14))
        log.append(f"pass {p_}: empty {longest:.0f} px -> +{added}")
        if not added:
            break
        nd, msg = SF._solve(d)
        if nd is None:
            return None, "; ".join(log + [f"re-solve failed ({msg})"])
        m = re.search(r"margin=([0-9.]+)", msg)
        margin = float(m.group(1)) if m else None
        log.append(f"re-solved margin={margin}")
        d = nd
    longest = SF.emptiness(d)[0]
    if longest > LIMIT:
        return None, "; ".join(log + [f"still empty {longest:.0f} px"])
    if margin is not None and margin < MIN_MARGIN:
        return None, "; ".join(log + [f"margin {margin} < {MIN_MARGIN}"])
    _, res = replay(LevelData(d), d.get("ref_taps", []), max_seconds=400)
    if res is None or res["stars"] != 3:
        return None, "; ".join(log + [f"3-star replay failed ({res and res['stars']})"])
    return d, "; ".join(log + [f"empty {longest:.0f} px"])


def work(i):
    t0 = time.time()
    os.environ["RESPEED_BEAM"] = "48"
    src = os.path.join(RAW, f"level{i}.json") if "--raw" in sys.argv else os.path.join(ROOT, "levels", f"level{i}.json")
    d0 = json.load(open(src, encoding="utf-8"))
    notes = []
    for soft, seed in RECIPES:
        d, msg = attempt(i, d0, soft, seed)
        notes.append(msg)
        if d is not None:
            json.dump(d, open(os.path.join(ROOT, "levels", f"level{i}.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
            return i, True, msg, time.time() - t0
    return i, False, " || ".join(notes)[-600:], time.time() - t0


if __name__ == "__main__":
    mp.freeze_support()
    ids = list(range(101, 141))
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) == 2:
        ids = list(range(int(args[0]), int(args[1]) + 1))
    for a in sys.argv[1:]:
        if a.startswith("--only="):
            ids = [int(x) for x in a[7:].split(",") if x]
    t0 = time.time()
    bad = []
    with mp.Pool(min(14, len(ids))) as pool:
        for i, ok, msg, secs in pool.imap_unordered(work, ids):
            print(f"L{i:3d} {'OK ' if ok else 'BAD'} ({secs:.0f}s) {msg}", flush=True)
            if not ok:
                bad.append(i)
    print("BAD:", bad)
    print("done in", round(time.time() - t0), "s")
