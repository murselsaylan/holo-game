"""Tiny haptic feedback helper (Android and iOS; silently does nothing elsewhere).

The vibrator is a Java system service reached through pyjnius: looking the classes up takes long, and every vibrate()
is a synchronous binder call. Both happen on a small worker thread (set up at start, not on the first bump), so a
bounce or a pickup never makes the game loop wait for Android.
"""
import queue
import threading

import paths

enabled = True
_jobs = queue.Queue(maxsize=4)          # a burst of events keeps only a few pulses, the rest are dropped
_started = False


def set_enabled(v):
    global enabled
    enabled = bool(v)


def _worker():
    vib = None
    try:
        from jnius import autoclass  # provided by python-for-android
        activity = autoclass("org.kivy.android.PythonActivity").mActivity
        vib = activity.getSystemService(autoclass("android.content.Context").VIBRATOR_SERVICE)
    except Exception:
        vib = None
    while True:
        ms = _jobs.get()
        if vib is None:
            continue
        try:
            vib.vibrate(int(ms))
        except Exception:
            pass


def start():
    """Look the vibrator up in the background right away (call once at startup)."""
    global _started
    if _started or not paths.is_android():
        return
    _started = True
    threading.Thread(target=_worker, daemon=True).start()


_ios_gen = None          # UIImpactFeedbackGenerator (iOS), False when unavailable


def _ios_buzz(ms):
    """iOS: a light / medium tap from the Taptic Engine (UIKit wants the main thread, which runs the game loop)."""
    global _ios_gen
    if _ios_gen is None:
        try:
            from rubicon.objc import ObjCClass
            _ios_gen = [ObjCClass("UIImpactFeedbackGenerator").alloc().initWithStyle_(style) for style in (0, 1)]
        except Exception as e:
            print("haptics (iOS) unavailable:", e)
            _ios_gen = False
    if _ios_gen:
        try:
            _ios_gen[1 if ms >= 30 else 0].impactOccurred()
        except Exception:
            pass


def buzz(ms=20):
    if not enabled:
        return
    if paths.is_ios():
        _ios_buzz(ms)
        return
    if not paths.is_android():
        return
    if not _started:
        start()
    try:
        _jobs.put_nowait(ms)
    except queue.Full:
        pass
