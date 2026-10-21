"""Daily login calendar + the 1.0.6 achievements in the game (local wallet).

    python tools/login_test.py
"""
import os
import sys
import tempfile

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["HOLO_SAVE_DIR"] = tempfile.mkdtemp(prefix="holo_login_")
os.environ["HOLO_SERVER"] = "http://127.0.0.1:1"

import holo  # noqa: E402
import ui  # noqa: E402
import login_rewards as L  # noqa: E402
import achievements as A  # noqa: E402

ok = True


def check(name, cond, extra=""):
    global ok
    ok &= bool(cond)
    print(("PASS " if cond else "FAIL ") + name, extra)


g = holo.HoloGame(headless=True)
sm = g.save_mgr
sm.wallet = None
sm.data.update(is_profile_set=True, player_name="DAILY", player_country="TR", diamonds=0)
g.state = "menu"
for _ in range(80):                                  # it waits a second on the menu first
    g.update(1 / 60, (450, 900))
    g.draw()
check("the calendar pops up on the menu", g.state == "login" and isinstance(g.login_modal, ui.LoginRewardModal))
g._claim_login()
g.draw()
check("day 1 pays", sm.diamonds == L.LOGIN_REWARDS[0] and g.login_modal.claimed[0] == 1, sm.diamonds)
check("once a day", L.claim(sm) is None)
g.close_login_reward()
for _ in range(120):
    g.update(1 / 60, (450, 900))
check("no second popup the same day", g.state == "menu")
# the next days (dates passed in)
import datetime
d0 = datetime.date.today()
got = [L.claim(sm, (d0 + datetime.timedelta(days=k)).isoformat())[1] for k in range(1, 7)]
check("days 2-7", got == L.LOGIN_REWARDS[1:], got)
check("day 7 also fills the star wallet", sm.star_coins == L.WEEKLY_STARS)
check("the first full week opens the first Seri skin", sm.is_skin_unlocked("streak_spark") and not sm.is_skin_unlocked("streak_ember"))
check("Seri skins are not for sale", all(x not in __import__("skin_catalog").COST and x not in __import__("skin_catalog").shop_skins()
                                          and x not in __import__("skins").PREMIUM_SKINS for x in L.STREAK_SKIN_WEEKS))
check("a missed day restarts", L.claim(sm, (d0 + datetime.timedelta(days=9)).isoformat())[0] == 1)
check("loyal_7 achievement counts the best run", A.value(sm, "stat:login_best") == 7)
check("36 achievements", len(A.ACHIEVEMENTS) == 36, len(A.ACHIEVEMENTS))
g.open_achievements()
for _ in range(3):
    g.update(1 / 60, (450, 900))
    g.draw()
for p in range(g.ach_ui.max_pages):
    g.ach_ui.page = p
    g.draw()
check("every achievement page draws", True)
# 12 full weeks in a row: the five Seri skins open at 1, 2, 4, 8 and 12 completed runs
sm.data["login"] = {"last": "", "streak": 0, "days": 0, "best": 0}
sm.data["unlocked_skins"] = ["neon_pulse"]
d1 = datetime.date(2030, 1, 1)
opened = {}
for k in range(84):
    L.claim(sm, (d1 + datetime.timedelta(days=k)).isoformat())
    for sid in L.STREAK_SKIN_WEEKS:
        if sm.is_skin_unlocked(sid):
            opened.setdefault(sid, k // 7 + (1 if k % 7 == 6 else 0))
check("Seri skins open at 1/2/4/8/12 weeks", opened == {"streak_spark": 1, "streak_ember": 2, "streak_flame": 4, "streak_nova": 8,
                                                         "streak_aurora": 12}, opened)
check("next Seri skin after 4 weeks", L.next_streak_skin(4) == ("streak_nova", 8) and L.next_streak_skin(12) is None)
check("unlock text counts the weeks", "12" in sm.unlock_text("streak_aurora"))
# the calendar with the day-7 skin preview + the skin page, as pictures
import pygame  # noqa: E402
sm.data["login"] = {"last": "", "streak": 6, "days": 6, "best": 6, "weeks": 1}
sm.data["unlocked_skins"] = ["neon_pulse", "streak_spark"]
g.open_login_reward()
g.update(1 / 60, (450, 900)); g.draw()
out = os.environ.get("HOLO_SHOTS")
if out:
    pygame.image.save(g.window, os.path.join(out, "login_day7.png"))
g._claim_login(); g.draw()
if out:
    pygame.image.save(g.window, os.path.join(out, "login_day7_claimed.png"))
g.close_login_reward()
g.open_skins() if hasattr(g, "open_skins") else None
print("ALL OK" if ok else "SOME FAILED")
os._exit(0 if ok else 1)
