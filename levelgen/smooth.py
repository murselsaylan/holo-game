"""Smooth difficulty: every level about as hard as its number says - never a spike or a dip against its neighbours.

    python levelgen/smooth.py                  # report: felt difficulty vs the curve, outliers
    python levelgen/smooth.py --fix 52,58,60   # rebuild those levels, keeping the candidate closest to the curve

"Felt" difficulty F adds what rebalance.py's D leaves out - how narrow the corridors are and how little safety margin the
best line has - to D (time, swaps, hazards, gates, speed). The curve is K x rebalance.target(i): it only ever rises, so
level 60 always lands between 40 and 80. A rebuilt level's previous file goes to levelgen/legacy_levels (the server keeps
replaying runs of games that were not updated yet on it). When levels are added past 100, extend target() first.
"""
import json
import multiprocessing as mp
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
LEVELS = os.path.join(ROOT, "levels")
LEGACY = os.path.join(ROOT, "levelgen", "legacy_levels")
K = 1.245                       # median F / target over the campaign (2026-10): the curve's scale
FIRST = 41                      # the first 40 are left alone: hand-tuned onboarding, players pass them fine
HARD, EASY = 1.20, 0.78         # outlier thresholds on F / curve


def felt(d):
    df = d["difficulty"]
    haz = sum(len(d.get(k, [])) for k in ("moving_walls", "lasers", "spinners", "circles", "reverse_walls"))
    gates = sum(1 for k in ("barriers", "breakables", "chasers", "shrink_zones", "growth_zones") if d.get(k))
    gates += len(d.get("chasers", [])) + len(d.get("barriers", [])) + len(d.get("breakables", []))
    D = 0.55 * df["ref_time"] + 0.30 * df["swaps"] + 1.2 * haz + 5.0 * min(gates, 6) + 30.0 * (d["speed"] - 0.9)
    narrow = max(0.0, 300.0 - df["corridor"]) / 150.0          # 0 at 300 px, 1 at 150 px
    return D + 30.0 * narrow + 0.5 * max(0.0, 20.0 - df["margin"])


def target(i):
    return 10.0 + 90.0 * ((i - 1) / 99.0) ** 0.9


def curve(i):
    return K * target(i)


def load(i):
    return json.load(open(os.path.join(LEVELS, f"level{i}.json"), encoding="utf-8"))


def ratio(i, d=None):
    return felt(d or load(i)) / curve(i)


def outliers(lo=FIRST, hi=100):
    out = []
    for i in range(lo, hi + 1):
        r = ratio(i)
        if r > HARD or r < EASY:
            out.append((i, round(r, 2)))
    return out


def _work(job):
    i, off = job
    os.environ["HOLO_TIGHT_OFFSET"] = str(off)
    os.environ["HOLO_NO_HARDEN"] = "1" if off < 0 else "0"
    from levelgen import gen as G
    try:
        d, rep = G.make(i, 0)
    except Exception as e:  # pragma: no cover
        return i, off, None, repr(e)
    return i, off, d, rep


def fix(ids):
    jobs = []
    for i in ids:
        r = ratio(i)
        offs = (-0.08, -0.16, -0.24, -0.32) if r > 1.0 else (0.06, 0.12, 0.18)
        jobs += [(i, o) for o in offs]
    best = {}
    with mp.Pool(min(14, len(jobs))) as pool:
        for i, off, d, rep in pool.imap_unordered(_work, jobs):
            if d is None:
                print(f"L{i} off {off:+.2f} FAILED {str(rep)[:120]}", flush=True)
                continue
            r = ratio(i, d)
            print(f"L{i} off {off:+.2f}: F/curve {r:.2f}  W={d['difficulty']['corridor']} margin={d['difficulty']['margin']} "
                  f"swaps={d['difficulty']['swaps']} t={d['difficulty']['ref_time']}", flush=True)
            if i not in best or abs(r - 1.0) < abs(best[i][0] - 1.0):
                best[i] = (r, d)
    os.makedirs(LEGACY, exist_ok=True)
    from levelgen import gen as G
    for i in ids:
        old = ratio(i)
        if i in best and abs(best[i][0] - 1.0) < abs(old - 1.0):
            leg = os.path.join(LEGACY, f"level{i}.json")
            if not os.path.exists(leg):                        # keep the version players have (the first one replaced)
                shutil.copy(os.path.join(LEVELS, f"level{i}.json"), leg)
            G.save(best[i][1])
            print(f"L{i}: {old:.2f} -> {best[i][0]:.2f}  saved", flush=True)
        else:
            print(f"L{i}: kept ({old:.2f})", flush=True)


def main():
    args = [a for a in sys.argv[1:] if a.startswith("--fix")]
    if args:
        val = args[0].split("=", 1)[1] if "=" in args[0] else (sys.argv[sys.argv.index(args[0]) + 1] if len(sys.argv) > sys.argv.index(args[0]) + 1 else "")
        ids = [int(x) for x in val.split(",") if x] if val else [i for i, _ in outliers()]
        fix(ids)
    for i in range(FIRST, 101):
        r = ratio(i)
        mark = " <-- hard" if r > HARD else (" <-- easy" if r < EASY else "")
        print(f"L{i:3d} F={felt(load(i)):6.1f} curve={curve(i):6.1f} ratio={r:.2f}{mark}")
    print("outliers:", outliers())


if __name__ == "__main__":
    mp.freeze_support()
    main()
