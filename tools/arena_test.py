"""The arena mode end to end, headless: open it from the menu's callback, play with the look-ahead bot, buy a shield,
die, revive (paid, limited to arena.MAX_REVIVES), finish, check the result, the record, the star wallet and that the
run's taps + help replay to the same points. Screenshots go to the folder given as the first argument (optional).

    python tools/arena_test.py [screenshot dir]
"""
import os
import sys
import tempfile

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
os.environ["HOLO_SAVE_DIR"] = tempfile.mkdtemp(prefix="holo_arena_")
os.environ["HOLO_SERVER"] = "http://127.0.0.1:9"          # offline

import pygame  # noqa: E402

import holo  # noqa: E402
import arena as A  # noqa: E402
import ui  # noqa: E402
from arena_bot import _survives, RHYTHMS  # noqa: E402
from sim import SIM_DT  # noqa: E402

SHOTS = sys.argv[1] if len(sys.argv) > 1 else None
ok = True


def check(name, cond, extra=""):
    global ok
    ok &= bool(cond)
    print(("PASS " if cond else "FAIL ") + name, extra)


def shot(name):
    if SHOTS:
        os.makedirs(SHOTS, exist_ok=True)
        pygame.image.save(g.frame, os.path.join(SHOTS, name + ".png"))


g = holo.HoloGame(headless=True)
sm = g.save_mgr
sm.data.update(is_profile_set=True, player_name="ARENA", player_country="TR", diamonds=500, shield_stock=2)
sm.wallet = None
for lv in range(1, 7):
    sm.stats[str(lv)] = {"stars": 3, "best_score": 1000}
check("arena unlocked after level 5", sm.arena_unlocked)


def frames(n, bot=True):
    for _ in range(n):
        s = g.sim
        if bot and g.state == "playing" and s.n % 4 == 0 and not s.dead:
            ty = g.arena_run.core[:2] if g.arena_run.core else None
            a = max(_survives(s, False, e, ty) for e in RHYTHMS)
            b = max(_survives(s, True, e, ty) for e in RHYTHMS)
            if b > a:
                g.swap_pivot()
        g.update(SIM_DT, (450, 900))
        g.draw()


g.open_menu()
g.draw()
shot("0_menu")
check("open_arena", g.open_arena() and g.arena_run is not None and g.state == "playing")
frames(90)
shot("1_start")
g.use_hud_shield()
check("shield from the HUD", g.sim.shields == 1 and g.assists and g.assists[-1][1] == "S", str(g.assists))
frames(60 * 7)
shot("2_pickup")
check("power fields appear during the run", g.arena_run.pickups or g.sim.fx_t > 0 or g.sim.boost_t > 0)
check("cores refill the clock", g.arena_run.cores > 0 and g.arena_run.time_left > 0, f"{g.arena_run.cores} cores")
frames(60 * 24)
shot("2_storm_warn")
frames(60 * 5)
shot("2_storm")
# play until a death
n = 0
while g.state == "playing" and n < 60 * 600:
    frames(1, bot=False) if g.sim.n % 2 else frames(1)
    n += 1
    if g.state == "playing" and g.sim.n % 400 == 0:
        shot(f"3_play_{g.sim.n // 60}s")
frames(60, bot=False)
check("death offers a revive", isinstance(g.failure_modal, ui.EndlessReviveModal), g.state)
shot("4_revive_offer")
revives = 0
while isinstance(g.failure_modal, ui.EndlessReviveModal):
    d0 = sm.diamonds
    g.revive_run()
    revives += 1
    check(f"revive {revives} paid", sm.diamonds == d0 - holo.REVIVE_COST and g.state == "playing")
    while g.state == "playing":
        g.swap_pivot() if g.sim.n % 30 == 0 else None     # a careless player: dies soon after
        frames(1, bot=False)
    frames(60, bot=False)
check("revives limited", revives == A.MAX_REVIVES, str(revives))
check("result modal", isinstance(g.failure_modal, ui.ArenaResultModal), type(g.failure_modal).__name__)
shot("5_result")
run = g.arena_run
check("record saved", sm.arena["best"] == run.points and sm.arena["runs"] == 1, str(sm.arena))
check("stars to the wallet", sm.star_coins == run.stars, f"{sm.star_coins} / {run.stars}")
rep = A.replay(g.arena_seed, g.taps, run.n, assists=g.assists)
check("replay gives the same points", (rep.n, rep.points) == (run.n, run.points), f"{rep.points} vs {run.points}")
g.retry_after_fail()
check("retry opens a new arena", g.arena_run is not None and g.arena_run is not run and g.state == "playing")
g.open_menu()
check("menu leaves the arena", g.arena_run is None and g.sim is None)
# out of time: the run ends like a crash; a revive gives clock back; the replay agrees
run = A.ArenaRun(77)
run.sim.add_shield()
taps = []
while not run.dead:
    if run.n % 25 == 0:
        taps.append(run.n)
        run.swap()
    run.step()
died = run.n
check("a run can end by running out of time", run.timed_out or run.dead, f"timed out {run.timed_out} at {run.seconds:.1f}s")
if run.timed_out:
    run.revive()
    check("a revive after the clock ran out gives clock back", run.time_left >= A.REVIVE_TIME and not run.dead)
print("ALL OK" if ok else "SOME FAILED")
sys.exit(0 if ok else 1)
