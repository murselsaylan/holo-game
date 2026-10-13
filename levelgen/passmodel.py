"""HOLO pass model (1.0.8): how many tries a level takes a player, and how long they spend to clear it.

    python levelgen/passmodel.py               # measure every level (cached in levels/_windows.json) + report
    python levelgen/passmodel.py 58,59,60      # only these

Why: a weighted sum of "difficulty points" needs arbitrary weights. Players feel one thing - how often they fail and
how much time a failure costs - so the model predicts that directly (the approach live games use: pass rate per
attempt, attempts per level, time to clear; difficulty rises in a sawtooth, never a straight ramp).

1. Tap windows. The reference line is replayed; each tap is tried up to WINDOW frames (250 ms) early and late with the
   rest of the line shifted along (a player follows up from where the pair really is). The contiguous range of
   offsets around 0 the pair survives until the next tap is that tap's window [a, b] in frames.
2. A player's tap lands with a timing error ~ Normal(0, SIGMA) (people tapping to an expected moment: 25-60 ms, a
   touch screen adds a frame or two of jitter). p_tap = Phi((b + .5) / s) - Phi((a - .5) / s).
3. One try clears the level with P = product of p_tap. Expected tries A = 1 / P (each try independent - a player who
   learns a level does better, which LEARN folds in for the first tries).
4. Time to clear: the expected time of a failed try (where along the line the deaths fall) x failed tries + the
   level's own time + RESTART seconds per retry.

Targets (target_tries / target_minutes): tries rise slowly with the level number in a sawtooth (each sector opens
with a breather and ends on a boss); time to clear is capped, so a long level must be safer per tap.
"""
import json
import math
import multiprocessing as mp
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from sim import LevelData, Sim, SIM_DT  # noqa: E402

OUT = os.path.join(ROOT, "levels", "_windows.json")
VERSION = 1
WINDOW = 15                     # frames tried each way (250 ms)
SIGMA = 2.7                     # frames (45 ms): a player's tap timing error (calibrated in calibrate())
RESTART = 2.5                   # seconds a retry costs besides the replayed part
LEARN = 1.6                     # the first try at a level is this much less precise (sigma x LEARN), easing to 1


def windows(d):
    """[(a, b, t_seconds)] per tap of the reference line: the frames it may be early (a <= 0) / late (b >= 0)."""
    lvl = LevelData(d)
    taps = sorted(d["ref_taps"])
    sim = Sim(lvl)
    out = []
    for k, tk in enumerate(taps):
        start = max(taps[k - 1] + 1 if k else 0, tk - WINDOW)
        while sim.n < start and not sim.dead:
            sim.step()
        base = sim.clone()
        nxt = taps[k + 1] if k + 1 < len(taps) else tk + 90
        alive = {}
        for delta in range(-WINDOW, WINDOW + 1):
            target = tk + delta
            if target < start:
                alive[delta] = False
                continue
            c = base.clone()
            while c.n < target and not c.dead and not c.won:
                c.step()
            if not c.dead and not c.won:
                c.swap()
            end = min(nxt + delta, target + 150)
            while c.n < end and not c.dead and not c.won:
                c.step()
            alive[delta] = not c.dead
        a = 0
        while a - 1 >= -WINDOW and alive.get(a - 1):
            a -= 1
        b = 0
        while b + 1 <= WINDOW and alive.get(b + 1):
            b += 1
        out.append((a, b, round(tk * SIM_DT, 2)))
        while sim.n < tk and not sim.dead:
            sim.step()
        sim.swap()
    while not sim.dead and not sim.won and sim.n < 60 * 400:
        sim.step()
    return out, round(sim.n * SIM_DT, 2)


def _phi(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def p_tap(a, b, s):
    if a <= -WINDOW and b >= WINDOW:
        return 1.0
    lo = -1e9 if a <= -WINDOW else (a - 0.5) / s
    hi = 1e9 if b >= WINDOW else (b + 0.5) / s
    return max(1e-6, _phi(hi) - _phi(lo))


def predict(w, total, sigma=SIGMA):
    """{P, tries, minutes, fail_t} for one level's windows."""
    def run(s):
        surv, p_all, fail_t = 1.0, 1.0, 0.0
        for (a, b, t) in w:
            p = p_tap(a, b, s)
            fail_t += surv * (1.0 - p) * t
            surv *= p
        return surv, fail_t
    P, fail_t = run(sigma)
    P0, _ = run(sigma * LEARN)                         # a first try, not knowing the level
    mean_fail = fail_t / max(1e-9, 1.0 - P)
    tries = 1.0 + (1.0 - P0) / max(P, 1e-9)            # the first try at P0, the rest at P
    minutes = ((tries - 1.0) * (mean_fail + RESTART) + total) / 60.0
    return {"P": P, "tries": tries, "minutes": minutes, "fail_t": mean_fail, "taps": len(w), "time": total}


def target_tries(i):
    """Expected tries the developer wants at level i: slow rise (1.2 at 1, ~4 at 50, ~7 at 100, ~11 at 200) with a
    sawtooth - a sector (20 levels) opens with a breather and builds to a boss, and every 5 levels breathe once."""
    base = 1.15 + 0.06 * (i - 1) ** 0.95
    k = (i - 1) % 20                                   # place in the sector
    sector = 0.8 + 0.4 * k / 19.0                      # 0.8 at the first level of a sector -> 1.2 at its boss
    micro = (0.92, 1.0, 1.06, 1.12, 0.9)[(i - 1) % 5]  # the 5-level wave
    if k == 19:
        micro = 1.25                                   # boss
    return base * sector * micro


def target_minutes(i):
    """Most time a level may take to clear on average (minutes): failures must stay cheap."""
    return 2.0 + 4.0 * min(1.0, (i - 1) / 99.0) + 2.0 * max(0.0, min(1.0, (i - 100) / 100.0))


def _work(i):
    d = json.load(open(os.path.join(ROOT, "levels", f"level{i}.json"), encoding="utf-8"))
    w, total = windows(d)
    return i, LevelData(d).digest, w, total


def measure_all(ids):
    cache = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}
    todo = [i for i in ids if cache.get(str(i), {}).get("digest") != LevelData.load(i).digest
            or cache.get(str(i), {}).get("v") != VERSION]
    if todo:
        with mp.Pool(min(14, len(todo))) as pool:
            for i, dg, w, total in pool.imap_unordered(_work, todo):
                cache[str(i)] = {"digest": dg, "w": w, "time": total, "v": VERSION}
                print(f"measured L{i}", flush=True)
        json.dump(cache, open(OUT, "w", encoding="utf-8"))
    return {i: cache[str(i)] for i in ids}


def main():
    ids = [int(x) for x in sys.argv[1].split(",")] if len(sys.argv) > 1 else list(range(1, 101))
    res = measure_all(ids)
    for i in ids:
        r = predict(res[i]["w"], res[i]["time"])
        t = target_tries(i)
        print(f"L{i:3d} P={r['P']:.3f} tries={r['tries']:5.1f} (target {t:4.1f}, x{r['tries'] / t:4.2f})  "
              f"minutes={r['minutes']:4.1f} (max {target_minutes(i):3.1f})  taps={r['taps']} t={r['time']}s")


if __name__ == "__main__":
    mp.freeze_support()
    main()
