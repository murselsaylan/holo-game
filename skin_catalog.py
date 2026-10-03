"""The skin catalogue: 15 themed catalogues x 5 skins = 75 skins, ranked from the most premium to the most ordinary.

Every catalogue has one skin of each rarity, listed in this order:

    1 EFSANEVİ / LEGENDARY  diamonds (500) or real money ($4.99, Google Play product skin_<id>)
    2 DESTANSI / EPIC       diamonds (350)
    3 NADİR / RARE          diamonds (250)
    4 ÖZEL / UNCOMMON       8 of them are achievement rewards, the other 7 cost 150 diamonds
    5 SIRADAN / COMMON      unlocked automatically when the player reaches a level (0 ... 100)
"""

TIERS = {
    1: {"tr": "EFSANEVİ", "en": "LEGENDARY", "color": (255, 200, 60), "cost": 500},
    2: {"tr": "DESTANSI", "en": "EPIC", "color": (190, 110, 255), "cost": 350},
    3: {"tr": "NADİR", "en": "RARE", "color": (80, 170, 255), "cost": 250},
    4: {"tr": "ÖZEL", "en": "UNCOMMON", "color": (70, 230, 150), "cost": 150},
    5: {"tr": "SIRADAN", "en": "COMMON", "color": (170, 178, 195), "cost": 0},
}

# (name tr, name en, [legendary, epic, rare, uncommon, common])
THEMES = [
    ("Siber Şehir", "Cyber City", ["cyber_phantom", "electric_storm", "cyber_matrix", "pixel_retro", "neon_pulse"]),
    ("Güneş Fırtınası", "Solar Storm", ["supernova", "inferno_dragon", "solar_nova", "solar_wind", "mars_rover"]),
    ("Kara Delik", "Black Hole", ["event_horizon", "dark_matter", "cosmic_void", "galactic_nebula", "stardust_dream"]),
    ("Yıldız Yağmuru", "Star Shower", ["big_bang", "neutron_star", "pulsar_beam", "comet_tail", "starry_pastel"]),
    ("Kristal Mağara", "Crystal Cave", ["quantum_lattice", "frost_crystal", "moon_dust", "pixel_probe", "quartz"]),
    ("Gezegenler", "Planets", ["saturn_ring", "aurora_borealis", "gas_giant", "ice_moon", "red_dwarf"]),
    ("Kedi Kulübü", "Cat Club", ["galaxy_cat", "astro_kitty", "solar_flare_cat", "berry_kitty", "meow_paw"]),
    ("Sevimli Dostlar", "Cute Friends", ["rainbow_unicorn", "sugar_puppy", "bunny_moon", "cloud_bunny", "mochi_pal"]),
    ("Kraliyet", "Royalty", ["royal_crown", "angel_halo", "golden_crown", "comet_angel", "little_prince"]),
    ("Kalp ve Şeker", "Hearts & Sweets", ["nova_heart", "diamond_heart", "gummy_pop", "boba_tea", "sakura_dream"]),
    ("Orman Dostları", "Forest Friends", ["sakura_fox", "panda_boba", "star_bear", "honey_bee", "lemon_chick"]),
    ("Okyanus", "Ocean", ["leviathan", "deep_ocean", "nebula_koi", "jelly_drift", "mint_blob"]),
    ("Gölgeler", "Shadows", ["void_walker", "phantom_wraith", "alien_slime", "toxic_hazard", "monochrome_zen"]),
    ("Kutup", "Arctic", ["snow_leopard", "cosmic_penguin", "starlight_chick", "frost_fox", "snowball"]),
    ("Arcade", "Arcade", ["rocket_bunny", "arcade_king", "pixel_heart", "joystick", "coin_pop"]),
    # bought only with the stars collected in the endless climb (never with diamonds or money)
    ("Yıldız Avcısı", "Star Hunter", ["star_hunter", "comet_rider", "starfall", "twinkle_orb", "stargazer"]),
    # every skin here is sold for diamonds (none are level rewards) and all 5 cost more than the same rarity
    # elsewhere; the top one is the single most expensive item in the game, in diamonds and in real money.
    ("Değerli Madenler", "Precious Metals", ["diamond_prestige", "platinum_prestige", "gold_prestige", "silver_prestige", "bronze_prestige"]),
]
PRESTIGE_THEME = len(THEMES) - 1

# COMMON skin of every catalogue -> level that unlocks it (0 = owned from the start); None = sold in the shop instead
COMMON_LEVELS = [0, 5, 10, 15, 20, 25, 30, 40, 50, 60, 70, 80, 85, 90, 100, None, None]

# Değerli Madenler costs (diamonds): well above the normal tier price at every rarity, topped by a genuinely expensive piece
PRESTIGE_COST = {
    "diamond_prestige": 1500, "platinum_prestige": 700, "gold_prestige": 450, "silver_prestige": 300, "bronze_prestige": 220,
}
PRESTIGE_TOP = "diamond_prestige"          # real-money price is set separately in shop.py (well above the other legendaries)

# Yıldız Avcısı: price in endless-climb stars (the only thing those stars buy)
STAR_COST = {"star_hunter": 600, "comet_rider": 350, "starfall": 200, "twinkle_orb": 100, "stargazer": 40}
STAR_THEME = next(i for i, th in enumerate(THEMES) if th[2][0] == "star_hunter")

# UNCOMMON skins that are achievement rewards (the other 7 are sold for 150 diamonds)
ACH = {
    "pixel_retro": "combo4", "solar_wind": "runner", "galactic_nebula": "s_rank", "comet_tail": "warp",
    "pixel_probe": "smasher", "ice_moon": "tiny", "berry_kitty": "grazer", "cloud_bunny": "heavy",
}
ACH_REWARD = {v: k for k, v in ACH.items()}

LEVEL = {}
THEME_OF = {}
TIER_OF = {}
ORDER = []
for ti, (_tr, _en, members) in enumerate(THEMES):
    for k, sid in enumerate(members):
        THEME_OF[sid] = ti
        TIER_OF[sid] = k + 1
        ORDER.append(sid)
    if COMMON_LEVELS[ti] is not None:
        LEVEL[members[4]] = COMMON_LEVELS[ti]

COST = {sid: TIERS[t]["cost"] for sid, t in TIER_OF.items() if t < 5 and sid not in ACH and sid not in STAR_COST}
COST.update(PRESTIGE_COST)             # overrides, including the tier-5 (Bronze) member which is shop-priced here


def tier(sid):
    return TIER_OF.get(sid, 5)


def theme_index(sid):
    return THEME_OF.get(sid, 0)


def theme_name(ti, lang="tr"):
    return THEMES[ti][0 if lang == "tr" else 1]


def tier_name(t, lang="tr"):
    return TIERS[t]["tr" if lang == "tr" else "en"]


def source(sid):
    """('level', n) | ('ach', id) | ('star', endless stars) | ('shop', gems)"""
    if sid in STAR_COST:
        return ("star", STAR_COST[sid])
    if sid in LEVEL:
        return ("level", LEVEL[sid])
    if sid in ACH:
        return ("ach", ACH[sid])
    return ("shop", COST.get(sid, 250))


def premium_ids():
    """Legendary skins: also sold for real money (Play products skin_<id>)."""
    return [sid for sid in ORDER if TIER_OF[sid] == 1 and sid not in STAR_COST]


def shop_skins():
    """Everything sold for diamonds: most premium first, then catalogue order."""
    return sorted((s for s in ORDER if s not in LEVEL and s not in ACH and s not in STAR_COST),
                  key=lambda s: (TIER_OF[s], THEME_OF[s]))


def featured_skins(n=3, date_str=None):
    """The showcase of the day: `n` legendary skins, a different trio every day (same for everyone, no server call)."""
    import datetime
    if not date_str:
        date_str = datetime.date.today().isoformat()
    y, m, d = (int(x) for x in date_str.split("-"))
    idx = datetime.date(y, m, d).toordinal()
    legends = premium_ids()
    k = len(legends)
    start = (idx * n) % k
    return [legends[(start + i) % k] for i in range(min(n, k))]


def featured_skin(date_str=None):
    """Shop showcase: one legendary skin spotlighted per day, deterministic (same pick for everyone, no server call)."""
    import datetime
    if not date_str:
        date_str = datetime.date.today().isoformat()
    y, m, d = (int(x) for x in date_str.split("-"))
    idx = datetime.date(y, m, d).toordinal()
    legends = premium_ids()
    return legends[idx % len(legends)]
