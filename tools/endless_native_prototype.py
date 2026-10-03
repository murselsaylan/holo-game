"""Standalone endless-session experiment built from HOLO's real levels and physics.

No production file is modified. Click/Space swaps pivot, R restarts the run, Esc quits.
"""
from __future__ import annotations

import hashlib
import os
import random
import sys
from pathlib import Path

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from level_manager import Level
from sim import SIM_DT, Sim
from skins import draw_orb, draw_tether, get_skin

VW, VH = 900, 1600
HUD_H = 130
VIEW_H = VH - HUD_H
DW, DH = 540, 960
WORLD_SEED = "HOLO-ENDLESS-NATIVE-S01"
ORDER_VERSION = 1
MAP_ID = hashlib.sha256(f"{WORLD_SEED}|{ORDER_VERSION}".encode()).hexdigest()[:12].upper()

# The opening demonstrates actual route families quickly. Level 9 already contains three backward legs.
OPENING = [1, 9, 31, 39, 36, 67, 65, 81, 61, 99, 12, 29]


def level_for_stage(stage: int) -> int:
    if stage < len(OPENING):
        return OPENING[stage]
    offset = stage - len(OPENING)
    cycle, slot = divmod(offset, 100)
    order = list(range(1, 101))
    random.Random(f"{WORLD_SEED}|cycle:{cycle}").shuffle(order)
    return order[slot]


class NativeEndless:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((DW, DH))
        pygame.display.set_caption("HOLO — Gerçek Bölümlerle Sonsuz Mod")
        self.frame = pygame.Surface((VW, VH)).convert()
        self.clock = pygame.time.Clock()
        fonts = ROOT / "assets/fonts"
        self.font = pygame.font.Font(str(fonts / "Rajdhani-SemiBold.ttf"), 35)
        self.big = pygame.font.Font(str(fonts / "Rajdhani-Bold.ttf"), 58)
        self.small = pygame.font.Font(str(fonts / "Rajdhani-Medium.ttf"), 25)
        self.skin = get_skin("neon_pulse")
        self.stage = 0
        self.completed_distance = 0.0
        self.best_distance = 0.0
        self.dead = False
        self.transition = 0.0
        self.accum = 0.0
        self.load_stage()

    def load_stage(self):
        self.level_id = level_for_stage(self.stage)
        self.level = Level(self.level_id)
        if not self.level.load():
            raise RuntimeError(f"level {self.level_id} could not be loaded")
        self.sim = Sim(self.level.data, record_events=True)
        self.cam_y = self.camera_target()
        self.transition = 1.25

    def camera_target(self):
        h = self.level.height
        if h <= VIEW_H:
            return -(VIEW_H - h) / 2
        cy = (self.sim.pivot.y + self.sim.rotating.y) / 2
        upward = self.level.data.end[1] < self.level.data.start[1]
        top = cy - VIEW_H * (.62 if upward else .38)
        return max(0.0, min(h - VIEW_H, top))

    def restart(self):
        self.stage = 0
        self.completed_distance = self.best_distance = 0.0
        self.dead = False
        self.load_stage()

    def swap(self):
        if self.dead:
            self.restart()
        elif self.transition <= 0:
            self.sim.swap()

    def tick(self):
        if self.dead:
            return
        if self.transition > 0:
            self.transition = max(0.0, self.transition - SIM_DT)
            return
        self.sim.step()
        self.sim.events.clear()
        target = self.camera_target()
        self.cam_y += (target - self.cam_y) * .11
        current = self.level.data.path_total * self.sim.max_progress
        self.best_distance = max(self.best_distance, self.completed_distance + current)
        if self.sim.dead:
            self.dead = True
        elif self.sim.won:
            self.completed_distance += self.level.data.path_total
            self.best_distance = max(self.best_distance, self.completed_distance)
            self.stage += 1
            self.load_stage()

    def draw_hud(self):
        f = self.frame
        pygame.draw.rect(f, (2, 7, 16), (0, 0, VW, HUD_H))
        pal = self.level.palette
        f.blit(self.font.render("SONSUZ ROTA", True, (230, 249, 255)), (28, 16))
        metres = int(self.best_distance / 10)
        f.blit(self.big.render(f"{metres:,} m".replace(",", "."), True, pal["accent"]), (26, 54))
        level_text = self.small.render(
            f"ETAP {self.stage + 1}  •  L{self.level_id} {self.level.level_title}", True, (160, 194, 211))
        f.blit(level_text, (VW - level_text.get_width() - 28, 73))
        ident = self.small.render(f"SEZON 01  •  HARİTA {MAP_ID}", True, (70, 146, 172))
        f.blit(ident, (VW - ident.get_width() - 28, 22))

    def draw(self):
        self.draw_hud()
        view = self.frame.subsurface((0, HUD_H, VW, VIEW_H))
        boost = self.sim.smooth / max(.01, self.level.data.speed)
        self.level.draw(view, self.sim.t, self.sim, self.cam_y, boost)
        p0, p1 = self.sim.orbs
        a = (p0.x, p0.y - self.cam_y)
        b = (p1.x, p1.y - self.cam_y)
        draw_tether(view, a, b, self.skin, self.sim.t)
        draw_orb(view, a, p0.r, self.skin["color1"], self.skin["glow1"], self.sim.piv == 0, self.skin, self.sim.t)
        draw_orb(view, b, p1.r, self.skin["color2"], self.skin["glow2"], self.sim.piv == 1, self.skin, self.sim.t)

        if self.transition > 0:
            alpha = min(220, int(self.transition / 1.25 * 220))
            shade = pygame.Surface((VW, VIEW_H), pygame.SRCALPHA)
            shade.fill((2, 6, 15, alpha))
            view.blit(shade, (0, 0))
            title = self.big.render(f"ETAP {self.stage + 1}", True, self.level.palette["accent"])
            name = self.font.render(f"L{self.level_id}  •  {self.level.level_title}", True, (235, 250, 255))
            view.blit(title, ((VW - title.get_width()) // 2, 565))
            view.blit(name, ((VW - name.get_width()) // 2, 640))

        if self.dead:
            shade = pygame.Surface((VW, VH), pygame.SRCALPHA)
            shade.fill((2, 5, 13, 194))
            self.frame.blit(shade, (0, 0))
            title = self.big.render("YÖRÜNGE KIRILDI", True, (255, 75, 120))
            score = self.font.render(f"{int(self.best_distance / 10)} m  •  {self.stage} ETAP", True, (230, 249, 255))
            retry = self.font.render("YENİDEN BAŞLAMAK İÇİN DOKUN", True, (40, 220, 250))
            self.frame.blit(title, ((VW - title.get_width()) // 2, 650))
            self.frame.blit(score, ((VW - score.get_width()) // 2, 730))
            self.frame.blit(retry, ((VW - retry.get_width()) // 2, 810))

        pygame.transform.smoothscale(self.frame, (DW, DH), self.screen)
        pygame.display.flip()

    def loop(self):
        running = True
        while running:
            self.accum += min(.05, self.clock.tick(60) / 1000)
            for e in pygame.event.get():
                if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
                    running = False
                elif e.type == pygame.KEYDOWN and e.key == pygame.K_r:
                    self.restart()
                elif e.type in (pygame.MOUSEBUTTONDOWN, pygame.FINGERDOWN) or (
                        e.type == pygame.KEYDOWN and e.key in (pygame.K_SPACE, pygame.K_UP)):
                    self.swap()
            while self.accum >= SIM_DT:
                self.tick()
                self.accum -= SIM_DT
            self.draw()
        pygame.quit()


if __name__ == "__main__":
    NativeEndless().loop()
