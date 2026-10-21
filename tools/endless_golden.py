"""Golden endless runs for the server parity test (supabase/functions/scores/parity_endless_test.ts).

    python tools/endless_golden.py [seconds]     random runs + bot runs that climb through several stages
    (v5 = this file's output, endless_golden_v5.json. endless_golden.json (v4) and endless_golden_v3.json are FROZEN: made
     by the 1.0.8 / 1.0.7 code, the server keeps replaying them - do not regenerate them with the current endless.py.)
"""
import json
import os
import random
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import endless as E  # noqa: E402

OUT = os.path.join(ROOT, "supabase", "functions", "scores", "endless_golden_v5.json")


def record(seed, taps, end=None, assists=None):
    run = E.replay(seed, taps, end, assists=assists)
    s = run.sim
    return {"seed": seed, "v": E.ENDLESS_VERSION, "taps": list(taps), "end": end, "assists": assists or [],
            "py": {"n": run.n, "dead": run.dead, "metres": run.metres, "stars": run.stars, "points": run.points,
                   "w0": run.w0, "stage": run.stage,
                   "orbs": [s.orbs[0].x, s.orbs[0].y, s.orbs[1].x, s.orbs[1].y]}}


def main():
    global OUT
    if "--legacy" in sys.argv:
        raise SystemExit("v3 / v4 goldens are frozen (see the module doc)")
    if False:                            # a 1.0.7 game: v3 seeds, the shipped campaign maps
        sys.argv.remove("--legacy")
        E.ENDLESS_VERSION = 3
        leg = os.path.join(ROOT, "levelgen", "legacy_levels")
        for name in os.listdir(leg):
            if name.startswith("level") and name.endswith(".json"):
                E._RAW[int(name[5:-5])] = json.load(open(os.path.join(leg, name), encoding="utf-8"))
        OUT = OUT.replace("endless_golden.json", "endless_golden_v3.json")
    secs = float(sys.argv[1]) if len(sys.argv) > 1 else 240
    rng = random.Random(77)
    cases = []
    for i in range(40):                                   # short random runs, many seeds
        seed = E.seed_of(f"2026-W{30 + i % 20:02d}", "%08x" % rng.getrandbits(32))
        taps, n = [], rng.randint(20, 90)
        for _ in range(rng.randint(3, 40)):
            taps.append(n)
            n += rng.randint(8, 80)
        cases.append(record(seed, taps, rng.choice([None, n + 200])))
    for i in range(12):                                   # runs that die, revive (R2 / R) or buy shields, go on
        seed = E.seed_of("2026-W40", "%08x" % rng.getrandbits(32))
        run = E.EndlessRun(seed)
        taps, helps, n_next = [], [], rng.randint(30, 80)
        while run.n < 60 * 60 and len([h for h in helps if h[1] != "S"]) <= E.MAX_REVIVES:
            if run.dead:
                if len([h for h in helps if h[1] != "S"]) >= E.MAX_REVIVES:
                    break
                kind = ("R", "R2", "R3")[i % 3]
                helps.append([run.n, kind])
                run.sim.revive(guarded=kind in ("R2", "R3"), walls=kind == "R3")
                continue
            if run.n >= n_next:
                run.swap()
                taps.append(run.n)
                n_next = run.n + rng.randint(12, 70)
            if rng.random() < 0.002:
                helps.append([run.n, "S"])
                run.sim.add_shield()
            run.step()
        cases.append(record(seed, taps, None, helps))
        assert cases[-1]["py"]["n"] == run.n, (cases[-1]["py"]["n"], run.n)
    import endless_qa as Q
    t0 = time.time()
    for i in range(4):                                    # bot runs that cross several stages (window moves)
        seed = E.seed_of("2026-W40", "%08x" % (0x1000 + i))
        best, taps = Q.climb_bot(seed, 4, time.time() + secs / 4)
        cases.append(record(seed, sorted(taps), best.n))
    for ev in (E.EV_STARS, E.EV_SHIELD, E.EV_BUBBLE):     # bot runs that fly through a stage carrying each event kind
        n = 0
        while True:
            n += 1
            seed = E.seed_of("2026-W41", "%08x" % (0x2000 + n))
            w = E.World(seed)
            if w.stage(1).event == ev:
                break
        best, taps = Q.climb_bot(seed, 3, time.time() + secs / 4)
        cases.append(record(seed, sorted(taps), best.n))
        print("event", ev, "seed", seed, "reached stage", cases[-1]["py"]["stage"], "stars", cases[-1]["py"]["stars"])
    plans = []                                            # zones + events far beyond what a run reaches
    for i in range(12):
        seed = E.seed_of(f"2026-W{40 + i % 6:02d}", "%08x" % rng.getrandbits(32))
        w = E.World(seed)
        plans.append({"seed": seed, "v": E.ENDLESS_VERSION,
                      "plan": [[w.stage(k).level, w.stage(k).sector, w.stage(k).event] for k in range(40)]})
    cases.append({"plans": plans})
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(cases, f)
    runs = [c for c in cases if "py" in c]
    print(len(runs), "cases; max stage", max(c["py"]["stage"] for c in runs), "max w0", max(c["py"]["w0"] for c in runs),
          f"({time.time() - t0:.0f}s bots) ->", OUT)


if __name__ == "__main__":
    main()
