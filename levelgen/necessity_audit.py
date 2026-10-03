"""Audit: for every level with power-up gates, is the level unsolvable WITHOUT the matching pickup (also against a fast tapper)?

    python levelgen/necessity_audit.py            # all levels
    python levelgen/necessity_audit.py 41 42 45   # some levels
"""
import os, sys, json, multiprocessing as mp
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from sim import LevelData  # noqa: E402
from levelgen import solver as S  # noqa: E402


def audit(i):
    lvl = LevelData.load(i)
    raw = lvl.raw
    out = {}
    for kind, key in (("shrink", "shrink_zones"), ("grow", "growth_zones"), ("shield", "shields"), ("boost", "boost_pads")):
        has = {"shrink": bool(raw.get("shrink_zones")), "grow": bool(raw.get("growth_zones")),
               "shield": bool(raw.get("barriers")), "boost": bool(raw.get("chasers"))}[kind]
        if not has:
            continue
        d2 = dict(raw)
        d2[key] = []
        if kind == "shield":
            # spare shields are removed too: the barrier must not be passable at all
            d2["shields"] = []
        fast = dict(min_delay=5, stride=2) if kind == "shrink" else {}
        out[kind] = S.solve(LevelData(d2), margin=0.0, beam=64, max_layers=320, **fast).solved     # True = gate is OPTIONAL (bad)
    return i, out


if __name__ == "__main__":
    mp.freeze_support()
    ids = [int(a) for a in sys.argv[1:]] or list(range(1, 101))
    bad = {}
    with mp.Pool(min(14, len(ids))) as pool:
        for i, res in pool.imap_unordered(audit, ids):
            if res:
                flag = [k for k, v in res.items() if v]
                print(f"L{i:3d}", res, "  <-- OPTIONAL: " + ",".join(flag) if flag else "  ok", flush=True)
                if flag:
                    bad[i] = flag
    print("optional gates:", json.dumps(bad))
