"""Difficulty ordering: every level should be about as hard as its number says.

    python levelgen/rebalance.py            # report only
    python levelgen/rebalance.py --fix      # re-roll (variants.json) and regenerate levels that are far too easy / too hard, up to 3 rounds

Score D = 0.55*time + 0.30*swaps + 1.2*hazards + 5*gates + 30*(speed-0.9)   (all measured from the level file and its
reference solution). The target rises smoothly from ~10 (level 1) to ~100 (level 100). A level is an outlier when D / target
is outside [0.6, 1.5] (boss levels 20/40/60/80/100 must not be easier than 0.9 x target).
"""
import json
import multiprocessing as mp
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
VARIANTS = os.path.join(ROOT, "levelgen", "variants.json")
BOSS = (20, 40, 60, 80, 100)


def score(i):
    d = json.load(open(os.path.join(ROOT, "levels", f"level{i}.json"), encoding="utf-8"))
    df = d["difficulty"]
    haz = sum(len(d.get(k, [])) for k in ("moving_walls", "lasers", "spinners", "circles", "reverse_walls"))
    gates = sum(1 for k in ("barriers", "breakables", "chasers", "shrink_zones", "growth_zones") if d.get(k))
    gates += len(d.get("chasers", [])) + len(d.get("barriers", [])) + len(d.get("breakables", []))
    return 0.55 * df["ref_time"] + 0.30 * df["swaps"] + 1.2 * haz + 5.0 * min(gates, 6) + 30.0 * (d["speed"] - 0.9)


def target(i):
    return 10.0 + 90.0 * ((i - 1) / 99.0) ** 0.9


def outliers(D):
    out = []
    for i in range(4, 101):
        r = D[i] / target(i)
        lo = 0.9 if i in BOSS else 0.6
        if r < lo or r > 1.5:
            out.append(i)
    return out


def _work(i):
    from levelgen import gen as GEN
    d, rep = GEN.make(i, 0)
    return i, d, rep


def main():
    D = {i: score(i) for i in range(1, 101)}
    print("sector means of D/target:")
    for s in range(5):
        ids = range(s * 20 + 1, s * 20 + 21)
        print(f"  {s*20+1:3d}-{s*20+20:3d}: D avg {sum(D[i] for i in ids)/20:5.1f}  (target avg {sum(target(i) for i in ids)/20:5.1f})")
    bad = outliers(D)
    print("outliers:", [(i, round(D[i] / target(i), 2)) for i in bad])
    if "--fix" not in sys.argv or not bad:
        return
    from levelgen import gen as GEN
    var = json.load(open(VARIANTS)) if os.path.exists(VARIANTS) else {}
    for rnd in range(3):
        if not bad:
            break
        for i in bad:
            var[str(i)] = var.get(str(i), 0) + 1
        json.dump(var, open(VARIANTS, "w"))
        with mp.Pool(min(14, len(bad))) as pool:
            for i, d, rep in pool.imap_unordered(_work, [(i) for i in bad]):
                if d:
                    GEN.save(d)
                    print(f"round {rnd+1}: L{i} regenerated ({rep['family']}, {rep['time']}s, {rep['swaps']} swaps)")
                else:
                    var[str(i)] -= 1                      # keep the old file and the matching variant
                    print(f"round {rnd+1}: L{i} FAILED, kept old")
        json.dump(var, open(VARIANTS, "w"))
        D = {i: score(i) for i in range(1, 101)}
        bad = outliers(D)
        print("outliers now:", [(i, round(D[i] / target(i), 2)) for i in bad])


if __name__ == "__main__":
    mp.freeze_support()
    main()
