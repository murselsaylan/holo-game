"""Re-time the campaign to the speed curve in plan.speed_of without changing any layout (2026-10, 1.0.8).

    python levelgen/respeed.py             # all 100 levels
    python levelgen/respeed.py 61,62,90    # only these

Per level: every spinner made as short as the ones in narrow corridors (hazards.small_spinners), the new speed, a new
reference solution on the real simulation (robust to +-2 frame tap jitter where possible), stars re-placed along the
new winning line (the old ones may sit off it at another speed), par time / swaps and the difficulty fields refreshed,
then a final replay that must win with all three stars. A level whose file changes and that players already have
keeps its previous version in levelgen/legacy_levels (the server replays not-updated games on it).
"""
import json
import multiprocessing as mp
import os
import random
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from sim import LevelData, replay  # noqa: E402
from levelgen import plan as P  # noqa: E402
from levelgen import hazards as H  # noqa: E402
from levelgen import solver as S  # noqa: E402
from levelgen.gen import pick, save  # noqa: E402

LEVELS = os.path.join(ROOT, "levels")
BEAM = int(os.environ.get("RESPEED_BEAM", "48"))      # a wider search for levels the default one gives up on
KW = {"max_delay": int(os.environ.get("RESPEED_MAXDELAY", "175")),      # longer waits between taps (slow levels)
      "max_layers": int(os.environ.get("RESPEED_LAYERS", "320"))}
LEGACY = os.path.join(ROOT, "levelgen", "legacy_levels")
SHIPPED = "a412c5b"           # the commit whose levels/ every released game (1.0.6, 1.0.7) carries


def jitter_rate(lvl, taps, trials=8, spread=2):
    rng = random.Random(20260919)
    win = 0
    for _ in range(trials):
        t2 = sorted(max(0, tp + rng.randint(-spread, spread)) for tp in taps)
        _, res = replay(lvl, t2, max_seconds=max(90.0, lvl.par_time * 6))
        win += 1 if res is not None else 0
    return win / float(trials)


def dilate(d, k):
    """The whole level slowed down by k (< 1): moving walls, lasers, spinners and chasers run at the pair's new pace,
    so the same layout plays exactly as before, only slower (for levels whose hazards no longer line up otherwise)."""
    if d.get("moving_walls"):
        d["moving_walls"] = [list(m) if len(m) > 10 else      # rectangle loops are paced by tidy_roamers
                             list(m[:6]) + [round(m[6] * k, 4), m[7]] + ([round(m[8] * k, 4), m[9]] if len(m) > 8 else [])
                             for m in d["moving_walls"]]
    out = []
    for l in d.get("lasers", []):
        l = list(l) + [3.0, 0.4, 0.0][len(l) - 4:]
        out.append(l[:4] + [round(l[4] / k, 3), l[5], round(l[6] / k, 3)])
    if d.get("lasers"):
        d["lasers"] = out
    d["spinners"] = [list(s[:3]) + [round(s[3] * k, 4)] + list(s[4:]) for s in d.get("spinners", [])]
    if d.get("chasers"):
        d["chasers"] = [list(c[:4]) + [round(c[4] * k, 2), round(c[5] * k, 2)] + list(c[6:]) for c in d.get("chasers", [])]
    return d


def respeed(i):
    d = json.load(open(os.path.join(LEVELS, f"level{i}.json"), encoding="utf-8"))
    H.small_spinners(d)
    if os.environ.get("RESPEED_DILATE") == "1":
        dilate(d, P.speed_of(i) / d["speed"])
    d["speed"] = round(P.speed_of(i) * float(os.environ.get("RESPEED_SPEED_MUL", "1")), 3)
    H.tidy_roamers(d)                                     # rectangle loops, paced by the new speed
    lvl = LevelData(d)
    m = S.max_margin(lvl, hi=64.0, iters=4, beam=BEAM, **KW)
    if m < 0:
        return i, None, "unsolvable at the new speed"
    gate_shield = bool(d.get("barriers"))                  # the energy-barrier gate: pop timing shifts with a margin
    use = 0.0 if gate_shield else min(m, 20.0) * 0.9
    sol = S.solve(lvl, margin=use, beam=2 * BEAM, **KW)
    if not sol.solved:
        sol = S.solve(lvl, margin=0.0, beam=3 * BEAM, **KW)
    if not sol.solved:
        return i, None, "no reference solution"
    if not gate_shield:
        best = jitter_rate(lvl, sol.taps)
        if best < 0.75:
            for um, bm in ((min(m, 28.0), 96), (m * 0.95, 144)):
                s2 = S.solve(lvl, margin=um, beam=bm, **KW)
                if s2.solved:
                    r2 = jitter_rate(lvl, s2.taps)
                    if r2 > best:
                        sol, best = s2, r2
                if best >= 0.75:
                    break
    def place_stars(taps):
        pts, _ = S.trajectory(lvl, taps, margin=0.0)
        out = []
        for prog in (0.24, 0.52, 0.80):
            p = None
            for shift in (0.0, 0.05, -0.05, 0.1, -0.1):       # a spot near the target point if the point itself has none
                p = pick(pts, min(0.95, max(0.05, prog + shift)), 0.07, avoid=out)
                if p is not None:
                    break
            if p is None:
                return None
            out.append((round(p["x"]), round(p["y"])))
        return out

    # the chosen line, then the plain one: stars along it, and the level with those stars must still be won
    why = "star placement"
    s0 = None
    for cand in (sol, "plain"):
        if cand == "plain":
            s0 = S.solve(lvl, margin=0.0, beam=2 * BEAM, **KW)
            if not s0.solved:
                break
            cand = s0
        stars = place_stars(cand.taps)
        if stars is None:
            continue
        d2 = dict(d)
        d2["stars"] = [list(s) for s in stars]
        sim, res = replay(LevelData(d2), cand.taps)
        if res is None or sim.stars_collected < 3:
            why = f"final replay won={res is not None} stars={sim.stars_collected}"
            continue
        d = d2
        sol = cand
        break
    else:
        return i, None, why
    if s0 is not None and not s0.solved:
        return i, None, why
    d["par_time"] = round(sol.time_s * 1.15, 1)
    d["par_swaps"] = int(sol.swaps * 1.15) + 1
    d["ref_taps"] = list(sol.taps)
    df = d["difficulty"]
    df.update(margin=round(m, 1), speed=d["speed"], swaps=sol.swaps, ref_time=round(sol.time_s, 1))
    return i, d, f"speed {d['speed']} t={df['ref_time']}s swaps={sol.swaps} margin={df['margin']}"


def keep_shipped(i):
    """The version players have, before this level's file is replaced (once)."""
    leg = os.path.join(LEGACY, f"level{i}.json")
    if os.path.exists(leg):
        return
    old = subprocess.run(["git", "show", f"{SHIPPED}:levels/level{i}.json"], cwd=ROOT, capture_output=True)
    if old.returncode == 0:
        os.makedirs(LEGACY, exist_ok=True)
        open(leg, "wb").write(old.stdout)


def main():
    ids = [int(x) for x in sys.argv[1].split(",")] if len(sys.argv) > 1 else list(range(1, 101))
    failed = []
    with mp.Pool(min(14, len(ids))) as pool:
        for i, d, msg in pool.imap_unordered(respeed, ids):
            if d is None:
                failed.append(i)
                print(f"L{i}: FAILED - {msg}", flush=True)
                continue
            keep_shipped(i)
            save(d)
            print(f"L{i}: {msg}", flush=True)
    print("failed:", sorted(failed))


if __name__ == "__main__":
    mp.freeze_support()
    main()
