"""Headless checks of the checkpoint flow in the real game:  python tools/checkpoint_test.py [level]
Plays the reference taps to just after the first flag lights, lets the pair die, presses "retry" and checks that the
run goes on from the flag (not from the start); writes screenshots (flag lit / resumed) to screenshots/."""
import os
import sys
import tempfile

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("HOLO_SERVER", "http://127.0.0.1:1")
os.environ.setdefault("HOLO_SAVE_DIR", tempfile.mkdtemp(prefix="holo_test_"))

import math  # noqa: E402
import pygame  # noqa: E402
import holo  # noqa: E402
from sim import SIM_DT  # noqa: E402

SHOTS = os.path.join(ROOT, "screenshots")
os.makedirs(SHOTS, exist_ok=True)


def shot(game, name):
    game.draw()
    pygame.image.save(game.frame, os.path.join(SHOTS, name))


def main(level_id):
    import random
    rng = random.Random(3)
    game = holo.HoloGame(headless=True)
    game.save_mgr.data["howto_seen"] = True
    game.online.url = "http://127.0.0.1:1"
    game.attempts = 1
    assert game.load_and_play_level(level_id)
    s = game.sim
    cps = game.level.data.checkpoints
    assert cps, "level has no checkpoints"
    taps = sorted(game.level.data.raw["ref_taps"])
    ti = frames = 0
    while game.state == "playing" and s.cp_next == 0 and frames < 60 * 400:
        while ti < len(taps) and taps[ti] <= s.n:
            game.swap_pivot()
            ti += 1
        game.update_gameplay(SIM_DT)
        game._update_camera(SIM_DT)
        frames += 1
    assert s.cp_next == 1, "the flag never lit"
    for _ in range(40):                                   # a few frames so the popup / glow show
        game.update_gameplay(SIM_DT)
        game._update_camera(SIM_DT)
    shot(game, f"checkpoint_lit_level{level_id}.png")
    lit_stars, lit_shields, lit_n = s.stars_collected, s.shields, s.n
    # now stop tapping: the pair crashes sooner or later
    while game.state == "playing" and frames < 60 * 400:
        if rng.random() < 0.04:
            game.swap_pivot()                             # wild tapping: it hits a wall soon
        game.update_gameplay(SIM_DT)
        game._update_camera(SIM_DT)
        frames += 1
    assert s.dead, f"the pair should have died: state={game.state} dead={s.dead} won={s.won} n={s.n} frames={frames} sim_same={game.sim is s}"
    for _ in range(240):                                  # dying animation -> failure screen
        game.update(SIM_DT, (0, 0))
        if game.state == "failed":
            break
    assert game.state == "failed", game.state
    assert game.failure_modal.cp_resume, "failure screen should offer the checkpoint"
    died_n, attempts = s.n, game.attempts
    game.retry_after_fail()
    assert game.state == "playing" and not s.dead
    assert game.assists == [[died_n, "C"]], game.assists
    assert game.sim is s and s.n == died_n, "the run must go on (time not rewound)"
    assert game.attempts == attempts + 1
    cp = cps[0]
    near = min(math.hypot(o.x - cp[0], o.y - cp[1]) for o in s.orbs)
    assert near < 140, f"pair should be back at the flag, is {near:.0f}px away"
    assert s.stars_collected <= lit_stars + 0 or s.stars_collected == lit_stars, "stars after the flag must be reset"
    assert s.shields == lit_shields and s.guard
    for _ in range(20):
        game.update_gameplay(SIM_DT)
        game._update_camera(SIM_DT)
    shot(game, f"checkpoint_resumed_level{level_id}.png")
    for _ in range(80):                                   # CHECKPOINT_SHIELD_S (1.2 s) later the shield has run out
        game.update_gameplay(SIM_DT)
        game._update_camera(SIM_DT)
        if s.dead:
            break
    assert s.dead or not s.guard, "the resume shield should be over after about 1.2 s"
    # a restart (pause menu) starts over and forgets the flags
    game.restart_level()
    assert game.sim.cp_next == 0 and game.assists == []
    print(f"level {level_id}: flag lit at step {lit_n}, died at {died_n}, resumed {near:.0f}px from the flag - ALL OK")


def streak_rules(level_id):
    """Sim level: 1st and 2nd resume from a flag are shielded + slow, the 3rd in a row is plain, a new flag resets it."""
    from sim import Sim, LevelData, CHECKPOINT_SHIELD_S, CHECKPOINT_SLOW_S, CHECKPOINT_FREE_RESUMES
    lvl = LevelData.load(level_id)
    s = Sim(lvl)
    taps = sorted(lvl.raw["ref_taps"])
    ti = 0
    while s.cp_next == 0:
        while ti < len(taps) and taps[ti] <= s.n:
            s.swap()
            ti += 1
        s.step()
    seen = []
    for k in range(4):
        s.dead = True
        assert s.resume_checkpoint()
        seen.append((s.guard, s.guard_t, s.spin_ramp_s if s.spin_ramp < 1 else None))
    assert seen[0] == (True, CHECKPOINT_SHIELD_S, CHECKPOINT_SLOW_S) and seen[1] == seen[0], seen
    assert seen[2] == (False, 0.0, None) and seen[3] == seen[2] and CHECKPOINT_FREE_RESUMES == 2, seen
    assert s.cp_streak == 4 and s.cp_used == 4
    for _ in range(int(CHECKPOINT_SHIELD_S * 60) + 3):    # the shield of a fresh resume ends by itself
        pass
    s.dead = False
    print(f"level {level_id}: streak rules OK {seen}")


if __name__ == "__main__":
    streak_rules(63)
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 63)
