"""Dry run of the whole campaign: build every level (no solving), report errors and missing gates."""
import os, sys, traceback
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from levelgen import gen as GEN, plan as P

bad = 0
for i in range(1, 101):
    try:
        pl0 = P.plan(i)
        d, pl, ctx = GEN.build(i, P.difficulty(i))
        want = [pl["gates"][k % len(pl["gates"])] for k in range(pl["gcount"])] if pl["gates"] and pl["gcount"] else []
        if pl["family"] in ("gates", "chambers") and pl["gates"]:
            want = [k for k in pl["fkw"].get("door_kinds", []) if k]
        miss = len(want) - len(pl["placed"])
        flag = f"  <-- MISSING {miss}" if miss > 0 else ""
        if miss > 0:
            bad += 1
        print(f"L{i:3d} {pl['family']:8s} W={ctx.W:4.0f} H={d['height']} kit={','.join(pl['kit']) or '-':32s} gates={pl['placed']}{flag}")
    except Exception:
        bad += 1
        print(f"L{i:3d} ERROR"); traceback.print_exc()
print("problems:", bad)
