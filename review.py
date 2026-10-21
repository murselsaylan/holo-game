"""The store's own "rate this game" sheet (Google Play in-app review / App Store SKStoreReviewController).

Asked only at good moments: the first time the player clears level 5, 10, 25, 50, 75, 100 and 120 (each once), never twice within a
week, and only after a clean win screen (not after a paid revive). The stores keep their own quota and may show nothing;
neither tells whether the player rated, so the game simply moves on. Desktop: nothing happens.
"""
import time

import paths

MILESTONES = (5, 10, 25, 50, 75, 100, 120)
MIN_GAP_S = 7 * 86400
DELAY_S = 2.5                   # after the win screen appears: the score has landed, the player is pleased

_bridge = None
_tried = False


def should_ask(save_data, level_id, first_clear, assisted, now=None):
    """True when this win is a moment to ask (pure logic, testable on the desktop)."""
    if not first_clear or assisted or level_id not in MILESTONES:
        return False
    rec = save_data.get("review_asked") or {}
    if level_id in rec.get("levels", []):
        return False
    now = time.time() if now is None else now
    return now - float(rec.get("t", 0) or 0) >= MIN_GAP_S


def mark_asked(save_data, level_id, now=None):
    rec = save_data.setdefault("review_asked", {})
    rec.setdefault("levels", []).append(level_id)
    rec["t"] = time.time() if now is None else now


def _android():
    global _bridge, _tried
    if not _tried:
        _tried = True
        try:
            from jnius import autoclass     # python-for-android only
            activity = autoclass("org.kivy.android.PythonActivity").mActivity
            _bridge = autoclass("org.holo.review.ReviewBridge")(activity)
        except Exception as e:
            print("review unavailable:", e)
            _bridge = None
    return _bridge


def _ios_ask():
    """iOS 14+: requestReviewInScene with the app's window scene (the old requestReview is deprecated)."""
    from rubicon.objc import ObjCClass

    def p(obj, name):
        v = getattr(obj, name)
        return v() if callable(v) else v

    ctl = ObjCClass("SKStoreReviewController")
    app = p(ObjCClass("UIApplication"), "sharedApplication")
    scene = p(p(app, "connectedScenes"), "anyObject")
    if scene is not None:
        ctl.requestReviewInScene_(scene)
    else:
        ctl.requestReview()


def ask():
    """Shows the store's sheet if the platform has one. Returns True if it was asked for."""
    try:
        if paths.is_ios():
            _ios_ask()
            return True
        if paths.is_android():
            b = _android()
            if b is not None:
                b.ask()
                return True
    except Exception as e:
        print("review ask failed:", e)
    return False
