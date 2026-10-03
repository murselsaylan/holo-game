"""Which campaign maps may appear in the endless climb, per tier?  Writes levels/endless_pool.json.

    python tools/endless_pool.py            # every level x tier (multiprocess, ~10-20 min)

A map enters a tier's pool only if the offline bot beats it as an endless stage (hazards filtered to that tier,
climbing orientation, tunnels cut) at the tier's TOP speed while playing like a slower human: taps >= 200 ms apart
on a 100 ms grid, with a 6 px safety margin around the orbs (level_qa's "coarse" standard). The first tiers only
take maps that are still beaten with a 12 px margin, so the climb starts gently.
"""
import json
import multiprocessing as mp
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import endless as E  # noqa: E402
from sim import LevelData, MAX_LEVELS  # noqa: E402
from levelgen import solver as S  # noqa: E402

EASY_TIERS = (0, 1, 2)
EASY_MARGIN = 12.0
MARGIN = 6.0


def check(job):
    lid, tier = job
    out = {"level": lid, "tier": tier, "speed": round(E.tier_max_speed(tier), 3)}
    t0 = time.time()
    need = EASY_MARGIN if tier in EASY_TIERS else MARGIN
    variants = [False, True] if tier == 0 else [False]           # stage 0 has no entry tunnel
    ok = True
    for first in variants:
        d = E.build_stage(lid, tier, first=first)
        d["speed"] = E.tier_max_speed(tier)
        r = S.solve(LevelData(d), margin=need, beam=64, stride=6, min_delay=12, max_layers=320,
                    deadline=time.time() + 150)
        ok = ok and r.solved
        if not ok:
            break
    out["ok"] = ok
    out["secs"] = round(time.time() - t0, 1)
    return out


def apply_content_rule(out):
    """Drop stages that are (nearly) empty at their tier (E.has_content) - a subset of the passable ones."""
    empty = {}
    for t, ids in out["tiers"].items():
        keep = [lid for lid in ids if E.has_content(lid, int(t))]
        empty[t] = sorted(set(ids) - set(keep))
        out["tiers"][t] = keep
    out["empty"] = empty
    # the collectable stars of every pooled stage at its tier (stage coordinates)
    out["stars"] = {t: {str(lid): E.make_stars(lid, int(t)) for lid in ids} for t, ids in out["tiers"].items()}
    out["rule"] = out["rule"].split(";")[0] + f"; walls cover >= {E.MIN_FILL:g} or >= {E.MIN_HAZARDS:g} hazards per 1000 px"
    return out


def main():
    if sys.argv[1:] == ["--content-only"]:          # re-apply the content rule to the verified pool (no bot runs)
        with open(E.POOL_FILE, "r", encoding="utf-8") as f:
            out = json.load(f)
        apply_content_rule(out)
        with open(E.POOL_FILE, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=1)
        print({t: len(v) for t, v in out["tiers"].items()}, "written", E.POOL_FILE)
        return
    jobs = [(lid, t) for t in range(E.MAX_TIER + 1) for lid in range(1, MAX_LEVELS + 1)]
    t0 = time.time()
    res = []
    with mp.Pool(max(1, (os.cpu_count() or 2) - 1)) as p:
        for i, r in enumerate(p.imap_unordered(check, jobs, chunksize=1)):
            res.append(r)
            if (i + 1) % 50 == 0:
                print(f"{i + 1}/{len(jobs)}  {time.time() - t0:.0f}s", flush=True)
    tiers = {t: sorted(r["level"] for r in res if r["tier"] == t and r["ok"]) for t in range(E.MAX_TIER + 1)}
    out = {"version": E.ENDLESS_VERSION, "rule": f"bot beats the stage at the tier's top speed, taps >= 200 ms apart, "
                                                  f"margin {MARGIN:g} px ({EASY_MARGIN:g} px for tiers {list(EASY_TIERS)})",
           "tiers": {str(t): ids for t, ids in tiers.items()},
           "rejected": {str(t): sorted(r["level"] for r in res if r["tier"] == t and not r["ok"]) for t in tiers}}
    apply_content_rule(out)
    with open(E.POOL_FILE, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    for t, ids in tiers.items():
        print(f"tier {t} (speed {E.tier_max_speed(t):.2f}): {len(ids)} maps")
    print("written", E.POOL_FILE, f"in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
