"""Shop extras (1.0.9): the weekly showcase, consumable packs, prestige frames / titles, the weekly Star Market and the
Star Chest - the numbers and the deterministic weekly rotation.

The server (supabase/functions/scores/shopx.ts) is the authority: tools/gen_wallet_data.py copies the tables into
wallet_data.ts (SHOPX) and tools/shopx_golden.py checks that the rotation below and the TypeScript one pick the same
items. Change a number here, regenerate, redeploy. The client never sends an amount - only an item id and a retry ref.
"""
import math

import skin_catalog

DAY = 86400

# ------------------------------------------------------------------------------------------------ weekly rotation
def week_index(now):
    """Monday-based week number of a unix time (UTC); the showcase and the Star Market turn over together."""
    return (int(now // DAY) + 3) // 7


def week_end(now):
    return ((week_index(now) + 1) * 7 - 3) * DAY


def _rounded_5(x):
    return int(math.floor(x / 5.0 + 0.5)) * 5


def pick(pool, seed, count):
    """`count` distinct members of `pool` (a sorted list), the same on the server (shopx.ts pick)."""
    n = len(pool)
    count = min(count, n)
    start = (seed * 7919 + 13) % n
    step = max(1, n // count)
    out = []
    for k in range(count):
        i = (start + k * step) % n
        while i in out:
            i = (i + 1) % n
        out.append(i)
    return [pool[i] for i in out]


# ------------------------------------------------------------------------------------------------ prestige
# kind: perm (diamonds, always) | limited (diamonds, only in its showcase week) | star (chest / Star Market only)
# (id, price, kind, colour 1, colour 2)
FRAMES = [
    ("frame_bronze", 400, "perm", (205, 127, 50), (120, 70, 30)),
    ("frame_silver", 900, "perm", (215, 225, 240), (120, 135, 160)),
    ("frame_gold", 1800, "perm", (255, 205, 70), (200, 130, 20)),
    ("frame_nebula", 3000, "perm", (190, 110, 255), (60, 200, 255)),
    ("frame_diamond", 5000, "perm", (120, 240, 255), (255, 255, 255)),
    ("frame_stardust", 0, "star", (255, 236, 170), (255, 190, 80)),
    ("frame_comet", 0, "star", (150, 210, 255), (80, 120, 255)),
    ("lim_ember", 600, "limited", (255, 120, 60), (255, 200, 60)),
    ("lim_frost", 600, "limited", (170, 230, 255), (90, 160, 255)),
    ("lim_toxic", 600, "limited", (140, 255, 90), (40, 170, 90)),
    ("lim_rose", 600, "limited", (255, 130, 190), (200, 60, 130)),
    ("lim_ion", 600, "limited", (90, 255, 230), (60, 110, 255)),
    ("lim_sunset", 600, "limited", (255, 170, 90), (230, 70, 140)),
]
TITLES = [
    ("title_pilot", 300, "perm"),
    ("title_comet", 600, "perm"),
    ("title_orbit", 1000, "perm"),
    ("title_nova", 1600, "perm"),
    ("title_void", 2400, "perm"),
    ("title_legend", 3500, "perm"),
    ("title_pulse", 5000, "perm"),
    ("title_collector", 0, "star"),
    ("title_hunter", 0, "star"),
]
FRAME = {f[0]: f for f in FRAMES}
TITLE = {t[0]: t for t in TITLES}
LIMITED_FRAMES = sorted(f[0] for f in FRAMES if f[2] == "limited")
STAR_FRAMES = sorted(f[0] for f in FRAMES if f[2] == "star")
STAR_TITLES = sorted(t[0] for t in TITLES if t[2] == "star")


def prestige_price(item):
    f = FRAME.get(item) or TITLE.get(item)
    return f[1] if f else None


# ------------------------------------------------------------------------------------------------ weekly showcase
WEEKLY_SKINS = 3
WEEKLY_OFF = 0.2                                           # the skins of the week cost 20 % less (the daily deal is 30 %)
LIMITED_FRAME_PRICE = 600


def skin_pool():
    """The same pool as the daily deal: every diamond skin except the prestige ones."""
    return sorted(k for k in skin_catalog.COST if "prestige" not in k)


def weekly_skins(now):
    """[(skin id, price, full price)] of the week - 3 diamond skins at 20 % off."""
    out = []
    for sid in pick(skin_pool(), week_index(now), WEEKLY_SKINS):
        full = skin_catalog.COST[sid]
        out.append((sid, _rounded_5(full * (1 - WEEKLY_OFF)), full))
    return out


def weekly_frame(now):
    """The limited frame of the week (diamonds, bought only while it is in the showcase; owned for good)."""
    return LIMITED_FRAMES[week_index(now) % len(LIMITED_FRAMES)]


def weekly_skin_price(skin_id, now):
    for sid, price, _full in weekly_skins(now):
        if sid == skin_id:
            return price
    return None


# ------------------------------------------------------------------------------------------------ consumable packs
# id: (item, units, diamonds)  - a shield is SHIELD_COST (10) alone, a revive REVIVE_COST (20)
PACKS = {
    "shield3": ("shield", 3, 27),
    "shield10": ("shield", 10, 80),
    "revive3": ("revive", 3, 54),
    "revive10": ("revive", 10, 170),
}
PACK_UNITS_PER_DAY = {"shield": 20, "revive": 10}           # units bought through packs in 24 h
STOCK_CAP = {"shield": 25, "revive": 20}                    # what a player can hold (the game's local stock)

# ------------------------------------------------------------------------------------------------ stars
STAR_CAP = 900                                              # stars above this turn into diamonds (OVERFLOW_RATE each)
OVERFLOW_RATE = 1
# Star Market: slot 0 a consumable, slot 1 a diamond conversion, slot 2 a cosmetic - one of each pool a week.
# id: (kind, payload, stars, limit per week)
MARKET_POOLS = [
    [("m_shield3", "shield", 3, 30, 3), ("m_shield10", "shield", 10, 90, 1),
     ("m_revive2", "revive", 2, 36, 3), ("m_revive5", "revive", 5, 85, 1)],
    [("m_gems100", "gems", 100, 40, 2), ("m_gems300", "gems", 300, 100, 1)],
    [("m_frame_stardust", "frame", "frame_stardust", 150, 1), ("m_frame_comet", "frame", "frame_comet", 220, 1),
     ("m_title_collector", "title", "title_collector", 120, 1), ("m_title_hunter", "title", "title_hunter", 180, 1)],
]
MARKET = {m[0]: m for pool in MARKET_POOLS for m in pool}


def market(now):
    """The three items of this week's Star Market (one from each pool)."""
    wk = week_index(now)
    return [pool[(wk * (3 + i) + i) % len(pool)] for i, pool in enumerate(MARKET_POOLS)]


CHEST_COST = 40                                             # stars
CHEST_PER_DAY = 5
# (weight, kind, payload) - weights add up to 100; a frame already owned pays DUP_FRAME_GEMS diamonds instead
CHEST_TABLE = [
    (30, "gems", 30), (22, "shield", 2), (16, "revive", 1), (12, "gems", 60),
    (8, "shield", 5), (6, "gems", 120), (4, "revive", 3), (2, "frame", 0),
]
DUP_FRAME_GEMS = 150


def chest_reward(roll):
    """The table row for a roll in 0..99."""
    acc = 0
    for w, kind, payload in CHEST_TABLE:
        acc += w
        if roll < acc:
            return kind, payload
    return CHEST_TABLE[-1][1:]


def server_table():
    """What tools/gen_wallet_data.py writes into wallet_data.ts (SHOPX)."""
    return {
        "FRAMES": {f[0]: {"price": f[1], "kind": f[2]} for f in FRAMES},
        "TITLES": {t[0]: {"price": t[1], "kind": t[2]} for t in TITLES},
        "LIMITED_FRAMES": LIMITED_FRAMES, "STAR_FRAMES": STAR_FRAMES, "STAR_TITLES": STAR_TITLES,
        "WEEKLY_SKINS": WEEKLY_SKINS, "WEEKLY_OFF": WEEKLY_OFF, "LIMITED_FRAME_PRICE": LIMITED_FRAME_PRICE,
        "PACKS": {k: {"item": v[0], "units": v[1], "price": v[2]} for k, v in PACKS.items()},
        "PACK_UNITS_PER_DAY": PACK_UNITS_PER_DAY, "STOCK_CAP": STOCK_CAP,
        "STAR_CAP": STAR_CAP, "OVERFLOW_RATE": OVERFLOW_RATE,
        "MARKET_POOLS": [[{"id": m[0], "kind": m[1], "payload": m[2], "stars": m[3], "limit": m[4]} for m in pool]
                         for pool in MARKET_POOLS],
        "CHEST": {"cost": CHEST_COST, "per_day": CHEST_PER_DAY, "dup_frame_gems": DUP_FRAME_GEMS,
                  "table": [{"w": w, "kind": k, "payload": p} for w, k, p in CHEST_TABLE]},
    }
