"""Sector ranges (1.0.8): every sector has a range for each difficulty value; a level outside it is brought back
without touching its layout beyond what the range needs.

    python levelgen/sector_fix.py              # report: score vs the target curve, corridor width, hazards
    python levelgen/sector_fix.py --fix 90,96  # fix those (or --fix=all: every level of 21..100 out of range)

Ranges (SECTORS): the widest corridor along the reference line, the fewest moving hazards, and the score band around
the target curve (levelgen/curve.json, anchored by the developer: 98 is "exactly as hard as a 98").

Fixes, in order:
  1. corridors wider than the sector's max are narrowed: the walls on both sides grow inward along the straight run
     (never across a junction, a gate, a hazard's path, the start or the goal);
  2. a level under the band gets hazards along its reference line (sliding pistons across the corridor, spinners in
     wider spots), away from the existing ones - more until it is in the band;
  3. every candidate is re-timed and re-solved (levelgen/respeed.py: new reference line, stars, 3-star replay) and
     scored on the simulation; the one closest to the curve with a safety margin >= 8 px is kept.
"""
import json
import math
import multiprocessing as mp
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# sector: widest corridor (px) along the line, fewest moving hazards, score band (x curve)
SECTORS = {
    1: {"max_w": None, "min_haz": 0, "band": (0.6, 1.6)},      # onboarding: left alone
    2: {"max_w": 360, "min_haz": 1, "band": (0.85, 1.25)},
    3: {"max_w": 320, "min_haz": 2, "band": (0.85, 1.25)},
    4: {"max_w": 290, "min_haz": 3, "band": (0.85, 1.25)},
    5: {"max_w": 260, "min_haz": 4, "band": (0.85, 1.25)},
}
HAZ = ("moving_walls", "lasers", "spinners", "chasers", "reverse_walls")
ZONES = ("growth_zones", "shrink_zones", "boost_pads", "shields")


def hazards(d):
    return sum(len(d.get(k, [])) for k in HAZ)


def _edges(lvl, x, y):
    """Distances to the nearest wall left, right, up and down of (x, y) (the arena edges count)."""
    from sim import ARENA_W
    l, r, u, dn = x, ARENA_W - x, y, lvl.height - y
    for (wx, wy, ww, wh) in lvl.walls + lvl.reverse_walls:
        if wy <= y <= wy + wh:
            if wx + ww <= x:
                l = min(l, x - (wx + ww))
            elif wx >= x:
                r = min(r, wx - x)
        if wx <= x <= wx + ww:
            if wy + wh <= y:
                u = min(u, y - (wy + wh))
            elif wy >= y:
                dn = min(dn, wy - y)
    return l, r, u, dn


def _line(d):
    from sim import LevelData
    from levelgen import solver as SV
    lvl = LevelData(d)
    pts, _ = SV.trajectory(lvl, d["ref_taps"])
    return lvl, [(p["px"], p["py"]) for p in pts[::3]]


def _blocked(d, rect, pad=0.0, soft=False):
    """Does rect (x, y, w, h) touch something that must stay free: start, goal, gates, hazards' reach, pillars?
    soft (a wall growing inward): a spinner only blocks where its (corridor-halved) arm reaches, and one-axis
    pistons do not block at all - narrow() moves them to the new wall."""
    x, y, w, h = rect
    def hit(cx, cy, r):
        px = min(max(cx, x), x + w)
        py = min(max(cy, y), y + h)
        return math.hypot(cx - px, cy - py) < r + pad
    if hit(*d["start"], 170) or hit(*d["end"], 170):
        return True
    for k in ZONES:
        for z in d.get(k, []):
            if hit(z[0], z[1], (z[2] if len(z) > 2 else 32) + 40):
                return True
    for c in d.get("circles", []):
        if hit(c[0], c[1], c[2] + 30):
            return True
    for s in d.get("spinners", []):
        if hit(s[0], s[1], (s[2] * 0.5 + 12) if soft else (s[2] + 40)):
            return True
    for m in d.get("moving_walls", []):
        if soft and len(m) <= 8:
            continue
        rx_, ry_ = abs(m[4]), abs(m[5])
        bx, by = m[0] - rx_ - 10, m[1] - ry_ - 10
        if not (bx > x + w or bx + m[2] + 2 * rx_ + 20 < x or by > y + h or by + m[3] + 2 * ry_ + 20 < y):
            return True
    for k in ("breakables", "barriers"):
        for b in d.get(k, []):
            if not (b[0] > x + w + 40 or b[0] + b[2] < x - 40 or b[1] > y + h + 40 or b[1] + b[3] < y - 40):
                return True
    for c in d.get("chasers", []):
        for (bx, by, bw, bh) in ((c[0], c[1], c[2], c[3]), (c[6], c[7], c[8], c[9])):
            if not (bx > x + w + 40 or bx + bw < x - 40 or by > y + h + 40 or by + bh < y - 40):
                return True
    return False


def narrow(d, max_w):
    """Walls grow inward where the corridor along the line is wider than max_w (+30 slack). Returns the slabs."""
    lvl, line = _line(d)
    seen, slabs, moved = set(), [], set()
    d["moving_walls"] = [list(m) for m in d.get("moving_walls", [])]
    for (x, y) in line:
        l, r, u, dn = _edges(lvl, x, y)
        hor = l + r <= u + dn                              # corridor runs up/down: its width is left + right
        width = l + r if hor else u + dn
        if width <= max_w + 30 or width > max_w + 220:     # in range, or a chamber / open field (not a corridor)
            continue
        a, b = (x - l, x + r) if hor else (y - u, y + dn)
        key = (round(a), round(b), hor)
        if key in seen:
            continue
        seen.add(key)
        # how far the same two walls run along the corridor
        lo = hi = (y if hor else x)
        lim = lvl.height if hor else 900
        for sgn in (-1, 1):
            t = lo if sgn < 0 else hi
            while 0 < t < lim:
                t2 = t + sgn * 8
                e = _edges(lvl, x, t2) if hor else _edges(lvl, t2, y)
                ea, eb = ((x - e[0], x + e[1]) if hor else (y - e[2], y + e[3]))
                if abs(ea - a) > 1 or abs(eb - b) > 1:
                    break
                t = t2
            if sgn < 0:
                lo = t
            else:
                hi = t
        lo, hi = lo + 40, hi - 40                          # clear of the junctions at both ends
        if hi - lo < 400:                                  # only long straight runs (a turn chamber is no corridor)
            continue
        cut = (width - max_w) / 2.0

        def pair(t0, t1):
            return [((side, t0, cut, t1 - t0) if hor else (t0, side, t1 - t0, cut)) for side in (a, b - cut)]
        # the run in 40 px steps: slabs only where nothing (hazard, gate, start, goal) is in their way
        segs, t, cur = [], lo, None
        while t < hi:
            t1 = min(hi, t + 40)
            if any(_blocked(d, rc, soft=True) for rc in pair(t, t1)):
                if cur:
                    segs.append(cur)
                cur = None
            else:
                cur = [cur[0], t1] if cur else [t, t1]
            t = t1
        if cur:
            segs.append(cur)
        for (t0, t1) in segs:
            if t1 - t0 < 160:
                continue
            slabs += [[round(v, 1) for v in rc] for rc in pair(t0, t1)]
            # pistons across this stretch move with the walls: a door steps inward, a centred one swings less
            mid = (a + b) / 2.0
            for m in d.get("moving_walls", []):
                if len(m) > 8 or id(m) in moved:
                    continue
                ax, al = (0, 1) if hor else (1, 0)             # across / along the corridor
                c_al = m[al] + m[2 + al] / 2.0
                if not (t0 <= c_al <= t1) or m[4 + ax] == 0:
                    continue
                lo_, hi_ = m[ax] - abs(m[4 + ax]), m[ax] + m[2 + ax] + abs(m[4 + ax])
                if hi_ < a + cut and lo_ > b - cut:
                    continue
                moved.add(id(m))
                if lo_ <= a + cut + 2 and hi_ >= b - cut - 2 and a + 20 < m[ax] and m[ax] + m[2 + ax] < b - 20:
                    m[4 + ax] = round(math.copysign(max(10.0, abs(m[4 + ax]) - cut), m[4 + ax]), 2)   # centred
                elif m[ax] + m[2 + ax] / 2.0 < mid:
                    m[ax] = round(m[ax] + cut, 2)                                                    # a door on the low side
                else:
                    m[ax] = round(m[ax] - cut, 2)
            for l_ in d.get("lasers", []):               # lasers across this stretch end at the new walls
                if hor and abs(l_[1] - l_[3]) < 1 and t0 <= l_[1] <= t1:
                    l_[0], l_[2] = max(min(l_[0], l_[2]), a + cut), min(max(l_[0], l_[2]), b - cut)
                elif not hor and abs(l_[0] - l_[2]) < 1 and t0 <= l_[0] <= t1:
                    l_[1], l_[3] = max(min(l_[1], l_[3]), a + cut), min(max(l_[1], l_[3]), b - cut)
    d["walls"] = d.get("walls", []) + slabs
    return slabs


def _near_ends(d, rect, dist=220.0):
    """Is rect (x, y, w, h) - a hazard's whole sweep - within dist px of the start or the goal?"""
    x, y, w, h = rect
    for k in ("start", "end"):
        px, py = d[k]
        if math.hypot(px - min(max(px, x), x + w), py - min(max(py, y), y + h)) < dist:
            return True
    return False


def fill_field(d, rows, seed, kinds=("door", "spin"), half=80.0):
    """Open fields (no corridors): `rows` new rows in the widest empty bands between the existing ones - by turns a
    pair of doors closing on a gap, and a pair of full-size spinners turning against each other."""
    from sim import ARENA_W
    rng = random.Random(seed * 104729 + d["id"])
    ys = [d["start"][1], d["end"][1]]
    ys += [m[1] + m[3] / 2 for m in d.get("moving_walls", [])] + [s[1] for s in d.get("spinners", [])]
    ys += [c[1] for c in d.get("circles", [])] + [r[1] + r[3] / 2 for r in d.get("reverse_walls", [])]
    ys += [(l[1] + l[3]) / 2 for l in d.get("lasers", [])]
    for k in ZONES:
        ys += [z[1] for z in d.get(k, [])]
    spd = float(d.get("speed", 1.0))
    added, kind = 0, rng.randrange(len(kinds))
    for _ in range(rows):
        srt = sorted(set(round(v) for v in ys))
        gaps = sorted(((b - a, (a + b) / 2.0) for a, b in zip(srt, srt[1:])), reverse=True)
        if not gaps or gaps[0][0] < 300:
            break
        y = gaps[0][1]
        if _near_ends(d, (0, y - 60, ARENA_W, 120), 240.0):
            ys.append(y)
            continue
        if kinds[kind] == "door":                          # two doors closing on a gap (as the arena rows do)
            gx = rng.uniform(240.0, ARENA_W - 240.0)       # the gap: 2 x half at rest, +- 110 as the doors swing
            om = round(rng.uniform(0.8, 1.05) * spd / 1.2, 3)
            ph = round(rng.uniform(0, 6.28), 2)
            d.setdefault("moving_walls", []).append([-20.0, round(y - 23, 2), round(gx - half + 20, 2), 46.0, 55.0, 0.0, om, ph])
            d["moving_walls"].append([round(gx + half, 2), round(y - 23, 2), round(ARENA_W - gx - half + 20, 2), 46.0, -55.0, 0.0, om, ph])
        else:                                              # two big spinners, turning against each other
            hl = rng.uniform(46.0, 54.0)
            om = round(rng.uniform(0.6, 0.8), 2)
            ph = round(rng.uniform(0, 6.28), 2)
            x0 = rng.uniform(250.0, 330.0)
            d.setdefault("spinners", []).append([round(x0, 2), round(y, 2), round(hl, 2), om, ph, 10.0])
            d["spinners"].append([round(ARENA_W - x0, 2), round(y, 2), round(hl, 2), -om, round(ph + 1.7, 2), 10.0])
        ys.append(y)
        kind = (kind + 1) % len(kinds)
        added += 1
    return added


REACH = 260.0                    # an element is "met" when the line passes within this many px of it
SPINNER_FROM = 61                # the first level of the shipped game with a spinner: none is added before it
                                 # (a hazard kind is never added before the level that introduces it)


def _clean(lvl, x, y):
    """Is (x, y) on a plain stretch - the same two walls for 120 px both ways along the corridor? A hazard next to a
    step or a bump of the wall looks wrong."""
    l, r, u, dn = _edges(lvl, x, y)
    hor = l + r <= u + dn
    a, b = (x - l, x + r) if hor else (y - u, y + dn)
    for off in (-120, -60, 60, 120):
        e = _edges(lvl, x, y + off) if hor else _edges(lvl, x + off, y)
        ea, eb = (x - e[0], x + e[1]) if hor else (y - e[2], y + e[3])
        if abs(ea - a) > 3 or abs(eb - b) > 3:
            return False
    return True


def _elements(d):
    """Boxes (x0, y0, x1, y1) of everything a player has to deal with - hazards with their whole sweep, pillars,
    bumpers, gates, power fields."""
    el = []
    for m in d.get("moving_walls", []):
        el.append((m[0] - abs(m[4]), m[1] - abs(m[5]), m[0] + m[2] + abs(m[4]), m[1] + m[3] + abs(m[5])))
    for s in d.get("spinners", []):
        el.append((s[0] - s[2], s[1] - s[2], s[0] + s[2], s[1] + s[2]))
    for l in d.get("lasers", []):
        el.append((min(l[0], l[2]), min(l[1], l[3]), max(l[0], l[2]), max(l[1], l[3])))
    for c in d.get("circles", []):
        el.append((c[0] - c[2], c[1] - c[2], c[0] + c[2], c[1] + c[2]))
    for k in ("reverse_walls", "breakables", "barriers"):
        for r in d.get(k, []):
            el.append((r[0], r[1], r[0] + r[2], r[1] + r[3]))
    for c in d.get("chasers", []):
        el.append((c[0], c[1], c[0] + c[2], c[1] + c[3]))
    for k in ZONES:
        for z in d.get(k, []):
            el.append((z[0] - 30, z[1] - 30, z[0] + 30, z[1] + 30))
    return el


def stretches(d, lvl=None, line=None):
    """Empty stretches of the reference line - nothing within REACH and no pinch under 200 px - as
    [(length px, first index, last index)], longest first; plus the line's length."""
    if line is None:
        lvl, line = _line(d)
    el = _elements(d)
    def met(x, y):
        for (x0, y0, x1, y1) in el:
            if math.hypot(x - min(max(x, x0), x1), y - min(max(y, y0), y1)) < REACH:
                return True
        return lvl._corridor_span(x, y) < 200.0
    out, total, run, start = [], 0.0, 0.0, None
    for k in range(1, len(line)):
        seg = math.hypot(line[k][0] - line[k - 1][0], line[k][1] - line[k - 1][1])
        total += seg
        if met(*line[k]):
            if start is not None:
                out.append((run, start, k - 1))
            run, start = 0.0, None
        else:
            if start is None:
                start = k
            run += seg
    if start is not None:
        out.append((run, start, len(line) - 1))
    return sorted(out, reverse=True), total


def emptiness(d, lvl=None, line=None):
    """(longest empty stretch px, share of the line that is empty, its index range)."""
    st, total = stretches(d, lvl, line)
    if not st:
        return 0.0, 0.0, None
    return st[0][0], sum(x[0] for x in st) / max(1.0, total), (st[0][1], st[0][2])


def fill_gaps(d, seed, max_empty=600.0, soft=False, limit=7):
    """A hazard in the middle of the longest empty stretch of the line, again and again until no stretch is longer
    than max_empty (a stretch with no plain spot for one is left and the next longest tried). soft (a level already
    hard enough): easy ones - a short piston, a small spinner - that give the stretch something to do without making
    the level much harder. Rules: only on plain straight walls (_clean), no spinner before SPINNER_FROM, nothing by
    the start or the goal, never touching a wall."""
    rng = random.Random(seed * 15485863 + d["id"])
    lvl, line = _line(d)
    spd = float(d.get("speed", 1.0))
    added, tried, dead = 0, set(), set()
    while added < limit:
        todo = [x for x in stretches(d, lvl, line)[0] if x[0] > max_empty and (x[1], x[2]) not in dead]
        if not todo:
            break
        _, a_, b_ = todo[0]
        placed = False
        order = sorted(range(a_, b_ + 1), key=lambda k: abs(k - (a_ + b_) / 2.0))      # the middle first
        for k in order:
            if k in tried:
                continue
            tried.add(k)
            x, y = line[k]
            l, r, u, dn = _edges(lvl, x, y)
            hor = l + r <= u + dn
            width = l + r if hor else u + dn
            if width < 150 or _blocked(d, (x - 60, y - 60, 120, 120), pad=30) or (d.get("walls") and not _clean(lvl, x, y)):
                continue
            cx, cy = (x - l + width / 2, y) if hor else (x, y - u + width / 2)
            if d.get("walls") and not _clean(lvl, cx, cy):     # where the hazard itself sits, not only where the line runs
                continue
            if d["id"] >= SPINNER_FROM and width > 230 and rng.random() < (0.6 if soft else 0.45):
                hl = rng.uniform(24.0, 30.0) if soft else rng.uniform(32.0, 40.0)
                sp = [round(cx, 2), round(cy, 2), round(hl, 2), round(rng.choice((1, -1)) * rng.uniform(0.6, 0.85), 2),
                      round(rng.uniform(0, 6.28), 2), 10.0]
                if _near_ends(d, (sp[0] - hl, sp[1] - hl, 2 * hl, 2 * hl)):
                    continue
                d.setdefault("spinners", []).append(sp)
            else:
                pw = max(44.0, width * (0.22 if soft else 0.30))
                rngx = max(30.0, ((width - pw) / 2.0 - 8.0) * (0.6 if soft else 1.0))
                om = round(rng.uniform(0.75, 1.0 if soft else 1.25) * spd / 1.2, 3)
                if hor:
                    m = [round(cx - pw / 2, 2), round(cy - 23, 2), round(pw, 2), 46.0, round(rngx, 2), 0.0, om, round(rng.uniform(0, 6.28), 2)]
                else:
                    m = [round(cx - 23, 2), round(cy - pw / 2, 2), 46.0, round(pw, 2), 0.0, round(rngx, 2), om, round(rng.uniform(0, 6.28), 2)]
                sweep = (m[0] - m[4], m[1] - m[5], m[2] + 2 * m[4], m[3] + 2 * m[5])
                if any(sweep[0] < w_[0] + w_[2] - 2 and sweep[0] + sweep[2] > w_[0] + 2 and sweep[1] < w_[1] + w_[3] - 2
                       and sweep[1] + sweep[3] > w_[1] + 2 for w_ in d.get("walls", [])) or _near_ends(d, sweep):
                    continue
                d.setdefault("moving_walls", []).append(m)
            added += 1
            placed = True
            break
        if not placed:
            dead.add((a_, b_))                             # no plain spot in this stretch: on to the next
    return added


def add_hazards(d, n, seed, min_gap=300.0):
    """n hazards on the reference line, evenly spread through the gaps between the existing ones."""
    rng = random.Random(seed * 7919 + d["id"])
    lvl, line = _line(d)
    taken = [(h[0] + h[2] / 2, h[1] + h[3] / 2) for h in d.get("moving_walls", [])]
    taken += [(s[0], s[1]) for s in d.get("spinners", [])]
    taken += [((l_[0] + l_[2]) / 2, (l_[1] + l_[3]) / 2) for l_ in d.get("lasers", [])]
    spd = float(d.get("speed", 1.0))
    added = 0
    order = list(range(len(line)))
    rng.shuffle(order)
    for k in order:
        if added >= n:
            break
        x, y = line[k]
        if not (0.06 < k / len(line) < 0.94):
            continue
        if any(math.hypot(x - tx, y - ty) < min_gap for tx, ty in taken):
            continue
        l, r, u, dn = _edges(lvl, x, y)
        hor = l + r <= u + dn
        width = l + r if hor else u + dn
        if width < 150 or _blocked(d, (x - 60, y - 60, 120, 120), pad=30) or (d.get("walls") and not _clean(lvl, x, y)):
            continue
        cx, cy = (x - l + width / 2, y) if hor else (x, y - u + width / 2)
        if d.get("walls") and not _clean(lvl, cx, cy):
            continue
        if d["id"] >= SPINNER_FROM and width > 230 and rng.random() < 0.5:   # a spinner in the middle of the corridor
            hl = rng.uniform(30.0, 38.0)
            d.setdefault("spinners", []).append([round(cx, 2), round(cy, 2), round(hl, 2),
                                                 round(rng.choice((1, -1)) * rng.uniform(0.65, 0.9), 2),
                                                 round(rng.uniform(0, 6.28), 2), 10.0])
        else:                                              # a piston sliding across the corridor
            pw = max(44.0, width * 0.30)
            rngx = max(30.0, (width - pw) / 2.0 - 8.0)
            om = round(rng.uniform(0.85, 1.25) * spd / 1.2, 3)
            if hor:
                m = [round(cx - pw / 2, 2), round(cy - 23, 2), round(pw, 2), 46.0, round(rngx, 2), 0.0, om, round(rng.uniform(0, 6.28), 2)]
            else:
                m = [round(cx - 23, 2), round(cy - pw / 2, 2), 46.0, round(pw, 2), 0.0, round(rngx, 2), om, round(rng.uniform(0, 6.28), 2)]
            # never resting in, or sliding into, a wall
            sweep = (m[0] - m[4], m[1] - m[5], m[2] + 2 * m[4], m[3] + 2 * m[5])
            if any(sweep[0] < w_[0] + w_[2] - 2 and sweep[0] + sweep[2] > w_[0] + 2 and sweep[1] < w_[1] + w_[3] - 2
                   and sweep[1] + sweep[3] > w_[1] + 2 for w_ in d.get("walls", [])) or _near_ends(d, sweep):
                continue
            d.setdefault("moving_walls", []).append(m)
        taken.append((cx, cy))
        added += 1
    return added


def _solve(d):
    """Re-time / re-solve a changed level (respeed's path: reference line, stars, 3-star replay)."""
    from levelgen import respeed as R
    i = d["id"]
    orig = json.load
    def fake(fp, *a, **k):
        if getattr(fp, "name", "").endswith(f"level{i}.json"):
            fp.read()
            return json.loads(json.dumps(d))
        return orig(fp, *a, **k)
    json.load = fake
    try:
        return R.respeed(i)[1:]
    finally:
        json.load = orig


def _job(a):
    i, n_add, seed, do_narrow = a
    os.environ["RESPEED_BEAM"] = "48"
    from levelgen import difficulty as D
    from levelgen import smooth as S
    d = json.load(open(os.path.join(ROOT, "levels", f"level{i}.json"), encoding="utf-8"))
    sec = SECTORS[d.get("sector", 1)]
    slabs = narrow(d, sec["max_w"]) if (do_narrow and sec["max_w"]) else []
    added = add_hazards(d, n_add, seed) if n_add else 0
    if not slabs and not added:
        return i, n_add, seed, do_narrow, None, "nothing to change", 0
    try:
        nd, msg = _solve(d)
    except Exception as e:  # pragma: no cover
        return i, n_add, seed, do_narrow, None, repr(e)[:120], 0
    if nd is None:
        return i, n_add, seed, do_narrow, None, msg, 0
    raw = D.measure(nd)
    sc = D.score(raw)[1] if raw else 0.0
    return i, n_add, seed, do_narrow, nd, f"{msg} slabs={len(slabs)} added={added}", sc / S.curve(i)


def report(ids):
    from levelgen import smooth as S
    sc = S.load_scores(ids)
    out = {}
    for i in ids:
        d = json.load(open(os.path.join(ROOT, "levels", f"level{i}.json"), encoding="utf-8"))
        sec = SECTORS[d.get("sector", 1)]
        r = sc[i] / S.curve(i)
        out[i] = (r, hazards(d), sec)
    return out


def main():
    from levelgen.gen import save
    from levelgen.plan import ARENA_LEVELS
    ids = list(range(21, 101))
    arg = [a for a in sys.argv[1:] if a.startswith("--fix")]
    rep = report(ids)
    todo = []
    for i in ids:
        r, n, sec = rep[i]
        low = r < sec["band"][0] or n < sec["min_haz"]
        print(f"L{i:3d} ratio={r:.2f} hazards={n}{'  <-- low' if low else ''}")
        if low or (sec["max_w"] and i not in ARENA_LEVELS):
            todo.append((i, r))
    if not arg:
        return
    val = arg[0].split("=", 1)[1] if "=" in arg[0] else "all"
    if val != "all":
        want = {int(x) for x in val.split(",")}
        todo = [t for t in todo if t[0] in want] + [(i, rep[i][0]) for i in want if i not in [t[0] for t in todo]]
    jobs = []
    for i, r in todo:
        sec = rep[i][2]
        if "--narrow-only" in sys.argv or (r >= sec["band"][0] and rep[i][1] >= sec["min_haz"]):   # only its corridor width
            jobs.append((i, 0, 0, True))
            continue
        need = max(0, sec["min_haz"] - rep[i][1])
        deficit = max(0.0, 1.0 - r)
        n = max(need, int(round(deficit * 10)))          # ~ +10 % of the curve per hazard
        if "--more" in sys.argv:                           # a second pass for the ones still under the band
            for n_add in (n + 1, n + 2, n + 3):
                for seed in (1, 2):
                    jobs.append((i, n_add, seed, i not in ARENA_LEVELS))
            continue
        for n_add in sorted({n, n + 1} if n else {1}):     # two counts, one roll each: ~1 h for the campaign
            jobs.append((i, n_add, 0, i not in ARENA_LEVELS))
    print(f"{len(jobs)} candidates for {len(todo)} levels", flush=True)
    best = {}
    with mp.Pool(14) as pool:
        for i, n_add, seed, nar, nd, msg, ratio in pool.imap_unordered(_job, jobs):
            print(f"L{i} +{n_add} s{seed} narrow={nar}: {('ratio %.2f ' % ratio) if nd else ''}{msg}", flush=True)
            if nd is None or nd["difficulty"]["margin"] < 8.0:
                continue
            lo, hi = rep[i][2]["band"]
            # prefer: in the band, narrowed (the width range holds), then closest to the curve
            key = (lo <= ratio <= hi, nar, -abs(ratio - 1.0))
            if i not in best or key > best[i][0]:
                best[i] = (key, nd, ratio, msg)
    for i, _ in todo:
        hi = rep[i][2]["band"][1]
        if i in best and rep[i][0] - (0.15 if "--narrow-only" in sys.argv else 0.02) < best[i][2] <= max(hi, rep[i][0] + (0.15 if "--narrow-only" in sys.argv else 0.05)):   # never pushed over the band
            save(best[i][1])
            print(f"L{i}: {rep[i][0]:.2f} -> {best[i][2]:.2f}  saved ({best[i][3]})", flush=True)
        else:
            print(f"L{i}: kept ({rep[i][0]:.2f})", flush=True)


if __name__ == "__main__":
    mp.freeze_support()
    main()
