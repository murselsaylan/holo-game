"""Screenshots of the v5 endless zones: teleports the pair into chosen stages of a seed and saves the frame.

    python tools/endless_shots.py [out_dir] [seed nonce hex]
"""
import os
import sys
import tempfile

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["HOLO_SAVE_DIR"] = tempfile.mkdtemp(prefix="holo_shots_")
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "store_assets", "endless_v5_shots")
os.makedirs(OUT, exist_ok=True)

import pygame  # noqa: E402
import holo  # noqa: E402
import endless as E  # noqa: E402
from endless_view import EndlessLevel  # noqa: E402
from sim import SIM_DT  # noqa: E402

g = holo.HoloGame(headless=True)
sm = g.save_mgr
sm.data.update(is_profile_set=True, player_name="CLIMBER", player_country="TR")
for lv in range(1, 11):
    sm.stats[str(lv)] = {"stars": 3, "best_score": 1000}
sm.endless["ghost"] = [i * 4 for i in range(400)]
sm.endless["best_m"] = 600
nonce = sys.argv[2] if len(sys.argv) > 2 else "00000000deadbeef"
g.open_endless()
week = g.endless_week
run = E.EndlessRun(E.seed_of(week, nonce), record_events=True)
lvl = EndlessLevel(run)
lvl.finish(run.w0)
lvl.record_m, lvl.ghost = 600, sm.endless["ghost"]
g.endless_run, g.level, g.sim = run, lvl, run.sim
g._reset_attempt()
g.endless_fx = {"m100": 0, "tier": 0, "record": False, "streak": 0, "last_star": -9.0, "stage": 0, "goal": 0, "series": []}
g.state = "playing"
targets = [int(x) for x in (sys.argv[3].split(",") if len(sys.argv) > 3 else "0,1,2,4,6,10,11,13".split(","))]


def teleport(k):
    while run.w0 < max(0, k - 1):
        run._advance()
    st = run.world.stage(k)
    s = run.sim
    x, y = st.d["start"][0], st.d["start"][1] - 150.0
    for o in s.orbs:
        o.x, o.y = x, y
    run.best_y = min(run.best_y, y)
    s.t = 4.0
    s.swaps = 1
    s.guard = True                              # the pair bounces instead of dying while the shot is taken


for k in targets:
    teleport(k)
    g.resume_timer = 0
    for _ in range(6):
        g.update(SIM_DT, (450, 900))
    g.endless_fx["stage"] = k - 1
    for _ in range(40):
        run.sim.guard = True
        g.update(SIM_DT, (450, 900))
        g.draw()
    st = run.world.stage(k)
    name = f"zone_{k:02d}_sector{st.sector}_ev{st.event}_lvl{st.level}.png"
    pygame.image.save(g.frame, os.path.join(OUT, name))
    print(name, "stage", run.stage, "metres", run.metres)
os._exit(0)
