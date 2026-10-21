"""Local reminders (1.0.6, android_src/org/holo/notify/NotifyWorker.java).

Three reminders in Olo's voice (notify_lines.py, the title is always "Olo"), all re-planned every time the game starts and after the daily login reward is claimed (a newer plan
replaces the older one, so a player who comes back every day never sees one):
  daily     the next day's login reward, at REMIND_HOUR local time
  comeback  COMEBACK_DAYS after the last start - the endless map is new every climb
  weekly    the next Saturday at WEEKLY_HOUR - weekly missions, the endless climb's weekly prize, a hard level
Android: WorkManager (NotifyWorker.java); iOS: UNUserNotificationCenter (notify_ios.py). Both need the player's OK:
ask_permission() asks once, right after the first login reward (the moment the reminder makes sense). Off the phone
(desktop, tests) everything here is a no-op. The text is picked at random from notify_lines.py in the player's language,
never the same line as the last time for that kind.
"""
import datetime
import random

import login_rewards
import notify_lines
import paths
from locales import get_language

REMIND_HOUR = 18
COMEBACK_DAYS = 3
WEEKLY_HOUR = 12
WEEKLY_WEEKDAY = 5                              # Saturday (Monday = 0)

_backend = None       # (schedule(tag, delay_s, title, text, id), ask()) once looked up; False = no notifications here


def _bridge():
    global _backend
    if _backend is None:
        try:
            if paths.is_ios():
                import notify_ios
                _backend = (notify_ios.schedule, notify_ios.ask_permission)
            else:
                from jnius import autoclass   # python-for-android only
                cls = autoclass("org.holo.notify.NotifyWorker")
                act = autoclass("org.kivy.android.PythonActivity").mActivity
                _backend = (lambda tag, delay, title, text, nid: cls.schedule(act, tag, delay, title, text, nid),
                            lambda: cls.askPermission(act))
        except Exception as e:
            print("notifications unavailable:", e)
            _backend = False
    return _backend or (None, None)


def pick(kind, save, lang=None, rng=random):
    """A random line of `kind` in the player's language; never the one used last time (remembered in the save)."""
    pool = notify_lines.lines(kind, lang or get_language())
    last = save.data.setdefault("notif_last", {})
    choices = [i for i in range(len(pool)) if i != last.get(kind)] or list(range(len(pool)))
    i = rng.choice(choices)
    last[kind] = i
    return pool[i]


def weekly_delay(now=None):
    """Seconds until the next Saturday WEEKLY_HOUR:00 (a week from now when it is already past on a Saturday)."""
    now = now or datetime.datetime.now()
    target = now.replace(hour=WEEKLY_HOUR, minute=0, second=0, microsecond=0)
    target += datetime.timedelta(days=(WEEKLY_WEEKDAY - now.weekday()) % 7)
    if target <= now:
        target += datetime.timedelta(days=7)
    return int((target - now).total_seconds())


def daily_delay(save, now=None):
    """Seconds until the next login-reward reminder, and that reward's (day, diamonds)."""
    now = now or datetime.datetime.now()
    target = now.replace(hour=REMIND_HOUR, minute=0, second=0, microsecond=0)
    if target <= now or not login_rewards.claimable(save, now.date().isoformat()):
        target += datetime.timedelta(days=1)
        if target <= now:
            target += datetime.timedelta(days=1)
    day, _streak = login_rewards.next_day(save, target.date().isoformat())
    return int((target - now).total_seconds()), day, login_rewards.LOGIN_REWARDS[day - 1]


def plan(save, now=None):
    schedule, _ask = _bridge()
    if schedule is None or not save.is_profile_set:
        return False
    try:
        delay, day, gems = daily_delay(save, now)
        title = notify_lines.TITLE
        schedule("daily", delay, title, pick("daily", save).format(d=day, n=gems), 1)
        schedule("comeback", COMEBACK_DAYS * 86400, title, pick("comeback", save), 2)
        schedule("weekly", weekly_delay(now), title, pick("weekly", save), 3)
        save.save()                           # the "last line" memory
        return True
    except Exception as e:
        print("notification plan failed:", e)
        return False


def ask_permission(save):
    """Asks for the notification permission once per install (the system dialog; both OSes remember a "no")."""
    if save.data.get("notif_asked"):
        return
    _schedule, ask = _bridge()
    if ask is None:
        return
    save.data["notif_asked"] = True
    save.save()
    try:
        ask()
    except Exception as e:
        print("notification permission failed:", e)
