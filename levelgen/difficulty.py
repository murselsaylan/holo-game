"""HOLO difficulty score (1.0.8): how hard a level is to clear, measured by playing it on the real simulation.

    python levelgen/difficulty.py              # score all levels -> levels/_difficulty.json (+ a summary)
    python levelgen/difficulty.py 58,59,60     # only these

The reference solution is replayed step by step. Along the way the pair's distance to the static walls and to the
moving hazards (moving walls, chasers, lasers that are on, spinners) is sampled every 3 steps; then the same taps are
replayed with small timing errors to see how precise the player has to be. Every part is a number in "points"; the
score is their sum (see WEIGHTS). levelgen/smooth.py fits a rising curve to the scores and rebuilds the levels that
stand out; new levels are generated against the same curve.

Parts
  time        seconds the reference line takes                       (endurance)
  tempo       taps per second, plus taps that follow within 0.4 s    (hand speed)
  walls       share of the path closer than 25 px to a wall, and how deep under 60 px it goes (narrow passages)
  hazards     close passes (within 45 px of a moving hazard) per 10 s, and the share of the path spent that close
  spacing     close passes that start less than 1 s after the previous one ended (no time to breathe between hazards)
  precision   how narrow each tap's timing window is: the tap moved 1..6 frames early / late (the rest of the line
              shifted with it, as a player would follow up) - does the pair live until the next tap? 1 - share that
              lives, averaged over the taps; plus taps whose window is +-1 frame or less
  speed       pair speed above 0.9 and the hidden end-of-level speed-up
  gates       power-up gates that must be used (shield, grow, shrink, boost, cracked walls, chasers)
  margin      how little safety margin (px) the best line keeps under 25 px
"""
import json
import math
import multiprocessing as mp
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from sim import LevelData, Sim, replay, ARENA_W, EDGE_MARGIN, BUCKET, SIM_DT, _seg_dist  # noqa: E402

OUT = os.path.join(ROOT, "levels", "_difficulty.json")
SAMPLE = 3                      # steps between samples
WALL_NEAR, WALL_DEEP = 25.0, 60.0
HAZ_NEAR = 45.0
BREATH = 1.0                    # seconds between two close passes that still count as a rest
WINDOW = 6                      # each tap is tried up to 6 frames (100 ms) early / late

WEIGHTS = {                     # points per unit of each raw measure
    "time": 0.225,              # per second (halved 2026-10-13: length counts less, hazards fill short-of-curve levels)
    "tempo": 9.0,               # per tap per second
    "quick": 0.35,              # per tap within 0.4 s of the previous one
    "wall_close": 35.0,         # x share of the path within 25 px of a wall
    "wall_depth": 25.0,         # x mean of (60 - clearance) / 60 under 60 px
    "haz_rate": 1.5,            # per close pass per 10 s (a quarter since 2026-10-13: hazards count less)
    "haz_close": 7.5,           # x share of the path within 45 px of a moving hazard (a quarter, as haz_rate)
    "spacing": 2.0,             # per close pass with less than 1 s of rest before it
    "precision": 45.0,          # x mean share of a tap's +-6 frame window that dies
    "razor": 0.8,               # per tap whose window is +-1 frame or less
    "speed": 45.0,              # per unit of speed above 0.9
    "ramp": 15.0,               # x hidden end speed-up
    "gates": 4.0,               # per gate
    "margin": 0.6,              # per px of safety margin under 25
}
GROUPS = {"time": ("time",), "tempo": ("tempo", "quick"), "walls": ("wall_close", "wall_depth"),
          "hazards": ("haz_rate", "haz_close"), "spacing": ("spacing",), "precision": ("precision", "razor"),
          "speed": ("speed", "ramp"), "gates": ("gates",), "margin": ("margin",)}


def _wall_clear(sim, o):
    """Distance from an orb's edge to the nearest static wall or arena edge (px)."""
    lvl = sim.lvl
    x, y = o.x, o.y
    best = min(x - EDGE_MARGIN - o.r, ARENA_W - EDGE_MARGIN - o.r - x, y - EDGE_MARGIN - o.r,
               lvl.height - EDGE_MARGIN - o.r - y)
    rr = 70
    for i in range(int((x - rr) // BUCKET), int((x + rr) // BUCKET) + 1):
        for j in range(int((y - rr) // BUCKET), int((y + rr) // BUCKET) + 1):
            for (_, wx, wy, ww, wh) in lvl.wall_buckets.get((i, j), ()):
                px = wx if x < wx else (wx + ww if x > wx + ww else x)
                py = wy if y < wy else (wy + wh if y > wy + wh else y)
                best = min(best, math.hypot(x - px, y - py) - o.r)
    for (cx, cy, cr) in lvl.circles:
        best = min(best, math.hypot(x - cx, y - cy) - cr - o.r)
    return best


def _haz_clear(sim, o):
    """Distance from an orb's edge to the nearest moving hazard right now (px); 999 when there is none."""
    lvl, t = sim.lvl, sim.t
    x, y = o.x, o.y
    best = 999.0
    for m in lvl.moving_walls:
        wx, wy, ww, wh = lvl.moving_rect(m, t)
        px = wx if x < wx else (wx + ww if x > wx + ww else x)
        py = wy if y < wy else (wy + wh if y > wy + wh else y)
        best = min(best, math.hypot(x - px, y - py) - o.r)
    for ci, c in enumerate(lvl.chasers):
        cr_ = lvl.chaser_rect(c, sim.chase_t0[ci], t)
        if cr_ is not None:
            wx, wy, ww, wh = cr_
            px = wx if x < wx else (wx + ww if x > wx + ww else x)
            py = wy if y < wy else (wy + wh if y > wy + wh else y)
            best = min(best, math.hypot(x - px, y - py) - o.r)
    for l in lvl.lasers:
        if lvl.laser_state(l, t)[0]:
            best = min(best, _seg_dist(x, y, l[0], l[1], l[2], l[3]) - o.r - 3)
    for s in lvl.spinners:
        best = min(best, _seg_dist(x, y, *lvl.spinner_segment(s, t)) - o.r - s[5] * 0.5)
    return best


def _windows(lvl, taps):
    """(mean share of each tap's +-WINDOW frame window that dies before the next tap, taps with a window <= +-1)."""
    sim = Sim(lvl)
    shares, razor = [], 0
    for k, tk in enumerate(taps):
        start = max(taps[k - 1] + 1 if k else 0, tk - WINDOW)
        while sim.n < start and not sim.dead:
            sim.step()
        base = sim.clone()
        nxt = taps[k + 1] if k + 1 < len(taps) else tk + 60
        ok = tried = 0
        alive = []
        for delta in range(-WINDOW, WINDOW + 1):
            target = tk + delta
            if target < start:
                continue
            c = base.clone()
            while c.n < target and not c.dead and not c.won:
                c.step()
            if not c.dead and not c.won:
                c.swap()
            end = min(nxt + delta, target + 120)
            while c.n < end and not c.dead and not c.won:
                c.step()
            tried += 1
            live = not c.dead
            ok += live
            alive.append((delta, live))
        if tried:
            shares.append(1.0 - ok / float(tried))
            width = sum(1 for dl, lv in alive if lv and abs(dl) <= 2)
            if width <= 3 and any(lv for dl, lv in alive if dl == 0):
                razor += 1
        while sim.n < tk and not sim.dead:
            sim.step()
        sim.swap()
    return (sum(shares) / len(shares) if shares else 0.0), razor


def _gates(d):
    n = sum(1 for k in ("growth_zones", "shrink_zones", "boost_pads") if d.get(k))
    n += len(d.get("barriers", [])) + len(d.get("breakables", [])) + len(d.get("chasers", []))
    return n


def measure(d):
    """Raw measures of a level dict (it must carry ref_taps). None if the reference line does not win."""
    lvl = LevelData(d)
    taps = sorted(d["ref_taps"])
    sim = Sim(lvl)
    ti = 0
    walls, hazards = [], []
    while not sim.dead and not sim.won and sim.n < 60 * 400:
        while ti < len(taps) and taps[ti] <= sim.n:
            sim.swap()
            ti += 1
        sim.step()
        if sim.n % SAMPLE == 0:
            walls.append(min(_wall_clear(sim, o) for o in sim.orbs))
            hazards.append(min(_haz_clear(sim, o) for o in sim.orbs))
    if not sim.won:
        return None
    T = sim.n * SIM_DT
    n = max(1, len(walls))
    gaps = [(b - a) * SIM_DT for a, b in zip(taps, taps[1:])]
    # close passes: runs of samples within HAZ_NEAR of a moving hazard, and the rest before each one
    passes, rests, inside, last_end = 0, [], False, None
    for k, h in enumerate(hazards):
        if h < HAZ_NEAR and not inside:
            passes += 1
            if last_end is not None:
                rests.append((k - last_end) * SAMPLE * SIM_DT)
            inside = True
        elif h >= HAZ_NEAR and inside:
            inside, last_end = False, k
    fails, razor = _windows(lvl, taps)
    return {
        "time": T,
        "tempo": len(taps) / max(1.0, T),
        "quick": sum(1 for g in gaps if g < 0.4),
        "wall_close": sum(1 for w in walls if w < WALL_NEAR) / n,
        "wall_depth": sum(max(0.0, WALL_DEEP - min(w, WALL_DEEP)) for w in walls) / (WALL_DEEP * n),
        "haz_rate": passes / max(1.0, T) * 10.0,
        "haz_close": sum(1 for h in hazards if h < HAZ_NEAR) / n,
        "spacing": sum(1 for r in rests if r < BREATH),
        "precision": fails,
        "razor": razor,
        "speed": max(0.0, d["speed"] - 0.9),
        "ramp": d.get("ramp", 0.0),
        "gates": _gates(d),
        "margin": max(0.0, 25.0 - d.get("difficulty", {}).get("margin", 25.0)),
    }


def score(raw):
    """Points per part (GROUPS) and the total."""
    pts = {k: WEIGHTS[k] * raw[k] for k in WEIGHTS}
    parts = {g: sum(pts[k] for k in ks) for g, ks in GROUPS.items()}
    return parts, sum(parts.values())


def _work(i):
    d = json.load(open(os.path.join(ROOT, "levels", f"level{i}.json"), encoding="utf-8"))
    try:
        raw = measure(d)
    except Exception as e:  # pragma: no cover
        return i, None, repr(e)
    return i, raw, LevelData(d).digest


def score_all(ids):
    """{level: {"digest", "raw"}} for ids, reusing cached results of unchanged levels."""
    cache = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}
    todo = []
    for i in ids:
        dg = LevelData.load(i).digest
        c = cache.get(str(i))
        if not c or c.get("digest") != dg or c.get("v") != VERSION:
            todo.append(i)
    if todo:
        with mp.Pool(min(14, len(todo))) as pool:
            for i, raw, dg in pool.imap_unordered(_work, todo):
                if raw is None:
                    print(f"L{i}: reference line does not win ({dg})", flush=True)
                    continue
                cache[str(i)] = {"digest": dg, "raw": raw, "v": VERSION}
        json.dump(cache, open(OUT, "w", encoding="utf-8"), indent=0)
    return {i: cache[str(i)] for i in ids if str(i) in cache}


VERSION = 2                     # bump when measure() changes: cached results are redone


def main():
    ids = [int(x) for x in sys.argv[1].split(",")] if len(sys.argv) > 1 else list(range(1, 101))
    res = score_all(ids)
    tot = {g: 0.0 for g in GROUPS}
    for i in ids:
        if i not in res:
            continue
        parts, total = score(res[i]["raw"])
        for g in GROUPS:
            tot[g] += parts[g]
        print(f"L{i:3d} {total:6.1f}  " + " ".join(f"{g}={parts[g]:.0f}" for g in GROUPS))
    s = sum(tot.values()) or 1.0
    print("share:", {g: f"{100 * v / s:.0f}%" for g, v in tot.items()})


if __name__ == "__main__":
    mp.freeze_support()
    main()
