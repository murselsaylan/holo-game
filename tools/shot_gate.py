"""Render gameplay frames of gate levels (headless) near each power-up gate -> screenshots/gate_<level>.png

    python tools/shot_gate.py 7 11 15 18
"""
import os, sys, tempfile
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["HOLO_SAVE_DIR"] = tempfile.mkdtemp(prefix="holo_shots_")
os.environ["HOLO_SERVER"] = "http://127.0.0.1:1"
import pygame
import holo

SH = os.path.join(ROOT, "screenshots")
os.makedirs(SH, exist_ok=True)
g = holo.HoloGame(headless=True)
g.save_mgr.data["is_profile_set"] = True
for lid in [int(a) for a in sys.argv[1:]]:
    g.attempts = 2
    g.load_and_play_level(lid)
    d = g.level.data
    taps = list(d.raw.get("ref_taps", []))
    # gate focus points: barriers / breakables / chaser triggers / shrink zone
    pts = [(b[0] + b[2] / 2, b[1] + b[3] / 2) for b in d.barriers] + [(b[0] + b[2] / 2, b[1] + b[3] / 2) for b in d.breakables] \
        + [(c[6] + c[8] / 2, c[7] + c[9] / 2) for c in d.chasers] + [(z[0], z[1]) for z in d.shrink]
    if not pts:
        pts = [(450, d.height / 2)]
    fx, fy = pts[0]
    ti = 0
    s = g.sim
    for _ in range(60 * 90):
        while ti < len(taps) and taps[ti] <= s.n:
            s.swap(); ti += 1
        s.step()
        if s.dead or s.won:
            break
        # stop when the pair is ~250px before the focus point (in travel direction)
        if abs(s.pivot.y - fy) < 260 and s.n > 120 and any(abs(s.pivot.y - z[1]) < 260 for z in [(fx, fy)]):
            if lid in (7, 11) or True:
                if abs(s.pivot.y - fy) < 200:
                    break
    s.events.clear()
    g.state = "playing"
    g.accum = 0.0
    g.cam_y = g._camera_target()
    for _ in range(2):
        g.update(1 / 60.0, (450, 800))
    g.draw()
    pygame.image.save(g.frame, os.path.join(SH, f"gate_{lid}.png"))
    print("saved gate", lid, "dead" if s.dead else "ok", "n", s.n, "fx", round(s.fx_t, 1), "chase", s.chase_t0, "broken", s.broken)
