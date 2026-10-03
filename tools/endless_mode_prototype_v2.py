"""Standalone HOLO endless-world prototype with multi-direction routes.

This file is intentionally isolated from holo.py and the shipped level files.
Click/Space swaps the pivot. R restarts. Esc quits.
"""
from __future__ import annotations

import hashlib
import math
import os
import random
from dataclasses import dataclass
from pathlib import Path

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame

ROOT = Path(__file__).resolve().parents[1]
W, H = 540, 960
FPS = 60
DT = 1 / FPS
TETHER = 100.0
ORB_R = 15.0
WORLD_SEED = "HOLO-ENDLESS-S01"
GENERATOR_VERSION = 2
MAP_ID = hashlib.sha256(f"{WORLD_SEED}|{GENERATOR_VERSION}".encode()).hexdigest()[:12].upper()
KINDS = ("ORBITAL", "WANDER", "U-DÖNÜŞÜ", "ODALAR", "ARENA")


def point_segment_distance(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    ll = dx * dx + dy * dy
    if ll == 0:
        return math.hypot(px - ax, py - ay), 0.0
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / ll))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy)), t


@dataclass(frozen=True)
class Segment:
    a: tuple[float, float]
    b: tuple[float, float]
    width: float
    start_distance: float
    kind: str
    color: tuple[int, int, int]

    @property
    def length(self):
        return math.dist(self.a, self.b)


@dataclass(frozen=True)
class Pickup:
    x: float
    y: float
    distance: float


class World:
    COLORS = ((0, 205, 255), (218, 75, 255), (47, 235, 151), (255, 133, 37), (255, 50, 91))

    def __init__(self):
        self.segments: list[Segment] = []
        self.pickups: list[Pickup] = []
        self.end = (0.0, 0.0)
        self.total = 0.0
        self.motif_count = 0
        self.extend(18)

    def _motif_points(self, index: int, start: tuple[float, float]):
        rng = random.Random(int.from_bytes(hashlib.sha256(f"{WORLD_SEED}|v{GENERATOR_VERSION}|{index}".encode()).digest()[:8], "big"))
        x, y = start
        kind = KINDS[index % len(KINDS)]
        side = -1 if rng.random() < .5 else 1
        if kind == "ORBITAL":
            points = [(x, y), (x + side * rng.randint(80, 170), y + 420), (x, y + 900)]
        elif kind == "WANDER":
            points = [(x, y), (x + side * 250, y + 230), (x - side * 190, y + 470),
                      (x + side * 230, y + 720), (x, y + 980)]
        elif kind == "U-DÖNÜŞÜ":
            # The centre line genuinely travels up, back down, sideways and up again.
            points = [(x, y), (x + side * 250, y + 180), (x + side * 250, y + 850),
                      (x - side * 250, y + 850), (x - side * 250, y + 300),
                      (x - side * 500, y + 300), (x - side * 500, y + 1050)]
        elif kind == "ODALAR":
            points = [(x, y), (x, y + 220), (x + side * 310, y + 220),
                      (x + side * 310, y + 590), (x - side * 80, y + 590),
                      (x - side * 80, y + 970)]
        else:  # arena: a wide open detour with a narrowing exit
            points = [(x, y), (x + side * 330, y + 250), (x + side * 330, y + 620),
                      (x - side * 300, y + 620), (x - side * 300, y + 900), (x, y + 1120)]
        return kind, points

    def extend(self, motifs=8):
        for index in range(self.motif_count, self.motif_count + motifs):
            kind, points = self._motif_points(index, self.end)
            color = self.COLORS[index % len(self.COLORS)]
            rng = random.Random(index * 9199 + 71)
            base_width = 330 - min(52, index * 1.1)
            for a, b in zip(points, points[1:]):
                width = base_width + (75 if kind == "ARENA" else rng.uniform(-18, 18))
                seg = Segment(a, b, width, self.total, kind, color)
                self.segments.append(seg)
                if seg.length > 250:
                    for f in (.34, .68):
                        if rng.random() < .72:
                            px = a[0] + (b[0] - a[0]) * f
                            py = a[1] + (b[1] - a[1]) * f
                            self.pickups.append(Pickup(px, py, self.total + seg.length * f))
                self.total += seg.length
            self.end = points[-1]
        self.motif_count += motifs

    def nearest(self, x, y):
        best = (1e9, 0.0, None)
        # A prototype-friendly scan; only several dozen segments exist near the player.
        for seg in self.segments:
            d, t = point_segment_distance(x, y, *seg.a, *seg.b)
            if d < best[0]:
                best = (d, seg.start_distance + seg.length * t, seg)
        return best

    def ensure_ahead(self, distance):
        if self.total - distance < 7000:
            self.extend(8)


class Run:
    def __init__(self, world: World):
        self.world = world
        self.reset()

    def reset(self):
        self.orbs = [[0.0, 40.0], [TETHER, 40.0]]
        self.pivot = 0
        self.angle = 0.0
        self.time = self.distance = self.best_distance = 0.0
        self.camera = [0.0, 40.0]
        self.dead = False
        self.swaps = self.stars = 0
        self.taken: set[int] = set()

    def swap(self):
        if self.dead:
            self.reset()
            return
        self.pivot = 1 - self.pivot
        self.angle = (self.angle + math.pi) % math.tau
        self.swaps += 1

    def step(self):
        if self.dead:
            return
        self.time += DT
        speed = 1.0 + min(.32, self.best_distance / 50000)
        self.angle = (self.angle + 3.12 * speed * DT) % math.tau
        p = self.orbs[self.pivot]
        r = self.orbs[1 - self.pivot]
        r[0] = p[0] + math.cos(self.angle) * TETHER
        r[1] = p[1] + math.sin(self.angle) * TETHER

        d0, prog0, seg0 = self.world.nearest(*self.orbs[0])
        d1, prog1, seg1 = self.world.nearest(*self.orbs[1])
        self.distance = max(prog0, prog1)
        self.best_distance = max(self.best_distance, self.distance)
        self.world.ensure_ahead(self.best_distance)
        if d0 > seg0.width / 2 - ORB_R or d1 > seg1.width / 2 - ORB_R:
            self.dead = True

        for i, item in enumerate(self.world.pickups):
            if i not in self.taken and abs(item.distance - self.distance) < 280:
                if any(math.hypot(o[0] - item.x, o[1] - item.y) < 33 for o in self.orbs):
                    self.taken.add(i)
                    self.stars += 1

        midx = (self.orbs[0][0] + self.orbs[1][0]) / 2
        midy = (self.orbs[0][1] + self.orbs[1][1]) / 2
        self.camera[0] += (midx - self.camera[0]) * .08
        self.camera[1] += (midy - self.camera[1]) * .08


class App:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((W, H))
        pygame.display.set_caption("HOLO — Sonsuz Dünya v2")
        self.clock = pygame.time.Clock()
        self.world = World()
        self.run = Run(self.world)
        fp = ROOT / "assets/fonts"
        self.f_title = pygame.font.Font(str(fp / "Rajdhani-SemiBold.ttf"), 25)
        self.f_big = pygame.font.Font(str(fp / "Rajdhani-Bold.ttf"), 46)
        self.f_small = pygame.font.Font(str(fp / "Rajdhani-Medium.ttf"), 17)
        self.scale = .54

    def screen_pos(self, p):
        dx = (p[0] - self.run.camera[0]) * self.scale
        dy = (p[1] - self.run.camera[1]) * self.scale
        return int(W / 2 + dx), int(H * .62 - dy)

    def visible(self, a, b, margin=220):
        aa, bb = self.screen_pos(a), self.screen_pos(b)
        return not (max(aa[0], bb[0]) < -margin or min(aa[0], bb[0]) > W + margin or
                    max(aa[1], bb[1]) < -margin or min(aa[1], bb[1]) > H + margin)

    def draw(self):
        s = self.screen
        s.fill((13, 29, 48))
        # Corridors are cut through the wall mass; layered lines create the same neon-edged language as HOLO.
        current_kind = "ORBITAL"
        current_color = (0, 205, 255)
        for seg in self.world.segments:
            if not self.visible(seg.a, seg.b):
                continue
            a, b = self.screen_pos(seg.a), self.screen_pos(seg.b)
            width = int(seg.width * self.scale)
            pygame.draw.line(s, tuple(c // 5 for c in seg.color), a, b, width + 10)
            pygame.draw.line(s, seg.color, a, b, width + 3)
            pygame.draw.line(s, (3, 8, 18), a, b, width)
            pygame.draw.circle(s, (3, 8, 18), a, width // 2)
            pygame.draw.circle(s, (3, 8, 18), b, width // 2)
            if seg.start_distance <= self.run.distance <= seg.start_distance + seg.length:
                current_kind, current_color = seg.kind, seg.color

        for i, item in enumerate(self.world.pickups):
            if i in self.run.taken:
                continue
            x, y = self.screen_pos((item.x, item.y))
            if -20 < x < W + 20 and 90 < y < H + 20:
                pygame.draw.circle(s, (91, 67, 8), (x, y), 11)
                pygame.draw.circle(s, (255, 229, 76), (x, y), 5)

        a, b = [self.screen_pos(o) for o in self.run.orbs]
        pygame.draw.line(s, (30, 116, 145), a, b, 3)
        for pos, col in ((a, (38, 229, 255)), (b, (255, 70, 151))):
            pygame.draw.circle(s, tuple(c // 5 for c in col), pos, 18)
            pygame.draw.circle(s, col, pos, 10)
            pygame.draw.circle(s, (245, 254, 255), pos, 4)

        pygame.draw.rect(s, (2, 7, 16), (0, 0, W, 116))
        s.blit(self.f_title.render("SONSUZ DÜNYA", True, (230, 249, 255)), (20, 14))
        metres = int(self.run.best_distance / 10)
        s.blit(self.f_big.render(f"{metres:,} m".replace(",", "."), True, current_color), (18, 46))
        info = self.f_small.render(f"{current_kind}   •   YILDIZ {self.run.stars}   •   HAMLE {self.run.swaps}", True, (152, 187, 204))
        s.blit(info, (W - info.get_width() - 15, 79))
        ident = self.f_small.render(f"SEZON 01  •  {MAP_ID}", True, (63, 144, 170))
        s.blit(ident, (W - ident.get_width() - 15, 17))

        if self.run.dead:
            veil = pygame.Surface((W, H), pygame.SRCALPHA)
            veil.fill((2, 5, 13, 190))
            s.blit(veil, (0, 0))
            title = self.f_big.render("YÖRÜNGE KIRILDI", True, (255, 78, 121))
            s.blit(title, ((W - title.get_width()) // 2, 370))
            text = self.f_title.render(f"{metres} m  •  {self.run.stars} YILDIZ", True, (230, 249, 255))
            s.blit(text, ((W - text.get_width()) // 2, 435))
            tap = self.f_title.render("YENİDEN BAŞLAMAK İÇİN DOKUN", True, (38, 218, 248))
            s.blit(tap, ((W - tap.get_width()) // 2, 493))
        pygame.display.flip()

    def loop(self):
        accumulator = 0.0
        running = True
        while running:
            accumulator += min(.05, self.clock.tick(FPS) / 1000)
            for e in pygame.event.get():
                if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
                    running = False
                elif e.type == pygame.KEYDOWN and e.key == pygame.K_r:
                    self.run.reset()
                elif e.type in (pygame.MOUSEBUTTONDOWN, pygame.FINGERDOWN) or (
                        e.type == pygame.KEYDOWN and e.key in (pygame.K_SPACE, pygame.K_UP)):
                    self.run.swap()
            while accumulator >= DT:
                self.run.step()
                accumulator -= DT
            self.draw()
        pygame.quit()


if __name__ == "__main__":
    App().loop()
