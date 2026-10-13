"""Rendering of a level (the simulation data lives in sim.py).

The static part (background, walls, neon outlines, rails) is rendered once into an opaque surface so a frame
only costs one blit plus the handful of animated hazards - important for phones.  Levels can be taller than
the screen: `draw` takes a camera offset `oy`.
"""
import math
import random
import pygame

import gfx
from render_cache import SurfaceCache

import space_art
from sim import LevelData, ARENA_W

W_I = int(ARENA_W)

SECTOR_NAMES = {1: "ALPHA ORBITAL", 2: "PULSAR VOID", 3: "QUANTUM PUZZLES", 4: "EVENT HORIZON", 5: "OMEGA VOID"}


def sector_of(level_id):
    return min(5, max(1, (level_id - 1) // 20 + 1))


def get_sector_info(level_id):
    s = sector_of(level_id)
    return f"SEKTÖR {s}", SECTOR_NAMES[s]


PALETTES = {
    1: {"fill": (20, 27, 44), "grid": (30, 40, 62), "border": (0, 210, 255), "accent": (0, 240, 255),
        "bg_top": (8, 12, 24), "bg_bot": (12, 22, 40), "star_color": (255, 235, 90), "star_glow": (255, 210, 40)},
    2: {"fill": (30, 20, 44), "grid": (44, 30, 64), "border": (210, 60, 255), "accent": (240, 110, 255),
        "bg_top": (14, 8, 24), "bg_bot": (26, 12, 40), "star_color": (255, 210, 140), "star_glow": (220, 70, 255)},
    3: {"fill": (16, 34, 30), "grid": (24, 50, 44), "border": (35, 245, 140), "accent": (80, 255, 180),
        "bg_top": (6, 16, 14), "bg_bot": (10, 28, 24), "star_color": (240, 255, 130), "star_glow": (50, 255, 150)},
    4: {"fill": (40, 22, 18), "grid": (58, 32, 26), "border": (255, 115, 25), "accent": (255, 180, 50),
        "bg_top": (20, 9, 8), "bg_bot": (34, 14, 10), "star_color": (255, 190, 40), "star_glow": (255, 90, 20)},
    5: {"fill": (24, 16, 32), "grid": (38, 26, 50), "border": (255, 35, 75), "accent": (255, 215, 50),
        "bg_top": (10, 6, 16), "bg_bot": (24, 8, 22), "star_color": (255, 255, 220), "star_glow": (255, 190, 40)},
}


def get_sector_palette(level_id):
    return PALETTES[sector_of(level_id)]


_GLOW = SurfaceCache(12 * 1024 * 1024)


def glow_sprite(radius, color, strength=1.0):
    """Soft radial glow for additive blitting (BLEND_ADD ignores alpha, so intensity is baked into the colour)."""
    strength = round(strength * 16) / 16.0
    key = (int(radius), tuple(color), strength)
    spr = _GLOW.get(key)
    if spr is None:
        r = int(radius)
        spr = pygame.Surface((r * 2 + 2, r * 2 + 2))
        for i in range(8, 0, -1):
            k = 0.30 * strength * ((9 - i) / 8.0) ** 1.6
            pygame.draw.circle(spr, tuple(max(0, min(255, int(c * k))) for c in color), (r + 1, r + 1), int(r * i / 8.0))
        spr = _GLOW.put(key, gfx.cv(spr))
    return spr


# Glows with a changing strength are drawn in a few fixed steps, all built when the level loads (Level.warm_glows):
# every new strength used to build a ~300 px glow sprite in the middle of play - the stutter on each bumper bounce.
def _bumper_glow_r(w, h):
    return int(max(int(w), int(h)) * 0.45) + 26


def _bumper_glow_k(fl):
    return 0.22 + 0.55 * round(max(0.0, min(1.0, fl)) * 4) / 4.0


def _barrier_glow_r(w, h):
    return int(max(int(w), int(h)) * 0.35) + 20


def _barrier_glow_k(pulse):
    return 0.35 * round(pulse * 8) / 8.0


def add_glow(surface, x, y, radius, color, strength=1.0):
    spr = glow_sprite(radius, color, strength)
    surface.blit(spr, (int(x - radius - 1), int(y - radius - 1)), special_flags=pygame.BLEND_ADD)


class Level:
    def __init__(self, level_id):
        self.id = level_id
        self.data = None
        self.far = None
        self.fg = None
        self.loaded = False
        self.sector = sector_of(level_id)
        self.sector_code, self.sector_title = get_sector_info(level_id)
        self.level_title = ""
        self.palette = get_sector_palette(level_id)
        self._piston = {}

    @property
    def start_pos(self):
        return self.data.start

    @property
    def end_pos(self):
        return self.data.end

    @property
    def height(self):
        return self.data.height

    def load(self, levels_dir=None):
        self.data = LevelData.load(self.id, levels_dir)
        if self.data is None:
            return False
        self.level_title = self.data.title
        self._render_static()
        self.warm_glows()
        self.loaded = True
        return True

    def warm_glows(self):
        """Build every glow sprite whose strength changes during play now, not in the middle of a swing."""
        d = self.data
        for (x, y, w, h) in d.reverse_walls:
            for k in range(5):
                glow_sprite(_bumper_glow_r(w, h), (40, 255, 170), _bumper_glow_k(k / 4.0))
        for (x, y, w, h) in d.barriers:
            for k in range(5, 9):                    # pulse = 0.65 .. 1.0 -> 0.625 .. 1.0 in eighths
                glow_sprite(_barrier_glow_r(w, h), (40, 160, 255), _barrier_glow_k(k / 8.0))

    # ---- static layers ---------------------------------------------------------------
    KEY = (255, 0, 255)

    def _render_static(self):
        """far: opaque parallax space backdrop; fg: walls + neon edges (colour-keyed, free space transparent)."""
        d = self.data
        pal = self.palette
        H_I = int(d.height)
        far_h = int(1900 + 0.3 * max(0, H_I - 1400))
        self.far = gfx.cv(space_art.make_far_layer(self.sector, self.id, W_I, far_h))

        walls = pygame.Surface((W_I, H_I), pygame.SRCALPHA)
        for (x, y, w, h) in d.walls:
            pygame.draw.rect(walls, (255, 255, 255, 255), (int(x), int(y), int(w), int(h)))
        mask = pygame.mask.from_surface(walls, 127)
        tex = space_art.make_wall_texture(self.sector, W_I, H_I, self.id)
        walls.blit(tex, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)

        fg = pygame.Surface((W_I, H_I))
        fg.fill(self.KEY)
        fg.blit(walls, (0, 0))
        border, accent = pal["border"], pal["accent"]
        dim1 = tuple(int(c * 0.28) for c in border)
        dim2 = tuple(int(c * 0.62) for c in border)
        # Boundaries of the wall mass: outline() only traces the OUTER contour of a component, so corridors that are
        # "holes" inside a big wall mass must be traced from the inverted (free space) mask as well.
        free_mask = mask.copy()
        free_mask.invert()
        contours = []
        for m_ in (mask, free_mask):
            try:
                comps = m_.connected_components()
            except Exception:
                comps = [m_]
            for comp in comps:
                if comp.count() < 60:
                    continue
                pts = comp.outline()
                if len(pts) >= 3:
                    contours.append(pts)
        for width, col in ((8, dim1), (5, dim2), (2, border)):
            for pts in contours:
                pygame.draw.lines(fg, col, True, pts, width)
        for pts in contours:
            pygame.draw.lines(fg, accent, True, pts, 1)

        # moving walls: the track each one runs along, so a player can see how far it will come (1.0.8: brighter,
        # with end stops; a two-axis wall shows the whole area it roams instead of a cross)
        rail, stop = (150, 96, 42), (220, 140, 50)
        for m in d.moving_walls:
            x, y, w, h = m[0], m[1], m[2], m[3]
            two_axis = len(m) > 8 and m[4] > 0 and m[5] > 0
            if two_axis:                     # the loop its centre runs along (1.0.8 levels: one clean oval), dashed
                per = 2.0 * math.pi / max(0.05, abs(m[6]))
                pts = [(x + w / 2 + math.sin(t * m[6] + m[7]) * m[4], y + h / 2 + math.sin(t * m[8] + m[9]) * m[5])
                       for t in (per * k / 72.0 for k in range(73))]
                for k in range(0, 72, 2):
                    pygame.draw.line(fg, rail, pts[k], pts[k + 1], 4)
                pygame.draw.circle(fg, stop, (int(x + w / 2), int(y + h / 2)), 6)
                continue
            if m[4] > 0:
                a, b, cy = x - m[4], x + w + m[4], y + h / 2
                pygame.draw.line(fg, rail, (a, cy), (b, cy), 4)
                for ex in (a, b):
                    pygame.draw.line(fg, stop, (ex, cy - 12), (ex, cy + 12), 4)
            if m[5] > 0:
                a, b, cx = y - m[5], y + h + m[5], x + w / 2
                pygame.draw.line(fg, rail, (cx, a), (cx, b), 4)
                for ey in (a, b):
                    pygame.draw.line(fg, stop, (cx - 12, ey), (cx + 12, ey), 4)
        for l in d.lasers:
            for (px, py) in ((l[0], l[1]), (l[2], l[3])):
                pygame.draw.circle(fg, (60, 64, 80), (int(px), int(py)), 11)
                pygame.draw.circle(fg, (150, 40, 70), (int(px), int(py)), 7)
        for s_ in d.spinners:
            pygame.draw.circle(fg, (60, 64, 80), (int(s_[0]), int(s_[1])), 14)
            pygame.draw.circle(fg, (150, 40, 90), (int(s_[0]), int(s_[1])), 9)
        self.fg = gfx.cv(fg)
        self.fg.set_colorkey(self.KEY, pygame.RLEACCEL)
        rng = random.Random(self.id * 17)
        self.twinkles = [(rng.randrange(20, W_I - 20), rng.randrange(0, far_h), rng.uniform(0, 6.28)) for _ in range(46)]
        self.dust = [(rng.randrange(10, W_I - 10), rng.random(), rng.random()) for _ in range(40)]
        self.far_h = far_h
        th = space_art.THEMES[self.sector]
        rr = random.Random(self.id * 41)
        span = int(H_I * 0.55 + 1900)
        self.rocks = [(rr.uniform(0, W_I + 160), rr.uniform(0, span), rr.uniform(14, 46), rr.uniform(-0.8, 0.8), rr.uniform(6, 26),
                       space_art.make_rock_shape(rr)) for _ in range(int(6 + span / 450))]
        self.rock_col = (space_art._scale(th["wall2"], 1.05), space_art._scale(th["accent"], 0.5))

    # ---- dynamic layer ------------------------------------------------------------------
    def _draw_space_life(self, arena, t, vh, far_y, boost):
        # twinkling stars (parallax with the far layer)
        for (x, y, ph) in self.twinkles:
            yy = y - far_y
            if 0 <= yy < vh:
                v = int(150 + 105 * math.sin(t * 2.3 + ph))
                arena.set_at((x, yy), (v, v, 255))
                arena.set_at((x + 1, yy), (v // 2, v // 2, 200))
        # drifting asteroids (nearer than the nebula, so they parallax faster)
        base, edge = self.rock_col
        oyp = int(far_y * 1.8)
        for (x0, y0, size, spin, vx, shape) in self.rocks:
            yy = y0 - oyp
            if -80 < yy < vh + 80:
                space_art.draw_rock(arena, (x0 + vx * t) % (W_I + 160) - 80, yy, size, t * spin, shape, base, edge)
        # a comet now and then
        for k in range(2):
            per = 11.0 + 6.0 * k
            ph = (t + k * 4.3) % per
            if ph < 1.4:
                f = ph / 1.4
                sx = 120 + 260 * k + (self.id * 53 % 300)
                sy = 120 + (self.id * 37 % 400) + 180 * k
                hx, hy = sx + 520 * f, sy + 260 * f
                for j in range(9):
                    tt = max(0.0, f - j * 0.025)
                    px, py = sx + 520 * tt, sy + 260 * tt
                    c = int(230 * (1 - j / 9.0) * math.sin(math.pi * min(1.0, f + 0.05)))
                    pygame.draw.circle(arena, (c, c, min(255, c + 25)), (int(px), int(py)), max(1, 4 - j // 3))
        # space dust streaks: only appear once the (hidden) speed-up kicks in
        if boost > 1.035:
            dirn = 1.0 if self.data.end[1] < self.data.start[1] else -1.0
            k_ = min(1.0, (boost - 1.035) / 0.6)
            vel = 120 + 900 * k_
            ln = 10 + 90 * k_
            col = (int(70 + 90 * k_), int(110 + 100 * k_), int(160 + 90 * k_))
            for (x, sp, ph) in self.dust:
                y = ((ph * (vh + 200) + dirn * t * vel * (0.35 + 0.65 * sp)) % (vh + 200)) - 100
                pygame.draw.line(arena, col, (x, y), (x, y - dirn * ln * (0.4 + sp)), 1 + int(k_ > 0.5))

    def _piston_sprite(self, w, h):
        key = (int(w), int(h))
        spr = self._piston.get(key)
        if spr is None:
            spr = pygame.Surface(key)
            spr.fill((44, 26, 18))
            for sx in range(-key[1], key[0] + 20, 18):
                pygame.draw.line(spr, (255, 135, 20), (sx, 0), (sx + key[1], key[1]), 3)
            pygame.draw.rect(spr, (255, 175, 30), spr.get_rect(), 2, border_radius=4)
            self._piston[key] = gfx.cv(spr)
        return spr

    def reset_fx(self):
        """Forget per-attempt effects (bumper flashes) when an attempt restarts."""
        self.rev_hits = {}

    def flash_bumper(self, idx, t):
        if not hasattr(self, "rev_hits"):
            self.rev_hits = {}
        self.rev_hits[idx] = t

    def draw(self, arena, t, sim=None, oy=0.0, boost=1.0):
        """Draw the level into `arena` (a surface as big as the viewport) with camera offset `oy`.
        `boost` = current speed / base speed; it only drives subtle scenery (space dust streaks)."""
        d = self.data
        pal = self.palette
        vh = arena.get_height()
        oy = int(oy)
        far_y = max(0, min(int(oy * 0.3), self.far_h - vh))
        arena.blit(self.far, (0, -far_y))
        self._draw_space_life(arena, t, vh, far_y, boost)
        arena.blit(self.fg, (0, -oy))
        self._draw_dynamic(arena, t, sim, oy)

    def _draw_dynamic(self, arena, t, sim, oy):
        """Everything that moves or changes (drawn over the static layers); `oy` = int camera offset."""
        d = self.data
        pal = self.palette
        vh = arena.get_height()

        def vis(y0, y1):
            return y1 - oy >= -60 and y0 - oy <= vh + 60

        # reverse walls (kinetic bumpers)
        pulse = 0.85 + 0.15 * math.sin(t * 5.0)
        border_c = (int(35 * pulse), int(245 * pulse), int(165 * pulse))
        wave = (t * 35.0) % 32.0
        hits = getattr(self, "rev_hits", {})
        for ridx, (x, y, w, h) in enumerate(d.reverse_walls):
            if not vis(y, y + h):
                continue
            r = pygame.Rect(int(x), int(y) - oy, int(w), int(h))
            # 1 right after a bounce, fades out. A hit time from an earlier attempt (retry / rewind restarts t) lies in
            # the "future": ignore it - unclamped it pushed the colours past 255 and crashed the game on TRY AGAIN.
            since = t - hits.get(ridx, -9.0)
            fl = max(0.0, 1.0 - since / 0.55) if since >= 0.0 else 0.0
            add_glow(arena, r.centerx, r.centery, _bumper_glow_r(w, h), (40, 255, 170), _bumper_glow_k(fl))
            pygame.draw.rect(arena, (int(12 + 120 * fl), int(52 + 180 * fl), int(42 + 120 * fl)), r, border_radius=6)
            pygame.draw.rect(arena, (int(10 + 150 * fl), int(150 + 90 * fl), int(100 + 110 * fl)), r, 3 + int(3 * fl), border_radius=6)
            pygame.draw.rect(arena, border_c, r, 1, border_radius=6)
            if fl > 0.02:
                grow = int(22 * (1.0 - fl))
                pygame.draw.rect(arena, (200, 255, 230), r.inflate(grow, grow), 2, border_radius=10)
            cx, cy = r.centerx, r.centery
            if r.w >= r.h:
                for xp in range(r.left + 18, r.right - 10, 32):
                    px = xp + int(wave) - 16
                    if r.left + 8 <= px <= r.right - 8:
                        pygame.draw.polygon(arena, (130, 255, 210), [(px - 6, cy - 6), (px + 4, cy), (px - 6, cy + 6)], 2)
            else:
                for yp in range(r.top + 18, r.bottom - 10, 32):
                    py = yp + int(wave) - 16
                    if r.top + 8 <= py <= r.bottom - 8:
                        pygame.draw.polygon(arena, (130, 255, 210), [(cx - 6, py - 4), (cx, py + 5), (cx + 6, py - 4)], 2)

        # just revived: moving walls, lasers and spinners spare the pair (sim REVIVE_SAFE) - drawn faded, fading back in
        spare = sim.revive_t if sim is not None else 0.0
        fade = 1.0 if spare <= 0 else max(0.22, 1.0 - spare)
        fq = round(fade, 1)                    # glow sprites are cached by strength: a few steps only

        def fc(c):
            return c if fade >= 1.0 else tuple(int(16 + (v - 16) * fade) for v in c)

        # moving walls
        for m in d.moving_walls:
            x, y, w, h = d.moving_rect(m, t)
            if not vis(y, y + h):
                continue
            spr = self._piston_sprite(w, h)
            if fade < 1.0:
                ghost = self._piston.get(("ghost", spr.get_size()))
                if ghost is None:
                    ghost = self._piston[("ghost", spr.get_size())] = spr.copy()
                ghost.set_alpha(int(255 * fade))
                spr = ghost
            arena.blit(spr, (int(x), int(y) - oy))
            led = (math.sin(t * 9.0) + 1.0) * 0.5
            pygame.draw.circle(arena, (int(200 + 55 * led), int(50 * led), 20), (int(x + w / 2), int(y + h / 2) - oy), 5)

        # power-up gates: energy barriers, cracked walls, chaser walls
        for (x, y, w, h) in d.barriers:
            if vis(y, y + h):
                self._draw_barrier(arena, x, y - oy, w, h, t)
        for i, (x, y, w, h) in enumerate(d.breakables):
            if (sim is not None and sim.broken[i]) or not vis(y, y + h):
                continue
            self._draw_breakable(arena, x, y - oy, w, h, t)
        for i, c in enumerate(d.chasers):
            t0 = sim.chase_t0[i] if sim is not None else None
            if t0 is None:
                if vis(c[7], c[7] + c[9]):
                    self._draw_run_line(arena, c, t, oy)
                continue
            r_ = d.chaser_rect(c, t0, sim.t)
            if r_ is not None and vis(r_[1], r_[1] + r_[3]):
                self._draw_chaser(arena, r_, c, t, oy)

        # zones
        for zs, col, glyph in ((d.growth, (40, 255, 130), "+"), (d.shrink, (90, 200, 255), "-"), (d.boost, (255, 190, 40), ">")):
            for z in zs:
                if vis(z[1] - z[2], z[1] + z[2]):
                    self._draw_zone(arena, z, t, col, glyph, oy)

        # mines
        for (x, y, r) in d.circles:
            if vis(y - r, y + r):
                self._draw_mine(arena, x, y - oy, r, t)

        # lasers
        for l in d.lasers:
            if not vis(min(l[1], l[3]), max(l[1], l[3])):
                continue
            active, warn = d.laser_state(l, t)
            a, b = (int(l[0]), int(l[1]) - oy), (int(l[2]), int(l[3]) - oy)
            if active:
                pygame.draw.line(arena, fc((120, 20, 50)), a, b, 16)
                pygame.draw.line(arena, fc((255, 60, 110)), a, b, 8)
                pygame.draw.line(arena, fc((255, 235, 240)), a, b, 3)
                for p in (a, b):
                    add_glow(arena, p[0], p[1], 26, (255, 60, 100), fq)
            elif warn:
                # A persistent dashed amber guide telegraphs the danger even
                # on a low-refresh display; solid pink still means active.
                dx, dy = b[0] - a[0], b[1] - a[1]
                length = max(1.0, math.hypot(dx, dy))
                color = (255, 175 + int(35 * math.sin(t * 9)), 85)
                for distance in range(0, int(length), 26):
                    end = min(length, distance + 13)
                    pygame.draw.line(arena, color,
                                     (int(a[0] + dx * distance / length), int(a[1] + dy * distance / length)),
                                     (int(a[0] + dx * end / length), int(a[1] + dy * end / length)), 2)
                for p in (a, b):
                    pygame.draw.circle(arena, color, p, 8, 2)

        # spinners (rotating hazard lasers)
        for s in d.spinners:
            if not vis(s[1] - s[2] - 16, s[1] + s[2] + 16):
                continue
            cx_i, cy_i = int(s[0]), int(s[1] - oy)
            r_spin = int(s[2])
            # Faint circular hazard sweep ring showing the exact rotation danger boundary
            pygame.draw.circle(arena, (120, 20, 65), (cx_i, cy_i), r_spin, 1)

            x1, y1, x2, y2 = d.spinner_segment(s, t)
            a, b = (int(x1), int(y1) - oy), (int(x2), int(y2) - oy)
            th = int(s[5])

            # Multi-layer intense neon laser beam
            pygame.draw.line(arena, fc((130, 15, 80)), a, b, th + 10)
            pygame.draw.line(arena, fc((255, 50, 150)), a, b, th + 2)
            pygame.draw.line(arena, fc((255, 245, 250)), a, b, 4)

            # High-energy plasma beads at the beam tips
            r_tip = th // 2 + 4
            for p in (a, b):
                pygame.draw.circle(arena, fc((255, 50, 150)), p, r_tip + 2)
                pygame.draw.circle(arena, fc((255, 245, 255)), p, r_tip - 1)

            # Central emitter reactor core
            pygame.draw.circle(arena, (18, 10, 30), (cx_i, cy_i), 11)
            pygame.draw.circle(arena, (255, 60, 160), (cx_i, cy_i), 8, 2)
            pygame.draw.circle(arena, (255, 240, 255), (cx_i, cy_i), 4)

            # Ambient neon danger glow
            add_glow(arena, s[0], s[1] - oy, r_spin + 20, (255, 50, 150), round(0.55 * fq, 2))

        for i, z in enumerate(d.shields):
            if (sim is not None and sim.shield_taken[i]) or not vis(z[1] - 40, z[1] + 40):
                continue
            self._draw_shield(arena, z[0], z[1] - oy, t)

        for i, z in enumerate(d.stars):
            if (sim is not None and sim.stars[i]) or not vis(z[1] - 50, z[1] + 50):
                continue
            self._draw_star(arena, z[0], z[1] - oy, t, i, pal)

        if vis(d.end[1] - 100, d.end[1] + 100):
            self._draw_goal(arena, t, oy)

    def _draw_barrier(self, arena, x, y, w, h, t):
        r = pygame.Rect(int(x), int(y), int(w), int(h))
        pygame.draw.rect(arena, (6, 24, 46), r)
        horiz = r.w >= r.h
        pulse = 0.65 + 0.35 * math.sin(t * 7.0)
        col = (int(60 + 60 * pulse), int(190 + 50 * pulse), 255)
        if horiz:
            step = 22
            for k, xp in enumerate(range(r.left + 4, r.right, step)):
                a = math.sin(t * 6.0 + k * 0.9) * (r.h * 0.28)
                pygame.draw.line(arena, col, (xp, r.centery - int(a) - 3), (xp, r.centery + int(a) + 3), 2)
            pygame.draw.line(arena, col, (r.left, r.top + 1), (r.right, r.top + 1), 2)
            pygame.draw.line(arena, col, (r.left, r.bottom - 2), (r.right, r.bottom - 2), 2)
        else:
            step = 22
            for k, yp in enumerate(range(r.top + 4, r.bottom, step)):
                a = math.sin(t * 6.0 + k * 0.9) * (r.w * 0.28)
                pygame.draw.line(arena, col, (r.centerx - int(a) - 3, yp), (r.centerx + int(a) + 3, yp), 2)
            pygame.draw.line(arena, col, (r.left + 1, r.top), (r.left + 1, r.bottom), 2)
            pygame.draw.line(arena, col, (r.right - 2, r.top), (r.right - 2, r.bottom), 2)
        add_glow(arena, r.centerx, r.centery, _barrier_glow_r(w, h), (40, 160, 255), _barrier_glow_k(pulse))

    def _draw_breakable(self, arena, x, y, w, h, t):
        r = pygame.Rect(int(x), int(y), int(w), int(h))
        pygame.draw.rect(arena, (96, 62, 38), r, border_radius=4)
        pygame.draw.rect(arena, (176, 118, 66), r, 3, border_radius=4)
        rnd = random.Random(int(x) * 31 + int(y))
        for _ in range(max(4, int(max(r.w, r.h) / 26))):
            px = r.left + rnd.random() * r.w
            py = r.top + rnd.random() * r.h
            a = rnd.random() * 6.28
            ln = 10 + rnd.random() * 16
            mx = px + math.cos(a) * ln
            my = py + math.sin(a) * ln
            pygame.draw.lines(arena, (34, 20, 12), False, [(px, py), ((px + mx) / 2 + rnd.uniform(-4, 4), (py + my) / 2 + rnd.uniform(-4, 4)), (mx, my)], 2)
        glint = 0.5 + 0.5 * math.sin(t * 3.0 + x * 0.02)
        pygame.draw.rect(arena, (int(230 + 25 * glint), int(160 + 60 * glint), 80), r, 1, border_radius=4)

    def _draw_run_line(self, arena, c, t, oy):
        """Faint dashed line marking where a chaser wall gets triggered."""
        tx, ty, tw, th = c[6], c[7] - oy, c[8], c[9]
        vx, vy = c[4], c[5]
        col = (255, 110, 90)
        if abs(vy) >= abs(vx):
            yy = int(ty + th / 2)
            for xp in range(int(tx), int(tx + tw), 26):
                pygame.draw.line(arena, col, (xp, yy), (min(xp + 12, tx + tw), yy), 2)
        else:
            xx = int(tx + tw / 2)
            for yp in range(int(ty), int(ty + th), 26):
                pygame.draw.line(arena, col, (xx, yp), (xx, min(yp + 12, ty + th)), 2)

    def _draw_chaser(self, arena, r_, c, t, oy):
        x, y, w, h = r_
        r = pygame.Rect(int(x), int(y) - oy, int(w), int(h))
        pygame.draw.rect(arena, (70, 10, 26), r, border_radius=6)
        off = int((t * 90) % 28)
        vertical_move = abs(c[5]) >= abs(c[4])
        clip = arena.get_clip()
        arena.set_clip(r.clip(arena.get_rect()))
        for k in range(-2, int(max(r.w, r.h) / 14) + 3):
            p = k * 28 + off
            if vertical_move:
                pygame.draw.line(arena, (255, 70, 90), (r.left + p, r.bottom), (r.left + p + r.h, r.top), 6)
            else:
                pygame.draw.line(arena, (255, 70, 90), (r.left, r.top + p), (r.right, r.top + p - r.w), 6)
        arena.set_clip(clip)
        pygame.draw.rect(arena, (255, 60, 90), r, 3, border_radius=6)
        add_glow(arena, r.centerx, r.centery, int(max(r.w, r.h) * 0.5) + 30, (255, 40, 80), 0.6)

    def _draw_zone(self, arena, z, t, col, glyph, oy=0):
        x, y, r = z
        y = y - oy
        pulse = 1.0 + 0.05 * math.sin(t * 5 + x)
        add_glow(arena, x, y, int(r * 1.05), col, 0.7)
        pygame.draw.circle(arena, col, (int(x), int(y)), int(r * pulse), 3)
        pygame.draw.circle(arena, tuple(c // 2 for c in col), (int(x), int(y)), int(r * 0.66 * pulse), 1)
        s = 16
        cx, cy = int(x), int(y)
        if glyph == "+":
            pygame.draw.line(arena, (200, 255, 220), (cx - s, cy), (cx + s, cy), 5)
            pygame.draw.line(arena, (200, 255, 220), (cx, cy - s), (cx, cy + s), 5)
        elif glyph == "-":
            pygame.draw.line(arena, (215, 240, 255), (cx - s, cy), (cx + s, cy), 5)
        else:
            off = int((t * 60) % 40) - 20
            for k in (-30, 0, 30):
                px = cx + k + off // 2
                pygame.draw.polygon(arena, (255, 235, 150), [(px - 8, cy - 12), (px + 8, cy), (px - 8, cy + 12)], 3)

    def _draw_mine(self, arena, x, y, r, t):
        cx, cy = int(x), int(y)
        for k in range(10):
            a = k * math.pi / 5 + t * 0.4
            pygame.draw.line(arena, (150, 40, 50), (cx + math.cos(a) * r * 0.7, cy + math.sin(a) * r * 0.7),
                             (cx + math.cos(a) * (r + 7), cy + math.sin(a) * (r + 7)), 4)
        pygame.draw.circle(arena, (52, 20, 28), (cx, cy), int(r))
        pygame.draw.circle(arena, (200, 50, 70), (cx, cy), int(r), 3)
        led = 0.5 + 0.5 * math.sin(t * 6 + x * 0.05)
        pygame.draw.circle(arena, (255, int(70 + 100 * led), int(80 + 60 * led)), (cx, cy), max(4, int(r * 0.32)))

    def _draw_shield(self, arena, x, y, t):
        rad = int(20 * (1.0 + 0.12 * math.sin(t * 4)))
        pts = [(x + math.cos(t * 1.5 + i * math.pi / 3) * rad, y + math.sin(t * 1.5 + i * math.pi / 3) * rad) for i in range(6)]
        add_glow(arena, x, y, 34, (0, 200, 255), 0.9)
        pygame.draw.polygon(arena, (150, 240, 255), pts, 3)
        pygame.draw.circle(arena, (255, 255, 255), (int(x), int(y)), 5)

    def _draw_star(self, arena, x, y, t, idx, pal):
        star_c, glow_c = pal["star_color"], pal["star_glow"]
        rad = int(16 * (1.0 + 0.15 * math.sin(t * 5.5 + idx * 1.6)))
        add_glow(arena, x, y, int(rad * 2.4), glow_c, 1.0)
        a0 = t * 2.2 + idx
        pts = []
        for i in range(16):
            rr = rad if i % 2 == 0 else rad * 0.42
            a = a0 + i * math.pi / 8.0
            pts.append((x + math.cos(a) * rr, y + math.sin(a) * rr))
        pygame.draw.polygon(arena, star_c, pts)
        inner = []
        for i in range(8):
            rr = rad * 0.5 if i % 2 == 0 else rad * 0.22
            a = -a0 * 1.5 + i * math.pi / 4.0
            inner.append((x + math.cos(a) * rr, y + math.sin(a) * rr))
        pygame.draw.polygon(arena, (255, 255, 255), inner)

    def _draw_goal(self, arena, t, oy=0):
        gx, gy = self.data.end
        cx, cy = int(gx), int(gy) - oy
        acc = self.palette["accent"]
        soft = tuple(int(c * 0.55) for c in acc)
        r1 = 20 + 4 * math.sin(t * 4)
        r2 = 30 + 5 * math.sin(t * 3 + 1)
        r3 = 42 + 6 * math.sin(t * 2 + 2)
        add_glow(arena, gx, cy, 84, acc, 1.0)
        for arm in range(4):
            pts = []
            for k in range(16):
                rr = 6 + k * 3.2
                a = t * 2.6 + arm * math.pi / 2 + k * 0.28
                pts.append((cx + math.cos(a) * rr, cy + math.sin(a) * rr))
            pygame.draw.lines(arena, soft, False, pts, 3)
            pygame.draw.lines(arena, acc, False, pts[6:], 2)
        pygame.draw.circle(arena, soft, (cx, cy), int(r3), 3)
        pygame.draw.circle(arena, acc, (cx, cy), int(r2), 2)
        pygame.draw.circle(arena, (220, 245, 255), (cx, cy), int(r1), 3)
        pygame.draw.circle(arena, (255, 255, 255), (cx, cy), 8)
        for i in range(6):
            a = t * 2.2 + i * math.pi / 3
            p = (int(cx + math.cos(a) * (r2 + 8)), int(cy + math.sin(a) * (r2 + 8)))
            pygame.draw.circle(arena, acc, p, 4)
            pygame.draw.circle(arena, (255, 255, 255), p, 2)
