"""Kinetic bumpers (reverse walls), sim v10: the swinging orb may never move deeper into one.

v9 muted a bumper after a bounce until both orbs had left it; with the pivot resting against the bumper it never
un-muted and the other orb swung straight inside ("seken duvarın dibinde içine girme").

    python tools/bumper_test.py
"""
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from sim import LevelData, Sim, rect_penetration  # noqa: E402

ok = True


def check(name, cond, info=""):
    global ok
    ok &= bool(cond)
    print(("PASS " if cond else "FAIL ") + name, info)


base = dict(LevelData.load(11).raw)              # an empty arena with one bumper in the middle
for k in ("walls", "moving_walls", "lasers", "spinners", "circles", "growth_zones", "shrink_zones", "boost_pads",
          "shields", "stars", "breakables", "chasers", "barriers"):
    base[k] = []
base["reverse_walls"] = [[315.0, 800.0, 270.0, 24.0]]
base["end"] = [450, 100]
lvl = LevelData(base)
bx, by, bw, bh = lvl.reverse_walls[0]

for label, pivot, ang in (("pivot resting under the bumper", (bx + bw / 2, by + bh + 14.5), math.pi),
                          ("pivot resting on top of the bumper", (bx + bw / 2, by - 14.5), 0.0),
                          ("pivot at the bumper's end", (bx + bw + 14.0, by + bh / 2), math.pi / 2)):
    s = Sim(lvl, record_events=True, fixed_angle=ang)
    s.swaps, s.t = 1, 10.0                       # past the spawn grace
    piv = s.orbs[s.piv]
    piv.x, piv.y = pivot
    s._place_rotating()
    worst = -1e9
    bounces = 0
    for _ in range(600):
        s.step()
        if s.dead or s.won:
            break
        rot = s.orbs[1 - s.piv]
        worst = max(worst, rect_penetration(rot.x, rot.y, rot.r, bx, by, bw, bh))
        bounces += sum(1 for e in s.events if e[0] == "reverse")
        s.events.clear()
    check(label + ": swinging orb never inside", worst <= 0.5, f"(deepest {worst:.2f}px, {bounces} bounces)")
    check(label + ": it keeps bouncing", bounces >= 2)

print("ALL OK" if ok else "SOME FAILED")
sys.exit(0 if ok else 1)
