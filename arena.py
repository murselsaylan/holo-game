"""Arena mode: survive against the clock in one big hand-made arena (no pygame in here).

The arena is one fixed map, the same for everybody (fair ranking): the screen's width and about 1.8 screens tall, three
zones stacked bottom to top, each with its own furniture built from the campaign's pieces (ledges, an island, pillars,
a ring of bumpers, power fields). On top of it the run brings hazards in waves - every WAVE_SECS a new set:
rotating lasers (spinners), side walls that squeeze in (moving walls), flashing laser bars (lasers) - in a few zones,
and radar strikes all along: a lock on the pair's position, 1.5 s later a laser cross hits that spot. Standing still
is not an option. Stars keep appearing around the pair.

Everything comes from the run's seed through a tiny integer PRNG (xorshift32) - deterministic, so the ranking server
can replay a run's taps and get the same survival time (to be mirrored in supabase/functions/scores/arena.ts).
Score: 10 points per second survived + 100 per star.
"""
import math

from sim import LevelData, Sim, SIM_DT

ARENA_VERSION = 1
W = 900.0
H = 2600.0                     # about 1.8 screens (the view is ~1400 px tall)
WALL = 40.0
ZONES = 3
ZONE_H = (H - 2 * WALL) / ZONES
START = (450.0, H - 260.0)
WAVE_SECS = 15.0               # the first wave (0..15 s) brings nothing: stars only
STRIKE_WARN = 2.5              # radar lock -> hit
FIRST_STRIKE = 10.0
STRIKE_ON = 0.4                # how long the strike's laser cross burns
STRIKE_ARM = 130.0             # half length of each arm of the cross
STAR_EVERY = 8.0
POINTS_PER_SEC = 5
# the clock: it runs down, every energy core picked up refills it - out of time is the end of the run
START_TIME = 25.0
MAX_TIME = 35.0
CORE_R = 34.0
CORE_DIST = (300.0, 560.0)     # how far from the pair the next core appears
CORE_POINTS = 100              # x the chain multiplier
CHAIN_SECS = 7.0               # a core taken this soon after it appeared raises the multiplier, a slower one resets it
CHAIN_MAX = 5
REVIVE_TIME = 10.0             # a revive after running out of time gives this much clock back
POINTS_PER_STAR = 100
MAX_STEPS = 60 * 60 * 20       # a run is cut after 20 minutes
UNLOCK_LEVEL = 5               # opens after the campaign's first few levels
CLOSE_FROM_WAVE = 999          # the storm is retired (the clock keeps the pair moving); its code stays for later
CLOSE_WARN = 2.0               # the zone flashes this long, then the storm front starts at its far end ...
CLOSE_SWEEP = 8.0              # ... and crosses the whole zone in this time (~105 px/s), until the next wave clears it
PICKUP_LIFE = 9.0              # a power field stays this long unless the pair takes it
PICKUP_EVERY = 8.0             # a random one this often (besides the ones the situation calls for)
PICKUP_MAX = 3
REVIVE_CALM = 3.0              # after a revive: no radar lock for this long, the pending ones are dropped
GUARD_STEPS = 180              # a revive's bounce-shield lasts 3 s here (score is time: waiting under it must not pay)


class Rng:
    """xorshift32: the same numbers in Python and TypeScript."""

    def __init__(self, seed):
        self.s = (int(seed) & 0xFFFFFFFF) or 0x9E3779B9

    def next(self):
        x = self.s
        x ^= (x << 13) & 0xFFFFFFFF
        x ^= x >> 17
        x ^= (x << 5) & 0xFFFFFFFF
        self.s = x & 0xFFFFFFFF
        return self.s

    def unit(self):
        return self.next() / 4294967296.0

    def uniform(self, a, b):
        return a + (b - a) * self.unit()

    def pick(self, seq):
        return seq[self.next() % len(seq)]


def zone_top(z):
    """Top y of zone z (0 = the bottom zone, where the run starts)."""
    return H - WALL - (z + 1) * ZONE_H


def zone_of(y):
    return max(0, min(ZONES - 1, int((H - WALL - y) // ZONE_H)))


def arena_dict():
    """The fixed map: frame, chamfered corners and each zone's furniture."""
    walls = [(0.0, 0.0, WALL, H), (W - WALL, 0.0, WALL, H), (0.0, 0.0, W, WALL), (0.0, H - WALL, W, WALL)]
    walls += [(WALL, WALL, 110.0, 110.0), (W - WALL - 110.0, WALL, 110.0, 110.0),           # chamfered corners
              (WALL, H - WALL - 110.0, 110.0, 110.0), (W - WALL - 110.0, H - WALL - 110.0, 110.0, 110.0)]
    rev, growth, shrink, boost = [], [], [], []
    # The middle stays open (x 300..600): the furniture hugs the side walls, the hazards come into the middle.
    # The power fields (grow / shrink / boost) are not part of the map: the run puts them where they help (_pickups).
    # zone 0 (start): two short side ledges
    y = zone_top(0)
    walls += [(WALL, y + 200.0, 170.0, 36.0), (W - WALL - 170.0, y + 470.0, 170.0, 36.0)]
    # zone 1: bumpers on both side walls, a small pillar beside each
    y = zone_top(1)
    rev += [(WALL, y + 140.0, 26.0, 140.0), (W - WALL - 26.0, y + 560.0, 26.0, 140.0)]
    walls += [(150.0, y + 560.0, 60.0, 60.0), (W - 210.0, y + 200.0, 60.0, 60.0)]
    # zone 2 (top): bumpers on the side walls, two pillars near the walls
    y = zone_top(2)
    rev += [(WALL, y + 380.0, 26.0, 140.0), (W - WALL - 26.0, y + 380.0, 26.0, 140.0)]
    walls += [(170.0, y + 660.0, 60.0, 60.0), (W - 230.0, y + 660.0, 60.0, 60.0)]
    return {
        "id": 9001, "title": "ARENA", "start": list(START), "end": [-1000.0, -1000.0], "height": H,
        "speed": 1.0, "ramp": 0.0, "par_time": 60.0, "par_swaps": 60,
        "waypoints": [list(START), [450.0, WALL + 200.0]],
        "walls": [list(w) for w in walls], "reverse_walls": [list(r) for r in rev],
        "growth_zones": [list(z) for z in growth], "shrink_zones": [list(z) for z in shrink],
        "boost_pads": [list(z) for z in boost], "stars": [], "pre_adjusted": True,
    }


class ArenaRun:
    """One arena attempt. step() once per 1/60 s, swap() on a tap - exactly like Sim."""

    def __init__(self, seed, record_events=False, margin=0.0):
        self.seed = int(seed) & 0xFFFFFFFF
        self.rng = Rng(self.seed)
        self.data = LevelData(arena_dict())
        self.sim = Sim(self.data, margin=margin, record_events=record_events)
        self.wave = -1
        self.wave_hazards = {"spinners": [], "moving_walls": [], "lasers": []}
        self.strikes = []                    # [hit time, x, y] - radar locks and their burning crosses
        self.next_strike_t = FIRST_STRIKE
        self.next_star_t = 2.0
        self.zones_hot = []                  # zones holding this wave's hazards (the HUD / view can mark them)
        self.guard_steps = 0
        self.close = None                    # [zone, started at, ends at, exit is up] - the storm of this wave
        self.pickups = []                    # [kind "grow" / "shrink" / "boost", x, y, born, gone at]
        self.time_left = START_TIME
        self.core = None                     # [x, y, appeared at] - the energy core to reach next
        self.cores = 0
        self.chain = 0
        self.core_pts = 0
        self.timed_out = False
        self.next_pickup_t = 6.0

    # -- queries
    @property
    def n(self):
        return self.sim.n

    @property
    def dead(self):
        return self.sim.dead

    @property
    def seconds(self):
        return self.sim.n * SIM_DT

    @property
    def stars(self):
        return sum(1 for x in self.sim.stars if x)

    @property
    def points(self):
        return int(self.seconds) * POINTS_PER_SEC + self.stars * POINTS_PER_STAR + self.core_pts

    def core_secs(self):
        """Clock refill of the next core: 7 s at first, 5 s from the 20th core on."""
        return 7.0 - 0.1 * min(self.cores, 20)

    @property
    def tier(self):
        return max(0, self.wave)

    def storm_rect(self, t=None):
        """The storm's deadly block (x, y, w, h) at time t, or None (no storm / still only flashing)."""
        c = self.close
        t = self.sim.t if t is None else t
        if c is None or t >= c[2]:
            return None
        k = (t - c[1] - CLOSE_WARN) / CLOSE_SWEEP
        if k <= 0.0:
            return None
        h = ZONE_H * min(1.0, k)
        top = zone_top(c[0])
        y = top + ZONE_H - h if c[3] else top            # exit up: it rises from the zone's floor
        return (WALL, y, W - 2 * WALL, h)

    def closing(self):
        """(zone, "warn" / "storm", exit is up) while this wave's storm runs, else None (for the view and banners)."""
        c, t = self.close, self.sim.t
        if c is None or t >= c[2]:
            return None
        return c[0], ("warn" if t < c[1] + CLOSE_WARN else "storm"), c[3]

    def target_y(self):
        """While a storm runs: the middle of the zone its exit leads to (the view's arrow, a bot's goal), else None."""
        cl = self.closing()
        if cl is None:
            return None
        return zone_top(cl[0] + 1 if cl[2] else cl[0] - 1) + ZONE_H / 2

    def warnings(self):
        """Radar locks still waiting to hit: [(x, y, 0..1 how close the hit is)] (for the view)."""
        t = self.sim.t
        return [(x, y, 1.0 - (hit - t) / STRIKE_WARN) for hit, x, y in self.strikes if t < hit]

    # -- input / physics
    def swap(self):
        self.sim.swap()

    def revive(self, guarded=True):
        """A paid revive: the pair goes back to a safe spot (Sim.revive) and the radar calms down for a moment -
        the locks still waiting would otherwise hit the spot the pair has just been put back to."""
        self.sim.revive(guarded=guarded)
        if self.timed_out:                   # out of time: the revive buys some clock
            self.timed_out = False
            self.time_left = max(self.time_left, REVIVE_TIME)
        self.strikes = []
        self.next_strike_t = max(self.next_strike_t, self.sim.t + REVIVE_CALM)
        if self.close is not None and zone_of(self.sim.pivot.y) == self.close[0]:
            self.close = None                # put back inside the closed zone: it opens
        self._sync(self.sim.t)

    def step(self):
        s = self.sim
        if s.dead:
            return
        t = s.t + SIM_DT                     # the time the coming step simulates
        if t >= (self.wave + 1) * WAVE_SECS:
            self._new_wave(t)
        if t >= self.next_strike_t:
            self._strike(t)
        if t >= self.next_star_t:
            self._star(t)
        if self.core is None:
            self._spawn_core(t)
        if t >= self.next_pickup_t:
            self._pickup(t, self.rng.pick(("shrink", "boost", "shrink", "grow")), 260.0, 520.0)
            self.next_pickup_t = t + PICKUP_EVERY
        self._sync(t)
        s.lvl.speed = min(1.3, 1.0 + 0.03 * self.tier)
        if s.guard:
            self.guard_steps += 1
            if self.guard_steps > GUARD_STEPS:
                s.guard = False
        else:
            self.guard_steps = 0
        s.step()
        self._take_pickups()
        if s.dead:
            return
        self._take_core(t)
        self.time_left -= SIM_DT
        if self.time_left <= 0.0:            # out of time: the run ends like a crash (a revive can buy clock)
            self.time_left = 0.0
            self.timed_out = True
            s.dead = True
            s._ev("die", s.pivot.x, s.pivot.y)

    # -- the run's hazards
    def _sync(self, t):
        """The level's hazard lists = this wave's set + the radar crosses still to come / burning."""
        lv = self.data
        self.strikes = [st for st in self.strikes if t < st[0] + STRIKE_ON + 0.05]
        lasers = list(self.wave_hazards["lasers"])
        for hit, x, y in self.strikes:
            period = 1000.0
            phase = (-hit) % period          # cycle = t - hit: burning for STRIKE_ON after the hit
            ratio = STRIKE_ON / period
            lasers.append((x - STRIKE_ARM, y, x + STRIKE_ARM, y, period, ratio, phase))
            lasers.append((x, y - STRIKE_ARM, x, y + STRIKE_ARM, period, ratio, phase))
        lv.lasers = lasers
        lv.spinners = self.wave_hazards["spinners"]
        walls = self.wave_hazards["moving_walls"]
        st = self.storm_rect(t)
        if st is not None:                               # the storm: one deadly block growing over the zone
            walls = walls + [st + (0.0, 0.0, 0.0, 0.0)]
        lv.moving_walls = walls
        self.pickups = [pk for pk in self.pickups if t < pk[4]]
        lv.growth = [(pk[1], pk[2], 32.0) for pk in self.pickups if pk[0] == "grow"]
        lv.shrink = [(pk[1], pk[2], 30.0) for pk in self.pickups if pk[0] == "shrink"]
        lv.boost = [(pk[1], pk[2], 28.0) for pk in self.pickups if pk[0] == "boost"]

    def _blocked(self, x, y, pad):
        """True when (x, y) lies within `pad` of a wall or anywhere this wave's hazards sweep (a spinner's whole
        circle, a squeeze wall's whole stroke, a laser bar's line) or a radar cross still to come."""
        if self.sim._wall_hit(x, y, pad):
            return True
        haz = self.wave_hazards
        for s_ in haz["spinners"]:
            if math.hypot(x - s_[0], y - s_[1]) < s_[2] + pad:
                return True
        for m in haz["moving_walls"]:
            ax, ay = abs(m[4]), abs(m[5])
            if m[0] - ax - pad < x < m[0] + m[2] + ax + pad and m[1] - ay - pad < y < m[1] + m[3] + ay + pad:
                return True
        for l in haz["lasers"]:
            if min(l[0], l[2]) - pad < x < max(l[0], l[2]) + pad and min(l[1], l[3]) - pad < y < max(l[1], l[3]) + pad:
                return True
        for hit, sx, sy in self.strikes:
            if (abs(x - sx) < STRIKE_ARM + pad and abs(y - sy) < pad) or (abs(y - sy) < STRIKE_ARM + pad and abs(x - sx) < pad):
                return True
        return False

    def _spawn_core(self, t):
        r = self.rng
        p = self.sim.pivot
        for i in range(24):
            d = r.uniform(*CORE_DIST) * (1.0 if i < 14 else 0.6)
            a = r.uniform(0.0, 6.283)
            x = min(W - WALL - 90.0, max(WALL + 90.0, p.x + math.cos(a) * d))
            y = min(H - WALL - 90.0, max(WALL + 90.0, p.y + math.sin(a) * d))
            if math.hypot(x - p.x, y - p.y) > 250.0 and not self._blocked(x, y, CORE_R + 50.0):
                self.core = [x, y, t]
                return
        self.core = [W / 2.0, zone_top(zone_of(p.y)) + ZONE_H / 2.0, t]       # fallback: the zone's open middle

    def _take_core(self, t):
        c = self.core
        if c is None or not any(math.hypot(o.x - c[0], o.y - c[1]) < CORE_R + o.r for o in self.sim.orbs):
            return
        fast = t - c[2] <= CHAIN_SECS
        self.chain = min(CHAIN_MAX, self.chain + 1) if fast else 1
        gain = self.core_secs()
        self.time_left = min(MAX_TIME, self.time_left + gain)
        self.cores += 1
        self.core_pts += CORE_POINTS * self.chain
        self.sim._ev("core", c[0], c[1], self.chain, gain)
        self.core = None

    def _take_pickups(self):
        """A field the pair has touched (Sim's own rule) is used up: it disappears."""
        if not self.pickups:
            return
        orbs = self.sim.orbs
        rad = {"grow": 32.0, "shrink": 30.0, "boost": 28.0}
        self.pickups = [pk for pk in self.pickups
                        if not any(math.hypot(o.x - pk[1], o.y - pk[2]) < rad[pk[0]] + o.r * 0.5 for o in orbs)]

    def _pickup(self, t, kind, dmin, dmax, toward=None):
        """Put a power field dmin..dmax px from the pair (towards a height if given), in free space, out of the storm."""
        if len(self.pickups) >= PICKUP_MAX:
            return
        r = self.rng
        p = self.sim.pivot
        for _ in range(10):
            d = r.uniform(dmin, dmax)
            if toward is None:
                a = r.uniform(0.0, 6.283)
            else:
                a = (-math.pi / 2 if toward < p.y else math.pi / 2) + r.uniform(-0.6, 0.6)
            x = min(W - WALL - 80.0, max(WALL + 80.0, p.x + math.cos(a) * d))
            y = min(H - WALL - 80.0, max(WALL + 80.0, p.y + math.sin(a) * d))
            c = self.close
            if toward is None and c is not None and t < c[2] and zone_of(y) == c[0]:
                continue
            if self._blocked(x, y, 60.0) or any(math.hypot(x - q[1], y - q[2]) < 120.0 for q in self.pickups) or \
                    (self.core is not None and math.hypot(x - self.core[0], y - self.core[1]) < 130.0):
                continue
            self.pickups.append([kind, x, y, t, t + PICKUP_LIFE])
            return

    def _new_wave(self, t):
        self.wave += 1
        r = self.rng
        k = self.wave
        here = zone_of(self.sim.pivot.y)
        others = [z for z in range(ZONES) if z != here]
        closing = k >= CLOSE_FROM_WAVE
        if closing:                          # a storm sweeps the pair's zone towards its nearer exit
            py = self.sim.pivot.y
            up = here + 1 < ZONES and (here == 0 or py < zone_top(here) + ZONE_H / 2)
            self.close = [here, t, (k + 1) * WAVE_SECS, up]
            exit_y = zone_top(here + 1 if up else here - 1) + ZONE_H / 2
            self._pickup(t, "boost", 150.0, 260.0, toward=exit_y)
            if self.sim.fx_t > 0 and self.sim.orbs[0].tr < 12:
                self._pickup(t, "grow", 120.0, 220.0, toward=exit_y)
        n_far = 0 if k == 0 else (1 if k < 5 else 2)
        zones = []
        for _ in range(n_far):
            z = r.pick(others)
            others.remove(z)
            zones.append(z)
        if not closing and k > 0:
            zones.append(here)
        kinds = ["spin"] if k <= 1 else (["spin", "squeeze"] if k < 4 else ["spin", "squeeze", "laser"])
        haz = {"spinners": [], "moving_walls": [], "lasers": []}
        for z in zones:
            self._place(haz, r.pick(kinds), z, t, z == here)
        self.wave_hazards = haz
        self.zones_hot = zones
        c = self.core
        if c is not None and self._blocked(c[0], c[1], CORE_R + 30.0):
            born = c[2]
            self._spawn_core(t)
            self.core[2] = born
        self.pickups = [pk for pk in self.pickups if not self._blocked(pk[1], pk[2], 40.0)]
        if here in zones:
            self._pickup(t, "shrink", 180.0, 320.0)

    def _place(self, haz, kind, z, t, near_pair):
        r = self.rng
        k = self.tier
        y0 = zone_top(z)
        px, py = self.sim.pivot.x, self.sim.pivot.y
        if kind == "spin":
            count = 1 + min(2, k // 3)
            for i in range(count):
                cy = y0 + ZONE_H * (i + 1) / (count + 1)
                cx = r.uniform(300.0, W - 300.0)
                hlen = 150.0 + 12.0 * min(k, 8)
                if near_pair and math.hypot(cx - px, cy - py) < hlen + 170.0:
                    cy = y0 + 160.0 if py > y0 + ZONE_H / 2 else y0 + ZONE_H - 160.0
                omega = (0.9 + 0.08 * min(k, 8)) * (1 if r.next() & 1 else -1)
                haz["spinners"].append((cx, cy, hlen, omega, r.uniform(0.0, 6.283), 10.0))
        elif kind == "squeeze":
            speed = 0.7 + 0.05 * min(k, 8)
            reach = 120.0 + 10.0 * min(k, 8)
            phase = -math.pi / 2.0 - t * speed                  # starts fully retracted
            for side in (0, 1):
                ym = y0 + r.uniform(220.0, ZONE_H - 340.0)
                x0 = WALL - 40.0 if side == 0 else W - WALL - 160.0 + 40.0
                rng_x = reach if side == 0 else -reach
                haz["moving_walls"].append((x0 + rng_x / 2.0, ym, 160.0, 120.0,
                                            abs(rng_x) / 2.0 * (1 if side == 0 else -1), 0.0, speed, phase))
        else:                                                    # flashing laser bars across the zone
            period = 3.2 - 0.12 * min(k, 8)
            ratio = 0.32 + 0.02 * min(k, 8)
            for i in range(2):
                y = y0 + ZONE_H * (i + 1) / 3.0
                phase = (ratio * period + 0.15 - t) % period    # just switched off: ~2 s before it first fires
                haz["lasers"].append((WALL, y, W - WALL, y, period, ratio, phase))

    def _strike(self, t):
        p = self.sim.pivot
        self.strikes.append([t + STRIKE_WARN, p.x, p.y])
        self.next_strike_t = t + max(3.2, 6.5 - 0.25 * self.tier)

    def _star(self, t):
        r = self.rng
        p = self.sim.pivot
        for _ in range(8):
            x = min(W - WALL - 70.0, max(WALL + 70.0, p.x + r.uniform(-350.0, 350.0)))
            y = min(H - WALL - 70.0, max(WALL + 70.0, p.y + r.uniform(-650.0, 650.0)))
            c = self.close
            if c is not None and t < c[2] and zone_of(y) == c[0]:
                continue                     # never into the zone the storm is sweeping
            if math.hypot(x - p.x, y - p.y) > 170.0 and not self._blocked(x, y, 50.0) and \
                    (self.core is None or math.hypot(x - self.core[0], y - self.core[1]) > 110.0):
                self.data.stars.append((x, y))
                self.sim.stars.append(False)
                break
        self.next_star_t = t + STAR_EVERY


MAX_REVIVES = 3                # paid revives per run, like the endless climb


def replay(seed, taps, end_step=None, max_steps=MAX_STEPS, assists=None):
    """Server side check: the run's taps on a fresh arena; returns the finished ArenaRun. `assists` as in
    endless.replay: [step, "S"] a bought shield, [step, "R2"] a revive after dying at that step."""
    run = ArenaRun(seed)
    taps = sorted(taps)
    helps = sorted(((int(a[0]), str(a[1])) for a in (assists or [])), key=lambda a: a[0])
    limit = max_steps if end_step is None else min(max_steps, int(end_step))
    i = hi = 0
    while run.n < limit:
        while hi < len(helps) and helps[hi][0] <= run.n and (helps[hi][1] == "S" or run.dead):
            if helps[hi][1] == "S":
                run.sim.add_shield()
            else:
                run.revive(guarded=helps[hi][1] in ("R2", "R3"))
            hi += 1
        if run.dead:
            break
        while i < len(taps) and taps[i] <= run.n:
            run.swap()
            i += 1
        run.step()
    return run
