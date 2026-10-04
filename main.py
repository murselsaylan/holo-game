"""Entry point (desktop: `python main.py`; Android/python-for-android runs this file)."""
import sys
import time
import traceback


def _log_crash(exc):
    try:
        import paths
        import os
        path = os.path.join(paths.user_dir(), "crash.log")
        with open(path, "a", encoding="utf-8") as f:
            f.write("\n=== " + time.strftime("%Y-%m-%d %H:%M:%S") + " ===\n")
            f.write("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))
    except Exception:
        pass


if __name__ == "__main__":
    # iOS (pygame-ios) runs this file as the package's __main__: the game's modules sit next to it, not on sys.path
    import os
    _here = os.path.dirname(os.path.abspath(__file__))
    if _here not in sys.path:
        sys.path.insert(0, _here)
    if sys.platform == "ios":                    # iOS does not show print() anywhere: keep it in the save folder
        try:
            import paths
            sys.stdout = sys.stderr = open(os.path.join(paths.user_dir(), "holo.log"), "w", encoding="utf-8", buffering=1)
        except Exception:
            pass
    try:
        from holo import HoloGame
        HoloGame().run()
    except SystemExit:
        raise
    except BaseException as e:               # write the reason next to the save file so it can be sent to the developer
        _log_crash(e)
        raise
