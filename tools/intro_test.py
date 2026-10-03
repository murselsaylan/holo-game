"""Start-up intro: renders, continues the Android loading image, a tap speeds it up, it ends in the menu."""
import os
import sys
import tempfile

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["HOLO_SAVE_DIR"] = tempfile.mkdtemp(prefix="holo_intro_")
os.environ["HOLO_SERVER"] = "http://127.0.0.1:1"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import pygame  # noqa: E402
import holo  # noqa: E402

game = holo.HoloGame(headless=True)
game.save_mgr.data["is_profile_set"] = True
game.state, game._after_intro, game.intro_t, game.intro_speed = "intro", "menu", 0.0, 1.0

# frame 0 == assets/presplash.png (same flat colour, the logo at the same spot), so the hand-over has no jump
game.draw()
splash = pygame.image.load(os.path.join(ROOT, "assets", "presplash.png"))
assert splash.get_at((5, 5))[:3] == holo.BG_DARK and game.frame.get_at((5, 5))[:3] == holo.BG_DARK, "flat splash colour"

game.intro_t = 1.3
game.draw()
pygame.image.save(game.frame, os.path.join(ROOT, "screenshots", "intro_mid.png"))

game.intro_t = 0.2
game.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(450, 800)))
assert game.state == "intro" and game.intro_speed > 1.0, "a tap plays the rest faster, it does not cut it"
for _ in range(40):
    game.update(1 / 60.0, (450, 800))
assert game.state == "menu", "a sped-up intro ends within a second"

game.state, game.intro_t, game.intro_speed = "intro", 0.0, 1.0
for _ in range(int(holo.INTRO_LEN * 60) + 5):
    game.update(1 / 60.0, (450, 800))
assert game.state == "menu", "the intro ends by itself"
print("PASS: intro render, splash hand-over, tap speed-up and automatic end")
