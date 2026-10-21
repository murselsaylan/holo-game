"""Reminder timing (notify.py): python tools/notify_test.py"""
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import login_rewards as L  # noqa: E402
import notify  # noqa: E402


class Save:
    def __init__(self, last="", streak=0):
        self.data = {"login": {"last": last, "streak": streak, "days": streak, "best": streak}}
        self.is_profile_set = True

    def save(self):
        pass


now = datetime.datetime(2026, 10, 2, 9, 30)
d, day, gems = notify.daily_delay(Save(), now)
assert d == int(8.5 * 3600) and day == 1, (d, day)                 # unclaimed today: this evening, day 1
d, day, gems = notify.daily_delay(Save("2026-10-02", 3), now)
assert d == int(32.5 * 3600) and day == 4 and gems == L.LOGIN_REWARDS[3], (d, day)   # claimed: tomorrow, next day
d, day, gems = notify.daily_delay(Save("2026-10-01", 2), datetime.datetime(2026, 10, 2, 20, 0))
assert d == 22 * 3600 and day == 1, (d, day)                       # evening, still unclaimed: tomorrow (streak broken)
assert notify.plan(Save()) is False                                 # off the phone: no-op

# weekly: the next Saturday noon
assert notify.weekly_delay(datetime.datetime(2026, 10, 19, 9, 0)) == int(5.125 * 86400)          # Monday 09:00
assert notify.weekly_delay(datetime.datetime(2026, 10, 17, 11, 0)) == 3600                       # Saturday 11:00: today
assert notify.weekly_delay(datetime.datetime(2026, 10, 17, 12, 0, 1)) == 7 * 86400 - 1           # just past: next week

# Olo's lines: every language has every kind, placeholders format, titles are "Olo", no line twice in a row
import random  # noqa: E402
import notify_lines  # noqa: E402
assert notify_lines.TITLE == "Olo"
for kind in ("daily", "comeback", "weekly"):
    for lang in ("tr", "en", "de", "es"):
        assert all(r.get(lang) for r in notify_lines.R[kind]), (kind, lang)
        assert len(notify_lines.lines(kind, lang)) >= 6
        for line in notify_lines.lines(kind, lang):
            line.format(d=3, n=10)
sv = Save()
for lang in ("tr", "en", "de", "es"):
    seen = [notify.pick("weekly", sv, lang, random.Random(k)) for k in range(1)]
    prev = None
    rng = random.Random(7)
    for _ in range(300):
        cur = notify.pick("daily", sv, lang, rng)
        assert cur != prev
        prev = cur

# plan() schedules the three reminders with the right tags / delays / title
calls = []
notify._backend = (lambda tag, delay, title, text, nid: calls.append((tag, delay, title, text, nid)), lambda: calls.append("ask"))
assert notify.plan(Save(), now)
assert [c[0] for c in calls] == ["daily", "comeback", "weekly"] and all(c[2] == "Olo" for c in calls), calls
assert calls[1][1] == 3 * 86400 and calls[2][1] == notify.weekly_delay(now) and "{" not in calls[0][3]
sv = Save()
notify.ask_permission(sv); notify.ask_permission(sv)
assert calls.count("ask") == 1                                       # asked once
notify._backend = None
print("ALL NOTIFY TESTS PASSED")
