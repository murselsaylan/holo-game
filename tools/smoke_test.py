"""Headless end-to-end checks of the real game classes.   python tools/smoke_test.py [level ...]"""
import os
import sys
import json
import time

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("HOLO_SERVER", "http://127.0.0.1:1")   # never talk to a real server
import tempfile
os.environ.setdefault("HOLO_SAVE_DIR", tempfile.mkdtemp(prefix="holo_test_"))   # never touch the real save

import pygame  # noqa: E402
import holo  # noqa: E402
from sim import SIM_DT, LevelData, replay  # noqa: E402

SHOTS = os.path.join(ROOT, "screenshots")
os.makedirs(SHOTS, exist_ok=True)


def play_reference(game, level_id):
    """Drive the real game loop with the level's reference taps."""
    game.attempts = 1
    assert game.load_and_play_level(level_id)
    d = game.level.data.raw
    taps = sorted(d["ref_taps"])
    ti = 0
    frames = 0
    shot_done = False
    while game.state == "playing" and frames < 60 * 400:
        while ti < len(taps) and taps[ti] <= game.sim.n:
            game.swap_pivot()
            ti += 1
        game.update_gameplay(SIM_DT)
        game._update_camera(SIM_DT)
        frames += 1
        if not shot_done and game.sim.progress > 0.5 and level_id in SHOT_LEVELS:
            game.draw()
            pygame.image.save(game.frame, os.path.join(SHOTS, f"play_level{level_id}.png"))
            shot_done = True
    return game.state, frames


SHOT_LEVELS = set()

if __name__ == "__main__":
    ids = [int(a) for a in sys.argv[1:]] or [1, 5, 25, 63, 99]
    SHOT_LEVELS = set(ids)
    game = holo.HoloGame(headless=True)
    game.save_mgr.data["howto_seen"] = True  # onboarding is covered by ui_test.py
    game.online.url = "http://127.0.0.1:1"
    ok = True
    for lid in ids:
        t0 = time.time()
        state, frames = play_reference(game, lid)
        res = game.victory_modal.r if game.victory_modal else None
        print(f"level {lid}: state={state} frames={frames} stars={res and res['stars']} score={res and res['level_total']} "
              f"rank={res and res['rank']} taps={len(game.taps)} ({time.time()-t0:.1f}s)")
        ok &= (state == "victory")
        flags = len(game.level.data.checkpoints)          # checkpoints (1.0.9): the reference run lights them all, in order
        if flags:
            print(f"  checkpoints: {game.sim.cp_next}/{flags} lit")
            ok &= (game.sim.cp_next == flags and not any(a[1] == "C" for a in game.assists))
    print("ALL OK" if ok else "FAILURES")
    sys.exit(0 if ok else 1)
