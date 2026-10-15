"""Frame-time diagnostics (1.0.8): how smooth the game really runs on the player's phone.

Every frame the main loop hands over how long the update, the drawing and the flip took. Per screen it keeps the
frame count, the average and how many frames ran slow (over 20 / 33 / 50 ms), and the 12 slowest frames with their
split and what else happened in them (a save written, network results handled, a level loaded - see mark()).
Once the game has run a while in front (and again later at most every 5 minutes) a short report goes to the server
(/api/report, kind "perf") with the phone model - nothing else about the player. The developer reads it to find
what stutters on real phones; the game never shows it.
"""
import json
import time

SLOW = (20.0, 33.0, 50.0)
FIRST_AFTER = 90.0                # seconds in front before the first report
EVERY = 300.0                     # then at most one per this many seconds

_marks = []                       # (name, ms) of main-thread events in the current frame
_busy = {}                        # background job -> how many are running now
_seen = set()                     # background jobs that ran at some point during the current frame
_built = 0                        # cached surfaces made during the current frame (render_cache.SurfaceCache.put)


def mark(name, ms=0.0):
    """Something notable happened on the main thread this frame (shown with a slow frame)."""
    if len(_marks) < 8:
        _marks.append((name, round(ms, 1)))


def busy(name, on):
    """A background thread starts / ends a job. A slow frame lists the jobs that ran meanwhile: Python runs one
    thread at a time, so a thread busy in Python or in a C call that keeps the lock makes the game loop wait."""
    if on:
        _busy[name] = _busy.get(name, 0) + 1
        _seen.add(name)
    else:
        _busy[name] = max(0, _busy.get(name, 0) - 1)


def built():
    global _built
    _built += 1


_gc_t0 = 0.0


def _gc_cb(phase, info):
    """Python's garbage collector pauses the game while it runs: collections over 2 ms are marked."""
    global _gc_t0
    if phase == "start":
        _gc_t0 = time.perf_counter()
    else:
        ms = (time.perf_counter() - _gc_t0) * 1000.0
        if ms >= 2.0:
            mark(f"gc{info.get('generation', '?')}", ms)


def watch_gc():
    import gc
    if _gc_cb not in gc.callbacks:
        gc.callbacks.append(_gc_cb)


def bench(frame):
    """One-time timings of the drawing operations the game leans on (ms), measured on the player's phone at start-up:
    the perf report then shows which operation is slow on that phone compared with the PC (PC values in comments)."""
    import pygame
    out = {}

    def run(name, fn, n=1):
        t0 = time.perf_counter()
        for _ in range(n):
            fn()
        out[name] = round((time.perf_counter() - t0) * 1000.0 / n, 2)

    try:
        w, h = frame.get_size()
        work = frame.copy()
        opaque = frame.copy()
        veil = pygame.Surface((w, h))
        veil.fill((5, 8, 15))
        veil.set_alpha(215)
        alpha = pygame.Surface((w, h), pygame.SRCALPHA)
        alpha.fill((20, 30, 40, 120))
        small = pygame.Surface((664, 34), pygame.SRCALPHA)
        small.fill((40, 60, 90, 200))
        font = pygame.font.Font(None, 40)
        big = pygame.Surface((400, 400), pygame.SRCALPHA)
        run("blit_full_opaque", lambda: work.blit(opaque, (0, 0)), 3)          # PC ~0.3
        run("blit_full_veil", lambda: work.blit(veil, (0, 0)), 3)               # PC ~2.1 (surface alpha)
        run("blit_full_srcalpha", lambda: work.blit(alpha, (0, 0)), 3)          # PC ~1.0 (per-pixel alpha)
        run("blit_small_premul", lambda: work.blit(small, (100, 100), special_flags=pygame.BLEND_PREMULTIPLIED), 20)
        run("blit_small_alpha", lambda: work.blit(small, (100, 100)), 20)
        run("copy_full", lambda: frame.copy(), 3)
        run("fill_full", lambda: work.fill((10, 12, 18)), 3)
        run("font_render", lambda: font.render("HOLO 1234 Deneme", True, (255, 255, 255)), 10)
        run("rect_rounded", lambda: pygame.draw.rect(work, (40, 60, 90), (50, 50, 600, 100), border_radius=26), 10)
        run("smoothscale", lambda: pygame.transform.smoothscale(big, (200, 200)), 3)
        run("convert_alpha", lambda: big.convert_alpha(), 3)
        out["masks_frame"] = [hex(m) for m in frame.get_masks()]
        out["masks_srcalpha"] = [hex(m) for m in alpha.get_masks()]
    except Exception as e:
        out["error"] = repr(e)[:120]
    return out


class Profiler:
    """cProfile on the player's phone, a few frames of the screens that run slow there (first visits only): the
    perf report lists where the time goes, function by function - what a PC can't show."""
    STATES = ("failed", "victory", "login", "menu", "skins", "playing")
    FRAMES = 30
    VISITS = 2

    def __init__(self):
        self.prof = None
        self.left = 0
        self.visits = {}
        self.stats = None
        self.state = None

    def frame_start(self, state):
        if self.prof is None and state != self.state:
            self.state = state
            if state in self.STATES and self.visits.get(state, 0) < self.VISITS:
                self.visits[state] = self.visits.get(state, 0) + 1
                import cProfile
                self.prof = cProfile.Profile()
                self.left = self.FRAMES
                self.prof.enable()
        elif self.prof is None:
            self.state = state

    def frame_end(self):
        if self.prof is None:
            return
        self.left -= 1
        if self.left > 0:
            return
        self.prof.disable()
        import pstats
        if self.stats is None:
            self.stats = pstats.Stats(self.prof)
        else:
            self.stats.add(self.prof)
        self.prof = None

    def top(self, n=24):
        """[[file:line func, calls, own ms, total ms], ...] by own time."""
        if self.stats is None:
            return []
        rows = []
        for (fn, line, name), (cc, nc, tt, ct, callers) in self.stats.stats.items():
            rows.append([f"{fn.replace(chr(92), '/').split('/')[-1]}:{line} {name}"[:60], nc, round(tt * 1000, 1),
                         round(ct * 1000, 1)])
        rows.sort(key=lambda r: -r[2])
        return rows[:n]


def cpu_ms():
    """CPU time of the calling (main) thread: a frame whose wall time is far above it was waiting, not working."""
    try:
        return time.thread_time() * 1000.0
    except Exception:
        return 0.0


class PerfStat:
    def __init__(self):
        self.states = {}
        self.slow = []
        self.front_s = 0.0
        self.sent_at = None
        self.frames = 0

    def frame(self, state, level, u_ms, d_ms, f_ms, dt, c_ms=0.0):
        global _marks, _seen, _built
        total = u_ms + d_ms
        st = self.states.get(state)
        if st is None:
            st = self.states[state] = [0, 0.0, 0, 0, 0, 0.0, 0.0, 0]   # n, sum ms, >20, >33, >50, max, sum cpu, builds
        st[0] += 1
        st[1] += total
        for k, lim in enumerate(SLOW):
            if total > lim:
                st[2 + k] += 1
        st[5] = max(st[5], total)
        st[6] += c_ms
        st[7] += _built
        if total > SLOW[1]:
            bg = sorted(_seen | {k for k, v in _busy.items() if v})
            self.slow.append((round(total, 1), state, level, round(u_ms, 1), round(d_ms - f_ms, 1), round(f_ms, 1),
                              list(_marks), round(c_ms, 1), _built, bg))
            self.slow.sort(key=lambda x: -x[0])
            del self.slow[20:]
        _marks = []
        _seen = set()
        _built = 0
        self.front_s += dt
        self.frames += 1

    def due(self):
        if self.frames < 300:
            return False
        if self.sent_at is None:
            return self.front_s >= FIRST_AFTER
        return self.front_s - self.sent_at >= EVERY

    def report(self, device, extra=None):
        """The report text (and the counters start over)."""
        states = {k: [v[0], round(v[1] / max(1, v[0]), 2), v[2], v[3], v[4], round(v[5], 1),
                      round(v[6] / max(1, v[0]), 2), v[7]]
                  for k, v in sorted(self.states.items(), key=lambda kv: -kv[1][0])}
        body = {"device": device, "front_s": round(self.front_s), "frames": self.frames,
                "states": states,
                "cols": ["frames", "avg_ms", ">20ms", ">33ms", ">50ms", "max_ms", "avg_cpu_ms", "builds"],
                "slowest": self.slow,
                "slow_cols": ["ms", "state", "level", "update", "draw", "flip", "marks", "cpu_ms", "builds", "bg"]}
        if extra:
            body.update(extra)
        self.sent_at = self.front_s
        self.states, self.slow, self.frames = {}, [], 0
        text = json.dumps(body, separators=(",", ":"))
        while len(text) > 11500 and body.get("profile"):
            body["profile"] = body["profile"][:-4]
            text = json.dumps(body, separators=(",", ":"))
        while len(text) > 11500 and body["slowest"]:
            body["slowest"] = body["slowest"][:-2]
            text = json.dumps(body, separators=(",", ":"))
        return text[:11500]


def device_info():
    """Phone model and OS (Android via jnius; elsewhere the platform)."""
    try:
        import paths
        if paths.is_android():
            from jnius import autoclass
            b = autoclass("android.os.Build")
            v = autoclass("android.os.Build$VERSION")
            return f"{b.MANUFACTURER} {b.MODEL} / Android {v.RELEASE} (API {v.SDK_INT})"
        import platform
        return f"{platform.system()} {platform.release()} {platform.machine()}"
    except Exception as e:
        return f"unknown ({e.__class__.__name__})"


def now_ms():
    return time.perf_counter() * 1000.0
