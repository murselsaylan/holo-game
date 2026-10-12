"""Golden cases for revive parity: random runs that die, revive (rewind to a safe point) and go on.

    python tools/revive_golden.py      -> supabase/functions/scores/revive_golden.json
    node supabase/functions/scores/revive_parity_test.ts
"""
import json
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from sim import LevelData, Sim, replay, REVIVE_BACK  # noqa: E402

OUT = os.path.join(ROOT, "supabase", "functions", "scores", "revive_golden.json")


def one(level, rng, kind="R"):
    lvl = LevelData.load(level)
    s = Sim(lvl)
    taps, helps = [], []
    nxt = rng.randint(20, 90)
    while s.n < 60 * 90 and not s.won:
        if s.dead:
            if len([h for h in helps if h[1] in ("R", "R2", "R3")]) >= 5:
                break
            helps.append([s.n, kind])
            s.revive(guarded=kind in ("R2", "R3"), walls=kind == "R3")
            continue
        if s.n >= nxt:
            s.swap()
            taps.append(s.n)
            nxt = s.n + rng.randint(8, 70)
        if rng.random() < 0.0015:
            helps.append([s.n, "S"])
            s.add_shield()
        s.step()
    sim, res = replay(lvl, taps, max_seconds=90.0 + 30.0 * len(helps), assists=helps)
    assert (sim.n, sim.won, sim.dead) == (s.n, s.won, s.dead) or s.n >= 60 * 90, (level, sim.n, s.n)
    return {"level": level, "taps": taps, "assists": helps,
            "py": {"n": sim.n, "won": sim.won, "dead": sim.dead, "orbs": [sim.orbs[0].x, sim.orbs[0].y, sim.orbs[1].x, sim.orbs[1].y],
                   "revive_t": sim.revive_t, "total": res["level_total"] if res else None}}


def main():
    rng = random.Random(505)
    cases = [one(level, rng, kind) for level in range(1, 101, 3) for kind in ("R", "R2", "R3")]
    revs = sum(1 for c in cases for h in c["assists"] if h[1] in ("R", "R2", "R3"))
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(cases, f)
    print(f"{len(cases)} cases, {revs} revives, wins {sum(c['py']['won'] for c in cases)} -> {OUT}")


if __name__ == "__main__":
    main()
