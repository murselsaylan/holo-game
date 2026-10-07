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


def _last_exit_check():
    """The last run ended while the game was in front (session.json still says running) - the system closed it
    (a native crash, out of memory, a watchdog) without a Python traceback. Write exit_last.log with where the game
    was and the end of its log; the next server contact sends it (online._send_reports)."""
    try:
        import json
        import os
        import paths
        d = paths.user_dir()
        sess = os.path.join(d, "session.json")
        if not os.path.isfile(sess):
            return
        with open(sess, encoding="utf-8") as f:
            info = json.load(f)
        os.remove(sess)
        if not info.get("running"):
            return
        tail = ""
        log = os.path.join(d, "holo.log")
        if os.path.isfile(log):
            with open(log, encoding="utf-8", errors="replace") as f:
                tail = f.read()[-6000:]
        with open(os.path.join(d, "exit_last.log"), "w", encoding="utf-8") as f:
            f.write("unexpected end of the last run (closed by the system while in front)\n")
            f.write(json.dumps(info) + "\n--- end of holo.log ---\n" + tail)
    except Exception:
        pass


if __name__ == "__main__":
    # iOS (pygame-ios) runs this file as the package's __main__: the game's modules sit next to it, not on sys.path
    import os
    _here = os.path.dirname(os.path.abspath(__file__))
    if _here not in sys.path:
        sys.path.insert(0, _here)
    _last_exit_check()
    if sys.platform == "ios":                    # iOS does not show print() anywhere: keep it in the save folder
        try:
            import paths
            sys.stdout = sys.stderr = open(os.path.join(paths.user_dir(), "holo.log"), "w", encoding="utf-8", buffering=1)
        except Exception:
            pass
    try:
        # a native crash (segfault in a C library) leaves no Python traceback: faulthandler writes every thread's
        # Python stack to fault.log at that moment; the next start sends it to the developer (online.report_fault)
        import faulthandler
        import paths
        _now = os.path.join(paths.user_dir(), "fault_now.log")
        if os.path.isfile(_now) and os.path.getsize(_now) > 0:              # the last run crashed: keep its stack
            os.replace(_now, os.path.join(paths.user_dir(), "fault_last.log"))
        _fault = open(_now, "w", encoding="utf-8")
        faulthandler.enable(file=_fault, all_threads=True)
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
