"""Headless checks of the first-run tutorial (Level 0) and the funnel queue on the real game classes.

    python tools/tutorial_test.py            # screenshots go to screenshots/tutorial_*.png
"""
import os
import sys
import json
import random
import tempfile

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("HOLO_SERVER", "http://127.0.0.1:1")      # never talk to a real server
os.environ["HOLO_SAVE_DIR"] = tempfile.mkdtemp(prefix="holo_tut_")  # a brand-new install

import pygame  # noqa: E402
import holo  # noqa: E402
import tutorial  # noqa: E402
from sim import SIM_DT, LevelData, Sim, replay  # noqa: E402

SHOTS = os.path.join(ROOT, "screenshots")
os.makedirs(SHOTS, exist_ok=True)
failed = 0


def check(name, ok, extra=""):
    global failed
    print(("PASS " if ok else "FAIL ") + name, extra)
    if not ok:
        failed += 1


def shot(game, name):
    game.draw()
    pygame.image.save(game.frame, os.path.join(SHOTS, f"tutorial_{name}.png"))


def run(game, taps, max_frames=60 * 120, shots=None):
    """Play the tutorial with these taps (sim steps) through the real game loop."""
    taps = sorted(taps)
    ti, frames, shots = 0, 0, dict(shots or {})
    while game.state == "playing" and game.tut is not None and frames < max_frames:
        while ti < len(taps) and taps[ti] <= game.sim.n:
            game.swap_pivot()
            ti += 1
        game.update_gameplay(SIM_DT)
        game._update_camera(SIM_DT)
        frames += 1
        for name, when in list(shots.items()):
            if when(game):
                shot(game, name)
                shots.pop(name)
    return frames


def crash_taps():
    """Taps that crash the pair into a wall in the tutorial (found on the plain simulation)."""
    lvl = LevelData(tutorial.LEVEL)
    rnd = random.Random(7)
    for _ in range(400):
        taps, n = [], 0
        for _ in range(6):
            n += rnd.randint(5, 40)
            taps.append(n)
        s = Sim(lvl)
        i = 0
        while not s.dead and not s.won and s.n < 900:
            while i < len(taps) and taps[i] <= s.n:
                s.swap()
                i += 1
            s.step()
        if s.dead:
            return taps
    return None


# ---- the level itself: the reference solution wins with 3 stars
lvl = LevelData(tutorial.LEVEL)
sim, res = replay(lvl, tutorial.LEVEL["ref_taps"])
check("reference solution clears Level 0 with 3 stars", sim.won and res["stars"] == 3, res and res["stars"])
check("Level 0 is wider and slower than level 1",
      (tutorial.LEVEL["walls"][2][0] - tutorial.LEVEL["walls"][1][2]) > 334 and tutorial.LEVEL["speed"] < 0.92)

# ---- a new install: profile first, then straight into the tutorial
game = holo.HoloGame(headless=True)
game.online.url = "http://127.0.0.1:1"
sm = game.save_mgr
if os.environ.get("HOLO_LANG"):                      # screenshots in another language: HOLO_LANG=tr
    sm.language = os.environ["HOLO_LANG"]
check("new install opens the profile first", game.state == "profile", game.state)
check("app_open + profile_shown queued", {"app_open", "profile_shown"} <= set(sm.data.get("funnel_q", {})), sm.data.get("funnel_q"))
sm.player_name = "TESTPILOT"
sm.is_profile_set = True
game.close_profile()
check("saving the profile starts the tutorial", game.tut is not None and game.state == "playing" and game.level_id == 0,
      (game.state, game.level_id))
check("profile_done + tut_start queued", {"profile_done", "tut_start"} <= set(sm.data["funnel_q"]))
shot(game, "1_tap")

# ---- a crash rewinds, no failure screen
taps = crash_taps()
check("found taps that crash on the plain simulation", taps is not None, taps)
before = game.tut.deaths
run(game, taps, max_frames=900, shots={"2_crash": lambda g: g.tut is not None and g.tut.death_tip > 2.2})
check("a crash in the tutorial does not fail it", game.state == "playing" and game.tut is not None, game.state)
check("the crash was counted and the pair is alive again", game.tut.deaths > before and not game.sim.dead, game.tut.deaths)
check("a player who stops tapping after a crash is not crashed again", game.tut.deaths - before == 1, game.tut.deaths - before)
check("tut_death counted for the funnel", sm.data["funnel_q"].get("tut_death", 0) >= 1, sm.data["funnel_q"].get("tut_death"))

# ---- the reference run from a fresh attempt finishes it -> level 1 (how-to on its 2nd page)
game.restart_level()
frames = run(game, tutorial.LEVEL["ref_taps"], shots={
    "3_climb": lambda g: g.tut is not None and g.tut.step == 1 and g.sim.progress > 0.15,
    "4_goal": lambda g: g.tut is not None and g.tut.step == 3 and g.sim.progress > 0.75,
})
check("finishing the tutorial loads level 1", game.tut is None and game.level_id == 1, (game.state, game.level_id))
check("tutorial marked done", sm.data.get("tutorial_done") == "done")
check("level 1's how-to opens on its second page", game.state == "howto" and game.howto_ui.page == 1,
      (game.state, game.howto_ui.page))
q = sm.data["funnel_q"]
check("tut_tap / tut_half / tut_star / tut_done / l1_start queued",
      {"tut_tap", "tut_half", "tut_star", "tut_done", "l1_start"} <= set(q), sorted(q))
ops = [(o["kind"], o["ref"]) for o in sm.data.get("wallet_ops", [])]
check("tutorial reward claimed once from the server", ops.count(("tutorial", "1")) == 1, ops)
shot(game, "5_level1")

# ---- never again: level 1 from the menu is level 1
game.open_menu()
game.attempts = 1
game.load_and_play_level(1)
check("after it is done, level 1 is level 1", game.tut is None and game.level_id == 1)

# ---- one-time steps are counted once, counters keep counting
n_start = q.get("tut_start")
game.online.funnel("tut_start")
game.online.funnel("app_open")
check("one-time step not counted twice", sm.data["funnel_q"].get("tut_start") == n_start)
check("counter step keeps counting", sm.data["funnel_q"].get("app_open", 0) >= 2, sm.data["funnel_q"].get("app_open"))

# ---- skip path on another fresh save
sm.data.pop("tutorial_done", None)
game.open_menu()
game.load_and_play_level(1)
check("tutorial offered again on a fresh progress", game.tut is not None)
game.skip_tutorial()
check("skip goes to level 1 and is remembered", game.tut is None and game.level_id == 1 and sm.data.get("tutorial_done") == "skip")
check("tut_skip queued", "tut_skip" in sm.data["funnel_q"])

# ---- the skip button sits where the tap lands
sm.data.pop("tutorial_done", None)
game.open_menu()
game.load_and_play_level(1)
r = game._tut_skip_rect().move(0, holo.HUD_H)
scale = min(game.win_w / float(holo.VW), game.win_h / float(game.vh))      # virtual -> window pixels
win_pos = (int(r.centerx * scale + (game.win_w - holo.VW * scale) / 2), int(r.centery * scale + (game.win_h - game.vh * scale) / 2))
swaps = game.sim.swaps
ev = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"pos": win_pos, "button": 1})
game.handle_event(ev)
check("tapping SKIP skips (and does not swap)", game.tut is None and game.level_id == 1 and game.sim.swaps == 0, swaps)

# ---- players from before 1.1.0 never see it
sm.data.pop("tutorial_done", None)
sm.stats["1"] = {"stars": 3, "score": 1000}
check("a pilot who cleared level 1 is not offered the tutorial", not tutorial.should_offer(sm))

# ---- funnel upload: a 400 drops the queue, an offline error keeps it
class _Conn:
    def __init__(self, err=None):
        self.err, self.sent = err, None

    def request(self, method, path, body=None, timeout=0):
        self.sent = (path, body)
        if self.err:
            raise self.err
        return {"ok": True}

import online  # noqa: E402
c = _Conn()
before = dict(sm.data["funnel_q"])
game.online._do_funnel(c)
check("upload goes to /api/funnel with the counts", c.sent[0] == "/api/funnel"
      and {e["s"]: e["n"] for e in c.sent[1]["events"]} == {k: v for k, v in list(before.items())[:20]}, c.sent)
check("uploaded counts leave the queue", not sm.data["funnel_q"], sm.data["funnel_q"])
game.online.funnel("l1_fail")
try:
    game.online._do_funnel(_Conn(OSError("offline")))
except OSError:
    pass
check("offline: the queue is kept for later", sm.data["funnel_q"].get("l1_fail") == 1)
game.online._do_funnel(_Conn(online.HTTPError(400, {"error": "bad funnel"})))
check("refused by the server: dropped (no endless retry)", not sm.data["funnel_q"])

print("ALL TUTORIAL TESTS PASSED" if not failed else f"{failed} TUTORIAL TESTS FAILED")
sys.exit(1 if failed else 0)
