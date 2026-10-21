"""HOLO deterministic simulation core.

Pure python (no pygame) so that the very same physics runs in
  * the game client (fixed 60 Hz timestep, render-interpolated),
  * the offline level solver / difficulty tuner,
  * the leaderboard server, which replays submitted tap logs to verify scores.

Level coordinates are arena-local: x in [0, ARENA_W], y in [0, ARENA_H].
"""
import math
import json
import os
import sys
import hashlib

SIM_DT = 1.0 / 60.0
ARENA_W = 900.0
ARENA_H = 1470.0
TETHER = 100.0
SHRINK_TETHER = 62.0          # a shrink field makes the whole pair compact (needed for very narrow throats)
WALL_SHIELD_INVULN = 0.15    # after a shield bounces the pair off a solid wall (no phasing through walls)
BOUNCE_BOOST = 0.7            # seconds of extra speed (x1.35) after a kinetic bumper throws the pair back
SHIELD_INVULN = 0.8           # seconds of invulnerability after a shield pops
SNAP_EVERY = 15               # revive: a clean state of the pair is kept every quarter second ...
SNAP_KEEP = 8                 # ... the last two seconds of them
REVIVE_BACK = 60              # a revive rewinds the pair to a state at least one second before it died
REVIVE_SAFE = 1.0             # then moving hazards spare it for a second (walls stay solid)
REVIVE_CLEAR = 30.0           # preferred revive point: both orbs this far from any solid wall
REVIVE_SPIN_START = 0.12      # revive "R2" (1.0.6): the pair starts turning at 12 % speed ...
REVIVE_SPIN_RAMP = 2.5        # ... and is back to full speed after this many seconds; it is shielded until the next tap
REVIVE_SPIN_RAMP_R3 = 4.0     # revive "R3" (1.0.8): a longer spin-up - players need time to get used to the speed again
BARRIER_PASS = 0.8            # seconds a shield lets the pair phase through energy barriers only (extended while inside one, sim v10)
SLOW_EASE = 0.05               # per step: the field slows / releases the pair gradually (about 0.4 s), not at once
SLOW_FACTOR = 0.6              # inside a slow field the pair turns at 60 % speed (levels 101+)
STRETCH_LONG = 1.6            # tether stretch field, kind +1: the tether grows by 60 % (levels 121+)
STRETCH_SHORT = 0.6           # kind -1: the tether shortens to 60 %
TETHER_EASE_SOFT = 0.08       # stretch fields: the tether eases in and out gently (0.14 for the old shrink / grow)
STRETCH_SLOW = 0.15             # turning rate lost at the moment of full stretch
STRETCH_DECAY = 150             # steps (2.5 s): after the moving orb touched a field the tether shortens back slowly over this time
SHORT_SPIN_MAX = 1.2          # short tether: at most 20 % faster turning
STRETCH_TIME = 6.0            # seconds a stretch field stays in effect (the tip speed is held constant meanwhile)
FX_TIME = 10.0                # seconds a shrink / growth field stays in effect
BREAK_R = 21.0                # only a grown (heavy) orb can smash a cracked wall
ORB_R = 15.0
BASE_OMEGA = 0.052 * 60.0          # rad / s at speed 1.0
EDGE_MARGIN = 15.0
SPAWN_GRACE = 3.5                  # seconds of safe orbiting before the first tap
BUCKET = 60
RAMP_EXP = 2.2
SIM_VERSION = 10
MAX_LEVELS = 140
CP_RADIUS = 60.0                   # checkpoints (1.0.9): either orb this close to the flag lights it
CHECKPOINT_SHIELD_S = 1.2          # resume from a checkpoint (free, light help): every hit bounces for this long (or until the first tap) ...
CHECKPOINT_SLOW_S = 1.5            # ... and the pair spins up from 12 % to full speed over this long (paid R3: unlimited shield until the tap, 4 s)
CHECKPOINT_FREE_RESUMES = 2        # the 3rd resume in a row from the SAME flag gets neither shield nor slow start
CP_PENALTY = 0.95                  # a clear that resumed from a checkpoint scores 95 % (the time of the death counts anyway)
MIN_TAP_GAP = 4                    # steps (66 ms) between swaps; the server rejects faster input

if getattr(sys, "frozen", False):
    LEVELS_DIR = os.path.join(getattr(sys, "_MEIPASS", os.path.dirname(sys.executable)), "levels")
else:
    LEVELS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "levels")

_HALF_PI = math.pi / 2.0
_TWO_PI = math.pi * 2.0


# --------------------------------------------------------------------------- geometry
def circle_rect_hit(cx, cy, r, x, y, w, h):
    px = x if cx < x else (x + w if cx > x + w else cx)
    py = y if cy < y else (y + h if cy > y + h else cy)
    dx = cx - px
    dy = cy - py
    return dx * dx + dy * dy < r * r


def rect_penetration(cx, cy, r, x, y, w, h):
    """How deep a circle reaches into a rect (<= 0: apart). sqrt, not hypot: must match sim.ts bit for bit."""
    dx = max(x - cx, 0.0, cx - (x + w))
    dy = max(y - cy, 0.0, cy - (y + h))
    if dx == 0.0 and dy == 0.0:                     # centre inside the rect
        return r + min(cx - x, x + w - cx, cy - y, y + h - cy)
    return r - math.sqrt(dx * dx + dy * dy)


def circle_segment_hit(cx, cy, r, x1, y1, x2, y2, thickness=6.0):
    dx = x2 - x1
    dy = y2 - y1
    ll = dx * dx + dy * dy
    rr = r + thickness * 0.5
    if ll == 0:
        return (cx - x1) ** 2 + (cy - y1) ** 2 < rr * rr
    tt = ((cx - x1) * dx + (cy - y1) * dy) / ll
    tt = 0.0 if tt < 0 else (1.0 if tt > 1 else tt)
    ex = x1 + tt * dx - cx
    ey = y1 + tt * dy - cy
    return ex * ex + ey * ey < rr * rr


# --------------------------------------------------------------------------- level data
class LevelData:
    """Immutable description of a level (loaded from levels/levelN.json)."""

    def __init__(self, d):
        self.raw = d
        self.id = int(d.get("id", 0))
        self.title = d.get("title", "")
        self.start = tuple(d["start"])
        self.end = tuple(d["end"])
        self.height = float(d.get("height", ARENA_H))
        self.speed = float(d.get("speed", 1.0))
        self.ramp = float(d.get("ramp", 0.15))
        self.par_time = float(d.get("par_time", 40.0))
        self.par_swaps = int(d.get("par_swaps", 20))
        self.waypoints = [tuple(p) for p in d.get("waypoints", [])]
        self.walls = [tuple(w) for w in d.get("walls", [])]
        self.reverse_walls = [tuple(w) for w in d.get("reverse_walls", [])]
        # x, y, w, h, range_x, range_y, speed, phase [, speed_y, phase_y]: the optional 9th/10th fields (sim v9)
        # give the y axis its own frequency/phase instead of sharing the x one, so the piece drifts along a
        # Lissajous-ish path through many directions instead of back and forth on one straight diagonal line.
        self.moving_walls = [tuple(m) + (0.0,) * ((10 if len(m) > 8 else 8) - len(m)) for m in d.get("moving_walls", [])]
        # x1, y1, x2, y2, period, active_ratio, phase
        self.lasers = [tuple(l) + (3.0, 0.4, 0.0)[len(l) - 4:] for l in d.get("lasers", [])]
        # cx, cy, half_len, omega, phase, thickness
        # In narrow corridors (span <= 380px), halve the laser length so the player has room to swing
        raw_spinners = [tuple(s) + (10.0,)[len(s) - 5:] for s in d.get("spinners", [])]
        adjusted_spinners = []
        for s in raw_spinners:
            cx, cy, hlen, omega, phase, thickness = s
            span = self._corridor_span(cx, cy)
            if span <= 380.0:
                hlen *= 0.5
            adjusted_spinners.append((cx, cy, hlen, omega, phase, thickness))
        self.spinners = adjusted_spinners
        pre = bool(d.get("pre_adjusted"))       # endless stages: spinners / chasers were already adjusted in their own map
        if pre:
            self.spinners = [tuple(s) + (10.0,)[len(s) - 5:] for s in d.get("spinners", [])]
        self.circles = [tuple(c) for c in d.get("circles", [])]
        # checkpoints (1.0.9): [x, y] flags in route order; not part of the digest (see `digest`), so a shipped
        # client's level versions stay valid
        self.checkpoints = [(float(c[0]), float(c[1])) for c in d.get("checkpoints", [])]
        self.stars = [tuple(s) for s in d.get("stars", [])][:None if pre else 3]    # endless: every stage's stars
        self.growth = [tuple(z) + (32.0,)[len(z) - 2:] for z in d.get("growth_zones", [])]
        self.shrink = [tuple(z) + (30.0,)[len(z) - 2:] for z in d.get("shrink_zones", [])]
        self.boost = [tuple(z) + (28.0,)[len(z) - 2:] for z in d.get("boost_pads", [])]
        self.slow = [tuple(z) for z in d.get("slow_zones", [])]                  # x, y, r
        self.stretch = [tuple(z) + (1,)[len(z) - 3:] for z in d.get("stretch_zones", [])]   # x, y, r, kind (+1 long / -1 short)
        self.shields = [tuple(z) for z in d.get("shields", [])]
        # x, y, w, h : cracked wall, smashed by a grown orb (radius >= BREAK_R) instead of killing it
        self.breakables = [tuple(b) for b in d.get("breakables", [])]
        # x, y, w, h, vx, vy, tx, ty, tw, th, max_dist : a wall that waits until an orb enters the trigger rect,
        # then appears at (x, y), moves at (vx, vy) px/s and vanishes after max_dist px.
        # Spawns further back (85px) for reaction room, with fair speed (0.90x) so human players can escape.
        raw_chasers = [tuple(c) + (0.0,) * (11 - len(c)) for c in d.get("chasers", [])]
        adjusted_chasers = []
        for c in raw_chasers:
            x, y, w, h, vx, vy, tx, ty, tw, th, max_dist = c
            spd = math.hypot(vx, vy)
            if spd > 1e-4:
                ux, uy = vx / spd, vy / spd
                OFFSET = 85.0
                SPEED_MULT = 0.90
                x -= ux * OFFSET
                y -= uy * OFFSET
                vx *= SPEED_MULT
                vy *= SPEED_MULT
                if max_dist > 0.0:
                    max_dist = max_dist + OFFSET
            adjusted_chasers.append((x, y, w, h, vx, vy, tx, ty, tw, th, max_dist))
        self.chasers = adjusted_chasers if not pre else [tuple(c) + (0.0,) * (11 - len(c)) for c in d.get("chasers", [])]
        # thin energy barriers that only a shield can cross; they are also listed in walls (rounded), and those
        # wall entries are flagged so a shield-phasing pair ignores them but still hits every solid wall (sim v10)
        self.barriers = [tuple(b) for b in d.get("barriers", [])]
        self.barrier_walls = {i for i, w in enumerate(self.walls)
                              if any(all(abs(a - c) <= 1.0 for a, c in zip(w, b)) for b in self.barriers)}
        self.end_rect = (self.end[0] - 25.0, self.end[1] - 25.0, 50.0, 50.0)
        self.timed = bool(self.moving_walls or self.lasers or self.spinners or self.chasers)
        self.time_period = self._time_period()
        self._build_buckets()
        self._build_path()

    @property
    def digest(self):
        """Short hash of everything that influences the physics (not of the reference solution)."""
        skip = ("ref_taps", "difficulty", "title", "checkpoints")
        body = json.dumps({k: v for k, v in self.raw.items() if k not in skip}, sort_keys=True, separators=(",", ":"))
        return hashlib.md5((body + f"|v{SIM_VERSION}").encode()).hexdigest()[:10]

    @classmethod
    def load(cls, level_id, levels_dir=None):
        path = os.path.join(levels_dir or LEVELS_DIR, f"level{level_id}.json")
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            return cls(json.load(f))

    def _time_period(self):
        """Rough repeat period of the time based hazards (used for state dedupe in the solver)."""
        periods = [2 * math.pi / max(0.1, m[6]) for m in self.moving_walls]
        periods += [60.0] * (1 if self.chasers else 0)
        periods += [l[4] for l in self.lasers]
        periods += [2 * math.pi / max(0.1, abs(s[3])) for s in self.spinners]
        return max(periods) if periods else 0.0

    def _corridor_span(self, cx, cy):
        """Measures the minimum corridor clearance (width or height) around (cx, cy)."""
        left_dist = cx
        right_dist = ARENA_W - cx
        up_dist = cy
        down_dist = self.height - cy
        for w in self.walls + self.reverse_walls:
            x, y, w_w, h_h = w
            if y <= cy <= y + h_h:
                if x + w_w <= cx:
                    left_dist = min(left_dist, cx - (x + w_w))
                elif x >= cx:
                    right_dist = min(right_dist, x - cx)
            if x <= cx <= x + w_w:
                if y + h_h <= cy:
                    up_dist = min(up_dist, cy - (y + h_h))
                elif y >= cy:
                    down_dist = min(down_dist, y - cy)
        return min(left_dist + right_dist, up_dist + down_dist)

    def _build_buckets(self):
        self.wall_buckets = {}
        self.solid_buckets = {}             # walls without the energy barriers
        self.barrier_buckets = {}           # the energy barriers only
        self.rev_buckets = {}
        for store, rects in ((self.wall_buckets, self.walls), (self.rev_buckets, self.reverse_walls)):
            for idx, (x, y, w, h) in enumerate(rects):
                for i in range(int(x // BUCKET), int((x + w) // BUCKET) + 1):
                    for j in range(int(y // BUCKET), int((y + h) // BUCKET) + 1):
                        store.setdefault((i, j), []).append((idx, x, y, w, h))
                        if store is self.wall_buckets:
                            sub = self.barrier_buckets if idx in self.barrier_walls else self.solid_buckets
                            sub.setdefault((i, j), []).append((idx, x, y, w, h))

    def _build_path(self):
        wp = self.waypoints if len(self.waypoints) >= 2 else [self.start, self.end]
        self.path = wp
        self.seg_len = []
        self.cum = [0.0]
        for i in range(len(wp) - 1):
            l = math.hypot(wp[i + 1][0] - wp[i][0], wp[i + 1][1] - wp[i][1])
            self.seg_len.append(l)
            self.cum.append(self.cum[-1] + l)
        self.path_total = self.cum[-1] or 1.0

    def progress(self, px, py):
        best_d = 1e18
        best_pos = 0.0
        wp = self.path
        for i, l in enumerate(self.seg_len):
            if l == 0:
                continue
            x1, y1 = wp[i]
            x2, y2 = wp[i + 1]
            dx = x2 - x1
            dy = y2 - y1
            tt = ((px - x1) * dx + (py - y1) * dy) / (l * l)
            tt = 0.0 if tt < 0 else (1.0 if tt > 1 else tt)
            ex = x1 + tt * dx - px
            ey = y1 + tt * dy - py
            d = ex * ex + ey * ey
            if d < best_d:
                best_d = d
                best_pos = self.cum[i] + tt * l
        p = best_pos / self.path_total
        return 0.0 if p < 0 else (1.0 if p > 1 else p)

    # ---- time based hazards -------------------------------------------------
    def moving_rect(self, m, t):
        if len(m) > 10 and m[10] == 1.0:                 # 1.0.8: round a rectangle at a steady pace (m[8] = +-1 way round)
            rx, ry = m[4], m[5]
            u = m[8] * (t * m[6] + m[7]) / _TWO_PI
            s = (u - math.floor(u)) * 4.0 * (rx + ry)
            if s < 2.0 * rx:
                ox, oy = s - rx, -ry
            elif s < 2.0 * rx + 2.0 * ry:
                ox, oy = rx, s - 2.0 * rx - ry
            elif s < 4.0 * rx + 2.0 * ry:
                ox, oy = 3.0 * rx + 2.0 * ry - s, ry
            else:
                ox, oy = -rx, 4.0 * rx + 3.0 * ry - s
            return (m[0] + ox, m[1] + oy, m[2], m[3])
        if len(m) > 8:                                   # sim v9: independent x/y frequency (Lissajous drift)
            offx = math.sin(t * m[6] + m[7])
            offy = math.sin(t * m[8] + m[9])
            return (m[0] + offx * m[4], m[1] + offy * m[5], m[2], m[3])
        off = math.sin(t * m[6] + m[7])
        return (m[0] + off * m[4], m[1] + off * m[5], m[2], m[3])

    def chaser_rect(self, c, t0, t):
        """Current rectangle of a chaser (t0 = time it was triggered); None while dormant and once it has vanished."""
        if t0 is None:
            return None
        dt_ = t - t0
        if dt_ < 0.0:
            dt_ = 0.0
        if c[10] > 0.0 and math.hypot(c[4], c[5]) * dt_ > c[10]:
            return None
        return (c[0] + c[4] * dt_, c[1] + c[5] * dt_, c[2], c[3])

    def laser_state(self, l, t):
        """returns (active, warning)"""
        cycle = (t + l[6]) % l[4]
        active = (cycle / l[4]) < l[5]
        warn = (not active) and (l[4] - cycle) < 0.6
        return active, warn

    def spinner_segment(self, s, t):
        a = s[4] + s[3] * t
        c = math.cos(a) * s[2]
        d = math.sin(a) * s[2]
        return (s[0] - c, s[1] - d, s[0] + c, s[1] + d)


# --------------------------------------------------------------------------- simulation
class Orb:
    __slots__ = ("x", "y", "r", "tr", "m", "tm")

    def __init__(self, x=0.0, y=0.0):
        self.x = x
        self.y = y
        self.r = ORB_R
        self.tr = ORB_R
        self.m = 1.0
        self.tm = 1.0

    def copy(self):
        o = Orb.__new__(Orb)
        o.x = self.x
        o.y = self.y
        o.r = self.r
        o.tr = self.tr
        o.m = self.m
        o.tm = self.tm
        return o


class Sim:
    """One attempt at one level. Call swap() for a tap, step() for every 1/60 s."""

    def __init__(self, lvl, margin=0.0, record_events=False, fixed_angle=None):
        self.lvl = lvl
        self.margin = margin            # extra radius for FATAL collisions only (solver safety slack); never changes the dynamics
        self.record = record_events
        self.events = []
        self.n = 0
        self.t = 0.0
        sx, sy = lvl.start
        self.orbs = [Orb(sx, sy), Orb(sx, sy)]
        self.piv = 0
        self.tether = TETHER
        self.tether_base = TETHER
        self.broken = [False] * len(lvl.breakables)
        self.chase_t0 = [None] * len(lvl.chasers)
        self.fx_t = 0.0
        self.stretch_soft = False          # a stretch field's tether eases slowly (in and out)
        self.slow_f = 1.0                  # the slow field's current turning factor: it eases in and out (no jump)
        self.stretch_hold = 0              # steps left of the stretch's slow decay after the moving orb touched a field
        self.stretch_amp = 0.0             # how far the stretch pulls the tether from its normal length
        self.rot_sign = 1.0
        self.smooth = lvl.speed
        self.boost_t = 0.0
        self.shields = 0
        self.grace = 0.0                # only used by the holo game for visuals; no free pass after the first tap
        self.invuln = 0.0
        self.wall_escaping = False      # still recovering from a shield-vs-wall bounce (sim v8)
        self.wall_escape_t = 0.0
        self.barrier_t = 0.0            # shield phasing through energy barriers - and only them (sim v10)
        self.swaps = 0
        self.dead = False
        self.won = False
        self.stars = [False] * len(lvl.stars)
        self.shield_taken = [False] * len(lvl.shields)
        self.combo_streak = 0
        self.combo_mult = 1
        self.max_combo = 1
        self.combo_points = 0
        self.last_swap_t = 0.0
        self.near_cool = 0.0
        self.near_count = 0
        self.near_pts = 0
        self.last_graze_x = None
        self.last_graze_y = None
        self.grazed_cells = {}
        self.star_pts = 0
        self.progress = 0.0
        self.max_progress = 0.0
        self.min_clear = 999.0
        self.revive_t = 0.0
        self.guard = False                 # revive R2: every hit bounces (no shield used up) until the next tap
        self.spin_ramp = 1.0               # revive R2: rotation speed ramp 0 -> 1 (1 = normal)
        self.guard_walls = False           # revive R3: while guarded, walls stay solid even during a bounce's invulnerability
        self.spin_ramp_s = REVIVE_SPIN_RAMP  # seconds of the current revive's spin-up (R3: longer)
        self.cp_next = 0                   # checkpoints lit so far (the next one to reach)
        self.cp_state = None               # the pair's state at the latest lit checkpoint (see _take_checkpoint)
        self.cp_used = 0                   # times a death was resumed from a checkpoint
        self.cp_streak = 0                 # resumes in a row from the latest flag (reset when the next flag is lit)
        self.guard_t = 0.0                 # checkpoint resume: seconds of shield left (0 = no timer: revive shields last until the tap)
        self.ang = fixed_angle if fixed_angle is not None else self._best_start_angle()
        self._place_rotating()
        self.snaps = [self._snap()]      # revive points (see revive())

    # ---- helpers -------------------------------------------------------------
    def _place_rotating(self):
        p = self.orbs[self.piv]
        r = self.orbs[1 - self.piv]
        r.x = p.x + math.cos(self.ang) * self.tether
        r.y = p.y + math.sin(self.ang) * self.tether

    def _best_start_angle(self):
        lvl = self.lvl
        sx, sy = lvl.start
        best_a, best_c = 0.0, -1.0
        for i in range(36):
            a = i * (_TWO_PI / 36.0)
            tx = sx + math.cos(a) * TETHER
            ty = sy + math.sin(a) * TETHER
            if not (25 <= tx <= ARENA_W - 25 and 25 <= ty <= lvl.height - 25):
                continue
            c = 9999.0
            for rects in (lvl.walls, lvl.reverse_walls):
                for (x, y, w, h) in rects:
                    px = x if tx < x else (x + w if tx > x + w else tx)
                    py = y if ty < y else (y + h if ty > y + h else ty)
                    c = min(c, math.hypot(tx - px, ty - py))
            for m in lvl.moving_walls:
                x, y, w, h = lvl.moving_rect(m, 0.0)
                px = x if tx < x else (x + w if tx > x + w else tx)
                py = y if ty < y else (y + h if ty > y + h else ty)
                c = min(c, math.hypot(tx - px, ty - py))
            if c > best_c:
                best_c, best_a = c, a
        return best_a

    def clone(self):
        c = Sim.__new__(Sim)
        c.lvl = self.lvl
        c.margin = self.margin
        c.record = False
        c.events = []
        c.n = self.n
        c.t = self.t
        c.orbs = [self.orbs[0].copy(), self.orbs[1].copy()]
        c.piv = self.piv
        c.tether = self.tether
        c.tether_base = self.tether_base
        c.broken = list(self.broken)
        c.chase_t0 = list(self.chase_t0)
        c.fx_t = self.fx_t
        c.stretch_soft = self.stretch_soft
        c.stretch_hold = self.stretch_hold
        c.slow_f = self.slow_f
        c.stretch_amp = self.stretch_amp
        c.rot_sign = self.rot_sign
        c.smooth = self.smooth
        c.boost_t = self.boost_t
        c.shields = self.shields
        c.grace = self.grace
        c.invuln = self.invuln
        c.wall_escaping = self.wall_escaping
        c.wall_escape_t = self.wall_escape_t
        c.barrier_t = self.barrier_t
        c.swaps = self.swaps
        c.dead = self.dead
        c.won = self.won
        c.stars = list(self.stars)
        c.shield_taken = list(self.shield_taken)
        c.combo_streak = self.combo_streak
        c.combo_mult = self.combo_mult
        c.max_combo = self.max_combo
        c.combo_points = self.combo_points
        c.last_swap_t = self.last_swap_t
        c.near_cool = self.near_cool
        c.near_count = self.near_count
        c.near_pts = self.near_pts
        c.last_graze_x = self.last_graze_x
        c.last_graze_y = self.last_graze_y
        c.grazed_cells = dict(self.grazed_cells)
        c.star_pts = self.star_pts
        c.progress = self.progress
        c.max_progress = self.max_progress
        c.min_clear = self.min_clear
        c.ang = self.ang
        c.revive_t = self.revive_t
        c.guard = self.guard
        c.guard_walls = self.guard_walls
        c.spin_ramp_s = self.spin_ramp_s
        c.spin_ramp = self.spin_ramp
        c.cp_next = self.cp_next
        c.cp_state = self.cp_state          # immutable once taken
        c.cp_used = self.cp_used
        c.cp_streak = self.cp_streak
        c.guard_t = self.guard_t
        c.snaps = list(self.snaps)
        return c

    def _ev(self, *e):
        if self.record:
            self.events.append(e)

    @property
    def pivot(self):
        return self.orbs[self.piv]

    @property
    def rotating(self):
        return self.orbs[1 - self.piv]

    @property
    def stars_collected(self):
        return sum(1 for s in self.stars if s)

    @property
    def protected(self):
        return self.grace > 0 or self.invuln > 0 or (self.swaps == 0 and self.t < SPAWN_GRACE)

    @property
    def chaser_active(self):
        """Returns True while at least one chaser wall is triggered and actively moving."""
        if not self.lvl.chasers:
            return False
        for i, c in enumerate(self.lvl.chasers):
            if self.chase_t0[i] is not None and self.lvl.chaser_rect(c, self.chase_t0[i], self.t) is not None:
                return True
        return False

    # ---- input -----------------------------------------------------------------
    # ---- paid help: the game and the server's replay apply exactly these (normal physics unchanged)
    def add_shield(self):
        """A shield bought with diamonds and put on the pair (HUD button)."""
        self.shields += 1

    def _snap(self):
        return (self.n, tuple((o.x, o.y, o.r, o.tr, o.m, o.tm) for o in self.orbs), self.piv, self.ang, self.rot_sign,
                self.tether, self.tether_base, self.fx_t, self.boost_t, self.smooth)

    def revive(self, guarded=False, walls=False):
        """Continue after dying (20 diamonds): the pair goes back to where it safely was at least a second before
        (a clean state kept every quarter second), walls stay solid, and moving hazards spare it for a second.
        Time, taps, shields, stars and smashed walls are not rewound - only the pair's own motion.
        guarded (assist "R2", 1.0.6+): it starts turning very slowly, speeding up over REVIVE_SPIN_RAMP seconds, and
        every hit bounces it like a shield (without using one up) until the player taps again.
        walls (assist "R3", 1.0.8+): on top of that, the swinging orb can never enter a wall while guarded - a bounce's
        invulnerability used to let it swing straight through one."""
        self.dead = False
        target = self.n - REVIVE_BACK
        snap = None
        fallback = self.snaps[0]
        for s in reversed(self.snaps):            # newest first: the latest point well away from the walls
            if s[0] > target:
                continue
            if fallback is self.snaps[0] and s is not self.snaps[0]:
                fallback = s
            if not any(self._wall_hit(st[0], st[1], st[2] + REVIVE_CLEAR, True) for st in s[1]):
                snap = s
                break
        if snap is None:
            snap = fallback
        _, orbs, self.piv, self.ang, self.rot_sign, self.tether, self.tether_base, self.fx_t, self.boost_t, self.smooth = snap
        for o, st in zip(self.orbs, orbs):
            o.x, o.y, o.r, o.tr, o.m, o.tm = st
        self.invuln = 0.0
        self.wall_escaping = False
        self.wall_escape_t = 0.0
        self.barrier_t = 0.0
        self.revive_t = REVIVE_SAFE
        self.snaps = [snap]
        self.guard_t = 0.0
        if guarded:
            self.guard = True
            self.spin_ramp = 0.0
        self.guard_walls = bool(guarded and walls)
        self.spin_ramp_s = REVIVE_SPIN_RAMP_R3 if (guarded and walls) else REVIVE_SPIN_RAMP

    def _take_checkpoint(self):
        """A flag lit: remember the pair as it is (motion, speed, tether, shields, stars, smashed walls, chasers)."""
        self.cp_state = {
            "snap": self._snap(), "stretch": (self.stretch_soft, self.stretch_hold, self.stretch_amp),
            "shields": self.shields, "stars": tuple(self.stars), "shield_taken": tuple(self.shield_taken),
            "star_pts": self.star_pts, "broken": tuple(self.broken), "chase_t0": tuple(self.chase_t0), "t": self.t,
        }
        self.cp_next += 1
        self.cp_streak = 0
        o = self.pivot
        self._ev("checkpoint", o.x, o.y, self.cp_next)

    def resume_checkpoint(self):
        """Continue after dying from the latest lit checkpoint (free, assist "C"). Returns False when none was lit.
        The pair gets back its motion, speed, tether, shields, the stars and smashed walls it had there (what it
        picked up since is back on the track); time, swaps and taps are not rewound, and the chasers are in the same
        relative state as at the flag. Revive R3 rules follow: slow spin-up, shielded until the next tap."""
        cp = self.cp_state
        if cp is None or not self.dead:
            return False
        self.dead = False
        _, orbs, self.piv, self.ang, self.rot_sign, self.tether, self.tether_base, self.fx_t, self.boost_t, self.smooth = cp["snap"]
        for o, st in zip(self.orbs, orbs):
            o.x, o.y, o.r, o.tr, o.m, o.tm = st
        self.stretch_soft, self.stretch_hold, self.stretch_amp = cp["stretch"]
        self.shields = cp["shields"]
        self.stars = list(cp["stars"])
        self.shield_taken = list(cp["shield_taken"])
        self.star_pts = cp["star_pts"]
        self.broken = list(cp["broken"])
        shift = self.t - cp["t"]
        self.chase_t0 = [None if v is None else v + shift for v in cp["chase_t0"]]
        self.grace = 0.0
        self.invuln = 0.0
        self.wall_escaping = False
        self.wall_escape_t = 0.0
        self.barrier_t = 0.0
        self.revive_t = REVIVE_SAFE
        self.snaps = [cp["snap"]]
        self.cp_streak += 1
        self.cp_used += 1
        if self.cp_streak <= CHECKPOINT_FREE_RESUMES:     # light help: a short shield (walls stay solid) and a short slow start
            self.guard = True
            self.guard_t = CHECKPOINT_SHIELD_S
            self.guard_walls = True
            self.spin_ramp = 0.0
            self.spin_ramp_s = CHECKPOINT_SLOW_S
        else:
            self.guard = False
            self.guard_t = 0.0
            self.guard_walls = False
            self.spin_ramp = 1.0
        return True

    def swap(self):
        if self.dead or self.won:
            return
        self.guard = False                       # the revive shield lasts until the player's first tap
        self.guard_t = 0.0
        self.guard_walls = False
        since = self.t - self.last_swap_t
        self.last_swap_t = self.t
        if 0.28 <= since <= 1.35:
            self.combo_streak += 1
            prev = self.combo_mult
            s = self.combo_streak
            self.combo_mult = 4 if s >= 8 else (3 if s >= 5 else (2 if s >= 2 else 1))
            if self.combo_mult > self.max_combo:
                self.max_combo = self.combo_mult
            if self.combo_mult > prev:
                r = self.rotating
                self._ev("combo", r.x, r.y, self.combo_mult)
        else:
            self.combo_streak = 0
            self.combo_mult = 1

        self.tether = self.tether_base + 3.5 * self.rotating.m
        self.piv = 1 - self.piv
        self.ang += math.pi
        if self.ang > _TWO_PI:
            self.ang -= _TWO_PI
        self.swaps += 1
        pts = 100 * self.combo_mult
        self.combo_points += pts
        p = self.pivot
        self._ev("swap", p.x, p.y)

    # ---- one physics tick --------------------------------------------------------
    def step(self):
        if self.dead or self.won:
            return
        dt = SIM_DT
        lvl = self.lvl
        self.n += 1
        self.t += dt
        t = self.t
        o0, o1 = self.orbs
        piv = self.orbs[self.piv]
        rot = self.orbs[1 - self.piv]
        ang0 = self.ang                          # angle before this step's rotation (bounces restore it)

        for o in (o0, o1):
            if o.r != o.tr:
                o.r += (o.tr - o.r) * 0.18
            if o.m != o.tm:
                o.m += (o.tm - o.m) * 0.18
        if self.stretch_soft:
            self.tether += (self.tether_base - self.tether) * TETHER_EASE_SOFT
            if self.tether_base == TETHER and abs(self.tether - TETHER) < 1.0:
                self.stretch_soft = False
        else:
            self.tether += (self.tether_base - self.tether) * 0.14

        prog = lvl.progress(piv.x, piv.y)
        self.progress = prog
        if prog > self.max_progress:
            self.max_progress = prog

        # secret end-game acceleration: back-loaded so the first half feels unchanged, the last stretch sprints
        target = lvl.speed * (1.0 + lvl.ramp * (prog ** RAMP_EXP))
        if self.boost_t > 0:
            self.boost_t -= dt
            target *= 1.35
        self.smooth += (target - self.smooth) * 0.04

        omega = BASE_OMEGA * self.smooth / (rot.m ** 0.35)
        slow_target = 1.0
        if lvl.slow:                             # slow field: either orb inside -> the turning factor eases down to SLOW_FACTOR
            for z in lvl.slow:
                if (math.hypot(o0.x - z[0], o0.y - z[1]) < z[2] + o0.r * 0.5
                        or math.hypot(o1.x - z[0], o1.y - z[1]) < z[2] + o1.r * 0.5):
                    slow_target = SLOW_FACTOR
                    break
        if lvl.slow or self.slow_f != 1.0:
            self.slow_f += (slow_target - self.slow_f) * SLOW_EASE
            if abs(self.slow_f - 1.0) < 1e-4:
                self.slow_f = 1.0
            omega *= self.slow_f
        if self.stretch_hold > 0:                # a stretched tether turns a little slower (up to STRETCH_SLOW), easing back with the decay
            omega *= 1.0 - STRETCH_SLOW * self.stretch_hold / STRETCH_DECAY
        if self.spin_ramp < 1.0:                 # just revived (R2): turning slowly, easing back to full speed
            omega *= REVIVE_SPIN_START + (1.0 - REVIVE_SPIN_START) * self.spin_ramp * self.spin_ramp
            self.spin_ramp = min(1.0, self.spin_ramp + dt / self.spin_ramp_s)
        d_ang = omega * dt * self.rot_sign
        sub = d_ang / 4.0

        # time based hazards at this instant
        mrects = [lvl.moving_rect(m, t) for m in lvl.moving_walls] if lvl.moving_walls else ()
        lasers = ()
        if lvl.lasers:
            lasers = [(l[0], l[1], l[2], l[3]) for l in lvl.lasers if lvl.laser_state(l, t)[0]]
        spins = [lvl.spinner_segment(s, t) + (s[5],) for s in lvl.spinners] if lvl.spinners else ()
        if lvl.chasers:
            for i, c in enumerate(lvl.chasers):
                if self.chase_t0[i] is None and (
                        circle_rect_hit(o0.x, o0.y, o0.r, c[6], c[7], c[8], c[9])
                        or circle_rect_hit(o1.x, o1.y, o1.r, c[6], c[7], c[8], c[9])):
                    self.chase_t0[i] = t
                    self._ev("chase", c[0] + c[2] / 2.0, c[1] + c[3] / 2.0, i)
            mrects = list(mrects) + [r_ for r_ in (lvl.chaser_rect(c, self.chase_t0[i], t)
                                                    for i, c in enumerate(lvl.chasers)) if r_ is not None]

        # rotation in sub-steps, tunnelling-safe reverse-wall bounce (sim v10): the swinging orb bounces whenever a
        # step would take it deeper into a bumper - moving out is always allowed, moving in never. (v9 muted a bumper
        # until both orbs had left it, so with the pivot resting against one the other orb swung straight inside.)
        rev = lvl.reverse_walls
        if rev:
            px, py = piv.x, piv.y
            rr = rot.r
            for _ in range(4):
                prev = self.ang
                ox = px + math.cos(prev) * self.tether
                oy = py + math.sin(prev) * self.tether
                self.ang += sub
                tx = px + math.cos(self.ang) * self.tether
                ty = py + math.sin(self.ang) * self.tether
                bounced = False
                for idx, (x, y, w, h) in enumerate(rev):
                    pen = rect_penetration(tx, ty, rr, x, y, w, h)
                    if pen > 0.0 and pen > rect_penetration(ox, oy, rr, x, y, w, h) + 1e-9:
                        self.rot_sign = -self.rot_sign
                        sub = -sub
                        self.ang = prev
                        if self.boost_t < BOUNCE_BOOST:
                            self.boost_t = BOUNCE_BOOST                 # the bounce also kicks the pair forward
                        self._ev("reverse", tx, ty, idx)
                        bounced = True
                        break
                if bounced:
                    break
        else:
            self.ang += d_ang

        if self.ang > _TWO_PI:
            self.ang -= _TWO_PI
        elif self.ang < 0:
            self.ang += _TWO_PI
        rot.x = piv.x + math.cos(self.ang) * self.tether
        rot.y = piv.y + math.sin(self.ang) * self.tether
        if self.swaps == 0 and self.t < SPAWN_GRACE and self._wall_hit(rot.x, rot.y, rot.r):
            # spawn protection never lets the swinging orb sink into a wall: it bounces off like a bumper
            self.ang = ang0
            self.rot_sign = -self.rot_sign
            rot.x = piv.x + math.cos(self.ang) * self.tether
            rot.y = piv.y + math.sin(self.ang) * self.tether

        # ---- anomalies -------------------------------------------------------
        if lvl.stretch:                                  # touching a field stretches the tether once; it then shortens slowly by itself
            kind = 0
            for z in lvl.stretch:
                if math.hypot(rot.x - z[0], rot.y - z[1]) < z[2] + rot.r * 0.5:
                    kind = 1 if z[3] > 0 else -1
            if kind:
                self.stretch_amp = TETHER * ((STRETCH_LONG if kind > 0 else STRETCH_SHORT) - 1.0)
                if self.stretch_hold <= 0:
                    self._ev("stretch", rot.x, rot.y, kind)
                self.stretch_hold = STRETCH_DECAY
                self.stretch_soft = True
                self.tether_base = TETHER + self.stretch_amp
            elif self.stretch_hold > 0:
                self.stretch_hold -= 1
                self.tether_base = TETHER + self.stretch_amp * self.stretch_hold / STRETCH_DECAY
        if lvl.growth or lvl.shrink or lvl.boost:
            for orb in (rot, piv):
                for z in lvl.growth:
                    if math.hypot(orb.x - z[0], orb.y - z[1]) < z[2] + orb.r * 0.5:
                        if orb.tr < 24:
                            orb.tr = 26.0
                            orb.tm = 2.2
                            self.tether_base = TETHER
                            self._ev("grow", orb.x, orb.y)
                        self.fx_t = FX_TIME
                for z in lvl.shrink:
                    if math.hypot(orb.x - z[0], orb.y - z[1]) < z[2] + orb.r * 0.5:
                        if orb.tr > 11:
                            orb.tr = 9.0
                            orb.tm = 0.5
                            self.tether_base = SHRINK_TETHER
                            self._ev("shrink", orb.x, orb.y)
                        self.fx_t = FX_TIME
                for z in lvl.boost:
                    if math.hypot(orb.x - z[0], orb.y - z[1]) < z[2] + orb.r * 0.5 and self.boost_t <= 0.2:
                        self.boost_t = 1.3
                        self._ev("boost", orb.x, orb.y)

        if self.fx_t > 0.0:
            self.fx_t -= dt
            if self.fx_t <= 0.0:
                self.fx_t = 0.0
                for orb in (o0, o1):
                    orb.tr = ORB_R
                    orb.tm = 1.0
                self.tether_base = TETHER
                self._ev("fx_end", rot.x, rot.y)

        for i, z in enumerate(lvl.shields):
            if not self.shield_taken[i]:
                for orb in (o0, o1):
                    if math.hypot(orb.x - z[0], orb.y - z[1]) < 20 + orb.r:
                        self.shield_taken[i] = True
                        self.shields = min(3, self.shields + 1)
                        self._ev("shield_get", z[0], z[1])
                        break

        for i, z in enumerate(lvl.stars):
            if not self.stars[i]:
                for orb in (o0, o1):
                    if math.hypot(orb.x - z[0], orb.y - z[1]) < 16 + orb.r:
                        self.stars[i] = True
                        pts = 1500 * self.combo_mult
                        self.star_pts += pts
                        self._ev("star", z[0], z[1], pts)
                        break

        # ---- timers ------------------------------------------------------------
        if self.grace > 0:
            self.grace -= dt
        if self.invuln > 0:
            self.invuln -= dt
        if self.revive_t > 0:
            self.revive_t -= dt
        if self.guard_t > 0:                       # a checkpoint resume's shield runs out on its own
            self.guard_t -= dt
            if self.guard_t <= 0:
                self.guard = False
                self.guard_walls = False
        if self.barrier_t > 0:
            self.barrier_t -= dt
            if self.barrier_t < 0.2:
                for orb in (o0, o1):
                    for (bx, by, bw, bh) in lvl.barriers:
                        if circle_rect_hit(orb.x, orb.y, orb.r + 2.0, bx, by, bw, bh):
                            self.barrier_t = 0.2
        self.near_cool -= dt

        # ---- near miss (graze) -------------------------------------------------------
        if self.near_cool <= 0 and lvl.walls:
            for orb in (o0, o1):
                if self._wall_hit(orb.x, orb.y, orb.r + 7) and not self._wall_hit(orb.x, orb.y, orb.r):
                    cell = (int(orb.x // 60), int(orb.y // 60))
                    last_t = self.grazed_cells.get(cell, -999.0)
                    dist_ok = (self.last_graze_x is None or
                               math.hypot(orb.x - self.last_graze_x, orb.y - self.last_graze_y) >= 45.0)
                    if (t - last_t >= 4.0) and dist_ok:
                        self.near_count += 1
                        self.near_pts += 450
                        self.near_cool = 0.35
                        self.last_graze_x = orb.x
                        self.last_graze_y = orb.y
                        self.grazed_cells[cell] = t
                        self._ev("graze", orb.x, orb.y)
                        break

        # ---- wall-escape recovery (sim v8): keep a shield-bounced pair protected until it is truly clear of the
        # wall it bounced off, instead of a fixed timer that can expire while still embedded ("stuck in the wall").
        if self.wall_escaping:
            self.wall_escape_t += dt
            still_stuck = self._wall_hit(o0.x, o0.y, o0.r, True) or \
                self._wall_hit(o1.x, o1.y, o1.r, True)
            if still_stuck and self.wall_escape_t < 1.0:
                self.invuln = max(self.invuln, 0.05)
            else:
                self.wall_escaping = False

        # ---- revive R3: while guarded and invulnerable after a bounce, the swinging orb still may not enter a wall
        # (an orb already inside one - the wall-escape case - is free to move out)
        if self.guard_walls and self.protected:
            if self._wall_hit(rot.x, rot.y, rot.r, True):
                ox = piv.x + math.cos(ang0) * self.tether
                oy = piv.y + math.sin(ang0) * self.tether
                if not self._wall_hit(ox, oy, rot.r, True):
                    self.ang = ang0
                    rot.x, rot.y = ox, oy
                    self.rot_sign = -self.rot_sign

        # ---- fatal collisions -----------------------------------------------------------
        if not self.protected:
            phasing = self.barrier_t > 0
            hit = self._fatal(o0, mrects, lasers, spins, phasing) or self._fatal(o1, mrects, lasers, spins, phasing)
            if hit:
                if self.shields > 0 or self.guard:
                    if not self.guard:
                        self.shields -= 1
                    if hit[3]:
                        self.barrier_t = BARRIER_PASS           # energy barrier: phase through it, whatever the orb size
                    else:
                        self.invuln = SHIELD_INVULN
                        self.rot_sign = -self.rot_sign          # ordinary hit: the shield bounces you back
                        if self._wall_hit(hit[0], hit[1], hit[2] + 1.0, True):
                            # a solid wall: throw the swinging orb back out and keep it protected until it truly clears
                            self.ang = ang0
                            rot.x = piv.x + math.cos(self.ang) * self.tether
                            rot.y = piv.y + math.sin(self.ang) * self.tether
                            self.wall_escaping = True
                            self.wall_escape_t = 0.0
                            self.invuln = WALL_SHIELD_INVULN
                    self._ev("shield_pop", hit[0], hit[1])
                else:
                    self.dead = True
                    self._ev("die", hit[0], hit[1])
                    return

        # ---- win -------------------------------------------------------------------------
        x, y, w, h = lvl.end_rect
        if circle_rect_hit(o0.x, o0.y, o0.r, x, y, w, h) or circle_rect_hit(o1.x, o1.y, o1.r, x, y, w, h):
            self.won = True
            self._ev("win")
            return

        # ---- checkpoints: lit in route order, in a clean state (same condition as a revive point)
        if self.cp_next < len(lvl.checkpoints) and self.invuln <= 0 and not self.wall_escaping and self.barrier_t <= 0:
            cx, cy = lvl.checkpoints[self.cp_next]
            if (math.hypot(o0.x - cx, o0.y - cy) < CP_RADIUS + o0.r) or (math.hypot(o1.x - cx, o1.y - cy) < CP_RADIUS + o1.r):
                self._take_checkpoint()

        # ---- revive points: a clean state (no shield / barrier / wall-escape protection active) every SNAP_EVERY steps
        if self.n % SNAP_EVERY == 0 and self.invuln <= 0 and not self.wall_escaping and self.barrier_t <= 0:
            self.snaps.append(self._snap())
            if len(self.snaps) > SNAP_KEEP:
                del self.snaps[0]

    # ---- collision helpers ----------------------------------------------------------------
    def _wall_hit(self, cx, cy, r, solid_only=False, barriers_only=False):
        wb = self.lvl.solid_buckets if solid_only else (self.lvl.barrier_buckets if barriers_only else self.lvl.wall_buckets)
        for i in range(int((cx - r) // BUCKET), int((cx + r) // BUCKET) + 1):
            for j in range(int((cy - r) // BUCKET), int((cy + r) // BUCKET) + 1):
                cell = wb.get((i, j))
                if cell:
                    for (_, x, y, w, h) in cell:
                        if circle_rect_hit(cx, cy, r, x, y, w, h):
                            return True
        return False

    def _fatal(self, o, mrects, lasers, spins, phasing=False):
        """Returns (x, y, orb radius, hit an energy barrier) or None. While phasing, barriers are ignored.
        An orb that overlaps a barrier ignores the solid walls it touches: barriers fill gaps between walls, so crossing
        one near its end grazes the neighbouring wall (at most by the orb radius - it can never pass through it)."""
        r = o.r + self.margin
        x, y = o.x, o.y
        if x < EDGE_MARGIN + self.margin or x > ARENA_W - EDGE_MARGIN - self.margin or \
           y < EDGE_MARGIN + self.margin or y > self.lvl.height - EDGE_MARGIN - self.margin:
            return (x, y, o.r, False)
        in_barrier = bool(self.lvl.barrier_walls) and self._wall_hit(x, y, r, barriers_only=True)
        if in_barrier:
            if not phasing:
                return (x, y, o.r, True)
        elif self._wall_hit(x, y, r, True):
            return (x, y, o.r, False)
        if self.lvl.breakables:
            for idx, (bx, by, bw, bh) in enumerate(self.lvl.breakables):
                if not self.broken[idx] and circle_rect_hit(x, y, r, bx, by, bw, bh):
                    if o.r >= BREAK_R:
                        self.broken[idx] = True
                        self._ev("smash", bx + bw / 2.0, by + bh / 2.0, idx)
                    else:
                        return (x, y, o.r, False)
        if self.revive_t <= 0:                           # just revived: moving hazards spare the pair
            for (mx, my, mw, mh) in mrects:
                if circle_rect_hit(x, y, r, mx, my, mw, mh):
                    return (x, y, o.r, False)
            for (x1, y1, x2, y2) in lasers:
                if circle_segment_hit(x, y, r, x1, y1, x2, y2):
                    return (x, y, o.r, False)
            for (x1, y1, x2, y2, th) in spins:
                if circle_segment_hit(x, y, r, x1, y1, x2, y2, th):
                    return (x, y, o.r, False)
        for (cx, cy, cr) in self.lvl.circles:
            if (x - cx) ** 2 + (y - cy) ** 2 < (r + cr) ** 2:
                return (x, y, o.r, False)
        return None

    def clearance(self):
        """Distance-ish measure of how close the orbs are to any hazard (px). Solver metric."""
        lvl = self.lvl
        t = self.t
        best = 999.0
        for o in self.orbs:
            x, y = o.x, o.y
            best = min(best, x - EDGE_MARGIN - o.r, ARENA_W - EDGE_MARGIN - o.r - x,
                       y - EDGE_MARGIN - o.r, lvl.height - EDGE_MARGIN - o.r - y)
            wb = lvl.wall_buckets
            rr = 60
            for i in range(int((x - rr) // BUCKET), int((x + rr) // BUCKET) + 1):
                for j in range(int((y - rr) // BUCKET), int((y + rr) // BUCKET) + 1):
                    for (_, wx, wy, ww, wh) in wb.get((i, j), ()):
                        px = wx if x < wx else (wx + ww if x > wx + ww else x)
                        py = wy if y < wy else (wy + wh if y > wy + wh else y)
                        best = min(best, math.hypot(x - px, y - py) - o.r)
            for m in lvl.moving_walls:
                wx, wy, ww, wh = lvl.moving_rect(m, t)
                px = wx if x < wx else (wx + ww if x > wx + ww else x)
                py = wy if y < wy else (wy + wh if y > wy + wh else y)
                best = min(best, math.hypot(x - px, y - py) - o.r)
            for ci, c in enumerate(lvl.chasers):
                cr_ = lvl.chaser_rect(c, self.chase_t0[ci], t)
                if cr_ is None:
                    continue
                wx, wy, ww, wh = cr_
                px = wx if x < wx else (wx + ww if x > wx + ww else x)
                py = wy if y < wy else (wy + wh if y > wy + wh else y)
                best = min(best, math.hypot(x - px, y - py) - o.r)
            for l in lvl.lasers:
                if lvl.laser_state(l, t)[0]:
                    best = min(best, _seg_dist(x, y, l[0], l[1], l[2], l[3]) - o.r - 3)
            for s in lvl.spinners:
                sg = lvl.spinner_segment(s, t)
                best = min(best, _seg_dist(x, y, *sg) - o.r - s[5] * 0.5)
            for (cx, cy, cr) in lvl.circles:
                best = min(best, math.hypot(x - cx, y - cy) - cr - o.r)
        return best


def _seg_dist(px, py, x1, y1, x2, y2):
    dx = x2 - x1
    dy = y2 - y1
    ll = dx * dx + dy * dy
    if ll == 0:
        return math.hypot(px - x1, py - y1)
    tt = ((px - x1) * dx + (py - y1) * dy) / ll
    tt = 0.0 if tt < 0 else (1.0 if tt > 1 else tt)
    return math.hypot(px - (x1 + tt * dx), py - (y1 + tt * dy))


# --------------------------------------------------------------------------- scoring
def compute_result(sim):
    """Deterministic score / rank from a finished (won) simulation."""
    lvl = sim.lvl
    stars = sim.stars_collected
    base = lvl.id * 1000
    time_bonus = max(0, int((lvl.par_time * 1.6 - sim.t) * 120))
    # Fewer swaps = more points: the efficiency bonus falls smoothly with every extra swap (par earns the full
    # amount, half of par doubles it, twice par halves it) and grows with the level. Tapping itself scores nothing.
    swap_bonus = int((3000 + 150 * lvl.id) * lvl.par_swaps / max(float(sim.swaps), lvl.par_swaps * 0.5, 1.0))
    combo_bonus = 0
    graze_bonus = sim.near_count * 450
    star_bonus = stars * 2500
    star_mult = 1.0 + stars * 0.15
    subtotal = base + time_bonus + swap_bonus + combo_bonus + graze_bonus + star_bonus
    total = int(subtotal * star_mult)
    if getattr(sim, "cp_used", 0) > 0:
        total = int(total * CP_PENALTY)       # resumed from a checkpoint: a small cut (sim v11 rule, replayed by the server)

    t_ratio = sim.t / max(1.0, lvl.par_time)
    s_ratio = sim.swaps / max(1, lvl.par_swaps)
    if stars == 3 and t_ratio <= 1.05 and s_ratio <= 1.2:
        rank = "S+"
    elif stars == 3 or (stars >= 2 and t_ratio <= 0.95):
        rank = "S"
    elif stars >= 2 or (stars >= 1 and t_ratio <= 1.25):
        rank = "A"
    elif stars >= 1:
        rank = "B"
    else:
        rank = "C"
    return {
        "base": base, "time_bonus": time_bonus, "swap_bonus": swap_bonus,
        "combo_bonus": combo_bonus, "max_combo": sim.max_combo,
        "near_miss_bonus": graze_bonus, "near_miss_count": sim.near_count,
        "star_bonus": star_bonus, "star_mult": star_mult, "level_total": total,
        "stars": stars, "time": round(sim.t, 3), "swaps": sim.swaps, "rank": rank,
    }


def replay(lvl, taps, margin=0.0, max_seconds=400.0, jitter=None, assists=None):
    """Replay a list of tap step-indices (swap applied before step number `tap`).
    `assists`: paid help as [step, "S"] (a bought shield put on the pair before that step), [step, "R2"] (the 1.0.6
    slow-spin shielded revive), [step, "R3"] (1.0.8: R2 with walls solid for the revive shield), [step, "R"] (a revive
    after dying at that step) and [step, "C"] (1.0.9: free resume from the latest lit checkpoint after dying at that step). Returns (Sim, result_dict_or_None)."""
    sim = Sim(lvl, margin=margin)
    taps = sorted(taps)
    helps = sorted(((int(a[0]), str(a[1])) for a in (assists or [])), key=lambda a: a[0])
    ti = hi = 0
    max_steps = int(max_seconds / SIM_DT)
    while sim.n < max_steps and not sim.won:
        while hi < len(helps) and helps[hi][0] <= sim.n and (helps[hi][1] == "S" or sim.dead):
            if helps[hi][1] == "S":
                sim.add_shield()
            elif helps[hi][1] == "C":
                sim.resume_checkpoint()
            else:
                sim.revive(guarded=helps[hi][1] in ("R2", "R3"), walls=helps[hi][1] == "R3")
            hi += 1
        if sim.dead:
            break
        while ti < len(taps) and taps[ti] <= sim.n:
            sim.swap()
            ti += 1
        sim.step()
    if sim.won:
        return sim, compute_result(sim)
    return sim, None
