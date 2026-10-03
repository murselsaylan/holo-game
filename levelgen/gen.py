"""Level generator + auto tuner.

    python levelgen/gen.py 1 100          # generate + verify levels 1..100 (multiprocess)
    python levelgen/gen.py 37 --show      # single level, print report

For each level: build layout -> solve on the real simulation -> loosen the difficulty knob until the
level is solvable with the required safety margin -> derive stars/shields from the winning trajectory ->
verify by replay -> write levels/levelN.json (+ report in levels/_report.json).
"""
import os
import sys
import json
import math
import time
import random
import multiprocessing as mp

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from sim import LevelData, replay, ARENA_W, ARENA_H, LEVELS_DIR  # noqa: E402
from levelgen import plan as P  # noqa: E402
from levelgen import families as F  # noqa: E402
from levelgen import hazards as H  # noqa: E402
from levelgen import solver as S  # noqa: E402


CARVE = ('custom', 'snake_h', 'snake_v', 'zigzag', 'spiral', 'maze', 'wander')


def build(i, tight, seed=0, count_delta=0, gk=0, roamers=0):
    pl = P.plan(i)
    pl['count'] = max(0, pl['count'] + count_delta)
    pl['bumpers'] = max(0, pl['bumpers'] + count_delta)
    rng = random.Random(i * 7919 + seed * 104729 + pl.get("variant", 0) * 31337)
    ctx = F.Ctx(i, tight, rng, height=P.height_of(i))
    ctx.speed = P.speed_of(i)
    ctx.gk = gk
    ctx.style = pl.get("style", ctx.style)
    fam = F.FAMILIES[pl["family"]]
    fkw = dict(pl["fkw"])
    if count_delta < 0 and pl["family"] in ("arena", "mines") and "rows" in fkw:
        fkw["rows"] = max(2, fkw["rows"] + count_delta // 2)      # fallback: fewer rows when the level cannot be solved
    L, start, end = fam(ctx, **fkw)
    pl["placed"] = list(getattr(L, "placed_gates", []))
    pl["sig"] = getattr(L, "sig", None)
    if pl["gates"] and pl["gcount"]:
        pl["placed"] += H.apply_gates(L, ctx, pl["gates"], pl["gcount"])
    if pl["bumpers"] and pl["family"] in CARVE:
        H.add_bumpers(L, ctx, pl["bumpers"], rng)
    if pl["kit"] and pl["count"]:
        H.apply(L, ctx, pl["kit"], pl["count"], rng)
    if roamers and count_delta >= 0:          # not on the emergency low-hazard fallback: keep that path minimal
        H.add_roamers(L, ctx, roamers, rng)
    d = L.to_level(i, pl["title"], start, end, P.speed_of(i), P.ramp_of(i))
    d["sector"] = pl["sector"]
    return d, pl, ctx


def pick(pts, prog, window, min_clear=18.0, prefer_low=True, avoid=()):
    for w_mul, mc, dist in ((1, min_clear, 140), (2, min(min_clear, 12.0), 110), (3, 6.0, 80), (5, 2.0, 60)):
        cands = [p for p in pts if abs(p["prog"] - prog) <= window * w_mul and p["clear"] >= mc
                 and all(math.hypot(p["x"] - a[0], p["y"] - a[1]) > dist for a in avoid)]
        if cands:
            cands.sort(key=lambda p: p["clear"])
            return cands[0] if prefer_low else cands[-1]
    return None


GATE_KEYS = {"gshrink": "shrink_zones", "ggrow": "growth_zones", "gshield": "shields", "gboost": "boost_pads"}


def optional_gate(d, pl, beam):
    """Name of a placed gate whose pickup is NOT needed (level still solvable without it), else None."""
    for kind in dict.fromkeys(pl.get("placed", [])):
        d2 = dict(d)
        d2[GATE_KEYS[kind]] = []
        if kind == "gshield":
            d2["shields"] = []
        # a gate must hold even against a very fast tapper (12 taps/s): the small-angle 'wiggle' can slip through a loose throat
        fast = dict(min_delay=5, stride=2) if kind == "gshrink" else {}
        if S.solve(LevelData(d2), margin=0.0, beam=max(64, beam), max_layers=320, **fast).solved:
            return kind
    return None


def make(i, seed=0, beam=48, verbose=False, roamers=0):
    t0 = time.time()
    tight = max(0.0, P.difficulty(i) + float(os.environ.get("HOLO_TIGHT_OFFSET", 0.0)))
    pl0 = P.plan(i)
    kit_factor = 1.0
    if "spin" in pl0["kit"] or "twin" in pl0["kit"]:
        kit_factor = 0.6
    elif "shutter" in pl0["kit"]:
        kit_factor = 0.7
    elif "sweep" in pl0["kit"]:
        kit_factor = 0.75
    elif "laser" in pl0["kit"]:
        kit_factor = 0.85
    floor = max(5.0, 0.7 * P.margin_target(i) * kit_factor)
    if "gshrink" in pl0["gates"]:
        floor = min(floor, 11.0)                 # a pinched throat caps the safety margin by design
    if "gboost" in pl0["gates"]:
        floor = min(floor, 16.0)
    gk = 0
    best = None
    log = []
    base_tight = tight
    budget = 360.0                        # seconds of tuning per level before falling back to fewer hazards
    for count_delta in (0, -2, -99):
        # a layout can be geometrically unsolvable at its full hazard count no matter the tightness (a bad placement,
        # not too many hazards); try a couple of alternate seeds - different route/hazard positions, same plan - before
        # giving up and stripping hazards down to count_delta -2/-99, which is what used to leave levels feeling empty.
        n_seeds = 3 if (count_delta == 0 and (pl0["kit"] or pl0["gates"])) else 1
        for seed_off in range(n_seeds):
            tight = base_tight
            for attempt in range(5 if n_seeds > 1 else (8 if pl0["gates"] else 5)):
                d, pl, ctx = build(i, tight, seed + seed_off, count_delta, gk, roamers)
                lvl = LevelData(d)
                m = S.max_margin(lvl, hi=max(64.0, floor * 1.5), iters=4, beam=beam, max_layers=320)
                log.append((round(tight, 3), round(m, 1), count_delta, seed_off))
                if verbose:
                    print(f"  L{i} d={count_delta} seed+{seed_off} attempt {attempt}: tight={tight:.3f} W={ctx.W:.0f} H={d['height']} margin*={m:.1f} (floor {floor:.1f})")
                if m >= floor:
                    bad = optional_gate(d, pl, beam) if pl.get("placed") else None
                    if bad and gk < 6:
                        gk += 1
                        log.append(("optional", bad, "gk", gk))
                        if verbose:
                            print(f"  L{i}: gate {bad} is optional -> stricter (gk={gk})")
                        continue
                    best = (d, pl, ctx, m, tight)
                    break
                tight = max(0.0, tight - (0.10 if m >= 0 else 0.18))
                if time.time() - t0 > budget and count_delta != -99:
                    break
                if tight <= 0.0 and attempt >= 2:
                    break
            if best is not None:
                break
        if best is not None:
            break
        if not pl0["kit"] and not pl0["bumpers"] and pl0["family"] not in ("arena", "mines"):
            break
    if best is None:
        return None, {"level": i, "error": "unsolvable", "log": log}
    # harden pass: the loop above only ever loosens a level that turned out too hard; a level that lands far above
    # its target margin (the common cause of "empty" / trivially easy levels) is never pushed back down. Try adding
    # more hazards and tightening further, keeping the hardest variant that is still solvable at the floor margin.
    d, pl, ctx, m, tight = best
    hi_val = max(64.0, floor * 1.5)
    # levels 1-3 are fixed hand-placed tutorial routes: never hardened. Levels with power-up gates are already tuned by
    # the gk (gate-strictness) mechanism above; adding independent extra hazards on top can open a different solving
    # path that quietly makes the gate's pickup optional again, so leave those alone too.
    if i > 3 and not pl0["gates"] and (m > floor * 1.8 or m >= hi_val - 0.5):
        ceiling = time.time() + 90.0
        for cd in (2, 4, 6):
            if time.time() > ceiling:
                break
            for tt in (min(1.0, tight + 0.12), min(1.0, tight + 0.28), min(1.0, tight + 0.45)):
                d2, pl2, ctx2 = build(i, tt, seed, cd, gk, roamers)
                lvl2 = LevelData(d2)
                m2 = S.max_margin(lvl2, hi=max(64.0, floor * 1.5), iters=4, beam=beam, max_layers=320)
                log.append(("harden", cd, round(tt, 3), round(m2, 1)))
                if floor <= m2 < m:
                    bad2 = optional_gate(d2, pl2, beam) if pl2.get("placed") else None
                    if bad2:
                        continue
                    d, pl, ctx, m, tight = d2, pl2, ctx2, m2, tt
                if time.time() > ceiling:
                    break
    lvl = LevelData(d)

    # robust reference solution: not just "wins", but wins even if every tap is off by up to 2 frames (33ms), so the
    # level does not silently demand frame-perfect input to be beatable at all (margin alone does not guarantee this -
    # a spatially safe path can still sit right on a laser/spinner's on/off edge in time).
    def jitter_rate(lvl_, taps_, trials=8, spread=2):
        rng_ = random.Random(20260919)
        win = 0
        for _ in range(trials):
            t2 = sorted(max(0, tp + rng_.randint(-spread, spread)) for tp in taps_)
            _, res2 = replay(lvl_, t2, max_seconds=max(90.0, lvl_.par_time * 6))
            win += 1 if res2 is not None else 0
        return win / float(trials)

    use_margin = min(m, max(floor, 6.0)) * 0.9
    if "gshield" in pl.get("placed", []):
        use_margin = 0.0                        # pop timing shifts with the margin; the real game is played at 0
    sol = S.solve(lvl, margin=use_margin, beam=beam * 2, max_layers=320)
    if not sol.solved:
        sol = S.solve(lvl, margin=0.0, beam=beam * 3, max_layers=320)
    if not sol.solved:
        return None, {"level": i, "error": "no reference solution", "log": log}
    # a spatially safe path can still sit on a razor's edge in TIME (a tap a couple of frames early/late loses): try a
    # few alternative solves and keep whichever survives +-2 frame (33ms) tap jitter most often, not just "any win".
    if "gshield" not in pl.get("placed", []):
        best_rate = jitter_rate(lvl, sol.taps)
        if best_rate < 0.75:
            for um, bm in ((min(m, floor * 1.4), beam * 2), (min(m, floor * 1.8), beam * 3), (m * 0.95, beam * 3)):
                sol2 = S.solve(lvl, margin=um, beam=bm, max_layers=320)
                if sol2.solved:
                    r2 = jitter_rate(lvl, sol2.taps)
                    if r2 > best_rate:
                        sol, best_rate = sol2, r2
                if best_rate >= 0.75:
                    break
            log.append(("jitter_rate", round(best_rate, 2)))
    pts, _ = S.trajectory(lvl, sol.taps, margin=0.0)

    # stars along the winning line at the riskiest safe spots
    stars = []
    for prog in (0.24, 0.52, 0.80):
        p = pick(pts, prog, 0.07, avoid=stars)
        if p is None:
            return None, {"level": i, "error": "star placement", "log": log}
        stars.append((round(p["x"]), round(p["y"])))
    d["stars"] = [list(s) for s in stars]

    # shields on the line, earlier than the harder half of the level
    gate_shields = [tuple(s) for s in d["shields"]]
    shields = []
    for prog in ([0.30] if pl["shields"] == 1 else ([0.28, 0.62] if pl["shields"] > 1 else [])):
        p = pick(pts, prog, 0.06, min_clear=24.0, prefer_low=False, avoid=stars + shields + gate_shields)
        if p:
            shields.append((round(p["x"]), round(p["y"])))
    d["shields"] = [list(s) for s in gate_shields] + [list(s) for s in shields]

    d["par_time"] = round(sol.time_s * 1.15, 1)
    d["par_swaps"] = int(sol.swaps * 1.15) + 1
    d["ref_taps"] = list(sol.taps)
    d["difficulty"] = {"tight": round(tight, 3), "margin": round(m, 1), "corridor": round(ctx.W),
                       "speed": d["speed"], "swaps": sol.swaps, "ref_time": round(sol.time_s, 1)}

    # final replay proof on the real simulation with stars in place
    lvl2 = LevelData(d)
    sim, res = replay(lvl2, sol.taps)
    if res is None or res["stars"] < 3:
        return None, {"level": i, "error": f"replay failed stars={res and res['stars']}", "log": log}
    rep = {"level": i, "title": d["title"], "family": pl["family"], "tight": round(tight, 3), "margin": round(m, 1),
           "gates": pl.get("placed", []), "gk": gk, "W": round(ctx.W), "swaps": sol.swaps, "time": round(sol.time_s, 1), "speed": d["speed"],
           "haz": {k: len(d[k]) for k in ("moving_walls", "lasers", "spinners", "circles", "reverse_walls",
                                            "growth_zones", "shrink_zones", "boost_pads", "shields", "breakables", "chasers", "barriers")},
           "log": log, "secs": round(time.time() - t0, 1)}
    return d, rep


def _work(args):
    i, seed = args
    try:
        d, rep = make(i, seed)
    except Exception as e:  # pragma: no cover
        import traceback
        return i, None, {"level": i, "error": repr(e), "tb": traceback.format_exc()}
    return i, d, rep


def save(d, out_dir=None):
    out_dir = out_dir or LEVELS_DIR
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, f"level{d['id']}.json"), "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, separators=(",", ":"))


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    lo = int(args[0]) if args else 1
    hi = int(args[1]) if len(args) > 1 else lo
    jobs = [(i, 0) for i in range(lo, hi + 1)]
    for a in sys.argv[1:]:
        if a.startswith("--only="):
            jobs = [(int(x), 0) for x in a[7:].split(",") if x]
    reports = {}
    if "--show" in sys.argv:
        for i, _ in jobs:
            d, rep = make(i, 0, verbose=True)
            print(json.dumps(rep, indent=1, ensure_ascii=False))
            if d and "--nosave" not in sys.argv:
                save(d)
        return
    t0 = time.time()
    with mp.Pool(min(14, len(jobs))) as pool:
        for i, d, rep in pool.imap_unordered(_work, jobs):
            reports[i] = rep
            if d:
                save(d)
                print(f"L{i:3d} {rep['title'][:22]:22s} {rep['family']:9s} W={rep['W']:3d} m*={rep['margin']:5.1f} "
                      f"swaps={rep['swaps']:3d} t={rep['time']:5.1f}s haz={sum(rep['haz'].values())} ({rep['secs']}s)", flush=True)
            else:
                print(f"L{i:3d} FAILED {rep}", flush=True)
    rp = os.path.join(LEVELS_DIR, "_report.json")
    old = {}
    if os.path.exists(rp):
        try:
            old = json.load(open(rp, encoding="utf-8"))
        except Exception:
            old = {}
    old.update({str(k): v for k, v in reports.items()})
    json.dump(old, open(rp, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print("done in", round(time.time() - t0), "s")


if __name__ == "__main__":
    mp.freeze_support()
    main()
