"""Ranking name safeguards: the offensive-name filter, hiding a pilot, reporting a name (tap a row)."""
import os
import sys
import tempfile

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["HOLO_SAVE_DIR"] = tempfile.mkdtemp(prefix="holo_names_")
os.environ["HOLO_SERVER"] = "http://127.0.0.1:1"

import pygame  # noqa: E402
import name_filter as nf  # noqa: E402
import holo  # noqa: E402

FAIL = []


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        FAIL.append(name)


for bad in ("AMK", "SİKTİR", "S1KT1R", "FUCK YOU", "A.M.K", "OROSPU", "PUTA", "GÖT", "MK SEN"):
    check(f"offensive: {bad}", nf.is_offensive(bad))
for ok in ("PİLOT", "NOVA", "ÇOCUK", "NORMAL", "KAMIL", "BANANIN", "SALAK", "MAKAS", "KASIK", "GÖTÜR", "EYEYEY"):
    check(f"fine: {ok}", not nf.is_offensive(ok))
check("masked keeps the first letter", nf.masked("AMK") == "A***")

g = holo.HoloGame(headless=True)
sm = g.save_mgr
rows = [{"rank": 1, "id": "a" * 32, "name": "AMK", "country": "TR", "levels": 9, "stars": 20, "score": 900},
        {"rank": 2, "id": "b" * 32, "name": "NOVA", "country": "DE", "levels": 8, "stars": 18, "score": 800},
        {"rank": 3, "id": sm.player_id, "name": sm.player_name, "country": "TR", "levels": 1, "stars": 3, "score": 10}]
g.online.boards["global"] = {"rows": rows}
sent = []
g.online.report_name = lambda pid, name: sent.append((pid, name))
lb = g.leaderboard_ui
lb.scope = "global"

check("filter on by default: masked", nf.shown_name(sm, rows[0]["id"], rows[0]["name"]) == "A***")
check("clean names untouched", nf.shown_name(sm, rows[1]["id"], "NOVA") == "NOVA")


def tap(x, y):
    for t_, b in ((pygame.MOUSEBUTTONDOWN, 1), (pygame.MOUSEBUTTONUP, 1)):
        cb = lb.handle_event(pygame.event.Event(t_, button=b, pos=(x, y)))
        if callable(cb):
            cb()


def row_y(i):
    return lb._lt() + 60 + i * lb.ROW_H + 40


tap(500, row_y(2))
check("tapping my own row opens nothing", lb.sel is None)
tap(500, row_y(1))
check("tapping a pilot opens the actions", lb.sel is not None and lb.sel["id"] == "b" * 32)
lb.draw(g.frame)
lb.sel_btns[1].callback()
check("report sends id and real name", sent == [("b" * 32, "NOVA")] and lb.sel is None)
tap(500, row_y(1))
lb.sel_btns[0].callback()
check("hide stores the pilot", "b" * 32 in nf.hidden_players(sm))
check("hidden pilot shows no name", nf.shown_name(sm, "b" * 32, "NOVA") is None)
lb.draw(g.frame)
tap(500, row_y(1))
lb.sel_btns[0].callback()
check("show again", "b" * 32 not in nf.hidden_players(sm))
tap(500, row_y(0))
lb.sel_btns[2].callback()
check("filter switch off", sm.settings["hide_bad_names"] is False and lb.sel is not None)
check("filter off: real name", nf.shown_name(sm, rows[0]["id"], "AMK") == "AMK")
lb.sel_btns[3].callback()
check("close", lb.sel is None)
for _ in range(3):
    lb.update((0, 0))
    lb.draw(g.frame)
print("ALL OK" if not FAIL else f"FAILED: {FAIL}")
sys.exit(1 if FAIL else 0)
