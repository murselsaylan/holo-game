"""Local reminders (1.0.6, android_src/org/holo/notify/NotifyWorker.java).

Two reminders, both re-planned every time the game starts and after the daily login reward is claimed (a newer plan
replaces the older one, so a player who comes back every day never sees one):
  daily     the next day's login reward, at REMIND_HOUR local time
  comeback  COMEBACK_DAYS after the last start - the endless map is new every climb
Android 13+ needs the player's OK: ask_permission() asks once, right after the first login reward (the moment the
reminder makes sense). Off the phone (desktop, tests) everything here is a no-op.
"""
import datetime

import login_rewards
from locales import t

REMIND_HOUR = 18
COMEBACK_DAYS = 3

_java = None          # (NotifyWorker class, activity) once looked up; False = not on Android


def _bridge():
    global _java
    if _java is None:
        try:
            from jnius import autoclass   # python-for-android only
            _java = (autoclass("org.holo.notify.NotifyWorker"), autoclass("org.kivy.android.PythonActivity").mActivity)
        except Exception as e:
            print("notifications unavailable:", e)
            _java = False
    return _java or (None, None)


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
    cls, act = _bridge()
    if cls is None or not save.is_profile_set:
        return False
    try:
        delay, day, gems = daily_delay(save, now)
        cls.schedule(act, "daily", delay, t("notif_daily_title"), t("notif_daily_text", d=day, n=gems), 1)
        cls.schedule(act, "comeback", COMEBACK_DAYS * 86400, t("notif_back_title"), t("notif_back_text"), 2)
        return True
    except Exception as e:
        print("notification plan failed:", e)
        return False


def ask_permission(save):
    """Asks for the notification permission once per install (Android 13+ only shows the system dialog)."""
    if save.data.get("notif_asked"):
        return
    cls, act = _bridge()
    if cls is None:
        return
    save.data["notif_asked"] = True
    save.save()
    try:
        cls.askPermission(act)
    except Exception as e:
        print("notification permission failed:", e)
