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


now = datetime.datetime(2026, 10, 2, 9, 30)
d, day, gems = notify.daily_delay(Save(), now)
assert d == int(8.5 * 3600) and day == 1, (d, day)                 # unclaimed today: this evening, day 1
d, day, gems = notify.daily_delay(Save("2026-10-02", 3), now)
assert d == int(32.5 * 3600) and day == 4 and gems == L.LOGIN_REWARDS[3], (d, day)   # claimed: tomorrow, next day
d, day, gems = notify.daily_delay(Save("2026-10-01", 2), datetime.datetime(2026, 10, 2, 20, 0))
assert d == 22 * 3600 and day == 1, (d, day)                       # evening, still unclaimed: tomorrow (streak broken)
assert notify.plan(Save()) is False                                 # off the phone: no-op
print("ALL NOTIFY TESTS PASSED")
