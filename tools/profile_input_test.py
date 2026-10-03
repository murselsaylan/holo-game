"""Regression test: letters used as desktop shortcuts must remain typeable in profiles."""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame

from holo import HoloGame


pygame.init()
game = HoloGame(headless=True)
game.save_mgr.is_profile_set = True
game.open_profile("menu")
game.profile_modal.name_text = "HO"

# Android/SDL sends KEYDOWN before TEXTINPUT. P used to close this modal here.
game.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_p, unicode="p"))
assert game.state == "profile", "P closed the profile editor"
game.handle_event(pygame.event.Event(pygame.TEXTINPUT, text="p"))
game.handle_event(pygame.event.Event(pygame.TEXTINPUT, text="wator"))
assert game.profile_modal.name_text == "HOPWATOR"

print("PASS: HOPWATOR remains typeable and the profile modal stays open")
