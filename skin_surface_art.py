"""Spherical skin materials: the surface is the design, never a framed icon."""
import math
import pygame
from render_cache import SurfaceCache

_CACHE = SurfaceCache(4 * 1024 * 1024)
_LIGHT_CACHE = SurfaceCache(1024 * 1024)
_MOVING = frozenset(("dragon", "aurora", "pulsar", "bolt", "jellyfish"))

# Preserve the game's signature orb and two related ring skins, plus Honey Bee.
PRESERVED_ART = frozenset(("neon_pulse", "solar_wind", "twinkle_orb", "honey_bee"))
# Related skins share a drawing vocabulary; IDs select layouts and details.
SURFACE_ART = {}
for _family, _ids in {
    "circuit": "cyber_phantom pixel_probe",
    "gear": "cyber_matrix",
    "bolt": "electric_storm",
    "pixel": "pixel_retro pixel_heart arcade_king",
    "solar": "solar_nova supernova red_dwarf streak_nova",
    "dragon": "inferno_dragon",
    "wind": "comet_rider",
    "rover": "mars_rover",
    "vortex": "event_horizon cosmic_void dark_matter stardust_dream",
    "nebula": "galactic_nebula big_bang",
    "pulsar": "neutron_star pulsar_beam",
    "comet_art": "comet_tail",
    "lunar": "starry_pastel ice_moon moon_dust stargazer",
    "lattice": "quantum_lattice frost_crystal",
    "quartz_cluster": "quartz",
    "bands": "saturn_ring gas_giant",
    "aurora": "aurora_borealis streak_aurora",
    "cat": "galaxy_cat astro_kitty solar_flare_cat berry_kitty snow_leopard",
    "unicorn": "rainbow_unicorn",
    "puppy": "sugar_puppy",
    "bunny": "bunny_moon cloud_bunny rocket_bunny",
    "mochi": "mochi_pal",
    "royal": "royal_crown golden_crown little_prince",
    "halo": "angel_halo comet_angel",
    "heart": "nova_heart diamond_heart",
    "gummy": "gummy_pop mint_blob alien_slime",
    "tea": "boba_tea",
    "petal": "sakura_dream sakura_fox",
    "panda": "panda_boba",
    "bear": "star_bear",
    "chick": "lemon_chick starlight_chick",
    "ocean": "leviathan deep_ocean",
    "koi": "nebula_koi",
    "jellyfish": "jelly_drift",
    "spectral": "void_walker phantom_wraith",
    "hazard": "toxic_hazard",
    "zen": "monochrome_zen bronze_prestige streak_spark",
    "penguin": "cosmic_penguin",
    "fox": "frost_fox",
    "snowflake": "snowball",
    "gamepad": "joystick",
    "coin": "coin_pop",
    "diamond": "diamond_prestige",
    "platinum": "platinum_prestige",
    "ingot": "gold_prestige",
    "silver": "silver_prestige",
    "star": "star_hunter starfall",
    "ember": "streak_flame streak_ember",
    "paw": "meow_paw",
}.items():
    for _sid in _ids.split():
        SURFACE_ART[_sid] = _family


def draw_surface_orb(surface, x, y, rad, color, style, tv, tier, sid=""):
    rad = max(1, int(rad))
    frame = int(tv * 8) % 48 if style in _MOVING and tier <= 3 else 0
    key = (rad, tuple(color[:3]), style, tier, frame, sid)
    art = _CACHE.get(key)
    if art is None:
        art = _build(rad, color[:3], style, frame / 8, tier, sid)
        _CACHE.put(key, art)
    surface.blit(art, (x - rad - 1, y - rad - 1))


def _build(r, color, style, t, tier, sid=""):
    size = 2 * r + 3
    c = r + 1
    art = pygame.Surface((size, size), pygame.SRCALPHA)
    light = tuple(min(255, int(v * .6 + 105)) for v in color)
    dark = tuple(max(12, int(v * .28)) for v in color)
    pale = (235, 247, 255)
    ink = (25, 27, 43)
    w = max(1, r // 12)
    variant = sum((i + 1) * ord(ch) for i, ch in enumerate(sid))
    phase = (variant % 17) / 17 * math.tau

    def p(a, b):
        return (round(c + a * r), round(c + b * r))

    def dot(a, b, rr, fill):
        pygame.draw.circle(art, fill, p(a, b), max(1, round(rr * r)))

    def line(points, fill, width=w):
        pygame.draw.lines(art, fill, False, [p(a, b) for a, b in points], max(1, width))

    def poly(points, fill):
        pygame.draw.polygon(art, fill, [p(a, b) for a, b in points])

    def ellipse(a, b, rw, rh, fill, width=0):
        pygame.draw.ellipse(art, fill, (*p(a, b), max(1, round(rw * r)), max(1, round(rh * r))), width)

    pygame.draw.circle(art, color, (c, c), r)
    if sid == "bronze_prestige":
        # Hammered bronze with riveted equatorial plates, no yin-yang reuse.
        for row in range(5):
            for col in range(6):
                a, b = -1.15 + col * .43, -1.05 + row * .47
                dot(a, b, .13, dark)
                dot(a - .035, b - .04, .095, light)
        for b in (-.45, .45):
            line([(-1.1, b), (1.1, b)], dark, max(2, r // 10))
            for a in (-.7, 0, .7):
                dot(a, b, .065, pale)
    elif sid == "streak_spark":
        pygame.draw.circle(art, dark, (c, c), r)
        for j in range(5):
            a = j * math.tau / 5 + .4
            line([(math.cos(a) * .45, math.sin(a) * .45),
                  (math.cos(a + .3) * .75, math.sin(a + .3) * .75),
                  (math.cos(a) * 1.1, math.sin(a) * 1.1)], color, max(2, r // 7))
        dot(0, 0, .24, light)
    elif sid == "streak_nova":
        pygame.draw.circle(art, dark, (c, c), r)
        for j in range(8):
            a = j * math.tau / 8
            poly([(math.cos(a) * .3, math.sin(a) * .3),
                  (math.cos(a + .18), math.sin(a + .18)),
                  (math.cos(a + .35) * .58, math.sin(a + .35) * .58)], color)
            line([(math.cos(a) * .4, math.sin(a) * .4), (math.cos(a + .18), math.sin(a + .18))], light)
        dot(0, 0, .32, pale)
    elif sid == "pixel_heart":
        # All-over interlocking pixel hearts, not the arcade checkerboard.
        pygame.draw.circle(art, dark, (c, c), r)
        for row in range(3):
            for col in range(3):
                a = -1.15 + col * .85 + (row % 2) * .4
                b = -1.1 + row * .8
                poly([(a, b), (a + .2, b), (a + .3, b + .12), (a + .4, b),
                      (a + .6, b), (a + .6, b + .25), (a + .3, b + .55), (a, b + .25)], color)
    elif sid == "arcade_king":
        pygame.draw.circle(art, dark, (c, c), r)
        for row in range(4):
            b = -.9 + row * .55
            line([(-1.1, b), (-.45, b), (-.45, b + .2), (.35, b + .2), (.35, b), (1.1, b)], color, max(2, r // 8))
        for a in (-.7, 0, .7):
            dot(a, -.1, .1, pale)
        line([(-.65, -.8), (-.4, -.5), (0, -.8), (.4, -.5), (.65, -.8)], light, max(2, r // 9))
    elif sid == "moon_dust":
        # Regolith dunes and scattered mineral flecks instead of moon craters.
        for j in range(5):
            b = -.8 + j * .5
            line([(-1.2 + k * .1, b + .22 * math.sin(k * .19 + j)) for k in range(25)], dark if j % 2 else light, max(2, r // 5))
        for j in range(18):
            a = j * 2.4
            rr = .25 + (j % 5) * .15
            dot(math.cos(a) * rr, math.sin(a) * rr, .035, pale)
    elif sid == "stargazer":
        pygame.draw.circle(art, dark, (c, c), r)
        pts = [(-.8, -.4), (-.25, -.7), (.25, -.2), (.6, -.45), (.75, .35), (.1, .7), (-.4, .2)]
        line(pts, color, max(1, r // 12))
        for a, b in pts:
            dot(a, b, .075, pale)
    elif sid == "frost_crystal":
        # Branching ice fractures cover the orb instead of a diamond grid.
        for j in range(6):
            a = j * math.tau / 6
            ux, uy = math.cos(a), math.sin(a)
            line([(0, 0), (ux, uy)], light, max(2, r // 9))
            for rr in (.4, .7):
                for sign in (-1, 1):
                    line([(ux * rr, uy * rr), (ux * (rr + .12) + sign * uy * .25,
                          uy * (rr + .12) - sign * ux * .25)], pale)
        dot(0, 0, .15, pale)
    elif sid == "mint_blob":
        # Smooth milky marbling: broad islands, not gummy stripes.
        for a, b, rr in ((-.7, -.55, .65), (.65, .15, .7), (-.35, .85, .55)):
            dot(a, b, rr, light)
            dot(a + .15, b + .08, rr * .6, color)
    elif sid == "alien_slime":
        pygame.draw.circle(art, dark, (c, c), r)
        for a, b, rr in ((-.6, -.5, .44), (.4, -.5, .35), (-.1, .3, .55), (.8, .6, .3)):
            dot(a, b, rr, color)
            dot(a - .09, b - .1, rr * .3, light)
        for a in (-.32, .32):
            ellipse(a - .14, -.25, .28, .45, ink)
            dot(a, -.15, .06, pale)
    elif sid == "comet_angel":
        # Swept pearly feather bands across the complete shell.
        for j in range(6):
            b = -.85 + j * .4
            line([(-1.1, b + .5), (-.25, b), (.35, b - .08), (1.1, b - .4)], light, max(2, r // 5))
            line([(-1.1, b + .6), (-.25, b + .1), (1.1, b - .3)], dark)
    elif sid == "rainbow_unicorn":
        for j, shade in enumerate(((250, 141, 189), (252, 216, 126), (135, 228, 203), (155, 189, 255), (200, 155, 242))):
            b = -.9 + j * .45
            line([(-1.2, b + .35), (-.4, b), (.4, b - .1), (1.2, b - .35)], shade, max(2, r // 3))
        poly([(-.18, -.45), (0, -1.1), (.18, -.45)], pale)
        for a in (-.4, .4):
            line([(a - .16, .05), (a, .15), (a + .16, .05)], ink, max(1, r // 10))
        for a, b in ((-.65, -.5), (.6, .55)):
            line([(a - .1, b), (a + .1, b)], pale)
            line([(a, b - .1), (a, b + .1)], pale)
    elif sid == "sugar_puppy":
        # Floppy ear patches, a broad muzzle and a chocolate nose.
        for a in (-1, .52):
            ellipse(a, -1.05, .48, 1.65, dark)
        ellipse(-.68, -.05, 1.36, 1, light)
        for a in (-.35, .35):
            dot(a, -.22, .12, ink)
            dot(a - .03, -.25, .035, pale)
        ellipse(-.22, .08, .44, .3, ink)
        line([(0, .3), (0, .55), (.17, .6)], ink)
    elif sid == "mochi_pal":
        # Toasted rice cap and a creamy fold make it a confection, not an animal.
        ellipse(-1.25, -1.65, 2.5, 1.35, dark)
        line([(-1, -.48), (-.4, -.35), (.3, -.42), (1, -.6)], light, max(2, r // 8))
        for a, b in ((-.65, -.7), (-.25, -.57), (.3, -.7), (.65, -.65)):
            line([(a - .04, b - .06), (a + .04, b + .06)], pale)
        ellipse(-1.1, .1, 2.2, 1.2, light)
        for a in (-.35, .35):
            line([(a - .15, -.15), (a, -.25), (a + .15, -.15)], ink, max(1, r // 10))
            ellipse(a - .18, .04, .36, .17, (250, 147, 176))
        line([(-.18, .17), (0, .3), (.18, .17)], ink)
    elif style in ("circuit", "pixel", "gear", "lattice"):
        pygame.draw.circle(art, dark, (c, c), r)
        if style == "gear":
            for j in range(12):
                a = j * math.tau / 12
                poly([(math.cos(a - .12) * .65, math.sin(a - .12) * .65),
                      (math.cos(a - .12), math.sin(a - .12)),
                      (math.cos(a + .12), math.sin(a + .12)),
                      (math.cos(a + .12) * .65, math.sin(a + .12) * .65)], color)
            dot(0, 0, .68, color)
            ellipse(-.48, -.48, .96, .96, light, w)
            dot(0, 0, .23, dark)
            for a, b in ((-.35, -.35), (.35, -.35), (.35, .35), (-.35, .35)):
                dot(a, b, .07, dark)
        elif style == "circuit":
            for j in range(5):
                a = -.85 + j * .42
                b = .18 * math.sin(j + phase)
                line([(a, -1.1), (a, b - .3), (a + .24, b), (a + .24, 1.1)], color, max(2, r // 9))
                dot(a + .24, b, .07, pale)
            if tier <= 2:
                ellipse(-.6, -.6, 1.2, 1.2, light, w)
        elif style == "pixel":
            for row in range(7):
                for col in range(7):
                    if (row * 7 + col * 3 + variant) % 5 < 2:
                        a, b = -1.05 + col * .32, -1.05 + row * .32
                        poly([(a, b), (a + .27, b), (a + .27, b + .27), (a, b + .27)], light if row % 2 else color)
        else:
            for j in range(7):
                a = -1.5 + j * .5
                line([(a, -1.2), (a + 1.5, 1.2)], color, max(2, r // 8))
                line([(a, 1.2), (a + 1.5, -1.2)], light, w)
            if tier == 1:
                ellipse(-.5, -.5, 1, 1, pale, w)
    elif style in ("solar", "wind", "ember", "bands", "ocean", "nebula"):
        if style in ("solar", "ember", "nebula"):
            pygame.draw.circle(art, dark, (c, c), r)
        for j in range(6):
            yy = -1.1 + j * .42
            pts = []
            for k in range(29):
                xx = -1.4 + k * .1
                wave = .12 * math.sin(k * .34 + j + phase)
                if style in ("solar", "ember"):
                    wave += .11 * math.sin(k * .9 + j * 2)
                pts.append((xx, yy + wave + (xx * .25 if style == "wind" else 0)))
            palette = (color, light, dark) if style == "bands" else (color, light, color)
            line(pts, palette[j % 3], max(2, r // (4 if style == "bands" else 7)))
        if style == "ocean":
            for j in range(5):
                dot(-.65 + j * .3, .5 * math.sin(j * 2 + phase), .045, pale)
        elif style == "nebula":
            for j in range(12 if tier == 1 else 6):
                a = j * 2.4 + phase
                rr = .22 + .06 * j
                dot(math.cos(a) * rr, math.sin(a) * rr, .04, pale)
        elif style == "solar":
            ellipse(-.55, -.5, 1, .85, light, max(1, r // 12))
    elif style == "vortex":
        pygame.draw.circle(art, (8, 9, 22), (c, c), r)
        for j in range(3 if tier >= 4 else 5):
            pts = []
            for k in range(44):
                a = k * .12 + j * math.tau / 5 + phase
                rr = .08 + k * .025
                pts.append((math.cos(a) * rr, math.sin(a) * rr * .7))
            line(pts, color if j % 2 else light, max(1, r // 10))
        dot(0, 0, .28 if sid == "event_horizon" else .18, (3, 4, 12))
    elif style in ("lunar", "silver"):
        for a, b, rr in ((-.45, -.4, .26), (.5, .1, .3), (-.2, .5, .2), (.45, -.65, .12)):
            a, b = (a * math.cos(phase) - b * math.sin(phase),
                    a * math.sin(phase) + b * math.cos(phase))
            dot(a, b, rr, dark)
            dot(a - .05, b - .04, rr * .78, light)
            dot(a + .02, b + .03, rr * .64, color)
        if sid == "ice_moon":
            line([(-.7, -1), (-.3, -.2), (-.5, .25), (.2, 1)], pale, w)
        elif sid == "starry_pastel":
            for a, b in ((-.5, -.5), (.45, .35)):
                line([(a - .1, b), (a + .1, b)], pale)
                line([(a, b - .1), (a, b + .1)], pale)
        if style == "silver":
            for a in (-.7, -.35, .5):
                line([(a, -1), (a + .5, 1)], light, max(1, r // 8))
    elif style in ("cat", "fox", "puppy", "bunny", "unicorn", "panda", "mochi", "chick"):
        # The circular body is the face; markings reach its edge, no tiny mascot.
        if style in ("fox", "puppy"):
            poly([(-1, -.4), (-.1, .15), (0, .85), (-1, .7)], light)
            poly([(1, -.4), (.1, .15), (0, .85), (1, .7)], light)
        elif style == "panda":
            pygame.draw.circle(art, (234, 242, 230), (c, c), r)
            for a in (-.4, .4):
                ellipse(a - .24, -.4, .48, .65, dark)
        elif style in ("bunny", "unicorn"):
            for a in (-.45, .22):
                ellipse(a, -1.12, .23, .65, light)
            if style == "unicorn":
                for j, shade in enumerate(((255, 155, 202), (164, 216, 255), (255, 230, 151))):
                    line([(-1, -.8 + j * .2), (0, -.55 + j * .2), (1, -.9 + j * .2)], shade, max(2, r // 6))
        elif style == "cat":
            if sid == "snow_leopard":
                for j in range(9):
                    a = j * 2.4
                    dot(math.cos(a) * .8, math.sin(a) * .8, .12, dark)
                    dot(math.cos(a) * .8, math.sin(a) * .8, .06, color)
            elif sid == "galaxy_cat":
                for j in range(9):
                    a = j * 2.4
                    dot(math.cos(a) * .8, math.sin(a) * .8, .045, pale)
            elif sid == "solar_flare_cat":
                for a in (-.8, .8):
                    line([(a, -.8), (a * .7, -.4), (a, -.1)], light, max(2, r // 7))
            elif sid == "astro_kitty":
                ellipse(-.85, -.85, 1.7, 1.7, pale, max(1, r // 10))
            else:
                ellipse(-1, -.95, 1.1, .65, light)
            for a in (-.7, .7):
                line([(a, -.92), (a * .65, -.58)], dark, max(2, r // 8))
        elif style == "mochi":
            ellipse(-1.1, .25, 2.2, 1.2, light)
        for a in (-.36, .36):
            dot(a, -.13, .115, ink)
            dot(a - .025, -.17, .035, pale)
            if style != "panda":
                ellipse(a - .16, .12, .28, .14, (245, 145, 175))
        if style == "chick":
            poly([(-.18, .08), (.18, .08), (0, .32)], (235, 125, 34))
            line([(-.25, -.9), (0, -.7), (.25, -.9)], light, max(2, w))
        else:
            poly([(-.1, .1), (.1, .1), (0, .22)], ink)
            line([(-.2, .3), (0, .39), (.2, .3)], ink)
            if style == "cat":
                for sign in (-1, 1):
                    for b in (.12, .32):
                        line([(sign * .55, b), (sign * .93, b - .05)], dark)
    elif style in ("royal", "halo", "heart", "diamond", "platinum", "star"):
        if style in ("royal", "platinum"):
            for j in range(5):
                a = j * math.pi / 4 + phase
                pts = [(math.sin(k * .12 + a) * .6, -1.2 + k * .1) for k in range(25)]
                line(pts, light if j % 2 else dark, max(2, r // 6))
            line([(-1, .3), (-.6, .05), (-.2, .3), (.2, .05), (.6, .3), (1, .05)], pale, max(1, r // 10))
            for a in (-.6, 0, .6):
                dot(a, -.1, .09, (255, 207, 100))
        elif style == "halo":
            for sign in (-1, 1):
                for j in range(4):
                    line([(sign * .1, .8 - j * .35), (sign * .65, .35 - j * .3), (sign, -.4 - j * .15)], light, max(2, r // 7))
            ellipse(-1.1, -.6, 2.2, .65, pale, max(1, r // 10))
        elif style == "heart":
            # Broad heart-shaped colour fields are part of the surface enamel.
            for sign in (-1, 1):
                dot(sign * .4, -.38, .56, light)
            poly([(-.9, -.2), (.9, -.2), (0, 1.05)], light)
            if sid == "diamond_heart":
                for a in (-.65, 0, .65):
                    line([(a, -1), (a * .5, .1), (0, 1)], color)
        elif style == "diamond":
            for j in range(10):
                a, b = j * math.tau / 10, (j + 1) * math.tau / 10
                poly([(math.cos(a), math.sin(a)), (math.cos(b), math.sin(b)), (0, 0)], (pale, color, light, (142, 194, 232))[j % 4])
                line([(math.cos(a), math.sin(a)), (0, 0)], pale)
            ellipse(-.55, -.55, 1.1, 1.1, pale, w)
        else:
            pygame.draw.circle(art, dark, (c, c), r)
            for j in range(5 if tier >= 4 else 9):
                a = phase + j * 2.4
                rr = .25 + (j % 3) * .23
                xx, yy = math.cos(a) * rr, math.sin(a) * rr
                line([(xx - .1, yy), (xx + .1, yy)], light)
                line([(xx, yy - .1), (xx, yy + .1)], pale)
    elif style in ("gummy", "petal", "spectral", "hazard", "zen", "paw"):
        if style == "gummy":
            for j in range(4):
                a = -.9 + j * .55
                ellipse(a, -.8 + .2 * math.sin(j + phase), .9, 1.8, light if j % 2 else dark)
            if sid == "alien_slime":
                for a, b in ((-.45, .3), (.3, -.4), (.6, .55)):
                    dot(a, b, .13, color)
        elif style == "petal":
            for j in range(7):
                a = phase + j * math.tau / 7
                dot(math.cos(a) * .8, math.sin(a) * .8, .38, light)
            for j in range(5):
                a = j * math.tau / 5
                ellipse(math.cos(a) * .38 - .2, math.sin(a) * .38 - .2, .4, .4, (255, 219, 230))
            dot(0, 0, .15, (255, 214, 122))
        elif style == "spectral":
            pygame.draw.circle(art, dark, (c, c), r)
            for j in range(5):
                a = -.9 + j * .44
                line([(a, -1), (a - .2, -.3), (a + .18, .25), (a, 1)], color, max(2, r // 5))
            for a in (-.32, .32):
                ellipse(a - .12, -.2, .24, .36, pale)
        elif style == "hazard":
            for j in range(5):
                a = -1.5 + j * .65
                poly([(a, -1.2), (a + .3, -1.2), (a + 1.7, 1.2), (a + 1.4, 1.2)], ink)
            line([(-1, .45), (1, .45)], light, max(2, r // 8))
        elif style == "zen":
            poly([(-1, -1), (0, -1), (0, 1), (-1, 1)], light)
            dot(0, -.5, .5, color)
            dot(0, .5, .5, light)
            dot(0, -.5, .13, light)
            dot(0, .5, .13, dark)
        else:
            for a, b in ((-.7, -.35), (-.25, -.65), (.25, -.65), (.7, -.35)):
                ellipse(a - .16, b - .17, .32, .4, light)
            ellipse(-.5, -.05, 1, .85, light)
    elif style == "rover":
        # Rust-red spherical terrain with broad sediment bands and impact basins.
        for j, shade in enumerate((light, dark, color, light)):
            yy = -.65 + j * .45
            line([(-1.1 + i * .11, yy + .11 * math.sin(i * .45 + j)) for i in range(21)], shade, max(2, r // 5))
        for a, b, rr in ((-.4, -.35, .24), (.45, .3, .32), (-.3, .65, .13)):
            dot(a, b, rr, dark)
            dot(a - .04, b - .05, rr * .7, color)
            ellipse(a - rr, b - rr, rr * 2, rr * 2, light, w)
    elif style == "dragon":
        # Interlocking scales wrap the entire orb; hot seams breathe underneath.
        pygame.draw.circle(art, dark, (c, c), r)
        for row in range(6):
            for col in range(6):
                a = -1.25 + col * .48 + (row % 2) * .24
                b = -1.1 + row * .43
                poly([(a, b), (a + .42, b), (a + .36, b + .3), (a + .21, b + .43), (a + .05, b + .3)], color)
                line([(a + .05, b + .04), (a + .34, b + .04)], light)
        heat = (255, int(145 + 45 * math.sin(t * math.tau / 6)), 45)
        line([(-.8, -.65), (-.36, -.25), (-.45, .05), (.1, .4), (.35, 1)], heat, max(1, r // 10))
    elif style == "tea":
        # The whole sphere is milky tea, with a creamy cap and suspended pearls.
        ellipse(-1.2, -1.25, 2.4, 1.45, (255, 226, 217))
        line([(-1, -.05), (-.4, -.15), (.2, -.05), (.7, -.15), (1, -.05)], light, max(2, r // 8))
        for a, b, rr in ((-.6, .35, .17), (-.15, .65, .2), (.4, .4, .18), (.65, .75, .15), (-.65, .8, .16)):
            dot(a, b, rr, (75, 42, 40))
            dot(a - .04, b - .05, rr * .3, (182, 121, 110))
    elif style == "aurora":
        pygame.draw.circle(art, dark, (c, c), r)
        for j in range(4):
            pts = [(-1.2 + i * .08, -.5 + j * .32 + .28 * math.sin(i * .23 + j * .6 + t * math.tau / 6)) for i in range(31)]
            line(pts, ((50, 215, 170), color, (140, 110, 240), light)[j], max(2, r // 5))
        for a, b in ((-.55, -.65), (.25, -.8), (.6, .55)):
            dot(a, b, .045, pale)
    elif style in ("bolt", "pulsar"):
        pygame.draw.circle(art, dark, (c, c), r)
        if style == "bolt":
            for j in range(3):
                a = -.8 + j * .7
                pts = [(a, -1), (a - .2, -.45), (a + .15, -.12), (a - .15, .25), (a + .12, .65), (a, 1)]
                line(pts, color, max(3, r // 5))
                line(pts, pale, w)
                line([(a + .15, -.12), (a + .5, -.25), (a + .7, -.6)], light)
        else:
            for rr in (.9, .64, .38):
                ellipse(-rr, -rr, rr * 2, rr * 2, color, max(1, r // 9))
            poly([(-1, -.17), (-.18, -.08), (.2, -.28), (1, -.1), (1, .17), (.18, .08), (-.2, .28), (-1, .1)], pale)
            dot(0, 0, .22 + .025 * math.sin(t * math.tau / 6), light)
    elif style == "comet_art":
        for j in range(4):
            a = -.9 + j * .55
            line([(-1.2, a - .45), (-.5, a), (.2, a + .25), (1.2, a + .35)], light if j % 2 else dark, max(2, r // 5))
        for a, b, rr in ((-.55, -.45, .2), (.3, .3, .32), (.55, -.35, .12)):
            dot(a, b, rr, dark)
            dot(a - .04, b - .05, rr * .6, color)
    elif style in ("penguin", "bear"):
        if style == "penguin":
            # A round penguin face: no separate miniature body inside the ball.
            pygame.draw.circle(art, dark, (c, c), r)
            ellipse(-.85, -.6, .95, 1.55, pale)
            ellipse(-.1, -.6, .95, 1.55, pale)
            poly([(-.2, .12), (.2, .12), (0, .38)], (255, 181, 64))
        else:
            ellipse(-.7, -.85, .4, .4, dark)
            ellipse(.3, -.85, .4, .4, dark)
            ellipse(-.48, -.05, .96, .85, (255, 225, 181))
            poly([(-.18, .14), (.18, .14), (0, .35)], ink)
            line([(0, .3), (0, .5), (-.15, .56)], ink)
        for a in (-.38, .38):
            dot(a, -.15, .11, ink)
            dot(a - .025, -.18, .035, pale)
    elif style == "koi":
        pygame.draw.circle(art, (240, 233, 216), (c, c), r)
        for a, b, rr in ((-.7, -.5, .58), (.65, .35, .65), (-.25, .8, .35)):
            dot(a, b, rr, color)
        for row in range(4):
            for col in range(4):
                a = -.95 + col * .55 + (row % 2) * .27
                b = -.8 + row * .5
                line([(a, b), (a + .23, b + .16), (a + .46, b)], dark)
    elif style == "jellyfish":
        pygame.draw.circle(art, dark, (c, c), r)
        for j in range(7):
            a = -1.1 + j * .36
            line([(a + .1 * math.sin(k * .5 + t * math.tau / 6 + j), -1 + k * .1) for k in range(21)], color, max(2, r // 7))
        ellipse(-.9, -.85, 1.8, .6, light, max(1, r // 10))
        for a, b in ((-.5, .2), (.25, -.1), (.5, .6)):
            dot(a, b, .08, pale)
    elif style == "gamepad":
        # A spherical arcade shell with wraparound equatorial panel and buttons.
        line([(-1.1, .2), (1.1, -.15)], dark, max(3, r // 2))
        line([(-1, .52), (1, .17)], light, w)
        line([(-.7, -.12), (-.2, -.12)], ink, max(2, r // 7))
        line([(-.45, -.36), (-.45, .12)], ink, max(2, r // 7))
        dot(.35, -.18, .14, (255, 90, 155))
        dot(.65, .05, .13, (255, 227, 103))
    elif style in ("coin", "ingot"):
        # Machined metal sphere; broad curved bands replace object silhouettes.
        for j in range(5):
            a = -1.2 + j * .48
            poly([(a, -1.2), (a + .23, -1.2), (a + .85, 1.2), (a + .52, 1.2)], light if j % 2 else dark)
        ellipse(-.86, -.86, 1.72, 1.72, light, max(1, r // 12))
        if style == "coin":
            ellipse(-.67, -.67, 1.34, 1.34, dark, max(1, r // 10))
        else:
            for a in (-.55, .55):
                dot(a, .35, .07, pale)
            line([(-.7, -.1), (.7, -.1)], light, max(2, r // 9))
    elif style == "quartz_cluster":
        # The orb itself is rose quartz, tessellated into large translucent facets.
        pts = [(-1, -.6), (-.35, -1), (.4, -.9), (1, -.25), (.75, .65), (0, 1), (-.8, .7)]
        for j in range(len(pts)):
            a, b = pts[j], pts[(j + 1) % len(pts)]
            poly([a, b, (-.15, .05)], (light, color, dark, color)[j % 4])
            line([a, (-.15, .05), b], light)
    elif style == "snowflake":
        for a, b, rr in ((-.5, .35, .36), (.55, -.1, .5), (0, -.6, .3)):
            dot(a, b, rr, light)
        for j in range(3):
            yy = -.4 + j * .5
            line([(-1 + i * .1, yy + .12 * math.sin(i * .4 + j)) for i in range(21)], pale, max(1, r // 12))

    # Signature surface treatments separate close relatives beyond palette swaps.
    if sid == "event_horizon":
        ellipse(-1.2, -.35, 2.4, .7, (255, 200, 117), max(2, r // 9))
        dot(0, 0, .5, (3, 4, 12))
        ellipse(-.54, -.54, 1.08, 1.08, light, w)
    elif sid == "dark_matter":
        for j in range(5):
            a = j * math.tau / 5
            line([(math.cos(a), math.sin(a)), (math.cos(a + .3) * .65, math.sin(a + .3) * .65),
                  (math.cos(a) * .38, math.sin(a) * .38)], pale, w)
    elif sid == "cosmic_void":
        ellipse(-1.1, -.65, 2.2, 1.3, color, max(2, r // 6))
        dot(0, 0, .35, dark)
    elif sid == "supernova":
        for j in range(12):
            a = j * math.tau / 12
            poly([(math.cos(a - .07) * .45, math.sin(a - .07) * .45),
                  (math.cos(a), math.sin(a)),
                  (math.cos(a + .07) * .45, math.sin(a + .07) * .45)], light)
        dot(0, 0, .35, (255, 232, 161))
    elif sid == "red_dwarf":
        for a, b, rr in ((-.5, -.25, .25), (.35, .4, .18)):
            dot(a, b, rr, dark)
    elif sid == "neutron_star":
        line([(-1, -.85), (1, .85)], pale, max(2, r // 5))
        dot(0, 0, .35, pale)
        dot(0, 0, .2, color)
    elif sid == "saturn_ring":
        ellipse(-1.3, -.45, 2.6, .9, dark, max(3, r // 3))
        ellipse(-1.3, -.45, 2.6, .9, light, max(1, r // 10))
    elif sid == "leviathan":
        for j in range(4):
            a = -.9 + j * .6
            poly([(a, -1.1), (a + .25, -.5), (a + .15, .3), (a + .45, 1.1),
                  (a + .05, .5), (a - .05, -.3)], dark)
        line([(-1, .25), (0, .45), (1, .25)], light, max(2, r // 8))
    elif sid in ("royal_crown", "golden_crown", "little_prince"):
        if sid == "royal_crown":
            # Tall fleur-like enamel panels follow the round shell.
            for a in (-.65, 0, .65):
                poly([(a - .18, .7), (a - .23, -.25), (a, -.85), (a + .23, -.25), (a + .18, .7)], dark)
                dot(a, -.2, .12, (255, 204, 112))
            line([(-1, .6), (1, .6)], pale, max(2, r // 8))
        elif sid == "golden_crown":
            line([(-1, -.45), (-.5, .1), (0, -.45), (.5, .1), (1, -.45)], pale, max(2, r // 5))
        else:
            line([(-1.1, -.7), (1.1, .65)], pale, max(3, r // 3))
            line([(-1.1, -.7), (1.1, .65)], color, max(1, r // 8))
    elif sid in ("sakura_fox", "rocket_bunny"):
        # Edge-to-edge animal markings instead of flowers or a separate mascot.
        for sign in (-1, 1):
            poly([(sign, -.55), (sign * .25, .05), (0, .85), (sign, .75)], light)
            if sid == "rocket_bunny":
                line([(sign * .38, -.95), (sign * .25, -.48)], dark, max(2, r // 7))
            dot(sign * .35, -.12, .11, ink)
            dot(sign * .37, -.16, .035, pale)
        poly([(-.13, .2), (.13, .2), (0, .37)], ink)
    elif sid == "bunny_moon":
        ellipse(-1.1, -.95, .9, 2.1, light)
        for a in (-.48, .26):
            ellipse(a, -1.1, .22, .75, dark)
    elif sid == "cloud_bunny":
        for a, b in ((-.85, .4), (-.3, .65), (.3, .6), (.85, .4)):
            dot(a, b, .35, light)
    elif sid == "starlight_chick":
        for a, b in ((-.65, -.65), (.55, -.55), (.65, .5)):
            line([(a - .09, b), (a + .09, b)], pale)
            line([(a, b - .09), (a, b + .09)], pale)
    elif sid == "void_walker":
        poly([(-1, -1), (0, -.5), (1, -1)], dark)
        for sign in (-1, 1):
            line([(sign * .65, -.25), (sign * .18, -.1)], pale, max(2, r // 7))
    elif sid == "streak_flame":
        for j in range(4):
            a = -.9 + j * .6
            poly([(a - .25, 1.1), (a, -.65), (a + .1, .1), (a + .4, -.35), (a + .3, 1.1)], light)
    elif sid == "streak_ember":
        for a, b, rr in ((-.5, -.4, .22), (.4, .2, .25), (-.25, .6, .15)):
            dot(a, b, rr, dark)
            dot(a, b, rr * .55, light)
    elif sid == "star_hunter":
        ellipse(-1.1, -.4, 2.2, .8, color, max(2, r // 8))
        ellipse(-.4, -1.1, .8, 2.2, light, w)
    elif sid == "starfall":
        for j in range(4):
            a = -.85 + j * .55
            line([(a - .4, -1), (a + .5, 1)], light, max(2, r // 8))
    elif sid == "streak_aurora":
        for j in range(3):
            a = -.8 + j * .7
            line([(a - .4, -1), (a, -.3), (a - .1, .3), (a + .4, 1)], pale, w)

    # Shared curvature lights the complete material, not a circle behind an icon.
    shade = _LIGHT_CACHE.get(r)
    if shade is None:
        shade = pygame.Surface((size, size), pygame.SRCALPHA)
        for yy in range(size):
            for xx in range(size):
                nx, ny = (xx - c) / r, (yy - c) / r
                d = nx * nx + ny * ny
                if d <= 1:
                    z = math.sqrt(1 - d)
                    value = max(0, min(1, .48 * z - .34 * nx - .38 * ny))
                    shade.set_at((xx, yy), (0, 0, 0, round(115 * (1 - value))))
        _LIGHT_CACHE.put(r, shade)
    art.blit(shade, (0, 0))

    # HOLO's objects read as charged glass: a dark coloured body with luminous
    # material seams, rather than a matte painted toy. The original pattern
    # remains visible underneath; its boundaries supply the emissive detail.
    emission = pygame.transform.laplacian(art)
    emission.set_alpha(None)
    emission.fill(tuple(max(24, int(v * .38)) for v in color), special_flags=pygame.BLEND_RGB_MULT)
    art.fill((184, 184, 198, 255), special_flags=pygame.BLEND_RGBA_MULT)
    art.blit(emission, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
    # One continuous charged rim keeps every skin legible as a gameplay orb.
    pygame.draw.circle(art, color, (c, c), r, max(1, r // 14))
    rim = max(1, r - max(2, r // 8))
    pygame.draw.arc(art, light, (c - rim, c - rim, 2 * rim, 2 * rim), .8, 2.65, max(1, r // 22))
    if tier <= 3:
        # Fine glints distinguish premium materials without obscuring the pattern.
        line([(.43, -.57), (.61, -.57)], light)
        line([(.52, -.66), (.52, -.48)], light)
    mask = pygame.Surface((size, size), pygame.SRCALPHA)
    pygame.draw.circle(mask, (255, 255, 255, 255), (c, c), r)
    art.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    return art
