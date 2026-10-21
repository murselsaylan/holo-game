"""Audit of the new levels (default 101-140):  python tools/audit_new_levels.py [first last]

 1. the file exists and the reference solution wins with 3 stars on the real simulation
 2. tutorial levels really contain their new mechanic (101 slow field, 121 short-tether field, 124 long-tether field)
 3. 'no empty level': the longest stretch of the reference line with nothing in reach stays under ~600 px
 4. nothing hazardous within 200 px of the start or the goal
 5. a sensible table: height, speed, corridor, margin, swaps, time, hazards, slow/stretch counts
"""
import os
import sys
import math
import json

os.environ["SDL_VIDEODRIVER"] = "dummy"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from sim import LevelData, replay  # noqa: E402
from levelgen import sector_fix as SF  # noqa: E402

lo = int(sys.argv[1]) if len(sys.argv) > 1 else 101
hi = int(sys.argv[2]) if len(sys.argv) > 2 else 140
TUTORIAL = {101: ("slow_zones", None), 121: ("shrink_zones", None)}
problems, rows = [], []


def near(d, x, y, dist):
    """Dangerous things closer than `dist` px to (x, y)."""
    hit = []
    for m in d.get("moving_walls", []):
        if math.hypot(x - min(max(x, m[0]), m[0] + m[2]), y - min(max(y, m[1]), m[1] + m[3])) < dist:
            hit.append("moving wall")
    for l in d.get("lasers", []):
        mx, my = (l[0] + l[2]) / 2, (l[1] + l[3]) / 2
        if math.hypot(x - mx, y - my) < dist:
            hit.append("laser")
    for s in d.get("spinners", []):
        if math.hypot(x - s[0], y - s[1]) < dist:
            hit.append("spinner")
    for c in d.get("circles", []):
        if math.hypot(x - c[0], y - c[1]) - c[2] < dist:
            hit.append("mine")
    return hit


for i in range(lo, hi + 1):
    p = os.path.join(ROOT, "levels", f"level{i}.json")
    if not os.path.exists(p):
        problems.append((i, "missing file"))
        continue
    d = json.load(open(p, encoding="utf-8"))
    lvl = LevelData(d)
    sim, res = replay(lvl, d.get("ref_taps", []), max_seconds=400)
    if res is None:
        problems.append((i, "reference solution does not win"))
        continue
    if res["stars"] != 3:
        problems.append((i, f"reference collects {res['stars']} stars"))
    if i in TUTORIAL:
        key, kind = TUTORIAL[i]
        zs = d.get(key, [])
        if not zs or (kind is not None and not any((z[3] if len(z) > 3 else 1) == kind for z in zs)):
            problems.append((i, f"tutorial level lacks its {key} (kind {kind})"))
    try:
        longest, share, _ = SF.emptiness(d)
    except Exception as e:                          # pragma: no cover
        longest, share = -1.0, -1.0
        problems.append((i, f"emptiness check failed: {e!r}"))
    if longest > 650:
        problems.append((i, f"empty stretch {longest:.0f} px"))
    # rule: a stretch field must not overlap an obstacle (a stretched tether next to a hazard kills at once)
    haz = [(m[0] + m[2] / 2, m[1] + m[3] / 2, max(m[2], m[3]) / 2 + max(m[4], m[5])) for m in d.get("moving_walls", [])]
    haz += [(q[0], q[1], q[2]) for q in d.get("spinners", [])] + [(q[0], q[1], q[2]) for q in d.get("circles", [])]
    haz += [((l[0] + l[2]) / 2, (l[1] + l[3]) / 2, math.hypot(l[2] - l[0], l[3] - l[1]) / 2) for l in d.get("lasers", [])]
    for z in d.get("stretch_zones", []) + d.get("shrink_zones", []):
        if any(math.hypot(z[0] - hx, z[1] - hy) < z[2] + hr + 30 for hx, hy, hr in haz):
            problems.append((i, f"stretch field at ({z[0]:.0f},{z[1]:.0f}) overlaps a hazard (< 30 px)"))
        if math.hypot(z[0] - d["start"][0], z[1] - d["start"][1]) < z[2] + 60 or math.hypot(z[0] - d["end"][0], z[1] - d["end"][1]) < z[2] + 60:
            problems.append((i, "stretch field on the start or the goal"))
    sx, sy = d["start"]
    ex, ey = d["end"]
    for tag, (x, y) in (("start", (sx, sy)), ("goal", (ex, ey))):
        h = near(d, x, y, 200.0)
        if h:
            problems.append((i, f"{'/'.join(sorted(set(h)))} within 200 px of the {tag}"))
    from levelgen import checkpoints as CPS  # checkpoints (1.0.9): count by ref time, safe spots, lit in order by the reference run
    for msg in CPS.audit(lvl, d.get("ref_taps")):
        problems.append((i, "checkpoint: " + msg))
    haz = sum(len(d.get(k, [])) for k in ("moving_walls", "lasers", "spinners", "circles", "breakables", "chasers", "barriers"))
    dd = d.get("difficulty", {})
    rows.append((i, d["title"], int(lvl.height), lvl.speed, dd.get("corridor"), dd.get("margin"), res["swaps"], res["time"], haz,
                 len(d.get("slow_zones", [])), len(d.get("stretch_zones", [])), round(longest)))

print(f"{'lvl':>3} {'title':26s} {'H':>5} {'speed':>5} {'W':>4} {'m':>5} {'taps':>4} {'sec':>5} {'haz':>3} {'slow':>4} {'strch':>5} {'empty':>5}")
for r in rows:
    print(f"{r[0]:3d} {r[1][:26]:26s} {r[2]:5d} {r[3]:5.2f} {r[4]!s:>4} {r[5]!s:>5} {r[6]:4d} {r[7]:5.1f} {r[8]:3d} {r[9]:4d} {r[10]:5d} {r[11]:5d}")
print(f"\nchecked {len(rows)} of {hi - lo + 1} levels; problems: {len(problems)}")
for pr in problems:
    print("  ", pr)
sys.exit(1 if problems else 0)
