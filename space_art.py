"""Procedural space scenery: per-sector nebula/star backdrops, hero objects (planets, pulsar, black hole ...)
and wall textures (asteroid ice, station hull, crystal lattice, lava rock, obsidian).  Everything is generated once at
level load from a seed, so a frame costs only a couple of blits."""
import math
import random
import pygame

THEMES = {
    1: dict(top=(5, 9, 22), bot=(11, 24, 48), neb=[(30, 90, 170), (50, 150, 200), (90, 70, 160)], hero="ringed",
            wall=(22, 30, 48), wall2=(34, 48, 74), accent=(0, 210, 255)),
    2: dict(top=(12, 5, 22), bot=(28, 10, 46), neb=[(130, 40, 180), (70, 40, 170), (170, 60, 150)], hero="pulsar",
            wall=(30, 20, 44), wall2=(48, 32, 68), accent=(210, 60, 255)),
    3: dict(top=(4, 16, 14), bot=(8, 32, 28), neb=[(30, 160, 110), (20, 110, 160), (100, 200, 120)], hero="crystal",
            wall=(16, 34, 30), wall2=(26, 54, 48), accent=(35, 245, 140)),
    4: dict(top=(20, 8, 6), bot=(38, 12, 8), neb=[(200, 80, 30), (150, 40, 30), (230, 150, 40)], hero="blackhole",
            wall=(40, 22, 18), wall2=(62, 34, 26), accent=(255, 115, 25)),
    5: dict(top=(10, 4, 14), bot=(28, 6, 24), neb=[(190, 30, 70), (100, 30, 130), (210, 160, 40)], hero="supernova",
            wall=(24, 16, 32), wall2=(40, 26, 52), accent=(255, 35, 75)),
    6: dict(top=(14, 10, 4), bot=(36, 24, 8), neb=[(210, 150, 30), (150, 90, 20), (90, 140, 170)], hero="rift",
            wall=(34, 28, 16), wall2=(56, 46, 24), accent=(255, 200, 60)),
    7: dict(top=(4, 6, 22), bot=(12, 14, 50), neb=[(60, 80, 220), (120, 70, 210), (40, 150, 220)], hero="strings",
            wall=(16, 20, 46), wall2=(28, 34, 76), accent=(110, 140, 255)),
}


def _lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _scale(c, k):
    return tuple(max(0, min(255, int(v * k))) for v in c)


def blob(w, h, color, strength=0.4):
    """Soft elliptical glow (RGB, premultiplied for BLEND_ADD)."""
    sw, sh = max(4, w // 8), max(4, h // 8)
    s = pygame.Surface((sw, sh))
    for i in range(12, 0, -1):
        k = strength * ((13 - i) / 12.0) ** 2.2
        pygame.draw.ellipse(s, _scale(color, k), (sw * (1 - i / 12.0) / 2, sh * (1 - i / 12.0) / 2, sw * i / 12.0, sh * i / 12.0))
    return pygame.transform.smoothscale(s, (w, h))


# --------------------------------------------------------------------------- hero objects
def _sphere(surf, cx, cy, r, base, light=(-0.4, -0.5), bands=None):
    for i in range(r, 0, -2):
        t = 1.0 - i / float(r)
        off = (light[0] * r * 0.5 * t, light[1] * r * 0.5 * t)
        col = _lerp(_scale(base, 0.28), _scale(base, 1.25), t ** 0.8)
        pygame.draw.circle(surf, col, (cx + off[0], cy + off[1]), i)
    if bands:
        for k, (dy, hh, c) in enumerate(bands):
            rect = pygame.Rect(cx - r, cy + int(dy * r), 2 * r, max(2, int(hh * r)))
            band = pygame.Surface(rect.size, pygame.SRCALPHA)
            band.fill((*c, 45))
            mask = pygame.Surface((2 * r, 2 * r), pygame.SRCALPHA)
            pygame.draw.circle(mask, (255, 255, 255, 255), (r, r), r)
            tmp = pygame.Surface((2 * r, 2 * r), pygame.SRCALPHA)
            tmp.blit(band, (0, rect.y - (cy - r)))
            tmp.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            surf.blit(tmp, (cx - r, cy - r))
    # terminator shadow
    sh = pygame.Surface((2 * r, 2 * r), pygame.SRCALPHA)
    pygame.draw.circle(sh, (0, 0, 8, 120), (r + int(r * 0.55), r + int(r * 0.45)), r)
    m = pygame.Surface((2 * r, 2 * r), pygame.SRCALPHA)
    pygame.draw.circle(m, (255, 255, 255, 255), (r, r), r)
    sh.blit(m, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    surf.blit(sh, (cx - r, cy - r))


def draw_hero(surface, kind, cx, cy, r, seed=1):
    """Draw a hero object centred at (cx, cy) with characteristic radius r, using alpha blending."""
    pad = int(r * 2.6)
    tmp = pygame.Surface((pad * 2, pad * 2), pygame.SRCALPHA)
    c = pad
    rng = random.Random(seed)
    if kind == "ringed":
        ring = pygame.Rect(c - int(r * 1.9), c - int(r * 0.55), int(r * 3.8), int(r * 1.1))
        for k, (col, w) in enumerate([((120, 190, 230, 120), 6), ((200, 235, 255, 150), 3), ((90, 150, 210, 100), 8)]):
            rr = ring.inflate(-k * int(r * 0.22), -k * int(r * 0.06))
            pygame.draw.arc(tmp, col, rr, math.pi, 2 * math.pi, max(2, int(w * r / 90)))
        _sphere(tmp, c, c, r, (70, 140, 210), bands=[(-0.4, 0.15, (200, 230, 255)), (0.05, 0.2, (40, 90, 160)), (0.45, 0.12, (220, 240, 255))])
        for k, (col, w) in enumerate([((120, 190, 230, 150), 6), ((200, 235, 255, 190), 3), ((90, 150, 210, 130), 8)]):
            rr = ring.inflate(-k * int(r * 0.22), -k * int(r * 0.06))
            pygame.draw.arc(tmp, col, rr, 0, math.pi, max(2, int(w * r / 90)))
        _sphere(tmp, c + int(r * 2.0), c - int(r * 1.0), max(6, int(r * 0.22)), (210, 220, 235))
    elif kind == "pulsar":
        for k in range(14, 0, -1):
            pygame.draw.circle(tmp, (200, 120, 255, int(9 + 6 * (14 - k))), (c, c), int(r * 0.35 * k / 3.0 + 4))
        for sgn in (-1, 1):
            ang = -0.9 if sgn < 0 else -0.9 + math.pi
            for k, (w, a) in enumerate([(0.34, 30), (0.2, 60), (0.09, 120)]):
                tip = (c + math.cos(ang) * r * 2.4, c + math.sin(ang) * r * 2.4)
                nx, ny = -math.sin(ang), math.cos(ang)
                pygame.draw.polygon(tmp, (230, 150, 255, a), [(c + nx * r * w * 0.35, c + ny * r * w * 0.35), tip, (c - nx * r * w * 0.35, c - ny * r * w * 0.35)])
        pygame.draw.circle(tmp, (255, 255, 255, 255), (c, c), max(3, int(r * 0.13)))
        for k in range(3):
            pygame.draw.circle(tmp, (200, 130, 255, 110 - k * 30), (c, c), int(r * (0.55 + 0.3 * k)), 2)
    elif kind == "crystal":
        for k in range(7):
            ang = rng.uniform(-2.4, -0.7) if k else -1.57
            ln = r * rng.uniform(0.9, 1.7) if k else r * 1.9
            wd = r * rng.uniform(0.16, 0.3)
            bx, by = c + rng.uniform(-0.4, 0.4) * r, c + r * 0.9
            tx, ty = bx + math.cos(ang) * ln, by + math.sin(ang) * ln
            nx, ny = -math.sin(ang), math.cos(ang)
            pts = [(bx + nx * wd, by + ny * wd), (bx - nx * wd, by - ny * wd), (tx - nx * wd * 0.3, ty - ny * wd * 0.3), (tx + nx * wd * 0.3, ty + ny * wd * 0.3)]
            pygame.draw.polygon(tmp, (60, 200, 150, 200), pts)
            pygame.draw.polygon(tmp, (170, 255, 220, 230), [pts[0], pts[3], ((tx + bx) / 2, (ty + by) / 2)])
            pygame.draw.polygon(tmp, (200, 255, 235, 255), pts, 2)
            pygame.draw.polygon(tmp, (255, 255, 255, 230), [(tx + nx * wd * 0.3, ty + ny * wd * 0.3), (tx - nx * wd * 0.3, ty - ny * wd * 0.3), (tx + math.cos(ang) * wd, ty + math.sin(ang) * wd)])
    elif kind == "blackhole":
        disc = pygame.Rect(c - int(r * 2.2), c - int(r * 0.55), int(r * 4.4), int(r * 1.1))
        for k, col in enumerate([(120, 40, 10, 90), (220, 100, 20, 140), (255, 190, 70, 200), (255, 240, 200, 230)]):
            pygame.draw.ellipse(tmp, col, disc.inflate(-k * int(r * 0.8), -k * int(r * 0.2)), max(2, int(r * 0.09)))
        pygame.draw.circle(tmp, (0, 0, 0, 255), (c, c), int(r * 0.85))
        pygame.draw.circle(tmp, (255, 200, 120, 220), (c, c), int(r * 0.88), 3)
        arc = pygame.Rect(c - int(r * 1.15), c - int(r * 1.15), int(r * 2.3), int(r * 2.3))
        pygame.draw.arc(tmp, (255, 170, 60, 200), arc, 0.25, math.pi - 0.25, max(3, int(r * 0.08)))
        pygame.draw.ellipse(tmp, (255, 220, 150, 235), disc.inflate(-int(r * 1.2), -int(r * 0.42)), max(2, int(r * 0.06)))
    elif kind == "supernova":
        for k in range(6):
            pygame.draw.circle(tmp, (255, 90, 60, 70 - k * 10), (c, c), int(r * (1.0 + 0.32 * k)), max(2, int(r * 0.05)))
        _sphere(tmp, c, c, int(r * 0.78), (230, 70, 50), light=(-0.2, -0.3))
        for _ in range(40):
            a = rng.uniform(0, 6.283)
            d = r * rng.uniform(1.1, 2.4)
            pygame.draw.circle(tmp, (255, rng.randint(120, 220), 70, rng.randint(90, 200)), (c + math.cos(a) * d, c + math.sin(a) * d), rng.randint(1, 4))
        pygame.draw.circle(tmp, (255, 235, 200, 220), (c, c), max(3, int(r * 0.2)))
    elif kind == "rift":                  # a clock face swallowed by a time vortex
        for k in range(5):
            pygame.draw.circle(tmp, (255, 200, 70, 70 - k * 11), (c, c), int(r * (0.7 + 0.3 * k)), max(2, int(r * 0.04)))
        for i in range(12):
            a = i * math.pi / 6
            r1, r2 = r * 1.45, r * (1.66 if i % 3 == 0 else 1.55)
            pygame.draw.line(tmp, (255, 225, 120, 210), (c + math.cos(a) * r1, c + math.sin(a) * r1), (c + math.cos(a) * r2, c + math.sin(a) * r2), max(2, int(r * 0.04)))
        for arm in range(3):
            pts = [(c + math.cos(u + arm * 2.094) * (r * 0.08 + r * 0.9 * u / 12.0), c + math.sin(u + arm * 2.094) * (r * 0.08 + r * 0.9 * u / 12.0))
                   for u in [k * 0.25 for k in range(0, 49)]]
            pygame.draw.lines(tmp, (255, 235, 160, 190), False, pts, max(2, int(r * 0.05)))
        for ang, ln in ((-1.1, 0.85), (0.5, 0.6)):
            pygame.draw.line(tmp, (255, 245, 210, 235), (c, c), (c + math.cos(ang) * r * ln, c + math.sin(ang) * r * ln), max(3, int(r * 0.06)))
        pygame.draw.circle(tmp, (255, 250, 230, 255), (c, c), max(3, int(r * 0.1)))
    elif kind == "strings":                # vibrating strings with bead nodes
        for k in range(7):
            col = (150, 180, 255, 170) if k % 2 == 0 else (210, 150, 255, 150)
            pts = []
            for x in range(-int(r * 2.2), int(r * 2.2) + 1, 6):
                env = max(0.0, 1.0 - abs(x) / (r * 2.3))
                pts.append((c + x, c + (k - 3) * r * 0.3 + math.sin(x / (r * 0.34) + k * 0.9) * r * 0.24 * env))
            pygame.draw.lines(tmp, col, False, pts, max(2, int(r * 0.035)))
            for j in range(0, len(pts), 16):
                pygame.draw.circle(tmp, (235, 240, 255, 230), pts[j], max(2, int(r * 0.045)))
        pygame.draw.circle(tmp, (255, 255, 255, 240), (c, c), max(3, int(r * 0.12)))
        pygame.draw.circle(tmp, (160, 190, 255, 110), (c, c), int(r * 0.3), 2)
    surface.blit(tmp, (int(cx - pad), int(cy - pad)))


# --------------------------------------------------------------------------- backdrops
def make_far_layer(sector, seed, w, h, hero_pos=None):
    th = THEMES[sector]
    rng = random.Random(seed * 977 + sector)
    surf = pygame.Surface((w, h))
    for y in range(0, h, 8):
        pygame.draw.rect(surf, _lerp(th["top"], th["bot"], y / float(h)), (0, y, w, 8))
    for _ in range(int(9 + h / 350)):
        bw, bh = rng.randint(380, 820), rng.randint(260, 620)
        surf.blit(blob(bw, bh, rng.choice(th["neb"]), rng.uniform(0.22, 0.5)), (rng.randint(-200, w - 100), rng.randint(-100, h - 100)),
                  special_flags=pygame.BLEND_ADD)
    # star layers
    for _ in range(int(w * h / 5200)):
        x, y = rng.randrange(w), rng.randrange(h)
        v = rng.randint(60, 150)
        surf.set_at((x, y), (v, v, min(255, v + 50)))
    for _ in range(int(w * h / 26000)):
        x, y = rng.randrange(w), rng.randrange(h)
        v = rng.randint(170, 255)
        col = rng.choice([(v, v, 255), (255, v, v - 40 if v > 60 else 0), (v, 255, v)])
        pygame.draw.rect(surf, col, (x, y, 2, 2))
    for _ in range(int(w * h / 190000)):
        x, y = rng.randrange(40, w - 40), rng.randrange(h)
        col = (255, 255, 255)
        pygame.draw.line(surf, _scale(col, 0.6), (x - 6, y), (x + 6, y), 1)
        pygame.draw.line(surf, _scale(col, 0.6), (x, y - 6), (x, y + 6), 1)
        surf.set_at((x, y), col)
    # hero objects: a big one and a small companion at different depths
    hx = hero_pos[0] if hero_pos else rng.choice([rng.randint(120, 300), rng.randint(600, 780)])
    hy = hero_pos[1] if hero_pos else rng.randint(int(h * 0.22), int(h * 0.55))
    draw_hero(surf, th["hero"], hx, hy, rng.randint(120, 170), seed)
    other = {1: "crystal", 2: "supernova", 3: "ringed", 4: "pulsar", 5: "blackhole", 6: "strings", 7: "rift"}[sector]
    draw_hero(surf, other, w - hx + rng.randint(-60, 60), min(h - 200, hy + rng.randint(500, 900)), rng.randint(50, 80), seed + 7)
    return surf


def make_wall_texture(sector, w, h, seed):
    th = THEMES[sector]
    rng = random.Random(seed * 131 + sector)
    tex = pygame.Surface((w, h))
    for y in range(0, h, 8):
        pygame.draw.rect(tex, _lerp(_scale(th["wall"], 0.9), _scale(th["wall"], 1.2), (y % 900) / 900.0), (0, y, w, 8))
    # planetary surface shading: a few giant limbs so the walls read as huge bodies
    for _ in range(max(2, int(h / 900))):
        r = rng.randint(520, 900)
        cx, cy = rng.choice([-r * 0.55, w + r * 0.55, w * rng.random()]), rng.randint(0, h)
        for i in range(r, 0, -6):
            t = 1.0 - i / float(r)
            pygame.draw.circle(tex, _lerp(_scale(th["wall"], 0.75), _scale(th["wall2"], 1.05), t ** 0.7), (int(cx - r * 0.15 * t), int(cy - r * 0.15 * t)), i)
    # mottling
    for _ in range(int(w * h / 9000)):
        x, y, rr = rng.randrange(w), rng.randrange(h), rng.randint(14, 60)
        col = _scale(th["wall2"], rng.uniform(0.7, 1.15))
        pygame.draw.circle(tex, _lerp(tex.get_at((x % w, y % h))[:3], col, 0.35), (x, y), rr)
    acc = th["accent"]
    if sector == 1:      # cratered ice moon
        for _ in range(int(w * h / 30000)):
            x, y, rr = rng.randrange(w), rng.randrange(h), rng.randint(10, 44)
            pygame.draw.circle(tex, _scale(th["wall"], 0.55), (x, y), rr)
            pygame.draw.circle(tex, _scale(th["wall2"], 1.35), (x - 2, y - 2), rr, 2)
            pygame.draw.circle(tex, _scale(th["wall"], 0.4), (x + rr // 4, y + rr // 4), rr // 2)
        for _ in range(int(w * h / 26000)):
            x, y = rng.randrange(w), rng.randrange(h)
            ang = rng.uniform(0, 6.28)
            pts = [(x + math.cos(ang + k * 1.26) * rng.randint(6, 20), y + math.sin(ang + k * 1.26) * rng.randint(6, 20)) for k in range(5)]
            pygame.draw.polygon(tex, _scale(acc, 0.55), pts)
            pygame.draw.polygon(tex, (190, 235, 255), pts, 1)
    elif sector == 2:    # station hull plates
        for gy in range(0, h, 120):
            for gx in range(0, w, 150):
                ox = 75 if (gy // 120) % 2 else 0
                r = pygame.Rect(gx - ox, gy, 150, 120)
                pygame.draw.rect(tex, _scale(th["wall2"], rng.uniform(0.75, 1.05)), r.inflate(-4, -4))
                pygame.draw.rect(tex, _scale(th["wall"], 0.5), r, 2)
                for cxp, cyp in ((r.x + 10, r.y + 10), (r.right - 10, r.y + 10), (r.x + 10, r.bottom - 10), (r.right - 10, r.bottom - 10)):
                    pygame.draw.circle(tex, _scale(th["wall2"], 1.5), (cxp, cyp), 3)
                if rng.random() < 0.28:
                    pygame.draw.circle(tex, acc, (r.centerx, r.centery), 5)
                    pygame.draw.circle(tex, _scale(acc, 0.5), (r.centerx, r.centery), 9, 2)
    elif sector == 3:    # crystal lattice
        for gy in range(0, h, 80):
            for gx in range(0, w + 80, 92):
                cx = gx + (46 if (gy // 80) % 2 else 0)
                pts = [(cx + math.cos(k * 1.047 + 0.52) * 46, gy + 40 + math.sin(k * 1.047 + 0.52) * 46) for k in range(6)]
                pygame.draw.polygon(tex, _scale(th["wall2"], rng.uniform(0.75, 1.1)), pts)
                pygame.draw.polygon(tex, _scale(acc, 0.32), pts, 2)
                if rng.random() < 0.16:
                    pygame.draw.circle(tex, acc, (cx, gy + 40), 4)
    elif sector == 4:    # lava rock
        for _ in range(int(w * h / 22000)):
            x, y = rng.randrange(w), rng.randrange(h)
            pts = [(x, y)]
            for _k in range(rng.randint(4, 9)):
                x += rng.randint(-26, 26)
                y += rng.randint(-14, 30)
                pts.append((x, y))
            pygame.draw.lines(tex, (60, 14, 6), False, pts, 7)
            pygame.draw.lines(tex, (255, 110, 20), False, pts, 3)
            pygame.draw.lines(tex, (255, 220, 120), False, pts, 1)
        for _ in range(int(w * h / 12000)):
            pygame.draw.circle(tex, (255, rng.randint(120, 200), 40), (rng.randrange(w), rng.randrange(h)), rng.randint(1, 2))
    elif sector == 6:    # brass clockwork: gears and ticking dials
        for _ in range(int(w * h / 55000)):
            gx, gy, rr = rng.randrange(w), rng.randrange(h), rng.randint(36, 110)
            teeth = max(8, rr // 7)
            pts = []
            for k in range(teeth * 2):
                a = k * math.pi / teeth
                rad = rr if k % 2 == 0 else rr * 0.82
                pts.append((gx + math.cos(a) * rad, gy + math.sin(a) * rad))
            pygame.draw.polygon(tex, _scale(th["wall2"], rng.uniform(0.85, 1.2)), pts)
            pygame.draw.polygon(tex, _scale(acc, 0.5), pts, 2)
            pygame.draw.circle(tex, _scale(th["wall"], 0.6), (gx, gy), rr // 3)
            pygame.draw.circle(tex, _scale(acc, 0.7), (gx, gy), rr // 3, 2)
            pygame.draw.circle(tex, acc, (gx, gy), max(3, rr // 10))
        for _ in range(int(w * h / 16000)):
            pygame.draw.circle(tex, (255, 230, 150), (rng.randrange(w), rng.randrange(h)), 1)
    elif sector == 7:    # a lattice of humming strings
        for y0 in range(0, h, 34):
            ph, am = rng.uniform(0, 6.28), rng.uniform(3, 9)
            pts = [(x, y0 + math.sin(x / 46.0 + ph) * am) for x in range(0, w + 12, 12)]
            pygame.draw.lines(tex, _scale(acc, rng.uniform(0.22, 0.45)), False, pts, 2)
        for _ in range(int(w * h / 14000)):
            pygame.draw.circle(tex, (210, 225, 255), (rng.randrange(w), rng.randrange(h)), rng.randint(1, 2))
        for _ in range(int(w * h / 90000)):
            x, y, rr = rng.randrange(w), rng.randrange(h), rng.randint(20, 54)
            pygame.draw.circle(tex, _scale(acc, 0.5), (x, y), rr, 2)
    else:                # obsidian with red fractures and gold dust
        for _ in range(int(w * h / 34000)):
            x, y = rng.randrange(w), rng.randrange(h)
            pts = [(x, y)]
            for _k in range(rng.randint(3, 7)):
                x += rng.randint(-40, 40)
                y += rng.randint(-30, 40)
                pts.append((x, y))
            pygame.draw.lines(tex, (50, 6, 18), False, pts, 6)
            pygame.draw.lines(tex, (255, 40, 80), False, pts, 2)
        for _ in range(int(w * h / 9000)):
            pygame.draw.circle(tex, (255, 210, 90), (rng.randrange(w), rng.randrange(h)), 1)
        for _ in range(int(w * h / 60000)):
            x, y, rr = rng.randrange(w), rng.randrange(h), rng.randint(30, 80)
            pygame.draw.circle(tex, _scale(th["wall2"], 1.4), (x, y), rr, 2)
    return tex


def make_menu_backdrop(w, h, seed=5):
    """Full-screen backdrop for menus (sector 1 nebula + ringed planet low on the screen)."""
    return make_far_layer(1, seed, w, h, hero_pos=(w - 190, int(h * 0.86)))


# --------------------------------------------------------------------------- drifting rocks / animated scenery
def make_rock_shape(rng, n=9):
    return [(i * 6.283 / n + rng.uniform(-0.25, 0.25), rng.uniform(0.62, 1.0)) for i in range(n)]


def draw_rock(surface, x, y, size, ang, shape, base, edge):
    pts = [(x + math.cos(a + ang) * size * r, y + math.sin(a + ang) * size * r) for a, r in shape]
    pygame.draw.polygon(surface, base, pts)
    pygame.draw.polygon(surface, edge, pts, 2)
    # crater + lit rim
    cx, cy = x + math.cos(ang + 1.0) * size * 0.25, y + math.sin(ang + 1.0) * size * 0.25
    pygame.draw.circle(surface, _scale(base, 0.6), (int(cx), int(cy)), max(2, int(size * 0.24)))
    pygame.draw.circle(surface, _scale(edge, 0.9), (int(cx - 1), int(cy - 1)), max(2, int(size * 0.24)), 1)


class SpaceLife:
    """Twinkling stars, comets and slowly drifting asteroids drawn over a static backdrop (menus)."""

    def __init__(self, w, h, sector=1, seed=11, quality=1.0):
        rng = random.Random(seed)
        th = THEMES[sector]
        self.w, self.h = w, h
        quality = max(0.35, min(1.0, float(quality)))
        self.twinkles = [(rng.randrange(10, w - 10), rng.randrange(10, h - 10), rng.uniform(0, 6.28))
                         for _ in range(max(24, int(70 * quality)))]
        self.rocks = [(rng.uniform(0, w + 160), rng.uniform(80, h - 80), rng.uniform(10, 30), rng.uniform(-0.6, 0.6),
                       rng.uniform(6, 22), make_rock_shape(rng)) for _ in range(max(3, int(6 * quality)))]
        self.base = _scale(th["wall2"], 1.0)
        self.edge = _scale(th["accent"], 0.55)

    def draw(self, surface, t, avoid=None):
        """`avoid`: rects covered by UI (no twinkle there). Returns the rects of the rocks / comets drawn."""
        tw = self.twinkles
        if avoid is not None:
            key = id(avoid)
            if getattr(self, "_tw_key", None) != key:
                self._tw_key = key
                self._tw = [p for p in self.twinkles if not any(r.collidepoint(p[0], p[1]) for r in avoid)]
            tw = self._tw
        drawn = []
        for (x, y, ph) in tw:
            v = int(120 + 120 * math.sin(t * 2.0 + ph))
            surface.set_at((x, y), (v, v, 255))
        for k in range(2):
            per = 9.0 + 5.0 * k
            ph = (t + k * 3.7) % per
            if ph < 1.5:
                f = ph / 1.5
                sx, sy = 60 + 380 * k, 90 + 250 * k
                for j in range(9):
                    tt = max(0.0, f - j * 0.025)
                    c = int(220 * (1 - j / 9.0) * math.sin(math.pi * min(1.0, f + 0.05)))
                    pygame.draw.circle(surface, (c, c, min(255, c + 25)), (int(sx + 520 * tt), int(sy + 260 * tt)), max(1, 4 - j // 3))
                hx, hy = sx + 520 * f, sy + 260 * f
                drawn.append(pygame.Rect(int(hx - 110), int(hy - 60), 120, 70))
        for (x0, y0, size, spin, vx, shape) in self.rocks:
            x = (x0 + vx * t) % (self.w + 160) - 80
            y = y0 + 6 * math.sin(t * 0.5 + x0)
            draw_rock(surface, x, y, size, t * spin, shape, self.base, self.edge)
            drawn.append(pygame.Rect(int(x - size * 1.5), int(y - size * 1.5), int(size * 3) + 2, int(size * 3) + 2))
        return drawn
