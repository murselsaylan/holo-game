"""Golden cases for checkpoint parity: runs that light flags, die, resume from the latest flag ("C") and go on.

    python tools/checkpoint_golden.py      -> supabase/functions/scores/checkpoint_golden.json
    deno run -A --no-check supabase/functions/scores/checkpoint_parity_test.ts

The bot follows the reference taps with a little timing noise (so it usually dies a while after a flag), resumes at
the latest flag, then taps at random until it dies again, wins or the time is up.
"""
import json
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from sim import LevelData, Sim, replay, MIN_TAP_GAP  # noqa: E402

OUT = os.path.join(ROOT, "supabase", "functions", "scores", "checkpoint_golden.json")


def _plan(s, horizon=150, max_delay=26):
    """Greedy look-ahead for the part of a run after a resume: the delay before the next tap that survives longest and
    gets furthest along the route (None: nothing survives)."""
    best, best_key = None, None
    for d in range(0, max_delay, 2):
        c = s.clone()
        for _ in range(d):
            c.step()
            if c.dead or c.won:
                break
        if not (c.dead or c.won):
            c.swap()
            for _ in range(horizon):
                c.step()
                if c.dead or c.won:
                    break
        key = (c.won, not c.dead, c.max_progress)
        if best_key is None or key > best_key:
            best, best_key = d, key
    return best


def one(level, rng, noise, bot=False):
    lvl = LevelData.load(level)
    ref = sorted(lvl.raw.get("ref_taps", []))
    s = Sim(lvl)
    taps, helps = [], []
    cut = int(len(ref) * rng.uniform(0.55, 0.85))      # exact up to there (lights the flags), noisy after
    jit = [t if i < cut else t + rng.randint(-noise, noise + 2) for i, t in enumerate(ref)]
    ji = 0
    nxt = None
    while s.n < 60 * 100 and not s.won:
        if s.dead:
            if s.cp_state is None or len(helps) >= 4:
                break
            helps.append([s.n, "C"])
            assert s.resume_checkpoint()
            nxt = s.n + rng.randint(8, 40)           # after a resume the bot taps at random
            if bot:
                nxt = s.n + (_plan(s) or 0) + 1
            continue
        if nxt is None:
            while ji < len(jit) and jit[ji] <= s.n:
                if not taps or jit[ji] - taps[-1] >= 4:
                    s.swap()
                    taps.append(s.n)
                ji += 1
        elif s.n >= nxt:
            s.swap()
            taps.append(s.n)
            nxt = s.n + rng.randint(8, 70)
            if bot:
                nxt = s.n + max(MIN_TAP_GAP, (_plan(s) or 0) + 1)
        s.step()
    sim, res = replay(lvl, taps, max_seconds=100.0, assists=helps)
    assert (sim.n, sim.won, sim.dead, sim.cp_used) == (s.n, s.won, s.dead, s.cp_used), (level, sim.n, s.n)
    return {"level": level, "taps": taps, "assists": helps,
            "py": {"n": sim.n, "won": sim.won, "dead": sim.dead, "cp_next": sim.cp_next, "cp_used": sim.cp_used,
                   "orbs": [sim.orbs[0].x, sim.orbs[0].y, sim.orbs[1].x, sim.orbs[1].y],
                   "stars": sum(sim.stars), "shields": sim.shields, "total": res["level_total"] if res else None}}


def main():
    rng = random.Random(909)
    cases = []
    for level in range(1, 141):
        d = LevelData.load(level)
        if not d or not d.checkpoints:
            continue
        for noise in (1, 4, 9):
            cases.append(one(level, rng, noise))
    cases = [c for c in cases if c["py"]["cp_next"] > 0]
    used = sum(c["py"]["cp_used"] for c in cases)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(cases, f)
    print(f"{len(cases)} cases, {used} resumes, wins {sum(c['py']['won'] for c in cases)} -> {OUT}")


if __name__ == "__main__":
    main()
