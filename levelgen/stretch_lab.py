"""Calibrate the tether stretch gates.
  long  (+1): tether x2 -> twice the advance per swap -> beats a chaser wall the normal pair cannot outrun
  short (-1): tether x0.5 -> compact pair -> passes a hole narrower than the normal / shrink pair
    python levelgen/stretch_lab.py long|short"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sim import LevelData
from levelgen import gate_lab as GL, gates as G, solver as S

def solved(d, margin, **kw):
    return S.solve(LevelData(d), margin=margin, beam=64, max_layers=320, **kw).solved

t0 = time.time()
kind = sys.argv[1]
if kind == "long":
    for v in (124, 128, 132, 136):
        ctx, L, s, e = GL.base(W=300.0, H=2300)
        site = GL.find_site(L, ctx)
        G.gate_boost(L, ctx, site, chaser_speed=v)
        pads = L.data["boost_pads"]; L.data["boost_pads"] = []
        zr = pads[0][2]
        x, y, dx, dy, span = site
        for p in pads:                                  # the run is covered by stretch fields instead of boost pads
            L.add("stretch_zones", [p[0], p[1], zr, 1])
        # one more field just before the run so the tether is long when the wall starts moving
        L.add("stretch_zones", [x - dx * 0 + 0, y - 460 / 2.0 - 200, zr, 1]) if abs(dy) > abs(dx) else None
        d = L.to_level(1, "LAB", s, e, 1.1, 0.2)
        a = solved(d, 4.0)
        b = solved(GL.strip(d, ["stretch_zones"]), 0.0)
        print(f"chaser {v}: with long tether solvable={a} | without={b}{'  KEY' if a and not b else ''}  ({time.time()-t0:.0f}s)", flush=True)
else:
    for tw in (118, 112, 106, 100, 94):
        ctx, L, s, e = GL.base(W=280.0, H=2300)
        site = GL.find_site(L, ctx)
        x, y, dx, dy, span = site
        length = 300.0
        half = (span - tw) / 2.0
        L.pillar(x - span / 2 - 6, y - length / 2, half + 6, length)
        L.pillar(x + tw / 2, y - length / 2, half + 6, length)
        zx, zy = G._along(site, -(length / 2 + 130))          # BEFORE the throat in travel direction
        L.add("stretch_zones", [zx, zy, 100, -1])
        d = L.to_level(1, "LAB", s, e, 1.1, 0.2)
        a = solved(d, 4.0)
        b = solved(GL.strip(d, ["stretch_zones"]), 0.0)
        print(f"throat {tw}: with short tether solvable={a} | without={b}{'  KEY' if a and not b else ''}  ({time.time()-t0:.0f}s)", flush=True)
