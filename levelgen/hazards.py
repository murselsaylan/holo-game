"""Hazard kits: attach moving walls, lasers, spinners, zones ... to legs of a layout's route."""
import os
import sys
import math

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from levelgen.families import lerp  # noqa: E402
from levelgen import gates as G  # noqa: E402
from sim import ARENA_W  # noqa: E402


def _st(ctx, key):
    return getattr(ctx, "style", {}).get(key, 1.0)


def route_legs(route):
    legs = []
    for a, b in zip(route, route[1:]):
        l = math.hypot(b[0] - a[0], b[1] - a[1])
        horiz = abs(a[1] - b[1]) < 1.0
        vert = abs(a[0] - b[0]) < 1.0
        legs.append({"a": a, "b": b, "len": l, "h": horiz, "v": vert})
    return legs


def leg_slots(route, ctx, footprint=40.0, spacing=250.0, relaxed=False, widths=None):
    """Hazard sites on straight legs, away from the corner squares. (x, y, horizontal, span)"""
    out = []
    for li, lg in enumerate(route_legs(route)):
        if not (lg["h"] or lg["v"]):
            continue
        lw = widths[li] if widths and li < len(widths) else ctx.W
        edge = lw / 2.0 + footprint + 70.0
        usable = lg["len"] - 2 * edge
        if usable < 0 and relaxed and lg["len"] >= lw * 0.9:
            x = (lg["a"][0] + lg["b"][0]) / 2.0
            y = (lg["a"][1] + lg["b"][1]) / 2.0
            out.append((x, y, lg["h"], lw))
            continue
        if usable >= 0:
            n = int(usable // spacing) + 1
            for k in range(n):
                tt = 0.5 if n == 1 else (edge + usable * k / (n - 1)) / lg["len"]
                x = lg["a"][0] + (lg["b"][0] - lg["a"][0]) * tt
                y = lg["a"][1] + (lg["b"][1] - lg["a"][1]) * tt
                out.append((x, y, lg["h"], lw))
    return out


# ---- individual hazards ---------------------------------------------------------------
def sweeper(L, ctx, x, y, horiz, span, phase=0.0, speed=None):
    g = max(112.0, min(span * 0.62, lerp(250.0, 150.0, ctx.tight)))
    Lb = span - g
    sp = (speed or lerp(0.6, 1.25, ctx.tight)) * _st(ctx, "sp")
    th = 44.0
    if horiz:
        L.add("moving_walls", [x - th / 2, y - Lb / 2 - (0 if span < 500 else 0), th, Lb, 0.0, g / 2.0, sp, phase])
    else:
        L.add("moving_walls", [x - Lb / 2, y - th / 2, Lb, th, g / 2.0, 0.0, sp, phase])


def laser(L, ctx, x, y, horiz, span, phase=0.0):
    period = lerp(4.2, 2.6, ctx.tight) * _st(ctx, "lp")
    ratio = lerp(0.30, 0.46, ctx.tight)
    if horiz:
        L.add("lasers", [x, y - span / 2 - 2, x, y + span / 2 + 2, period, ratio, phase])
    else:
        L.add("lasers", [x - span / 2 - 2, y, x + span / 2 + 2, y, period, ratio, phase])
    return period


SPIN_ROOM = 115.0                # px a pair needs between a spinner's tip and the nearest wall to slip past it


def _spin_room(lvl, s):
    """Free room (px) between a spinner's sweep and the nearest static wall, pillar or arena edge."""
    x, y = s[0], s[1]
    best = min(x - 15.0, ARENA_W - 15.0 - x)
    for (wx, wy, ww, wh) in lvl.walls + lvl.reverse_walls:
        px = min(max(x, wx), wx + ww)
        py = min(max(y, wy), wy + wh)
        best = min(best, math.hypot(x - px, y - py))
    for (cx, cy, cr) in lvl.circles:
        best = min(best, math.hypot(x - cx, y - cy) - cr)
    return best - s[2] - 5.0


def small_spinners(d):
    """1.0.8: a spinner in open space keeps its full length unless it leaves under SPIN_ROOM px beside it (then it is
    halved like the ones in narrow corridors, which the game halves itself - sim.LevelData). Open fields (no walls to
    squeeze past) keep them all full size."""
    from sim import LevelData
    from levelgen.plan import ARENA_LEVELS
    lvl = LevelData(dict(d))
    out = []
    for s in d.get("spinners", []):
        s = list(s)
        if (d.get("id") not in ARENA_LEVELS and lvl._corridor_span(s[0], s[1]) > 380.0
                and _spin_room(lvl, s) < SPIN_ROOM):
            s = [s[0], s[1], round(s[2] * 0.5, 2)] + s[3:]
        out.append(s)
    d["spinners"] = out
    return d


def spinner(L, ctx, x, y, horiz, span, sign=1, phase=0.0):
    hl = min(span / 2.0 - 40.0, lerp(30.0, 44.0, ctx.tight) * _st(ctx, "sz"))
    om = sign * lerp(0.6, 1.0, ctx.tight) * _st(ctx, "sp")
    L.add("spinners", [x, y, max(30.0, hl), om, phase, 10.0])


def pillars(L, ctx, x, y, horiz, span, side=1):
    r = lerp(26.0, 40.0, ctx.tight) * _st(ctx, "sz")
    off = side * (span / 2.0 - r - lerp(78.0, 52.0, ctx.tight))
    if horiz:
        L.add("circles", [x, y + off, r])
    else:
        L.add("circles", [x + off, y, r])


def micro_gate(L, ctx, x, y, horiz, span):
    """Two wall blocks pinching the corridor to a narrow slot (needs precise steering)."""
    gm = lerp(200.0, 118.0, ctx.tight)
    if gm > span - 30:
        gm = span - 30
    thick = 60.0
    half = (span - gm) / 2.0
    if half < 10 or span > 400:
        return
    if horiz:
        L.pillar(x - thick / 2, y - span / 2 - 4, thick, half + 4)
        L.pillar(x - thick / 2, y + gm / 2, thick, half + 4)
    else:
        L.pillar(x - span / 2 - 4, y - thick / 2, half + 4, thick)
        L.pillar(x + gm / 2, y - thick / 2, half + 4, thick)


def _block(L, x, y, horiz, span, s, depth, thick, side):
    """Wall block sticking `depth` px out of the side wall (side -1 = low side, +1 = high side) at position `s` along the leg."""
    if depth < 8:
        return
    if horiz:
        yy = (y - span / 2.0 - 4) if side < 0 else (y + span / 2.0 - depth)
        L.pillar(x + s - thick / 2.0, yy, thick, depth + 4)
    else:
        xx = (x - span / 2.0 - 4) if side < 0 else (x + span / 2.0 - depth)
        L.pillar(xx, y + s - thick / 2.0, depth + 4, thick)


def baffles(L, ctx, x, y, horiz, span, side=1):
    """Three staggered blocks from alternating walls: the pair has to weave (S-steering)."""
    gm = max(122.0, lerp(200.0, 132.0, ctx.tight))
    depth = span - gm
    if depth < 30:
        return
    pitch = lerp(250.0, 215.0, ctx.tight) * _st(ctx, "sz")
    for k, s in enumerate((-pitch, 0.0, pitch)):
        _block(L, x, y, horiz, span, s, depth, 44.0, side if k % 2 == 0 else -side)


def funnel(L, ctx, x, y, horiz, span, side=1):
    """Corridor narrows in steps to a tight waist and opens again (blocks from both walls)."""
    waist = max(128.0, lerp(190.0, 128.0, ctx.tight))
    if span - waist < 50:
        return
    fr = [0.9, 0.7, 0.0, 0.7, 0.9]
    for k, f in enumerate(fr):
        gm = waist + (span - waist) * f
        depth = (span - gm) / 2.0
        s = (k - 2) * 66.0
        _block(L, x, y, horiz, span, s, depth, 66.0, -1)
        _block(L, x, y, horiz, span, s, depth, 66.0, 1)


def shutter(L, ctx, x, y, horiz, span, phase=0.0):
    """Two blocks that close like a camera shutter and open again (a timing gate)."""
    if span < 200:
        return
    gb, amp = 120.0, 60.0
    sp = lerp(0.95, 1.5, ctx.tight) * _st(ctx, "sp")
    th = 46.0
    ln = span / 2.0 - gb / 2.0 + 20.0
    if horiz:
        L.add("moving_walls", [x - th / 2, y - span / 2 - 20, th, ln, 0.0, amp, sp, phase])
        L.add("moving_walls", [x - th / 2, y + gb / 2, th, ln, 0.0, -amp, sp, phase])
    else:
        L.add("moving_walls", [x - span / 2 - 20, y - th / 2, ln, th, amp, 0.0, sp, phase])
        L.add("moving_walls", [x + gb / 2, y - th / 2, ln, th, -amp, 0.0, sp, phase])


def twin_spinner(L, ctx, x, y, horiz, span, sign=1, phase=0.0):
    off = 118.0
    if horiz:
        spinner(L, ctx, x - off, y, horiz, span, sign=sign, phase=phase)
        spinner(L, ctx, x + off, y, horiz, span, sign=-sign, phase=phase + 1.7)
    else:
        spinner(L, ctx, x, y - off, horiz, span, sign=sign, phase=phase)
        spinner(L, ctx, x, y + off, horiz, span, sign=-sign, phase=phase + 1.7)


def bumper_at_joint(L, ctx, p_prev, p_joint, p_next):
    """Kinetic reverse-strip lining the far wall of a corner square."""
    room = ctx.W + 0.0
    dx = p_joint[0] - p_prev[0]
    dy = p_joint[1] - p_prev[1]
    jx, jy = p_joint
    t = 24.0
    span = room - 70.0
    if span < 40:
        return False
    inset = 2.0
    if abs(dx) > abs(dy):
        s = 1 if dx > 0 else -1
        L.add("reverse_walls", [jx + s * (room / 2.0) - (t if s > 0 else 0) - s * inset, jy - span / 2, t, span])
    else:
        s = 1 if dy > 0 else -1
        L.add("reverse_walls", [jx - span / 2, jy + s * (room / 2.0) - (t if s > 0 else 0) - s * inset, span, t])
    return True


def zone_radius(span):
    return max(60.0, min(115.0, span / 2.0 - 6.0))


def gate_sites(L, ctx, kinds, count):
    """Pick (kind, site) pairs for `count` power-up gates on distinct straight legs, spread along the route.
    site = (x, y, dx, dy, span), (dx, dy) = unit travel direction."""
    route = L.route
    if count <= 0 or not kinds or len(route) < 2:
        return []
    sx, sy = route[0]
    ex, ey = route[-1]
    widths = getattr(L, "leg_widths", None)
    legs = []
    for idx, lg in enumerate(route_legs(route)):
        if not (lg["h"] or lg["v"]):
            continue
        lw = widths[idx] if widths and idx < len(widths) else ctx.W
        edge = lw / 2.0 + 90.0
        usable = lg["len"] - 2 * edge
        if usable < 150:
            continue
        ux = (lg["b"][0] - lg["a"][0]) / lg["len"]
        uy = (lg["b"][1] - lg["a"][1]) / lg["len"]
        legs.append({"idx": idx, "lg": lg, "usable": usable, "u": (ux, uy), "w": lw, "edge": edge})
    want = [kinds[i % len(kinds)] for i in range(count)]
    order = sorted(range(len(want)), key=lambda i: -sum(G.EXTENT[want[i]]))     # hardest to fit first
    # a long leg is cut into slots (>= ~800 px) so it can carry more than one gate
    slots = []
    for leg in legs:
        n = max(1, int(leg["usable"] // 800))
        size = leg["usable"] / n
        for k in range(n):
            slots.append({"leg": leg, "a": leg["edge"] + k * size, "size": size, "id": (leg["idx"], k)})
    taken = []
    out = []

    def site_for(sl, kind):
        back, fwd = G.EXTENT[kind]
        if sl["size"] < back + fwd:
            return None
        leg = sl["leg"]
        s = sl["a"] + back + (sl["size"] - back - fwd) / 2.0
        a = leg["lg"]["a"]
        ux, uy = leg["u"]
        x, y = a[0] + ux * s, a[1] + uy * s
        if math.hypot(x - sx, y - sy) < ctx.start_room / 2 + 110 or math.hypot(x - ex, y - ey) < ctx.goal_room / 2 + 90:
            return None
        return (x, y, ux, uy, leg["w"])

    for wi in order:
        kind = want[wi]
        best = None
        for sl in slots:
            if sl["id"] in taken:
                continue
            st = site_for(sl, kind)
            if st is None:
                continue
            legs_used = [t[0] for t in taken]
            dist = min([abs(sl["leg"]["idx"] - t) for t in legs_used] or [99])
            key = (min(dist, 3), sl["size"])                 # prefer other legs, then roomier slots
            if best is None or key > best[0]:
                best = (key, sl, st)
        if best:
            taken.append(best[1]["id"])
            out.append((best[1]["leg"]["idx"] + best[1]["id"][1] * 0.001, kind, best[2]))
    out.sort(key=lambda o: o[0])
    return [(k, st) for _, k, st in out]


def apply_gates(L, ctx, kinds, count):
    """Attach power-up gates: obstacles that cannot be passed without the matching pickup. Returns the kinds placed."""
    placed = []
    gk = getattr(ctx, "gk", 0)
    L.gate_zones = getattr(L, "gate_zones", [])
    for kind, site in gate_sites(L, ctx, kinds, count):
        span = site[4]
        if kind == "gshrink":
            throat = max(92.0, min(lerp(136.0, 112.0, ctx.tight) - 6.0 * gk, span - 40.0))
            ok = G.gate_shrink(L, ctx, site, throat_w=throat)
        elif kind == "ggrow":
            ok = G.gate_grow(L, ctx, site)
        elif kind == "gshield":
            ok = G.gate_shield(L, ctx, site)
        else:
            ok = G.gate_boost(L, ctx, site, chaser_speed=130.0 * (ctx.speed / 1.1) * (1.0 + 0.12 * gk))
        if ok:
            back, fwd = G.EXTENT[kind]
            L.gate_zones.append((site[0], site[1], max(back, fwd) + 120.0))
            placed.append(kind)
    return placed


def apply(L, ctx, kit, count, rng):
    """Attach `count` hazards from `kit` (names cycled) onto the family's hazard sites."""
    route = L.route
    sl = list(L.slots) if L.slots else leg_slots(route, ctx, relaxed=getattr(L, 'relaxed', False), widths=getattr(L, 'leg_widths', None))
    sx, sy = route[0]
    ex, ey = route[-1]
    sl = [s for s in sl if math.hypot(s[0] - sx, s[1] - sy) > ctx.start_room / 2 + 110
          and math.hypot(s[0] - ex, s[1] - ey) > ctx.goal_room / 2 + 90]
    for (gx, gy, gr) in getattr(L, "gate_zones", ()):
        sl = [s for s in sl if math.hypot(s[0] - gx, s[1] - gy) > gr]
    if not sl or not kit or count <= 0:
        return 0
    if count >= len(sl):
        chosen = sl
    else:
        # stratified random: spread along the route but not evenly (every level differs)
        idx = []
        for i in range(count):
            lo = int(i * len(sl) / count)
            hi = max(lo + 1, int((i + 1) * len(sl) / count))
            idx.append(rng.randrange(lo, hi))
        chosen = [sl[i] for i in sorted(set(idx))]
    seq = []
    while len(seq) < len(chosen):                         # shuffled kit cycle instead of a fixed rotation
        cyc = list(kit)
        rng.shuffle(cyc)
        if seq and cyc[0] == seq[-1] and len(cyc) > 1:
            cyc.append(cyc.pop(0))
        seq += cyc
    placed = 0
    laser_k = 0
    side = 1
    for i, (x, y, horiz, span) in enumerate(chosen):
        name = seq[i]
        if name == "sweep":
            sweeper(L, ctx, x, y, horiz, span, phase=rng.uniform(0, 6.28))
        elif name == "laser":
            laser(L, ctx, x, y, horiz, span, phase=(laser_k % 2) * 1.55 + rng.uniform(-0.2, 0.2))
            laser_k += 1
        elif name == "spin":
            spinner(L, ctx, x, y, horiz, span, sign=side, phase=rng.uniform(0, 6.28))
            side = -side
        elif name == "pillar":
            pillars(L, ctx, x, y, horiz, span, side)
            side = -side
        elif name == "micro":
            micro_gate(L, ctx, x, y, horiz, span)
        elif name == "baffle":
            baffles(L, ctx, x, y, horiz, span, side)
            side = -side
        elif name == "funnel":
            funnel(L, ctx, x, y, horiz, span)
        elif name == "shutter":
            shutter(L, ctx, x, y, horiz, span, phase=rng.uniform(0, 6.28))
        elif name == "twin":
            twin_spinner(L, ctx, x, y, horiz, span, sign=side, phase=rng.uniform(0, 6.28))
            side = -side
        elif name == "shrink":
            L.add("shrink_zones", [x, y, zone_radius(span)])
        elif name == "grow":
            L.add("growth_zones", [x, y, zone_radius(span)])
        elif name == "boost":
            L.add("boost_pads", [x, y, zone_radius(span)])
        else:
            continue
        placed += 1
    return placed


ROAM_X, ROAM_Y = 240.0, 320.0      # a two-axis wall's reach from its centre (px)
ROAM_PACE = 140.0                  # px/s a rectangle-loop wall travels at level speed 1.0


def tidy_roamers(d):
    """1.0.8: every two-axis wall goes round a rectangle at a steady pace (11-field form: ..., speed, phase, +-1 way
    round, 0, 1) - the old mismatched sine frequencies wandered unpredictably over up to 1800 px. Reach capped at
    ROAM_X / ROAM_Y; it moves at ROAM_PACE px/s x the level speed. The game draws the rectangle. Idempotent."""
    out = []
    for m in d.get("moving_walls", []):
        m = list(m)
        if len(m) > 8 and m[4] > 0 and m[5] > 0:
            rx, ry = round(min(m[4], ROAM_X), 2), round(min(m[5], ROAM_Y), 2)
            way = 1.0 if (m[8] if len(m) > 10 else m[8] * m[6]) >= 0 else -1.0
            om = ROAM_PACE * float(d.get("speed", 1.0)) * 2.0 * math.pi / (4.0 * (rx + ry))
            m = m[:4] + [rx, ry, round(om, 4), m[7], way, 0.0, 1.0]
        out.append(m)
    if "moving_walls" in d:
        d["moving_walls"] = out
    return d


def add_roamers(L, ctx, count, rng):
    """Wall fragments that drift across most of the level's height (not pinned to one row) along a
    Lissajous-ish path - the x and y axes get their own, deliberately mismatched frequency (sim v9's 10-field
    moving_walls form), so the piece loops through many different directions over time instead of sliding back
    and forth on one straight diagonal line. Size stays modest so a gap always exists somewhere along the
    loop; the normal solver retry loop rejects any placement that turns out to be unsolvable, same as every
    other hazard."""
    H_ = ctx.H
    n = 0
    for k in range(count):
        w = rng.uniform(110.0, 170.0)
        h = rng.uniform(65.0, 95.0)
        band = (k + rng.uniform(0.15, 0.85)) / max(1, count)       # spread roamers across the level's height
        cy = 160.0 + band * (H_ - 320.0)
        rng_y = min(H_ * rng.uniform(0.26, 0.42), max(60.0, min(cy - 90.0, H_ - 90.0 - cy)))
        cx = rng.uniform(260.0, ARENA_W - 260.0)
        rng_x = rng.uniform(150.0, 280.0)
        speed_x = rng.uniform(0.24, 0.38)
        phase_x = rng.uniform(0.0, 6.28)
        turn = rng.choice((1.0, -1.0))                                # 1.0.8: round a rectangle, either way round
        rng_x, rng_y = min(rng_x, ROAM_X), min(rng_y, ROAM_Y)
        speed_x = ROAM_PACE * ctx.speed * 2.0 * math.pi / (4.0 * (rng_x + rng_y)) if hasattr(ctx, "speed") else speed_x
        L.add("moving_walls", [cx - w / 2.0, cy - h / 2.0, w, h, rng_x, rng_y, speed_x, phase_x, turn, 0.0, 1.0])
        n += 1
    return n


def add_bumpers(L, ctx, count, rng):
    route = L.route
    joints = list(range(1, len(route) - 1))
    if not joints or count <= 0:
        return 0
    rng.shuffle(joints)
    n = 0
    for j in joints:
        if n >= count:
            break
        p0, p1 = route[j - 1], route[j]
        if bumper_at_joint(L, ctx, p0, p1, route[j + 1]):
            n += 1
    return n
