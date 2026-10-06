import pygame

import gfx
import math
import random

from fonts import get_font

_FLOAT_TEXT = {}      # (text, colour) -> (label, shadow) surfaces for the floating popups

MAX_PARTICLES = 260


class FloatingText:
    __slots__ = ('x', 'y', 'text', 'color', 'life', 'max_life', 'vy')

    def __init__(self, x, y, text, color=(255, 255, 255), duration=1.2):
        self.x = float(x)
        self.y = float(y)
        self.text = text
        self.color = color
        self.life = float(duration)
        self.max_life = float(duration)
        self.vy = -1.6

    def update(self, dt=1.0):
        self.y += self.vy * dt
        self.life -= 0.02 * dt
        return self.life > 0


class Particle:
    __slots__ = ('x', 'y', 'vx', 'vy', 'color', 'radius', 'max_life', 'life', 'decay', 'shape', 'gravity')

    def __init__(self, x, y, vx, vy, color, radius=4, life=1.0, decay=0.03, shape="circle", gravity=0.0):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.color = color
        self.radius = radius
        self.max_life = life
        self.life = life
        self.decay = decay
        self.shape = shape
        self.gravity = gravity

    def update(self, dt=1.0):
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.vy += self.gravity * dt
        self.vx *= 0.96
        self.vy *= 0.96
        self.life -= self.decay * dt
        return self.life > 0


class Shockwave:
    __slots__ = ('x', 'y', 'radius', 'max_radius', 'color', 'width', 'life', 'decay')

    def __init__(self, x, y, color, max_radius=60, speed=4.0, width=4):
        self.x = x
        self.y = y
        self.radius = 8.0
        self.max_radius = max_radius
        self.color = color
        self.width = width
        self.life = 1.0
        self.decay = speed / max_radius

    def update(self, dt=1.0):
        self.radius += (self.max_radius - self.radius) * 0.18 * dt
        self.life -= self.decay * dt
        return self.life > 0 and self.radius < self.max_radius


def draw_shape(surface, kind, x, y, rad, col):
    """Small vector shapes used by skin trails and explosions."""
    x, y, rad = int(x), int(y), max(1, int(rad))
    if kind == "heart":
        r = max(2, rad)
        pygame.draw.circle(surface, col, (x - r // 2, y - r // 3), max(1, r // 2 + 1))
        pygame.draw.circle(surface, col, (x + r // 2, y - r // 3), max(1, r // 2 + 1))
        pygame.draw.polygon(surface, col, [(x - r, y - r // 5), (x + r, y - r // 5), (x, y + r)])
    elif kind == "star":
        pts = []
        for k in range(8):
            rr = rad * (1.5 if k % 2 == 0 else 0.55)
            a = -math.pi / 2 + k * math.pi / 4
            pts.append((x + math.cos(a) * rr, y + math.sin(a) * rr))
        pygame.draw.polygon(surface, col, pts)
    elif kind == "bubble":
        pygame.draw.circle(surface, col, (x, y), rad + 1, 1)
        pygame.draw.circle(surface, col, (x - rad // 3, y - rad // 3), max(1, rad // 4))
    elif kind in ("pixel", "hex"):
        pygame.draw.rect(surface, col, (x - rad, y - rad, 2 * rad, 2 * rad))
    elif kind == "flame":
        pygame.draw.polygon(surface, col, [(x - rad, y + rad), (x, y - rad * 1.7), (x + rad, y + rad)])
    elif kind == "snow":
        for a in (0, math.pi / 3, 2 * math.pi / 3):
            pygame.draw.line(surface, col, (x - math.cos(a) * rad * 1.4, y - math.sin(a) * rad * 1.4), (x + math.cos(a) * rad * 1.4, y + math.sin(a) * rad * 1.4), 1)
    elif kind == "paw":
        pygame.draw.circle(surface, col, (x, y + rad // 3), rad)
        for dx in (-1, 0, 1):
            pygame.draw.circle(surface, col, (x + dx * rad, y - rad), max(1, rad // 2))
    elif kind == "bolt":
        pygame.draw.lines(surface, col, False, [(x - rad, y - rad), (x, y - 1), (x - 2, y + 1), (x + rad, y + rad * 1.4)], 2)
    elif kind == "wisp":
        pygame.draw.ellipse(surface, col, (x - rad, y - rad // 2, rad * 2, max(2, rad)))
    elif kind == "rainbow":
        pygame.draw.circle(surface, (col[2], col[0], col[1]), (x, y), rad)
        pygame.draw.circle(surface, col, (x, y), max(1, rad // 2))
    else:
        pygame.draw.circle(surface, col, (x, y), rad)


class ParticleSystem:
    """Particles live in arena coordinates; the starfield lives in screen coordinates."""

    def __init__(self, screen_w=900, screen_h=1620, quality=1.0):
        self.w = screen_w
        self.h = screen_h
        self.quality = quality
        self.particles = []
        self.shockwaves = []
        self.trails = []
        self.starfield = []
        self.constellations = []
        self.floating_texts = []
        self.screen_shake = 0.0
        self._init_starfield()

    def resize(self, w, h):
        self.w, self.h = w, h
        self._init_starfield()

    def _init_starfield(self, count=110):
        self.starfield = []
        colors = [(210, 240, 255), (110, 215, 255), (190, 160, 255), (255, 225, 140)]
        for _ in range(count):
            self.starfield.append({
                'x': random.uniform(0, self.w), 'y': random.uniform(0, self.h),
                'speed': random.uniform(0.12, 0.6), 'size': random.choice([1, 1, 2, 3]),
                'color': random.choice(colors), 'alpha': random.randint(80, 230),
                'po': random.uniform(0, math.pi * 2), 'ps': random.uniform(0.04, 0.12),
            })
        self.constellations = []
        for i in range(min(18, len(self.starfield))):
            s1 = self.starfield[i]
            for j in range(i + 1, min(i + 7, len(self.starfield))):
                s2 = self.starfield[j]
                if 60 < math.hypot(s1['x'] - s2['x'], s1['y'] - s2['y']) < 170:
                    self.constellations.append((i, j))
                    break

    # ---- emitters --------------------------------------------------------------
    def add_shake(self, amount):
        self.screen_shake = min(25.0, self.screen_shake + amount)

    def get_shake_offset(self):
        if self.screen_shake <= 0.05:
            self.screen_shake = 0.0
            return 0, 0
        mag = self.screen_shake * self.screen_shake * 0.06
        ox = random.uniform(-mag, mag)
        oy = random.uniform(-mag, mag)
        self.screen_shake *= 0.85
        return int(ox), int(oy)

    def emit_floating_text(self, x, y, text, color=(255, 240, 60)):
        self.floating_texts.append(FloatingText(x, y, text, color))

    def emit_trail(self, x, y, color, radius=12, kind="circle"):
        self.trails.append({'x': x, 'y': y, 'color': color, 'radius': radius, 'life': 1.0, 'decay': 0.07, 'kind': kind})

    def _burst(self, x, y, color, n, smin, smax, rmin, rmax, dmin, dmax, shape, gravity=0.0, white=0.0):
        n = int(n * self.quality)
        for _ in range(n):
            if len(self.particles) >= MAX_PARTICLES:
                break
            angle = random.uniform(0, math.pi * 2)
            speed = random.uniform(smin, smax)
            c = (255, 255, 255) if random.random() < white else color
            self.particles.append(Particle(x, y, math.cos(angle) * speed, math.sin(angle) * speed, c,
                                           radius=random.uniform(rmin, rmax), life=1.0,
                                           decay=random.uniform(dmin, dmax), shape=shape, gravity=gravity))

    def emit_swap_pulse(self, x, y, color):
        self.shockwaves.append(Shockwave(x, y, color, max_radius=55, speed=5.0, width=3))
        self._burst(x, y, color, 10, 2.5, 6.0, 2.0, 4.0, 0.04, 0.08, "spark")

    def emit_explosion(self, x, y, color, kind="circle"):
        self.add_shake(18.0)
        self.shockwaves.append(Shockwave(x, y, color, max_radius=110, speed=8.0, width=5))
        self._burst(x, y, color, 40, 3.0, 11.0, 3.0, 6.0, 0.02, 0.045, "spark" if kind == "circle" else kind, gravity=0.1, white=0.3)
        if kind != "circle":
            self._burst(x, y, color, 14, 2.0, 7.0, 4.0, 7.0, 0.02, 0.04, "spark", gravity=0.05)

    def emit_bounce(self, x, y, color):
        """A bumper bounce: one ring and a small spark burst (it used to fire the full death explosion - 40 sparks,
        a shockwave and a heavy shake - on every bounce, which is what made bouncing stutter on phones)."""
        self.shockwaves.append(Shockwave(x, y, color, max_radius=70, speed=6.0, width=4))
        self._burst(x, y, color, 12, 2.5, 7.0, 2.5, 4.5, 0.03, 0.06, "spark")

    def emit_star_collect(self, x, y):
        self.add_shake(6.0)
        self.shockwaves.append(Shockwave(x, y, (255, 230, 80), max_radius=70, speed=6.0, width=3))
        self._burst(x, y, (255, 230, 80), 22, 3.0, 7.5, 2.5, 4.5, 0.03, 0.06, "circle")

    def emit_portal_particles(self, cx, cy, color=(80, 180, 255)):
        if random.random() < 0.5 * self.quality and len(self.particles) < MAX_PARTICLES:
            d = random.uniform(35, 65)
            a = random.uniform(0, math.pi * 2)
            tangent = a + math.pi * 0.6
            self.particles.append(Particle(cx + math.cos(a) * d, cy + math.sin(a) * d,
                                           math.cos(tangent) * 2.2 - math.cos(a) * 1.5,
                                           math.sin(tangent) * 2.2 - math.sin(a) * 1.5, color,
                                           radius=random.uniform(1.8, 3.2), life=1.0, decay=0.035, shape="circle"))

    # ---- update --------------------------------------------------------------------
    def update(self, dt=1.0):
        # Compact the hot lists in place.  The old comprehensions allocated
        # three fresh lists every frame and caused periodic GC pauses on Android.
        write = 0
        for item in self.particles:
            if item.update(dt):
                self.particles[write] = item
                write += 1
        del self.particles[write:]
        write = 0
        for item in self.shockwaves:
            if item.update(dt):
                self.shockwaves[write] = item
                write += 1
        del self.shockwaves[write:]
        for t in self.trails:
            t['life'] -= t['decay'] * dt
        write = 0
        for item in self.trails:
            if item['life'] > 0:
                self.trails[write] = item
                write += 1
        del self.trails[write:]
        for s in self.starfield:
            s['y'] = (s['y'] + s['speed'] * dt) % self.h
            s['po'] += s['ps'] * dt
        write = 0
        for item in self.floating_texts:
            if item.update(dt):
                self.floating_texts[write] = item
                write += 1
        del self.floating_texts[write:]

    # ---- drawing ---------------------------------------------------------------------
    def draw_starfield(self, surface):
        for i1, i2 in self.constellations:
            s1, s2 = self.starfield[i1], self.starfield[i2]
            pygame.draw.line(surface, (22, 34, 56), (int(s1['x']), int(s1['y'])), (int(s2['x']), int(s2['y'])), 1)
        for s in self.starfield:
            a = max(0.15, min(1.0, (s['alpha'] + 50 * math.sin(s['po'])) / 255.0))
            r, g, b = s['color']
            col = (int(r * a * 0.9), int(g * a * 0.9), int(b * a * 0.9))
            x, y = int(s['x']), int(s['y'])
            if s['size'] == 1:
                surface.set_at((x, y), col) if 0 <= x < self.w and 0 <= y < self.h else None
            elif s['size'] == 2:
                pygame.draw.rect(surface, col, (x, y, 2, 2))
            else:
                pygame.draw.line(surface, col, (x - 3, y), (x + 3, y), 1)
                pygame.draw.line(surface, col, (x, y - 3), (x, y + 3), 1)
                surface.set_at((x, y), (255, 255, 255)) if 0 <= x < self.w and 0 <= y < self.h else None

    def draw_spawn_shield(self, surface, p1, p2, time_val, life_ratio=1.0):
        pulse = 1.0 + 0.08 * math.sin(time_val * 14)
        a = max(0.0, min(1.0, life_ratio))
        col = (int(120 * a), int(245 * a), int(255 * a))
        for pt in (p1, p2):
            rad = int(26 * pulse)
            pygame.draw.circle(surface, col, (int(pt[0]), int(pt[1])), rad, 2)
            pts = [(pt[0] + math.cos(time_val * 3.0 + i * math.pi / 3) * (rad + 5),
                    pt[1] + math.sin(time_val * 3.0 + i * math.pi / 3) * (rad + 5)) for i in range(6)]
            pygame.draw.polygon(surface, (0, int(150 * a), int(160 * a)), pts, 1)

    def draw_floating_texts(self, surface, oy=0):
        font = get_font(26, bold=True)
        for ft in self.floating_texts:
            alpha = int(max(0, min(255, (ft.life / ft.max_life) * 255)))
            if alpha <= 5:
                continue
            # Popups appear exactly when a lot happens (grow, smash, shield...): alpha-blending two text layers per
            # popup per frame made those moments stutter on phones. Now: rendered on black, black = colour key (RLE),
            # the anti-aliased rim doubles as the dark outline; fading = 4 pre-darkened versions.
            lvl = min(4, max(1, (alpha + 63) // 64))
            key = (ft.text, tuple(ft.color[:3]), lvl)
            txt = _FLOAT_TEXT.get(key)
            if txt is None:
                if len(_FLOAT_TEXT) > 96:
                    _FLOAT_TEXT.clear()
                k = lvl / 4.0
                col = tuple(max(8, int(c * k)) for c in ft.color[:3])
                raw = font.render(ft.text, True, col)
                txt = gfx.cv(pygame.Surface((raw.get_width() + 4, raw.get_height() + 4)))
                txt.fill((0, 0, 0))
                txt.blit(font.render(ft.text, True, (1, 1, 1)), (3, 3))   # near-black drop shadow (opaque)
                txt.blit(raw, (1, 1))
                txt.set_colorkey((0, 0, 0), pygame.RLEACCEL)
                _FLOAT_TEXT[key] = txt
            surface.blit(txt, (int(ft.x - txt.get_width() / 2), int(ft.y - oy)))

    def draw(self, surface, oy=0):
        view_h = surface.get_height()
        for t in self.trails:
            f = max(0.0, t['life'])
            if f <= 0.03:
                continue
            screen_y = t['y'] - oy
            if screen_y < -40 or screen_y > view_h + 40:
                continue
            rad = max(1, int(t['radius'] * (0.3 + 0.7 * f)))
            r, g, b = t['color'][:3]
            col = (int(r * f * 0.6), int(g * f * 0.6), int(b * f * 0.6))
            kind = t.get('kind', 'circle')
            if kind == 'circle':
                pygame.draw.circle(surface, col, (int(t['x']), int(screen_y)), rad)
            else:
                draw_shape(surface, kind, t['x'], screen_y - (0 if kind != 'flame' else (1.0 - f) * 12), max(2, rad * 0.55), col)
        for sw in self.shockwaves:
            if sw.life <= 0.03 or sw.radius < 2:
                continue
            screen_y = sw.y - oy
            if screen_y + sw.radius < 0 or screen_y - sw.radius > view_h:
                continue
            r, g, b = sw.color[:3]
            w = max(1, min(int(sw.width * sw.life), int(sw.radius)))
            pygame.draw.circle(surface, (int(r * sw.life), int(g * sw.life), int(b * sw.life)),
                               (int(sw.x), int(screen_y)), int(sw.radius), w)
        for p in self.particles:
            f = p.life / p.max_life
            if f <= 0.04:
                continue
            py = p.y - oy
            if py < -24 or py > view_h + 24:
                continue
            rad = max(1, int(p.radius * f))
            r, g, b = p.color[:3]
            col = (int(r * f), int(g * f), int(b * f))
            if p.shape == "spark":
                pygame.draw.line(surface, col, (p.x - rad, py), (p.x + rad, py), 2)
                pygame.draw.line(surface, col, (p.x, py - rad), (p.x, py + rad), 2)
            elif p.shape == "circle":
                pygame.draw.circle(surface, col, (int(p.x), int(py)), rad)
            else:
                draw_shape(surface, p.shape, p.x, py, rad, col)
        self.draw_floating_texts(surface, oy)

    def clear(self):
        self.particles.clear()
        self.shockwaves.clear()
        self.trails.clear()
        self.floating_texts.clear()
        self.screen_shake = 0.0
