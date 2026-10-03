"""Standalone HOLO endless-mode prototype. It does not modify or import the game client.

Run: python tools/endless_mode_prototype.py
Tap/click/Space: swap pivot. R: restart. Esc: quit.
"""
from __future__ import annotations

import argparse
import hashlib
import math
import os
import random
from dataclasses import dataclass
from pathlib import Path

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame


ROOT = Path(__file__).resolve().parents[1]
WORLD_SEED = "HOLO-ENDLESS-S01"
GENERATOR_VERSION = 1
LOGICAL_W, LOGICAL_H = 540, 960
WORLD_W = 900.0
SCALE = LOGICAL_W / WORLD_W
ROW_H = 150
TETHER = 100.0
ORB_R = 15.0
OMEGA = 3.12
DT = 1.0 / 60.0


def seed_for(*parts: object) -> int:
    text = "|".join(map(str, (WORLD_SEED, GENERATOR_VERSION, *parts)))
    return int.from_bytes(hashlib.sha256(text.encode()).digest()[:8], "big")


def center_at(row: int) -> float:
    """Continuous deterministic center line; no prior chunk state is needed."""
    return 450.0 + 92.0 * math.sin(row * 0.31) + 48.0 * math.sin(row * 0.117 + 1.7)


@dataclass(frozen=True)
class Row:
    index: int
    y: float
    center: float
    width: float
    walls: tuple[tuple[float, float, float, float], ...]
    stars: tuple[tuple[float, float], ...]
    gate: bool


def make_row(index: int) -> Row:
    rng = random.Random(seed_for("row", index))
    y = index * ROW_H
    center = center_at(index)
    difficulty = min(1.0, index / 90.0)
    width = rng.uniform(355.0 - 50.0 * difficulty, 420.0 - 55.0 * difficulty)
    left = max(0.0, center - width / 2)
    right = min(WORLD_W, center + width / 2)
    walls: list[tuple[float, float, float, float]] = []
    if left > 0:
        walls.append((0, y, left, ROW_H + 2))
    if right < WORLD_W:
        walls.append((right, y, WORLD_W - right, ROW_H + 2))

    # Short alternating teeth introduce rhythm but always leave a wide route.
    gate = index >= 5 and rng.random() < 0.30 + 0.18 * difficulty
    if gate:
        tooth_w = rng.uniform(45, 90 + 25 * difficulty)
        tooth_h = rng.uniform(24, 42)
        gy = y + rng.uniform(34, ROW_H - 48)
        if rng.random() < 0.5:
            walls.append((left, gy, tooth_w, tooth_h))
        else:
            walls.append((right - tooth_w, gy, tooth_w, tooth_h))

    stars: list[tuple[float, float]] = []
    if index >= 2 and rng.random() < 0.72:
        sx = rng.uniform(left + 65, right - 65)
        stars.append((sx, y + rng.uniform(36, ROW_H - 36)))
    return Row(index, y, center, width, tuple(walls), tuple(stars), gate)


def map_signature(count: int = 160) -> str:
    # Public map id stays constant however far a player has travelled.
    body = f"{WORLD_SEED}|generator:{GENERATOR_VERSION}".encode()
    return hashlib.sha256(body).hexdigest()[:12].upper()


def circle_rect_hit(cx: float, cy: float, radius: float,
                    rect: tuple[float, float, float, float]) -> bool:
    x, y, w, h = rect
    px = max(x, min(cx, x + w))
    py = max(y, min(cy, y + h))
    return (cx - px) ** 2 + (cy - py) ** 2 < radius ** 2


class EndlessRun:
    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        x = center_at(0)
        self.orbs = [[x, 55.0], [x + TETHER, 55.0]]
        self.pivot = 0
        self.angle = 0.0
        self.dead = False
        self.time = 0.0
        self.swaps = 0
        self.max_y = 55.0
        self.camera_y = 0.0
        self.stars = 0
        self.taken: set[tuple[int, int]] = set()
        self.flash = 0.0

    def swap(self) -> None:
        if self.dead:
            return
        self.pivot = 1 - self.pivot
        self.angle = (self.angle + math.pi) % (2 * math.pi)
        self.swaps += 1

    def step(self) -> None:
        if self.dead:
            self.flash = max(0.0, self.flash - DT)
            return
        self.time += DT
        difficulty = min(1.0, self.max_y / 14000.0)
        self.angle = (self.angle + OMEGA * (1.0 + 0.24 * difficulty) * DT) % (2 * math.pi)
        p = self.orbs[self.pivot]
        r = self.orbs[1 - self.pivot]
        r[0] = p[0] + math.cos(self.angle) * TETHER
        r[1] = p[1] + math.sin(self.angle) * TETHER
        self.max_y = max(self.max_y, p[1], r[1])
        target_cam = max(0.0, self.max_y - 520.0)
        self.camera_y += (target_cam - self.camera_y) * 0.075

        lo = max(0, int((min(p[1], r[1]) - 100) // ROW_H))
        hi = int((max(p[1], r[1]) + 100) // ROW_H) + 1
        for row_index in range(lo, hi + 1):
            row = make_row(row_index)
            for rect in row.walls:
                if circle_rect_hit(p[0], p[1], ORB_R, rect) or circle_rect_hit(r[0], r[1], ORB_R, rect):
                    self.dead = True
                    self.flash = 0.28
                    return
            for star_index, (sx, sy) in enumerate(row.stars):
                key = (row_index, star_index)
                if key not in self.taken and any((o[0] - sx) ** 2 + (o[1] - sy) ** 2 < 34 ** 2 for o in self.orbs):
                    self.taken.add(key)
                    self.stars += 1

    @property
    def metres(self) -> int:
        return max(0, int((self.max_y - 55.0) / 10.0))


class App:
    def __init__(self, screenshot: Path | None = None) -> None:
        pygame.init()
        self.screen = pygame.display.set_mode((LOGICAL_W, LOGICAL_H))
        pygame.display.set_caption("HOLO — Sonsuz Mod Prototipi")
        self.clock = pygame.time.Clock()
        self.run = EndlessRun()
        self.font = pygame.font.Font(str(ROOT / "assets/fonts/Rajdhani-SemiBold.ttf"), 25)
        self.big = pygame.font.Font(str(ROOT / "assets/fonts/Rajdhani-Bold.ttf"), 48)
        self.small = pygame.font.Font(str(ROOT / "assets/fonts/Rajdhani-Medium.ttf"), 17)
        self.screenshot = screenshot

    def world_to_screen(self, x: float, y: float) -> tuple[int, int]:
        return int(x * SCALE), int(LOGICAL_H * 0.76 - (y - self.run.camera_y) * SCALE)

    def draw(self) -> None:
        surf = self.screen
        surf.fill((3, 7, 17))
        for gy in range(0, LOGICAL_H, 48):
            pygame.draw.line(surf, (8, 23, 38), (0, gy), (LOGICAL_W, gy), 1)
        for gx in range(0, LOGICAL_W, 54):
            pygame.draw.line(surf, (6, 18, 31), (gx, 0), (gx, LOGICAL_H), 1)

        bottom = max(0, int((self.run.camera_y - 500) // ROW_H))
        top = int((self.run.camera_y + 1700) // ROW_H) + 1
        for row_index in range(bottom, top + 1):
            row = make_row(row_index)
            for x, y, w, h in row.walls:
                rx, ry = self.world_to_screen(x, y + h)
                rect = pygame.Rect(rx, ry, max(1, int(w * SCALE)), max(1, int(h * SCALE)))
                pygame.draw.rect(surf, (13, 29, 48), rect)
                pygame.draw.rect(surf, (0, 142, 190), rect, 1)
            for star_index, (sx, sy) in enumerate(row.stars):
                if (row_index, star_index) in self.run.taken:
                    continue
                px, py = self.world_to_screen(sx, sy)
                pygame.draw.circle(surf, (95, 72, 12), (px, py), 10)
                pygame.draw.circle(surf, (255, 228, 86), (px, py), 5)

        a = self.world_to_screen(*self.run.orbs[0])
        b = self.world_to_screen(*self.run.orbs[1])
        pygame.draw.line(surf, (33, 125, 155), a, b, 3)
        for pos, color in ((a, (44, 233, 255)), (b, (255, 78, 159))):
            pygame.draw.circle(surf, tuple(c // 5 for c in color), pos, 18)
            pygame.draw.circle(surf, color, pos, 10)
            pygame.draw.circle(surf, (244, 253, 255), pos, 4)

        pygame.draw.rect(surf, (2, 8, 18), (0, 0, LOGICAL_W, 112))
        title = self.font.render("SONSUZ YÖRÜNGE", True, (225, 247, 255))
        surf.blit(title, (22, 16))
        dist = self.big.render(f"{self.run.metres:,} m".replace(",", "."), True, (35, 222, 255))
        surf.blit(dist, (20, 45))
        right = self.small.render(f"YILDIZ  {self.run.stars}   •   HAMLE  {self.run.swaps}", True, (142, 179, 197))
        surf.blit(right, (LOGICAL_W - right.get_width() - 18, 73))
        seed = self.small.render(f"SEZON 01  •  HARİTA {map_signature(32)}", True, (61, 139, 166))
        surf.blit(seed, (LOGICAL_W - seed.get_width() - 18, 19))

        if self.run.dead:
            veil = pygame.Surface((LOGICAL_W, LOGICAL_H), pygame.SRCALPHA)
            veil.fill((2, 5, 13, 185))
            surf.blit(veil, (0, 0))
            msg = self.big.render("YÖRÜNGE KIRILDI", True, (255, 84, 127))
            surf.blit(msg, ((LOGICAL_W - msg.get_width()) // 2, 368))
            score = self.font.render(f"MESAFE  {self.run.metres} m   •   YILDIZ  {self.run.stars}", True, (225, 247, 255))
            surf.blit(score, ((LOGICAL_W - score.get_width()) // 2, 432))
            retry = self.font.render("TEKRAR DENEMEK İÇİN DOKUN", True, (42, 218, 248))
            surf.blit(retry, ((LOGICAL_W - retry.get_width()) // 2, 490))
        pygame.display.flip()

    def loop(self, max_frames: int = 0) -> None:
        running, accumulator, frames = True, 0.0, 0
        while running:
            frame_dt = min(0.05, self.clock.tick(60) / 1000.0)
            accumulator += frame_dt
            for event in pygame.event.get():
                if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                    running = False
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_r:
                    self.run.reset()
                elif event.type in (pygame.MOUSEBUTTONDOWN, pygame.FINGERDOWN) or (
                        event.type == pygame.KEYDOWN and event.key in (pygame.K_SPACE, pygame.K_UP)):
                    self.run.reset() if self.run.dead else self.run.swap()
            while accumulator >= DT:
                self.run.step()
                accumulator -= DT
            self.draw()
            frames += 1
            if max_frames and frames >= max_frames:
                if self.screenshot:
                    self.screenshot.parent.mkdir(parents=True, exist_ok=True)
                    pygame.image.save(self.screen, self.screenshot)
                running = False
        pygame.quit()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frames", type=int, default=0)
    parser.add_argument("--screenshot", type=Path)
    args = parser.parse_args()
    App(args.screenshot).loop(args.frames)


if __name__ == "__main__":
    main()
