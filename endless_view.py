"""Drawing the endless climb.

A campaign level renders its whole map into one surface when it loads. The endless world never ends, so each stage
is rendered into 128 px bands by a generator that the game advances a millisecond or two per frame (pump) while the
player is still one or two stages below - no frame ever pays for a whole map. Wall outlines are traced from the
rectangles themselves (no pixel masks), wall surfaces use one texture tile per sector. The climb passes through the
campaign's five sectors in order; each sector's backdrop and wall texture are made once, in a background thread,
well before the climb reaches them. A band that is not ready yet (only after a very fast climb) is drawn as plain
walls, so the picture is never wrong.
"""
import math
import random
import threading
import time

import pygame

import endless as E
import level_manager as lm
import space_art

W = int(lm.W_I)
BAND = 128
TEX_H = 1024
FAR_H = 1900
KEY = (255, 0, 255)
_TIER_SECTOR = (1, 1, 2, 2, 3, 3, 4, 5)


def sector_for_stage(k):
    return _TIER_SECTOR[E.tier_of(k)]


class _SectorArt:
    """Backdrop (+ its mirror, so it tiles without a seam) and wall texture of one sector, made in a thread."""

    def __init__(self, sector, sync=False):
        self.sector = sector
        self._raw = None
        self.far = self.far_flip = self.tex = None
        if sync:
            self._make()
        else:
            threading.Thread(target=self._make, daemon=True).start()

    def _make(self):
        far = space_art.make_far_layer(self.sector, 700 + self.sector, W, FAR_H)
        time.sleep(0)
        tex = space_art.make_wall_texture(self.sector, W, TEX_H, 900 + self.sector)
        self._raw = (far, pygame.transform.flip(far, False, True), tex)

    def ready(self):
        """True once usable; converts one image to the display format per call (a few ms each on a phone)."""
        if self.far is None and self._raw is not None:
            raw = self._raw
            if self.tex is None:
                self.tex = raw[2].convert()
            elif self.far_flip is None:
                self.far_flip = raw[1].convert()
            else:
                self.far = raw[0].convert()
                self._raw = None
        return self.far is not None


def _outline(walls, h, out):
    """(generator) Appends to `out` the boundary segments of the union of axis-aligned rects (x, y, w, h) inside [0, W] x [0, h]:
    ('v', x, y0, y1) / ('h', y, x0, x1). The arena edges themselves are not outlined (like the campaign maps)."""
    xs = sorted({0, W} | {max(0, min(W, x)) for (x, y, w, hh) in walls} | {max(0, min(W, x + w)) for (x, y, w, hh) in walls})
    ys = sorted({0, h} | {max(0, min(h, y)) for (x, y, w, hh) in walls} | {max(0, min(h, y + hh)) for (x, y, w, hh) in walls})
    xi = {v: i for i, v in enumerate(xs)}
    yi = {v: j for j, v in enumerate(ys)}
    nx, ny = len(xs) - 1, len(ys) - 1
    grid = [bytearray(nx) for _ in range(ny)]
    yield
    for n, (x, y, w, hh) in enumerate(walls):
        x0, x1 = xi[max(0, min(W, x))], xi[max(0, min(W, x + w))]
        y0, y1 = yi[max(0, min(h, y))], yi[max(0, min(h, y + hh))]
        for j in range(y0, y1):
            grid[j][x0:x1] = b"" * (x1 - x0)
        if n % 16 == 15:
            yield
    segs = out
    for i in range(1, nx):
        if i % 12 == 0:
            yield                           # vertical boundaries (interior grid lines only)
        run = None
        for j in range(ny):
            edge = grid[j][i - 1] != grid[j][i]
            if edge and run is None:
                run = ys[j]
            elif not edge and run is not None:
                segs.append(("v", xs[i], run, ys[j]))
                run = None
        if run is not None:
            segs.append(("v", xs[i], run, ys[ny]))
    for j in range(1, ny):                           # horizontal boundaries
        if j % 12 == 0:
            yield
        run = None
        a, b = grid[j - 1], grid[j]
        for i in range(nx):
            edge = a[i] != b[i]
            if edge and run is None:
                run = xs[i]
            elif not edge and run is not None:
                segs.append(("h", ys[j], run, xs[i]))
                run = None
        if run is not None:
            segs.append(("h", ys[j], run, xs[nx]))


class EndlessLevel(lm.Level):
    """lm.Level for an EndlessRun: same hazard drawing, streamed static layers."""

    def __init__(self, run):
        super().__init__(1)
        self.run = run
        self.data = run.sim.lvl
        self.loaded = True
        self.level_title = ""
        self.rev_hits = {}
        self.bands = {}                  # (stage, band) -> surface
        self.jobs = {}                   # stage -> generator
        self.done = set()
        self.arts = {}
        self._dummy = pygame.Surface((1, 1))
        self._fade = None                # (old art, started at) while the backdrop crossfades to a new sector
        self._shown_sector = sector_for_stage(0)
        self._art(self._shown_sector, sync=True)
        self._art(sector_for_stage(4))   # next sector, early
        rng = random.Random(4242)
        self.far_h = FAR_H * 2
        self.twinkles = [(rng.randrange(20, W - 20), rng.randrange(0, self.far_h), rng.uniform(0, 6.28)) for _ in range(60)]
        self.dust = [(rng.randrange(10, W - 10), rng.random(), rng.random()) for _ in range(40)]
        self.rocks = [(rng.uniform(0, W + 160), rng.uniform(0, 5200), rng.uniform(14, 46), rng.uniform(-0.8, 0.8),
                       rng.uniform(6, 26), space_art.make_rock_shape(rng)) for _ in range(14)]
        self._set_sector(self._shown_sector)

    # ---- resources ---------------------------------------------------------------------------------------------
    def _art(self, sector, sync=False):
        a = self.arts.get(sector)
        if a is None:
            a = self.arts[sector] = _SectorArt(sector, sync)
        return a

    def _set_sector(self, sector):
        self.sector = sector
        self.palette = lm.PALETTES[sector]
        th = space_art.THEMES[sector]
        self.rock_col = (space_art._scale(th["wall2"], 1.05), space_art._scale(th["accent"], 0.5))

    def prepare(self, upto):
        """Queue the static layers of every window stage up to `upto`; forget stages two below the window."""
        w0 = self.run.w0
        for k in range(w0, upto + 1):
            if k not in self.done and k not in self.jobs:
                self.jobs[k] = self._render_stage(k)
        for key in [key for key in self.bands if key[0] < w0 - 1]:
            del self.bands[key]
        self.done = {k for k in self.done if k >= w0 - 1}
        nxt = sector_for_stage(w0 + E.WINDOW + 1)
        if nxt not in self.arts:
            self._art(nxt)
        for s in [s for s in self.arts if s not in (self.sector, nxt, sector_for_stage(w0))]:
            if self._fade is None or self._fade[0] is not self.arts[s]:
                del self.arts[s]

    def pump(self, budget_s):
        """Advance the render jobs (nearest stage first) for about `budget_s` seconds."""
        if not self.jobs:
            return
        end = time.perf_counter() + budget_s
        for k in sorted(self.jobs):
            job = self.jobs[k]
            while time.perf_counter() < end:
                try:
                    next(job)
                except StopIteration:
                    del self.jobs[k]
                    self.done.add(k)
                    break
            if time.perf_counter() >= end:
                return

    def finish(self, upto):
        """Loading screen: everything up to stage `upto`, now."""
        self.prepare(upto)
        while self.jobs:
            self.pump(1.0)

    # ---- stage rendering (generator) ---------------------------------------------------------------------------
    def _render_stage(self, k):
        world = self.run.world
        st = world.stage(k)
        sector = sector_for_stage(k)
        art = self._art(sector)
        while not art.ready():
            yield
        tex = art.tex
        pal = lm.PALETTES[sector]
        top = st.top
        h = int(round(st.height))
        walls = [(int(round(x)), int(round(y - top)), int(round(w)), int(round(hh))) for (x, y, w, hh) in st.d["walls"]]
        yield
        segs = []
        yield from _outline(walls, h, segs)
        yield
        border, accent = pal["border"], pal["accent"]
        dim1 = tuple(int(c * 0.28) for c in border)
        dim2 = tuple(int(c * 0.62) for c in border)
        styles = ((8, dim1), (5, dim2), (2, border), (1, accent))
        tex_off = (k * 389) % TEX_H
        for b in range((h + BAND - 1) // BAND):
            y0 = b * BAND
            bh = min(BAND, h - y0)
            disp = pygame.display.get_surface()
            surf = pygame.Surface((W, bh), 0, disp) if disp is not None else pygame.Surface((W, bh))
            surf.fill(KEY)
            n = 0
            for (x, y, w, hh) in walls:
                a, z = max(y, y0), min(y + hh, y0 + bh)
                if a >= z or w <= 0:
                    continue
                yy = a
                while yy < z:                                  # the texture tile repeats every TEX_H px
                    ty = (yy + tex_off) % TEX_H
                    part = min(z - yy, TEX_H - ty)
                    surf.blit(tex, (x, yy - y0), (x, ty, w, part))
                    yy += part
                n += 1
                if n % 3 == 0:
                    yield
            yield
            for width, col in styles:
                half = width // 2 + 1
                n = 0
                for s in segs:
                    if s[0] == "v":
                        _, x, a, z = s
                        if z < y0 - half or a > y0 + bh + half:
                            continue
                        pygame.draw.line(surf, col, (x, a - y0), (x, z - y0), width)
                        if width > 2:
                            pygame.draw.rect(surf, col, (x - width // 2, a - y0 - width // 2, width, width))
                            pygame.draw.rect(surf, col, (x - width // 2, z - y0 - width // 2, width, width))
                    else:
                        _, y, a, z = s
                        if y < y0 - half or y > y0 + bh + half:
                            continue
                        pygame.draw.line(surf, col, (a, y - y0), (z, y - y0), width)
                    n += 1
                    if n % 16 == 0:
                        yield
                yield
            for m in st.d["moving_walls"]:                   # rails
                x, y, w, hh = m[0], m[1] - top - y0, m[2], m[3]
                if -200 < y < bh + 200:
                    if m[4] > 0:
                        pygame.draw.line(surf, (90, 58, 40), (x - m[4], y + hh / 2), (x + w + m[4], y + hh / 2), 3)
                    if m[5] > 0:
                        pygame.draw.line(surf, (90, 58, 40), (x + w / 2, y - m[5]), (x + w / 2, y + hh + m[5]), 3)
            for l in st.d["lasers"]:
                for (px, py) in ((l[0], l[1]), (l[2], l[3])):
                    py -= top + y0
                    if -20 < py < bh + 20:
                        pygame.draw.circle(surf, (60, 64, 80), (int(px), int(py)), 11)
                        pygame.draw.circle(surf, (150, 40, 70), (int(px), int(py)), 7)
            for s_ in st.d["spinners"]:
                py = s_[1] - top - y0
                if -20 < py < bh + 20:
                    pygame.draw.circle(surf, (60, 64, 80), (int(s_[0]), int(py)), 14)
                    pygame.draw.circle(surf, (150, 40, 90), (int(s_[0]), int(py)), 9)
            yield
            surf.set_colorkey(KEY, pygame.RLEACCEL)
            self._dummy.blit(surf, (0, 0), (0, 0, 1, 1))       # RLE-encode now, not at its first real blit
            self.bands[(k, b)] = surf
            yield

    # ---- drawing -----------------------------------------------------------------------------------------------
    def draw(self, arena, t, sim=None, oy=0.0, boost=1.0):
        run = self.run
        self.data = run.sim.lvl
        vh = arena.get_height()
        oy = int(oy)
        k_now = run.stage_at(oy + vh * 0.5)
        want = sector_for_stage(k_now)
        if want != self._shown_sector and self._art(want).ready():
            self._fade = (self.arts.get(self._shown_sector), time.perf_counter())
            self._shown_sector = want
            self._set_sector(want)
        art = self._art(self._shown_sector)
        far_y = int(oy * 0.3)
        self._blit_far(arena, art, far_y, vh, None)
        if self._fade is not None:
            old, t0 = self._fade
            k = 1.0 - (time.perf_counter() - t0) / 1.2
            if k <= 0.0 or old is None or not old.ready():
                self._fade = None
            else:
                self._blit_far(arena, old, far_y, vh, int(255 * k))
        self._draw_space_life(arena, t, vh, far_y % self.far_h, boost)
        pal = self.palette
        for k in range(run.w0, run.w0 + E.WINDOW):
            st = run.world.stage(k)
            if st.bottom < oy - 10 or st.top - E.GAP > oy + vh + 10:
                continue
            cy = st.top - E.GAP - oy                             # connector chamber above this stage
            if cy + E.GAP > -10 and cy < vh + 10 and k < run.w0 + E.WINDOW - 1:
                self._draw_connector(arena, int(cy), lm.PALETTES[sector_for_stage(k + 1)])
            for b in range((int(round(st.height)) + BAND - 1) // BAND):
                y = int(round(st.top)) + b * BAND - oy
                if y + BAND < 0 or y > vh:
                    continue
                surf = self.bands.get((k, b))
                if surf is not None:
                    arena.blit(surf, (0, y))
                else:
                    self._draw_plain(arena, st, k, oy, y, min(BAND, int(round(st.height)) - b * BAND))
        self._draw_marks(arena, oy, vh)
        self._draw_dynamic(arena, t, sim, oy)

    def _mark_label(self, text, color):
        cache = self.__dict__.setdefault("_labels", {})
        s = cache.get((text, color))
        if s is None:
            import ui
            s = cache[(text, color)] = ui.text_surface(text, 22, color, bold=True, bg="key")
        return s

    def _draw_marks(self, arena, oy, vh):
        """Every 100 m a faint height line, every diamond height a cyan one with a gem, the player's record in gold."""
        run = self.run
        sy = run.start_y
        top_m = int((sy - oy) / E.PX_PER_M) + 1
        bot_m = max(1, int((sy - (oy + vh)) / E.PX_PER_M))
        for m in range((bot_m + 99) // 100 * 100, top_m + 1, 100):
            y = int(sy - m * E.PX_PER_M - oy)
            gem = m % E.DIAMOND_EVERY_M == 0
            col = (0, 200, 255) if gem else (90, 110, 150)
            for x in range(0, W, 36):
                pygame.draw.line(arena, col, (x, y), (x + 18, y), 2 if gem else 1)
            lab = self._mark_label(f"{m} m", col)
            arena.blit(lab, (14, y - lab.get_height() - 2))
            if gem:
                cx, cy = W - 34, y - 16
                pygame.draw.polygon(arena, (0, 230, 255), [(cx, cy - 12), (cx + 10, cy), (cx, cy + 12), (cx - 10, cy)])
                pygame.draw.polygon(arena, (220, 250, 255), [(cx, cy - 12), (cx + 10, cy), (cx, cy + 12), (cx - 10, cy)], 2)
        rec = getattr(self, "record_m", 0)
        if rec > 0 and bot_m <= rec <= top_m:
            y = int(sy - rec * E.PX_PER_M - oy)
            pygame.draw.line(arena, (255, 200, 50), (0, y), (W, y), 4)
            lab = self._mark_label(f"REKOR {rec} m" if __import__("locales").get_language() == "tr" else f"RECORD {rec} m",
                                   (255, 215, 80))
            arena.blit(lab, (W - lab.get_width() - 14, y - lab.get_height() - 4))

    def _blit_far(self, arena, art, far_y, vh, alpha):
        if art is None or not art.ready():
            arena.fill(self.palette["bg_top"])
            return
        y = -(far_y % (2 * FAR_H))
        while y < vh:
            img = art.far if ((y + far_y) // FAR_H) % 2 == 0 else art.far_flip
            if alpha is not None:
                img.set_alpha(alpha)
                arena.blit(img, (0, y))
                img.set_alpha(None)
            else:
                arena.blit(img, (0, y))
            y += FAR_H

    def _draw_connector(self, arena, y, pal):
        g = int(E.GAP)
        side = int(E.SIDE)
        for x in (0, W - side):
            pygame.draw.rect(arena, pal["fill"], (x, y, side, g))
        border = pal["border"]
        dim = tuple(int(c * 0.45) for c in border)
        pygame.draw.line(arena, dim, (side, y), (side, y + g), 5)
        pygame.draw.line(arena, dim, (W - side, y), (W - side, y + g), 5)
        pygame.draw.line(arena, border, (side, y), (side, y + g), 2)
        pygame.draw.line(arena, border, (W - side, y), (W - side, y + g), 2)

    def _draw_plain(self, arena, st, k, oy, y, bh):
        pal = lm.PALETTES[sector_for_stage(k)]
        top = st.top
        for (x, wy, w, h) in st.d["walls"]:
            sy = wy - oy
            if sy + h < max(0, y) or sy > min(arena.get_height(), y + bh):
                continue
            r = pygame.Rect(int(x), int(sy), int(w), int(h))
            pygame.draw.rect(arena, pal["fill"], r)
            pygame.draw.rect(arena, pal["border"], r, 2)
