"""The 100-level design plan: sector themes, difficulty curve, per-level family + hazard kit."""
import math

SECTORS = {
    1: ("ALPHA ORBITAL", "Yörünge temelleri • dar koridorlar • seken duvarlar"),
    2: ("PULSAR VOID", "Süpürücü pistonlar • Aegis bariyerleri • çatlak duvarlar"),
    3: ("QUANTUM PUZZLES", "Küçülme boğazları • kaçış koşuları • kırılan duvarlar"),
    4: ("EVENT HORIZON", "Lazer kapıları • döner kollar • ritim pencereleri"),
    5: ("OMEGA VOID", "Her şey bir arada • uzun dayanıklılık • tek hata yok"),
}

ADJ = {
    1: ["FIRST", "LONG", "BROAD", "TWIN", "OPEN", "SILENT", "BRIGHT", "STEADY", "WIDE", "CALM",
        "KINETIC", "REBOUND", "SHARP", "NARROW", "CLOSING", "TIGHT", "DEEP", "HOLLOW", "DISTANT", "ALPHA"],
    2: ["PULSE", "IRON", "HEARTBEAT", "CRUSHING", "OFF-BEAT", "TIMED", "HEAVY", "AEGIS", "COUNTER", "PISTON",
        "RHYTHM", "PRESS", "DEAD", "GUILLOTINE", "HAMMER", "STEEL", "DRIVEN", "RELENTLESS", "GRINDING", "PULSAR"],
    3: ["QUANTUM", "WARPED", "SHRINKING", "HEAVY-CORE", "PINCHED", "NEEDLE", "FLICKER", "PHASED", "DENSE", "BOOSTED",
        "GRAVITY", "SQUEEZED", "PRECISE", "UNSTABLE", "FRACTAL", "ENTANGLED", "COLLAPSING", "SUBATOMIC", "VOID-LINED", "SINGULAR"],
    4: ["STROBE", "RAZOR", "BURNING", "CROSSFIRE", "PRISM", "SUPERNOVA", "BLINDING", "SEARING", "SPLIT", "LIGHT-SPEED",
        "PHOTON", "SCARLET", "RELENTLESS", "BLADED", "EVENT", "SHADOWLESS", "HORIZON", "DEEP-STROBE", "FINAL", "CORE"],
    5: ["OMEGA", "HYBRID", "ENDLESS", "IRON-BLOOM", "CHAOS", "KNIFE-EDGE", "GAUNTLET", "ZERO", "BLACK", "LAST",
        "ABYSSAL", "MERCILESS", "COLLAPSE", "TWIN-PROP", "THE-WALL", "ETERNAL", "APOCALYPTIC", "NIRVANA", "TRIAL", "COSMIC"],
}
FAMNAME = {"arena": "TRIAL", "wander": "PASSAGE", "snake_h": "SERPENTINE", "snake_v": "COLUMNS", "zigzag": "ZIGZAG", "spiral": "SPIRAL", "maze": "LABYRINTH",
           "gates": "GATEWAY", "mines": "MINEFIELD", "chambers": "CHAMBERS", "custom": "PASSAGE"}
SPECIAL = {1: "FIRST ORBIT", 2: "LONG JOG", 3: "U-TURN", 100: "COSMIC APEX", 20: "ALPHA APEX", 40: "PULSAR CORE",
           60: "SINGULARITY", 80: "EVENT HORIZON CORE"}


def sector_of(i):
    return (i - 1) // 20 + 1


def difficulty(i):
    """tight in [0,1]: grows across the whole campaign, with a soft reset at the start of each sector."""
    base = ((i - 1) / 99.0) ** 0.85
    local = (i - 1) % 20
    wave = -0.07 * (1.0 - local / 19.0) if local < 6 else 0.0
    boss = 0.04 if local == 19 else 0.0
    return max(0.02, min(1.0, 0.04 + 0.94 * base + wave + boss))


def speed_of(i):
    return round(0.92 + 0.62 * ((i - 1) / 99.0) ** 0.85, 3)


def ramp_of(i):
    """Hidden end-of-level speed-up (fraction of extra speed at the goal). Grows with the level number."""
    return round(0.22 + 0.26 * ((i - 1) / 99.0) ** 0.9, 3)


def margin_target(i):
    """Safety margin (px of extra orb radius) the best possible line must still tolerate on level i.
    ~20 px at the last level = roughly +-40 ms timing slack on the tightest move: brutal but humanly possible."""
    return 58.0 * (20.0 / 58.0) ** ((i - 1) / 99.0)


def height_of(i):
    """Arena height. Later levels scroll: endurance is what makes level 100 hard to reach."""
    g = (i - 1) / 99.0
    bonus = 1300.0 * (max(0.0, i - 40) / 60.0) ** 1.3          # late levels are taller: more distance = more endurance
    return int(round((1470 + 2100 * g ** 1.2 + bonus) / 10.0) * 10)


import copy
import random

# Families available to fill the campaign. Each sector uses (approximately) this mix so no layout dominates.
ARENA_LEVELS = {6, 13, 16, 26, 34, 43, 47, 53, 57, 66, 74, 84, 88, 94}      # open-field trials (no power-up gates)
ARENA_KINDS = {1: ["slider", "bars", "pillars", "bounce"], 2: ["slider", "bars", "laser", "shutter", "bounce"], 3: ["pillars", "bars", "slider", "shutter", "bounce"],
               4: ["laser", "spin", "slider", "shutter", "bounce"], 5: ["laser", "spin", "slider", "shutter", "bars", "pillars", "bounce"]}
FAMILY_MIX = {
    1: {"wander": 8, "snake_h": 2, "zigzag": 2, "spiral": 2, "gates": 3, "chambers": 2, "mines": 1},
    2: {"wander": 9, "snake_h": 2, "zigzag": 2, "spiral": 2, "gates": 2, "chambers": 2, "mines": 1},
    3: {"wander": 8, "snake_h": 1, "zigzag": 2, "spiral": 2, "gates": 2, "chambers": 3, "mines": 2},
    4: {"wander": 8, "snake_h": 2, "zigzag": 2, "spiral": 2, "gates": 2, "chambers": 2, "mines": 2},
    5: {"wander": 9, "snake_h": 1, "zigzag": 2, "spiral": 2, "gates": 2, "chambers": 2, "mines": 2},
}
KIT_POOL = {
    1: ["pillar", "micro", "baffle"],
    2: ["sweep", "shutter", "baffle", "pillar", "micro"],
    3: ["micro", "funnel", "baffle", "pillar", "sweep", "shutter"],
    4: ["laser", "spin", "twin", "sweep", "shutter", "funnel"],
    5: ["laser", "spin", "twin", "sweep", "shutter", "funnel", "baffle", "micro", "pillar"],
}
# level -> re-roll counter; bump a level's number here when the similarity report says it looks like another level
VARIANT = {}
try:                                                     # levelgen/similar.py --fix writes re-rolls for levels that looked alike
    import json as _json
    import os as _os
    _vp = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "variants.json")
    if _os.path.exists(_vp):
        VARIANT = {int(k): int(v) for k, v in _json.load(open(_vp)).items()}
except Exception:
    VARIANT = {}
BOSS = {20: ("wander", {"legs": 8, "long_bias": 0.6}), 40: ("wander", {"legs": 10, "long_bias": 0.5}), 60: ("wander", {"legs": 12, "long_bias": 0.55}),
        80: ("wander", {"legs": 12, "long_bias": 0.5}), 100: ("wander", {"legs": 16, "long_bias": 0.7})}
TUTORIAL_GATES = {7: "ggrow", 11: "gshield", 15: "gshrink", 18: "gboost"}
DOOR_FAMILIES = ("gates", "chambers")


def _gate_program(i, sec, loc):
    """(gate kinds, count) for level i: every power-up gets introduced once, then mixed in with growing frequency."""
    if i in TUTORIAL_GATES:
        return [TUTORIAL_GATES[i]], 1
    k = loc // 4
    if sec == 1 or i in ARENA_LEVELS or (i % 9 == 0 and i not in BOSS):        # a few gate-free 'breather' levels: other layouts + pure hazards
        return [], 0
    if sec == 2:
        return (["gshield", "ggrow"] if loc % 2 == 0 else ["ggrow", "gshield"]), 1 + (1 if loc >= 8 else 0) + (1 if loc >= 15 else 0)
    if sec == 3:
        kinds = {0: ["gshrink"], 1: ["gboost", "gshrink"], 2: ["ggrow", "gshrink"], 3: ["gshrink", "gboost", "ggrow"],
                 4: ["gboost", "gshrink", "gshield"]}[k]
        return kinds, 1 + k // 2 + (1 if loc % 3 == 2 else 0)
    order = ["gshield", "gboost", "gshrink", "ggrow"] if sec == 4 else ["gshrink", "gboost", "gshield", "ggrow"]
    r = loc % 4
    kinds = order[r:] + order[:r]
    return kinds, (1 + (1 if loc >= 10 else 0)) if sec == 4 else 2 + k // 2


_SCHEDULE = {}


def _family_schedule():
    """Deterministic family per level (weighted by the sector mix, no repeats back to back)."""
    if _SCHEDULE:
        return _SCHEDULE
    for sec in range(1, 6):
        rng = random.Random(9000 + sec)
        remain = dict(FAMILY_MIX[sec])
        prev = None
        for loc in range(20):
            i = (sec - 1) * 20 + loc + 1
            if i <= 3 or i in BOSS:
                continue
            kinds, cnt = _gate_program(i, sec, loc)
            allowed = set(remain) | {"arena"}
            if i in ARENA_LEVELS:
                allowed = {"arena"}
            if kinds:
                allowed -= {"arena"}
                allowed &= {"wander", "zigzag", "spiral", "gates", "chambers"}
                if "gboost" in [kinds[j % len(kinds)] for j in range(max(1, cnt))]:
                    allowed &= {"wander"}
            opts = [f for f in allowed if f != prev and f != "spiral"] or ["wander"]
            if not opts:
                opts = ["wander"]
            wt = lambda f_: {"wander": 1.5, "zigzag": 0.5, "spiral": 0.0, "arena": 3.0}.get(f_, 1.0) * (1.0 if remain.get(f_, 0) > 0 else 0.3)
            tot = sum(wt(f_) for f_ in opts)
            r = rng.random() * tot
            for f in sorted(opts):
                r -= wt(f)
                if r <= 0:
                    break
            fam = f
            if fam in remain:
                remain[fam] = max(0, remain[fam] - 1)
            _SCHEDULE[i] = fam
            prev = fam
    return _SCHEDULE


def plan(i):
    """Return dict(family, fkw, kit, count, bumpers, shields, gates, gcount, style, title, sector, variant)"""
    sec = sector_of(i)
    loc = (i - 1) % 20
    var = VARIANT.get(i, 0)
    p = {"sector": sec, "kit": [], "count": 0, "bumpers": 0, "shields": 0, "gates": [], "gcount": 0, "variant": var}
    g = (i - 1) / 99.0
    rng = random.Random(i * 6151 + 17 + var * 977)

    if i <= 3:
        routes = {
            1: [(450, 1230), (450, 260)],
            2: [(260, 1240), (260, 780), (640, 780), (640, 260)],
            3: [(250, 1250), (650, 1250), (650, 420), (250, 420)],
        }
        p.update(family="custom", fkw={"pts": routes[i]}, style={"sp": 1.0, "lp": 1.0, "sz": 1.0})
        p["title"] = SPECIAL[i]
        return p

    kinds, gcount = _gate_program(i, sec, loc)
    p["gates"], p["gcount"] = kinds, gcount
    if i == 100:
        p["gates"], p["gcount"] = ["gshrink", "gboost", "ggrow", "gshield"], 4

    if i in BOSS:
        fam, fkw = BOSS[i]
    else:
        fam = _family_schedule().get(i, "wander")
        fkw = {}
    # per-level layout parameters (all drawn from the level's own random stream)
    flip = rng.random() < 0.5
    need_long = bool(p["gates"])
    if fam == "wander":
        wv = 0.0 if sec == 1 else rng.choice([0.0, 0.12, 0.2, 0.28])
        lb = rng.uniform(0.25, 0.9)
        if need_long:
            wanted = [p["gates"][j % len(p["gates"])] for j in range(max(1, p["gcount"]))]
            lb = max(lb, 0.95 if "gboost" in wanted else 0.7)
        base = dict(legs=4 + int(g * 8) + rng.randint(0, 3), long_bias=round(lb, 3), wvar=wv, flip=flip, reach=round(rng.uniform(0.55, 0.85), 2))
        if need_long:
            from levelgen import gates as G
            wanted = [p["gates"][j % len(p["gates"])] for j in range(max(1, p["gcount"]))]
            base["need"] = sorted((sum(G.EXTENT[k]) + 470.0 for k in wanted), reverse=True)[:2]      # long straight legs the gates sit on
            base["legs"] = max(base["legs"], len(wanted) + 3)
        fkw = dict(base, **fkw) if fkw else base
        fkw["flip"] = flip
    elif fam == "snake_h":
        fkw = {"lanes": 2 + int(g * 12) + rng.randint(0, 2), "flip": flip, "start_left": rng.random() < 0.5}
    elif fam == "zigzag":
        fkw = {"cols": rng.choice([2, 3, 3]), "flip": flip, "start_bottom": rng.random() < 0.6, "jag": rng.uniform(0.12, 0.42)}
    elif fam == "spiral" and i not in BOSS:
        fkw = {"turns": rng.choice([1, 2, 2, 3]) if sec > 1 else rng.choice([1, 2]), "clockwise": rng.random() < 0.5}
    elif fam == "gates":
        fkw = {"n": 2 + int(g * 5) + rng.randint(0, 1), "start_bottom": rng.random() < 0.6}
    elif fam == "chambers":
        fkw = {"n": 2 + int(g * 4) + rng.randint(0, 1), "start_bottom": rng.random() < 0.6}
    elif fam == "arena":
        fkw = {"rows": 3 + int(g * 9) + rng.randint(0, 2), "kinds": rng.sample(ARENA_KINDS[sec], min(len(ARENA_KINDS[sec]), rng.randint(2, 4))),
               "start_bottom": rng.random() < 0.6}
    elif fam == "mines":
        fkw = {"rows": 3 + int(g * 7) + rng.randint(0, 1), "start_bottom": rng.random() < 0.6}
    if fam in DOOR_FAMILIES and p["gates"]:
        allowed = [k for k in p["gates"] if k != "gboost"] or ["gshield"]
        fkw["door_kinds"] = [allowed[j % len(allowed)] if j < max(1, p["gcount"]) else None for j in range(fkw["n"])]
        p["gcount"] = 0                                    # the doors already carry the gates
    p.update(family=fam, fkw=fkw)
    p["title"] = SPECIAL.get(i) or f"{ADJ[sec][loc]} {FAMNAME[fam]}"

    # hazard kit: a random distinct subset of the sector's pool, so levels of a sector differ in kind, not just in count
    pool = KIT_POOL[sec]
    n_kinds = {1: 0 if loc < 6 else rng.randint(1, 2), 2: rng.randint(2, 3), 3: rng.randint(2, 4), 4: 3, 5: rng.randint(4, 5)}[sec]
    p["kit"] = rng.sample(pool, min(n_kinds, len(pool)))
    k = loc // 4
    cnt = {1: 0 if loc < 6 else 1 + (loc - 6) // 5, 2: 1 + k + (1 if loc >= 10 else 0), 3: 1 + k + (1 if loc % 2 else 0),
           4: 2 + k + (1 if loc % 3 == 0 else 0), 5: 3 + k + (1 if loc % 2 else 0)}[sec]
    p["count"] = cnt
    # kinetic bumpers (bounce + speed kick): now a regular part of every sector, more of them later on
    p["bumpers"] = {1: 0 if loc < 6 else 1 + (loc - 6) // 5, 2: (1 if loc % 3 == 1 else 0) + (1 if loc >= 14 else 0),
                    3: 1 if loc % 4 == 2 else 0, 4: 1 if loc % 3 == 0 else 0, 5: (1 + (1 if loc >= 12 else 0)) if loc % 2 == 1 else 0}[sec]
    if fam in ("arena",):
        p["kit"], p["count"], p["bumpers"] = [], 0, 0
    if fam in ("mines",):
        p["kit"] = [x for x in p["kit"] if x in ("sweep", "laser", "spin", "twin")][:2]
        p["count"] = 1 + k // 2
    if sec == 5 and not p["kit"]:
        p["kit"] = ["laser"]
    scale = 0.5 + 0.5 * height_of(i) / 1470.0
    p["count"] = int(round(p["count"] * scale))
    if i == 100:
        p["kit"] = ["spin", "laser", "sweep", "micro", "twin", "shutter"]
        p["count"] = 14
    # a spare shield would let the player skip a shield gate
    p["shields"] = 0 if any(x == "gshield" for x in p["gates"]) or fam in DOOR_FAMILIES else (1 if loc in (3, 8, 13, 18) and sec in (2, 4, 5) else 0)
    # style: every level's hazards move / size differently
    p["style"] = {"sp": round(rng.uniform(0.82, 1.25), 3), "lp": round(rng.uniform(0.85, 1.2), 3), "sz": round(rng.uniform(0.88, 1.15), 3)}
    return p
