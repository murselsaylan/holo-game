"""Smooth difficulty: every level about as hard as its number says - never a spike or a dip against its neighbours.

    python levelgen/smooth.py                  # report: felt difficulty vs the curve, outliers
    python levelgen/smooth.py --fix 52,58,60   # rebuild those levels, keeping the candidate closest to the curve
    python levelgen/smooth.py --band=0.10 --fix=55-80   # a tighter band (+-10 %) for the report and the fix

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
K = 1.13                        # median F / target over the campaign at the 1.0.8 speeds (was 1.245 before them)
from levelgen.plan import ARENA_LEVELS as OPEN_FIELD  # noqa: E402  (wall-less 'TRIAL' levels)
FIRST = 41                      # the first 40 are left alone: hand-tuned onboarding, players pass them fine
HARD, EASY = 1.20, 0.78         # outlier thresholds on F / curve


def felt(d):
    df = d["difficulty"]
    haz = sum(len(d.get(k, [])) for k in ("moving_walls", "lasers", "spinners", "circles", "reverse_walls"))
    gates = sum(1 for k in ("barriers", "breakables", "chasers", "shrink_zones", "growth_zones") if d.get(k))
    gates += len(d.get("chasers", [])) + len(d.get("barriers", [])) + len(d.get("breakables", []))
    D = 0.55 * df["ref_time"] + 0.30 * df["swaps"] + 1.2 * haz + 5.0 * min(gates, 6) + 30.0 * (d["speed"] - 0.9)
    narrow = max(0.0, 300.0 - df["corridor"]) / 150.0          # 0 at 300 px, 1 at 150 px
    if d.get("id") in OPEN_FIELD:                               # open-field trials have no corridor to be narrow
        narrow = 0.0
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
    i, var, off = job
    os.environ["HOLO_TIGHT_OFFSET"] = str(off)
    os.environ["HOLO_NO_HARDEN"] = "1" if off < 0 else "0"
    from levelgen import plan as P
    P.VARIANT[i] = var                                    # a different layout roll of the same plan
    from levelgen import gen as G
    try:
        d, rep = G.make(i, 0)
    except Exception as e:  # pragma: no cover
        return i, var, off, None, repr(e)
    return i, var, off, d, rep


def fix(ids, n_variants=3, force=(), n_offsets=3):
    """Candidates per level: its current layout roll and n_variants - 1 new ones, each at a few tightness offsets
    (looser when too hard, tighter when too easy). The candidate closest to the curve replaces the level if it is
    closer than the level is now; a new roll is written to variants.json so the level can be rebuilt the same way."""
    from levelgen import plan as P
    jobs = []
    for i in ids:
        r = ratio(i)
        offs = ((-0.06, -0.14, -0.24) if r > 1.0 else (0.0, 0.08, 0.16))[:n_offsets]
        if i in force:                                     # its file no longer works (e.g. re-timed): rebuild it anyway
            offs = (0.0, -0.1, 0.1)[:n_offsets]
        base = P.VARIANT.get(i, 0)
        jobs += [(i, base + k * 11, o) for k in range(n_variants) for o in offs]
    best = {}
    with mp.Pool(min(14, len(jobs))) as pool:
        for i, var, off, d, rep in pool.imap_unordered(_work, jobs):
            if d is None:
                print(f"L{i} v{var} off {off:+.2f} FAILED {str(rep)[:120]}", flush=True)
                continue
            r = ratio(i, d)
            print(f"L{i} v{var} off {off:+.2f}: F/curve {r:.2f}  W={d['difficulty']['corridor']} margin={d['difficulty']['margin']} "
                  f"swaps={d['difficulty']['swaps']} t={d['difficulty']['ref_time']}", flush=True)
            if i not in best or abs(r - 1.0) < abs(best[i][0] - 1.0):
                best[i] = (r, d, var)
    os.makedirs(LEGACY, exist_ok=True)
    from levelgen import gen as G
    var_path = os.path.join(ROOT, "levelgen", "variants.json")
    variants = json.load(open(var_path)) if os.path.exists(var_path) else {}
    for i in ids:
        old = ratio(i)
        if i in best and (i in force or abs(best[i][0] - 1.0) < abs(old - 1.0)):
            leg = os.path.join(LEGACY, f"level{i}.json")
            if not os.path.exists(leg):                        # keep the version players have (the first one replaced)
                shutil.copy(os.path.join(LEVELS, f"level{i}.json"), leg)
            G.save(best[i][1])
            if best[i][2]:
                variants[str(i)] = best[i][2]
            else:
                variants.pop(str(i), None)
            print(f"L{i}: {old:.2f} -> {best[i][0]:.2f}  saved (variant {best[i][2]})", flush=True)
        else:
            print(f"L{i}: kept ({old:.2f})", flush=True)
    json.dump(variants, open(var_path, "w"))


def _ids(val):
    out = []
    for part in val.split(","):
        if "-" in part:
            a, b = part.split("-")
            out += list(range(int(a), int(b) + 1))
        elif part:
            out.append(int(part))
    return out


def main():
    global HARD, EASY
    for a in sys.argv[1:]:
        if a.startswith("--band="):
            b = float(a.split("=", 1)[1])
            HARD, EASY = 1.0 + b, 1.0 - b
    args = [a for a in sys.argv[1:] if a.startswith("--fix")]
    if args:
        val = args[0].split("=", 1)[1] if "=" in args[0] else (sys.argv[sys.argv.index(args[0]) + 1] if len(sys.argv) > sys.argv.index(args[0]) + 1 else "")
        ids = _ids(val) if val else [i for i, _ in outliers()]
        if "-" in val:                                     # a range: only its outliers
            ids = [i for i in ids if not (EASY <= ratio(i) <= HARD)]
        force = []
        for a in sys.argv[1:]:
            if a.startswith("--force="):
                force = _ids(a.split("=", 1)[1])
        ids = sorted(set(ids) | set(force))
        quick = "--quick" in sys.argv                     # 2 layout rolls x 2 offsets per level instead of 3 x 3
        print("rebuilding", ids, "forced", force, flush=True)
        fix(ids, n_variants=2 if quick else 3, force=force, n_offsets=2 if quick else 3)
    for i in range(FIRST, 101):
        r = ratio(i)
        mark = " <-- hard" if r > HARD else (" <-- easy" if r < EASY else "")
        print(f"L{i:3d} F={felt(load(i)):6.1f} curve={curve(i):6.1f} ratio={r:.2f}{mark}")
    print("outliers:", outliers())


if __name__ == "__main__":
    mp.freeze_support()
    main()
