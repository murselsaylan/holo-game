"""Smooth difficulty: every level about as hard as its number says - never a spike or a dip against its neighbours.

    python levelgen/smooth.py                  # report: score vs the curve, outliers
    python levelgen/smooth.py --fit            # fit the curve to the current scores (levelgen/curve.json)
    python levelgen/smooth.py --fix 52,58,60   # rebuild those levels, keeping the candidate closest to the curve
    python levelgen/smooth.py --band=0.12 --quick --fix=41-100 --force=56,59   # band, fewer candidates, forced rebuilds

The score is levelgen/difficulty.py's (the level played on the real simulation: time, tempo, walls, hazards, spacing,
precision, speed, gates, margin). The curve is a + b * x^c with x = (i - 1) / 199 - fitted to the levels, rising, and
laid out over the planned ~200 levels, so a new level 150 is generated against the same curve. A rebuilt level's
previous file goes to levelgen/legacy_levels (the server keeps replaying runs of games that were not updated yet on it).
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
CURVE = os.path.join(ROOT, "levelgen", "curve.json")
FIRST = 41                      # the first 40 are left alone by default: onboarding, players pass them fine
HARD, EASY = 1.20, 0.80         # outlier thresholds on score / curve
from levelgen import difficulty as DIFF  # noqa: E402
from levelgen.plan import CAMPAIGN  # noqa: E402

_SCORES = {}


def score_of(d):
    """Difficulty score of a level dict (played on the simulation; 0 if its reference line does not win)."""
    raw = DIFF.measure(d)
    return DIFF.score(raw)[1] if raw else 0.0


def felt(d):
    i = d.get("id")
    if i is not None and _SCORES.get(i, (None,))[0] == _digest(d):
        return _SCORES[i][1]
    return score_of(d)


def _digest(d):
    from sim import LevelData
    return LevelData(d).digest


def load_scores(ids):
    """Scores of the level files (cached in levels/_difficulty.json, measured in parallel when out of date)."""
    res = DIFF.score_all(list(ids))
    for i, c in res.items():
        _SCORES[i] = (c["digest"], DIFF.score(c["raw"])[1])
    return {i: _SCORES[i][1] for i in res}


def _params():
    if os.path.exists(CURVE):
        return json.load(open(CURVE))
    return {"a": 15.0, "b": 260.0, "c": 0.8}


def curve(i):
    p = _params()
    x = min(1.0, (i - 1) / float(CAMPAIGN - 1))
    return p["a"] + p["b"] * x ** p["c"]


def fit(lo=4, hi=100):
    """Least-squares a + b x^c through the scores of levels lo..hi; written to levelgen/curve.json."""
    import numpy as np
    from scipy.optimize import curve_fit
    sc = load_scores(range(lo, hi + 1))
    xs = np.array([(i - 1) / float(CAMPAIGN - 1) for i in sorted(sc)])
    ys = np.array([sc[i] for i in sorted(sc)])
    (a, b, c), _ = curve_fit(lambda x, a, b, c: a + b * x ** c, xs, ys, p0=(15.0, 250.0, 0.8),
                             bounds=([0.0, 1.0, 0.3], [80.0, 2000.0, 3.0]))
    json.dump({"a": round(float(a), 3), "b": round(float(b), 3), "c": round(float(c), 4)}, open(CURVE, "w"))
    return a, b, c


def load(i):
    return json.load(open(os.path.join(LEVELS, f"level{i}.json"), encoding="utf-8"))


def ratio(i, d=None):
    if d is None:
        if i not in _SCORES:
            load_scores([i])
        return _SCORES[i][1] / curve(i)
    return felt(d) / curve(i)


def outliers(lo=FIRST, hi=100):
    out = []
    for i in range(lo, hi + 1):
        r = ratio(i)
        if r > HARD or r < EASY:
            out.append((i, round(r, 2)))
    return out


HAZARDS = ("moving_walls", "lasers", "spinners", "circles", "reverse_walls")


def hazard_count(d):
    return sum(len(d.get(k, [])) for k in HAZARDS)


def shipped_hazards(i):
    """Hazards in the version of level i that released games carry (levelgen/legacy_levels, else the current file)."""
    p = os.path.join(LEGACY, f"level{i}.json")
    if not os.path.exists(p):
        p = os.path.join(LEVELS, f"level{i}.json")
    return hazard_count(json.load(open(p, encoding="utf-8")))


def _work(job):
    i, var, off = job[:3]
    roamers = job[3] if len(job) > 3 else 0
    os.environ["HOLO_TIGHT_OFFSET"] = str(off)
    os.environ["HOLO_NO_HARDEN"] = "1" if off < 0 else "0"
    os.environ["HOLO_NO_STRIP"] = "1"                    # a level is never emptied of hazards to make it solvable
    from levelgen import plan as P
    P.VARIANT[i] = var                                    # a different layout roll of the same plan
    from levelgen import gen as G
    try:
        d, rep = G.make(i, 0, roamers=roamers)
    except Exception as e:  # pragma: no cover
        return i, var, off, None, repr(e)
    if d is not None:
        rep = dict(rep, score=score_of(d))
    return i, var, off, d, rep


def fix(ids, n_variants=3, force=(), n_offsets=3):
    """Candidates per level: its current layout roll and n_variants - 1 new ones, each at a few tightness offsets
    (looser when too hard, tighter when too easy). The candidate closest to the curve replaces the level if it is
    closer than the level is now; a new roll is written to variants.json so the level can be rebuilt the same way."""
    from levelgen import plan as P
    load_scores(ids)
    jobs = []
    for i in ids:
        r = ratio(i)
        offs = ((-0.06, -0.14, -0.24) if r > 1.0 else (0.0, 0.08, 0.16))[:n_offsets]
        if i in force:                                     # its file no longer works (e.g. re-timed): rebuild it anyway
            offs = (0.0, -0.1, 0.1)[:n_offsets]
        base = P.VARIANT.get(i, 0)
        roam = 0
        if i in P.ARENA_LEVELS and r < 1.0:                # open fields come out too easy: denser, tighter hazards
            offs, roam = (0.15, 0.3, 0.45)[:n_offsets], 0   # no roamers: two-axis drifting walls felt unfair
        jobs += [(i, base + k * 11, o, roam) for k in range(n_variants) for o in offs]
    best = {}
    with mp.Pool(min(14, len(jobs))) as pool:
        for i, var, off, d, rep in pool.imap_unordered(_work, jobs):  # noqa: B007
            if d is None:
                print(f"L{i} v{var} off {off:+.2f} FAILED {str(rep)[:120]}", flush=True)
                continue
            r = rep["score"] / curve(i)
            need = max(int(0.7 * shipped_hazards(i)), P.plan(i)["count"] // 2)
            if hazard_count(d) < need:                        # far emptier than the level players know: reject
                print(f"L{i} v{var} off {off:+.2f}: rejected - {hazard_count(d)} hazards, needs {need}", flush=True)
                continue
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
    if "--fit" in sys.argv:
        print("curve a, b, c =", fit())
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
    load_scores(range(1, 101))
    for i in range(FIRST, 101):
        r = ratio(i)
        mark = " <-- hard" if r > HARD else (" <-- easy" if r < EASY else "")
        print(f"L{i:3d} score={_SCORES[i][1]:6.1f} curve={curve(i):6.1f} ratio={r:.2f}{mark}")
    print("outliers:", outliers())


if __name__ == "__main__":
    mp.freeze_support()
    main()
