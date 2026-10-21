"""Slow field as a PRECISION key: a long narrow throat (wider than the normal pair needs only at exact timing) with a
chain of slow fields over it.  Solver at stride 1 (every frame) so timing precision is what decides."""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sim import LevelData
from levelgen import gate_lab as GL, gates as G, solver as S

def ok(d, margin):
    r = S.solve(LevelData(d), margin=margin, beam=64, stride=1, min_delay=6, max_layers=320)
    return r.solved

t0 = time.time()
for throat in (190, 176, 166, 158, 150, 144):
    for length in (800,):
        ctx, L, s, e = GL.base(W=280.0, H=2300)
        site = GL.find_site(L, ctx)
        x, y, dx, dy, span = site
        half = (span - throat) / 2.0
        L.pillar(x - span / 2 - 6, y - length / 2, half + 6, length)
        L.pillar(x + throat / 2, y - length / 2, half + 6, length)
        for k in range(int(length / 110) + 3):
            zy = y - length / 2 - 120 + k * 110
            L.add("slow_zones", [x, zy, 100])
        d = L.to_level(1, "LAB", s, e, 1.1, 0.2)
        res = []
        for m in (6.0, 9.0):          # same TIMING tolerance: at half speed a pixel margin m is worth 2m px at full speed
            a_ = ok(d, m); b_ = ok(GL.strip(d, ["slow_zones"]), 2 * m)
            res.append(f"with@{int(m)}px={a_} without@{int(2*m)}px={b_}{' KEY' if a_ and not b_ else ''}")
        print(f"throat {throat} length {length}: " + " | ".join(res) + f"  ({time.time()-t0:.0f}s)", flush=True)
