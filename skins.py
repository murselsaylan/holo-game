import pygame
import math
import random
from render_cache import SurfaceCache

_ORB_FX = SurfaceCache(2 * 1024 * 1024)

SKINS = {
    "neon_pulse": {
        "id": "neon_pulse",
        "name": "Neon Pulse",
        "desc": "Siberpunk neon ışık teması",
        "color1": (0, 240, 255),       # Cyan
        "color2": (255, 40, 160),      # Magenta
        "glow1": (0, 200, 255),
        "glow2": (255, 40, 160),
        "tether_type": "laser",
        "tether_color": (0, 230, 255),
        "orb_style": "ring", "unlock_desc": "Başlangıçta açık"
    },
    "cyber_matrix": {
        "id": "cyber_matrix",
        "name": "Gearbound",
        "desc": "Gümüş ve altın dişliler, metal zincir",
        "color1": (184, 196, 210),      # Brushed silver
        "color2": (218, 164, 52),       # Warm industrial gold
        "glow1": (115, 155, 190),
        "glow2": (220, 150, 35),
        "tether_type": "chain",
        "tether_color": (155, 168, 182),
        "tether_color2": (196, 142, 42),
        "orb_style": "gear", "unlock_desc": "6 Yıldız veya 5. Bölüm"
    },
    "solar_nova": {
        "id": "solar_nova",
        "name": "Solar Nova",
        "desc": "Alev kırmızısı güneş patlaması",
        "color1": (255, 75, 20),       # Solar orange-red
        "color2": (255, 210, 40),      # Bright yellow flame
        "glow1": (255, 90, 30),
        "glow2": (255, 200, 50),
        "tether_type": "plasma",
        "tether_color": (255, 130, 30),
        "orb_style": "sun", "unlock_desc": "15 Yıldız veya 10. Bölüm"
    },
    "cosmic_void": {
        "id": "cosmic_void",
        "name": "Cosmic Void",
        "desc": "Derin galaksi & nebula enerjisi",
        "color1": (175, 60, 255),      # Violet
        "color2": (70, 140, 255),      # Celestial blue
        "glow1": (160, 50, 255),
        "glow2": (70, 140, 255),
        "tether_type": "starlight",
        "tether_color": (150, 100, 255),
        "orb_style": "planet", "unlock_desc": "25 Yıldız veya 15. Bölüm"
    },
    "electric_storm": {
        "id": "electric_storm",
        "name": "Electric Storm",
        "desc": "Yüksek voltajlı plazma yıldırımları",
        "color1": (60, 220, 255),      # Arc blue
        "color2": (255, 235, 60),      # Electric yellow
        "glow1": (60, 220, 255),
        "glow2": (255, 230, 60),
        "tether_type": "lightning",
        "tether_color": (180, 240, 255),
        "orb_style": "gem", "unlock_desc": "38 Yıldız veya 20. Bölüm"
    },
    "sakura_dream": {
        "id": "sakura_dream",
        "name": "Sakura Dream",
        "desc": "Zarif kiraz çiçeği yaprakları",
        "color1": (255, 150, 195),     # Sakura pink
        "color2": (255, 240, 248),     # Blossom white
        "glow1": (255, 160, 200),
        "glow2": (255, 230, 245),
        "tether_type": "ribbon",
        "tether_color": (255, 180, 215),
        "orb_style": "flower", "unlock_desc": "45 Yıldız veya 22. Bölüm"
    },
    "monochrome_zen": {
        "id": "monochrome_zen",
        "name": "Zen Yin-Yang",
        "desc": "Siyah & beyaz kontrast uyumu",
        "color1": (35, 38, 48),        # Dark obsidian
        "color2": (245, 248, 255),     # Pure pearl
        "glow1": (120, 130, 150),
        "glow2": (220, 230, 255),
        "tether_type": "zen",
        "tether_color": (200, 210, 230),
        "orb_style": "half", "unlock_desc": "55 Yıldız veya 24. Bölüm"
    },
    "boba_tea": {
        "id": "boba_tea",
        "name": "Boba Milk Tea",
        "desc": "Çilekli süt & tatlı esmer şeker boba incileri",
        "color1": (255, 175, 200),     # Strawberry milk pink
        "color2": (130, 85, 65),       # Caramel brown boba pearl
        "glow1": (255, 190, 215),
        "glow2": (160, 105, 80),
        "tether_type": "boba_bubbles",
        "tether_color": (255, 195, 220),
        "orb_style": "bubble", "unlock_desc": "18 Yıldız veya 15. Bölüm"
    },
    "meow_paw": {
        "id": "meow_paw",
        "name": "Meow Paw",
        "desc": "Sevimli kedi patileri ve nane şekeri",
        "color1": (135, 245, 220),     # Pastel mint
        "color2": (255, 175, 200),     # Soft kitty peach pink
        "glow1": (150, 250, 230),
        "glow2": (255, 185, 210),
        "tether_type": "paw_chain",
        "tether_color": (210, 245, 235),
        "orb_style": "paw", "unlock_desc": "35 Yıldız veya 25. Bölüm"
    },
    "gummy_pop": {
        "id": "gummy_pop",
        "name": "Gummy Pop",
        "desc": "Rengarenk parıltılı tatlı jelibon şekeri",
        "color1": (20, 245, 230),      # Gummy cyan
        "color2": (255, 75, 185),      # Sugar magenta
        "glow1": (50, 255, 240),
        "glow2": (255, 100, 200),
        "tether_type": "jelly_ribbon",
        "tether_color": (140, 250, 240),
        "orb_style": "blob", "unlock_desc": "70 Yıldız veya 45. Bölüm"
    },
    "starry_pastel": {
        "id": "starry_pastel",
        "name": "Starry Pastel",
        "desc": "Yumuşacık bebek mavisi ve pastel yıldız tozu",
        "color1": (165, 215, 255),     # Baby blue
        "color2": (255, 240, 145),     # Marshmallow butter yellow
        "glow1": (180, 225, 255),
        "glow2": (255, 245, 165),
        "tether_type": "pastel_stardust",
        "tether_color": (210, 235, 255),
        "orb_style": "moon", "unlock_desc": "100 Yıldız veya 70. Bölüm"
    },
    "golden_crown": {
        "id": "golden_crown",
        "name": "Golden Crown",
        "desc": "Efsanevi parlayan saf altın taç",
        "color1": (255, 215, 15),      # Radiant gold
        "color2": (210, 90, 255),      # Royal violet
        "glow1": (255, 220, 40),
        "glow2": (200, 80, 255),
        "tether_type": "double_helix",
        "tether_color": (255, 225, 70),
        "orb_style": "gem", "unlock_desc": "130 Yıldız veya 85. Bölüm"
    },
    "aurora_borealis": {
        "id": "aurora_borealis",
        "name": "Aurora Borealis",
        "desc": "Kuzey ışıklarının polar zümrüt & mor aurası",
        "color1": (0, 255, 175),       # Shimmering polar emerald
        "color2": (165, 45, 255),      # Astral violet
        "glow1": (40, 255, 195),
        "glow2": (185, 75, 255),
        "tether_type": "aurora_wave",
        "tether_color": (50, 255, 200),
        "orb_style": "ring", "unlock_desc": "10 Yıldız veya 7. Bölüm"
    },
    "inferno_dragon": {
        "id": "inferno_dragon",
        "name": "Inferno Dragon",
        "desc": "Kavurucu magma alevi & volkanik kıvılcımlar",
        "color1": (255, 55, 10),       # Magma orange-red
        "color2": (255, 195, 25),      # Molten gold
        "glow1": (255, 80, 25),
        "glow2": (255, 220, 50),
        "tether_type": "flame_arc",
        "tether_color": (255, 110, 20),
        "orb_style": "sun", "unlock_desc": "20 Yıldız veya 12. Bölüm"
    },
    "deep_ocean": {
        "id": "deep_ocean",
        "name": "Deep Ocean",
        "desc": "Biyolüminesan okyanus uçurumu & mercan parıltısı",
        "color1": (0, 235, 225),       # Abyssal electric cyan
        "color2": (255, 75, 130),      # Deep coral pink
        "glow1": (30, 255, 235),
        "glow2": (255, 110, 160),
        "tether_type": "ocean_bubbles",
        "tether_color": (40, 240, 230),
        "orb_style": "bubble", "unlock_desc": "30 Yıldız veya 18. Bölüm"
    },
    "toxic_hazard": {
        "id": "toxic_hazard",
        "name": "Toxic Hazard",
        "desc": "Radyoaktif neon yeşili & yüksek tehlike asidi",
        "color1": (85, 255, 0),        # Radioactive lime
        "color2": (240, 255, 25),      # Acid hazard yellow
        "glow1": (105, 255, 30),
        "glow2": (245, 255, 60),
        "tether_type": "hazard_pulse",
        "tether_color": (120, 255, 40),
        "orb_style": "cube", "unlock_desc": "42 Yıldız veya 26. Bölüm"
    },
    "phantom_wraith": {
        "id": "phantom_wraith",
        "name": "Phantom Wraith",
        "desc": "Kozmik hayalet sisi & gölge lavanta aurası",
        "color1": (195, 145, 255),     # Spectral lavender
        "color2": (75, 40, 185),       # Shadow mist indigo
        "glow1": (215, 170, 255),
        "glow2": (105, 65, 225),
        "tether_type": "ghost_wisps",
        "tether_color": (180, 130, 255),
        "orb_style": "ghost", "unlock_desc": "55 Yıldız veya 35. Bölüm"
    },
    "galactic_nebula": {
        "id": "galactic_nebula",
        "name": "Galactic Nebula",
        "desc": "Derin galaksi bulutsusu & yıldızlararası toz",
        "color1": (140, 30, 245),      # Deep cosmic violet
        "color2": (255, 30, 145),      # Starlight hot fuchsia
        "glow1": (160, 50, 255),
        "glow2": (255, 75, 175),
        "tether_type": "nebula_spiral",
        "tether_color": (200, 50, 210),
        "orb_style": "planet", "unlock_desc": "65 Yıldız veya 45. Bölüm"
    },
    "frost_crystal": {
        "id": "frost_crystal",
        "name": "Frost Crystal",
        "desc": "Buzul kriyojenik kırağı & elmas parlaklığı",
        "color1": (135, 240, 255),     # Glacial cryo-cyan
        "color2": (245, 255, 255),     # Diamond white
        "glow1": (165, 245, 255),
        "glow2": (230, 250, 255),
        "tether_type": "ice_shards",
        "tether_color": (170, 245, 255),
        "orb_style": "gem", "unlock_desc": "78 Yıldız veya 55. Bölüm"
    },
    "pixel_retro": {
        "id": "pixel_retro",
        "name": "Pixel Arcade",
        "desc": "8-Bit retro arcade & neon pikselleri",
        "color1": (0, 255, 205),       # Vaporwave mint
        "color2": (255, 0, 135),       # Hot arcade magenta
        "glow1": (35, 255, 215),
        "glow2": (255, 45, 155),
        "tether_type": "pixel_chain",
        "tether_color": (255, 80, 180),
        "orb_style": "cube", "unlock_desc": "90 Yıldız veya 65. Bölüm"
    },
    "honey_bee": {
        "id": "honey_bee",
        "name": "Honey Bee",
        "desc": "Tatlı altın bal peteği & parıltılı kehribar",
        "color1": (255, 185, 15),      # Honey amber
        "color2": (45, 40, 35),        # Onyx bee stripe
        "glow1": (255, 205, 45),
        "glow2": (190, 155, 65),
        "tether_type": "honeycomb",
        "tether_color": (255, 195, 30),
        "orb_style": "striped", "unlock_desc": "110 Yıldız veya 78. Bölüm"
    },
    "cyber_phantom": {
        "id": "cyber_phantom",
        "name": "Cyber Phantom",
        "desc": "Elit siber titanyum & yanardöner hayalet zırh",
        "color1": (110, 125, 150),     # Stealth titanium
        "color2": (185, 245, 255),     # Iridescent chrome
        "glow1": (140, 160, 190),
        "glow2": (215, 250, 255),
        "tether_type": "stealth_pulse",
        "tether_color": (160, 220, 245),
        "orb_style": "half", "unlock_desc": "140 Yıldız veya 90. Bölüm"
    },
    "comet_tail": {
        "id": "comet_tail",
        "name": "Comet Tail",
        "desc": "Buz kuyruklu yıldızın parlayan izi",
        "color1": (170, 235, 255),
        "color2": (255, 255, 255),
        "glow1": (120, 200, 255),
        "glow2": (220, 240, 255),
        "tether_type": "comet",
        "tether_color": (150, 220, 255),
        "orb_style": "moon", "unlock_desc": ""
    },
    "stardust_dream": {
        "id": "stardust_dream",
        "name": "Stardust",
        "desc": "Altın ve pembe yıldız tozu bulutu",
        "color1": (255, 205, 90),
        "color2": (255, 120, 190),
        "glow1": (255, 200, 110),
        "glow2": (255, 130, 200),
        "tether_type": "stardust",
        "tether_color": (255, 190, 150),
        "orb_style": "flower", "unlock_desc": ""
    },
    "quantum_lattice": {
        "id": "quantum_lattice",
        "name": "Quantum Lattice",
        "desc": "Kuantum kafesi: kristal düğümler",
        "color1": (60, 255, 190),
        "color2": (90, 170, 255),
        "glow1": (50, 240, 180),
        "glow2": (90, 170, 255),
        "tether_type": "lattice",
        "tether_color": (60, 255, 190),
        "orb_style": "crystal",
        "unlock_desc": ""
    },
    "pulsar_beam": {
        "id": "pulsar_beam",
        "name": "Pulsar Beam",
        "desc": "Nötron yıldızından dalga dalga darbe",
        "color1": (235, 235, 255),
        "color2": (190, 110, 255),
        "glow1": (210, 200, 255),
        "glow2": (190, 110, 255),
        "tether_type": "pulse_wave",
        "tether_color": (200, 140, 255),
        "orb_style": "ring", "unlock_desc": ""
    },
    "supernova": {
        "id": "supernova",
        "name": "Supernova",
        "desc": "Patlayan yıldız: kor ve kıvılcım",
        "color1": (255, 90, 60),
        "color2": (255, 215, 90),
        "glow1": (255, 110, 60),
        "glow2": (255, 210, 90),
        "tether_type": "sparks",
        "tether_color": (255, 120, 60),
        "orb_style": "star",
        "unlock_desc": ""
    },
    "event_horizon": {
        "id": "event_horizon",
        "name": "Event Horizon",
        "desc": "Karanlık çekirdek, yanan yığılma halkası",
        "color1": (255, 150, 40),
        "color2": (200, 80, 255),
        "glow1": (255, 140, 40),
        "glow2": (200, 80, 255),
        "tether_type": "accretion",
        "tether_color": (255, 140, 40),
        "orb_style": "void",
        "unlock_desc": ""
    },
    # ---- sweet collection (free, earned by playing)
    "mochi_pal": {
        "id": "mochi_pal", "name": "Mochi Pal", "desc": "Yumuşacık pembe mochi arkadaşlar",
        "color1": (255, 178, 205), "color2": (255, 236, 244), "glow1": (255, 150, 190), "glow2": (255, 220, 235),
        "tether_type": "pastel_stardust", "tether_color": (255, 170, 205), "orb_style": "face", "unlock_desc": ""
    },
    "mint_blob": {
        "id": "mint_blob", "name": "Mint Blob", "desc": "Serin nane jölesi, hep gülümser",
        "color1": (140, 250, 200), "color2": (130, 215, 255), "glow1": (110, 240, 190), "glow2": (110, 200, 255),
        "tether_type": "ocean_bubbles", "tether_color": (130, 240, 210), "orb_style": "face", "unlock_desc": ""
    },
    "lemon_chick": {
        "id": "lemon_chick", "name": "Lemon Chick", "desc": "Limonlu civciv ikizleri",
        "color1": (255, 232, 100), "color2": (255, 198, 90), "glow1": (255, 225, 90), "glow2": (255, 190, 80),
        "tether_type": "honeycomb", "tether_color": (255, 215, 90), "orb_style": "face", "unlock_desc": ""
    },
    "berry_kitty": {
        "id": "berry_kitty", "name": "Berry Kitty", "desc": "Böğürtlen renkli minik kediler",
        "color1": (200, 130, 255), "color2": (255, 150, 200), "glow1": (190, 120, 255), "glow2": (255, 140, 190),
        "tether_type": "paw_chain", "tether_color": (220, 150, 255), "orb_style": "cat", "unlock_desc": ""
    },
    "cloud_bunny": {
        "id": "cloud_bunny", "name": "Cloud Bunny", "desc": "Bulut tavşanı: kulakları rüzgârda",
        "color1": (235, 245, 255), "color2": (200, 225, 255), "glow1": (200, 225, 255), "glow2": (170, 205, 255),
        "tether_type": "stardust", "tether_color": (200, 225, 255), "orb_style": "bunny", "unlock_desc": ""
    },
    # ---- premium collection (paid / supporter)
    "rainbow_unicorn": {
        "id": "rainbow_unicorn", "name": "Rainbow Unicorn", "desc": "Gökkuşağı yeleli tek boynuzlu at",
        "color1": (255, 200, 240), "color2": (200, 220, 255), "glow1": (255, 170, 230), "glow2": (170, 200, 255),
        "tether_type": "rainbow", "tether_color": (255, 190, 240), "orb_style": "unicorn", "unlock_desc": "", "premium": True
    },
    "galaxy_cat": {
        "id": "galaxy_cat", "name": "Galaxy Cat", "desc": "Yıldız tozlu uzay kedisi",
        "color1": (110, 90, 230), "color2": (255, 120, 210), "glow1": (120, 100, 255), "glow2": (255, 110, 200),
        "tether_type": "star_chain", "tether_color": (200, 170, 255), "orb_style": "cat", "unlock_desc": "", "premium": True
    },
    "bunny_moon": {
        "id": "bunny_moon", "name": "Moon Bunny", "desc": "Ay tavşanı: kalpli zincir",
        "color1": (255, 250, 220), "color2": (255, 205, 225), "glow1": (255, 245, 200), "glow2": (255, 190, 215),
        "tether_type": "hearts", "tether_color": (255, 170, 205), "orb_style": "bunny", "unlock_desc": "", "premium": True
    },
    "diamond_heart": {
        "id": "diamond_heart", "name": "Diamond Heart", "desc": "Parlayan kalp çifti",
        "color1": (255, 90, 150), "color2": (255, 170, 210), "glow1": (255, 80, 140), "glow2": (255, 160, 205),
        "tether_type": "hearts", "tether_color": (255, 110, 170), "orb_style": "heart", "unlock_desc": "", "premium": True
    },
    "angel_halo": {
        "id": "angel_halo", "name": "Angel Halo", "desc": "Halkalı melek orblar",
        "color1": (255, 255, 240), "color2": (200, 235, 255), "glow1": (255, 250, 200), "glow2": (180, 225, 255),
        "tether_type": "star_chain", "tether_color": (255, 245, 190), "orb_style": "angel", "unlock_desc": "", "premium": True
    },
    "royal_crown": {
        "id": "royal_crown", "name": "Royal Crown", "desc": "Altın taçlı kraliyet ikilisi",
        "color1": (255, 214, 70), "color2": (255, 140, 90), "glow1": (255, 210, 60), "glow2": (255, 130, 80),
        "tether_type": "rainbow", "tether_color": (255, 215, 90), "orb_style": "crown", "unlock_desc": "", "premium": True
    },
    "nebula_koi": {
        "id": "nebula_koi", "name": "Nebula Koi", "desc": "Nebulada yüzen turuncu koi çifti",
        "color1": (255, 150, 70), "color2": (255, 240, 230), "glow1": (255, 160, 80), "glow2": (255, 250, 240),
        "tether_type": "ocean_bubbles", "tether_color": (255, 150, 70), "orb_style": "face", "unlock_desc": ""
    },
    "moon_dust": {
        "id": "moon_dust", "name": "Moon Dust", "desc": "Ay tozu: gümüş kristal orblar",
        "color1": (200, 215, 235), "color2": (140, 170, 230), "glow1": (210, 225, 245), "glow2": (150, 180, 240),
        "tether_type": "comet", "tether_color": (200, 215, 235), "orb_style": "crystal", "unlock_desc": ""
    },
    "mars_rover": {
        "id": "mars_rover", "name": "Mars Rover", "desc": "Kızıl gezegenin kıvılcımlı gezgini",
        "color1": (235, 95, 55), "color2": (255, 190, 120), "glow1": (245, 105, 65), "glow2": (255, 200, 130),
        "tether_type": "sparks", "tether_color": (235, 95, 55), "orb_style": "star", "unlock_desc": ""
    },
    "saturn_ring": {
        "id": "saturn_ring", "name": "Saturn Ring", "desc": "Halkalı gezegenin altın-mor tozu",
        "color1": (255, 205, 100), "color2": (190, 150, 255), "glow1": (255, 215, 110), "glow2": (200, 160, 255),
        "tether_type": "nebula_spiral", "tether_color": (255, 205, 100), "orb_style": "planet", "unlock_desc": ""
    },
    "cosmic_penguin": {
        "id": "cosmic_penguin", "name": "Cosmic Penguin", "desc": "Buzul gezegenin uzay pengueni",
        "color1": (60, 75, 115), "color2": (235, 245, 255), "glow1": (70, 85, 125), "glow2": (245, 255, 255),
        "tether_type": "ice_shards", "tether_color": (60, 75, 115), "orb_style": "face", "unlock_desc": ""
    },
    "solar_flare_cat": {
        "id": "solar_flare_cat", "name": "Solar Flare Cat", "desc": "Güneş patlaması kadar sıcak bir kedi",
        "color1": (255, 150, 40), "color2": (255, 225, 90), "glow1": (255, 160, 50), "glow2": (255, 235, 100),
        "tether_type": "flame_arc", "tether_color": (255, 150, 40), "orb_style": "cat", "unlock_desc": ""
    },
    "alien_slime": {
        "id": "alien_slime", "name": "Alien Slime", "desc": "Uzaylı jölesi: yeşil ve mor",
        "color1": (120, 240, 110), "color2": (190, 110, 255), "glow1": (130, 250, 120), "glow2": (200, 120, 255),
        "tether_type": "jelly_ribbon", "tether_color": (120, 240, 110), "orb_style": "face", "unlock_desc": ""
    },
    "star_bear": {
        "id": "star_bear", "name": "Star Bear", "desc": "Yıldız tozuna bulanmış ayıcık",
        "color1": (215, 160, 105), "color2": (255, 235, 200), "glow1": (225, 170, 115), "glow2": (255, 245, 210),
        "tether_type": "honeycomb", "tether_color": (215, 160, 105), "orb_style": "face", "unlock_desc": ""
    },
    "pixel_probe": {
        "id": "pixel_probe", "name": "Pixel Probe", "desc": "Eski usul piksel sondası",
        "color1": (120, 255, 240), "color2": (240, 250, 255), "glow1": (130, 255, 250), "glow2": (250, 255, 255),
        "tether_type": "pixel_chain", "tether_color": (120, 255, 240), "orb_style": "crystal", "unlock_desc": ""
    },
    "dark_matter": {
        "id": "dark_matter", "name": "Dark Matter", "desc": "Görünmeyen kütle: karanlık çekirdek",
        "color1": (150, 60, 220), "color2": (255, 130, 60), "glow1": (160, 70, 230), "glow2": (255, 140, 70),
        "tether_type": "stealth_pulse", "tether_color": (150, 60, 220), "orb_style": "void", "unlock_desc": ""
    },
    "neutron_star": {
        "id": "neutron_star", "name": "Neutron Star", "desc": "Dönen nötron yıldızı ve darbeleri",
        "color1": (235, 245, 255), "color2": (110, 170, 255), "glow1": (245, 255, 255), "glow2": (120, 180, 255),
        "tether_type": "pulse_wave", "tether_color": (235, 245, 255), "orb_style": "star", "unlock_desc": ""
    },
    "big_bang": {
        "id": "big_bang", "name": "Big Bang", "desc": "Her şeyin başladığı an",
        "color1": (255, 240, 200), "color2": (255, 90, 160), "glow1": (255, 250, 210), "glow2": (255, 100, 170),
        "tether_type": "rainbow", "tether_color": (255, 240, 200), "orb_style": "star", "unlock_desc": ""
    },
    "astro_kitty": {
        "id": "astro_kitty", "name": "Astro Kitty", "desc": "Astronot kıyafetli minik kedi",
        "color1": (240, 245, 255), "color2": (130, 190, 255), "glow1": (250, 255, 255), "glow2": (140, 200, 255),
        "tether_type": "star_chain", "tether_color": (240, 245, 255), "orb_style": "cat", "unlock_desc": "", "premium": True
    },
    "rocket_bunny": {
        "id": "rocket_bunny", "name": "Rocket Bunny", "desc": "Roket yakıtıyla koşan tavşan",
        "color1": (255, 120, 110), "color2": (255, 220, 120), "glow1": (255, 130, 120), "glow2": (255, 230, 130),
        "tether_type": "sparks", "tether_color": (255, 120, 110), "orb_style": "bunny", "unlock_desc": "", "premium": True
    },
    "nova_heart": {
        "id": "nova_heart", "name": "Nova Heart", "desc": "Süpernova kalbi: gökkuşağı zinciri",
        "color1": (255, 70, 130), "color2": (255, 200, 90), "glow1": (255, 80, 140), "glow2": (255, 210, 100),
        "tether_type": "rainbow", "tether_color": (255, 70, 130), "orb_style": "heart", "unlock_desc": "", "premium": True
    },
    "comet_angel": {
        "id": "comet_angel", "name": "Comet Angel", "desc": "Kuyruklu yıldızdan doğan melek",
        "color1": (200, 235, 255), "color2": (255, 245, 190), "glow1": (210, 245, 255), "glow2": (255, 255, 200),
        "tether_type": "comet", "tether_color": (200, 235, 255), "orb_style": "angel", "unlock_desc": "", "premium": True
    },
    "sakura_fox": {
        "id": "sakura_fox", "name": "Sakura Fox", "desc": "Kiraz çiçeği yapraklarıyla dans eden tatlı tilki",
        "color1": (255, 140, 100), "color2": (255, 195, 215), "glow1": (255, 160, 120), "glow2": (255, 215, 230),
        "tether_type": "rainbow", "tether_color": (255, 185, 210), "orb_style": "fox", "unlock_desc": "", "premium": True
    },
    "panda_boba": {
        "id": "panda_boba", "name": "Panda Boba", "desc": "Boba incileriyle süzülen minik sevimli panda",
        "color1": (245, 245, 250), "color2": (160, 225, 195), "glow1": (255, 255, 255), "glow2": (180, 245, 215),
        "tether_type": "bubble", "tether_color": (160, 225, 195), "orb_style": "panda", "unlock_desc": "", "premium": True
    },
    "sugar_puppy": {
        "id": "sugar_puppy", "name": "Sugar Puppy", "desc": "Karamel şeker neşeli ve sevimli yavru köpek",
        "color1": (245, 210, 165), "color2": (255, 150, 180), "glow1": (255, 225, 185), "glow2": (255, 170, 200),
        "tether_type": "neon_cord", "tether_color": (255, 180, 120), "orb_style": "puppy", "unlock_desc": "", "premium": True
    },
    "starlight_chick": {
        "id": "starlight_chick", "name": "Starlight Chick", "desc": "Yıldız tozundan doğmuş minik şirin civciv",
        "color1": (255, 225, 90), "color2": (140, 220, 255), "glow1": (255, 235, 110), "glow2": (160, 235, 255),
        "tether_type": "star_chain", "tether_color": (255, 230, 120), "orb_style": "chick", "unlock_desc": "", "premium": True
    },
    "solar_wind": {
        "id": "solar_wind", "name": "Solar Wind", "desc": "Güneş rüzgârıyla savrulan altın parçacıklar",
        "color1": (255, 214, 90), "color2": (255, 150, 70), "glow1": (255, 224, 100), "glow2": (255, 160, 80),
        "tether_type": "comet", "tether_color": (255, 214, 90), "orb_style": "ring", "unlock_desc": ""
    },
    "quartz": {
        "id": "quartz", "name": "Quartz", "desc": "Saf kuvars kristali, içi ışık dolu",
        "color1": (200, 230, 255), "color2": (240, 200, 255), "glow1": (210, 240, 255), "glow2": (250, 210, 255),
        "tether_type": "lattice", "tether_color": (200, 230, 255), "orb_style": "gem", "unlock_desc": ""
    },
    "gas_giant": {
        "id": "gas_giant", "name": "Gas Giant", "desc": "Fırtınalı halkalı gaz devi",
        "color1": (255, 170, 110), "color2": (200, 120, 255), "glow1": (255, 180, 120), "glow2": (210, 130, 255),
        "tether_type": "nebula_spiral", "tether_color": (255, 170, 110), "orb_style": "planet", "unlock_desc": ""
    },
    "ice_moon": {
        "id": "ice_moon", "name": "Ice Moon", "desc": "Buzlu kraterleriyle donmuş uydu",
        "color1": (190, 235, 255), "color2": (140, 180, 255), "glow1": (200, 245, 255), "glow2": (150, 190, 255),
        "tether_type": "ice_shards", "tether_color": (190, 235, 255), "orb_style": "moon", "unlock_desc": ""
    },
    "red_dwarf": {
        "id": "red_dwarf", "name": "Red Dwarf", "desc": "Küçük ama yanan kırmızı cüce yıldız",
        "color1": (255, 90, 80), "color2": (255, 170, 120), "glow1": (255, 100, 90), "glow2": (255, 180, 130),
        "tether_type": "flame_arc", "tether_color": (255, 90, 80), "orb_style": "sun", "unlock_desc": ""
    },
    "little_prince": {
        "id": "little_prince", "name": "Little Prince", "desc": "Yıldızlar arasında gezen minik prens",
        "color1": (255, 214, 120), "color2": (150, 190, 255), "glow1": (255, 224, 130), "glow2": (160, 200, 255),
        "tether_type": "star_chain", "tether_color": (255, 214, 120), "orb_style": "face", "unlock_desc": ""
    },
    "leviathan": {
        "id": "leviathan", "name": "Leviathan", "desc": "Derinlerden gelen dev okyanus canavarı",
        "color1": (40, 200, 230), "color2": (20, 90, 170), "glow1": (50, 210, 240), "glow2": (30, 100, 180),
        "tether_type": "ocean_bubbles", "tether_color": (40, 200, 230), "orb_style": "bubble", "unlock_desc": ""
    },
    "jelly_drift": {
        "id": "jelly_drift", "name": "Jelly Drift", "desc": "Akıntıda süzülen ışıklı denizanası",
        "color1": (255, 140, 220), "color2": (150, 200, 255), "glow1": (255, 150, 230), "glow2": (160, 210, 255),
        "tether_type": "jelly_ribbon", "tether_color": (255, 140, 220), "orb_style": "blob", "unlock_desc": ""
    },
    "void_walker": {
        "id": "void_walker", "name": "Void Walker", "desc": "Boşlukta yürüyen gölge yolcu",
        "color1": (150, 90, 255), "color2": (255, 90, 200), "glow1": (160, 100, 255), "glow2": (255, 100, 210),
        "tether_type": "ghost_wisps", "tether_color": (150, 90, 255), "orb_style": "ghost", "unlock_desc": ""
    },
    "snow_leopard": {
        "id": "snow_leopard", "name": "Snow Leopard", "desc": "Karlı zirvelerin gizemli kaplanı",
        "color1": (230, 240, 255), "color2": (120, 160, 210), "glow1": (240, 250, 255), "glow2": (130, 170, 220),
        "tether_type": "ice_shards", "tether_color": (230, 240, 255), "orb_style": "cat", "unlock_desc": ""
    },
    "frost_fox": {
        "id": "frost_fox", "name": "Frost Fox", "desc": "Kırağıyla parlayan minik tilki",
        "color1": (160, 210, 255), "color2": (255, 255, 255), "glow1": (170, 220, 255), "glow2": (255, 255, 255),
        "tether_type": "pastel_stardust", "tether_color": (160, 210, 255), "orb_style": "fox", "unlock_desc": ""
    },
    "snowball": {
        "id": "snowball", "name": "Snowball", "desc": "Yumuşacık kartopu arkadaşlar",
        "color1": (240, 248, 255), "color2": (200, 225, 250), "glow1": (250, 255, 255), "glow2": (210, 235, 255),
        "tether_type": "pastel_stardust", "tether_color": (240, 248, 255), "orb_style": "face", "unlock_desc": ""
    },
    "arcade_king": {
        "id": "arcade_king", "name": "Arcade King", "desc": "Salonun rekortmeni, tacı hep onda",
        "color1": (255, 220, 60), "color2": (255, 60, 110), "glow1": (255, 230, 70), "glow2": (255, 70, 120),
        "tether_type": "pixel_chain", "tether_color": (255, 220, 60), "orb_style": "crown", "unlock_desc": ""
    },
    "pixel_heart": {
        "id": "pixel_heart", "name": "Pixel Heart", "desc": "Piksel piksel atan kalp",
        "color1": (255, 70, 120), "color2": (255, 200, 220), "glow1": (255, 80, 130), "glow2": (255, 210, 230),
        "tether_type": "pixel_chain", "tether_color": (255, 70, 120), "orb_style": "heart", "unlock_desc": ""
    },
    "joystick": {
        "id": "joystick", "name": "Joystick", "desc": "Retro kumandanın neon kolu",
        "color1": (90, 255, 160), "color2": (60, 180, 255), "glow1": (100, 255, 170), "glow2": (70, 190, 255),
        "tether_type": "segmented", "tether_color": (90, 255, 160), "orb_style": "cube", "unlock_desc": ""
    },
    "coin_pop": {
        "id": "coin_pop", "name": "Coin Pop", "desc": "Şıngırdayan altın jeton çifti",
        "color1": (255, 214, 60), "color2": (255, 240, 140), "glow1": (255, 224, 70), "glow2": (255, 250, 150),
        "tether_type": "stardust", "tether_color": (255, 214, 60), "orb_style": "ring", "unlock_desc": ""
    },

    "diamond_prestige": {
        "id": "diamond_prestige", "name": "Cosmic Diamond", "desc": "Kozmik elmas: evrenin en saf ışığı",
        "color1": (255, 255, 255), "color2": (150, 225, 255), "glow1": (255, 255, 255), "glow2": (160, 235, 255),
        "tether_type": "accretion", "tether_color": (255, 255, 255), "orb_style": "gem", "unlock_desc": ""
    },
    "platinum_prestige": {
        "id": "platinum_prestige", "name": "Nova Platinum", "desc": "Yıldız çekirdeğinden dövülmüş platin",
        "color1": (225, 230, 240), "color2": (180, 205, 225), "glow1": (235, 240, 250), "glow2": (190, 215, 235),
        "tether_type": "lattice", "tether_color": (225, 230, 240), "orb_style": "ring", "unlock_desc": ""
    },
    "gold_prestige": {
        "id": "gold_prestige", "name": "Solar Gold", "desc": "Güneşin kalbinden süzülen saf altın",
        "color1": (255, 210, 70), "color2": (255, 235, 150), "glow1": (255, 220, 80), "glow2": (255, 245, 160),
        "tether_type": "sparks", "tether_color": (255, 210, 70), "orb_style": "sun", "unlock_desc": ""
    },
    "silver_prestige": {
        "id": "silver_prestige", "name": "Lunar Silver", "desc": "Ay ışığında parlayan gümüş çift",
        "color1": (210, 215, 225), "color2": (235, 240, 250), "glow1": (220, 225, 235), "glow2": (245, 250, 255),
        "tether_type": "ice_shards", "tether_color": (210, 215, 225), "orb_style": "moon", "unlock_desc": ""
    },
    "bronze_prestige": {
        "id": "bronze_prestige", "name": "Stardust Bronze", "desc": "Yıldız tozuyla sertleşmiş bronz",
        "color1": (205, 145, 95), "color2": (230, 180, 130), "glow1": (215, 155, 105), "glow2": (240, 190, 140),
        "tether_type": "double_helix", "tether_color": (205, 145, 95), "orb_style": "half", "unlock_desc": ""
    },
    # ---- Yıldız Avcısı (Star Hunter): bought with endless-climb stars
    "star_hunter": {
        "id": "star_hunter", "name": "Star Hunter", "desc": "Sonsuz tırmanışın efsanesi: altın yıldız avcısı",
        "color1": (255, 214, 70), "color2": (255, 250, 225), "glow1": (255, 200, 50), "glow2": (255, 245, 200),
        "tether_type": "star_chain", "tether_color": (255, 214, 70), "orb_style": "star", "unlock_desc": ""
    },
    "comet_rider": {
        "id": "comet_rider", "name": "Comet Rider", "desc": "Kuyruklu yıldızın sırtında: mavi alev izi",
        "color1": (110, 200, 255), "color2": (255, 235, 150), "glow1": (120, 210, 255), "glow2": (255, 240, 170),
        "tether_type": "sparks", "tether_color": (140, 215, 255), "orb_style": "sun", "unlock_desc": ""
    },
    "starfall": {
        "id": "starfall", "name": "Starfall", "desc": "Yıldız yağmurunda mor bir gece",
        "color1": (190, 130, 255), "color2": (255, 225, 120), "glow1": (200, 140, 255), "glow2": (255, 230, 140),
        "tether_type": "stardust", "tether_color": (205, 160, 255), "orb_style": "gem", "unlock_desc": ""
    },
    "twinkle_orb": {
        "id": "twinkle_orb", "name": "Twinkle", "desc": "Göz kırpan minik yıldızlar",
        "color1": (255, 245, 170), "color2": (120, 235, 220), "glow1": (255, 245, 180), "glow2": (130, 240, 225),
        "tether_type": "stardust", "tether_color": (255, 240, 170), "orb_style": "ring", "unlock_desc": ""
    },
    "stargazer": {
        "id": "stargazer", "name": "Stargazer", "desc": "İlk yıldızlarını toplayan gözcü",
        "color1": (150, 175, 255), "color2": (255, 255, 255), "glow1": (160, 185, 255), "glow2": (240, 245, 255),
        "tether_type": "pulse_wave", "tether_color": (160, 185, 255), "orb_style": "moon", "unlock_desc": ""
    },
}

SKIN_LIST = list(SKINS.keys())
import skin_catalog as _catalog
# catalogue order (themes, then Legendary -> Common); Legendary skins are the "premium" ones that can also be bought with real money
SKIN_LIST = [k for k in _catalog.ORDER if k in SKINS] + [k for k in SKINS if k not in _catalog.THEME_OF]
PREMIUM_SKINS = [k for k in SKIN_LIST if _catalog.tier(k) == 1 and k not in _catalog.STAR_COST]

# Look-alikes separated (1.0.5): the Legendary original keeps its look, the cheaper twin gets its own identity.
_RETUNE = {
    # Saturn Ring (Legendary) and Gas Giant (Rare) were the same orange/violet ringed planet
    "gas_giant": {"color1": (70, 205, 190), "color2": (245, 175, 80), "glow1": (80, 215, 200), "glow2": (250, 185, 90),
                  "tether_type": "segmented", "tether_color": (90, 220, 205)},
    # five orange-red suns: Supernova (L) and Inferno Dragon (E) stay, the others move away from it
    "solar_nova": {"color1": (255, 80, 150), "color2": (255, 200, 90), "glow1": (255, 95, 160), "glow2": (255, 205, 100),
                   "tether_color": (255, 120, 170)},
    "mars_rover": {"color1": (190, 95, 60), "color2": (225, 170, 125), "glow1": (200, 105, 70), "glow2": (235, 180, 135),
                   "orb_style": "planet", "tether_type": "segmented", "tether_color": (200, 120, 80)},
    "red_dwarf": {"color1": (200, 30, 55), "color2": (255, 110, 90), "glow1": (215, 40, 65), "glow2": (255, 120, 100)},
    # Quartz (Common) looked like Frost Crystal / Quantum Lattice: rose quartz now
    "quartz": {"color1": (255, 175, 205), "color2": (255, 225, 240), "glow1": (255, 185, 215), "glow2": (255, 230, 245),
               "tether_color": (255, 190, 215)},
    # the most expensive item in the game: a brilliant-cut diamond with rainbow fire
    "diamond_prestige": {"orb_style": "brilliant", "color1": (225, 245, 255), "color2": (205, 230, 255),
                         "glow1": (170, 225, 255), "glow2": (200, 210, 255), "tether_color": (220, 240, 255)},
}
for _sid, _ch in _RETUNE.items():
    if _sid in SKINS:
        SKINS[_sid].update(_ch)

# Every catalogue its own look (1.0.6): too many catalogues used the same smiling face and look-alike tethers, so a
# Kutup skin could pass for an Okyanus one. Each theme now keeps to its own motif - ocean bubbles, ice shards, ghost
# wisps, crowns, honeycomb, nebula - without adding a single skin.
_THEME_RETUNE = {
    # Kara Delik: dark cores and swirling nebula, no flowers
    "stardust_dream": {"orb_style": "void", "tether_type": "nebula_spiral", "tether_color": (220, 150, 255),
                       "color1": (200, 130, 255), "color2": (255, 150, 210), "glow1": (190, 110, 255), "glow2": (255, 140, 205)},
    "galactic_nebula": {"tether_type": "accretion"},
    # Yıldız Yağmuru: stars and starlight
    "comet_tail": {"orb_style": "star", "tether_type": "starlight", "tether_color": (200, 225, 255)},
    "starry_pastel": {"tether_type": "starlight"},
    # Kristal Mağara: crystal lattice and ice
    "pixel_probe": {"tether_type": "lattice"},
    "moon_dust": {"tether_type": "ice_shards"},
    # Kraliyet: crowns, halos, gold
    "little_prince": {"orb_style": "crown", "tether_type": "star_chain", "tether_color": (255, 215, 90),
                      "color1": (255, 215, 90), "color2": (160, 120, 255), "glow1": (255, 205, 80), "glow2": (170, 130, 255)},
    "golden_crown": {"tether_type": "star_chain"},
    # Orman Dostları: honeycomb and forest creatures
    "lemon_chick": {"orb_style": "chick"},
    "panda_boba": {"tether_type": "honeycomb", "tether_color": (150, 220, 150)},
    "sakura_fox": {"tether_type": "honeycomb", "tether_color": (255, 170, 120)},
    # Okyanus: bubbles, blobs and jelly - no faces
    "nebula_koi": {"orb_style": "blob", "color1": (255, 140, 90), "color2": (90, 220, 230),
                   "glow1": (255, 150, 100), "glow2": (100, 230, 240)},
    "mint_blob": {"orb_style": "bubble"},
    "jelly_drift": {"tether_type": "ocean_bubbles"},
    # Gölgeler: ghosts and wisps
    "alien_slime": {"orb_style": "blob", "tether_type": "ghost_wisps", "tether_color": (140, 255, 140)},
    "toxic_hazard": {"tether_type": "ghost_wisps", "tether_color": (200, 255, 80)},
    # Kutup: ice shards everywhere, frosty colours
    "snowball": {"orb_style": "moon", "tether_type": "ice_shards", "tether_color": (200, 235, 255),
                 "color1": (225, 240, 255), "color2": (170, 210, 255), "glow1": (230, 245, 255), "glow2": (180, 220, 255)},
    "frost_fox": {"tether_type": "ice_shards"},
    "starlight_chick": {"tether_type": "ice_shards"},
    "cosmic_penguin": {"tether_type": "ice_shards"},
}
for _sid, _ch in _THEME_RETUNE.items():
    if _sid in SKINS:
        SKINS[_sid].update(_ch)

_TIER_OF = {k: _catalog.tier(k) for k in SKINS}
_GOLD = (255, 205, 80)
_EPIC = (200, 120, 255)


def _hue(h):
    """Fully saturated colour for hue h in [0, 1) (rainbow glints)."""
    h = (h % 1.0) * 6.0
    i, f = int(h), h - int(h)
    q, t_ = int(255 * (1 - f)), int(255 * f)
    return [(255, t_, 0), (q, 255, 0), (0, 255, t_), (0, q, 255), (t_, 0, 255), (255, 0, q)][i % 6]


def _draw_brilliant(surface, x, y, rad, color, tv):
    """Brilliant-cut diamond seen from above: octagonal girdle, eight star facets, a bright table, rainbow fire."""
    ring = [(x + math.cos(k * math.pi / 4 + math.pi / 8) * rad * 1.12, y + math.sin(k * math.pi / 4 + math.pi / 8) * rad * 1.12)
            for k in range(8)]
    table = [(x + math.cos(k * math.pi / 4 + math.pi / 8) * rad * 0.52, y + math.sin(k * math.pi / 4 + math.pi / 8) * rad * 0.52)
             for k in range(8)]
    cr, cg, cb = color[:3]
    tones = [(cr, cg, cb), (int(cr * 0.62), int(cg * 0.72), int(cb * 0.86)), (min(255, cr + 30), min(255, cg + 20), 255),
             (int(cr * 0.8), int(cg * 0.85), int(cb * 0.95))]
    for k in range(8):
        pygame.draw.polygon(surface, tones[k % 4], [ring[k], ring[(k + 1) % 8], table[(k + 1) % 8], table[k]])
    pygame.draw.polygon(surface, (250, 253, 255), table)
    pygame.draw.polygon(surface, (150, 200, 240), table, 1)
    for k in range(8):
        pygame.draw.line(surface, (140, 190, 235), table[k], ring[k], 1)
    pygame.draw.polygon(surface, (255, 255, 255), ring, max(1, rad // 9))
    for j in range(3):                                         # rainbow fire flashing across the facets
        a = tv * 1.7 + j * 2.1
        gx, gy = x + math.cos(a) * rad * 0.72, y + math.sin(a * 1.3) * rad * 0.62
        c = _hue(tv * 0.25 + j / 3.0)
        s = max(2, rad // 5)
        pygame.draw.line(surface, c, (gx - s, gy), (gx + s, gy), 2)
        pygame.draw.line(surface, c, (gx, gy - s), (gx, gy + s), 2)


def _draw_tier_fx(surface, x, y, rad, tier, glow, tv):
    """Rarity you can see: Legendary = turning golden crown of dashes + orbiting sparkles, Epic = a satellite on an
    orbit, Rare = a fine ring. Plain lines only (no alpha surfaces): nothing extra for the frame rate."""
    if tier == 1:
        rr = rad + 5
        box = pygame.Rect(x - rr, y - rr, 2 * rr, 2 * rr)
        for k in range(6):
            a = tv * 1.4 + k * math.pi / 3
            pygame.draw.arc(surface, _GOLD, box, a, a + 0.55, 2)
        for k in range(3):
            a = -tv * 2.2 + k * 2 * math.pi / 3
            sx, sy = x + math.cos(a) * (rad + 9), y + math.sin(a) * (rad + 9)
            s = 2 + int(1.2 * (1 + math.sin(tv * 6 + k)))
            pygame.draw.line(surface, (255, 250, 220), (sx - s, sy), (sx + s, sy), 2)
            pygame.draw.line(surface, (255, 250, 220), (sx, sy - s), (sx, sy + s), 2)
    elif tier == 2:
        rr = rad + 5
        mix = tuple((a + b) // 2 for a, b in zip(_EPIC, glow[:3]))
        box = pygame.Rect(x - rr, y - rr, 2 * rr, 2 * rr)
        a0 = tv * 1.1
        pygame.draw.arc(surface, mix, box, a0, a0 + 1.9, 2)
        pygame.draw.arc(surface, mix, box, a0 + math.pi, a0 + math.pi + 1.9, 2)
        a = tv * 3.0
        for j, (dr, dc) in enumerate(((0.0, 1.0), (0.35, 0.6), (0.7, 0.35))):   # satellite + fading tail
            c = tuple(int(v * dc) for v in (235, 210, 255))
            pygame.draw.circle(surface, c, (int(x + math.cos(a - dr) * rr), int(y + math.sin(a - dr) * rr)), max(1, 3 - j))
    elif tier == 3:
        c = tuple(int(v * 0.8) for v in glow[:3])
        pygame.draw.circle(surface, c, (x, y), rad + 4, 1)

def get_skin(skin_id):
    return SKINS.get(skin_id, SKINS["neon_pulse"])

_SCRATCH = {}
_DUST = [(_r.random(), _r.uniform(-13, 13)) for _r in [random.Random(5)] for _ in range(24)]


def _scratch(surface, p1, p2, pad=28):
    """Reusable full-size alpha scratch surface; only the bounding box of the tether is cleared/blitted.
    pad: the widest tether style reaches 17 px past the segment's bounding box (measured over all styles,
    angles and times), so 28 is safe - and the blended area is about half of what the old 70 px cost."""
    size = surface.get_size()
    sc = _SCRATCH.get(size)
    if sc is None:
        sc = pygame.Surface(size, pygame.SRCALPHA)
        _SCRATCH[size] = sc
    x0 = int(min(p1[0], p2[0])) - pad
    y0 = int(min(p1[1], p2[1])) - pad
    x1 = int(max(p1[0], p2[0])) + pad
    y1 = int(max(p1[1], p2[1])) + pad
    bb = pygame.Rect(x0, y0, x1 - x0, y1 - y0).clip(pygame.Rect(0, 0, size[0], size[1]))
    sc.fill((0, 0, 0, 0), bb)
    return sc, bb


_SHAPE_STYLES = ("ring", "cube", "sun", "planet", "gem", "flower", "half", "bubble", "paw", "blob", "moon", "ghost", "striped")

TRAIL_BY_TETHER = {"hearts": "heart", "star_chain": "star", "stardust": "star", "pastel_stardust": "star", "comet": "star",
                   "ocean_bubbles": "bubble", "boba_bubbles": "bubble", "bubble": "bubble", "pixel_chain": "pixel",
                   "flame_arc": "flame", "sparks": "flame", "accretion": "flame", "ice_shards": "snow", "paw_chain": "paw",
                   "rainbow": "rainbow", "lightning": "bolt", "aurora_wave": "star", "ghost_wisps": "wisp", "lattice": "pixel",
                   "honeycomb": "hex", "jelly_ribbon": "bubble", "double_helix": "star"}


def trail_kind(skin):
    """Shape of the particles this skin leaves behind / explodes into (default: plain dots)."""
    return skin.get("trail") or TRAIL_BY_TETHER.get(skin.get("tether_type"), "circle")


def _draw_shape_orb(surface, x, y, rad, color, tv, style):
    cr, cg, cb = color[:3]
    body = (cr, cg, cb)
    dark = (int(cr * 0.45), int(cg * 0.45), int(cb * 0.45))
    light = (min(255, cr + 90), min(255, cg + 90), min(255, cb + 90))
    white = (255, 255, 255)
    if style == "ring":
        pygame.draw.circle(surface, dark, (x, y), rad)
        pygame.draw.circle(surface, body, (x, y), rad, max(3, rad // 3))
        pygame.draw.circle(surface, light, (x, y), max(2, rad // 3))
        pygame.draw.circle(surface, white, (x - rad // 3, y - rad // 3), max(1, rad // 6))
    elif style == "cube":
        r = pygame.Rect(0, 0, int(rad * 1.75), int(rad * 1.75))
        r.center = (x, y)
        pygame.draw.rect(surface, body, r, border_radius=max(2, rad // 4))
        pygame.draw.rect(surface, light, r, max(1, rad // 6), border_radius=max(2, rad // 4))
        for dx, dy in ((-0.35, -0.35), (0.35, 0.35), (0.35, -0.35)):
            pygame.draw.rect(surface, dark, (int(x + dx * rad) - max(1, rad // 6), int(y + dy * rad) - max(1, rad // 6), max(2, rad // 3), max(2, rad // 3)))
    elif style == "sun":
        for k in range(12):
            a = tv * 1.2 + k * math.pi / 6.0
            pts = [(x + math.cos(a - 0.14) * rad * 0.9, y + math.sin(a - 0.14) * rad * 0.9),
                   (x + math.cos(a) * rad * 1.45, y + math.sin(a) * rad * 1.45),
                   (x + math.cos(a + 0.14) * rad * 0.9, y + math.sin(a + 0.14) * rad * 0.9)]
            pygame.draw.polygon(surface, light, pts)
        pygame.draw.circle(surface, body, (x, y), int(rad * 0.85))
        pygame.draw.circle(surface, white, (x - rad // 4, y - rad // 4), max(1, rad // 4))
    elif style == "planet":
        pygame.draw.circle(surface, body, (x, y), int(rad * 0.82))
        pygame.draw.circle(surface, light, (x - rad // 4, y - rad // 4), max(2, rad // 3))
        er = pygame.Rect(0, 0, int(rad * 2.5), int(rad * 0.85))
        er.center = (x, y)
        pygame.draw.ellipse(surface, light, er, max(2, rad // 5))
        pygame.draw.arc(surface, body, er, math.pi, 2 * math.pi, max(2, rad // 5))
    elif style == "gem":
        pts = [(x, y - rad * 1.25), (x + rad * 0.95, y - rad * 0.35), (x + rad * 0.6, y + rad * 1.0), (x - rad * 0.6, y + rad * 1.0), (x - rad * 0.95, y - rad * 0.35)]
        pygame.draw.polygon(surface, body, pts)
        pygame.draw.polygon(surface, light, [pts[0], pts[1], (x, y)])
        pygame.draw.polygon(surface, dark, [pts[3], pts[2], (x, y)])
        pygame.draw.polygon(surface, white, pts, max(1, rad // 8))
    elif style == "flower":
        for k in range(5):
            a = tv * 0.7 + k * 2 * math.pi / 5.0
            pygame.draw.circle(surface, body, (int(x + math.cos(a) * rad * 0.7), int(y + math.sin(a) * rad * 0.7)), max(2, int(rad * 0.55)))
            pygame.draw.circle(surface, light, (int(x + math.cos(a) * rad * 0.7), int(y + math.sin(a) * rad * 0.7)), max(1, int(rad * 0.3)))
        pygame.draw.circle(surface, (255, 225, 90), (x, y), max(2, int(rad * 0.42)))
    elif style == "half":
        pygame.draw.circle(surface, white, (x, y), rad)
        rect = pygame.Rect(x - rad, y - rad, 2 * rad, 2 * rad)
        pygame.draw.arc(surface, body, rect, tv, tv + math.pi, max(2, rad))
        pygame.draw.circle(surface, body, (x, y), rad, max(2, rad // 6))
        pygame.draw.circle(surface, dark, (x, y), max(1, rad // 4))
    elif style == "bubble":
        pygame.draw.circle(surface, dark, (x, y), rad)
        pygame.draw.circle(surface, body, (x, y), rad, max(2, rad // 4))
        pygame.draw.arc(surface, white, pygame.Rect(x - rad + 3, y - rad + 3, 2 * rad - 6, 2 * rad - 6), 1.9, 2.9, max(2, rad // 5))
        pygame.draw.circle(surface, light, (x + rad // 3, y + rad // 3), max(1, rad // 5))
    elif style == "paw":
        pygame.draw.ellipse(surface, body, pygame.Rect(x - int(rad * 0.75), y - int(rad * 0.05), int(rad * 1.5), int(rad * 1.15)))
        for dx, dy, rr in ((-0.85, -0.5, 0.36), (-0.3, -0.95, 0.36), (0.3, -0.95, 0.36), (0.85, -0.5, 0.36)):
            pygame.draw.circle(surface, body, (int(x + dx * rad), int(y + dy * rad)), max(2, int(rad * rr)))
        pygame.draw.ellipse(surface, light, pygame.Rect(x - int(rad * 0.4), y + int(rad * 0.15), int(rad * 0.8), int(rad * 0.55)))
    elif style == "blob":
        pts = []
        for k in range(18):
            a = k * math.pi / 9.0
            rr = rad * (1.0 + 0.16 * math.sin(tv * 3.0 + k * 1.7))
            pts.append((x + math.cos(a) * rr, y + math.sin(a) * rr))
        pygame.draw.polygon(surface, body, pts)
        pygame.draw.circle(surface, light, (x - rad // 3, y - rad // 3), max(2, rad // 3))
        pygame.draw.circle(surface, white, (x - rad // 2, y - rad // 2), max(1, rad // 6))
    elif style == "moon":
        pygame.draw.circle(surface, body, (x, y), rad)
        for dx, dy, rr in ((-0.35, -0.3, 0.28), (0.4, 0.15, 0.2), (-0.1, 0.5, 0.16)):
            pygame.draw.circle(surface, dark, (int(x + dx * rad), int(y + dy * rad)), max(1, int(rr * rad)))
        pygame.draw.circle(surface, light, (x, y), rad, max(1, rad // 8))
    elif style == "ghost":
        top = pygame.Rect(x - rad, y - rad, 2 * rad, 2 * rad)
        pygame.draw.ellipse(surface, body, top)
        pygame.draw.rect(surface, body, (x - rad, y, 2 * rad, int(rad * 0.85)))
        for k in range(3):
            wx = x - rad + (k + 0.5) * rad * 2 / 3.0
            wave = math.sin(tv * 5.0 + k) * 2
            pygame.draw.polygon(surface, (14, 16, 26), [(wx - rad / 3.0, y + rad * 0.85), (wx, y + rad * 0.5 + wave), (wx + rad / 3.0, y + rad * 0.85)])
        for sx in (-1, 1):
            pygame.draw.circle(surface, (20, 20, 40), (x + int(sx * rad * 0.35), y - int(rad * 0.15)), max(1, rad // 5))
    elif style == "striped":
        pygame.draw.circle(surface, body, (x, y), rad)
        for k, off in enumerate((-0.45, 0.05, 0.55)):
            hw = math.sqrt(max(0.0, 1.0 - off * off)) * rad
            pygame.draw.line(surface, (40, 30, 20), (x - hw, y + off * rad), (x + hw, y + off * rad), max(2, rad // 4))
        pygame.draw.circle(surface, light, (x - rad // 3, y - rad // 2), max(1, rad // 6))


_FACE_STYLES = ("face", "cat", "bunny", "unicorn", "angel", "crown", "heart", "fox", "panda", "puppy", "chick")


def _hsv(h, sat=0.55, val=1.0):
    import colorsys
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, sat, val)
    return int(r * 255), int(g * 255), int(b * 255)


def _heart_pts(x, y, size):
    pts = []
    for i in range(22):
        a = i * 2.0 * math.pi / 22.0
        hx = 16.0 * math.sin(a) ** 3
        hy = -(13.0 * math.cos(a) - 5.0 * math.cos(2 * a) - 2.0 * math.cos(3 * a) - math.cos(4 * a))
        pts.append((x + hx * size / 16.0, y + 1.0 + hy * size / 16.0))
    return pts


def _draw_kawaii(surface, x, y, rad, color, time_val, style):
    """Orb with a cute face; `style` adds ears / horn / halo / crown / heart body."""
    cr, cg, cb = color[:3]
    body = (cr, cg, cb)
    light = (min(255, cr + 70), min(255, cg + 70), min(255, cb + 70))
    pink = (255, 170, 195)
    edge = (int(cr * 0.55), int(cg * 0.55), int(cb * 0.55))
    ew = max(1, int(rad * 0.09))
    if style == "cat":
        for sx in (-1, 1):
            pts = [(x + sx * rad * 0.98, y - rad * 0.15), (x + sx * rad * 0.62, y - rad * 1.32), (x + sx * rad * 0.1, y - rad * 0.86)]
            pygame.draw.polygon(surface, body, pts)
            pygame.draw.polygon(surface, edge, pts, ew)
            pygame.draw.polygon(surface, pink, [(x + sx * rad * 0.8, y - rad * 0.5), (x + sx * rad * 0.62, y - rad * 1.02), (x + sx * rad * 0.34, y - rad * 0.78)])
    elif style == "bunny":
        for sx in (-1, 1):
            ex, ey = x + sx * rad * 0.42, y - rad * 1.32
            sway = math.sin(time_val * 3.0 + sx) * rad * 0.06
            pygame.draw.ellipse(surface, body, pygame.Rect(int(ex - rad * 0.24 + sway), int(ey - rad * 0.7), max(2, int(rad * 0.48)), max(3, int(rad * 1.4))))
            pygame.draw.ellipse(surface, edge, pygame.Rect(int(ex - rad * 0.24 + sway), int(ey - rad * 0.7), max(2, int(rad * 0.48)), max(3, int(rad * 1.4))), ew)
            pygame.draw.ellipse(surface, pink, pygame.Rect(int(ex - rad * 0.11 + sway), int(ey - rad * 0.5), max(1, int(rad * 0.22)), max(2, int(rad * 0.98))))
    elif style == "unicorn":
        for sx in (-1, 1):
            up = [(x + sx * rad * 0.95, y - rad * 0.3), (x + sx * rad * 0.72, y - rad * 1.12), (x + sx * rad * 0.3, y - rad * 0.8)]
            pygame.draw.polygon(surface, body, up)
            pygame.draw.polygon(surface, edge, up, ew)
    elif style == "fox":
        for sx in (-1, 1):
            pts = [(x + sx * rad * 0.96, y - rad * 0.2), (x + sx * rad * 0.65, y - rad * 1.45), (x + sx * rad * 0.15, y - rad * 0.85)]
            pygame.draw.polygon(surface, body, pts)
            pygame.draw.polygon(surface, edge, pts, ew)
            pygame.draw.polygon(surface, (255, 240, 235), [(x + sx * rad * 0.78, y - rad * 0.45), (x + sx * rad * 0.62, y - rad * 1.18), (x + sx * rad * 0.34, y - rad * 0.76)])
    elif style == "panda":
        for sx in (-1, 1):
            ex, ey = int(x + sx * rad * 0.74), int(y - rad * 0.88)
            pygame.draw.circle(surface, (32, 34, 44), (ex, ey), max(2, int(rad * 0.42)))
            pygame.draw.circle(surface, (16, 18, 26), (ex, ey), max(2, int(rad * 0.42)), ew)
    elif style == "puppy":
        for sx in (-1, 1):
            ex, ey = x + sx * rad * 0.76, y - rad * 0.1
            sway = math.sin(time_val * 3.0 + sx) * rad * 0.06
            pygame.draw.ellipse(surface, (195, 130, 80), pygame.Rect(int(ex - rad * 0.3 + sway), int(ey), max(2, int(rad * 0.58)), max(3, int(rad * 1.15))))
            pygame.draw.ellipse(surface, (140, 85, 45), pygame.Rect(int(ex - rad * 0.3 + sway), int(ey), max(2, int(rad * 0.58)), max(3, int(rad * 1.15))), ew)
    elif style == "chick":
        pygame.draw.polygon(surface, (255, 195, 30), [(x - rad * 0.18, y - rad * 0.92), (x, y - rad * 1.45), (x + rad * 0.18, y - rad * 0.92)])
        pygame.draw.polygon(surface, (255, 235, 100), [(x - rad * 0.1, y - rad * 0.95), (x, y - rad * 1.3), (x + rad * 0.1, y - rad * 0.95)])

    if style == "heart":
        pygame.draw.polygon(surface, body, _heart_pts(x, y - rad * 0.05, rad * 1.18))
        pygame.draw.polygon(surface, light, _heart_pts(x - rad * 0.12, y - rad * 0.12, rad * 0.7))
    else:
        pygame.draw.circle(surface, body, (x, y), rad)
        pygame.draw.circle(surface, edge, (x, y), rad, ew)
        pygame.draw.circle(surface, light, (x - int(rad * 0.18), y - int(rad * 0.2)), max(2, int(rad * 0.62)))

    # face
    ex = rad * 0.34
    ey = y + rad * (0.02 if style != "heart" else 0.12)
    er = max(1, int(rad * 0.15))
    blink = (time_val % 3.6) > 3.47
    for sx in (-1, 1):
        cx = int(x + sx * ex)
        if blink:
            pygame.draw.line(surface, (48, 32, 60), (cx - er, int(ey)), (cx + er, int(ey)), max(1, er // 2))
        else:
            pygame.draw.circle(surface, (44, 30, 58), (cx, int(ey)), er + (1 if rad >= 16 else 0))
            if rad >= 12:
                pygame.draw.circle(surface, (255, 255, 255), (cx - max(1, er // 3), int(ey) - max(1, er // 3)), max(1, er // 2))
    if rad >= 11:
        bl = max(3, int(rad * 0.5))
        bh = max(2, int(rad * 0.28))
        bs = pygame.Surface((bl, bh), pygame.SRCALPHA)
        pygame.draw.ellipse(bs, (255, 110, 150, 150), bs.get_rect())
        for sx in (-1, 1):
            surface.blit(bs, (int(x + sx * rad * 0.62 - bl / 2), int(ey + rad * 0.18)))
    mw, mh = max(3, int(rad * 0.44)), max(2, int(rad * 0.32))
    pygame.draw.arc(surface, (70, 40, 70), pygame.Rect(int(x - mw / 2), int(ey + rad * 0.08), mw, mh), math.pi, 2 * math.pi, max(1, int(rad * 0.1)))

    # accessories in front
    if style == "unicorn":
        pygame.draw.polygon(surface, (255, 222, 110), [(x - rad * 0.16, y - rad * 0.86), (x + rad * 0.16, y - rad * 0.86), (x, y - rad * 1.7)])
        pygame.draw.line(surface, (255, 250, 200), (x - rad * 0.06, y - rad * 1.0), (x + rad * 0.05, y - rad * 1.3), 1)
    elif style == "angel":
        hy = y - rad * 1.15 + math.sin(time_val * 3.0) * rad * 0.06
        pygame.draw.ellipse(surface, (255, 225, 110), pygame.Rect(int(x - rad * 0.62), int(hy - rad * 0.16), int(rad * 1.24), max(3, int(rad * 0.36))), max(2, int(rad * 0.14)))
    elif style == "crown":
        cy0 = y - rad * 0.86
        pts = [(x - rad * 0.7, cy0), (x - rad * 0.72, cy0 - rad * 0.68), (x - rad * 0.32, cy0 - rad * 0.3), (x, cy0 - rad * 0.8),
               (x + rad * 0.32, cy0 - rad * 0.3), (x + rad * 0.72, cy0 - rad * 0.68), (x + rad * 0.7, cy0)]
        pygame.draw.polygon(surface, (255, 218, 70), pts)
        pygame.draw.polygon(surface, (255, 250, 200), pts, 1)
        pygame.draw.circle(surface, (255, 80, 120), (int(x), int(cy0 - rad * 0.32)), max(1, int(rad * 0.1)))


def _flush(surface, sc, bb):
    surface.blit(sc, bb.topleft, area=bb, special_flags=pygame.BLEND_ADD)


def draw_tether(surface, p1, p2, skin_data, time_val=0.0):
    x1, y1 = p1
    x2, y2 = p2
    tether_type = skin_data.get("tether_type", "laser")
    tether_color = skin_data.get("tether_color", (0, 240, 255))
    dx = x2 - x1
    dy = y2 - y1
    dist = math.hypot(dx, dy)
    if dist < 1:
        return

    nx = dx / dist
    ny = dy / dist
    # Perpendicular normal
    px = -ny
    py = nx

    if tether_type == "laser":
        # Multi-layer glowing laser beam
        glow_surf, _bb = _scratch(surface, p1, p2)
        r, g, b = tether_color[:3]
        pygame.draw.line(glow_surf, (r, g, b, 60), (x1, y1), (x2, y2), 7)
        pygame.draw.line(glow_surf, (r, g, b, 140), (x1, y1), (x2, y2), 4)
        pygame.draw.line(glow_surf, (255, 255, 255, 230), (x1, y1), (x2, y2), 2)
        _flush(surface, glow_surf, _bb)

    elif tether_type == "segmented":
        # Dashed digital data stream
        num_segments = 14
        seg_len = dist / num_segments
        glow_surf, _bb = _scratch(surface, p1, p2)
        r, g, b = tether_color[:3]
        offset = (time_val * 45) % seg_len
        for i in range(num_segments):
            d1 = i * seg_len + offset
            d2 = d1 + seg_len * 0.55
            if d2 > dist:
                d2 = dist
            if d1 < dist:
                sx = x1 + nx * d1
                sy = y1 + ny * d1
                ex = x1 + nx * d2
                ey = y1 + ny * d2
                pygame.draw.line(glow_surf, (r, g, b, 220), (sx, sy), (ex, ey), 3)
                pygame.draw.line(glow_surf, (220, 255, 230, 255), (sx, sy), (ex, ey), 1)
        _flush(surface, glow_surf, _bb)

    elif tether_type == "chain":
        # Interlocking steel links. Alternating link planes make the chain readable
        # even in the small collection/shop previews.
        glow_surf, _bb = _scratch(surface, p1, p2)
        r, g, b = tether_color[:3]
        r2, g2, b2 = skin_data.get("tether_color2", tether_color)[:3]
        # fine links: as slim as the other skins' tethers (the old 8 px chain looked heavy next to them)
        link_count = max(5, int(dist / 10))
        half_long = min(5.5, dist / max(6, link_count) * 0.46)
        half_short = 2.2
        pygame.draw.line(glow_surf, (r, g, b, 40), (x1, y1), (x2, y2), 4)
        for i in range(link_count + 1):
            frac = i / link_count
            cx = x1 + dx * frac
            cy = y1 + dy * frac
            if i % 2:
                ax, ay, bx, by = px, py, nx, ny
            else:
                ax, ay, bx, by = nx, ny, px, py
            pts = [
                (cx + ax * half_long + bx * half_short, cy + ay * half_long + by * half_short),
                (cx - ax * half_long + bx * half_short, cy - ay * half_long + by * half_short),
                (cx - ax * half_long - bx * half_short, cy - ay * half_long - by * half_short),
                (cx + ax * half_long - bx * half_short, cy + ay * half_long - by * half_short),
            ]
            base = (r, g, b) if i % 2 == 0 else (r2, g2, b2)
            shadow = tuple(max(18, int(c * 0.38)) for c in base)
            shine = tuple(min(255, c + 72) for c in base)
            pygame.draw.lines(glow_surf, (*shadow, 200), True, pts, 3)
            pygame.draw.lines(glow_surf, (*base, 255), True, pts, 2)
            pygame.draw.lines(glow_surf, (*shine, 235), True, pts, 1)
        _flush(surface, glow_surf, _bb)

    elif tether_type == "plasma":
        # Fluctuating fiery plasma beam
        glow_surf, _bb = _scratch(surface, p1, p2)
        steps = 16
        pts = [(x1, y1)]
        for i in range(1, steps):
            frac = i / steps
            wave = math.sin(time_val * 12 + frac * math.pi * 4) * 4.0 * math.sin(frac * math.pi)
            bx = x1 + nx * (dist * frac) + px * wave
            by = y1 + ny * (dist * frac) + py * wave
            pts.append((bx, by))
        pts.append((x2, y2))
        r, g, b = tether_color[:3]
        pygame.draw.lines(glow_surf, (r, g, b, 80), False, pts, 8)
        pygame.draw.lines(glow_surf, (255, 180, 50, 180), False, pts, 4)
        pygame.draw.lines(glow_surf, (255, 255, 200, 240), False, pts, 2)
        _flush(surface, glow_surf, _bb)

    elif tether_type == "lightning":
        # Jagged electric arc with pseudo-random fractal branch
        glow_surf, _bb = _scratch(surface, p1, p2)
        steps = 10
        pts = [(x1, y1)]
        rng = random.Random(int(time_val * 24))
        for i in range(1, steps):
            frac = i / steps
            jitter = rng.uniform(-7, 7) * math.sin(frac * math.pi)
            bx = x1 + nx * (dist * frac) + px * jitter
            by = y1 + ny * (dist * frac) + py * jitter
            pts.append((bx, by))
        pts.append((x2, y2))
        r, g, b = tether_color[:3]
        pygame.draw.lines(glow_surf, (r, g, b, 120), False, pts, 6)
        pygame.draw.lines(glow_surf, (255, 255, 255, 240), False, pts, 2)
        _flush(surface, glow_surf, _bb)

    elif tether_type == "double_helix":
        # Double entwined sine wave helix
        glow_surf, _bb = _scratch(surface, p1, p2)
        steps = 22
        pts1 = [(x1, y1)]
        pts2 = [(x1, y1)]
        for i in range(1, steps):
            frac = i / steps
            wave1 = math.sin(time_val * 6 + frac * math.pi * 6) * 7.0 * math.sin(frac * math.pi)
            wave2 = -wave1
            bx1 = x1 + nx * (dist * frac) + px * wave1
            by1 = y1 + ny * (dist * frac) + py * wave1
            bx2 = x1 + nx * (dist * frac) + px * wave2
            by2 = y1 + ny * (dist * frac) + py * wave2
            pts1.append((bx1, by1))
            pts2.append((bx2, by2))
        pts1.append((x2, y2))
        pts2.append((x2, y2))
        pygame.draw.lines(glow_surf, (255, 215, 50, 180), False, pts1, 3)
        pygame.draw.lines(glow_surf, (210, 90, 255, 180), False, pts2, 3)
        _flush(surface, glow_surf, _bb)

    elif tether_type == "boba_bubbles":
        # Creamy strawberry milk tether with sliding boba pearls
        glow_surf, _bb = _scratch(surface, p1, p2)
        pygame.draw.line(glow_surf, (255, 185, 205, 120), (x1, y1), (x2, y2), 6)
        pygame.draw.line(glow_surf, (255, 240, 245, 240), (x1, y1), (x2, y2), 2)
        for i in range(4):
            frac = ((time_val * 0.4 + i * 0.25) % 1.0)
            bx = x1 + nx * (dist * frac)
            by = y1 + ny * (dist * frac)
            pygame.draw.circle(glow_surf, (90, 50, 35, 220), (int(bx), int(by)), 5)
            pygame.draw.circle(glow_surf, (255, 220, 230, 200), (int(bx - 1), int(by - 1)), 2)
        _flush(surface, glow_surf, _bb)

    elif tether_type == "paw_chain":
        # Mint & peach pastel link with paw stamp nodes
        glow_surf, _bb = _scratch(surface, p1, p2)
        pygame.draw.line(glow_surf, (140, 245, 225, 110), (x1, y1), (x2, y2), 5)
        for i in range(3):
            frac = 0.25 + i * 0.25
            px_val = x1 + nx * (dist * frac)
            py_val = y1 + ny * (dist * frac)
            pygame.draw.circle(glow_surf, (255, 185, 210, 230), (int(px_val), int(py_val)), 4)
            pygame.draw.circle(glow_surf, (255, 255, 255, 240), (int(px_val), int(py_val)), 2)
        _flush(surface, glow_surf, _bb)

    elif tether_type == "jelly_ribbon":
        # Wavy translucent neon gummy jelly
        glow_surf, _bb = _scratch(surface, p1, p2)
        steps = 18
        pts = [(x1, y1)]
        for i in range(1, steps):
            frac = i / steps
            wave = math.sin(time_val * 10 + frac * math.pi * 5) * 5.0 * math.sin(frac * math.pi)
            bx = x1 + nx * (dist * frac) + px * wave
            by = y1 + ny * (dist * frac) + py * wave
            pts.append((bx, by))
        pts.append((x2, y2))
        pygame.draw.lines(glow_surf, (255, 80, 180, 130), False, pts, 7)
        pygame.draw.lines(glow_surf, (30, 250, 235, 220), False, pts, 3)
        _flush(surface, glow_surf, _bb)

    elif tether_type == "pastel_stardust":
        # Baby blue and buttery yellow stardust twine
        glow_surf, _bb = _scratch(surface, p1, p2)
        steps = 16
        pts1 = [(x1, y1)]
        pts2 = [(x1, y1)]
        for i in range(1, steps):
            frac = i / steps
            wave = math.sin(time_val * 7 + frac * math.pi * 4) * 4.5 * math.sin(frac * math.pi)
            pts1.append((x1 + nx * (dist * frac) + px * wave, y1 + ny * (dist * frac) + py * wave))
            pts2.append((x1 + nx * (dist * frac) - px * wave, y1 + ny * (dist * frac) - py * wave))
        pts1.append((x2, y2))
        pts2.append((x2, y2))
        pygame.draw.lines(glow_surf, (165, 215, 255, 180), False, pts1, 3)
        pygame.draw.lines(glow_surf, (255, 240, 150, 180), False, pts2, 3)
        _flush(surface, glow_surf, _bb)

    elif tether_type == "aurora_wave":
        glow_surf, _bb = _scratch(surface, p1, p2)
        steps = 20
        pts_e = [(x1, y1)]
        pts_v = [(x1, y1)]
        for i in range(1, steps):
            frac = i / steps
            wave1 = math.sin(time_val * 6.0 + frac * math.pi * 4) * 6.0 * math.sin(frac * math.pi)
            wave2 = math.cos(time_val * 5.0 + frac * math.pi * 3) * 5.0 * math.sin(frac * math.pi)
            pts_e.append((x1 + nx * (dist * frac) + px * wave1, y1 + ny * (dist * frac) + py * wave1))
            pts_v.append((x1 + nx * (dist * frac) + px * wave2, y1 + ny * (dist * frac) + py * wave2))
        pts_e.append((x2, y2))
        pts_v.append((x2, y2))
        pygame.draw.lines(glow_surf, (0, 255, 180, 130), False, pts_e, 5)
        pygame.draw.lines(glow_surf, (180, 70, 255, 140), False, pts_v, 4)
        pygame.draw.line(glow_surf, (240, 255, 255, 200), (x1, y1), (x2, y2), 2)
        _flush(surface, glow_surf, _bb)

    elif tether_type == "flame_arc":
        glow_surf, _bb = _scratch(surface, p1, p2)
        pygame.draw.line(glow_surf, (255, 60, 10, 140), (x1, y1), (x2, y2), 7)
        pygame.draw.line(glow_surf, (255, 180, 30, 220), (x1, y1), (x2, y2), 3)
        pygame.draw.line(glow_surf, (255, 255, 220, 240), (x1, y1), (x2, y2), 1)
        for i in range(6):
            frac = ((time_val * 1.5 + i * 0.18) % 1.0)
            jitter = math.sin(time_val * 15 + i * 3) * 5.0 * math.sin(frac * math.pi)
            ex = x1 + nx * (dist * frac) + px * jitter
            ey = y1 + ny * (dist * frac) + py * jitter
            pygame.draw.circle(glow_surf, (255, 220, 40, 220), (int(ex), int(ey)), 3)
        _flush(surface, glow_surf, _bb)

    elif tether_type == "ocean_bubbles":
        glow_surf, _bb = _scratch(surface, p1, p2)
        pygame.draw.line(glow_surf, (0, 220, 230, 100), (x1, y1), (x2, y2), 6)
        pygame.draw.line(glow_surf, (255, 100, 150, 120), (x1, y1), (x2, y2), 2)
        for i in range(5):
            frac = ((time_val * 0.5 + i * 0.22) % 1.0)
            b_off = math.sin(time_val * 8 + i * 2) * 4.0
            bx = x1 + nx * (dist * frac) + px * b_off
            by = y1 + ny * (dist * frac) + py * b_off
            pygame.draw.circle(glow_surf, (40, 255, 240, 220), (int(bx), int(by)), 4, 1)
            pygame.draw.circle(glow_surf, (255, 255, 255, 240), (int(bx - 1), int(by - 1)), 1)
        _flush(surface, glow_surf, _bb)

    elif tether_type == "hazard_pulse":
        glow_surf, _bb = _scratch(surface, p1, p2)
        pygame.draw.line(glow_surf, (90, 255, 20, 90), (x1, y1), (x2, y2), 7)
        segs = 8
        shift = (time_val * 6.0) % 2.0
        for i in range(segs):
            f1 = max(0.0, min(1.0, (i + shift) / (segs + 1)))
            f2 = max(0.0, min(1.0, (i + 0.6 + shift) / (segs + 1)))
            p_a = (x1 + nx * dist * f1, y1 + ny * dist * f1)
            p_b = (x1 + nx * dist * f2, y1 + ny * dist * f2)
            c = (245, 255, 40, 220) if i % 2 == 0 else (80, 255, 10, 220)
            pygame.draw.line(glow_surf, c, p_a, p_b, 4)
        _flush(surface, glow_surf, _bb)

    elif tether_type == "ghost_wisps":
        glow_surf, _bb = _scratch(surface, p1, p2)
        steps = 15
        pts = [(x1, y1)]
        for i in range(1, steps):
            frac = i / steps
            wisp = math.sin(time_val * 4 + frac * math.pi * 3) * 7.0 * math.sin(frac * math.pi)
            pts.append((x1 + nx * (dist * frac) + px * wisp, y1 + ny * (dist * frac) + py * wisp))
        pts.append((x2, y2))
        pygame.draw.lines(glow_surf, (190, 140, 255, 90), False, pts, 9)
        pygame.draw.lines(glow_surf, (220, 190, 255, 190), False, pts, 3)
        _flush(surface, glow_surf, _bb)

    elif tether_type == "nebula_spiral":
        glow_surf, _bb = _scratch(surface, p1, p2)
        steps = 18
        pts_a = [(x1, y1)]
        pts_b = [(x1, y1)]
        for i in range(1, steps):
            frac = i / steps
            a_rot = time_val * 8.0 + frac * math.pi * 6
            w = math.sin(a_rot) * 5.5 * math.sin(frac * math.pi)
            pts_a.append((x1 + nx * (dist * frac) + px * w, y1 + ny * (dist * frac) + py * w))
            pts_b.append((x1 + nx * (dist * frac) - px * w, y1 + ny * (dist * frac) - py * w))
        pts_a.append((x2, y2))
        pts_b.append((x2, y2))
        pygame.draw.lines(glow_surf, (160, 40, 255, 170), False, pts_a, 3)
        pygame.draw.lines(glow_surf, (255, 40, 160, 170), False, pts_b, 3)
        _flush(surface, glow_surf, _bb)

    elif tether_type == "ice_shards":
        glow_surf, _bb = _scratch(surface, p1, p2)
        pygame.draw.line(glow_surf, (140, 240, 255, 110), (x1, y1), (x2, y2), 6)
        pygame.draw.line(glow_surf, (245, 255, 255, 230), (x1, y1), (x2, y2), 2)
        for i in range(4):
            frac = 0.2 + i * 0.2
            cx_val = x1 + nx * (dist * frac)
            cy_val = y1 + ny * (dist * frac)
            pygame.draw.polygon(glow_surf, (200, 250, 255, 220), [
                (cx_val, cy_val - 5), (cx_val + 4, cy_val),
                (cx_val, cy_val + 5), (cx_val - 4, cy_val)
            ])
        _flush(surface, glow_surf, _bb)

    elif tether_type == "pixel_chain":
        glow_surf, _bb = _scratch(surface, p1, p2)
        pygame.draw.line(glow_surf, (0, 240, 200, 80), (x1, y1), (x2, y2), 4)
        p_count = 6
        shift = (time_val * 5.0) % 1.0
        for i in range(p_count):
            frac = (i + shift) / p_count
            if 0.1 <= frac <= 0.9:
                px_val = int(x1 + nx * (dist * frac))
                py_val = int(y1 + ny * (dist * frac))
                c = (255, 30, 140, 230) if i % 2 == 0 else (0, 255, 200, 230)
                pygame.draw.rect(glow_surf, c, (px_val - 3, py_val - 3, 6, 6))
        _flush(surface, glow_surf, _bb)

    elif tether_type == "honeycomb":
        glow_surf, _bb = _scratch(surface, p1, p2)
        pygame.draw.line(glow_surf, (255, 185, 20, 110), (x1, y1), (x2, y2), 5)
        for i in range(3):
            frac = 0.25 + i * 0.25
            hx = x1 + nx * (dist * frac)
            hy = y1 + ny * (dist * frac)
            hex_pts = []
            for hi in range(6):
                ha = hi * (math.pi / 3.0)
                hex_pts.append((hx + math.cos(ha) * 5, hy + math.sin(ha) * 5))
            pygame.draw.polygon(glow_surf, (255, 210, 40, 220), hex_pts, 2)
            pygame.draw.circle(glow_surf, (255, 245, 180, 240), (int(hx), int(hy)), 2)
        _flush(surface, glow_surf, _bb)

    elif tether_type == "stealth_pulse":
        glow_surf, _bb = _scratch(surface, p1, p2)
        pygame.draw.line(glow_surf, (120, 145, 175, 70), (x1, y1), (x2, y2), 4)
        p_frac = (time_val * 1.8) % 1.0
        px_val = x1 + nx * (dist * p_frac)
        py_val = y1 + ny * (dist * p_frac)
        pygame.draw.circle(glow_surf, (190, 245, 255, 240), (int(px_val), int(py_val)), 4)
        pygame.draw.circle(glow_surf, (255, 255, 255, 255), (int(px_val), int(py_val)), 2)
        _flush(surface, glow_surf, _bb)

    elif tether_type == "comet":
        glow_surf, _bb = _scratch(surface, p1, p2)
        n = 16
        for i in range(n):
            f = i / float(n - 1)
            cx, cy = x2 - nx * dist * f, y2 - ny * dist * f
            k = 1.0 - f
            col = (int(60 + 160 * k), int(110 + 130 * k), int(150 + 105 * k))
            pygame.draw.circle(glow_surf, col, (int(cx), int(cy)), max(1, int(1 + 5 * k)))
        for j in range(6):
            f = (time_val * 0.7 + j / 6.0) % 1.0
            o = math.sin(time_val * 5 + j * 2.1) * 9 * f
            pygame.draw.circle(glow_surf, (220, 245, 255), (int(x2 - nx * dist * f + px * o), int(y2 - ny * dist * f + py * o)), 2)
        _flush(surface, glow_surf, _bb)

    elif tether_type == "stardust":
        glow_surf, _bb = _scratch(surface, p1, p2)
        pygame.draw.line(glow_surf, (120, 80, 70), (x1, y1), (x2, y2), 1)
        for i, (f, o0) in enumerate(_DUST):
            tw = 0.5 + 0.5 * math.sin(time_val * 6 + i * 1.3)
            off = o0 * (1.0 + 0.3 * math.sin(time_val * 3 + i))
            col = (int(255 * (0.55 + 0.45 * tw)), min(255, int((150 + 60 * (i % 3)) * (0.5 + 0.5 * tw))), int(150 * (0.4 + 0.6 * tw)))
            pygame.draw.circle(glow_surf, col, (int(x1 + nx * dist * f + px * off), int(y1 + ny * dist * f + py * off)), 1 + (i % 3 == 0))
        _flush(surface, glow_surf, _bb)

    elif tether_type == "lattice":
        glow_surf, _bb = _scratch(surface, p1, p2)
        n = 8
        pts = [(x1, y1)]
        for i in range(1, n):
            f = i / float(n)
            off = (9 if i % 2 else -9) * (0.65 + 0.35 * math.sin(time_val * 4 + i))
            pts.append((x1 + nx * dist * f + px * off, y1 + ny * dist * f + py * off))
        pts.append((x2, y2))
        pygame.draw.lines(glow_surf, (30, 170, 120), False, pts, 5)
        pygame.draw.lines(glow_surf, (90, 255, 200), False, pts, 2)
        for pt in pts[1:-1]:
            pygame.draw.rect(glow_surf, (210, 255, 240), (int(pt[0]) - 3, int(pt[1]) - 3, 6, 6))
        _flush(surface, glow_surf, _bb)

    elif tether_type == "pulse_wave":
        glow_surf, _bb = _scratch(surface, p1, p2)
        pygame.draw.line(glow_surf, (95, 60, 140), (x1, y1), (x2, y2), 2)
        for k in range(3):
            f = (time_val * 0.9 + k / 3.0) % 1.0
            w = 13 * math.sin(math.pi * f)
            cx, cy = x1 + nx * dist * f, y1 + ny * dist * f
            pygame.draw.line(glow_surf, (235, 200, 255), (cx - px * w, cy - py * w), (cx + px * w, cy + py * w), 3)
            pygame.draw.circle(glow_surf, (255, 255, 255), (int(cx), int(cy)), 3)
        _flush(surface, glow_surf, _bb)

    elif tether_type == "sparks":
        glow_surf, _bb = _scratch(surface, p1, p2)
        rng = random.Random(int(time_val * 24))
        pts = [(x1, y1)]
        for i in range(1, 9):
            f = i / 9.0
            j = rng.uniform(-6, 6) * math.sin(f * math.pi)
            pts.append((x1 + nx * dist * f + px * j, y1 + ny * dist * f + py * j))
        pts.append((x2, y2))
        pygame.draw.lines(glow_surf, (150, 40, 20), False, pts, 6)
        pygame.draw.lines(glow_surf, (255, 110, 50), False, pts, 3)
        pygame.draw.lines(glow_surf, (255, 225, 140), False, pts, 1)
        for _ in range(7):
            f = rng.random()
            bx, by = x1 + nx * dist * f, y1 + ny * dist * f
            a = rng.uniform(0, 6.283)
            ln = rng.uniform(5, 15)
            pygame.draw.line(glow_surf, (255, 225, 150), (bx, by), (bx + math.cos(a) * ln, by + math.sin(a) * ln), 1)
        _flush(surface, glow_surf, _bb)

    elif tether_type == "accretion":
        glow_surf, _bb = _scratch(surface, p1, p2)
        pygame.draw.line(glow_surf, (55, 22, 8), (x1, y1), (x2, y2), 5)
        for i in range(10):
            f = (time_val * 0.55 + i / 10.0) % 1.0
            ang = time_val * 5 + i * 1.4
            off = math.sin(ang) * 9 * (1.0 - 0.5 * f)
            k = 1.0 - f
            col = (255, int(120 + 130 * f), int(30 + 190 * f * f))
            cx = x2 - nx * dist * f + px * off
            cy = y2 - ny * dist * f + py * off
            pygame.draw.circle(glow_surf, col, (int(cx), int(cy)), 2 + (k > 0.5))
        _flush(surface, glow_surf, _bb)

    elif tether_type == "rainbow":
        glow_surf, _bb = _scratch(surface, p1, p2)
        n = 14
        pts = []
        for i in range(n + 1):
            f = i / float(n)
            off = math.sin(time_val * 5.0 + i * 0.75) * 5.0 * math.sin(math.pi * f)
            pts.append((x1 + nx * dist * f + px * off, y1 + ny * dist * f + py * off))
        for i in range(n):
            pygame.draw.line(glow_surf, (*_hsv(time_val * 0.45 + i / float(n)), 210), pts[i], pts[i + 1], 6)
        pygame.draw.lines(glow_surf, (255, 255, 255, 170), False, pts, 2)
        _flush(surface, glow_surf, _bb)

    elif tether_type == "hearts":
        glow_surf, _bb = _scratch(surface, p1, p2)
        pygame.draw.line(glow_surf, (255, 120, 170, 70), (x1, y1), (x2, y2), 3)
        for k in range(5):
            f = (time_val * 0.45 + k / 5.0) % 1.0
            off = math.sin(time_val * 4.0 + k * 1.7) * 7.0
            size = 5.0 + 3.0 * math.sin(math.pi * f)
            hx, hy = x1 + nx * dist * f + px * off, y1 + ny * dist * f + py * off
            pygame.draw.polygon(glow_surf, (255, 120, 175, 235), _heart_pts(hx, hy, size))
        _flush(surface, glow_surf, _bb)

    elif tether_type == "star_chain":
        glow_surf, _bb = _scratch(surface, p1, p2)
        pygame.draw.line(glow_surf, (255, 235, 150, 70), (x1, y1), (x2, y2), 2)
        for k in range(6):
            f = (k + 0.5) / 6.0
            tw = 0.55 + 0.45 * math.sin(time_val * 6.0 + k * 1.3)
            sx_, sy_ = x1 + nx * dist * f + px * math.sin(time_val * 3.0 + k) * 4.0, y1 + ny * dist * f + py * math.sin(time_val * 3.0 + k) * 4.0
            rr = 3.0 + 4.0 * tw
            pts = []
            for i in range(10):
                r_ = rr if i % 2 == 0 else rr * 0.45
                a_ = -math.pi / 2 + i * math.pi / 5 + time_val
                pts.append((sx_ + math.cos(a_) * r_, sy_ + math.sin(a_) * r_))
            pygame.draw.polygon(glow_surf, (255, 240, 170, int(150 + 100 * tw)), pts)
        _flush(surface, glow_surf, _bb)

    else:
        # Standard soft ribbon
        glow_surf, _bb = _scratch(surface, p1, p2)
        r, g, b = tether_color[:3]
        pygame.draw.line(glow_surf, (r, g, b, 90), (x1, y1), (x2, y2), 6)
        pygame.draw.line(glow_surf, (255, 255, 255, 220), (x1, y1), (x2, y2), 2)
        _flush(surface, glow_surf, _bb)

def draw_orb(surface, pos, radius, color, glow_color, is_pivot=False, skin_data=None, time_val=0.0):
    x, y = int(pos[0]), int(pos[1])
    rad = int(radius)
    glow_rad = rad + (8 if is_pivot else 6)

    # 1. Outer ambient glow ring
    gr, gg, gb = glow_color[:3]
    pulse = 1.0 + 0.12 * math.sin(time_val * 8) if is_pivot else 1.0
    effective_glow = int(glow_rad * pulse)
    center = effective_glow + 5

    glow_key = ("glow", effective_glow, gr, gg, gb)
    glow_surf = _ORB_FX.get(glow_key)
    if glow_surf is None:
        glow_surf = pygame.Surface((center * 2, center * 2), pygame.SRCALPHA)
        pygame.draw.circle(glow_surf, (gr, gg, gb, 45), (center, center), effective_glow)
        pygame.draw.circle(glow_surf, (gr, gg, gb, 90), (center, center), int(effective_glow * 0.75))
        _ORB_FX.put(glow_key, glow_surf)
    surface.blit(glow_surf, (x - center, y - center), special_flags=pygame.BLEND_ADD)

    # 2/3. Orb body (per-skin style)
    cr, cg, cb = color[:3]
    style = (skin_data or {}).get("orb_style")
    if style == "void":
        pygame.draw.circle(surface, (3, 3, 8), (x, y), rad)
        pygame.draw.circle(surface, (cr, cg, cb), (x, y), rad, max(2, rad // 4))
        a0 = time_val * 3.0
        pygame.draw.arc(surface, (255, 240, 200), pygame.Rect(x - rad - 3, y - rad - 3, 2 * rad + 6, 2 * rad + 6), a0, a0 + 2.2, 3)
        pygame.draw.circle(surface, (min(255, cr + 60), min(255, cg + 60), min(255, cb + 60)), (x + rad // 3, y - rad // 3), max(1, rad // 6))
    elif style == "crystal":
        pts = [(x + math.cos(time_val * 0.8 + k * math.pi / 3) * rad * 1.1, y + math.sin(time_val * 0.8 + k * math.pi / 3) * rad * 1.1) for k in range(6)]
        pygame.draw.polygon(surface, (cr, cg, cb), pts)
        pygame.draw.polygon(surface, (min(255, cr + 110), min(255, cg + 110), min(255, cb + 110)), [pts[0], pts[1], (x, y)])
        pygame.draw.polygon(surface, (235, 255, 250), pts, 2)
        pygame.draw.circle(surface, (255, 255, 255), (x - rad // 4, y - rad // 4), max(1, rad // 5))
    elif style == "star":
        pts = []
        for k in range(16):
            rr = rad * (1.35 if k % 2 == 0 else 0.62)
            a = time_val * 1.6 + k * math.pi / 8.0
            pts.append((x + math.cos(a) * rr, y + math.sin(a) * rr))
        pygame.draw.polygon(surface, (cr, cg, cb), pts)
        pygame.draw.circle(surface, (min(255, cr + 90), min(255, cg + 90), min(255, cb + 90)), (x, y), max(2, int(rad * 0.62)))
        pygame.draw.circle(surface, (255, 255, 255), (x - rad // 5, y - rad // 5), max(1, rad // 4))
    elif style == "gear":
        # Industrial gear: broad, flat tooth faces instead of a star/saw silhouette.
        angle = time_val * 0.7 + (math.pi / 12 if is_pivot else 0.0)
        teeth = []
        tooth_count = 10
        root_r, tip_r = rad * 0.86, rad * 1.18
        step = math.tau / tooth_count
        # Four corners per tooth give each tooth a rectangular top and steep sides.
        for k in range(tooth_count):
            center_a = angle + k * step
            for offset, rr in ((-0.50, root_r), (-0.29, tip_r), (0.29, tip_r), (0.50, root_r)):
                a = center_a + offset * step
                teeth.append((x + math.cos(a) * rr, y + math.sin(a) * rr))
        dark = (max(10, cr // 6), max(22, cg // 4), max(14, cb // 5))
        metal = (cr, cg, cb)
        edge = (min(255, cr + 58), min(255, cg + 58), min(255, cb + 58))
        pygame.draw.polygon(surface, metal, teeth)
        pygame.draw.polygon(surface, edge, teeth, max(2, rad // 9))
        # A solid machined plate avoids a wheel/rim silhouette. Recessed bolt
        # holes and the keyed centre bore provide the mechanical detail.
        plate_r = max(4, int(rad * 0.80))
        pygame.draw.circle(surface, metal, (x, y), plate_r)
        pygame.draw.circle(surface, edge, (x, y), plate_r, max(2, rad // 10))
        pygame.draw.circle(surface, dark, (x, y), max(3, int(rad * 0.55)), max(2, rad // 9))
        bolt_r = max(1, int(rad * 0.075))
        for k in range(4):
            a = angle + math.pi / 4 + k * math.pi / 2
            bx = int(x + math.cos(a) * rad * 0.48)
            by = int(y + math.sin(a) * rad * 0.48)
            pygame.draw.circle(surface, dark, (bx, by), bolt_r)
            pygame.draw.circle(surface, edge, (bx, by), bolt_r, 1)
        bore = max(2, int(rad * 0.20))
        pygame.draw.circle(surface, dark, (x, y), bore)
        # Keyway notch makes the centre read as a shaft coupling rather than a hubcap.
        key_w = max(2, int(rad * 0.10))
        pygame.draw.rect(surface, dark, (x - key_w // 2, y - bore, key_w, max(2, int(rad * 0.13))))
        pygame.draw.circle(surface, edge, (x, y), bore, max(1, rad // 12))
    elif style == "brilliant":
        _draw_brilliant(surface, x, y, rad, color, time_val)
    elif style in _FACE_STYLES:
        _draw_kawaii(surface, x, y, rad, color, time_val, style)
    elif style in _SHAPE_STYLES:
        _draw_shape_orb(surface, x, y, rad, color, time_val, style)
    else:
        pygame.draw.circle(surface, (cr, cg, cb), (x, y), rad)
        inner_rad = max(2, int(rad * 0.55))
        highlight_color = (min(255, cr + 80), min(255, cg + 80), min(255, cb + 80))
        pygame.draw.circle(surface, highlight_color, (x - int(rad * 0.2), y - int(rad * 0.2)), inner_rad)
        pygame.draw.circle(surface, (255, 255, 255), (x - int(rad * 0.28), y - int(rad * 0.28)), max(1, int(inner_rad * 0.4)))

    # 3b. rarity ornament (Legendary / Epic / Rare)
    tier = _TIER_OF.get((skin_data or {}).get("id"))
    if tier and tier <= 3 and rad >= 8:
        _draw_tier_fx(surface, x, y, rad, tier, glow_color, time_val)

    # 4. Pivot indicator halo
    if is_pivot:
        h_center = rad + 8
        h_rad = rad + 4 + int(2 * math.sin(time_val * 10))
        halo_key = ("halo", rad, h_rad)
        halo_surf = _ORB_FX.get(halo_key)
        if halo_surf is None:
            halo_surf = pygame.Surface((rad * 2 + 16, rad * 2 + 16), pygame.SRCALPHA)
            pygame.draw.circle(halo_surf, (255, 255, 255, 180), (h_center, h_center), h_rad, 2)
            _ORB_FX.put(halo_key, halo_surf)
        surface.blit(halo_surf, (x - h_center, y - h_center), special_flags=pygame.BLEND_ADD)
