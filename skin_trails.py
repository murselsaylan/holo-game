"""The shape each skin leaves behind its orbs (and bursts into when it crashes): one entry per skin, drawn by
particles.draw_shape. Skins that are not listed fall back to skins.trail_kind (the tether's family)."""

TRAILS = {
    "neon_pulse": "ring", "cyber_matrix": "gear", "solar_nova": "spark", "cosmic_void": "ring", "electric_storm": "bolt",
    "sakura_dream": "petal", "monochrome_zen": "yin", "boba_tea": "bubble", "meow_paw": "paw", "gummy_pop": "drop",
    "starry_pastel": "star", "golden_crown": "crown", "aurora_borealis": "wisp", "inferno_dragon": "flame",
    "deep_ocean": "bubble", "toxic_hazard": "drop", "phantom_wraith": "wisp", "galactic_nebula": "spark",
    "frost_crystal": "snow", "pixel_retro": "pixel", "honey_bee": "hex", "cyber_phantom": "cross", "comet_tail": "star",
    "stardust_dream": "spark", "quantum_lattice": "diamond", "pulsar_beam": "ring", "supernova": "flame",
    "event_horizon": "ring", "mochi_pal": "heart", "mint_blob": "drop", "lemon_chick": "spark", "berry_kitty": "paw",
    "cloud_bunny": "bubble", "rainbow_unicorn": "rainbow", "galaxy_cat": "star", "bunny_moon": "crescent",
    "diamond_heart": "diamond", "angel_halo": "ring", "royal_crown": "crown", "nebula_koi": "fish",
    "moon_dust": "crescent", "mars_rover": "gear", "saturn_ring": "ring", "cosmic_penguin": "snow",
    "solar_flare_cat": "flame", "alien_slime": "drop", "star_bear": "star", "pixel_probe": "pixel",
    "dark_matter": "wisp", "neutron_star": "spark", "big_bang": "rainbow", "astro_kitty": "paw",
    "rocket_bunny": "flame", "nova_heart": "heart", "comet_angel": "star", "sakura_fox": "petal",
    "panda_boba": "bubble", "sugar_puppy": "heart", "starlight_chick": "spark", "solar_wind": "spark",
    "quartz": "diamond", "gas_giant": "ring", "ice_moon": "crescent", "red_dwarf": "flame", "little_prince": "star",
    "leviathan": "fish", "jelly_drift": "drop", "void_walker": "wisp", "snow_leopard": "paw", "frost_fox": "snow",
    "snowball": "bubble", "arcade_king": "crown", "pixel_heart": "heart", "joystick": "cross", "coin_pop": "coin",
    "diamond_prestige": "diamond", "platinum_prestige": "spark", "gold_prestige": "coin", "silver_prestige": "crescent",
    "bronze_prestige": "gear", "star_hunter": "star", "comet_rider": "flame", "starfall": "star", "twinkle_orb": "spark",
    "stargazer": "spark", "streak_aurora": "wisp", "streak_nova": "flame", "streak_flame": "flame",
    "streak_ember": "flame", "streak_spark": "bolt",
}

# how a kind moves while it fades (arena px per 60 Hz step): petals and snow drift, bubbles and flames rise
DRIFT = {"petal": (0.7, 0.5), "snow": (0.25, 0.45), "bubble": (0.0, -0.5), "drop": (0.0, 0.6), "flame": (0.0, -0.4),
         "wisp": (0.0, -0.3), "spark": (0.0, -0.15)}
