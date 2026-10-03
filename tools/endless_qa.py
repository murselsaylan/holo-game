"""Endless climb QA: can a human-like player keep climbing, stage after stage, in the real stitched world?

    python tools/endless_qa.py                 # 12 weeks, up to 16 stages each (multiprocess)
    python tools/endless_qa.py 30 20           # 30 weeks, up to 20 stages

A beam-search bot plays EndlessRun (the exact code the game and the ranking server use) with human limits: taps at
least 200 ms apart on a 100 ms grid and a 6 px safety margin. For each week it reports how many stages it climbed
and, if it got stuck, where (stage, map, tier) - a stage or connector nobody can pass shows up as the same stuck map
across weeks. Every bot run is also replayed with the window disabled (the whole world simulated at once) to prove
the rolling window never changes the physics.
"""
import multiprocessing as mp
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import endless as E  # noqa: E402

MARGIN = 6.0
BEAM = 48
STRIDE = 6
MIN_DELAY = 12
MAX_DELAY = 175


def climb_bot(seed, stages, deadline, margin=MARGIN, beam=BEAM):
    """Returns (best EndlessRun, taps) after climbing `stages` stages or running out of ideas / time."""
    root = E.EndlessRun(seed, margin=margin)
    root.world.keep = True
    layer = [(0.0, root, ())]
    best = (root, ())
    for depth in range(4000):
        if time.time() > deadline:
            break
        cand = {}
        for _, node, taps in layer:
            s = node.clone()
            first = depth == 0
            limit = int(E.SPAWN_GRACE_STEPS) - 2 if first else MAX_DELAY
            for k in range(1, limit + 1):
                s.step()
                if s.dead:
                    break
                if k >= MIN_DELAY and k % STRIDE == 0:
                    c = s.clone()
                    c.swap()
                    p = c.sim.pivot
                    score = c.route_progress() - c.sim.t * 2.0
                    key = (int(p.x // 16), int(p.y // 16), int(c.sim.ang / 0.42), c.sim.rot_sign > 0,
                           int((c.sim.t % 6.0) / 0.5))
                    old = cand.get(key)
                    if old is None or score > old[0]:
                        cand[key] = (score, c, taps + (c.n,))
        if not cand:
            break
        ranked = sorted(cand.values(), key=lambda v: -v[0])
        used, layer = {}, []
        for v in ranked:                                   # spread the beam over places, keep time variants
            p = v[1].sim.pivot
            ck = (int(p.x // 60), int(p.y // 60))
            if used.get(ck, 0) < 4:
                used[ck] = used.get(ck, 0) + 1
                layer.append(v)
                if len(layer) >= beam:
                    break
        top = layer[0]
        if top[1].stage > best[0].stage or (top[1].stage == best[0].stage and top[1].metres > best[0].metres):
            best = (top[1], top[2])
        if top[1].stage >= stages:
            break
    return best


class _FullWorld(E.EndlessRun):
    """Reference: the whole world in one LevelData, no window."""

    def __init__(self, seed, count):
        self.seed = seed
        self.world = E.World(seed)
        self.world.keep = True
        self.w0 = 0
        self.count = count
        self.sim = E.Sim(self.world.window_data(0, count))
        self.start_y = self.sim.pivot.y
        self.best_y = self.start_y
        self.rebases = 0

    def stage_at(self, y):
        k = 0
        while k < self.count - 1 and y < self.world.stage(k).top - E.GAP * 0.5:
            k += 1
        return k

    def _advance(self):
        pass


def same_physics(seed, taps, count):
    """Replay with the window and without it: identical to the last bit, step by step."""
    a = E.EndlessRun(seed)
    b = _FullWorld(seed, count)
    ts = sorted(taps)
    i = 0
    while not a.dead and a.n < E.MAX_STEPS and a.stage < count - 2:
        while i < len(ts) and ts[i] <= a.n:
            a.swap()
            b.swap()
            i += 1
        a.step()
        b.step()
        sa, sb = a.sim, b.sim
        if (sa.dead != sb.dead or sa.ang != sb.ang or sa.piv != sb.piv
                or any(oa.x != ob.x or oa.y != ob.y or oa.r != ob.r for oa, ob in zip(sa.orbs, sb.orbs))):
            return False, a.n
        if i >= len(ts) and a.n > ts[-1] + 400:
            break
    return True, a.n


def run_week(args):
    week, stages, secs = args
    seed = E.seed_of(week)
    t0 = time.time()
    best, taps = climb_bot(seed, stages, time.time() + secs)
    k = best.stage
    st = best.world.stage(k)
    same, n = same_physics(seed, taps, k + 4) if taps else (True, 0)
    return {"week": week, "stage": k, "metres": best.metres, "stuck_level": st.level, "stuck_tier": st.tier,
            "rebases": best.rebases, "window_ok": same, "checked_steps": n, "secs": round(time.time() - t0)}


def main():
    weeks = int(sys.argv[1]) if len(sys.argv) > 1 else 12
    stages = int(sys.argv[2]) if len(sys.argv) > 2 else 16
    jobs = [(f"2026-W{w:02d}", stages, 1800) for w in range(30, 30 + weeks)]
    with mp.Pool(min(len(jobs), max(1, (os.cpu_count() or 2) - 1))) as p:
        res = sorted(p.map(run_week, jobs), key=lambda r: r["week"])
    for r in res:
        flag = "" if r["stage"] >= stages else f"   stuck in stage {r['stage']} = level {r['stuck_level']} (tier {r['stuck_tier']})"
        print(f"{r['week']}: {r['stage']:2d} stages, {r['metres']:6d} m, rebases {r['rebases']:2d}, "
              f"window {'OK' if r['window_ok'] else 'MISMATCH at step %d' % r['checked_steps']}, {r['secs']}s{flag}")
    bad = [r for r in res if not r["window_ok"]]
    print("window physics:", "identical in every run" if not bad else f"{len(bad)} MISMATCHES")
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
