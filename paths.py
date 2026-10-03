"""Where things live. Read-only assets ship with the app; saves go to a writable per-user directory."""
import os
import sys

if getattr(sys, "frozen", False):
    BASE_DIR = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def is_android():
    return "ANDROID_ARGUMENT" in os.environ or "ANDROID_PRIVATE" in os.environ or hasattr(sys, "getandroidapilevel")


def is_ios():
    """iPhone / iPad build (pygame-ios: Python 3.13 reports sys.platform "ios")."""
    return sys.platform == "ios"


def is_mobile():
    """A phone / tablet build: full screen, touch only, no quit button."""
    return is_android() or is_ios()


def asset(*parts):
    return os.path.join(BASE_DIR, "assets", *parts)


def user_dir():
    """Writable directory for save data (app-private storage on Android)."""
    override = os.environ.get("HOLO_SAVE_DIR")
    if override:
        os.makedirs(override, exist_ok=True)
        return override
    if is_android():
        d = os.environ.get("ANDROID_PRIVATE") or os.environ.get("ANDROID_ARGUMENT") or BASE_DIR
        return d
    if is_ios():
        # the app bundle is read-only; Application Support is private to the app and backed up by iCloud
        d = os.path.join(os.path.expanduser("~"), "Library", "Application Support", "holo")
        os.makedirs(d, exist_ok=True)
        return d
    # desktop:
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(sys.executable)
        try:
            test = os.path.join(exe_dir, ".write_test")
            with open(test, "w") as f:
                f.write("x")
            os.remove(test)
            return exe_dir
        except Exception:
            d = os.path.join(os.path.expanduser("~"), ".holo")
            os.makedirs(d, exist_ok=True)
            return d
    try:
        test = os.path.join(BASE_DIR, ".write_test")
        with open(test, "w") as f:
            f.write("x")
        os.remove(test)
        return BASE_DIR
    except Exception:
        d = os.path.join(os.path.expanduser("~"), ".holo")
        os.makedirs(d, exist_ok=True)
        return d
