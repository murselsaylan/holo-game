"""Which levels get which gates (dry run, no solving)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from levelgen import gen as GEN, plan as P

rows = []
for i in range(1, 101):
    pl0 = P.plan(i)
    if not pl0["gates"]:
        continue
    tight = P.difficulty(i)
    d, pl, ctx = GEN.build(i, tight)
    want = [pl["gates"][k % len(pl["gates"])] for k in range(pl["gcount"])]
    rows.append((i, pl["family"], round(ctx.W), d["height"], want, pl["placed"]))
    miss = len(want) - len(pl["placed"])
    print(f"L{i:3d} {pl['family']:8s} W={ctx.W:4.0f} H={d['height']} want={want} placed={pl['placed']}{'  <-- MISSING ' + str(miss) if miss else ''}")
print(len(rows), "gate levels")
