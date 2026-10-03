"""Energy-barrier rules (sim v10):

  * a shield lets the pair phase through energy barriers - also a grown orb (it used to bounce back off them)
  * while phasing, solid walls and every other hazard still count (the pair used to be fully invulnerable while
    an orb stayed inside a barrier, so the other orb could swing through solid walls)

    python tools/barrier_test.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from sim import LevelData, Sim, BREAK_R  # noqa: E402

ok = True


def check(name, cond):
    global ok
    ok &= bool(cond)
    print(("PASS " if cond else "FAIL ") + name)


lvl = LevelData.load(29)                       # barrier (521.89, 687.3, 249.23, 40) next to the solid wall (0, 665, 522, 84)
bx, by, bw, bh = lvl.barriers[0]
s = Sim(lvl)
o = s.orbs[0]


def fatal(x, y, r, phasing):
    o.x, o.y, o.r = x, y, r
    return s._fatal(o, (), (), (), phasing)


mid_x = bx + bw / 2.0
check("normal orb touching a barrier = barrier hit", (fatal(mid_x, by - 12, 15.0, False) or (0, 0, 0, None))[3] is True)
check("grown orb touching a barrier = barrier hit (no bounce)", (fatal(mid_x, by - 24, 26.0, False) or (0, 0, 0, None))[3] is True)
check("phasing: barrier ignored", fatal(mid_x, by + bh / 2.0, 15.0, True) is None)
check("phasing: grazing the wall next to the barrier is fine", fatal(bx + 4, by + bh / 2.0, 15.0, True) is None)
hit = fatal(300.0, 700.0, 15.0, True)         # deep inside the solid wall, nowhere near the barrier
check("phasing: a solid wall still kills", hit is not None and hit[3] is False)
hit = fatal(300.0, 700.0, 26.0, False)
check("grown orb vs solid wall = ordinary hit", hit is not None and hit[3] is False)
check("BREAK_R unchanged", BREAK_R == 21.0)

# Full step: park one orb inside the barrier with the phase timer running and swing the other into the solid wall.
s = Sim(lvl)
s.swaps, s.t = 1, 10.0
s.barrier_t, s.shields = 0.8, 0
piv = s.orbs[s.piv]
piv.x, piv.y = bx + 40, by + bh / 2.0
s.ang = 3.14159                                 # the swinging orb 100 px to the left: inside the solid wall
s.tether = 100.0
s._place_rotating()
s.step()
check("parked in a barrier, swinging into a solid wall -> dead", s.dead)

print("ALL OK" if ok else "SOME FAILED")
sys.exit(0 if ok else 1)
