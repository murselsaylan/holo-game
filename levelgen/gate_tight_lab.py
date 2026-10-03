"""Which gate breaks at high tightness? Build level i at tight t with ONE gate kind (no other hazards) and measure the margin."""
import os, sys, random
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from levelgen import gen as GEN, plan as P, solver as S, families as F, hazards as H
from sim import LevelData

i = int(sys.argv[1]) if len(sys.argv) > 1 else 100
for tight in (1.0, 0.8, 0.6, 0.45):
    for kind in ("gshrink", "ggrow", "gshield", "gboost"):
        pl = P.plan(i)
        rng = random.Random(i)
        ctx = F.Ctx(i, tight, rng, height=P.height_of(i))
        ctx.speed = P.speed_of(i)
        fam = F.FAMILIES["snake_v" if kind == "gboost" else pl["family"]]
        L, s, e = fam(ctx, **({"cols": 2} if kind == "gboost" else pl["fkw"]))
        placed = H.apply_gates(L, ctx, [kind], 1)
        d = L.to_level(i, "LAB", s, e, P.speed_of(i), P.ramp_of(i))
        m = S.max_margin(LevelData(d), hi=40.0, iters=4, beam=48, max_layers=320)
        print(f"L{i} tight {tight}: W={ctx.W:.0f} {kind}: placed={placed} margin={m:.1f}", flush=True)
