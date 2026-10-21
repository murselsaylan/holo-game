"""Golden vectors for the slow / stretch fields (levels 101+): Python results that sim.ts must reproduce exactly.
    python tools/fields_golden.py   -> supabase/functions/scores/fields_golden.json  (run fields_parity_test.ts after)"""
import os, sys, json, random
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from sim import LevelData, replay

OUT = os.path.join(ROOT, "supabase", "functions", "scores", "fields_golden.json")
rng = random.Random(7)
cases = []
for lid in (1, 20, 50):                                   # three different geometries
    base = json.load(open(os.path.join(ROOT, "levels", f"level{lid}.json"), encoding="utf-8"))
    sx, sy = base["start"]; ex, ey = base["end"]
    for k in range(6):
        d = dict(base)
        zs = []
        for _ in range(rng.randint(1, 3)):                # fields scattered along the first part of the route
            t = rng.uniform(0.0, 0.5)
            zs.append([round(sx + (ex - sx) * t + rng.uniform(-90, 90)), round(sy + (ey - sy) * t + rng.uniform(-90, 90)), rng.choice([70, 90, 120])])
        d["slow_zones"] = zs if k % 3 != 1 else []
        d["stretch_zones"] = [z + [rng.choice([1, -1])] for z in zs[::-1]] if k % 3 != 0 else []
        d["ref_taps"] = []
        lvl = LevelData(d)
        for rep in range(25):
            n = rng.randint(6, 40)
            taps = sorted(set(rng.randint(30, 1500) for _ in range(n)))
            taps = [t for i, t in enumerate(taps) if i == 0 or t - taps[i - 1] >= 5]
            sim, res = replay(lvl, taps, max_seconds=40.0)
            o = sim.orbs
            cases.append({"raw": d if rep == 0 else None, "case": len(cases) // 25, "taps": taps,
                          "py": {"won": sim.won, "dead": sim.dead, "n": sim.n, "swaps": sim.swaps,
                                 "orbs": [o[0].x, o[0].y, o[1].x, o[1].y], "tether": sim.tether, "base": sim.tether_base,
                                 "smooth": sim.smooth, "t": sim.t}})
json.dump(cases, open(OUT, "w"), separators=(",", ":"))
print("fields_golden.json:", len(cases), "cases;", sum(1 for c in cases if c["py"]["won"]), "wins,", sum(1 for c in cases if c["py"]["dead"]), "deaths")
