"""Continuous, portal-free prototype made by stitching real HOLO maps end to end."""
from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import random
import secrets
import sys
from pathlib import Path

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from level_manager import Level
from sim import LevelData, SIM_DT, Sim, circle_rect_hit
from skins import draw_orb, draw_tether, get_skin

VW, VH, HUD_H = 900, 1600, 130
VIEW_H = VH - HUD_H
DW, DH = 540, 960
GAP = 300
# Route shapes are mixed from the beginning. Mechanics are filtered separately
# by stage, so a late-sector chamber or U-turn can appear early without exposing
# its lasers/spinners before their tutorial tier.
GEOMETRY_POOLS = (
    (1, 2, 3, 5, 8, 9, 19, 36, 45, 57),
    (4, 9, 10, 12, 13, 17, 27, 34, 47, 53, 63),
    (6, 8, 14, 16, 20, 27, 36, 43, 45, 57, 84),
    (7, 11, 21, 22, 23, 24, 25, 28, 29, 31, 35, 39, 64, 68),
    (41, 42, 43, 46, 48, 49, 52, 55, 58, 60, 78, 82, 89, 92),
    tuple(range(61, 101)),                       # laser/spinner tier opens
    tuple(range(31, 101)),                       # every unlocked mechanic is mixed
    tuple(range(31, 101)),                       # sustained mixed endgame
)
DEFAULT_SEED = "HOLO-STITCHED-S01"
DEFAULT_STAGES = 24


def map_id(seed=DEFAULT_SEED):
    return hashlib.sha256(f"{seed}|v3".encode()).hexdigest()[:12].upper()


MAP_ID = map_id()


def choose_levels(seed, stages=DEFAULT_STAGES):
    rng = random.Random(seed)
    chosen = []
    for stage in range(stages):
        pool = GEOMETRY_POOLS[min(stage, len(GEOMETRY_POOLS) - 1)]
        options = [level_id for level_id in pool if not chosen or level_id != chosen[-1]]
        chosen.append(rng.choice(options or pool))
    return chosen


def filter_mechanics(raw, stage):
    """Keep route geometry varied while unlocking hazard families gradually."""
    d = copy.deepcopy(raw)
    if stage < 1:
        d["reverse_walls"] = []
        d["moving_walls"] = []
    if stage < 2:
        d["circles"] = []
    if stage < 3:
        barriers = d.get("barriers", [])
        if barriers:
            d["walls"] = [w for w in d.get("walls", []) if not any(
                all(abs(float(a) - float(b)) <= 1 for a, b in zip(w[:4], barrier[:4]))
                for barrier in barriers)]
        d["growth_zones"] = []
        d["breakables"] = []
        d["barriers"] = []
        d["shields"] = []
    if stage < 4:
        d["shrink_zones"] = []
        d["boost_pads"] = []
        d["chasers"] = []
    if stage < 5:
        d["lasers"] = []
        d["spinners"] = []
    return d

RECT_KEYS = ("walls", "reverse_walls", "breakables", "barriers")
POINT_RADIUS_KEYS = ("circles", "growth_zones", "shrink_zones", "boost_pads", "shields", "stars")


def subtract_rect(rect, cut):
    """Subtract an axis-aligned cut from a wall rectangle."""
    x, y, w, h = rect
    cx, cy, cw, ch = cut
    ix0, iy0 = max(x, cx), max(y, cy)
    ix1, iy1 = min(x + w, cx + cw), min(y + h, cy + ch)
    if ix0 >= ix1 or iy0 >= iy1:
        return [rect]
    pieces = []
    if y < iy0:
        pieces.append([x, y, w, iy0 - y])
    if iy1 < y + h:
        pieces.append([x, iy1, w, y + h - iy1])
    if x < ix0:
        pieces.append([x, iy0, ix0 - x, iy1 - iy0])
    if ix1 < x + w:
        pieces.append([ix1, iy0, x + w - ix1, iy1 - iy0])
    return [p for p in pieces if p[2] > 1 and p[3] > 1]


def canonical(raw):
    """Make every source level travel from its lower start toward its upper exit."""
    d = copy.deepcopy(raw)
    h = float(d["height"])
    flip = d["end"][1] > d["start"][1]
    if not flip:
        return d

    def point(p):
        return [p[0], h - p[1], *p[2:]]

    def rect(r):
        return [r[0], h - r[1] - r[3], r[2], r[3], *r[4:]]

    d["start"], d["end"] = point(d["start"]), point(d["end"])
    d["waypoints"] = [point(p) for p in d.get("waypoints", [])]
    for key in RECT_KEYS:
        d[key] = [rect(r) for r in d.get(key, [])]
    for key in POINT_RADIUS_KEYS:
        d[key] = [point(p) for p in d.get(key, [])]
    d["lasers"] = [[l[0], h - l[1], l[2], h - l[3], *l[4:]] for l in d.get("lasers", [])]
    d["spinners"] = [[s[0], h - s[1], s[2], -s[3], *s[4:]] for s in d.get("spinners", [])]
    moving = []
    for m in d.get("moving_walls", []):
        q = rect(m)
        if len(q) > 5:
            q[5] = -q[5]
        moving.append(q)
    d["moving_walls"] = moving
    chasers = []
    for c in d.get("chasers", []):
        q = rect(c)
        if len(q) >= 10:
            q[5] = -q[5]
            q[7] = h - c[7] - c[9]
        chasers.append(q)
    d["chasers"] = chasers
    return d


def shift_point(p, oy):
    return [p[0], p[1] + oy, *p[2:]]


def shift_rect(r, oy):
    return [r[0], r[1] + oy, r[2], r[3], *r[4:]]


def build_stitched(level_ids=None, seed=DEFAULT_SEED):
    level_ids = list(level_ids) if level_ids is not None else choose_levels(seed)
    levels = []
    stage_mechanics = []
    for stage, lid in enumerate(level_ids):
        raw = json.loads((ROOT / f"levels/level{lid}.json").read_text(encoding="utf-8"))
        prepared = canonical(filter_mechanics(raw, stage))
        levels.append(prepared)
        stage_mechanics.append({key: len(prepared.get(key, [])) for key in (
            "reverse_walls", "moving_walls", "circles", "growth_zones", "breakables", "barriers",
            "shields", "shrink_zones", "boost_pads", "chasers", "lasers", "spinners")})
    total_h = sum(float(d["height"]) for d in levels) + GAP * (len(levels) - 1)
    out = {
        "id": 100, "title": "ENDLESS STITCH TEST", "height": total_h,
        "speed": .98, "ramp": .20, "par_time": 9999, "par_swaps": 9999,
        "walls": [], "waypoints": [], "reverse_walls": [], "moving_walls": [],
        "lasers": [], "spinners": [], "circles": [], "growth_zones": [],
        "shrink_zones": [], "boost_pads": [], "shields": [], "stars": [],
        "breakables": [], "chasers": [], "barriers": [], "sector": 5,
        "_seed": seed, "_map_id": map_id(seed), "_return_gates": [], "_source_levels": level_ids,
        "_stage_mechanics": stage_mechanics,
    }
    cursor = total_h
    placements = []
    for idx, d in enumerate(levels):
        h = float(d["height"])
        oy = cursor - h
        cursor = oy - GAP
        placements.append((d, oy))

        # Open a physical tunnel from start/end rooms to the map boundaries.
        sx, sy = d["start"][:2]
        ex, ey = d["end"][:2]
        cuts = []
        if idx > 0:
            cuts.append((sx - 125, sy - 110, 250, h - sy + 120))
        if idx < len(levels) - 1:
            cuts.append((ex - 125, -10, 250, ey + 120))
        walls = d.get("walls", [])
        for cut in cuts:
            walls = [piece for wall in walls for piece in subtract_rect(wall, cut)]

        for key in RECT_KEYS:
            source = walls if key == "walls" else d.get(key, [])
            out[key].extend(shift_rect(v, oy) for v in source)
        for key in POINT_RADIUS_KEYS:
            out[key].extend(shift_point(v, oy) for v in d.get(key, []))
        out["moving_walls"].extend(shift_rect(v, oy) for v in d.get("moving_walls", []))
        out["lasers"].extend([[v[0], v[1] + oy, v[2], v[3] + oy, *v[4:]] for v in d.get("lasers", [])])
        out["spinners"].extend(shift_point(v, oy) for v in d.get("spinners", []))
        out["chasers"].extend(shift_rect(v, oy) for v in d.get("chasers", []))

    # Route order follows play: bottom map first, then each physical connector and the map above it.
    for idx, (d, oy) in enumerate(placements):
        wp = d.get("waypoints") or [d["start"], d["end"]]
        out["waypoints"].extend(shift_point(p, oy)[:2] for p in wp)
        if idx < len(placements) - 1:
            next_d, next_oy = placements[idx + 1]
            ex, ey = d["end"][:2]
            sx, sy = next_d["start"][:2]
            out["waypoints"].extend([[ex, oy - GAP / 2], [sx, next_oy + float(next_d["height"]) + GAP / 2]])

    first, first_oy = placements[0]
    last, last_oy = placements[-1]
    out["start"] = shift_point(first["start"], first_oy)[:2]
    out["end"] = shift_point(last["end"], last_oy)[:2]

    # Safe connector chambers between maps; their side walls keep the pair inside the arena.
    for idx in range(len(placements) - 1):
        upper_edge = placements[idx][1]
        out["walls"].extend([[0, upper_edge - GAP, 45, GAP], [855, upper_edge - GAP, 45, GAP]])
        out["_return_gates"].append([45, upper_edge - GAP / 2 - 14, 810, 28])
    return out


class App:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((DW, DH))
        pygame.display.set_caption("HOLO — Uç Uca Sonsuz Harita Prototipi")
        self.frame = pygame.Surface((VW, VH)).convert()
        self.scaled_frame = pygame.Surface((DW, DH)).convert()
        self.clock = pygame.time.Clock()
        fonts = ROOT / "assets/fonts"
        self.font = pygame.font.Font(str(fonts / "Rajdhani-SemiBold.ttf"), 35)
        self.big = pygame.font.Font(str(fonts / "Rajdhani-Bold.ttf"), 58)
        self.small = pygame.font.Font(str(fonts / "Rajdhani-Medium.ttf"), 25)
        self.skin = get_skin("neon_pulse")
        self.new_world()

    def new_world(self):
        self.seed = secrets.token_hex(8)
        stitched = build_stitched(seed=self.seed)
        self.current_map_id = stitched["_map_id"]
        self.source_levels = list(stitched["_source_levels"])
        self.return_gates = [tuple(r) for r in stitched["_return_gates"]]
        self.level = Level(100)
        self.level.data = LevelData(stitched)
        self.level.level_title = self.level.data.title
        self.level._render_static()
        self.level.warm_glows()
        self.level.loaded = True
        self.reset()

    def reset(self):
        self.sim = Sim(self.level.data, record_events=True)
        self.active_gates = set()
        self.dead = False
        self.accum = 0.0
        self.cam_y = self.camera_target()

    def camera_target(self):
        cy = (self.sim.pivot.y + self.sim.rotating.y) / 2
        return max(0.0, min(self.level.height - VIEW_H, cy - VIEW_H * .62))

    def tick(self):
        if self.dead or self.sim.won:
            return
        self.sim.step()
        self.sim.events.clear()
        progress = self.sim.max_progress
        self.sim.lvl.speed = .90 + .58 * (progress ** .82)
        self.cam_y += (self.camera_target() - self.cam_y) * .11
        for idx, gate in enumerate(self.return_gates):
            gy = gate[1]
            if idx not in self.active_gates and max(o.y for o in self.sim.orbs) < gy - 85:
                self.active_gates.add(idx)
            if idx in self.active_gates and any(circle_rect_hit(o.x, o.y, o.r, *gate) for o in self.sim.orbs):
                self.sim.dead = True
        self.dead = self.sim.dead

    def draw(self):
        pygame.draw.rect(self.frame, (2, 7, 16), (0, 0, VW, HUD_H))
        self.frame.blit(self.font.render("UÇ UCA SONSUZ ROTA", True, (230, 249, 255)), (28, 16))
        metres = int(self.level.data.path_total * self.sim.max_progress / 10)
        self.frame.blit(self.big.render(f"{metres:,} m".replace(",", "."), True, (255, 44, 92)), (26, 54))
        diff = 1 + min(6, int(self.sim.max_progress * 7))
        info = self.small.render(f"ZORLUK {diff}/7  •  GERİ DÖNÜŞ KİLİTLİ  •  {self.current_map_id}", True, (105, 170, 193))
        self.frame.blit(info, (VW - info.get_width() - 28, 77))

        view = self.frame.subsurface((0, HUD_H, VW, VIEW_H))
        self.level.draw(view, self.sim.t, self.sim, self.cam_y, self.sim.smooth / self.level.data.speed)
        for idx in self.active_gates:
            x, y, w, h = self.return_gates[idx]
            sy = int(y - self.cam_y)
            if -50 < sy < VIEW_H + 50:
                rect = pygame.Rect(int(x), sy, int(w), int(h))
                pulse = 175 + int(70 * abs(math.sin(self.sim.t * 6)))
                pygame.draw.rect(view, (8, 30, 48), rect)
                pygame.draw.rect(view, (40, pulse, 255), rect, 4)
                for px in range(rect.left + 12, rect.right, 28):
                    pygame.draw.line(view, (90, 220, 255), (px, rect.top + 4), (px - 10, rect.bottom - 4), 2)
        p0, p1 = self.sim.orbs
        a, b = (p0.x, p0.y - self.cam_y), (p1.x, p1.y - self.cam_y)
        draw_tether(view, a, b, self.skin, self.sim.t)
        draw_orb(view, a, p0.r, self.skin["color1"], self.skin["glow1"], self.sim.piv == 0, self.skin, self.sim.t)
        draw_orb(view, b, p1.r, self.skin["color2"], self.skin["glow2"], self.sim.piv == 1, self.skin, self.sim.t)

        if self.dead or self.sim.won:
            shade = pygame.Surface((VW, VH), pygame.SRCALPHA)
            shade.fill((2, 5, 13, 192))
            self.frame.blit(shade, (0, 0))
            label = "PROTOTİP TAMAMLANDI" if self.sim.won else "YÖRÜNGE KIRILDI"
            col = (70, 240, 170) if self.sim.won else (255, 75, 120)
            title = self.big.render(label, True, col)
            retry = self.font.render("YENİDEN BAŞLAMAK İÇİN DOKUN", True, (40, 220, 250))
            self.frame.blit(title, ((VW - title.get_width()) // 2, 690))
            self.frame.blit(retry, ((VW - retry.get_width()) // 2, 780))
        # Reuse the destination buffer; allocation-free scaling matters on phones.
        pygame.transform.scale(self.frame, (DW, DH), self.scaled_frame)
        self.screen.blit(self.scaled_frame, (0, 0))
        pygame.display.flip()

    def loop(self):
        running = True
        while running:
            self.accum += min(.05, self.clock.tick(60) / 1000)
            for e in pygame.event.get():
                if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
                    running = False
                elif e.type == pygame.KEYDOWN and e.key == pygame.K_r:
                    self.new_world()
                elif e.type in (pygame.MOUSEBUTTONDOWN, pygame.FINGERDOWN) or (
                        e.type == pygame.KEYDOWN and e.key in (pygame.K_SPACE, pygame.K_UP)):
                    if self.dead or self.sim.won:
                        self.new_world()
                    else:
                        self.sim.swap()
            while self.accum >= SIM_DT:
                self.tick()
                self.accum -= SIM_DT
            self.draw()
        pygame.quit()


if __name__ == "__main__":
    App().loop()
