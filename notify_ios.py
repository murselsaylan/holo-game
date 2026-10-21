"""iOS side of notify.py: local notifications through UNUserNotificationCenter (rubicon-objc). Same two calls as
android_src/org/holo/notify/NotifyWorker.java: schedule(tag, delay_s, title, text, id) replaces the pending request
of that tag, ask_permission() shows the system dialog once (iOS remembers the answer). Local notifications need no
entitlement or Info.plist key. A notification only appears while the app is not in the foreground, which is the
only time a reminder is wanted.
"""
import ctypes

ctypes.CDLL("/System/Library/Frameworks/UserNotifications.framework/UserNotifications")   # not linked by the app itself

from rubicon.objc import Block, ObjCClass
from rubicon.objc.runtime import objc_id

AUTH_OPTIONS = 1 | 2 | 4          # UNAuthorizationOptionBadge | Sound | Alert


def _center():
    return ObjCClass("UNUserNotificationCenter").currentNotificationCenter()


def schedule(tag, delay_s, title, text, _id=0):
    content = ObjCClass("UNMutableNotificationContent").alloc().init()
    content.title = title
    content.body = text
    content.sound = ObjCClass("UNNotificationSound").defaultSound
    trigger = ObjCClass("UNTimeIntervalNotificationTrigger").triggerWithTimeInterval_repeats_(max(1.0, float(delay_s)), False)
    req = ObjCClass("UNNotificationRequest").requestWithIdentifier_content_trigger_("holo_" + tag, content, trigger)
    _center().addNotificationRequest_withCompletionHandler_(req, None)      # same identifier = replaces the older one


def ask_permission():
    done = Block(lambda granted, error: None, None, bool, objc_id)
    _center().requestAuthorizationWithOptions_completionHandler_(AUTH_OPTIONS, done)
