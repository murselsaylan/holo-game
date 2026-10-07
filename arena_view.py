"""Drawing the arena mode: the fixed map is a normal lm.Level (rendered once) with some decoration, plus what the run
adds on top: radar locks, the storm sweeping a zone and the arrow towards its exit.

The run's hazards (spinners, squeezing walls, laser bars, the radar's laser crosses) live in the level data's lists,
so the campaign's hazard drawing shows them as they come and go. The storm is in that list too (a deadly block), but
it is drawn here as a red hatched field with a glowing front instead of a piston. Decoration never collides: zone
gates, floor emblems and wall lights are only paint.
"""
import math

import pygame

import arena as A
import gfx
import level_manager as lm

SECTOR_LEVEL = 30                 # the arena wears sector 2's look (purple), the climb starts in sector 1's
STORM = (255, 60, 90)


class ArenaLevel(lm.Level):

    def __init__(self, run):
        super().__init__(SECTOR_LEVEL)
        self.run = run
        self.data = run.data
        self.level_title = "ARENA"
        self._render_static()
        self.warm_glows()
        self.rev_hits = {}
        self.loaded = True
        self._hatch = None

    # ---- static: the map plus its decoration -------------------------------------------------------------------
    def _render_static(self):
        super()._render_static()
        fg = self.fg
        pal = self.palette
        acc = pal["accent"]
        faint = tuple(int(c * 0.22) for c in acc)
        soft = tuple(int(c * 0.45) for c in acc)
        x0, x1 = int(A.WALL), int(A.W - A.WALL)
        for z in range(A.ZONES):
            top = int(A.zone_top(z))
            cy = top + int(A.ZONE_H / 2)
            # a floor emblem in the open middle: two rings and four ticks (the two-orb motif)
            pygame.draw.circle(fg, faint, (450, cy), 110, 1)
            for i in range(z + 1):                       # zone number as pips under the ring
                pygame.draw.circle(fg, faint, (450 - 14 * z + 28 * i, cy + 128), 4)
            if z > 0:                                    # the gate between two zones: dashes and wall-side chevrons
                y = int(A.zone_top(z - 1))
                for x in range(x0 + 70, x1 - 70, 36):
                    pygame.draw.line(fg, faint, (x, y), (x + 16, y), 2)
                for x, d in ((x0 + 22, 1), (x1 - 22, -1)):
                    pygame.draw.polygon(fg, soft, [(x, y - 12), (x + d * 18, y), (x, y + 12)], 2)
        # the start pad
        sx, sy = int(A.START[0]), int(A.START[1])
        pygame.draw.circle(fg, soft, (sx, sy), 54, 2)
        pygame.draw.circle(fg, faint, (sx, sy), 70, 1)
        # wall lights (the blinking is drawn per frame, these are their sockets)
        self.lights = []
        for y in range(160, int(A.H) - 160, 150):
            for x in (int(A.WALL / 2), int(A.W - A.WALL / 2)):
                pygame.draw.circle(fg, (24, 20, 36), (x, y), 7)
                self.lights.append((x, y))

    # ---- per frame ---------------------------------------------------------------------------------------------
    def draw(self, arena, t, sim=None, oy=0.0, boost=1.0):
        d = self.data
        walls = d.moving_walls
        storm = walls[-1][:4] if walls and walls[-1][2] == A.W - 2 * A.WALL and walls[-1][4] == 0.0 else None
        if storm is not None:                            # the storm block is drawn here, not as a piston
            d.moving_walls = walls[:-1]
            super().draw(arena, t, sim, oy, boost)
            d.moving_walls = walls
        else:
            super().draw(arena, t, sim, oy, boost)
        oy = int(oy)
        self._draw_lights(arena, t, oy)
        self._draw_pickups(arena, t, oy)
        self._draw_storm(arena, t, oy, storm)
        self._draw_core(arena, t, oy)
        self._draw_locks(arena, t, oy)
        self._draw_exit_arrow(arena, t, oy)

    def _draw_lights(self, arena, t, oy):
        vh = arena.get_height()
        acc = self.palette["accent"]
        for i, (x, y) in enumerate(self.lights):
            yy = y - oy
            if -10 < yy < vh + 10:
                k = 0.5 + 0.5 * math.sin(t * 1.2 + i * 0.9)
                pygame.draw.circle(arena, tuple(int(c * (0.25 + 0.35 * k)) for c in acc), (x, yy), 3)

    CORE_COL = (90, 230, 255)

    def _draw_core(self, arena, t, oy):
        """The energy core to reach next: a turning diamond in two rings; off screen an arrow at the edge points
        to it (its distance written beside)."""
        c = self.run.core
        if c is None:
            return
        vh = arena.get_height()
        x, y, born = c
        cx, cy = int(x), int(y) - oy
        col = self.CORE_COL
        if -60 < cy < vh + 60:
            age = t - born
            if age < 0.5:
                pygame.draw.circle(arena, col, (cx, cy), int(20 + 160 * age), 3)
            lm.add_glow(arena, x, cy, 56, col, 0.6)
            rr = int(A.CORE_R + 10)
            box = pygame.Rect(0, 0, 2 * rr, 2 * rr)
            box.center = (cx, cy)
            a0 = t * 1.2
            for j in range(2):
                pygame.draw.arc(arena, col, box, a0 + j * math.pi, a0 + j * math.pi + 2.0, 2)
            s_ = 17 + 2 * math.sin(t * 3.0)
            a = t * 0.9
            pts = [(cx + math.cos(a + i * math.pi / 2) * s_, cy + math.sin(a + i * math.pi / 2) * s_) for i in range(4)]
            pygame.draw.polygon(arena, (210, 250, 255), pts)
            pygame.draw.polygon(arena, col, pts, 3)
            return
        p = self.run.sim.pivot                          # off screen: an arrow on the edge towards it
        up = cy < 0
        ax = max(70, min(arena.get_width() - 70, cx))
        ay = 60 if up else vh - 60
        d = -1 if up else 1
        pulse = 0.6 + 0.4 * math.sin(t * 7.0)
        colp = tuple(int(c_ * (0.6 + 0.4 * pulse)) for c_ in col)
        pygame.draw.polygon(arena, colp, [(ax - 26, ay - d * 12), (ax, ay + d * 18), (ax + 26, ay - d * 12)])
        pygame.draw.polygon(arena, (210, 250, 255), [(ax - 26, ay - d * 12), (ax, ay + d * 18), (ax + 26, ay - d * 12)], 2)
        dist = int(math.hypot(x - p.x, y - p.y) / 10)
        lab = self._dist_label(dist)
        arena.blit(lab, lab.get_rect(center=(ax, ay - d * 38)))

    def _dist_label(self, n):
        cache = self.__dict__.setdefault("_dist_cache", {})
        img = cache.get(n)
        if img is None:
            import ui
            img = ui.text_surface(f"{n} m", 22, (170, 235, 255), True)
            if len(cache) > 200:
                cache.clear()
            cache[n] = img
        return img

    _PICK_COL = {"grow": (40, 255, 130), "shrink": (90, 200, 255), "boost": (255, 190, 40)}

    def _draw_pickups(self, arena, t, oy):
        """The run's power fields (drawn by the level as zones): a ring opening as one appears and a countdown arc
        that blinks in its last two seconds."""
        vh = arena.get_height()
        for kind, x, y, born, gone in self.run.pickups:
            cy = int(y) - oy
            if cy < -80 or cy > vh + 80:
                continue
            col = self._PICK_COL[kind]
            age, left = t - born, gone - t
            if age < 0.6:
                pygame.draw.circle(arena, col, (int(x), cy), int(30 + 120 * age), 3)
            if left < 2.0 and int(t * 8) % 2:
                continue
            k = max(0.0, min(1.0, left / (gone - born)))
            box = pygame.Rect(0, 0, 84, 84)
            box.center = (int(x), cy)
            pygame.draw.arc(arena, tuple(int(c_ * 0.6) for c_ in col), box, math.pi / 2, math.pi / 2 + 2 * math.pi * k, 2)

    def _hatch_layer(self):
        """Red diagonal stripes as big as a zone (colour keyed, drawn once)."""
        if self._hatch is None:
            w, h = int(A.W - 2 * A.WALL), int(A.ZONE_H)
            surf = pygame.Surface((w, h))
            surf.fill((255, 0, 255))
            for x in range(-h, w, 34):
                pygame.draw.line(surf, (110, 20, 40), (x, h), (x + h, 0), 9)
            surf.set_colorkey((255, 0, 255), pygame.RLEACCEL)
            self._hatch = gfx.cv(surf)
            self._hatch.set_colorkey((255, 0, 255), pygame.RLEACCEL)
        return self._hatch

    def _draw_storm(self, arena, t, oy, storm):
        cl = self.run.closing()
        if cl is None:
            return
        z, phase, up = cl
        top = int(A.zone_top(z))
        x0, w = int(A.WALL), int(A.W - 2 * A.WALL)
        if phase == "warn":                              # the zone flashes before the storm comes in
            if int(t * 6) % 2 == 0:
                pygame.draw.rect(arena, STORM, (x0, top - oy, w, int(A.ZONE_H)), 5)
            return
        if storm is None:
            return
        x, y, _, h = storm
        y, h = int(y), int(h)
        src_y = int(A.ZONE_H) - h if up else 0
        hatch = self._hatch_layer()
        arena.blit(hatch, (x0, y - oy), (0, src_y, w, h))
        fy = y if up else y + h                          # the front, where the storm meets free space
        for k, (col, th) in enumerate((((120, 20, 45), 14), (STORM, 6), ((255, 220, 230), 2))):
            pts = [(xx, fy - oy + int(5 * math.sin(xx * 0.04 + t * 7.0 + k))) for xx in range(x0, x0 + w + 1, 30)]
            pygame.draw.lines(arena, col, False, pts, th)

    def _draw_exit_arrow(self, arena, t, oy):
        ty = self.run.target_y()
        if ty is None:
            return
        cl = self.run.closing()
        if A.zone_of(self.run.sim.pivot.y) != cl[0]:
            return                                       # already out of the storm's zone
        vh = arena.get_height()
        up = cl[2]
        y = 70 if up else vh - 70
        pulse = 0.6 + 0.4 * math.sin(t * 8.0)
        col = (255, int(160 + 80 * pulse), int(90 * pulse))
        d = -1 if up else 1
        for i in range(3):
            yy = y + d * (i * 22 - 22) + d * int(6 * pulse)
            pygame.draw.lines(arena, col, False, [(450 - 40, yy - d * 14), (450, yy + d * 6), (450 + 40, yy - d * 14)], 6)

    def _draw_locks(self, arena, t, oy):
        vh = arena.get_height()
        for x, y, k in self.run.warnings():
            cy = int(y) - oy
            if cy < -200 or cy > vh + 200:
                continue
            cx = int(x)
            k = max(0.0, min(1.0, k))
            blink = 0.75 + 0.25 * math.sin(t * (6.0 + 10.0 * k))
            col = (255, int(190 - 120 * k), int(90 - 50 * k))
            col = tuple(int(c * blink) for c in col)
            r = int(130 - 85 * k)                          # the ring closes in on the spot
            pygame.draw.circle(arena, col, (cx, cy), r, 2)
            pygame.draw.circle(arena, col, (cx, cy), 4)
            arm = int(A.STRIKE_ARM)                         # where the cross will burn: thin dashes
            dim = tuple(int(c * 0.4) for c in col)
            for d in range(-arm, arm, 26):
                pygame.draw.line(arena, dim, (cx + d, cy), (cx + min(arm, d + 10), cy), 1)
                pygame.draw.line(arena, dim, (cx, cy + d), (cx, cy + min(arm, d + 10)), 1)

    def _draw_goal(self, arena, t, oy=0):
        pass                                                # no portal: the arena is about staying alive
