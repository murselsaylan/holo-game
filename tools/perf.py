import os, sys, time, tempfile
os.environ["SDL_VIDEODRIVER"] = "dummy"; os.environ["SDL_AUDIODRIVER"] = "dummy"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["HOLO_SAVE_DIR"] = tempfile.mkdtemp(prefix="holo_perf_"); os.environ["HOLO_SERVER"] = "http://127.0.0.1:1"
import pygame, holo
from sim import SIM_DT
g = holo.HoloGame(headless=True)
for lid in [int(a) for a in sys.argv[1:]] or [10]:
    g.load_and_play_level(lid)
    t0 = time.time(); n = 0
    taps = sorted(g.level.data.raw.get("ref_taps", [])); ti = 0
    while g.state == "playing" and n < 600:
        while ti < len(taps) and taps[ti] <= g.sim.n:
            g.swap_pivot(); ti += 1
        g.update_gameplay(SIM_DT); g._update_camera(SIM_DT); n += 1
    upd = (time.time() - t0) / max(1, n) * 1000
    t0 = time.time()
    for _ in range(60):
        g.draw()
    drw = (time.time() - t0) / 60 * 1000
    t0 = time.time(); g.load_and_play_level(lid); load = time.time() - t0
    print(f"level {lid}: update {upd:.2f} ms/step, draw {drw:.2f} ms/frame, level load {load*1000:.0f} ms, walls={len(g.level.data.walls)} h={g.level.height:.0f}")
