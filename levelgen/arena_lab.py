"""Which arena row type is unsolvable?  python levelgen/arena_lab.py"""
import os, sys, random
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from levelgen import families as F, solver as S, plan as P
from sim import LevelData

for kind in F.ARENA_KINDS:
    for tight in (0.1, 0.5):
        ctx = F.Ctx(30, tight, random.Random(3), height=1900)
        ctx.speed = 1.1
        L, s, e = F.arena(ctx, rows=3, kinds=[kind])
        d = L.to_level(30, "LAB", s, e, 1.1, 0.2)
        m = S.max_margin(LevelData(d), hi=40.0, iters=4, beam=48, max_layers=320)
        print(f"{kind:8s} tight {tight}: margin {m:.1f}", flush=True)
