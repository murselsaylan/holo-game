"""Frame cost around gameplay events (the moments players reported as laggy).

    python tools/event_perf.py              # levels with growth / shrink / cracked walls / barriers / boosts
    python tools/event_perf.py 22 44        # some levels

The real game loop (update + draw of the whole frame) plays each level's reference solution; every frame is timed.
Frames up to 0.5 s after an event (grow, shrink, smash, barrier phase, shield pop, boost, revive) are compared with
the level's ordinary frames. A revive is forced once per level. Also times the menu screens. PC numbers - a phone is
several times slower, so what matters is how much an event frame costs relative to a normal one.
"""
import os
import sys
import tempfile
import time

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["HOLO_SAVE_DIR"] = tempfile.mkdtemp(prefix="holo_evperf_")
os.environ["HOLO_SERVER"] = "http://127.0.0.1:1"

import pygame  # noqa: E402
import holo  # noqa: E402
from sim import SIM_DT  # noqa: E402

EVENTS = ("grow", "shrink", "smash", "shield_pop", "boost", "fx_end", "chase")


def frame(g):
    t0 = time.perf_counter()
    g.update(SIM_DT, (450, 900))
    g.draw()
    return (time.perf_counter() - t0) * 1000.0


_SEEN = []


def _hook(g):
    orig = g._handle_sim_events

    def wrapped():
        _SEEN.extend(e[0] for e in g.sim.events)
        orig()
    g._handle_sim_events = wrapped


def play(g, lid, force_revive=True):
    g.load_and_play_level(lid)
    if g.state == "howto":
        g._close_howto()
    taps = sorted(g.level.data.raw.get("ref_taps", []))
    ti = 0
    normal, after = [], {}
    recent = {}                                   # event -> frames left in its window
    revived = False
    for _ in range(60 * 90):
        s = g.sim
        if g.state == "playing":
            while ti < len(taps) and taps[ti] <= s.n:
                g.swap_pivot()
                ti += 1
            if force_revive and not revived and s.n > 240 and not s.dead:
                s.dead = True                     # force a death + paid revive once (diamonds are local in tests)
                g.state = "failed"
                g.save_mgr.data["diamonds"] = 999
                g._revive_now(s)
                revived = True
                recent["revive"] = 90
        _SEEN.clear()
        ms = frame(g)
        for e in _SEEN:
            if e in EVENTS:
                recent[e] = 30
        if recent:
            for e in list(recent):
                after.setdefault(e, []).append(ms)
                recent[e] -= 1
                if recent[e] <= 0:
                    del recent[e]
        else:
            normal.append(ms)
        if g.state not in ("playing", "dying", "paused"):
            break
    return normal, after


def stat(v):
    v = sorted(v)
    return f"avg {sum(v) / len(v):5.2f}  p95 {v[int(len(v) * 0.95)]:5.2f}  max {v[-1]:5.2f} ms  (n={len(v)})" if v else "-"


def main():
    levels = [int(a) for a in sys.argv[1:]] or [7, 22, 29, 33, 44, 46, 51, 58, 73]
    g = holo.HoloGame(headless=True)
    _hook(g)
    g.settings["particles"] = True
    all_normal, all_after = [], {}
    for lid in levels:
        normal, after = play(g, lid)
        all_normal += normal
        for k, v in after.items():
            all_after.setdefault(k, []).extend(v)
        print(f"level {lid:3d}: normal {stat(normal)}")
    print("\nALL normal frames      :", stat(all_normal))
    for k, v in sorted(all_after.items()):
        print(f"after {k:12s}      :", stat(v))
    # menus
    for st in ("menu", "shop", "skins", "leaderboard", "levels", "achievements", "daily"):
        getattr(g, {"menu": "open_menu", "shop": "open_shop", "skins": "open_skins", "leaderboard": "open_leaderboard",
                    "levels": "open_level_select", "achievements": "open_achievements", "daily": "open_daily"}[st])()
        v = [frame(g) for _ in range(90)]
        print(f"menu screen {st:12s} :", stat(v))


if __name__ == "__main__":
    main()
