"""Checkpoints (1.0.9): how many a level gets, where they go, and the audit rules.

Count (by the reference solution's time, difficulty.ref_time - the clean run's length), one flag per ~35-40 s of route:
    ref_time < 30 s, or a (nearly) wall-free level  -> 0
    otherwise  n = 1 + floor((ref_time - 30) / 40):  30-70 s -> 1, 70-110 s -> 2, 110-150 s -> 3, ... (no upper limit)
    The flags sit at i/(n+1) of the route, so the gaps are ref_time/(n+1) = 15-37 s.
    "Wall-free": the walls cover less than WALL_FREE_SHARE (2 %) of the arena - open space with no or a few thin walls
    (levels 8 16 36 43 45 47 53 57 66 72 74 88 94 102 103 122 and the short ones 4 5 6 13 26 34 84 ...).
    FROZEN: levels in KEEP keep the flags they have (140: tuned by the developer, the reference for the spacing).

Place: on the reference route (the pivot's position at the step where the route has covered the target share of the
waypoint path), searched in a +-WINDOW share around the target for the safest spot. A spot is safe when
    * no moving wall (whole sweep), spinner (whole disc), laser, mine, chaser (trigger + whole sweep) or growth /
      shrink / boost / slow / stretch field is closer than HAZARD_MIN (150 px, edge to point),
    * the nearest solid wall is at least WALL_MIN away (the pair's tether is 100 px: a flag in a gate or narrow hole
      is not wanted) - and the roomiest candidate wins,
    * it is START_END_MIN (250 px) away from the start and the end.
When no candidate meets the full rule the hazard distance is relaxed in steps (HAZARD_TIERS) and the level is reported.

Usage:  python levelgen/checkpoints.py [ids|a-b] [--write] [--audit]
        (no --write: only reports; --write adds ONLY the "checkpoints" key to levels/levelN.json)
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import sim as S  # noqa: E402

SHORT_MAX = 30.0          # ref_time below this: no checkpoint
SEG_S = 40.0              # one more flag per this many seconds above SHORT_MAX
WALL_FREE_SHARE = 0.02    # walls cover less of the arena than this: no flags
KEEP = {140}              # frozen levels (flags tuned by hand)
# (hazard clearance, wall clearance, window): the first row is the rule; later rows are used (and reported) only when
# a level has no spot that meets the one before - narrow corridors / hazard-dense routes
TIERS = ((150.0, 100.0, 0.10), (120.0, 100.0, 0.10), (90.0, 100.0, 0.10), (150.0, 100.0, 0.16), (110.0, 100.0, 0.16),
         (90.0, 85.0, 0.16), (80.0, 70.0, 0.20), (60.0, 60.0, 0.25), (30.0, 45.0, 0.30))
HAZARD_MIN = TIERS[-1][0]          # the audit's hard floors
WALL_MIN = TIERS[-1][1]
START_END_MIN = 250.0
MIN_GAP = 0.20            # two flags are at least this share of the route apart
FAR = 1e9


def wall_share(raw):
    h = float(raw.get("height", S.ARENA_H))
    return sum(w[2] * w[3] for w in raw.get("walls", [])) / (S.ARENA_W * h)


def count_for(ref_time, raw=None):
    if ref_time < SHORT_MAX or (raw is not None and wall_share(raw) < WALL_FREE_SHARE):
        return 0
    return 1 + int((ref_time - SHORT_MAX) // SEG_S)


def targets(n):
    return [(i + 1) / (n + 1.0) for i in range(n)]


def _rect_d(x, y, r):
    rx, ry, w, h = r
    px = rx if x < rx else (rx + w if x > rx + w else x)
    py = ry if y < ry else (ry + h if y > ry + h else y)
    return math.hypot(x - px, y - py)


def wall_clear(lvl, x, y):
    d = FAR
    for r in lvl.walls + lvl.reverse_walls + lvl.breakables:
        d = min(d, _rect_d(x, y, r))
    return d


def hazard_clear(lvl, x, y):
    """Edge distance to the nearest non-wall hazard / field (moving things over their whole sweep)."""
    d = FAR
    for m in lvl.moving_walls:
        rx, ry = abs(m[4]), abs(m[5])
        d = min(d, _rect_d(x, y, (m[0] - rx, m[1] - ry, m[2] + 2 * rx, m[3] + 2 * ry)))
    for s in lvl.spinners:
        d = min(d, math.hypot(x - s[0], y - s[1]) - s[2] - s[5] * 0.5)
    for l in lvl.lasers:
        d = min(d, S._seg_dist(x, y, l[0], l[1], l[2], l[3]) - 3)
    for c in lvl.circles:
        d = min(d, math.hypot(x - c[0], y - c[1]) - c[2])
    for zs in (lvl.growth, lvl.shrink, lvl.boost, lvl.slow, lvl.stretch):
        for z in zs:
            d = min(d, math.hypot(x - z[0], y - z[1]) - z[2])
    for c in lvl.chasers:
        sp = math.hypot(c[4], c[5])
        reach = c[10] if c[10] > 0 else 6000.0
        ex, ey = (c[4] / sp * reach, c[5] / sp * reach) if sp > 1e-4 else (0.0, 0.0)
        x0, x1 = min(c[0], c[0] + ex), max(c[0] + c[2], c[0] + c[2] + ex)
        y0, y1 = min(c[1], c[1] + ey), max(c[1] + c[3], c[1] + c[3] + ey)
        d = min(d, _rect_d(x, y, (x0, y0, x1 - x0, y1 - y0)), _rect_d(x, y, (c[6], c[7], c[8], c[9])))
    return d


def route(lvl, taps):
    """The reference run as [(step, pivot x, pivot y, max_progress)]; None when it does not win."""
    sim = S.Sim(lvl)
    taps = sorted(taps)
    ti = 0
    out = []
    while sim.n < 60 * 400 and not sim.won and not sim.dead:
        while ti < len(taps) and taps[ti] <= sim.n:
            sim.swap()
            ti += 1
        sim.step()
        p = sim.pivot
        out.append((sim.n, p.x, p.y, sim.max_progress))
    return out if sim.won else None


def choose(lvl, taps):
    """Returns (list of [x, y], notes)."""
    n = count_for(float(lvl.raw.get("difficulty", {}).get("ref_time", lvl.par_time)), lvl.raw)
    if n == 0:
        return [], []
    rt = route(lvl, taps)
    if rt is None:
        return [], ["reference does not win"]
    picks, notes = [], []
    prev_prog = 0.0
    for ti, tgt in enumerate(targets(n)):
        best = None
        for ti_, (htier, wtier, window) in enumerate(TIERS):
            cands = []
            for (_, x, y, mp) in rt:
                if abs(mp - tgt) > window or mp < prev_prog + (0.6 / (n + 1) if ti else 0.0):
                    continue
                if math.hypot(x - lvl.start[0], y - lvl.start[1]) < START_END_MIN or \
                        math.hypot(x - lvl.end[0], y - lvl.end[1]) < START_END_MIN:
                    continue
                w, h = wall_clear(lvl, x, y), hazard_clear(lvl, x, y)
                if h >= htier and w >= wtier:
                    # roomiest first, then closest to the target share
                    cands.append((-min(w, 200.0), abs(mp - tgt), x, y, mp, w, h))
            if cands:
                best = min(cands)
                if ti_:
                    notes.append(f"flag {ti + 1}: relaxed to hazard>={htier:.0f} wall>={wtier:.0f} window {window:.2f}")
                break
        if best is None:
            notes.append(f"flag {ti + 1}: NO safe spot")
            continue
        _, _, x, y, mp, w, h = best
        picks.append([round(x, 1), round(y, 1)])
        prev_prog = mp
        notes.append(f"flag {ti + 1} at {mp * 100:.0f}% wall {w:.0f} hazard {min(h, 9999):.0f}")
    return picks, notes


def audit(lvl, taps=None):
    """Rule check of the checkpoints a level carries. Returns a list of problems (empty = fine)."""
    cps = lvl.checkpoints
    ref_time = float(lvl.raw.get("difficulty", {}).get("ref_time", lvl.par_time))
    bad = []
    want = count_for(ref_time, lvl.raw)
    if len(cps) != want:
        bad.append(f"{len(cps)} checkpoints, ref_time {ref_time:.1f}s wants {want}")
    last_p = -1.0
    for i, (x, y) in enumerate(cps):
        if not (20 <= x <= S.ARENA_W - 20 and 20 <= y <= lvl.height - 20):
            bad.append(f"flag {i + 1} outside the arena")
        w = wall_clear(lvl, x, y)
        h = hazard_clear(lvl, x, y)
        if w < WALL_MIN - 1:
            bad.append(f"flag {i + 1}: wall {w:.0f} px < {WALL_MIN:.0f}")
        if h < HAZARD_MIN - 1:
            bad.append(f"flag {i + 1}: hazard/field {h:.0f} px < {HAZARD_MIN:.0f}")
        for nm, pt in (("start", lvl.start), ("end", lvl.end)):
            if math.hypot(x - pt[0], y - pt[1]) < START_END_MIN - 1:
                bad.append(f"flag {i + 1} too close to {nm}")
        p = lvl.progress(x, y)
        if p <= last_p:
            bad.append(f"flag {i + 1} not in route order")
        last_p = p
    if taps:                                   # the reference run must light every flag, in order, and still win
        sim = S.Sim(lvl)
        ts = sorted(taps)
        ti = 0
        while sim.n < 60 * 400 and not sim.won and not sim.dead:
            while ti < len(ts) and ts[ti] <= sim.n:
                sim.swap()
                ti += 1
            sim.step()
        if not sim.won:
            bad.append("reference run does not win")
        elif sim.cp_next != len(cps):
            bad.append(f"reference run lights {sim.cp_next} of {len(cps)} flags")
    return bad


def _ids(args):
    ids = []
    for a in args:
        if a.startswith("--"):
            continue
        for part in a.split(","):
            if "-" in part:
                lo, hi = part.split("-")
                ids += list(range(int(lo), int(hi) + 1))
            elif part:
                ids.append(int(part))
    return ids or list(range(1, S.MAX_LEVELS + 1))


def main(argv):
    write = "--write" in argv
    do_audit = "--audit" in argv
    tot = {}
    for lid in _ids(argv):
        path = os.path.join(ROOT, "levels", f"level{lid}.json")
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8", newline="") as f:
            raw = f.read()
        d = json.loads(raw)
        lvl = S.LevelData(d)
        taps = d.get("ref_taps", [])
        if do_audit:
            bad = audit(lvl, taps)
            tot[len(lvl.checkpoints)] = tot.get(len(lvl.checkpoints), 0) + 1
            print(f"level {lid:3d}: {len(lvl.checkpoints)} flags " + ("OK" if not bad else "PROBLEM: " + "; ".join(bad)))
            continue
        if lid in KEEP and "checkpoints" in d:
            print(f"level {lid:3d}: frozen ({len(d['checkpoints'])} flags kept)")
            tot[len(d["checkpoints"])] = tot.get(len(d["checkpoints"]), 0) + 1
            continue
        cps, notes = choose(lvl, taps)
        tot[len(cps)] = tot.get(len(cps), 0) + 1
        print(f"level {lid:3d} ref {d.get('difficulty', {}).get('ref_time')}: {len(cps)} flags  " + " | ".join(notes))
        if write:
            if cps:
                d["checkpoints"] = cps
            else:
                d.pop("checkpoints", None)
            new = json.dumps(d, separators=(",", ":"), ensure_ascii=False)
            if new != raw:
                with open(path, "w", encoding="utf-8", newline="") as f:
                    f.write(new)
    print("flags per level:", tot)


if __name__ == "__main__":
    main(sys.argv[1:])
