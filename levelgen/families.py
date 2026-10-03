"""Level families: parametric layouts driven by one `tight` knob (0 = forgiving, 1 = brutal).

Every family returns (layout, start, end).  Hazards are attached afterwards by `hazards.apply`,
using `layout.slots` (family specific) or straight legs of `layout.route`.
"""
import os
import sys
import math

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sim import ARENA_W  # noqa: E402
from levelgen.builder import Layout, carve_route, dedupe_route  # noqa: E402


def lerp(a, b, t):
    return a + (b - a) * t


class Ctx:
    def __init__(self, lvl_id, tight, rng, height=1470.0):
        self.id = lvl_id
        self.H = float(height)
        self.tight = tight
        self.rng = rng
        self.W = lerp(340.0, 152.0, tight ** 0.9)        # corridor width
        self.room = self.W                                 # corner rooms are just the W x W junction
        self.gap = lerp(330.0, 140.0, tight ** 0.9)       # gate / door gap width
        self.start_room = min(300.0, self.W + 30.0)
        self.goal_room = min(230.0, self.W + 30.0)
        self.speed = 1.1                                   # level speed (set by gen.build); scales chaser walls
        self.style = {"sp": 1.0, "lp": 1.0, "sz": 1.0}  # per-level hazard style (speed / laser period / size multipliers)
        self.gk = 0                                        # gate strictness level (raised when a gate proves optional)


def margin_of(ctx):
    return max(ctx.W / 2.0 + 30.0, 150.0)


def _fit(span, W, want, min_wall=46.0):
    fit = int(span // (W + min_wall)) + 1
    return max(2, min(want, fit))


# ---------------------------------------------------------------------------------
def custom(ctx, pts, extra_room=0.0, widths=None):
    L = Layout(ctx.H)
    pts = dedupe_route(list(pts))
    carve_route(L, pts, ctx.W, ctx.W + extra_room if extra_room else None, widths)
    L.rect_c(pts[0][0], pts[0][1], ctx.start_room, ctx.start_room)
    L.rect_c(pts[-1][0], pts[-1][1], ctx.goal_room, ctx.goal_room)
    return L, pts[0], pts[-1]


def snake_h(ctx, lanes=4, flip=False, start_left=True):
    m = margin_of(ctx)
    xl, xr = m, ARENA_W - m
    yt = m
    yb = ctx.H - m
    lanes = _fit(yb - yt, ctx.W, lanes)
    ys = [yt + i * (yb - yt) / (lanes - 1) for i in range(lanes)]
    pts = []
    ltr = start_left
    for y in ys:
        a, b = (xl, xr) if ltr else (xr, xl)
        pts += [(a, y), (b, y)]
        ltr = not ltr
    if flip:
        pts = [(x, ctx.H - y) for x, y in pts]
    return custom(ctx, pts)


def snake_v(ctx, cols=3, flip=False, start_bottom=True):
    m = margin_of(ctx)
    xl, xr = m, ARENA_W - m
    cols = _fit(xr - xl, ctx.W, cols)
    xs = [xl + i * (xr - xl) / (cols - 1) for i in range(cols)]
    yt, yb = m, ctx.H - m
    pts = []
    up = start_bottom
    for x in xs:
        a, b = (yb, yt) if up else (yt, yb)
        pts += [(x, a), (x, b)]
        up = not up
    if flip:
        pts = [(ARENA_W - x, y) for x, y in pts]
    return custom(ctx, pts)


def zigzag(ctx, cols=3, flip=False, start_bottom=True, jag=0.3):
    """Like snake_v, but the turns happen at uneven heights (long straight legs of different lengths)."""
    m = margin_of(ctx)
    xl, xr = m, ARENA_W - m
    cols = _fit(xr - xl, ctx.W, cols)
    xs = [xl + i * (xr - xl) / (cols - 1) for i in range(cols)]
    yt, yb = m, ctx.H - m
    span = yb - yt
    up = start_bottom
    y_cur = yb if up else yt
    pts = []
    for ci, x in enumerate(xs):
        if ci == cols - 1:
            b = yt if up else yb
        else:
            short = ctx.rng.uniform(0.0, jag) * span
            b = (yt + short) if up else (yb - short)
        pts += [(x, y_cur), (x, b)]
        y_cur = b
        up = not up
    if flip:
        pts = [(ARENA_W - x, y) for x, y in pts]
    return custom(ctx, pts)


def spiral(ctx, turns=2, clockwise=True):
    m = margin_of(ctx)
    s = ctx.W + 46.0
    left, right, top, bottom = m, ARENA_W - m, m, ctx.H - m
    x, y = left, top
    pts = [(x, y)]
    legs, maxlegs = 0, 4 * turns + 1
    while legs < maxlegs:
        x = right
        pts.append((x, y))
        top += s
        legs += 1
        if legs >= maxlegs or bottom - top < 200:
            break
        y = bottom
        pts.append((x, y))
        right -= s
        legs += 1
        if legs >= maxlegs or right - left < 200:
            break
        x = left
        pts.append((x, y))
        bottom -= s
        legs += 1
        if legs >= maxlegs or bottom - top < 200:
            break
        y = top
        pts.append((x, y))
        left += s
        legs += 1
        if right - left < 200:
            break
    pts = dedupe_route(pts)
    if not clockwise:
        pts = [(ARENA_W - px, py) for px, py in pts]
    return custom(ctx, pts)


def maze(ctx, length=10, flip=False, straight=0.0, wvar=0.0, min_turns=6):
    """Random self-avoiding walk on a grid whose pitch keeps parallel corridors 60px apart."""
    rng = ctx.rng
    W = ctx.W
    m = margin_of(ctx)
    pitch = W + 62.0
    cols = max(2, int((ARENA_W - 2 * m) // pitch) + 1)
    rows = max(3, int((ctx.H - 2 * m) // pitch) + 1)
    xs = [m + i * (ARENA_W - 2 * m) / (cols - 1) for i in range(cols)]
    ys = [m + j * (ctx.H - 2 * m) / (rows - 1) for j in range(rows)]
    best = None
    for _ in range(400):
        cur = (rng.randrange(cols), rows - 1)
        path = [cur]
        seen = {cur}
        last_dir = None
        while len(path) < length + 1:
            opts = []
            for d in ((1, 0), (-1, 0), (0, -1), (0, 1)):
                n = (cur[0] + d[0], cur[1] + d[1])
                if 0 <= n[0] < cols and 0 <= n[1] < rows and n not in seen:
                    # avoid squeezing: do not touch a visited node sideways except the previous one
                    opts.append((d, n))
            if not opts:
                break
            # prefer turning and moving towards the top so the route uses the whole arena
            def w(o):
                d, n = o
                wgt = 1.0
                if last_dir is not None and d != last_dir:
                    wgt += 1.4 * (1.0 - straight)
                if last_dir is not None and d == last_dir:
                    wgt += 2.6 * straight
                if d == (0, -1):
                    wgt += 0.8
                return wgt
            tot = sum(w(o) for o in opts)
            r = rng.random() * tot
            for o in opts:
                r -= w(o)
                if r <= 0:
                    break
            last_dir = o[0]
            cur = o[1]
            path.append(cur)
            seen.add(cur)
        turns = sum(1 for a, b, c in zip(path, path[1:], path[2:]) if (b[0] - a[0], b[1] - a[1]) != (c[0] - b[0], c[1] - b[1]))
        score = len(path) + 0.3 * turns
        if len(path) < length + 1:
            score -= 50.0
        if turns < min_turns:
            score -= 20.0
        if best is None or score > best[0]:
            best = (score, path)
        if len(path) >= length + 1 and turns >= min_turns:
            best = (score, path)
            break
    path = best[1]
    pts = [(xs[c], ys[r]) for c, r in path]
    # merge collinear points
    out = [pts[0]]
    for a, b, c in zip(pts, pts[1:], pts[2:]):
        if (abs(a[0] - b[0]) < 1 and abs(b[0] - c[0]) < 1) or (abs(a[1] - b[1]) < 1 and abs(b[1] - c[1]) < 1):
            continue
        out.append(b)
    out.append(pts[-1])
    if flip:
        out = [(ARENA_W - x, y) for x, y in out]
    widths = None
    if wvar > 0:
        widths = [round(W * (1.0 - wvar * rng.choice((0.0, 0.0, 0.5, 1.0))), 1) for _ in range(len(out) - 1)]
    L, s, e = custom(ctx, out, widths=widths)
    L.rect_c(s[0], s[1], min(ctx.start_room, W + 40), min(ctx.start_room, W + 40))
    L.relaxed = True
    return L, s, e


def _door_gate(L, kind, cx, cy, w, thick, before):
    """Power-up door in an open-field divider: `before` = signed distance (along y) from the door to its pickup."""
    rect = [cx - w / 2.0, cy - thick / 2.0, w, thick]
    if kind == "ggrow":
        L.add("breakables", rect)
        L.add("growth_zones", [cx, cy + before, 92.0])
    elif kind == "gshield":
        L.pillar(*rect)
        L.add("barriers", rect)
        L.add("shields", [cx, cy + before])
    elif kind == "gshrink":
        L.add("shrink_zones", [cx, cy + before, 92.0])
    else:
        return
    L.placed_gates.append(kind)


ARENA_KINDS = ("slider", "laser", "spin", "bars", "pillars", "shutter", "bounce")


def arena(ctx, rows=6, kinds=ARENA_KINDS, start_bottom=True):
    """Open arena crossed by rows of different obstacles: sliding doors, full-width lasers, spinners, double-gap walls,
    pillar forests, camera shutters. Nothing to follow - the player reads each row and picks the moment."""
    rng = ctx.rng
    L = Layout(ctx.H)
    L.rect(0, 0, ARENA_W, ctx.H)
    st = getattr(ctx, "style", {})
    top, bot = 330.0, ctx.H - 330.0
    rows = max(2, min(rows, int((ctx.H - 660) // 430) + 1))          # rows >= 430 px apart: the pair needs a safe pause between them
    ys = [top + (bot - top) * k / (rows - 1) for k in range(rows)]
    if start_bottom:
        ys = ys[::-1]
    sy, ey = (ctx.H - 190.0, 190.0) if start_bottom else (190.0, ctx.H - 190.0)
    kinds = list(kinds)
    seq = []
    prev = None
    for y in ys:
        k = rng.choice([x for x in kinds if x != prev] or kinds)
        prev = k
        seq.append(k)
        g = lerp(300.0, 215.0, ctx.tight)
        ph = rng.uniform(0, 6.28)
        if k == "slider":
            sp = lerp(0.6, 1.1, ctx.tight) * st.get("sp", 1.0)
            L.add("moving_walls", [ARENA_W / 2 - (ARENA_W - g) / 2, y - 22, ARENA_W - g, 44, g / 2 - 8, 0.0, sp, ph])
        elif k == "laser":
            L.add("lasers", [6.0, y, ARENA_W - 6.0, y, lerp(4.2, 2.8, ctx.tight) * st.get("lp", 1.0), lerp(0.30, 0.44, ctx.tight), ph])
        elif k == "spin":
            hl = min(58.0, lerp(38.0, 50.0, ctx.tight) * st.get("sz", 1.0))
            for j, x in enumerate((300.0, 600.0)):
                L.add("spinners", [x, y, hl, (1 if j % 2 == 0 else -1) * lerp(0.6, 1.0, ctx.tight) * st.get("sp", 1.0), ph + j * 1.9, 10.0])
        elif k == "bars":
            T = 46.0
            gap = max(g, 210.0)
            centres = sorted(rng.sample([170.0, 330.0, 450.0, 570.0, 730.0], 2))
            if centres[1] - centres[0] < 220.0:
                centres = [180.0, 720.0]
            x0 = 0.0
            for c in centres:
                L.pillar(x0, y - T / 2, c - gap / 2.0 - x0, T)
                x0 = c + gap / 2.0
            L.pillar(x0, y - T / 2, ARENA_W - x0, T)
        elif k == "bounce":
            # soft walls: the swinging orb is thrown back (and kicked forward) instead of dying - a flipper row
            T = 46.0
            gap = max(g, 200.0)
            centres = sorted(rng.sample([200.0, 350.0, 450.0, 550.0, 700.0], 2))
            if centres[1] - centres[0] < 230.0:
                centres = [200.0, 700.0]
            x0 = 0.0
            for c in centres:
                if c - gap / 2.0 - x0 > 20:
                    L.add("reverse_walls", [x0, y - T / 2, c - gap / 2.0 - x0, T])
                x0 = c + gap / 2.0
            L.add("reverse_walls", [x0, y - T / 2, ARENA_W - x0, T])
        elif k == "pillars":
            r = lerp(30.0, 40.0, ctx.tight) * st.get("sz", 1.0)
            step = g + 2 * r
            off = rng.uniform(0, step)
            x = -r + off
            while x < ARENA_W + r:
                if x > -r:
                    L.data["circles"].append([round(x, 1), round(y, 1), round(r, 1)])
                x += step
        elif k == "shutter":
            H_ = __import__("levelgen.hazards", fromlist=["shutter"])
            H_.shutter(L, ctx, ARENA_W / 2.0, y, False, float(ARENA_W), phase=ph)
    L.route = [(450.0, sy), (450.0, ey)]
    L.slots = []
    L.sig = tuple(seq)
    return L, (450.0, sy), (450.0, ey)


def _leg_rect(a, b, w):
    """(x0, y0, x1, y1) of a corridor leg including its end caps (matches Layout.leg)."""
    (x1, y1), (x2, y2) = a, b
    if abs(x1 - x2) < 1e-6:
        return (x1 - w / 2.0, min(y1, y2) - w / 2.0, x1 + w / 2.0, max(y1, y2) + w / 2.0)
    return (min(x1, x2) - w / 2.0, y1 - w / 2.0, max(x1, x2) + w / 2.0, y1 + w / 2.0)


def _hit(r1, r2, pad):
    return not (r1[2] + pad <= r2[0] or r2[2] + pad <= r1[0] or r1[3] + pad <= r2[1] or r2[3] + pad <= r1[1])


def wander(ctx, legs=8, long_bias=0.5, flip=False, wvar=0.0, reach=0.7, start_x=None, need=None):
    """Free-form Manhattan route: legs of random length at random positions (no grid), kept apart by a wall of >= 46 px.
    Every call with another seed gives a different shape; `long_bias` favours long straight legs (room for power-up gates)."""
    rng = ctx.rng
    W = ctx.W
    hw = W / 2.0
    xmin, xmax = hw + 44.0, ARENA_W - hw - 44.0
    ymin, ymax = hw + 70.0, ctx.H - hw - 70.0
    lmin = W + 74.0
    best = None
    need = sorted(need or [], reverse=True)
    for attempt in range(1500 if need else 600):
        x = start_x if start_x is not None else rng.uniform(xmin, xmax)
        y = ymax
        pts = [(x, y)]
        rects = []
        orient = "V"
        ok = True
        for k in range(legs):
            placed = False
            for _ in range(60):
                if orient == "V":
                    up = y - ymin
                    dn = ymax - y
                    if up < lmin and dn < lmin:
                        break
                    d = -1 if (rng.random() * (up + dn) < up * 1.6 / 1.6 and up >= lmin) or dn < lmin else 1
                    if k == 0:
                        d = -1
                    avail = (up if d < 0 else dn)
                    if avail < lmin:
                        continue
                    L = lmin + (avail - lmin) * (rng.random() ** (1.0 - 0.85 * long_bias))
                    nx, ny = x, y + d * L
                else:
                    lf = x - xmin
                    rt = xmax - x
                    if lf < lmin and rt < lmin:
                        break
                    d = -1 if (rng.random() * (lf + rt) < lf and lf >= lmin) or rt < lmin else 1
                    avail = (lf if d < 0 else rt)
                    if avail < lmin:
                        continue
                    L = lmin + (avail - lmin) * (rng.random() ** (1.0 - 0.5 * long_bias))
                    nx, ny = x + d * L, y
                r = _leg_rect((x, y), (nx, ny), W)
                if any(_hit(r, rects[j], 46.0) for j in range(len(rects) - 1)):
                    continue
                rects.append(r)
                pts.append((nx, ny))
                x, y = nx, ny
                placed = True
                break
            if not placed:
                ok = k >= 3
                break
            orient = "H" if orient == "V" else "V"
        if not ok or len(pts) < 4:
            continue
        lens = sorted((abs(a[0] - b[0]) + abs(a[1] - b[1]) for a, b in zip(pts, pts[1:])), reverse=True)
        need_ok = all(j < len(lens) and lens[j] >= nv for j, nv in enumerate(need))
        if need and not need_ok:
            if best is None:
                best = (-999.0, pts)
            continue
        span = (ymax - min(p[1] for p in pts)) / max(1.0, ymax - ymin)
        length = sum(abs(a[0] - b[0]) + abs(a[1] - b[1]) for a, b in zip(pts, pts[1:]))
        score = len(pts) * 2.0 + min(span, reach) * 40.0 + length / 400.0
        if span < reach * 0.8:
            score -= 30.0
        if best is None or score > best[0] or best[0] == -999.0:
            best = (score, pts)
        if len(pts) >= legs + 1 and span >= reach:
            best = (score, pts)
            break
    pts = best[1] if best else [(450.0, ymax), (450.0, ymin)]
    if flip:
        pts = [(ARENA_W - px, py) for px, py in pts]
    widths = None
    if wvar > 0:
        widths = [round(W * (1.0 - wvar * rng.choice((0.0, 0.0, 0.5, 1.0))), 1) for _ in range(len(pts) - 1)]
    L, s, e = custom(ctx, pts, widths=widths)
    L.rect_c(s[0], s[1], min(ctx.start_room, W + 40), min(ctx.start_room, W + 40))
    L.relaxed = True
    return L, s, e


def gates(ctx, n=2, start_bottom=True, door_kinds=None):
    """Open field crossed by n full-width barriers, each with one gap (n <= 2: the pair needs room to swing)."""
    rng = ctx.rng
    n = max(1, min(n, int((ctx.H - 660) // 350) - 1))     # barrier spacing >= 350: the pair must be able to swing
    L = Layout(ctx.H)
    L.rect(0, 0, ARENA_W, ctx.H)
    T = 52.0
    top, bot = 330.0, ctx.H - 330.0
    ys = [top + (bot - top) * (i + 1) / (n + 1) for i in range(n)]
    gap0 = ctx.gap
    side = rng.choice([-1, 1])
    gx = []
    L.placed_gates = []
    for k, y in enumerate(ys):
        kind = door_kinds[k % len(door_kinds)] if door_kinds else None
        gap = gap0
        if kind == "gshrink":
            gap = max(92.0, min(gap0, 122.0 - 6.0 * getattr(ctx, "gk", 0)))
        cx = 450.0 + side * rng.uniform(170, 230)
        cx = max(gap / 2.0 + 70, min(ARENA_W - gap / 2.0 - 70, cx))
        gx.append(cx)
        L.pillar(0, y - T / 2, cx - gap / 2.0, T)
        L.pillar(cx + gap / 2.0, y - T / 2, ARENA_W - (cx + gap / 2.0), T)
        side = -side
        if kind:
            _door_gate(L, kind, cx, y, gap, T, (T / 2.0 + 150.0) * (1 if start_bottom else -1))
    sy, ey = (ctx.H - 200.0, 200.0) if start_bottom else (200.0, ctx.H - 200.0)
    pts = [(450.0, sy)]
    seq = list(zip(gx, ys))
    if start_bottom:
        seq = seq[::-1]
    for cx, y in seq:
        pts.append((cx, y + (T if start_bottom else -T)))
        pts.append((cx, y - (T if start_bottom else -T)))
    pts.append((450.0, ey))
    L.route = dedupe_route(pts)
    # hazard sites: the open lanes between barriers
    L.slots = []
    edges = [top - 20.0] + ys + [bot + 20.0]
    for a, b in zip(edges, edges[1:]):
        L.slots.append((450.0, (a + b) / 2.0, True, 460.0))
    return L, (450.0, sy), (450.0, ey)


def mines(ctx, rows=4, start_bottom=True):
    """Open arena; staggered rows of deadly mines with a single wide gap per row."""
    rng = ctx.rng
    L = Layout(ctx.H)
    L.rect(0, 0, ARENA_W, ctx.H)
    r = lerp(30.0, 38.0, ctx.tight)
    gap = lerp(250.0, 130.0, ctx.tight ** 0.9)
    top, bot = 330.0, ctx.H - 330.0
    rows = max(2, min(rows, int((ctx.H - 700) // 300) + 1))
    ys = [top + (bot - top) * i / (rows - 1) for i in range(rows)]
    sy, ey = (ctx.H - 190.0, 190.0) if start_bottom else (190.0, ctx.H - 190.0)
    pts = [(450.0, sy)]
    seq = ys[::-1] if start_bottom else ys
    side = rng.choice([-1, 1])
    step = gap + 2 * r
    L.slots = []
    for k, y in enumerate(seq):
        way = 450.0 + side * rng.uniform(150, 260)
        side = -side
        # mines to the left and right of the way, spaced by `step`
        x = way - (gap * 0.5 + r + 0.1)
        while x > -r:
            L.data["circles"].append([round(x, 1), round(y, 1), round(r, 1)])
            x -= step
        x = way + (gap * 0.5 + r + 0.1)
        while x < ARENA_W + r:
            L.data["circles"].append([round(x, 1), round(y, 1), round(r, 1)])
            x += step
        pts.append((way, y))
        if k < len(seq) - 1:
            L.slots.append((450.0, (y + seq[k + 1]) / 2.0, True, 460.0))
    pts.append((450.0, ey))
    L.route = dedupe_route(pts)
    return L, (450.0, sy), (450.0, ey)


def chambers(ctx, n=3, start_bottom=True, door_kinds=None):
    """Vertical chain of rooms joined by short doors alternating left/right."""
    rng = ctx.rng
    n = max(2, n)
    L = Layout(ctx.H)
    room_w = rng.uniform(560.0, 760.0)
    room_h = lerp(430.0, 340.0, ctx.tight) * rng.uniform(0.9, 1.15)
    neck = rng.uniform(70.0, 120.0)
    total = n * room_h + (n - 1) * neck
    ctx.H = max(ctx.H, total + 300.0)
    L.H = ctx.H
    y0 = (ctx.H - total) / 2.0
    door_w = min(ctx.gap * 0.85, ctx.W + 20)
    cx = 450.0
    rooms = []
    for i in range(n):
        ry = y0 + i * (room_h + neck)
        L.rect(cx - room_w / 2, ry, room_w, room_h)
        rooms.append((cx, ry + room_h / 2.0, ry, ry + room_h))
    doors = []
    side = rng.choice([-1, 1])
    L.placed_gates = []
    for i in range(n - 1):
        kind = door_kinds[i % len(door_kinds)] if door_kinds else None
        dw = door_w
        if kind == "gshrink":
            dw = max(92.0, min(door_w, 122.0 - 6.0 * getattr(ctx, "gk", 0)))
        dx = cx + side * rng.uniform(150.0, room_w / 2.0 - door_w / 2.0 - 30.0)
        y_a = rooms[i][3]
        L.rect(dx - dw / 2, y_a - 6, dw, neck + 12)
        doors.append((dx, y_a + neck / 2))
        side = -side
        if kind:
            # the player crosses this door upwards when the level starts at the bottom (larger y)
            before = (neck / 2.0 + 130.0) if start_bottom else -(neck / 2.0 + 130.0)
            _door_gate(L, kind, dx, y_a + neck / 2, dw, 40.0, before)
    order = list(range(n))
    if start_bottom:
        order = order[::-1]
    a0 = order[0]
    d0 = doors[min(order[0], order[1])]
    start = (2 * cx - d0[0], rooms[a0][1])
    pts = [start]
    for a, b in zip(order, order[1:]):
        d = doors[min(a, b)]
        pts += [(d[0], rooms[a][1]), (d[0], rooms[b][1])]
    dl = doors[min(order[-2], order[-1])]
    goal = (2 * cx - dl[0], rooms[order[-1]][1])
    pts.append(goal)
    L.route = dedupe_route(pts)
    L.slots = []
    for i, r in enumerate(rooms):
        L.slots.append((r[0], r[1], True, room_h - 40.0))
    return L, L.route[0], L.route[-1]


FAMILIES = {
    "custom": custom, "snake_h": snake_h, "snake_v": snake_v, "zigzag": zigzag, "spiral": spiral, "maze": maze, "wander": wander, "arena": arena,
    "gates": gates, "mines": mines, "chambers": chambers,
}
