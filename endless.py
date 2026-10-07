"""Endless mode: one never-ending climb stitched from the campaign's own maps (no pygame in here).

The world is deterministic for a seed and mirrored line by line in supabase/functions/scores/endless.ts, so the ranking
server replays a run's taps and measures the same height. Every climb gets a new map: the seed is the ISO week (the
ranking week) plus a random nonce the game picks for that run and sends along with its taps.

Layout: stage k is a campaign level (vertically flipped when its exit lies below its start, so every stage climbs),
its hazards filtered to the tier the climb has reached, with a tunnel cut from its start room down to its bottom
edge and from its exit up to its top edge. Stages are stacked upwards with an open connector chamber between them.
Coordinates are absolute and never shift: stage 0's bottom sits at Y_BASE and the climb heads towards y = 0 (which
no run can ever reach). Only a window of WINDOW stages is simulated; when the pivot enters the window's third stage
the lowest stage is dropped and the next one appended - the physics does not notice (objects keep their absolute
coordinates, per-object state is carried over), the window floor is simply lethal like the level floor always was.
"""
import copy
import datetime
import json
import os

from sim import ARENA_W, LevelData, Sim, LEVELS_DIR, MAX_LEVELS, SPAWN_GRACE, SIM_DT

ENDLESS_VERSION = 3            # v3 (1.0.7): the climb starts faster (speed floor 1.10); the server also takes v2
Y_BASE = 10_000_000.0          # bottom of stage 0 (the climb goes towards y = 0)
GAP = 640.0                    # connector chamber between two stages (roomy: the pair crosses it sideways)
TUNNEL = 340.0                 # width of the tunnels cut into a stage's start / exit rooms
SIDE = 45.0                    # connector side walls
WINDOW = 4                     # simulated stages: the one behind, the current one and two ahead
PX_PER_M = 10.0
MAX_STEPS = 60 * 60 * 25       # a run is cut after 25 minutes
POINTS_PER_M = 10               # climb score: 10 points per metre ...
POINTS_PER_STAR = 100           # ... and 100 per star collected
DIAMOND_EVERY_M = 500          # 1 diamond per 500 m of a run (server side, capped per day)
DIAMONDS_PER_DAY = 20
UNLOCK_LEVEL = 10              # the mode opens once this campaign level is cleared
SPAWN_GRACE_STEPS = int(SPAWN_GRACE / SIM_DT)

POOL_FILE = os.path.join(LEVELS_DIR, "endless_pool.json")

# hazard families and the tier from which they appear (a tier lasts two stages)
FAMILY_TIER = {
    "reverse_walls": 1, "moving_walls": 1,
    "circles": 2,
    "growth_zones": 3, "breakables": 3, "barriers": 3, "shields": 3,
    "shrink_zones": 4, "boost_pads": 4, "chasers": 4,
    "lasers": 5, "spinners": 5,
}
MAX_TIER = 7                   # 0-5: families unlock two stages apart; 6: all (stage 12-19); 7: stage 20+, top speed
RECT_KEYS = ("walls", "reverse_walls", "breakables", "barriers")
POINT_KEYS = ("circles", "growth_zones", "shrink_zones", "boost_pads", "shields")
STATE_KEYS = ("breakables", "chasers", "shields", "stars")  # lists whose objects carry per-run state in Sim


def tier_of(k):
    return 7 if k >= 20 else min(6, k // 2)


SPEED_FLOOR = 1.10             # v3: the first stages no longer crawl (v2 started at 0.95); same curve from stage 7 on


def stage_speed(k):
    """The climb's speed does not depend on the map: it starts briskly and tops out at the campaign's final speed."""
    return min(1.50, max(SPEED_FLOOR, 0.95 + 0.022 * k))


def tier_max_speed(t):
    return stage_speed(2 * t + 1) if t < 6 else (stage_speed(19) if t == 6 else stage_speed(10 ** 6))


def fnv1a(text):
    h = 0x811C9DC5
    for b in text.encode("utf-8"):
        h ^= b
        h = (h * 0x01000193) & 0xFFFFFFFF
    return h


def week_of(unix_s):
    """ISO week of a UTC timestamp, e.g. '2026-W39' - the ranking week and the world's seed."""
    d = datetime.datetime.fromtimestamp(int(unix_s), datetime.timezone.utc).date()
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def seed_of(week, nonce=""):
    """The world's seed: the ranking week + the run's own nonce (8-16 hex digits; "" = the week's base map)."""
    base = f"HOLO-ENDLESS|{week}|v{ENDLESS_VERSION}"
    return f"{base}|{nonce}" if nonce else base


def new_nonce():
    import secrets
    return secrets.token_hex(8)


RECENT_KEEP = 8                # a new climb never opens with a map one of the last RECENT_KEEP climbs opened with


def fresh_nonce(week, recent=()):
    """A nonce whose climb starts on a map none of the recent climbs started on -> (nonce, its first map id).
    Every nonce is already a different stage sequence; this also keeps the first thing the player sees new."""
    seen = set(recent)
    for _ in range(200):
        n = new_nonce()
        first = plan(seed_of(week, n), 1)[0]
        if first not in seen:
            return n, first
    return n, first


# ------------------------------------------------------------------------------------------------ level sources
_RAW = {}
_POOL = None


def raw_level(level_id):
    d = _RAW.get(level_id)
    if d is None:
        with open(os.path.join(LEVELS_DIR, f"level{level_id}.json"), "r", encoding="utf-8") as f:
            d = json.load(f)
        _RAW[level_id] = d
    return d


def pool():
    """{tier: [level ids]} - the maps checked to be passable at that tier's hazards and top speed."""
    global _POOL
    if _POOL is None:
        try:
            with open(POOL_FILE, "r", encoding="utf-8") as f:
                p = json.load(f)
            _POOL = {int(k): [int(x) for x in v] for k, v in p["tiers"].items()}
        except (OSError, ValueError, KeyError):
            _POOL = {t: list(range(1, MAX_LEVELS + 1)) for t in range(MAX_TIER + 1)}
    return _POOL


_STARS = None


def pool_stars():
    """{(tier, level id): [[x, y], ...]} - the collectable stars of each stage (stage coordinates, whole pixels),
    placed once by tools/endless_pool.py (make_stars) and shipped in the pool file."""
    global _STARS
    if _STARS is None:
        _STARS = {}
        try:
            with open(POOL_FILE, "r", encoding="utf-8") as f:
                p = json.load(f)
            for t, per in p.get("stars", {}).items():
                for lid, pts in per.items():
                    _STARS[(int(t), int(lid))] = [[int(a), int(b)] for a, b in pts]
        except (OSError, ValueError, KeyError):
            _STARS = {}
    return _STARS


def pool_digest():
    """Short hash of the pool in use (maps and their stars): the server refuses climbs from another pool."""
    pl = pool()
    txt = json.dumps({str(k): pl[k] for k in sorted(pl)}, separators=(",", ":"))
    st = pool_stars()
    if st:
        per = {}
        for (t, lid) in sorted(st):
            per.setdefault(str(t), {})[str(lid)] = st[(t, lid)]
        txt += "|" + json.dumps(per, separators=(",", ":"))
    return "%08x" % fnv1a(txt)


def set_pool(p, stars=None):
    """Tests / tools: use another pool ({tier: [ids]}, optional {(tier, id): stars}); None reloads the file."""
    global _POOL, _STARS
    _POOL = None if p is None else {int(k): list(v) for k, v in p.items()}
    _STARS = None if p is None else dict(stars or {})


RAMP_STAGES = 24               # the maps picked climb from the tier's easiest to its hardest over this many stages
NO_REPEAT = 6                  # a map does not come back within this many stages


def plan(seed, count, prev_plan=None):
    """Level ids of stages 0..count-1 (deterministic). Each tier's pool is ordered easiest first (campaign order);
    stage k picks from a window that slides towards the hard end as the climb goes on, and never repeats one of the
    last NO_REPEAT maps. Integer maths only (mirrored in endless.ts)."""
    out = list(prev_plan or [])
    pl = pool()
    for k in range(len(out), count):
        choices = pl[tier_of(k)]
        n = len(choices)
        center = min(n - 1, (n - 1) * k // RAMP_STAGES)
        lo = max(0, center - (3 * n) // 10)
        hi = min(n, max(lo + 1, center + n // 5 + 1))
        w = hi - lo
        i0 = fnv1a(f"{seed}|{k}") % w
        recent = out[-NO_REPEAT:]
        pick = choices[lo + i0]
        for j in range(w):
            c = choices[lo + (i0 + j) % w]
            if c not in recent:
                pick = c
                break
        out.append(pick)
    return out


# ------------------------------------------------------------------------------------------------ stage geometry
def _sub_rect(rect, cut):
    """rect minus cut (both x, y, w, h) as up to 4 rects."""
    x, y, w, h = rect[:4]
    cx, cy, cw, ch = cut
    ix0, iy0 = max(x, cx), max(y, cy)
    ix1, iy1 = min(x + w, cx + cw), min(y + h, cy + ch)
    if ix0 >= ix1 or iy0 >= iy1:
        return [list(rect)]
    out = []
    if y < iy0:
        out.append([x, y, w, iy0 - y])
    if iy1 < y + h:
        out.append([x, iy1, w, y + h - iy1])
    if x < ix0:
        out.append([x, iy0, ix0 - x, iy1 - iy0])
    if ix1 < x + w:
        out.append([ix1, iy0, x + w - ix1, iy1 - iy0])
    return [p for p in out if p[2] > 1.0 and p[3] > 1.0]


def _overlap(r, c):
    return r[0] < c[0] + c[2] and c[0] < r[0] + r[2] and r[1] < c[1] + c[3] and c[1] < r[1] + r[3]


def _is_barrier_wall(w, barriers):
    return any(all(abs(a - b) <= 1.0 for a, b in zip(w[:4], bb[:4])) for bb in barriers)


def _flip(d):
    """Mirror a level vertically (its exit lies below its start): every stage then climbs."""
    h = float(d["height"])

    def pt(p):
        return [p[0], h - p[1]] + list(p[2:])

    def rc(r):
        return [r[0], h - r[1] - r[3], r[2], r[3]] + list(r[4:])

    d["start"], d["end"] = pt(d["start"]), pt(d["end"])
    d["waypoints"] = [pt(p) for p in d.get("waypoints", [])]
    for key in RECT_KEYS:
        d[key] = [rc(r) for r in d.get(key, [])]
    for key in POINT_KEYS + ("stars",):
        d[key] = [pt(p) for p in d.get(key, [])]
    d["lasers"] = [[l[0], h - l[1], l[2], h - l[3]] + list(l[4:]) for l in d.get("lasers", [])]
    # a mirrored spinner turns the other way from the mirrored angle: negate its speed and its phase
    d["spinners"] = [[s[0], h - s[1], s[2], -s[3], -s[4]] + list(s[5:]) if len(s) > 4 else [s[0], h - s[1], s[2], -s[3]]
                     for s in d.get("spinners", [])]
    mv = []
    for m in d.get("moving_walls", []):
        m = list(m) + [0.0] * (8 - len(m)) if len(m) < 8 else list(m)
        q = rc(m)
        if len(q) > 8:
            q[9] = q[9] + 3.141592653589793                 # y swing mirrored: half a period later
        else:
            q = q[:8] + [q[6], q[7] + 3.141592653589793]      # own y frequency (= the shared one), mirrored phase
        mv.append(q)
    d["moving_walls"] = mv
    ch = []
    for c in d.get("chasers", []):
        c = list(c) + [0.0] * (11 - len(c))
        q = rc(c)
        q[5] = -q[5]
        q[7] = h - c[7] - c[9]
        ch.append(q)
    d["chasers"] = ch


def build_stage(level_id, tier, first=False):
    """A campaign map as an endless stage, in its own coordinates (0 = top edge): filtered to `tier`, climbing,
    tunnels cut. Spinners / chasers are final (LevelData 'pre_adjusted')."""
    d = copy.deepcopy(raw_level(level_id))
    for key, t in FAMILY_TIER.items():
        if tier < t:
            if key == "barriers" and d.get("barriers"):
                d["walls"] = [w for w in d.get("walls", []) if not _is_barrier_wall(w, d["barriers"])]
            d[key] = []
    d["stars"] = []
    if d["end"][1] > d["start"][1]:
        _flip(d)
    h = float(d["height"])
    sx, sy = d["start"][:2]
    ex, ey = d["end"][:2]
    cuts = [[ex - TUNNEL / 2, -10.0, TUNNEL, ey + 120.0]]
    if not first:
        cuts.append([sx - TUNNEL / 2, sy - 110.0, TUNNEL, h - sy + 120.0])
    bars = d.get("barriers", [])
    # anything but plain walls inside a tunnel is removed; plain walls are cut
    d["barriers"] = [b for b in bars if not any(_overlap(b, c) for c in cuts)]
    walls = []
    for w in d.get("walls", []):
        if _is_barrier_wall(w, bars):
            if _is_barrier_wall(w, d["barriers"]):
                walls.append(list(w))
            continue
        pieces = [list(w)]
        for c in cuts:
            pieces = [p for q in pieces for p in _sub_rect(q, c)]
        walls.extend(pieces)
    d["walls"] = walls
    for key in ("reverse_walls", "breakables"):
        d[key] = [r for r in d.get(key, []) if not any(_overlap(r, c) for c in cuts)]
    d["circles"] = [z for z in d.get("circles", [])
                    if not any(_overlap([z[0] - z[2], z[1] - z[2], 2 * z[2], 2 * z[2]], c) for c in cuts)]
    # final spinner / chaser geometry measured in the stage alone, so it never depends on the window around it
    ld = LevelData(d)
    d["spinners"] = [list(s) for s in ld.spinners]
    d["chasers"] = [list(c) for c in ld.chasers]
    d["pre_adjusted"] = True
    d["_level"] = level_id
    d["_tier"] = tier
    return d


FILL_KEYS = ("walls", "reverse_walls", "breakables", "barriers", "moving_walls")
HAZARD_KEYS = ("circles", "growth_zones", "shields", "shrink_zones", "boost_pads", "chasers", "lasers", "spinners",
               "moving_walls", "reverse_walls")
MIN_FILL = 0.12                # share of the stage covered by walls ...
MIN_HAZARDS = 3.0              # ... or hazards per 1000 px: a map whose challenge was all hazards the tier removes is empty


def has_content(level_id, tier):
    """False when the stage would be (nearly) empty at this tier - an open field with nothing to swing around.
    Used when the pool is made (tools/endless_pool.py); the game only reads the pool."""
    d = build_stage(level_id, tier)
    h = float(d["height"])
    fill = sum(r[2] * r[3] for k in FILL_KEYS for r in d.get(k, [])) / (ARENA_W * h)
    hz = 1000.0 * sum(len(d.get(k, [])) for k in HAZARD_KEYS) / h
    return fill >= MIN_FILL or hz >= MIN_HAZARDS


STAR_CLEAR = 40.0              # a placed star keeps this far from anything solid or dangerous
STAR_SPACING = 240.0           # ... and this far from the other stars
STAR_EVERY = 330.0             # about one star per this many pixels of stage height


def _clearance(d, x, y):
    """Distance from (x, y) to the nearest wall / hazard of a built stage (moving parts padded by their reach)."""
    best = 1e9
    for key in ("walls", "reverse_walls", "breakables", "barriers"):
        for r in d.get(key, []):
            dx = max(r[0] - x, 0.0, x - (r[0] + r[2]))
            dy = max(r[1] - y, 0.0, y - (r[1] + r[3]))
            best = min(best, (dx * dx + dy * dy) ** 0.5)
    for m in d.get("moving_walls", []):
        reach = max(abs(m[4]) if len(m) > 4 else 0.0, abs(m[5]) if len(m) > 5 else 0.0) + 20.0
        dx = max(m[0] - reach - x, 0.0, x - (m[0] + m[2] + reach))
        dy = max(m[1] - reach - y, 0.0, y - (m[1] + m[3] + reach))
        best = min(best, (dx * dx + dy * dy) ** 0.5)
    for c in d.get("circles", []):
        best = min(best, ((c[0] - x) ** 2 + (c[1] - y) ** 2) ** 0.5 - c[2])
    for sp in d.get("spinners", []):
        best = min(best, ((sp[0] - x) ** 2 + (sp[1] - y) ** 2) ** 0.5 - sp[2] - 10.0)
    for c in d.get("chasers", []):
        best = min(best, ((c[0] - x) ** 2 + (c[1] - y) ** 2) ** 0.5 - 120.0)
    for l in d.get("lasers", []):
        ax, ay, bx, by = l[0], l[1], l[2], l[3]
        vx, vy = bx - ax, by - ay
        ll = vx * vx + vy * vy
        t = 0.0 if ll == 0 else max(0.0, min(1.0, ((x - ax) * vx + (y - ay) * vy) / ll))
        best = min(best, ((ax + t * vx - x) ** 2 + (ay + t * vy - y) ** 2) ** 0.5 - 8.0)
    return best


def make_stars(level_id, tier):
    """Where a stage's collectable stars go (stage coordinates): the map's own three stars, then more along the
    map's route wherever there is room, about one per STAR_EVERY px of height. Tools only - the result is shipped."""
    raw = raw_level(level_id)
    h = float(raw["height"])
    flip = raw["end"][1] > raw["start"][1]
    out = [[float(p[0]), h - float(p[1]) if flip else float(p[1])] for p in raw.get("stars", [])]
    d = build_stage(level_id, tier)
    route = [list(d["start"])] + [list(p) for p in d.get("waypoints", [])] + [list(d["end"]), [d["end"][0], 60.0]]
    want = max(len(out), int(h / STAR_EVERY))
    samples = []
    for a, b in zip(route, route[1:]):
        seg = ((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5
        n = max(1, int(seg / 80.0))
        samples += [[a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n] for i in range(n)]
    for x, y in samples:
        if len(out) >= want:
            break
        if not (80.0 < y < h - 80.0 and 60.0 < x < ARENA_W - 60.0):
            continue
        if any(((x - p[0]) ** 2 + (y - p[1]) ** 2) ** 0.5 < STAR_SPACING for p in out):
            continue
        if _clearance(d, x, y) >= STAR_CLEAR:
            out.append([x, y])
    return [[int(round(x)), int(round(y))] for x, y in out]


class Stage:
    """A placed stage: absolute top y, geometry shifted there, per-list object counts."""
    __slots__ = ("k", "level", "tier", "top", "bottom", "height", "d", "speed", "counts", "route")

    def __init__(self, k, level_id, bottom):
        self.k = k
        self.level = level_id
        self.tier = tier_of(k)
        local = build_stage(level_id, self.tier, first=(k == 0))
        self.height = float(local["height"])
        self.bottom = bottom
        self.top = bottom - self.height
        self.speed = stage_speed(k)
        oy = self.top
        d = {"start": [local["start"][0], local["start"][1] + oy], "end": [local["end"][0], local["end"][1] + oy]}
        for key in RECT_KEYS:
            d[key] = [[r[0], r[1] + oy] + list(r[2:]) for r in local.get(key, [])]
        for key in POINT_KEYS:
            d[key] = [[p[0], p[1] + oy] + list(p[2:]) for p in local.get(key, [])]
        d["moving_walls"] = [[m[0], m[1] + oy] + list(m[2:]) for m in local.get("moving_walls", [])]
        d["lasers"] = [[l[0], l[1] + oy, l[2], l[3] + oy] + list(l[4:]) for l in local.get("lasers", [])]
        d["spinners"] = [[s[0], s[1] + oy] + list(s[2:]) for s in local.get("spinners", [])]
        d["chasers"] = [[c[0], c[1] + oy] + list(c[2:6]) + [c[6], c[7] + oy] + list(c[8:]) for c in local.get("chasers", [])]
        # collectable stars: the stage's own, plus one in the open chamber below it (on the way into its tunnel)
        stars = [list(p) for p in pool_stars().get((self.tier, level_id), [])]
        if k > 0:
            stars.append([local["start"][0], self.height + GAP * 0.45])
        d["stars"] = [[p[0], p[1] + oy] for p in stars]
        self.d = d
        self.counts = {key: len(d[key]) for key in STATE_KEYS}
        # the way through (bots / QA only, not physics): up the entry tunnel, the map's own route, out of the exit
        pts = ([[local["start"][0], self.bottom + GAP * 0.5]] if k > 0 else []) + [d["start"]]
        pts += [[p[0], p[1] + oy] for p in local.get("waypoints", [])] + [d["end"], [local["end"][0], self.top - GAP * 0.5]]
        self.route = pts


class World:
    """The stage sequence of one seed (built on demand, the old ones forgotten)."""

    def __init__(self, seed):
        self.seed = seed
        self.ids = []
        self.stages = {}
        self._bottoms = [Y_BASE]
        self.keep = False                  # bots: keep every stage (their clones sit at different heights)

    def stage(self, k):
        s = self.stages.get(k)
        if s is not None:
            return s
        if len(self.ids) <= k:
            self.ids = plan(self.seed, k + 1, self.ids)
        while len(self._bottoms) <= k:                     # stacked in order: stage k sits on every lower one
            j = len(self._bottoms) - 1
            sj = self.stages.get(j)
            if sj is None:
                sj = self.stages[j] = Stage(j, self.ids[j], self._bottoms[j])
            self._bottoms.append(sj.top - GAP)
        s = self.stages[k] = Stage(k, self.ids[k], self._bottoms[k])
        return s

    def forget_below(self, k):
        if self.keep:
            return
        for j in [j for j in self.stages if j < k]:
            del self.stages[j]

    def window_data(self, w0, count=WINDOW):
        """LevelData of stages w0 .. w0+count-1 (absolute coordinates)."""
        st = [self.stage(k) for k in range(w0, w0 + count)]
        d = {"id": 0, "title": "ENDLESS", "height": st[0].bottom, "speed": st[0].speed, "ramp": 0.0,
             "par_time": 9999.0, "par_swaps": 9999, "waypoints": [], "stars": [], "pre_adjusted": True,
             "start": list(st[0].d["start"]), "end": [ARENA_W / 2.0, 60.0]}
        for key in RECT_KEYS + POINT_KEYS + ("moving_walls", "lasers", "spinners", "chasers", "stars"):
            d[key] = [list(v) for s in st for v in s.d[key]]
        for s in st[:-1]:                                   # connector chambers' side walls
            y = s.top - GAP
            d["walls"] += [[0.0, y, SIDE, GAP], [ARENA_W - SIDE, y, SIDE, GAP]]
        # Sim integrates the swing in four sub-steps whenever the level has a bumper, else in one: rounding differs in
        # the last bit. An unreachable bumper (last, so real bumper indices keep their numbers) keeps every window on
        # the sub-step path, whether or not one of its stages has a bumper.
        d["reverse_walls"].append([-600.0, 0.0, 10.0, 10.0])
        return LevelData(d)


class EndlessRun:
    """One endless attempt. step() once per 1/60 s, swap() on a tap - exactly like Sim."""

    def __init__(self, seed, record_events=False, margin=0.0):
        self.seed = seed
        self.world = World(seed)
        self.w0 = 0
        self.sim = Sim(self.world.window_data(0), margin=margin, record_events=record_events)
        self.start_y = self.sim.pivot.y
        self.best_y = self.start_y
        self.rebases = 0
        self.stars_banked = 0              # stars collected in stages that already left the window

    def clone(self):
        c = EndlessRun.__new__(EndlessRun)
        c.seed, c.world, c.w0 = self.seed, self.world, self.w0
        c.sim = self.sim.clone()
        c.start_y, c.best_y, c.rebases = self.start_y, self.best_y, self.rebases
        c.stars_banked = self.stars_banked
        return c

    # -- queries
    @property
    def n(self):
        return self.sim.n

    @property
    def dead(self):
        return self.sim.dead

    @property
    def metres(self):
        return int((self.start_y - self.best_y) / PX_PER_M)

    @property
    def stars(self):
        """Stars collected on this climb."""
        return self.stars_banked + sum(1 for x in self.sim.stars if x)

    @property
    def points(self):
        """The climb's score (what the weekly ranking sorts by): the height plus the stars picked up on the way."""
        return self.metres * POINTS_PER_M + self.stars * POINTS_PER_STAR

    def stage_at(self, y):
        """Index of the stage (with the connector above it) that contains height y."""
        k = self.w0
        while k < self.w0 + WINDOW - 1 and y < self.world.stage(k).top - GAP * 0.5:
            k += 1
        return k

    @property
    def stage(self):
        return self.stage_at(self.sim.pivot.y)

    def route_progress(self):
        """Distance along the intended way through the stages (px) - for bots and QA, never for scoring."""
        p = self.sim.pivot
        k = self.stage_at(p.y)
        base = 0.0
        for j in range(k):
            base += _poly_len(self.world.stage(j).route)
        return base + _poly_proj(self.world.stage(k).route, p.x, p.y)

    # -- input / physics
    def swap(self):
        self.sim.swap()

    def step(self):
        s = self.sim
        if s.dead:
            return
        k = self.stage_at(s.pivot.y)
        s.lvl.speed = self.world.stage(k).speed
        s.step()
        py = s.pivot.y
        if py < self.best_y:
            self.best_y = py
        if not s.dead and self.stage_at(py) >= self.w0 + 2:
            self._advance()

    def _advance(self):
        """Drop the lowest stage of the window, append the next one; per-object state follows its object."""
        s = self.sim
        old = self.world.stage(self.w0)
        self.w0 += 1
        new = self.world.stage(self.w0 + WINDOW - 1)
        lvl = self.world.window_data(self.w0)
        speed = s.lvl.speed
        lvl.speed = speed
        nb, nc, ns, nst = old.counts["breakables"], old.counts["chasers"], old.counts["shields"], old.counts["stars"]
        s.broken = s.broken[nb:] + [False] * new.counts["breakables"]
        s.chase_t0 = s.chase_t0[nc:] + [None] * new.counts["chasers"]
        s.shield_taken = s.shield_taken[ns:] + [False] * new.counts["shields"]
        self.stars_banked += sum(1 for x in s.stars[:nst] if x)
        s.stars = s.stars[nst:] + [False] * new.counts["stars"]
        s.lvl = lvl
        self.world.forget_below(self.w0)
        self.rebases += 1


def _poly_len(pts):
    return sum(((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5 for a, b in zip(pts, pts[1:]))


def _poly_proj(pts, px, py):
    best_d, best_s, acc = 1e30, 0.0, 0.0
    for a, b in zip(pts, pts[1:]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        ll = dx * dx + dy * dy
        t = 0.0 if ll == 0 else max(0.0, min(1.0, ((px - a[0]) * dx + (py - a[1]) * dy) / ll))
        ex, ey = a[0] + t * dx - px, a[1] + t * dy - py
        d = ex * ex + ey * ey
        seg = ll ** 0.5
        if d < best_d:
            best_d, best_s = d, acc + t * seg
        acc += seg
    return best_s


MAX_REVIVES = 3                # paid revives per climb (1.0.6)


def assist_digest(taps, assists=None):
    """What the climb's signature covers: the taps, and the paid help when there is any (mirrored in online.py and
    handler.ts) - a climb without help hashes exactly as before 1.0.6."""
    txt = ",".join(str(int(x)) for x in taps)
    if assists:
        txt += "|" + ",".join(f"{int(a[0])}{a[1]}" for a in sorted(assists, key=lambda a: int(a[0])))
    return txt


def replay(seed, taps, end_step=None, max_steps=MAX_STEPS, assists=None):
    """Replay a run: taps are step indices (swap before that step). Runs until death, `end_step` (the player quit)
    or max_steps. `assists`: paid help like the campaign's - [step, "S"] a bought shield, [step, "R2"] / [step, "R"]
    a revive after dying at that step. Returns the finished EndlessRun."""
    run = EndlessRun(seed)
    taps = sorted(taps)
    helps = sorted(((int(a[0]), str(a[1])) for a in (assists or [])), key=lambda a: a[0])
    limit = max_steps if end_step is None else min(max_steps, int(end_step))
    i = hi = 0
    while run.n < limit:
        while hi < len(helps) and helps[hi][0] <= run.n and (helps[hi][1] == "S" or run.dead):
            if helps[hi][1] == "S":
                run.sim.add_shield()
            else:
                run.sim.revive(guarded=helps[hi][1] == "R2")
            hi += 1
        if run.dead:
            break
        while i < len(taps) and taps[i] <= run.n:
            run.swap()
            i += 1
        run.step()
    return run
