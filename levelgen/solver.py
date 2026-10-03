"""Beam-search bot that plays HOLO levels on the real deterministic simulation.

Used offline to (a) prove every level is beatable, (b) measure difficulty as the
largest safety margin (px added to the orb radius) with which a level is still
solvable, and (c) derive star positions from an actual winning trajectory.
"""
import os
import sys
import math
import time
import random

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sim import Sim, LevelData, SIM_DT, SPAWN_GRACE, replay  # noqa: E402


class Result:
    def __init__(self, solved, taps=None, time_s=0.0, swaps=0, nodes=0, depth=0, best=0.0):
        self.depth = depth
        self.best = best
        self.solved = solved
        self.taps = taps or []
        self.time_s = time_s
        self.swaps = swaps
        self.nodes = nodes


def solve(lvl, margin=0.0, beam=48, stride=3, min_delay=9, max_delay=175, max_layers=320,
          deadline=None, bias=None):
    """Return Result. `bias(sim)` may add to the beam score (e.g. star pickup)."""
    root = Sim(lvl, margin=margin)
    period = lvl.time_period
    rnd = random.Random(12345).random
    layer = [(0.0, root, ())]
    nodes = 0
    best_prog = 0.0
    for depth in range(max_layers):
        cand = {}
        for _, node, taps in layer:
            if deadline and time.time() > deadline:
                return Result(False, nodes=nodes, depth=depth, best=best_prog)
            s = node.clone()
            first = (depth == 0)
            limit = int(SPAWN_GRACE / SIM_DT) - 2 if first else max_delay
            for k in range(1, limit + 1):
                s.step()
                nodes += 1
                if s.dead:
                    break
                if s.won:
                    return Result(True, list(taps), s.t, len(taps), nodes)
                if k >= min_delay and k % stride == 0:
                    c = s.clone()
                    c.swap()
                    p = c.pivot
                    prog = lvl.progress(p.x, p.y)
                    score = prog * 1000.0 - c.t * 0.05 + (rnd() * 2.5 if period else 0.0)
                    if bias:
                        score += bias(c)
                    key = (int(p.x // 16), int(p.y // 16), int(c.ang / 0.42), c.rot_sign > 0)
                    if period:
                        key += (int((c.t % period) / 0.25),)
                    old = cand.get(key)
                    if old is None or score > old[0]:
                        cand[key] = (score, c, taps + (c.n,))
        if not cand:
            return Result(False, nodes=nodes, depth=depth, best=best_prog)
        ranked = sorted(cand.values(), key=lambda v: -v[0])
        if period:
            # timed hazards: keep several time-variants per place instead of only the earliest ones
            quota = max(4, beam // 10)
            used = {}
            layer = []
            for v in ranked:
                p = v[1].pivot
                ck = (int(p.x // 40), int(p.y // 40), int(v[1].ang / 1.6))
                n = used.get(ck, 0)
                if n < quota:
                    used[ck] = n + 1
                    layer.append(v)
                    if len(layer) >= beam:
                        break
        else:
            layer = ranked[:beam]
        best_prog = max(best_prog, layer[0][0] / 1000.0)
    return Result(False, nodes=nodes, depth=max_layers, best=best_prog)


def max_margin(lvl, lo=0.0, hi=64.0, iters=6, **kw):
    """Largest margin (px) at which the level is still solvable (bisection)."""
    if not solve(lvl, margin=lo, **kw).solved:
        return -1.0
    if solve(lvl, margin=hi, **kw).solved:
        return hi
    for _ in range(iters):
        mid = (lo + hi) / 2.0
        if solve(lvl, margin=mid, **kw).solved:
            lo = mid
        else:
            hi = mid
    return lo


def trajectory(lvl, taps, margin=0.0):
    """Replay `taps`; return list of dicts with orb positions & clearance every 3 steps."""
    sim = Sim(lvl, margin=margin)
    taps = sorted(taps)
    ti = 0
    pts = []
    while not sim.dead and not sim.won and sim.n < 60 * 400:
        while ti < len(taps) and taps[ti] <= sim.n:
            sim.swap()
            ti += 1
        sim.step()
        if sim.n % 3 == 0:
            o = sim.rotating
            pts.append({"n": sim.n, "t": sim.t, "x": o.x, "y": o.y, "px": sim.pivot.x, "py": sim.pivot.y,
                        "clear": sim.clearance(), "prog": lvl.progress(o.x, o.y)})
    return pts, sim


if __name__ == "__main__":
    lvl_id = int(sys.argv[1])
    lvl = LevelData.load(lvl_id)
    t0 = time.time()
    r = solve(lvl, margin=float(sys.argv[2]) if len(sys.argv) > 2 else 0.0)
    print("solved", r.solved, "time", r.time_s, "swaps", r.swaps, "nodes", r.nodes, "wall", round(time.time() - t0, 1))
