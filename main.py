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


_exit_cb = None


def _install_exit_traps():
    """iOS 'black box': if anything ends the process with exit() (native code - iOS keeps no crash report for that)
    or a termination signal, every thread's Python stack is written to exit_trace.log first; the next start sends it.
    The game itself leaves with os._exit, which skips these C atexit hooks, so only unexpected exits are recorded."""
    import ctypes
    import os
    import signal
    import threading
    import paths
    path = os.path.join(paths.user_dir(), "exit_trace.log")

    def dump(why):
        try:
            frames = sys._current_frames()
            with open(path, "w", encoding="utf-8") as f:
                f.write(f"{why}  ({time.strftime('%Y-%m-%d %H:%M:%S')})\n")
                for th in threading.enumerate():
                    f.write(f"--- thread {th.name}\n")
                    fr = frames.get(th.ident)
                    if fr is not None:
                        f.write("".join(traceback.format_stack(fr)))
        except Exception:
            pass

    global _exit_cb
    _exit_cb = ctypes.CFUNCTYPE(None)(lambda: dump("exit() called while the game was running"))
    ctypes.CDLL(None).atexit(_exit_cb)
    for sig in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT, signal.SIGQUIT):
        try:
            signal.signal(sig, lambda s, f: (dump(f"signal {s}"), os._exit(0)))
        except Exception:
            pass
    print("exit traps on")


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
        ios_quit = sys.platform == "ios" and info.get("quit")
        if not info.get("running") and not ios_quit:
            return
        tail = ""
        log = os.path.join(d, "holo.log")
        if os.path.isfile(log):
            with open(log, encoding="utf-8", errors="replace") as f:
                tail = f.read()[-9000:]
        with open(os.path.join(d, "exit_last.log"), "w", encoding="utf-8") as f:
            f.write("the last run quit by itself (iOS)\n" if ios_quit else
                    "unexpected end of the last run (closed by the system while in front)\n")
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
        print("faulthandler on")
    except Exception as e:
        print("faulthandler unavailable:", e)
    if sys.platform == "ios":
        try:
            _install_exit_traps()
        except Exception as e:
            print("exit traps unavailable:", e)
    try:
        from holo import HoloGame
        HoloGame().run()
    except SystemExit:
        raise
    except BaseException as e:               # write the reason next to the save file so it can be sent to the developer
        _log_crash(e)
        if sys.platform == "ios":                # leave without the exit trap (the reason is in crash.log)
            sys.stdout.flush()
            os._exit(1)
        raise
