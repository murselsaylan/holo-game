"""Die -> TRY AGAIN loop on every level, driven through real input events (finger + synthesized mouse, like
Android sends them). Any exception or a state other than "playing" after the tap is reported.

    python tools/retry_fuzz.py            # all levels, 3 retries each
"""
import os
import random
import sys
import traceback

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import pygame  # noqa: E402
import holo  # noqa: E402


def tap(game, pos):
    vw, vh = holo.VW, game.vh
    if not game.scaled:                                 # headless: the window is smaller than the virtual frame
        k = min(game.win_w / float(vw), game.win_h / float(vh))
        ox, oy = (game.win_w - vw * k) * 0.5, (game.win_h - vh * k) * 0.5
        pos = (int(pos[0] * k + ox), int(pos[1] * k + oy))
    fx, fy = pos[0] / vw, pos[1] / vh
    for ev in (pygame.event.Event(pygame.FINGERDOWN, x=fx, y=fy, finger_id=0, touch_id=0),
               pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=1, touch=True),
               pygame.event.Event(pygame.FINGERUP, x=fx, y=fy, finger_id=0, touch_id=0),
               pygame.event.Event(pygame.MOUSEBUTTONUP, pos=pos, button=1, touch=True)):
        game.handle_event(ev)
        game.update(1 / 60.0, pos)
        game.draw()


def main():
    rnd = random.Random(7)
    game = holo.HoloGame(headless=True)
    game.save_mgr.data["howto_seen"] = True
    game.save_mgr.save = lambda *a, **k: None          # never touch the real save file
    game.online.submit = lambda *a, **k: None
    problems = []
    levels = [int(a) for a in sys.argv[1:]] or list(range(1, 141))
    for lid in levels:
        try:
            game.load_and_play_level(lid)
            for attempt in range(3):
                frames = 0
                while game.state in ("playing", "dying") and frames < 60 * 40:
                    if game.state == "playing" and rnd.random() < 0.04:
                        game.swap_pivot()
                    game.update(1 / 60.0, (450, 800))
                    if frames % 6 == 0:
                        game.draw()
                    frames += 1
                if game.state == "victory":
                    game.restart_level()
                    continue
                if game.state != "failed":
                    problems.append((lid, attempt, "stuck in " + game.state))
                    break
                for _ in range(40):                     # let the modal animate in
                    game.update(1 / 60.0, (450, 800))
                    game.draw()
                btn = game.failure_modal.btn_retry.rect
                tap(game, btn.center)
                if game.state != "playing":
                    problems.append((lid, attempt, "after TRY AGAIN state=" + game.state))
                    break
        except Exception:
            problems.append((lid, "exception", traceback.format_exc()))
            game.state = "menu"
    for p in problems:
        print("PROBLEM", p)
    print("levels", len(levels), "problems", len(problems))


if __name__ == "__main__":
    main()
