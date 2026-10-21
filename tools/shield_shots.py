"""Screenshots of the failure screen's shield button (free / stock / buy / short) and the lit HUD button:
    python tools/shield_shots.py     -> screenshots/shield_fail_*.png, shield_hud.png"""
import os
import sys
import tempfile

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["HOLO_SAVE_DIR"] = tempfile.mkdtemp(prefix="holo_shield_")
os.environ["HOLO_SERVER"] = "http://127.0.0.1:1"

import pygame  # noqa: E402
import holo  # noqa: E402
import ui  # noqa: E402

pygame.init()
g = holo.HoloGame(headless=True) if "headless" in holo.HoloGame.__init__.__code__.co_varnames else holo.HoloGame()
sm = g.save_mgr
OUT = os.path.join(ROOT, "screenshots")


def frames(n=3):
    for _ in range(n):
        g.update(1 / 60.0, (450, 800))
        g.draw()


class W:
    credits = {"shield": 0, "revive": 0}
    free_shield = False

    def wallet_flush(self):
        pass


g.load_and_play_level(63)
g.state = "playing"
g.swap_pivot()
frames(20)
hud_shot = os.path.join(OUT, "shield_hud.png")
sm.wallet = W()
sm.wallet.free_shield = True
frames(2)
pygame.image.save(g.frame, hud_shot)                                   # the button lit, "BEDAVA" tag
g.sim.dead = True
g.state, g.death_timer = "dying", 0.01
g.attempts = 4
frames(3)
cases = (("free", 3, True, 0, 40), ("stock", 3, False, 2, 40), ("buy", 4, False, 0, 40), ("short", 4, False, 0, 3))
for name, tries, free, stock, dia in cases:
    sm.wallet.free_shield = free
    sm.data["shield_stock"] = stock
    sm.data["diamonds"] = dia
    g.attempts = tries
    g.failure_modal.attempts = tries
    for _ in range(4):
        frames(2)
    pygame.image.save(g.frame, os.path.join(OUT, f"shield_fail_{name}.png"))
    print("saved", name, g.failure_modal.shield_mode())

# endless result card
import config  # noqa: E402
config.dev_unlock_all = lambda: True
for name, free, stock, dia in (("endless_free", True, 0, 40), ("endless_stock", False, 2, 40), ("endless_buy", False, 0, 40)):
    sm.wallet.free_shield, sm.data["shield_stock"], sm.data["diamonds"] = free, stock, dia
    g.open_endless()
    g.state = "playing"
    g.swap_pivot()
    frames(40)
    g.sim.dead = True
    g.state, g.death_timer = "dying", 0.01
    frames(3)
    if isinstance(g.failure_modal, ui.EndlessReviveModal):
        g.failure_modal.on_finish()
    frames(6)
    pygame.image.save(g.frame, os.path.join(OUT, f"shield_fail_{name}.png"))
    print("saved", name, g.failure_modal.shield_mode())
