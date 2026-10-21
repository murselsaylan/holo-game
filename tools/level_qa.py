"""Level QA: is every level really passable by a human?

    python tools/level_qa.py               # all levels (multiprocess), writes levels/_qa.json
    python tools/level_qa.py 12 40 77      # some levels

Per level:
  replay   the reference solution wins on the real simulation
  taps/s   busiest one-second window and the shortest gap between taps of the reference run
  jitter   share of runs that still win when every tap is off by up to +-1 / +-2 / +-3 frames (16 / 33 / 50 ms)
  coarse   solvable by a *slower* player: taps >= 200 ms apart, timing on a 100 ms grid, with a 6 px safety margin
  spawn    the pair does not start inside a wall
"""
import json
import multiprocessing as mp
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from sim import LevelData, Sim, replay  # noqa: E402
from levelgen import solver as S  # noqa: E402

TRIALS = 20


def taps_stats(taps):
    if len(taps) < 2:
        return 0, 999
    gaps = [b - a for a, b in zip(taps, taps[1:])]
    best = 0
    j = 0
    for i in range(len(taps)):
        while taps[i] - taps[j] > 60:
            j += 1
        best = max(best, i - j + 1)
    return best, min(gaps)


def jitter_rate(lvl, taps, spread, rng):
    win = 0
    for _ in range(TRIALS):
        t2 = sorted(max(1, t + rng.randint(-spread, spread)) for t in taps)
        sim, res = replay(lvl, t2, max_seconds=max(120.0, lvl.par_time * 6))
        win += 1 if res is not None else 0
    return win / float(TRIALS)


def qa(i):
    lvl = LevelData.load(i)
    taps = list(lvl.raw["ref_taps"])
    out = {"level": i}
    sim, res = replay(lvl, taps, max_seconds=max(120.0, lvl.par_time * 6))
    out["replay"] = res is not None and res["stars"] == 3
    per_s, gap = taps_stats(taps)
    out["taps_per_s"] = per_s
    out["min_gap_steps"] = gap
    rng = random.Random(i)
    out["jitter"] = {str(sp): jitter_rate(lvl, taps, sp, rng) for sp in (1, 2, 3)}
    r = S.solve(lvl, margin=6.0, beam=64, stride=6, min_delay=12, max_layers=320)
    out["coarse"] = bool(r.solved)
    s0 = Sim(lvl)
    out["spawn"] = not any(s0._wall_hit(o.x, o.y, o.r) for o in s0.orbs)
    return out


def verdict(q):
    bad = []
    if not q["replay"]:
        bad.append("replay")
    if not q["spawn"]:
        bad.append("spawn")
    if not q["coarse"]:
        bad.append("coarse")
    if q["jitter"]["2"] < 0.25:
        bad.append("jitter2<25%")
    if q["taps_per_s"] > 7:
        bad.append("taps/s>7")
    return bad


if __name__ == "__main__":
    mp.freeze_support()
    ids = [int(a) for a in sys.argv[1:]] or list(range(1, 141))
    rows = []
    with mp.Pool(min(14, len(ids))) as pool:
        for q in pool.imap_unordered(qa, ids):
            rows.append(q)
    rows.sort(key=lambda r: r["level"])
    bad = {}
    print("lvl  replay spawn coarse taps/s gap  jitter(1f/2f/3f)")
    for q in rows:
        v = verdict(q)
        if v:
            bad[q["level"]] = v
        print(f"{q['level']:3d}  {'ok' if q['replay'] else 'NO':6s} {'ok' if q['spawn'] else 'NO':5s} {'ok' if q['coarse'] else 'NO':6s} "
              f"{q['taps_per_s']:5d} {q['min_gap_steps']:4d}  {q['jitter']['1']:.2f}/{q['jitter']['2']:.2f}/{q['jitter']['3']:.2f}"
              f"{'   <-- ' + ','.join(v) if v else ''}")
    json.dump({str(r['level']): r for r in rows}, open(os.path.join(ROOT, "levels", "_qa.json"), "w"), indent=1)
    print("\nlevels with problems:", json.dumps(bad))
