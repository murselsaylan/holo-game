"""Re-validate generated levels against the current simulation (run after any physics change).

    python levelgen/remeasure.py           # all levels present in levels/
    python levelgen/remeasure.py 5 10 20   # only these

For every level: (1) solvable at 80% of the recorded safety margin, (2) a fresh solve does not use far fewer
swaps than the route length implies (that would mean a shortcut / exploit).  Prints the levels to regenerate.
"""
import os
import sys
import json
import time
import multiprocessing as mp

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from sim import LevelData, LEVELS_DIR, replay  # noqa: E402
from levelgen import solver as S  # noqa: E402


def work(i):
    lvl = LevelData.load(i)
    if lvl is None:
        return i, {"missing": True}
    d = lvl.raw.get("difficulty", {})
    m = float(d.get("margin", 0.0))
    ref_ok = replay(lvl, lvl.raw.get("ref_taps", []))[1] is not None
    need = max(4.0, min(50.0, 0.8 * m))
    r_margin = S.solve(lvl, margin=need, beam=64, max_layers=320)
    r0 = S.solve(lvl, margin=0.0, beam=64, max_layers=320)
    route_swaps = lvl.path_total / 100.0
    exploit = bool(r0.solved and r0.swaps < 0.45 * route_swaps)
    return i, {"ref_ok": ref_ok, "margin_needed": need, "margin_ok": r_margin.solved, "swaps0": r0.swaps if r0.solved else None,
               "route_swaps": round(route_swaps, 1), "exploit": exploit}


if __name__ == "__main__":
    mp.freeze_support()
    ids = [int(a) for a in sys.argv[1:]] or [i for i in range(1, 101) if os.path.exists(os.path.join(LEVELS_DIR, f"level{i}.json"))]
    t0 = time.time()
    out = {}
    with mp.Pool(14) as pool:
        for i, r in pool.imap_unordered(work, ids):
            out[i] = r
            flag = "" if (r.get("ref_ok") and r.get("margin_ok") and not r.get("exploit")) else "  <-- REGENERATE"
            print(f"L{i:3d} {r}{flag}", flush=True)
    bad = sorted(i for i, r in out.items() if r.get("missing") or not (r.get("ref_ok") and r.get("margin_ok")) or r.get("exploit"))
    json.dump({str(k): v for k, v in out.items()}, open(os.path.join(LEVELS_DIR, "_remeasure.json"), "w"), indent=1)
    print("REGENERATE:", ",".join(str(b) for b in bad))
    print("done in", round(time.time() - t0), "s")
