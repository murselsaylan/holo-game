"""Calibration lab for power-up gates: is each gate (a) solvable WITH its pickup and (b) unsolvable WITHOUT it?

    python levelgen/gate_lab.py shrink|grow|shield|boost
"""
import os
import sys
import random
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from sim import LevelData  # noqa: E402
from levelgen import families as F, gates as G, solver as S  # noqa: E402
from levelgen.hazards import leg_slots  # noqa: E402


def base(W=280.0, cols=2, H=2300, seed=1):
    ctx = F.Ctx(1, 0.3, random.Random(seed), height=H)
    ctx.W = W
    ctx.room = W
    L, s, e = F.snake_v(ctx, cols=cols)
    return ctx, L, s, e


def find_site(L, ctx, min_leg=1000):
    """Middle of the first long straight leg (vertical)."""
    route = L.route
    for a, b in zip(route, route[1:]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        ln = (dx * dx + dy * dy) ** 0.5
        if ln >= min_leg and abs(dx) < 1:
            return ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0, dx / ln, dy / ln, ctx.W)
    raise SystemExit("no long leg")


def strip(d, keys):
    d2 = dict(d)
    for k in keys:
        d2[k] = []
    return d2


def build(kind, W, param, H=2300):
    ctx, L, s, e = base(W=W, H=H)
    site = find_site(L, ctx)
    if kind == "shrink":
        G.gate_shrink(L, ctx, site, throat_w=param)
    elif kind == "grow":
        G.gate_grow(L, ctx, site)
    elif kind == "shield":
        G.gate_shield(L, ctx, site)
    elif kind == "boost":
        G.gate_boost(L, ctx, site, chaser_speed=param)
    d = L.to_level(1, "LAB", s, e, 1.1, 0.2)
    return d


def solved(d, margin, beam=64):
    lvl = LevelData(d)
    r = S.solve(lvl, margin=margin, beam=beam, max_layers=320)
    return r.solved, (r.time_s if r.solved else None), (r.swaps if r.solved else None)


if __name__ == "__main__":
    kind = sys.argv[1]
    t0 = time.time()
    if kind == "shrink":
        for tw in (150, 130, 116, 104, 92):
            d = build("shrink", 280, tw)
            w_ok = solved(d, 8.0)
            wo = solved(strip(d, ["shrink_zones"]), 0.0)
            print(f"throat {tw}: with shrink@8px solvable={w_ok[0]}  | without shrink@0px solvable={wo[0]}  ({time.time()-t0:.0f}s)", flush=True)
    elif kind == "grow":
        d = build("grow", 280, 0)
        print("with grow@10:", solved(d, 10.0), "| without grow@0:", solved(strip(d, ["growth_zones"]), 0.0))
    elif kind == "shield":
        d = build("shield", 280, 0)
        print("with shield@10:", solved(d, 10.0), "| without shield@0:", solved(strip(d, ["shields"]), 0.0))
    elif kind == "boost":
        for v in (70, 90, 110, 130, 150, 175):
            d = build("boost", 280, v)
            a = solved(d, 4.0)
            b = solved(strip(d, ["boost_pads"]), 0.0)
            print(f"chaser {v} px/s: with pads solvable={a[0]} | without pads solvable={b[0]}  ({time.time()-t0:.0f}s)", flush=True)
