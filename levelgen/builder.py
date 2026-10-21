"""Level construction helpers: carve free space out of the arena and derive wall rects."""
import os
import sys
import math

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sim import ARENA_W  # noqa: E402


def _r(v):
    return int(round(v))


class Layout:
    """Free space = union of rects. Walls = arena minus free space (+ explicit pillars)."""

    def __init__(self, height=1470.0):
        self.H = float(height)
        self.free = []          # (x, y, w, h)
        self.pillars = []       # explicit wall rects added on top
        self.route = []         # waypoints polyline (for progress)
        self.slots = None       # optional family specific hazard sites (x, y, horizontal, span)
        self.data = {
            "reverse_walls": [], "moving_walls": [], "lasers": [], "spinners": [], "circles": [],
            "growth_zones": [], "shrink_zones": [], "boost_pads": [], "slow_zones": [], "stretch_zones": [], "shields": [], "stars": [],
            "breakables": [], "chasers": [], "barriers": [],
        }

    # ---- free space -----------------------------------------------------------
    def rect(self, x, y, w, h):
        self.free.append((x, y, w, h))

    def rect_c(self, cx, cy, w, h):
        self.free.append((cx - w / 2.0, cy - h / 2.0, w, h))

    def leg(self, p1, p2, width):
        (x1, y1), (x2, y2) = p1, p2
        if abs(x1 - x2) < 1e-6:                      # vertical
            self.rect(x1 - width / 2.0, min(y1, y2) - width / 2.0, width, abs(y2 - y1) + width)
        else:                                          # horizontal
            self.rect(min(x1, x2) - width / 2.0, y1 - width / 2.0, abs(x2 - x1) + width, width)

    def pillar(self, x, y, w, h):
        self.pillars.append((x, y, w, h))

    # ---- walls from complement ----------------------------------------------------
    def walls(self):
        xs = {0.0, ARENA_W}
        ys = {0.0, self.H}
        free = []
        for (x, y, w, h) in self.free:
            x0, y0 = max(0.0, x), max(0.0, y)
            x1, y1 = min(ARENA_W, x + w), min(self.H, y + h)
            if x1 - x0 > 0 and y1 - y0 > 0:
                free.append((x0, y0, x1, y1))
                xs.update((x0, x1))
                ys.update((y0, y1))
        xs = sorted(xs)
        ys = sorted(ys)
        # cell grid on compressed coordinates
        rows = []
        for j in range(len(ys) - 1):
            cy = (ys[j] + ys[j + 1]) / 2.0
            row = []
            for i in range(len(xs) - 1):
                cx = (xs[i] + xs[i + 1]) / 2.0
                is_free = any(f[0] <= cx <= f[2] and f[1] <= cy <= f[3] for f in free)
                row.append(not is_free)
            rows.append(row)
        # horizontal run merge, then vertical merge of identical runs
        active = {}
        out = []
        for j, row in enumerate(rows):
            runs = []
            i = 0
            while i < len(row):
                if row[i]:
                    k = i
                    while k + 1 < len(row) and row[k + 1]:
                        k += 1
                    runs.append((i, k))
                    i = k + 1
                else:
                    i += 1
            new_active = {}
            for run in runs:
                if run in active:
                    new_active[run] = active.pop(run)
                else:
                    new_active[run] = j
            for run, j0 in active.items():
                out.append((xs[run[0]], ys[j0], xs[run[1] + 1], ys[j]))
            active = new_active
        for run, j0 in active.items():
            out.append((xs[run[0]], ys[j0], xs[run[1] + 1], ys[len(ys) - 1]))
        walls = [[_r(a), _r(b), _r(c - a), _r(d - b)] for (a, b, c, d) in out if c - a >= 1 and d - b >= 1]
        walls += [[_r(x), _r(y), _r(w), _r(h)] for (x, y, w, h) in self.pillars]
        return walls

    # ---- hazard helpers ---------------------------------------------------------------
    def add(self, key, item):
        self.data[key].append([_r(v) if isinstance(v, (int,)) else round(float(v), 2) for v in item])

    def to_level(self, lvl_id, title, start, end, speed, ramp=0.15):
        d = {
            "id": lvl_id, "title": title, "height": _r(self.H),
            "start": [_r(start[0]), _r(start[1])], "end": [_r(end[0]), _r(end[1])],
            "speed": round(speed, 3), "ramp": ramp,
            "walls": self.walls(),
            "waypoints": [[_r(x), _r(y)] for (x, y) in self.route],
        }
        d.update({k: v for k, v in self.data.items()})
        return d


def dedupe_route(pts):
    out = []
    for p in pts:
        if not out or abs(out[-1][0] - p[0]) > 1e-6 or abs(out[-1][1] - p[1]) > 1e-6:
            out.append(p)
    return out


def carve_route(layout, pts, width, room=None, widths=None):
    """Carve corridors along the Manhattan polyline `pts` and rooms at the joints. `widths` = optional width per leg."""
    pts = dedupe_route(pts)
    if not widths or len(widths) != len(pts) - 1:
        widths = [width] * (len(pts) - 1)
    for a, b, w in zip(pts, pts[1:], widths):
        layout.leg(a, b, w)
    layout.leg_widths = list(widths)
    if room:
        for i, p in enumerate(pts[1:-1], 1):
            layout.rect_c(p[0], p[1], room, room)
    layout.route = pts
    return pts


def leg_points(pts, frac_list):
    """Points at given path-length fractions along polyline."""
    segs = []
    total = 0.0
    for a, b in zip(pts, pts[1:]):
        l = math.hypot(b[0] - a[0], b[1] - a[1])
        segs.append((a, b, l))
        total += l
    out = []
    for f in frac_list:
        target = f * total
        acc = 0.0
        for a, b, l in segs:
            if acc + l >= target or (a, b, l) is segs[-1]:
                tt = 0.0 if l == 0 else (target - acc) / l
                horiz = abs(a[1] - b[1]) < 1e-6
                out.append(((a[0] + (b[0] - a[0]) * tt, a[1] + (b[1] - a[1]) * tt), horiz))
                break
            acc += l
    return out
