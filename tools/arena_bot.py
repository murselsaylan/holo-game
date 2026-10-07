"""A look-ahead bot for the arena mode: how long can a careful player survive? (balancing aid)

    python tools/arena_bot.py [runs] [seconds]

Every few steps it tries "tap now" against "don't" on a copy of the physics (the hazards as they stand, radar crosses
already scheduled included) with a few tap rhythms afterwards, and keeps the choice that survives longer.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import arena  # noqa: E402

HORIZON = 100
RHYTHMS = (0, 14, 22, 34, 50)


def _survives(sim, tap_now, every, target=None):
    """Steps survived on a copy of the physics; with a target height (closing zone) also how close it got there."""
    c = sim.clone()
    if tap_now:
        c.swap()
    for k in range(1, HORIZON + 1):
        if every and k % every == 0:
            c.swap()
        c.step()
        if c.dead:
            return k
    if target is not None:                       # (x, y): closer to the next energy core is better
        return HORIZON + 1 - min(((o.x - target[0]) ** 2 + (o.y - target[1]) ** 2) ** 0.5 for o in c.orbs) / 1000.0
    return HORIZON + 1


def play(seed, max_secs=300):
    run = arena.ArenaRun(seed)
    taps = []
    while not run.dead and run.seconds < max_secs:
        if run.n % 4 == 0:
            ty = run.core[:2] if run.core else None
            a = max(_survives(run.sim, False, e, ty) for e in RHYTHMS)
            b = max(_survives(run.sim, True, e, ty) for e in RHYTHMS)
            if b > a:
                taps.append(run.n)
                run.swap()
        run.step()
    return run, taps


if __name__ == "__main__":
    runs = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    secs = float(sys.argv[2]) if len(sys.argv) > 2 else 300
    for i in range(runs):
        seed = 1000 + 7919 * i
        run, taps = play(seed, secs)
        check = arena.replay(seed, taps, run.n)
        print(f"seed {seed}: {run.seconds:6.1f} s  wave {run.wave:2d}  cores {run.cores:3d}  out of time {run.timed_out!s:5}  "
              f"stars {run.stars:2d}  points {run.points:5d}  "
              f"taps {len(taps)}  replay {'ok' if (check.n, check.points) == (run.n, run.points) else 'MISMATCH'}")
