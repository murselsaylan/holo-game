"""Regression checks for input, pause safety and HUD layout; isolated saves."""
import os
import sys
import tempfile

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["HOLO_SAVE_DIR"] = tempfile.mkdtemp(prefix="holo_polish_")
os.environ["HOLO_SERVER"] = "http://127.0.0.1:1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame
from holo import HoloGame, HUD_H, VW
from sim import SIM_DT, replay

g = HoloGame(headless=True)
g.save_mgr.data["howto_seen"] = True
assert g.load_and_play_level(2)
g.swap_pivot()
g.swap_pivot()
assert g.sim.swaps == 1 and g.taps == [0], "duplicate event swapped back"
g.update_gameplay(SIM_DT)
g.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE, repeat=True))
assert g.sim.swaps == 1, "held key generated a tap"
g.handle_event(pygame.event.Event(pygame.WINDOWFOCUSLOST))
assert g.state == "paused"
tick = g.sim.n
g.resume_game()
g.swap_pivot()
g.update_gameplay(0.2)
assert g.sim.n == tick and g.sim.swaps == 1, "countdown advanced physics/input"
g.draw()
pygame.image.save(g.frame, os.path.join(os.path.dirname(__file__), "../screenshots/polish_resume.png"))
g.update_gameplay(1.1)
g.update_gameplay(SIM_DT)
assert g.sim.n == tick + 1, "countdown accumulated catch-up frames"
# Footer and letterbox taps cannot change the orbit.
for x, y in [(-5, HUD_H + 100), (VW + 5, HUD_H + 100), (450, g.vh - 10)]:
    g.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(x / 2, y / 2)))
assert g.sim.swaps == 1
assert not any(g.hud.hit_pause((x, 70)) and g.hud.hit_shield((x, 70)) for x in range(VW))
g.toasts = [["Achievement", "Details", 4.0]]
g.update(0.1, (0, 0))
assert g.toasts[0][2] == 4.0, "deferred achievement expired unseen"
g.state = "paused"
g.update(0.1, (0, 0))
assert g.toasts[0][2] < 4.0
# Actual input path and server replay agree after the duplicate-event guard.
g.load_and_play_level(2)
taps = iter(g.level.data.raw["ref_taps"])
next_tap = next(taps, None)
while g.state == "playing" and g.sim.n < 24000:
    if next_tap == g.sim.n:
        g.swap_pivot()
        next_tap = next(taps, None)
    g.update_gameplay(SIM_DT)
assert g.state == "victory"
_, result = replay(g.level.data, g.taps)
assert result and result["stars"] == 3
pygame.quit()
print("PASS: input, resume, focus loss, touch bounds, HUD, toasts and replay")
