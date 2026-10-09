"""Portrait, touch-first UI for HOLO. Logical screen: VW x VH (900 x >=1620)."""
import math
import pygame

import gfx
from render_cache import SurfaceCache

from theme import (PANEL_BG, ACCENT_CYAN, ACCENT_GOLD, ACCENT_GREEN, TEXT_WHITE,
                   TEXT_MUTED, BTN_NORMAL, BTN_HOVER, BORDER_COLOR)
from fonts import get_font
from flags import draw_flag_icon, draw_country_badge, get_country_info
from skins import SKINS, SKIN_LIST, PREMIUM_SKINS, draw_tether, draw_orb, _heart_pts
import shop as shop_mod
import locales
from locales import t, get_language
from save_manager import COUNTRIES
from level_manager import SECTOR_NAMES
from sim import MAX_LEVELS
from version import __version__
import space_art
import config
import paths
import achievements as ach_mod
import skin_catalog as catalog
import skin_text

VW = 900
VH = 1620
HUD_H = 150

SECTOR_COL = {1: (0, 210, 255), 2: (210, 60, 255), 3: (35, 245, 140), 4: (255, 130, 35), 5: (255, 45, 85)}


_HERO_KIND = {1: "ringed", 2: "pulsar", 3: "crystal", 4: "blackhole", 5: "supernova"}
_ICONS = {}


def sector_icon(sector, size=150):
    """Cached space icon (planet / pulsar / crystal / black hole / supernova) for a sector."""
    key = (sector, size)
    ic = _ICONS.get(key)
    if ic is None:
        ic = pygame.Surface((size, size), pygame.SRCALPHA)
        space_art.draw_hero(ic, _HERO_KIND[sector], size // 2, size // 2, int(size * 0.24), sector)
        _ICONS[key] = ic
    return ic


def set_screen_size(w, h):
    global VW, VH
    VW, VH = int(w), int(h)


# ------------------------------------------------------------------------------------- helpers
_TEXT_CACHE = SurfaceCache(8 * 1024 * 1024)
_SKIN_THUMB_CACHE = {}


def skin_thumbnail(sid, width=110, height=70, radius=16):
    """Render card art once; twelve animated alpha-heavy previews were costly on Android."""
    key = (sid, width, height, radius)
    thumb = _SKIN_THUMB_CACHE.get(key)
    if thumb is None:
        thumb = pygame.Surface((width, height), pygame.SRCALPHA)
        sk = SKINS.get(sid, SKINS["neon_pulse"])
        cy = height // 2
        d = max(34, int(width * 0.26))                   # bigger cards spread the pair a little more
        p1, p2 = (width // 2 - d, cy), (width // 2 + d, cy)
        draw_tether(thumb, p1, p2, sk, 0.65)
        draw_orb(thumb, p1, radius, sk["color1"], sk["glow1"], False, sk, 0.65)
        draw_orb(thumb, p2, radius, sk["color2"], sk["glow2"], True, sk, 0.65)
        _SKIN_THUMB_CACHE[key] = thumb
    return thumb


def text_surface(txt, size, color, bold=True, max_w=None, bg=None):
    """Cached rendered label. With `bg` (the solid colour it will sit on) the label is rendered opaque onto that
    colour: it looks the same there but is copied instead of alpha-blended - much cheaper on phones.
    bg="key": over a moving scene - rendered on black with black as the colour key (RLE): the anti-aliased rim
    reads as a thin dark outline and the copy costs a fraction of an alpha blend."""
    # Pulsing/fading labels pass a slightly different colour every frame; snapping channels to steps of 4 (at most
    # 2/255 off - invisible) keeps them cacheable instead of re-rasterising the glyphs each frame.
    color = tuple(min(255, (v + 2) // 4 * 4) for v in tuple(pygame.Color(color))[:3])
    key = (str(txt), size, color, bold, max_w, bg)
    s = _TEXT_CACHE.get(key)
    if s is None:
        f = get_font(size, bold)
        s = f.render(str(txt), True, color)
        if max_w and s.get_width() > max_w:
            f = get_font(max(14, int(size * max_w / s.get_width())), bold)
            s = f.render(str(txt), True, color)
        if bg == "key":
            flat = gfx.cv(pygame.Surface(s.get_size()))
            flat.fill((0, 0, 0))
            flat.blit(s, (0, 0))
            flat.set_colorkey((0, 0, 0), pygame.RLEACCEL)
            s = flat
        elif bg is not None:
            flat = gfx.cv(pygame.Surface(s.get_size()))
            flat.fill(bg)
            flat.blit(s, (0, 0))
            s = flat
        _TEXT_CACHE.put(key, s)
    return s


def draw_text(surface, txt, size, color, pos, anchor="center", bold=True, max_w=None, bg=None):
    s = text_surface(txt, size, color, bold, max_w, bg)
    r = s.get_rect()
    setattr(r, anchor, pos)
    surface.blit(s, r)
    return r


def draw_text_wrapped(surface, txt, size, color, pos, max_w, bold=False, bg=None, line_gap=4):
    """Left-anchored label at (x, centre y) that breaks onto a second line instead of shrinking when too wide."""
    f = get_font(size, bold)
    words, lines, cur = str(txt).split(), [], ""
    for w in words:
        cand = (cur + " " + w).strip()
        if cur and f.size(cand)[0] > max_w:
            lines.append(cur)
            cur = w
        else:
            cur = cand
    if cur:
        lines.append(cur)
    if len(lines) > 2:                     # still too long: fall back to the shrinking single line
        return draw_text(surface, txt, size, color, pos, anchor="midleft", bold=bold, max_w=max_w, bg=bg)
    lh = f.get_linesize() + line_gap
    y0 = pos[1] - (len(lines) - 1) * lh / 2.0
    for i, line in enumerate(lines):
        draw_text(surface, line, size, color, (pos[0], int(y0 + i * lh)), anchor="midleft", bold=bold, max_w=max_w, bg=bg)


def draw_paragraph(surface, txt, size, color, x, top, max_w, line_gap=6, center=False):
    """Word-wrapped text block of any length, top at `top`; returns the y below the last line."""
    f = get_font(size, False)
    lines, cur = [], ""
    for w in str(txt).split():
        cand = (cur + " " + w).strip()
        if cur and f.size(cand)[0] > max_w:
            lines.append(cur)
            cur = w
        else:
            cur = cand
    if cur:
        lines.append(cur)
    lh = f.get_linesize() + line_gap
    for i, line in enumerate(lines):
        y = int(top + i * lh + lh / 2)
        if center:
            draw_text(surface, line, size, color, (x + max_w // 2, y), bold=False, max_w=max_w)
        else:
            draw_text(surface, line, size, color, (x, y), anchor="midleft", bold=False, max_w=max_w)
    return top + len(lines) * lh


def draw_vector_star(surface, x, y, radius=10, filled=True, color=ACCENT_GOLD):
    pts = []
    for i in range(10):
        r = radius if i % 2 == 0 else radius * 0.45
        a = -math.pi / 2 + i * math.pi / 5
        pts.append((x + math.cos(a) * r, y + math.sin(a) * r))
    if filled:
        pygame.draw.polygon(surface, color, pts)
        pygame.draw.polygon(surface, (255, 255, 235), [(p[0] * 0.55 + x * 0.45, p[1] * 0.55 + y * 0.45) for p in pts])
    else:
        pygame.draw.polygon(surface, (55, 65, 88), pts, 2)


def get_rank_color(rank):
    return {"S+": ACCENT_GOLD, "S": ACCENT_CYAN, "A": (210, 90, 255), "B": (80, 170, 255)}.get(rank, (160, 170, 190))


def _shade(c, k):
    return tuple(max(0, min(255, int(v * k))) for v in c[:3])


def _quant(c, q=6):
    return tuple(min(255, (int(v) // q) * q) for v in c[:3])


_CANDY = {}


def candy_surface(w, h, base, radius):
    """Cached glossy rounded gradient (light top, deeper bottom, white gloss, soft outline)."""
    key = (w, h, base, radius)
    s = _CANDY.get(key)
    if s is not None:
        return s
    top = tuple(min(255, int(v * 1.12 + 22)) for v in base)
    bot = _shade(base, 0.74)
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    for y in range(h):
        k = y / float(max(1, h - 1))
        pygame.draw.line(s, tuple(int(top[i] + (bot[i] - top[i]) * k) for i in range(3)) + (255,), (0, y), (w, y))
    mask = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.rect(mask, (255, 255, 255, 255), (0, 0, w, h), border_radius=radius)
    s.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    gloss = pygame.Surface((w, h), pygame.SRCALPHA)
    lum = 0.3 * base[0] + 0.59 * base[1] + 0.11 * base[2]
    pygame.draw.rect(gloss, (255, 255, 255, int(20 + 44 * min(1.0, lum / 170.0))), (8, 5, w - 16, max(6, int(h * 0.40))), border_radius=max(4, radius - 6))
    s.blit(gloss, (0, 0))
    pygame.draw.rect(s, _shade(base, 1.3) + (255,), (0, 0, w, h), 3, border_radius=radius)
    if len(_CANDY) > 400:
        _CANDY.clear()
    _CANDY[key] = s
    return s


_COCKPIT = {}


def cockpit_surface(w, h, top, bot, edge, radius):
    """Dark glass panel with a neon outline, a bright top rim and small HUD brackets (space-tech look)."""
    key = (w, h, top, bot, edge, radius)
    s = _COCKPIT.get(key)
    if s is not None:
        return s
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    for y in range(h):
        k = y / float(max(1, h - 1))
        pygame.draw.line(s, tuple(int(top[i] + (bot[i] - top[i]) * k) for i in range(3)) + (255,), (0, y), (w, y))
    mask = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.rect(mask, (255, 255, 255, 255), (0, 0, w, h), border_radius=radius)
    s.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    rim = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.rect(rim, (255, 255, 255, 34), (radius // 2 + 4, 4, w - radius - 8, 3), border_radius=2)
    s.blit(rim, (0, 0))
    pygame.draw.rect(s, edge + (255,), (0, 0, w, h), 3, border_radius=radius)
    if w > 200 and h > 70:
        ah = int(h * 0.36)
        for x in (12, w - 16):
            pygame.draw.rect(s, edge + (255,), (x, (h - ah) // 2, 4, ah), border_radius=2)
    if len(_COCKPIT) > 400:
        _COCKPIT.clear()
    _COCKPIT[key] = s
    return s


_HALO = {}


def neon_halo(w, h, colour, radius):
    key = (w, h, colour, radius)
    s = _HALO.get(key)
    if s is None:
        s = pygame.Surface((w + 24, h + 24), pygame.SRCALPHA)
        pygame.draw.rect(s, colour + (26,), (0, 0, w + 24, h + 24), border_radius=radius + 12)
        pygame.draw.rect(s, colour + (34,), (8, 8, w + 8, h + 8), border_radius=radius + 6)
        if len(_HALO) > 300:
            _HALO.clear()
        _HALO[key] = s
    return s


_SHADOW = {}


def soft_shadow(w, h, radius, alpha=95):
    key = (w, h, radius, alpha)
    s = _SHADOW.get(key)
    if s is None:
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(s, (2, 4, 12, alpha), (0, 0, w, h), border_radius=radius)
        if len(_SHADOW) > 300:
            _SHADOW.clear()
        _SHADOW[key] = s
    return s


def shadow_under(surface, rect, shadow_radius, alpha, dy, card_radius):
    """Drop shadow for an opaque rounded card drawn right after it at `rect`: the card hides every shadow row
    between its rounded ends, so only the two visible bands are blended (a full-card alpha blit was the most
    expensive part of the big modals)."""
    s = soft_shadow(rect.w, rect.h, shadow_radius, alpha)
    top = max(0, min(rect.h, card_radius - dy))
    bot = max(top, rect.h - card_radius - dy)
    if top > 0:
        surface.blit(s, (rect.x, rect.y + dy), area=pygame.Rect(0, 0, rect.w, top))
    if bot < rect.h:
        surface.blit(s, (rect.x, rect.y + dy + bot), area=pygame.Rect(0, bot, rect.w, rect.h - bot))


def sparkle(surface, x, y, size, color=(255, 255, 255)):
    """Four-point twinkle."""
    x, y = int(x), int(y)
    s = max(2, int(size))
    pygame.draw.polygon(surface, color, [(x, y - s), (x + s * 0.28, y - s * 0.28), (x + s, y), (x + s * 0.28, y + s * 0.28),
                                         (x, y + s), (x - s * 0.28, y + s * 0.28), (x - s, y), (x - s * 0.28, y - s * 0.28)])


def draw_heart(surface, x, y, size, color):
    pygame.draw.polygon(surface, color, _heart_pts(x, y, size))


def draw_diamond_icon(surface, cx, cy, size=16, color=(0, 230, 255)):
    """Crisp gemstone diamond icon with facets and shine."""
    s = size
    w_top = int(s * 0.65)
    w_mid = int(s * 1.05)
    y_top = cy - int(s * 0.7)
    y_mid = cy - int(s * 0.1)
    y_bot = cy + int(s * 0.85)

    outer_pts = [
        (cx - w_top, y_top),
        (cx + w_top, y_top),
        (cx + w_mid, y_mid),
        (cx, y_bot),
        (cx - w_mid, y_mid),
    ]
    pygame.draw.polygon(surface, color, outer_pts)
    top_facet = [(cx - w_top, y_top), (cx + w_top, y_top), (cx + int(w_top * 0.5), y_mid), (cx - int(w_top * 0.5), y_mid)]
    pygame.draw.polygon(surface, (255, 255, 255), top_facet)
    pygame.draw.polygon(surface, (min(255, color[0] + 40), min(255, color[1] + 40), min(255, color[2] + 40)),
                        [(cx - int(w_top * 0.5), y_mid), (cx + int(w_top * 0.5), y_mid), (cx, y_bot)])
    pygame.draw.polygon(surface, (255, 255, 255), outer_pts, 1)


def draw_diamond_badge(surface, cx, cy, amount):
    """Pill badge showing diamond icon and amount."""
    s_txt = str(amount)
    font = get_font(28, True)
    tw = font.size(s_txt)[0]
    bw = max(96, tw + 54)
    bh = 40
    rect = pygame.Rect(cx - bw // 2, cy - bh // 2, bw, bh)
    panel(surface, rect, (16, 26, 44), (0, 214, 255), 20, 2)
    draw_diamond_icon(surface, rect.x + 22, rect.centery, 13, (0, 230, 255))
    draw_text(surface, s_txt, 26, TEXT_WHITE, (rect.x + 36 + tw // 2, rect.centery), bold=True)


def panel(surface, rect, fill=PANEL_BG, border=BORDER_COLOR, radius=22, width=2):
    pygame.draw.rect(surface, fill, rect, border_radius=radius)
    if width:
        pygame.draw.rect(surface, border, rect, width, border_radius=radius)


_DIM = {}
_dim_mode = None             # None | "capture" | "replay" (see set_dim_mode)
_dim_snapshot = None


def set_dim_mode(mode):
    """Modals open with dim() over a background that no longer changes. "capture": the next dim() also copies
    the dimmed frame (take_dim_snapshot() returns it); "replay": dim() does nothing because the caller has
    already blitted that copy - so an open modal costs one opaque copy instead of redrawing the scene + veil."""
    global _dim_mode, _dim_snapshot
    _dim_mode = mode
    _dim_snapshot = None


def take_dim_snapshot():
    global _dim_snapshot
    snap, _dim_snapshot = _dim_snapshot, None
    return snap


def dim(surface, alpha=215, color=(5, 8, 15)):
    global _dim_mode, _dim_snapshot
    if _dim_mode == "replay":
        return
    # Uniform veil: an opaque surface with surface-alpha blends much faster than a per-pixel-alpha one.
    key = (VW, VH, alpha, tuple(color))
    d = _DIM.get(key)
    if d is None:
        d = pygame.Surface((VW, VH))
        d.fill(color)
        d.set_alpha(alpha)
        _DIM[key] = d
    surface.blit(d, (0, 0))
    if _dim_mode == "capture" and surface.get_size() == (VW, VH):
        _dim_snapshot = surface.copy()
        _dim_mode = None


def fmt_int(n):
    return f"{int(n):,}".replace(",", ".") if get_language() == "tr" else f"{int(n):,}"


_BUTTON_CACHE = {}
_SPLIT = {}          # button key -> (opaque body, its offset, edge bands to blend)
_PAD = 12            # room around a button sprite for the neon halo and the drop shadow
_BLOCKS = {}


def draw_buttons_on_backdrop(surface, buttons, backdrop):
    """Buttons that sit straight on a static full-screen backdrop: the whole group is cached as ONE opaque tile
    (backdrop + every button in draw order, so neighbouring shadows overlap exactly as before) and costs a
    plain copy per frame instead of one alpha blend per button. Rebuilt only when a button changes state."""
    sprites = [s for s in (b.sprite() for b in buttons) if s is not None]
    if not sprites:
        return
    area = pygame.Rect(sprites[0][2], sprites[0][1].get_size())
    for _, comp, pos in sprites[1:]:
        area.union_ip(pygame.Rect(pos, comp.get_size()))
    area = area.clip(backdrop.get_rect())
    key = (tuple((k, pos) for k, _, pos in sprites), id(backdrop), backdrop.get_size())
    tile = _BLOCKS.get(key)
    if tile is None:
        tile = backdrop.subsurface(area).copy()
        for _, comp, pos in sprites:
            tile.blit(comp, (pos[0] - area.x, pos[1] - area.y), special_flags=pygame.BLEND_PREMULTIPLIED)
        if len(_BLOCKS) > 16:
            _BLOCKS.clear()
        _BLOCKS[key] = tile
    surface.blit(tile, area.topleft)


def premultiplied(src):
    """Copy of a per-pixel-alpha surface with premultiplied colour (Surface.premul_alpha() is unreliable)."""
    over_black = pygame.Surface(src.get_size())
    over_black.fill((0, 0, 0))
    over_black.blit(src, (0, 0))                                   # rgb * alpha
    out = src.copy()
    out.fill((0, 0, 0, 255), special_flags=pygame.BLEND_RGBA_MIN)   # keep alpha, clear rgb
    out.blit(over_black, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
    return out


class Button:
    def __init__(self, rect, text, font_size=34, bg_color=BTN_NORMAL, hover_color=BTN_HOVER,
                 text_color=TEXT_WHITE, border_color=BORDER_COLOR, callback=None, sub=None, icon=None):
        self.icon = icon
        self.rect = pygame.Rect(rect)
        self.text = text
        self.sub = sub
        self.font_size = font_size
        self.bg_color = bg_color
        self.hover_color = hover_color
        self.text_color = text_color
        self.border_color = border_color
        self.callback = callback
        self.hover_progress = 0.0
        self.pressed = False
        self.enabled = True
        self.visible = True

    def update(self, mouse_pos, dt=1.0):
        target = 1.0 if self.pressed else 0.0
        self.hover_progress += (target - self.hover_progress) * 0.35 * min(2.0, dt)

    def handle_event(self, event):
        if not self.enabled or not self.visible:
            return False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.pressed = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            was = self.pressed
            self.pressed = False
            if was and self.rect.collidepoint(event.pos):
                return True
        return False

    def draw(self, surface):
        spr = self.sprite()
        if spr is None:
            return
        key, comp, (x, y) = spr
        parts = _SPLIT.get(key)
        if parts is None:
            # The glass body between the rounded ends is fully opaque: copy it plainly and blend only the edge
            # bands (halo, shadow, corners) - identical pixels, about half the blending work.
            W, H = comp.get_size()
            w, h, rad = W - 2 * _PAD, H - 2 * _PAD, key[8]
            top, bot = _PAD + rad, _PAD + h - rad
            if bot - top >= 8:
                core_r = pygame.Rect(_PAD, top, w, bot - top)
                core = gfx.cv(comp.subsurface(core_r).copy())
                bands = [pygame.Rect(0, 0, W, top), pygame.Rect(0, bot, W, H - bot),
                         pygame.Rect(0, top, _PAD, bot - top), pygame.Rect(_PAD + w, top, W - _PAD - w, bot - top)]
                parts = (core, core_r.topleft, bands)
            else:
                parts = (None, None, [pygame.Rect(0, 0, W, H)])
            if len(_SPLIT) > 300:
                _SPLIT.clear()
            _SPLIT[key] = parts
        core, core_pos, bands = parts
        if core is not None:
            surface.blit(core, (x + core_pos[0], y + core_pos[1]))
        for b in bands:
            surface.blit(comp, (x + b.x, y + b.y), area=b, special_flags=pygame.BLEND_PREMULTIPLIED)

    def sprite(self):
        """(cache key, premultiplied sprite, top-left) for the current state; None when hidden."""
        if not self.visible:
            return None
        p = self.hover_progress
        mix = lambda a, b: tuple(int(a[i] + (b[i] - a[i]) * p) for i in range(3))
        r = self.rect.copy()
        if self.pressed:
            r = r.inflate(-8, -8)
            r.y += 3
        bg = _quant(mix(self.bg_color, self.hover_color))
        if not self.enabled:
            bg = _quant(_shade(self.bg_color, 0.7))
        rad = min(r.h // 2, 22 if r.h > 70 else 16)
        lum = 0.3 * bg[0] + 0.59 * bg[1] + 0.11 * bg[2]
        halo = lum > 105 and self.enabled                    # saturated colour = neon accent on dark glass
        if halo:
            top, bot, edge = _quant(_shade(bg, 0.36)), _quant(_shade(bg, 0.15)), bg
        else:                                                # dark default button: navy glass, cyan edge when pressed
            edge = _quant(tuple(int(self.border_color[i] + (ACCENT_CYAN[i] - self.border_color[i]) * p) for i in range(3)))
            top, bot = _quant(_shade(bg, 1.5)), bg
            if not self.enabled:
                edge = (48, 56, 76)
        col = tuple(self.text_color if self.enabled else (110, 118, 140))
        key = (r.w, r.h, self.pressed, halo, bg, top, bot, edge, rad, col, str(self.text), str(self.sub), self.icon,
               self.font_size)
        comp = _BUTTON_CACHE.get(key)
        if comp is None:
            comp = self._compose(r.w, r.h, halo, bg, top, bot, edge, rad, col)
            if len(_BUTTON_CACHE) > 300:
                _BUTTON_CACHE.clear()
            _BUTTON_CACHE[key] = comp
        return key, comp, (r.x - _PAD, r.y - _PAD)

    def _compose(self, w, h, halo, bg, top, bot, edge, rad, col):
        """Shadow, halo, glass panel and label pre-blended into one premultiplied sprite: one blit per frame
        instead of five alpha blits (the menus redraw every frame, and phones blend pixels slowly)."""
        # Layers are built directly in premultiplied form (Surface.premul_alpha() garbles rows of some
        # widths in pygame 2.6.1). The glass panel has binary alpha with black outside, so it already is.
        comp = pygame.Surface((w + 2 * _PAD, h + 2 * _PAD), pygame.SRCALPHA)
        comp.fill((0, 0, 0, 0))

        def pm(c, a):
            return tuple(int(v * a / 255.0 + 0.5) for v in c[:3]) + (a,)

        def put(src, x, y):
            comp.blit(src, (x + _PAD, y + _PAD), special_flags=pygame.BLEND_PREMULTIPLIED)

        def label(txt, size, colour, center, bold=True, max_w=None):
            # Labels sit on the opaque panel, where plain alpha blending equals premultiplied blending.
            s = text_surface(txt, size, colour, bold, max_w)
            rr = s.get_rect(center=(int(center[0]), int(center[1])))
            comp.blit(s, (rr.x + _PAD, rr.y + _PAD))

        shadow = pygame.Surface((w, h), pygame.SRCALPHA)
        shadow.fill((0, 0, 0, 0))
        pygame.draw.rect(shadow, pm((2, 4, 12), 95), (0, 0, w, h), border_radius=rad)
        put(shadow, 0, 4 if self.pressed else 8)
        if halo:
            glow = pygame.Surface((w + 24, h + 24), pygame.SRCALPHA)
            glow.fill((0, 0, 0, 0))
            pygame.draw.rect(glow, pm(bg, 26), (0, 0, w + 24, h + 24), border_radius=rad + 12)
            pygame.draw.rect(glow, pm(bg, 34), (8, 8, w + 8, h + 8), border_radius=rad + 6)
            put(glow, -12, -12)
        put(cockpit_surface(w, h, top, bot, edge, rad), 0, 0)
        sh = (2, 4, 12)
        cx, cy = w / 2.0, h // 2
        if self.icon == "back":
            ax = 40 + _PAD
            pygame.draw.lines(comp, col, False, [(ax + 9, cy + _PAD - 16), (ax - 7, cy + _PAD), (ax + 9, cy + _PAD + 16)], 5)
            label(self.text, self.font_size, sh, (cx + 20, cy + 2), max_w=w - 80)
            label(self.text, self.font_size, col, (cx + 20, cy), max_w=w - 80)
        elif self.icon == "gem":
            tw = text_surface(self.text, self.font_size, col, True, w - 90).get_width()
            x0 = cx - (tw + 44) / 2.0
            label(self.text, self.font_size, sh, (x0 + tw / 2.0, cy + 2), max_w=w - 90)
            label(self.text, self.font_size, col, (x0 + tw / 2.0, cy), max_w=w - 90)
            draw_diamond_icon(comp, int(x0 + tw + 30) + _PAD, cy + _PAD, max(10, int(self.font_size * 0.45)), (0, 230, 255))
        elif self.sub:
            label(self.text, self.font_size, sh, (cx, cy - h * 0.16 + 2), max_w=w - 30)
            label(self.text, self.font_size, col, (cx, cy - h * 0.16), max_w=w - 30)
            label(self.sub, int(self.font_size * 0.62), _shade(col, 0.85), (cx, cy + h * 0.24), bold=False, max_w=w - 30)
        else:
            label(self.text, self.font_size, sh, (cx, cy + 2), max_w=w - 30)
            label(self.text, self.font_size, col, (cx, cy), max_w=w - 30)
        return comp


class Slider:
    def __init__(self, x, y, w, h, min_val=0.0, max_val=1.0, initial_val=0.5, on_change=None):
        self.rect = pygame.Rect(x, y, w, h)
        self.min_val, self.max_val = min_val, max_val
        self.value = initial_val
        self.on_change = on_change
        self.dragging = False

    def _hit(self, pos):
        return self.rect.inflate(30, 60).collidepoint(pos)

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self._hit(event.pos):
            self.dragging = True
            self._set(event.pos[0])
            return True
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.dragging = False
        elif event.type == pygame.MOUSEMOTION and self.dragging:
            self._set(event.pos[0])
            return True
        return False

    def _set(self, mx):
        f = max(0.0, min(1.0, (mx - self.rect.x) / self.rect.width))
        self.value = self.min_val + f * (self.max_val - self.min_val)
        if self.on_change:
            self.on_change(self.value)

    def draw(self, surface):
        pygame.draw.rect(surface, (35, 42, 60), self.rect, border_radius=8)
        f = (self.value - self.min_val) / (self.max_val - self.min_val)
        if f > 0:
            pygame.draw.rect(surface, ACCENT_CYAN, (self.rect.x, self.rect.y, int(self.rect.width * f), self.rect.height), border_radius=8)
        hx = int(self.rect.x + f * self.rect.width)
        h = pygame.Rect(0, 0, 36, 52)
        h.center = (hx, self.rect.centery)
        pygame.draw.rect(surface, (240, 245, 255), h, border_radius=10)
        pygame.draw.rect(surface, ACCENT_CYAN, h, 3, border_radius=10)


class Toggle:
    def __init__(self, rect, label, value, on_change):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.value = value
        self.on_change = on_change
        self.pressed = False

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.pressed = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            was, self.pressed = self.pressed, False
            if was and self.rect.collidepoint(event.pos):
                self.value = not self.value
                self.on_change(self.value)
                return True
        return False

    def draw(self, surface):
        draw_text(surface, self.label, 32, TEXT_WHITE, (self.rect.x, self.rect.centery), anchor="midleft")
        pill = pygame.Rect(0, 0, 130, 62)
        pill.midright = (self.rect.right, self.rect.centery)
        pygame.draw.rect(surface, (25, 70, 55) if self.value else (40, 30, 42), pill, border_radius=31)
        pygame.draw.rect(surface, ACCENT_GREEN if self.value else (110, 70, 90), pill, 3, border_radius=31)
        kx = pill.right - 34 if self.value else pill.left + 34
        pygame.draw.circle(surface, (235, 255, 245) if self.value else (170, 150, 165), (kx, pill.centery), 22)


def modal_sig(modal):
    """What a modal's picture depends on: its dyn_key() plus the state of every button / slider / toggle it holds.
    None = the modal animates (always redrawn). Equal signatures -> the game shows the cached frame."""
    dyn = getattr(modal, "dyn_key", None)
    if dyn is None:
        return None
    parts = [get_language(), dyn()]

    def one(k, v):
        if isinstance(v, Button):
            s = v.sprite() if v.visible else None
            parts.append((k, s[0] if s else None, v.rect.topleft))
        elif isinstance(v, Slider):
            parts.append((k, round(v.value, 3), v.dragging))
        elif isinstance(v, Toggle):
            parts.append((k, v.value, v.pressed))

    for k, v in modal.__dict__.items():
        if isinstance(v, (list, tuple)):
            for i, x in enumerate(v):
                one((k, i), x[-1] if isinstance(x, tuple) and x else x)
        else:
            one(k, v)
    return tuple(parts)


def screen_sig(screen, extra=()):
    """Everything a list screen's picture depends on: its own plain state (page, selection, tab ...), its buttons,
    its scroll position, plus `extra` (save / network state). Animation clocks (time_val, anim) are left out -
    animated bits are drawn by screen.draw_dynamic() over the cached frame."""
    parts = [get_language(), extra]
    for k, v in screen.__dict__.items():
        if k in ("time_val", "anim") or k.startswith("_"):
            continue
        if isinstance(v, (bool, int, str)) or v is None:
            parts.append((k, v))
        elif isinstance(v, float):
            parts.append((k, round(v, 1)))
        elif isinstance(v, Scroller):
            parts.append((k, int(v.y), v.dragging, abs(v.vel) > 0.05))
        elif isinstance(v, Button):
            s = v.sprite() if v.visible else None
            parts.append((k, s[0] if s else None, v.rect.topleft))
        elif isinstance(v, IconButton):
            parts.append((k, v.pressed))
        elif isinstance(v, (list, tuple)):
            for i, x in enumerate(v):
                x = x[-1] if isinstance(x, tuple) and x else x
                if isinstance(x, Button):
                    s = x.sprite() if x.visible else None
                    parts.append((k, i, s[0] if s else None, x.rect.topleft))
                elif isinstance(x, (bool, int, str, float)):
                    parts.append((k, i, x))
    return tuple(parts)


def _login_due(sm):
    """The menu's daily button badge, beside the daily missions: today's login reward + weekly missions to claim."""
    import login_rewards
    return (1 if sm.is_profile_set and login_rewards.claimable(sm) else 0) + sm.weekly_claimable_count()


def _event_due(sm):
    """The menu's achievements button badge: reward tiers of the running event that can be claimed."""
    import events
    return len(events.claimable(sm)) if sm.is_profile_set else 0


class Scroller:
    """Drag / wheel / inertia scrolling shared by the level list and the leaderboard."""

    def __init__(self):
        self.y = 0.0
        self.vel = 0.0
        self.down = None
        self.dragging = False
        self.last_y = 0

    def on_down(self, pos):
        self.down = pos
        self.dragging = False
        self.last_y = pos[1]
        self.vel = 0.0

    def on_move(self, pos):
        if self.down is None:
            return False
        if not self.dragging and abs(pos[1] - self.down[1]) > 16:
            self.dragging = True
        if self.dragging:
            dy = pos[1] - self.last_y
            self.y -= dy
            self.vel = -dy
        self.last_y = pos[1]
        return self.dragging

    def on_up(self, pos):
        """Returns the tap position if the gesture was a tap (not a drag)."""
        d, was_drag = self.down, self.dragging
        self.down = None
        self.dragging = False
        if d is not None and not was_drag:
            self.vel = 0.0
            return pos
        return None

    def wheel(self, dy):
        self.y -= dy * 90
        self.vel = 0.0

    def update(self, content_h, view_h, dt=1.0):
        if self.down is None and abs(self.vel) > 0.3:
            self.y += self.vel * dt
            self.vel *= 0.93 ** dt
        else:
            if self.down is None:
                self.vel = 0.0
        mx = max(0.0, content_h - view_h)
        if self.y < 0:
            self.y += (0 - self.y) * 0.25
            if self.down is None and self.y > -0.5:
                self.y = 0
        elif self.y > mx:
            self.y += (mx - self.y) * 0.25


def header(surface, title, back_btn, right_text=None):
    back_btn.draw(surface)
    draw_text(surface, title, 46, TEXT_WHITE, (VW // 2 + 40, 78))
    if right_text:
        surf = get_font(30, True).render(right_text, True, ACCENT_GOLD)
        pill = pygame.Rect(0, 0, surf.get_width() + 76, 50)
        pill.midright = (VW - 30, 122)
        pygame.draw.rect(surface, (28, 25, 20), pill, border_radius=25)
        pygame.draw.rect(surface, (180, 140, 30), pill, 2, border_radius=25)
        draw_vector_star(surface, pill.x + 30, pill.centery, radius=13, filled=True)
        surface.blit(surf, surf.get_rect(midright=(pill.right - 20, pill.centery)))


def back_button(cb):
    return Button((30, 34, 190, 88), t("back"), font_size=34, callback=cb, icon="back")


def draw_vector_gem(surface, x, y, r):
    pts = [(x, y - r), (x + r, y - r * 0.2), (x, y + r), (x - r, y - r * 0.2)]
    pygame.draw.polygon(surface, (90, 225, 255), pts)
    pygame.draw.polygon(surface, (230, 250, 255), pts, 2)


# ============================================================================================== HUD
class HUD:
    def __init__(self, on_pause=None):
        self.pause_rect = pygame.Rect(24, 24, 100, 100)
        self.shield_rect = pygame.Rect(134, 24, 92, 100)         # buy / arm a shield right next to pause
        self.pause_pressed = False
        self.shield_stock = 0
        self.diamonds = 0
        self.shield_active = 0                                   # shields currently on the pair

    def hit_pause(self, pos):
        return self.pause_rect.inflate(10, 20).collidepoint(pos)

    def hit_shield(self, pos):
        return self.shield_rect.inflate(8, 16).collidepoint(pos)

    def draw(self, surface, level_id, max_levels, stars_collected, score, combo_mult, shields, swaps, elapsed,
             progress, sector_title="", sector=1, attempts=1, title=""):
        # Everything but the progress bar only changes a few times per second: keep it as one opaque sprite and
        # re-render it on change (its text blits are the slowest part of a gameplay frame on phones).
        key = (level_id, max_levels, stars_collected, shields, sector_title, sector, attempts, title,
               min(100, max(0, int(progress * 100))), self.shield_stock, self.shield_active, get_language(), VW)
        if getattr(self, "_key", None) != key:
            if getattr(self, "_img", None) is None or self._img.get_width() != VW:
                self._img = gfx.cv(pygame.Surface((VW, HUD_H + 1)))   # +1: the 2 px bottom rule spills one row
            self._draw_static(self._img, level_id, max_levels, stars_collected, shields, progress, sector_title,
                              sector, attempts, title)
            self._key = key
        surface.blit(self._img, (0, 0))
        self._draw_bar(surface, progress, SECTOR_COL.get(sector, ACCENT_CYAN))

    def _draw_static(self, surface, level_id, max_levels, stars_collected, shields, progress, sector_title,
                     sector, attempts, title):
        col = SECTOR_COL.get(sector, ACCENT_CYAN)
        pygame.draw.rect(surface, (12, 16, 26), (0, 0, VW, HUD_H))
        pygame.draw.line(surface, (40, 55, 80), (0, HUD_H - 1), (VW, HUD_H - 1), 2)

        # pause button
        pr = self.pause_rect
        panel(surface, pr, (24, 30, 46), (70, 88, 122), 20)
        for dx in (-13, 13):
            pygame.draw.rect(surface, TEXT_WHITE, (pr.centerx + dx - 6, pr.centery - 22, 12, 44), border_radius=4)

        self._draw_shield_btn(surface)

        # title block
        draw_text(surface, f"{sector_title}", 24, col, (VW // 2 + 40, 34), max_w=400)
        draw_text(surface, t("level_title", lvl=level_id, max_lvl=max_levels), 54, TEXT_WHITE, (VW // 2 + 40, 78), max_w=420)
        draw_text(surface, title, 26, TEXT_MUTED, (VW // 2 + 40, 116), bold=False, max_w=400)

        # stars + shields
        for i in range(3):
            draw_vector_star(surface, VW - 190 + i * 52, 52, radius=21, filled=(i < stars_collected))
        draw_text(surface, f"{min(100, max(0, int(progress * 100)))}%", 22,
                  TEXT_MUTED, (VW - 138, 85), bold=False)
        if shields > 0:
            pygame.draw.circle(surface, (80, 220, 255), (VW - 178, 108), 14, 3)
            draw_text(surface, f"x{shields}", 28, (120, 235, 255), (VW - 156, 108), anchor="midleft")
        if attempts > 1:
            draw_text(surface, f"#{attempts}", 26, (255, 190, 80), (VW - 40, 108), anchor="midright")

    def _draw_shield_btn(self, surface):
        """Next to pause: tap = put a shield on the pair (own stock, or buy one for 10 diamonds)."""
        sr = self.shield_rect
        on = self.shield_active > 0
        panel(surface, sr, (14, 44, 66) if on else (24, 30, 46), (90, 230, 255) if on else (70, 88, 122), 20, 3 if on else 2)
        cx, cy = sr.centerx, sr.y + 40
        hexp = [(cx + math.cos(math.pi / 6 + k * math.pi / 3) * 26, cy + math.sin(math.pi / 6 + k * math.pi / 3) * 26) for k in range(6)]
        pygame.draw.polygon(surface, (60, 190, 255) if on else (40, 60, 90), hexp)
        pygame.draw.polygon(surface, (170, 240, 255), hexp, 3)
        pygame.draw.circle(surface, (255, 255, 255), (cx, cy), 5)
        if self.shield_stock > 0 or on:
            draw_text(surface, f"x{max(self.shield_stock, self.shield_active)}", 26, (150, 240, 255), (cx, sr.y + 82))
        else:
            draw_text(surface, "10", 24, (120, 235, 255), (cx - 8, sr.y + 82))
            draw_vector_gem(surface, cx + 16, sr.y + 82, 8)

    def _draw_bar(self, surface, progress, col):
        bar = pygame.Rect(0, HUD_H - 8, VW, 8)
        pygame.draw.rect(surface, (20, 26, 40), bar)
        w = int(VW * max(0.0, min(1.0, progress)))
        bc = (255, 65, 85) if progress >= 0.7 else (ACCENT_GOLD if progress >= 0.45 else col)
        if w > 0:
            pygame.draw.rect(surface, bc, (0, HUD_H - 8, w, 8))
            pygame.draw.line(surface, (225, 245, 255), (max(0, w - 2), HUD_H - 8),
                             (max(0, w - 2), HUD_H - 1), 2)
        for fraction in (0.25, 0.5, 0.75):
            x = int(VW * fraction)
            pygame.draw.line(surface, (12, 16, 26), (x, HUD_H - 8), (x, HUD_H - 1), 2)

    def draw_footer(self, surface, y, score, elapsed, swaps, combo_mult, near_miss):
        """Small stats line under the arena (or over it on tall screens)."""
        m = int(elapsed // 60)
        s = elapsed % 60
        clock = f"{m:02d}:{s:04.1f}"
        key = (score, clock, swaps, combo_mult, get_language(), VW)
        if getattr(self, "_fkey", None) != key:        # opaque sprite, re-rendered only when a value changes
            if getattr(self, "_fimg", None) is None or self._fimg.get_width() != VW:
                self._fimg = gfx.cv(pygame.Surface((VW, 72)))
            img, cy = self._fimg, 36
            img.fill((12, 16, 26))
            pygame.draw.line(img, BORDER_COLOR, (24, 1), (VW - 24, 1))
            draw_text(img, f"{score:,}", 30, TEXT_WHITE, (30, cy), anchor="midleft")
            draw_text(img, clock, 28, TEXT_MUTED, (VW // 2, cy), bold=False)
            if combo_mult <= 1:
                draw_text(img, f"{t('swaps')}: {swaps}", 24, TEXT_MUTED,
                          (VW - 30, cy), anchor="midright", max_w=270, bold=False)
            if combo_mult > 1:
                cb = ACCENT_GOLD if combo_mult >= 3 else ACCENT_GREEN
                draw_text(img, t("hud_combo", val=combo_mult), 40, cb, (VW - 40, cy), anchor="midright")
            self._fkey = key
        surface.blit(self._fimg, (0, y - 36))


# ========================================================================================= main menu
def _ease_out(k):
    k = max(0.0, min(1.0, k))
    return 1.0 - (1.0 - k) ** 3


def _draw_menu_icon(s, kind, cx, cy, u, col):
    """Vector glyph for a menu icon, centred on (cx, cy); `u` is the unit size (about half the glyph)."""
    white = (245, 250, 255)
    if kind == "rank":                                   # trophy
        cup = [(cx - u * 0.78, cy - u * 0.85), (cx + u * 0.78, cy - u * 0.85), (cx + u * 0.62, cy - u * 0.05),
               (cx + u * 0.25, cy + u * 0.3), (cx - u * 0.25, cy + u * 0.3), (cx - u * 0.62, cy - u * 0.05)]
        for sx in (-1, 1):
            pygame.draw.circle(s, white, (int(cx + sx * u * 0.78), int(cy - u * 0.42)), int(u * 0.38), max(3, int(u * 0.13)))
        pygame.draw.polygon(s, white, cup)
        pygame.draw.rect(s, white, (cx - u * 0.13, cy + u * 0.25, u * 0.26, u * 0.4))
        pygame.draw.rect(s, white, (cx - u * 0.55, cy + u * 0.62, u * 1.1, u * 0.26), border_radius=int(u * 0.08))
        draw_vector_star(s, cx, cy - u * 0.4, radius=u * 0.3, filled=True, color=col)
    elif kind == "ach":                                  # medal on a ribbon
        pygame.draw.polygon(s, col, [(cx - u * 0.62, cy - u * 0.95), (cx - u * 0.2, cy - u * 0.95), (cx + u * 0.18, cy - u * 0.05),
                                     (cx - u * 0.22, cy + u * 0.05)])
        pygame.draw.polygon(s, _shade(col, 0.75), [(cx + u * 0.62, cy - u * 0.95), (cx + u * 0.2, cy - u * 0.95),
                                                    (cx - u * 0.18, cy - u * 0.05), (cx + u * 0.22, cy + u * 0.05)])
        pygame.draw.circle(s, white, (int(cx), int(cy + u * 0.3)), int(u * 0.62))
        pygame.draw.circle(s, col, (int(cx), int(cy + u * 0.3)), int(u * 0.62), max(3, int(u * 0.1)))
        draw_vector_star(s, cx, cy + u * 0.3, radius=u * 0.36, filled=True, color=ACCENT_GOLD)
    elif kind == "daily":                                # calendar
        r = pygame.Rect(0, 0, int(u * 1.7), int(u * 1.55))
        r.center = (int(cx), int(cy + u * 0.1))
        pygame.draw.rect(s, white, r, border_radius=int(u * 0.22))
        pygame.draw.rect(s, col, (r.x, r.y, r.w, int(u * 0.45)), border_top_left_radius=int(u * 0.22),
                         border_top_right_radius=int(u * 0.22))
        for sx in (-0.45, 0.45):
            pygame.draw.rect(s, white, (cx + sx * u - u * 0.09, r.y - u * 0.22, u * 0.18, u * 0.42), border_radius=int(u * 0.08))
        pts = [(cx - u * 0.45, cy + u * 0.35), (cx - u * 0.1, cy + u * 0.65), (cx + u * 0.5, cy + u * 0.02)]
        pygame.draw.lines(s, col, False, pts, max(4, int(u * 0.2)))
    elif kind == "skins":                                # two orbs on a tether (the game's own motif)
        a, b = (cx - u * 0.55, cy + u * 0.45), (cx + u * 0.55, cy - u * 0.45)
        pygame.draw.line(s, (170, 250, 255), a, b, max(3, int(u * 0.14)))
        for p, c in ((a, (255, 60, 160)), (b, (0, 230, 255))):
            pygame.draw.circle(s, c, (int(p[0]), int(p[1])), int(u * 0.46))
            pygame.draw.circle(s, (255, 255, 255), (int(p[0] - u * 0.16), int(p[1] - u * 0.16)), int(u * 0.13))
    elif kind == "shop":                                 # shopping bag
        body = pygame.Rect(0, 0, int(u * 1.6), int(u * 1.3))
        body.midbottom = (int(cx), int(cy + u * 0.85))
        pygame.draw.arc(s, white, (cx - u * 0.48, body.y - u * 0.62, u * 0.96, u * 1.2), 0.0, math.pi, max(4, int(u * 0.16)))
        pygame.draw.rect(s, white, body, border_radius=int(u * 0.22))
        pygame.draw.rect(s, col, (body.x, body.y + int(u * 0.3), body.w, int(u * 0.16)))
        draw_vector_gem(s, cx, cy + u * 0.4, u * 0.3)
    elif kind == "settings":                             # gear
        n, ro, ri = 8, u * 0.95, u * 0.7
        pts = []
        for i in range(n * 2):
            a0 = i * math.pi / n
            r1 = ro if i % 2 == 0 else ri
            for da in (-0.2, 0.2):
                pts.append((cx + math.cos(a0 + da) * r1, cy + math.sin(a0 + da) * r1))
        pygame.draw.polygon(s, white, pts)
        pygame.draw.circle(s, _shade(col, 0.3), (int(cx), int(cy)), int(u * 0.34))
    elif kind == "quit":                                 # power symbol
        w = max(4, int(u * 0.18))
        # pygame arcs run counter-clockwise with pi/2 at the top: leave the gap around the top
        pygame.draw.arc(s, white, (cx - u * 0.75, cy - u * 0.7, u * 1.5, u * 1.5), math.pi * 0.72, math.pi * 2.28, w)
        pygame.draw.line(s, white, (cx, cy - u * 0.95), (cx, cy - u * 0.05), w)
    elif kind == "levels":                               # 2x2 grid of level tiles
        g = u * 0.78
        for i, (dx, dy) in enumerate(((-1, -1), (1, -1), (-1, 1), (1, 1))):
            r = pygame.Rect(0, 0, int(g), int(g))
            r.center = (int(cx + dx * g * 0.62), int(cy + dy * g * 0.62))
            pygame.draw.rect(s, white if i < 3 else col, r, border_radius=int(u * 0.16))


_ICON_SPRITES = {}
_SS = 2                        # icon sprites are drawn at 2x and smooth-scaled down (anti-aliased edges)


class IconButton:
    """Round glass button with a vector glyph and a short label underneath (the main menu's edge icons)."""

    def __init__(self, center, radius, icon, label, color, callback):
        self.center = (int(center[0]), int(center[1]))
        self.radius = int(radius)
        self.icon = icon
        self.text = label
        self.color = color
        self.callback = callback
        self.pressed = False
        self.enabled = True
        self.visible = True
        self.offset = (0, 0)                   # slide-in during the intro
        self._layout()

    def _layout(self):
        r = self.radius
        self.rect = pygame.Rect(0, 0, 2 * r, 2 * r)
        self.rect.center = (self.center[0] + self.offset[0], self.center[1] + self.offset[1])

    def _hit(self, pos):
        return self.rect.inflate(20, 70).move(0, 25).collidepoint(pos)

    def update(self, mouse_pos, dt=1.0):
        pass

    def handle_event(self, event):
        if not self.visible:
            return False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.pressed = self._hit(event.pos)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            was, self.pressed = self.pressed, False
            if was and self._hit(event.pos):
                return True
        return False

    def _sprite(self):
        key = (self.radius, self.icon, str(self.text), self.color, self.pressed)
        spr = _ICON_SPRITES.get(key)
        if spr is not None:
            return spr
        r, pad, lab_h = self.radius, 18, 40
        W, H = 2 * (r + pad), 2 * (r + pad) + lab_h
        big = pygame.Surface((W * _SS, H * _SS), pygame.SRCALPHA)
        big.fill((0, 0, 0, 0))
        c = (W * _SS // 2, (r + pad) * _SS)
        R = (r - (3 if self.pressed else 0)) * _SS
        col = self.color
        glow = pygame.Surface((W * _SS, (r + pad) * 2 * _SS), pygame.SRCALPHA)
        glow.fill((0, 0, 0, 0))
        pygame.draw.circle(glow, col + (40 if self.pressed else 26,), c, R + 14 * _SS)
        pygame.draw.circle(glow, col + (34,), c, R + 7 * _SS)
        big.blit(glow, (0, 0))
        pygame.draw.circle(big, (2, 4, 12, 70), (c[0], c[1] + 5 * _SS), R - 2 * _SS)   # soft drop shadow
        body_top = _shade(col, 0.32 if self.pressed else 0.24)
        pygame.draw.circle(big, _shade(col, 0.12) + (255,), c, R)
        pygame.draw.circle(big, body_top + (255,), (c[0], c[1] - int(R * 0.18)), int(R * 0.82))
        pygame.draw.circle(big, col + (255,), c, R, 3 * _SS)
        _draw_menu_icon(big, self.icon, c[0], c[1], R * 0.42, col)
        spr = pygame.transform.smoothscale(big, (W, H))
        lbl = text_surface(self.text, 21, (205, 218, 240), True, max_w=W + 40)
        lab = pygame.Surface((max(W, lbl.get_width() + 18), H), pygame.SRCALPHA)
        lab.fill((0, 0, 0, 0))
        lab.blit(spr, ((lab.get_width() - W) // 2, 0))
        if lbl.get_width() > 1:                       # dark pill keeps the label readable over the space art
            lr = lbl.get_rect(midtop=(lab.get_width() // 2, 2 * (r + pad) - 8))
            pill = pygame.Surface((lr.w + 16, lr.h + 2), pygame.SRCALPHA)
            pill.fill((0, 0, 0, 0))
            pygame.draw.rect(pill, (6, 9, 18, 185), pill.get_rect(), border_radius=(lr.h + 2) // 2)
            lab.blit(pill, (lr.x - 8, lr.y - 1))
            lab.blit(lbl, lr)
        if len(_ICON_SPRITES) > 120:
            _ICON_SPRITES.clear()
        _ICON_SPRITES[key] = lab
        return lab

    def draw(self, surface):
        if not self.visible:
            return
        spr = self._sprite()
        cx, cy = self.rect.center
        surface.blit(spr, (cx - spr.get_width() // 2, cy - self.radius - 18))


class _Chip:
    """Tappable area without its own look (the pilot chip in the menu's top bar)."""

    def __init__(self, rect, callback):
        self.rect = pygame.Rect(rect)
        self.callback = callback
        self.pressed = False

    def update(self, mouse_pos, dt=1.0):
        pass

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.pressed = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            was, self.pressed = self.pressed, False
            if was and self.rect.collidepoint(event.pos):
                return True
        return False


class MainMenu:
    """Clean main screen: logo, pilot chip, progress, one big PLAY button and a LEVELS button in the middle; every
    other destination is a round icon in a screen corner: settings top-left, shop + diamonds top-right, ranking /
    goals bottom-left, daily / skins bottom-right. Between the progress line and PLAY: the current level's card."""

    def __init__(self, save_manager, on_continue, on_levels, on_leaderboard, on_skins, on_profile, on_settings,
                 on_quit=None, rank_provider=None, on_shop=None, on_achievements=None, on_daily=None, on_endless=None, on_arena=None):
        self.time_val = 0.0
        self.save_mgr = save_manager
        self.rank_provider = rank_provider
        self.on_continue = on_continue
        self.callbacks = dict(levels=on_levels, lb=on_leaderboard, skins=on_skins, profile=on_profile,
                              settings=on_settings, quit=on_quit, shop=on_shop, ach=on_achievements, daily=on_daily,
                              endless=on_endless, arena=on_arena)
        self.buttons = []
        self.icons = []
        self.btn_daily = None
        self.btn_ach = None
        self.enter = 1.0                       # 0..1 while the start-up intro slides the edge icons in
        self.build()

    # ------------------------------------------------------------------ layout
    DOCK_H = 176

    def title_center(self):
        return VW // 2, int(VH * 0.19)

    def _chip_y(self):
        return int(VH * 0.19) + 238

    def build(self):
        cx = VW // 2
        cl = self.save_mgr.campaign_level
        started = self.save_mgr.levels_cleared > 0 or cl > 1
        white = (255, 255, 255)
        w = 600
        self.free_top = self._chip_y() + 118          # below chip + progress line + sector track
        base = VH - 48 - self.DOCK_H
        top = int((self.free_top + base) / 2 - 146 + 72)
        prim = Button((cx - w // 2, top, w, 150), t("continue_lvl", lvl=cl) if started else t("start_run"), 46,
                      bg_color=(0, 214, 255), hover_color=(90, 236, 255), text_color=white, callback=self.on_continue)
        # the game modes share the second row (the levels page opens from the progress bar above)
        modes = [m for m in ("endless", "arena") if self.callbacks[m]]
        self.buttons = [prim]
        if modes:
            bw = (w - 24 * (len(modes) - 1)) // len(modes)
            for i, mode in enumerate(modes):
                label, size, bg, hov, tc, cb = self._mode_style(mode, getattr(self.save_mgr, f"{mode}_unlocked"))
                self.buttons.append(Button((cx - w // 2 + i * (bw + 24), top + 176, bw, 96), label, size, bg_color=bg,
                                           hover_color=hov, text_color=tc, callback=self.callbacks[cb]))
        self.progress_rect = pygame.Rect(cx - 330, self._chip_y() + 34, 660, 80)
        self._progress_down = False
        self.card_bottom = top - 14                    # the current-level card sits between progress and PLAY

        # round icons in the four corners
        r, m, step = 44, 72, 120
        ty, by = 82, VH - 150
        spots = [("settings", t("icon_settings"), (120, 150, 215), "settings", m, ty, (0, -1))]
        if self.callbacks["quit"]:
            spots.append(("quit", t("icon_quit"), (230, 60, 90), "quit", m + step, ty, (0, -1)))
        if self.callbacks["shop"]:
            spots.append(("shop", t("shop_btn"), (255, 190, 40), "shop", VW - m, ty, (0, -1)))
        spots.append(("rank", t("icon_rank"), (35, 225, 140), "lb", m, by, (-1, 1)))
        if self.callbacks["ach"]:
            spots.append(("ach", t("ach_btn"), (255, 70, 160), "ach", m + step, by, (-1, 1)))
        if self.callbacks["daily"]:
            spots.append(("daily", t("daily_btn"), (255, 170, 40), "daily", VW - m - step, by, (1, 1)))
        spots.append(("skins", t("icon_skins"), (190, 100, 255), "skins", VW - m, by, (1, 1)))
        self.icons = []
        self.btn_daily = None
        self.btn_ach = None
        for kind, label, colr, cb, x, y, slide in spots:
            b = IconButton((x, y), r, kind, label, colr, self.callbacks[cb])
            b.slide = slide
            self.icons.append(b)
            if kind == "daily":
                self.btn_daily = b
            elif kind == "ach":
                self.btn_ach = b
        self.diamond_x = VW - m - (r + 22 if self.callbacks["shop"] else -r)
        self.top_y = ty
        self.chip = _Chip((0, 0, 1, 1), self.callbacks["profile"])
        self._apply_enter()

    _MODE_COL = {"endless": ((150, 70, 235), (190, 120, 255)), "arena": ((235, 70, 120), (255, 120, 160))}

    def _mode_style(self, mode, open_):
        """(label, font size, colours, callback key) of a game-mode button; a locked one says where it opens."""
        bg, hov = self._MODE_COL[mode]
        if open_:
            return t(f"{mode}_btn"), 32, bg, hov, (255, 255, 255), mode
        return t(f"{mode}_locked_btn"), 22, (58, 52, 78), (70, 64, 92), (170, 165, 190), mode

    def _apply_enter(self):
        for i, b in enumerate(self.icons):
            kk = _ease_out((self.enter - 0.07 * (i % 4)) / 0.79) if self.enter < 1.0 else 1.0
            b.offset = (int(b.slide[0] * 240 * (1.0 - kk)), int(b.slide[1] * 240 * (1.0 - kk)))
            b._layout()

    def set_enter(self, k):
        k = max(0.0, min(1.0, k))
        if k != self.enter:
            self.enter = k
            self._apply_enter()

    def refresh_texts(self):
        self.build()

    def set_campaign_level(self, lvl):
        self.build()

    def update(self, mouse_pos, dt=1.0):
        self.time_val += 0.03 * dt
        for b in self.buttons:
            b.update(mouse_pos, dt)

    def handle_event(self, event):
        for b in self.buttons + self.icons:
            if b.handle_event(event):
                return b.callback
        if self.chip.handle_event(event):
            return self.chip.callback
        # the progress line + sector track opens the levels page
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._progress_down = self.progress_rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            was, self._progress_down = self._progress_down, False
            if was and self.progress_rect.collidepoint(event.pos):
                return self.callbacks["levels"]
        return None

    # ------------------------------------------------------------------ drawing
    def _title_sprite(self):
        """The big logo and its offset shadow pre-blended into one premultiplied sprite (one blit, not two)."""
        spr = getattr(self, "_title", None)
        if spr is None:
            shadow = premultiplied(text_surface("HOLO", 190, (0, 150, 230)))
            face = premultiplied(text_surface("HOLO", 190, (255, 255, 255)))
            w, h = face.get_size()
            spr = pygame.Surface((w + 3, h + 10), pygame.SRCALPHA)
            spr.fill((0, 0, 0, 0))
            spr.blit(shadow, (3, 10), special_flags=pygame.BLEND_PREMULTIPLIED)
            spr.blit(face, (0, 0), special_flags=pygame.BLEND_PREMULTIPLIED)
            self._title = spr = (spr, w, h)
        return spr

    def draw_title(self, surface, skin_data, center, orbit_k=1.0, sparkles=True, subtitle=True, logo=True, orbs=True):
        """Logo with the orbiting orb pair. The intro calls it with a moving centre and a growing orbit.
        The menu's cached plate draws the logo only (logo=True, orbs=False, sparkles=False); every frame then adds
        just the orbs and sparkles (logo=False)."""
        cx, cy = center
        orbit = 120 * orbit_k
        p1 = (cx + math.cos(self.time_val) * orbit, cy + math.sin(self.time_val) * orbit)
        p2 = (cx + math.cos(self.time_val + math.pi) * orbit, cy + math.sin(self.time_val + math.pi) * orbit)
        bounce = 0                                   # a still logo can live in the cached plate (see draw_fast)
        spr, tw, th = self._title_sprite()
        face_rect = pygame.Rect(0, 0, tw, th)
        face_rect.center = (int(cx), int(cy) + bounce)
        self.title_rect = face_rect
        if logo:
            surface.blit(spr, face_rect.topleft, special_flags=pygame.BLEND_PREMULTIPLIED)
        if sparkles:
            for k, (dx, dy, sz) in enumerate(((-250, -70, 15), (255, -60, 12), (-200, 80, 9), (215, 84, 14), (0, -122, 10))):
                tw_ = 0.5 + 0.5 * math.sin(self.time_val * 3.0 + k * 1.7)
                sparkle(surface, cx + dx, cy + dy + bounce, sz * (0.5 + 0.7 * tw_), (255, 236, 170) if k % 2 else (200, 230, 255))
        if orbs and orbit_k > 0.02:
            rad = max(2, int(24 * min(1.0, orbit_k)))
            draw_tether(surface, p1, p2, skin_data, self.time_val)
            draw_orb(surface, p1, rad, skin_data["color1"], skin_data["glow1"], False, skin_data, self.time_val)
            draw_orb(surface, p2, rad, skin_data["color2"], skin_data["glow2"], True, skin_data, self.time_val)
        if subtitle and logo:
            draw_text(surface, t("subtitle"), 27, ACCENT_CYAN, (cx, cy + 158), max_w=720)

    def _draw_pilot_chip(self, surface, cy):
        """Flag + callsign pill under the logo; tapping it opens the profile."""
        sm = self.save_mgr
        name_s = text_surface(sm.player_name, 30, (215, 235, 255), max_w=320)
        chip_w = 100 + name_s.get_width() + 28
        chip = pygame.Rect(0, 0, chip_w, 64)
        chip.center = (VW // 2, cy)
        self.chip.rect = chip.inflate(16, 20)
        pygame.draw.rect(surface, (14, 22, 38), chip, border_radius=32)
        pygame.draw.rect(surface, (0, 170, 210) if self.chip.pressed else (50, 70, 105), chip, 2, border_radius=32)
        draw_country_badge(surface, sm.player_country, chip.x + 52, cy, width=74, height=36)
        surface.blit(name_s, (chip.x + 100, cy - name_s.get_height() // 2))

    def _draw_diamonds(self, surface):
        sm = self.save_mgr
        k = _ease_out(self.enter)
        font = get_font(28, True)
        bw = max(96, font.size(str(sm.diamonds))[0] + 54)
        draw_diamond_badge(surface, self.diamond_x - bw // 2, self.top_y + int(-240 * (1.0 - k)), sm.diamonds)

    _TITLES = {}

    @classmethod
    def level_title(cls, level_id):
        """Title of a level straight from its json (cached) - the menu needs it without loading the whole level."""
        if level_id not in cls._TITLES:
            title = ""
            try:
                import json, os
                from sim import LEVELS_DIR
                with open(os.path.join(LEVELS_DIR, f"level{level_id}.json"), encoding="utf-8") as f:
                    title = str(json.load(f).get("title", ""))
            except Exception:
                pass
            cls._TITLES[level_id] = title
        return cls._TITLES[level_id]

    def _draw_level_card(self, surface):
        """Where the pilot is now: sector emblem, sector name + theme, and the level's own title."""
        cl = min(MAX_LEVELS, max(1, self.save_mgr.campaign_level))
        sec = min(5, max(1, (cl - 1) // 20 + 1))
        col = SECTOR_COL[sec]
        cx = VW // 2
        title = self.level_title(cl)
        block_h = 104 + 44 + (46 if title else 0) + 34
        y = int((self.free_top + self.card_bottom - block_h) / 2)
        icon = sector_icon(sec, 124)
        surface.blit(icon, icon.get_rect(center=(cx, y + 52)))
        self.card_rect = pygame.Rect(40, y - 20, VW - 80, block_h + 40)
        y += 104 + 22
        draw_text(surface, f"{t('sector')} {sec}  •  {SECTOR_NAMES[sec]}", 28, col, (cx, y), max_w=760)
        y += 44
        if title:
            draw_text(surface, title, 44, (255, 255, 255), (cx, y), max_w=780)
            y += 46
        draw_text(surface, t(f"sector_desc_{sec}"), 24, TEXT_MUTED, (cx, y), bold=False, max_w=760)

    # ------------------------------------------------------------------ fast path (cached plate)
    def _plate_key(self, backdrop):
        sm = self.save_mgr
        info = self.rank_provider() if self.rank_provider else None
        return (get_language(), VW, VH, id(backdrop), sm.player_name, sm.player_country, sm.levels_cleared,
                sm.get_total_stars(), (info or {}).get("rank"), sm.campaign_level, sm.diamonds,
                (sm.daily_claimable_count() + _login_due(sm)) if self.btn_daily else 0,
                _event_due(sm) if self.btn_ach else 0,
                tuple((b.sprite() or (None,))[0] for b in self.buttons),
                tuple((b.pressed, b.offset) for b in self.icons), self.chip.pressed)

    def _ui_rects(self):
        """Screen areas the plate's UI covers: drifting rocks pass behind them."""
        rs = [self.title_rect.inflate(20, 70).move(0, 30), self.chip.rect.inflate(20, 10),
              pygame.Rect(40, self._chip_y() + 36, VW - 80, 60), getattr(self, "card_rect", pygame.Rect(0, 0, 0, 0))]
        area = None
        for b in self.buttons:
            area = b.rect.inflate(40, 40) if area is None else area.union(b.rect.inflate(40, 40))
        if area:
            rs.append(area)
        for b in self.icons:
            rs.append(b.rect.inflate(40, 80).move(0, 20))
        rs.append(pygame.Rect(self.diamond_x - 110, self.top_y - 30, 180, 60))
        rs.append(pygame.Rect(0, VH - 44, VW, 44))
        return [r for r in rs if r.w > 0 and r.h > 0]

    def plate(self, skin_data, backdrop):
        """Backdrop + every static element of the menu in one opaque surface (rebuilt only when something on it
        changes, e.g. a button is pressed). The start-up intro fades it in as a whole."""
        enter = self.enter
        if enter < 1.0:
            self.set_enter(1.0)                        # the plate shows the final layout
        key = self._plate_key(backdrop)
        if getattr(self, "_plate_k", None) != key:
            plate = getattr(self, "_plate", None)
            if plate is None or plate.get_size() != backdrop.get_size():
                plate = self._plate = backdrop.copy()
            else:
                plate.blit(backdrop, (0, 0))
            self.draw(plate, skin_data, backdrop=backdrop, static=True)
            self._plate_k = key
            self._rects = self._ui_rects()
        if enter < 1.0:
            self.set_enter(enter)
        return self._plate

    def draw_fast(self, surface, skin_data, backdrop, life, t):
        """The menu at a fraction of the cost: the cached plate (one copy) plus the moving bits."""
        surface.blit(self.plate(skin_data, backdrop), (0, 0))
        for r in life.draw(surface, t, avoid=self._rects):      # rocks / comets behind the UI: restore the UI
            for u in self._rects:
                c = r.clip(u)
                if c.w and c.h:
                    surface.blit(self._plate, c.topleft, c)
        self.draw_title(surface, skin_data, self.title_center(), logo=False)

    def draw(self, surface, skin_data, backdrop=None, static=False):
        cx = VW // 2
        self.draw_title(surface, skin_data, self.title_center(), orbs=not static, sparkles=not static)
        sm = self.save_mgr

        # pilot chip, progress line + five sector segments
        y = self._chip_y()
        self._draw_pilot_chip(surface, y)
        y += 60
        info = self.rank_provider() if self.rank_provider else None
        line = f"{t('progress_line', done=sm.levels_cleared, total=MAX_LEVELS, stars=sm.get_total_stars())}"
        if info and info.get("rank"):
            line += f"   •   {t('rank_world', rank=info['rank'])}"
        draw_text(surface, line, 26, TEXT_MUTED, (cx, y), bold=False, max_w=780)
        track_w, gap = 500, 8
        segment_w = (track_w - 4 * gap) // 5
        for index in range(5):
            track = pygame.Rect(cx - track_w // 2 + index * (segment_w + gap), y + 30, segment_w, 6)
            pygame.draw.rect(surface, (32, 42, 62), track, border_radius=3)
            fraction = max(0.0, min(1.0, (sm.levels_cleared - index * 20) / 20.0))
            if fraction:
                pygame.draw.rect(surface, SECTOR_COL[index + 1],
                                 (track.x, track.y, max(2, int(track.w * fraction)), track.h), border_radius=3)
        ax, ay = cx + track_w // 2 + 26, y + 33            # a chevron: the track opens the levels page
        pygame.draw.lines(surface, ACCENT_CYAN, False, [(ax - 6, ay - 10), (ax + 4, ay), (ax - 6, ay + 10)], 4)

        if backdrop is not None:        # the big buttons sit straight on the static space backdrop
            draw_buttons_on_backdrop(surface, self.buttons, backdrop)
        else:
            for b in self.buttons:
                b.draw(surface)
        self._draw_level_card(surface)
        for b in self.icons:
            b.draw(surface)
        self._draw_diamonds(surface)
        for btn, n in ((self.btn_daily, self.save_mgr.daily_claimable_count() + _login_due(self.save_mgr)),
                       (self.btn_ach, _event_due(self.save_mgr))):
            if btn is None or n <= 0:
                continue
            r = btn.rect
            dot = (r.right - 6, r.y + 8)
            pygame.draw.circle(surface, (255, 60, 70), dot, 15)
            pygame.draw.circle(surface, (255, 255, 255), dot, 15, 2)
            draw_text(surface, str(n), 20, (255, 255, 255), dot)
        draw_text(surface, t("footer", ver=__version__), 20, (90, 100, 125), (cx, VH - 22), bold=False)
        if config.test_tools():
            pill = pygame.Rect(0, 0, 640, 46)
            pill.midbottom = (cx, self.dock_rect.y - 14)
            pygame.draw.rect(surface, (70, 20, 30), pill, border_radius=23)
            pygame.draw.rect(surface, (255, 90, 110), pill, 2, border_radius=23)
            draw_text(surface, t("dev_badge"), 24, (255, 170, 180), pill.center, max_w=610)


# ======================================================================================== achievements
# ======================================================================================== themed list pieces
# The goals / achievements / login screens use the game's own cockpit look: dark glass cards with a neon rim and HUD
# brackets, an orbit emblem (a ring with an orb on it - the two-orb motif), neon progress bars with a glowing head.
_THEME_CACHE = {}


def _tcache(key, make):
    s = _THEME_CACHE.get(key)
    if s is None:
        if len(_THEME_CACHE) > 300:
            _THEME_CACHE.clear()
        s = _THEME_CACHE[key] = make()
    return s


def theme_card(surface, r, accent, mode="idle", radius=26):
    """mode: "idle" (quiet rim), "ready" (accent rim + glow - something to take), "done" (green rim)."""
    edge = {"idle": (46, 68, 108), "ready": accent, "done": (60, 200, 130)}[mode]
    top = (18, 40, 46) if mode == "done" else (22, 32, 58)
    if mode == "ready":
        surface.blit(neon_halo(r.w, r.h, accent, radius), (r.x - 12, r.y - 12))
    surface.blit(cockpit_surface(r.w, r.h, top, (8, 12, 26), edge, radius), r.topleft)


def orbit_badge(surface, cx, cy, rad, col, icon="gem", lit=True):
    """Round emblem: glass disc, neon orbit ring with an orb riding on it, an icon in the middle."""
    ring = col if lit else (58, 76, 112)

    def make():
        d = rad * 2 + 24
        s = pygame.Surface((d, d), pygame.SRCALPHA)
        c = d // 2
        if lit:
            for k, a in ((rad + 10, 26), (rad + 5, 40)):
                pygame.draw.circle(s, ring + (a,), (c, c), k)
        for i in range(rad, 0, -2):                      # disc: light centre, deep edge
            f = i / float(rad)
            base = (14, 22, 44) if lit else (14, 18, 30)
            pygame.draw.circle(s, tuple(int(v * (1.25 - 0.45 * f)) for v in base) + (255,), (c, c), i)
        pygame.draw.circle(s, ring + (255,), (c, c), rad, 3)
        pygame.draw.circle(s, ring + (110,), (c, c), rad - 9, 1)
        ox, oy = c + int(rad * 0.71), c - int(rad * 0.71)  # the orb on the ring (top right)
        orb = (255, 255, 255) if lit else (120, 135, 165)
        if lit:
            pygame.draw.circle(s, ring + (90,), (ox, oy), 9)
        pygame.draw.circle(s, ring + (255,), (ox, oy), 6)
        pygame.draw.circle(s, orb + (255,), (ox - 1, oy - 1), 3)
        return s

    spr = _tcache(("badge", rad, ring, lit), make)
    surface.blit(spr, spr.get_rect(center=(cx, cy)))
    k = rad / 42.0
    if icon == "gem":
        draw_vector_gem(surface, cx, cy, int(17 * k)) if lit else pygame.draw.polygon(
            surface, (70, 90, 125), [(cx, cy - 17 * k), (cx + 17 * k, cy - 3 * k), (cx, cy + 17 * k), (cx - 17 * k, cy - 3 * k)], 2)
    elif icon == "star":
        draw_vector_star(surface, cx, cy, int(20 * k), filled=lit, color=ACCENT_GOLD if lit else (90, 105, 140))
    elif icon == "check":
        pygame.draw.lines(surface, (255, 255, 255), False,
                          [(cx - 16 * k, cy + 1), (cx - 4 * k, cy + 13 * k), (cx + 18 * k, cy - 12 * k)], max(4, int(7 * k)))
    elif icon == "hex":
        pts = [(cx + math.cos(a) * 18 * k, cy + math.sin(a) * 18 * k) for a in [math.pi / 6 + i * math.pi / 3 for i in range(6)]]
        pygame.draw.polygon(surface, ring, pts, 3)


def neon_bar(surface, r, frac, col, done=False):
    """Progress bar: dark track, gradient fill, glowing orb at its head."""
    frac = max(0.0, min(1.0, frac))
    fill_col = (60, 210, 130) if done else col

    def make_track():
        s = pygame.Surface((r.w, r.h), pygame.SRCALPHA)
        pygame.draw.rect(s, (8, 12, 26, 255), (0, 0, r.w, r.h), border_radius=r.h // 2)
        pygame.draw.rect(s, (44, 62, 98, 255), (0, 0, r.w, r.h), 1, border_radius=r.h // 2)
        return s

    def make_fill():
        s = pygame.Surface((r.w, r.h), pygame.SRCALPHA)
        lo = tuple(int(v * 0.45) for v in fill_col)
        for x in range(r.w):
            k = x / float(max(1, r.w - 1))
            pygame.draw.line(s, tuple(int(lo[i] + (fill_col[i] - lo[i]) * k) for i in range(3)) + (255,), (x, 0), (x, r.h))
        pygame.draw.line(s, (255, 255, 255, 60), (r.h // 2, 2), (r.w - r.h // 2, 2))
        mask = pygame.Surface((r.w, r.h), pygame.SRCALPHA)
        pygame.draw.rect(mask, (255, 255, 255, 255), (0, 0, r.w, r.h), border_radius=r.h // 2)
        s.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        return s

    surface.blit(_tcache(("track", r.w, r.h), make_track), r.topleft)
    w = int(r.w * frac)
    if w <= 0:
        return
    w = max(r.h, w)
    surface.blit(_tcache(("fill", r.w, r.h, fill_col), make_fill), r.topleft, area=pygame.Rect(0, 0, w, r.h))
    hx, hy = r.x + w - r.h // 2, r.centery
    pygame.draw.circle(surface, tuple(min(255, v + 60) for v in fill_col), (hx, hy), r.h // 2 + 3)
    pygame.draw.circle(surface, (255, 255, 255), (hx, hy), max(2, r.h // 2 - 2))


def section_title(surface, y, text, col, right=None, x0=44):
    """Section heading: glowing orb, title, a neon rule running to the right edge."""
    pygame.draw.circle(surface, tuple(int(v * 0.35) for v in col), (x0 + 8, y), 11)
    pygame.draw.circle(surface, col, (x0 + 8, y), 6)
    tr = draw_text(surface, text, 28, col, (x0 + 26, y), anchor="midleft")
    end = VW - x0
    if right:
        rr = draw_text(surface, right, 22, TEXT_MUTED, (end, y), anchor="midright", bold=False)
        end = rr.x - 16
    if end - tr.right > 40:
        pygame.draw.line(surface, tuple(int(v * 0.55) for v in col), (tr.right + 16, y), (end, y), 2)


def state_pill(surface, r, text, mode):
    """The right-hand state of a row when there is nothing to press: "done" (green) or "locked" (quiet)."""
    edge = (60, 200, 130) if mode == "done" else (52, 64, 92)
    top = (24, 70, 56) if mode == "done" else (20, 26, 42)
    surface.blit(cockpit_surface(r.w, r.h, top, (10, 14, 24), edge, 18), r.topleft)
    if mode == "done":
        cx, cy = r.x + 30, r.centery
        pygame.draw.lines(surface, (255, 255, 255), False, [(cx - 9, cy), (cx - 2, cy + 7), (cx + 10, cy - 7)], 4)
        draw_text(surface, text, 22, (230, 255, 240), (r.centerx + 12, r.centery), max_w=r.w - 56)
    else:
        lx, ly = r.x + 28, r.centery + 2                  # small padlock
        pygame.draw.rect(surface, (100, 115, 150), (lx - 8, ly - 2, 16, 12), border_radius=3)
        pygame.draw.arc(surface, (100, 115, 150), (lx - 6, ly - 12, 12, 14), 0, math.pi, 2)
        draw_text(surface, text, 21, (140, 152, 180), (r.centerx + 12, r.centery), bold=False, max_w=r.w - 56)


class _ClaimMixin:
    """Claim buttons (daily / weekly missions, event tiers) and the running event's reward card - shared by the
    missions screen and the achievements screen. Needs self.save_mgr, self.audio, self.claim_buttons, self._claim_btns."""

    def _click(self):
        if self.audio:
            self.audio.play_sfx("sfx_click")

    def _paid(self, ok):
        if ok:
            self._click()
            if self.audio:
                self.audio.play_sfx("sfx_coin")

    def _claim(self, kind, key):
        def go():
            import events
            if kind == "daily":
                self._paid(self.save_mgr.claim_daily(key))
            elif kind == "weekly":
                self._paid(self.save_mgr.claim_weekly(key))
            else:
                self._paid(events.claim(self.save_mgr, key) is not None)
        return go

    def _button(self, surface, br, kind, key, label=None):
        btn = self._claim_btns.get((kind, key))
        if btn is None:
            btn = self._claim_btns[(kind, key)] = Button((br.x, br.y, br.w, br.h), t("daily_claim"), 24,
                                                         bg_color=(0, 150, 190), hover_color=(40, 200, 235),
                                                         text_color=(255, 255, 255), border_color=(120, 240, 255),
                                                         callback=self._claim(kind, key))
        btn.rect.topleft = br.topleft
        btn.text = label or t("daily_claim")
        btn.draw(surface)
        self.claim_buttons.append(btn)

    def _event(self, surface, y):
        import events
        ev, st = events.state(self.save_mgr)
        if not ev:
            return 0
        col = ev["color"]
        r = pygame.Rect(40, y, VW - 80, 300)
        surface.blit(neon_halo(r.w, r.h, col, 28), (r.x - 12, r.y - 12))
        surface.blit(cockpit_surface(r.w, r.h, (40, 28, 22), (14, 10, 12), col, 28), r.topleft)
        orbit_badge(surface, r.x + 54, r.y + 52, 30, col, "star")
        draw_text(surface, events.name(ev, get_language()).upper(), 34, col, (r.x + 98, r.y + 40), anchor="midleft",
                  max_w=r.w - 330)
        draw_text(surface, t("event_banner", n=ev["days_left"]), 22, (255, 225, 190), (r.right - 30, r.y + 40),
                  anchor="midright", bold=False)
        draw_text(surface, t("event_how"), 21, (200, 185, 175), (r.x + 98, r.y + 76), anchor="midleft", bold=False,
                  max_w=r.w - 130)
        tiers = ev["tiers"]
        top = tiers[-1][0]
        bar = pygame.Rect(r.x + 30, r.y + 112, r.w - 60, 16)
        neon_bar(surface, bar, st["points"] / float(top), col)
        draw_vector_star(surface, bar.x + 12, bar.bottom + 24, radius=12, filled=True)
        draw_text(surface, t("event_points", n=fmt_int(st["points"])), 22, (255, 225, 120), (bar.x + 32, bar.bottom + 24),
                  anchor="midleft")
        tw = (r.w - 60 - 3 * 14) // 4
        for i, (pts, gems, stars) in enumerate(tiers):
            tr_ = pygame.Rect(r.x + 30 + i * (tw + 14), r.y + 168, tw, 116)
            got = i in st["claimed"]
            ready = st["points"] >= pts and not got
            edge = col if ready else ((60, 200, 130) if got else (84, 70, 58))
            if ready:
                surface.blit(neon_halo(tr_.w, tr_.h, col, 18), (tr_.x - 12, tr_.y - 12))
            surface.blit(cockpit_surface(tr_.w, tr_.h, (34, 30, 26) if not got else (20, 46, 38), (12, 10, 12), edge, 18),
                         tr_.topleft)
            draw_text(surface, f"{fmt_int(pts)}", 20, (190, 175, 160), (tr_.centerx, tr_.y + 18), bold=False)
            draw_diamond_icon(surface, tr_.centerx - 30, tr_.y + 46, 11, (0, 230, 255))
            draw_text(surface, f"+{gems}", 22, (130, 235, 255), (tr_.centerx - 16, tr_.y + 46), anchor="midleft")
            if stars and not ready and not got:
                draw_vector_star(surface, tr_.centerx - 30, tr_.y + 80, radius=10, filled=True)
                draw_text(surface, f"+{stars}", 20, (255, 225, 120), (tr_.centerx - 16, tr_.y + 80), anchor="midleft")
            if ready:
                self._button(surface, pygame.Rect(tr_.x + 10, tr_.y + 70, tr_.w - 20, 38), "event", i)
            elif got:
                cx, cy = tr_.centerx, tr_.y + 88
                pygame.draw.lines(surface, (120, 240, 170), False, [(cx - 10, cy), (cx - 3, cy + 7), (cx + 11, cy - 8)], 4)
        return r.h


class AchievementsScreen(_ClaimMixin):
    PER_PAGE = 7
    ROW_H = 158

    def __init__(self, save_manager, on_back, audio_manager=None):
        self.save_mgr = save_manager
        self.on_back = on_back
        self.audio = audio_manager
        self.page = 0
        self.time_val = 0.0
        self.btn_back = back_button(on_back)
        self.btn_prev = Button((40, VH - 96, 260, 76), t("prev_page"), 28, callback=self._prev)
        self.btn_next = Button((VW - 300, VH - 96, 260, 76), t("next_page"), 28, callback=self._next)
        self.claim_buttons = []          # event tier claim buttons shown this frame
        self._claim_btns = {}

    @property
    def per_page(self):
        import events
        return self.PER_PAGE - 2 if events.current() else self.PER_PAGE      # room for the event card

    @property
    def max_pages(self):
        return (len(ach_mod.ACHIEVEMENTS) + self.per_page - 1) // self.per_page

    def refresh_texts(self):
        self.btn_back.text = t("back")
        self.btn_prev.text = t("prev_page")
        self.btn_next.text = t("next_page")

    def _prev(self):
        self.page = max(0, self.page - 1)

    def _next(self):
        self.page = min(self.max_pages - 1, self.page + 1)

    def update(self, mouse_pos, dt=1.0):
        self.time_val += 0.04 * dt
        for b in (self.btn_back, self.btn_prev, self.btn_next, *self.claim_buttons):
            b.update(mouse_pos, dt)

    def handle_event(self, event):
        if self.btn_back.handle_event(event):
            return self.on_back
        for b in self.claim_buttons:
            if b.handle_event(event):
                return b.callback
        if self.page > 0 and self.btn_prev.handle_event(event):
            return self._prev
        if self.page < self.max_pages - 1 and self.btn_next.handle_event(event):
            return self._next
        return None

    def draw(self, surface):
        sm = self.save_mgr
        got = ach_mod.unlocked_ids(sm)
        header(surface, t("ach_title"), self.btn_back, None)
        draw_text(surface, f"{len(got)} / {len(ach_mod.ACHIEVEMENTS)}", 34, (170, 232, 255), (VW // 2, 156))
        self.claim_buttons = []
        self.page = min(self.page, self.max_pages - 1)
        per = self.per_page
        items = ach_mod.ACHIEVEMENTS[self.page * per:(self.page + 1) * per]
        y = 190
        h = self._event(surface, y)
        y += h + 20 if h else 10
        for a in items:
            done = a[0] in got
            cur, tot = ach_mod.progress(sm, a)
            r = pygame.Rect(40, y, VW - 80, self.ROW_H - 18)
            theme_card(surface, r, ACCENT_CYAN, "done" if done else "idle")
            orbit_badge(surface, r.x + 70, r.centery, 42, ACCENT_GOLD if done else ACCENT_CYAN,
                        "star", lit=done or cur > 0)
            tx = r.x + 136
            draw_text(surface, ach_mod.title(a), 32, TEXT_WHITE if done else (205, 210, 232), (tx, r.y + 38),
                      anchor="midleft", max_w=r.w - 180)
            draw_text(surface, ach_mod.desc(a), 23, (170, 180, 215), (tx, r.y + 74), anchor="midleft", bold=False,
                      max_w=r.w - 180)
            bar = pygame.Rect(tx, r.y + 100, r.w - 136 - 120, 14)
            neon_bar(surface, bar, 1.0 if done else cur / float(max(1, tot)), ACCENT_CYAN, done=done)
            if done:
                draw_vector_star(surface, bar.right + 46, bar.centery, radius=13, filled=True)
            else:
                draw_text(surface, f"{cur}/{tot}", 20, (205, 215, 240), (bar.right + 52, bar.centery), bold=False)
            y += self.ROW_H
        if self.page > 0:
            self.btn_prev.draw(surface)
        if self.page < self.max_pages - 1:
            self.btn_next.draw(surface)
        draw_text(surface, t("page_indicator", cur=self.page + 1, total=self.max_pages), 26, TEXT_MUTED, (VW // 2, VH - 58), bold=False)


# ======================================================================================== daily missions
class DailyMissionsScreen(_ClaimMixin):
    """The missions screen (menu: DAILY): today's 3 missions and this week's 3 bigger ones (daily_missions.py,
    weekly_missions.py). Claiming pays diamonds through the wallet. The seasonal event is on the achievements screen."""
    ROW_H = 150

    def __init__(self, save_manager, on_back, audio_manager=None):
        self.save_mgr = save_manager
        self.on_back = on_back
        self.audio = audio_manager
        self.time_val = 0.0
        self.btn_back = back_button(on_back)
        self.claim_buttons = []          # the claim buttons shown this frame
        self._claim_btns = {}            # key -> Button, kept across frames so a touch that starts in one
                                         # frame and ends in a later one still counts as a press

    def refresh_texts(self):
        self.btn_back.text = t("back")

    def update(self, mouse_pos, dt=1.0):
        self.time_val += 0.04 * dt
        self.btn_back.update(mouse_pos, dt)
        for b in self.claim_buttons:
            b.update(mouse_pos, dt)

    def handle_event(self, event):
        if self.btn_back.handle_event(event):
            return self.on_back
        for b in self.claim_buttons:
            if b.handle_event(event):
                return b.callback
        return None

    def _row(self, surface, y, kind, m, cur, got, accent):
        tot = m["target"]
        done_full = cur >= tot
        r = pygame.Rect(40, y, VW - 80, self.ROW_H - 18)
        mode = "done" if got else ("ready" if done_full else "idle")
        theme_card(surface, r, accent, mode)
        orbit_badge(surface, r.x + 66, r.centery, 40, (60, 210, 130) if got else accent, "check" if got else "gem",
                    lit=got or done_full or cur > 0)
        tx = r.x + 128
        draw_text(surface, t(m["label_key"], n=fmt_int(tot)), 28, TEXT_WHITE, (tx, r.y + 34), anchor="midleft",
                  max_w=r.w - 350)
        draw_diamond_icon(surface, tx + 10, r.y + 68, 10, (0, 230, 255))
        draw_text(surface, t("daily_reward", n=m["reward"]), 21, (255, 215, 120), (tx + 26, r.y + 68), anchor="midleft",
                  bold=False, max_w=r.w - 380)
        bar = pygame.Rect(tx, r.y + 94, r.w - 128 - 230, 14)
        neon_bar(surface, bar, cur / float(max(1, tot)), accent, done=done_full)
        draw_text(surface, f"{fmt_int(min(cur, tot))}/{fmt_int(tot)}", 20, (205, 215, 240), (bar.right, bar.y - 12),
                  anchor="bottomright", bold=False)
        br = pygame.Rect(r.right - 210, r.centery - 34, 186, 68)
        if got:
            state_pill(surface, br, t("owned"), "done")
        elif done_full:
            self._button(surface, br, kind, m["id"])
        else:
            state_pill(surface, br, t("locked"), "locked")

    def draw(self, surface):
        sm = self.save_mgr
        header(surface, t("goals_title"), self.btn_back, None)
        self.claim_buttons = []
        missions, progress, claimed, streak = sm.daily_missions()
        y = 166
        section_title(surface, y, t("daily_section"), ACCENT_CYAN, t("daily_streak", n=streak) if streak > 0 else None)
        y += 30
        for m in missions:
            self._row(surface, y, "daily", m, progress.get(m["metric"], 0), m["id"] in claimed, (0, 220, 255))
            y += self.ROW_H
        import weekly_missions as wm
        wmissions, wprogress, wclaimed = sm.weekly_missions()
        y += 18
        section_title(surface, y, t("weekly_section"), ACCENT_GOLD, t("weekly_left", n=wm.days_left()))
        y += 30
        for m in wmissions:
            self._row(surface, y, "weekly", m, wprogress.get(m["metric"], 0), m["id"] in wclaimed, ACCENT_GOLD)
            y += self.ROW_H


# ======================================================================================== level select
class LevelSelectScreen:
    COLS, CARD, GAP, SEC_H = 4, 190, 20, 150

    def __init__(self, save_manager, on_select_level, on_back):
        self.save_mgr = save_manager
        self.on_select_level = on_select_level
        self.on_back = on_back
        self.btn_back = back_button(on_back)
        self.scroll = Scroller()
        self.anim = 0.0
        self.top = 150
        self.sec_block = self.SEC_H + 5 * (self.CARD + self.GAP) + 30
        self.refresh_content_height()
        self.margin = (VW - (self.COLS * self.CARD + (self.COLS - 1) * self.GAP)) // 2

    def refresh_texts(self):
        self.btn_back.text = t("back")

    def refresh_content_height(self):
        unlocked = self.save_mgr.unlocked_level
        full_sectors, last_index = divmod(unlocked - 1, 20)
        rows = (last_index + 1 + self.COLS - 1) // self.COLS
        self.content_h = full_sectors * self.sec_block + self.SEC_H + rows * (self.CARD + self.GAP) + 30

    def focus_level(self, lvl):
        self.refresh_content_height()
        lvl = max(1, min(lvl, self.save_mgr.unlocked_level))
        s = (lvl - 1) // 20
        idx = (lvl - 1) % 20
        row = idx // self.COLS
        y = s * self.sec_block + self.SEC_H + row * (self.CARD + self.GAP)
        view = VH - self.top
        self.scroll.y = max(0, min(self.content_h - view, y - view * 0.35))
        self.scroll.vel = 0

    def set_sector(self, s):
        self.scroll.y = (s - 1) * self.sec_block

    def card_rect(self, lvl):
        s = (lvl - 1) // 20
        idx = (lvl - 1) % 20
        col, row = idx % self.COLS, idx // self.COLS
        x = self.margin + col * (self.CARD + self.GAP)
        y = s * self.sec_block + self.SEC_H + row * (self.CARD + self.GAP)
        return pygame.Rect(x, int(self.top + y - self.scroll.y), self.CARD, self.CARD)

    def update(self, mouse_pos, dt=1.0):
        self.anim += 0.03 * dt
        self.btn_back.update(mouse_pos, dt)
        self.refresh_content_height()
        self.scroll.update(self.content_h, VH - self.top, dt)

    def handle_event(self, event):
        if self.btn_back.handle_event(event):
            return self.on_back
        if event.type == pygame.MOUSEWHEEL:
            self.scroll.wheel(event.y)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and event.pos[1] > self.top:
            self.scroll.on_down(event.pos)
        elif event.type == pygame.MOUSEMOTION and event.buttons[0]:
            self.scroll.on_move(event.pos)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            tap = self.scroll.on_up(event.pos)
            if tap and tap[1] > self.top:
                unlocked = self.save_mgr.unlocked_level
                for lvl in range(1, unlocked + 1):
                    if self.card_rect(lvl).collidepoint(tap) and lvl <= unlocked:
                        return lambda l=lvl: self.on_select_level(l)
        return None

    def draw(self, surface):
        clip = pygame.Rect(0, self.top, VW, VH - self.top)
        surface.set_clip(clip)
        sm = self.save_mgr
        for s in range(1, (sm.unlocked_level - 1) // 20 + 2):
            base = self.top + (s - 1) * self.sec_block - self.scroll.y
            if base > VH or base + self.sec_block < self.top:
                continue
            col = SECTOR_COL[s]
            done = sum(1 for l in range((s - 1) * 20 + 1, s * 20 + 1) if sm.get_level_stars(l) > 0)
            hr = pygame.Rect(self.margin, int(base + 10), VW - 2 * self.margin, self.SEC_H - 30)
            panel(surface, hr, (18, 22, 34), col, 20, 2)
            draw_text(surface, f"{t('sector')} {s} • {SECTOR_NAMES[s]}", 40, col, (hr.x + 28, hr.y + 40), anchor="midleft", max_w=hr.w - 380)
            draw_text(surface, t(f"sector_desc_{s}"), 24, TEXT_MUTED, (hr.x + 28, hr.y + 84), anchor="midleft", bold=False, max_w=hr.w - 380)
            surface.blit(sector_icon(s, 110), (hr.right - 250, hr.centery - 55))
            draw_text(surface, f"{done}/20", 46, TEXT_WHITE, (hr.right - 30, hr.centery), anchor="midright")
        unlocked = sm.unlocked_level
        current = sm.campaign_level
        for lvl in range(1, unlocked + 1):
            r = self.card_rect(lvl)
            if r.bottom < self.top or r.top > VH:
                continue
            sec_col = SECTOR_COL[(lvl - 1) // 20 + 1]
            if lvl <= unlocked:
                stars = sm.get_level_stars(lvl)
                is_cur = lvl == min(unlocked, current)
                panel(surface, r, (22, 30, 48), sec_col if is_cur else (48, 62, 92), 20, 3 if is_cur else 2)
                if is_cur:
                    pulse = 1.0                         # steady: the screen is shown from a cached frame
                    pygame.draw.rect(surface, tuple(int(c * pulse) for c in sec_col), r.inflate(8, 8), 2, border_radius=24)
                draw_text(surface, f"{lvl}", 62, sec_col if is_cur else TEXT_WHITE, (r.centerx, r.y + 62))
                for i in range(3):
                    draw_vector_star(surface, r.centerx - 44 + i * 44, r.y + 122, radius=17, filled=i < stars)
                best_score = sm.get_level_best_score(lvl)
                if stars:
                    draw_text(surface, f"{best_score:,}", 24, (160, 220, 255), (r.centerx, r.bottom - 26), bold=False)
                else:
                    draw_text(surface, t("play"), 26, sec_col, (r.centerx, r.bottom - 26))
            else:
                panel(surface, r, (14, 17, 26), (30, 35, 50), 20, 2)
                draw_text(surface, f"{lvl}", 46, (60, 70, 92), (r.centerx, r.y + 58))
                cx, cy = r.centerx, r.y + 118
                pygame.draw.arc(surface, (90, 100, 125), (cx - 16, cy - 30, 32, 30), 0, math.pi, 4)
                pygame.draw.rect(surface, (64, 74, 98), (cx - 20, cy - 10, 40, 32), border_radius=6)
                pygame.draw.circle(surface, (20, 25, 38), (cx, cy + 5), 5)
        surface.set_clip(None)

        pygame.draw.rect(surface, (10, 12, 18), (0, 0, VW, self.top))
        pygame.draw.line(surface, (40, 55, 80), (0, self.top), (VW, self.top), 2)
        header(surface, t("level_select"), self.btn_back, f"{sm.get_total_stars()}")


# ============================================================================================ leaderboard
class LeaderboardScreen:
    ROW_H = 112
    _ROWS = {}                  # rendered ranking rows (see _row_sprite)

    def __init__(self, save_manager, on_back, on_edit_profile=None, online=None):
        self.save_mgr = save_manager
        self.on_back = on_back
        self.on_edit_profile = on_edit_profile
        self.online = online
        self.btn_back = back_button(on_back)
        self.scope = "global"
        self.scroll = Scroller()
        self.top = 300
        self.bottom_h = 290
        self.tabs = []
        self.btn_refresh = Button((VW - 200, 34, 170, 88), t("refresh"), 30, callback=self.refresh)
        self.btn_profile = Button((VW // 2 - 240, VH - 150, 480, 84), t("profile_btn"), 30, callback=on_edit_profile)
        self._build_tabs()

    def _build_tabs(self):
        names = [("global", t("tab_world")), ("country", t("tab_country")), ("around", t("tab_around")),
                 ("endless", t("tab_endless"))]
        w = (VW - 80 - 3 * 12) // 4
        self.tabs = [(k, Button((40 + i * (w + 12), 172, w, 84), n, 26,
                                bg_color=(30, 58, 92) if k == self.scope else BTN_NORMAL,
                                border_color=ACCENT_CYAN if k == self.scope else BORDER_COLOR,
                                callback=lambda k=k: self.set_scope(k))) for i, (k, n) in enumerate(names)]

    def refresh_texts(self):
        self.btn_back.text = t("back")
        self.btn_refresh.text = t("refresh")
        self.btn_profile.text = t("profile_btn")
        self._build_tabs()

    def on_open(self):
        self.scroll.y = 0
        self.refresh()

    def set_scope(self, scope):
        self.scope = scope
        self.scroll.y = 0
        self._build_tabs()
        self.refresh()

    def refresh(self):
        if self.online:
            self.online.flush_pending()
            # "around me": just the 5 pilots right above and the 5 right below you, so it differs from the world list
            self.online.fetch(self.scope, limit=11 if self.scope == "around" else 100)

    def update(self, mouse_pos, dt=1.0):
        self.btn_back.update(mouse_pos, dt)
        self.btn_refresh.update(mouse_pos, dt)
        for _, b in self.tabs:
            b.update(mouse_pos, dt)
        if self.on_edit_profile:
            self.btn_profile.update(mouse_pos, dt)
        rows = self._rows()
        self.scroll.update(len(rows) * self.ROW_H + 20, VH - self.top - self.bottom_h, dt)

    def _rows(self):
        if self.online:
            board = self.online.boards.get(self.scope)
            if board and board.get("rows"):
                return board["rows"]
        return []

    def handle_event(self, event):
        if self.btn_back.handle_event(event):
            return self.on_back
        if self.btn_refresh.handle_event(event):
            return self.refresh
        for k, b in self.tabs:
            if b.handle_event(event):
                return b.callback
        if self.on_edit_profile and self.btn_profile.handle_event(event):
            return self.on_edit_profile
        if event.type == pygame.MOUSEWHEEL:
            self.scroll.wheel(event.y)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.top < event.pos[1] < VH - self.bottom_h:
            self.scroll.on_down(event.pos)
        elif event.type == pygame.MOUSEMOTION and event.buttons[0]:
            self.scroll.on_move(event.pos)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.scroll.on_up(event.pos)
        return None

    def _row_sprite(self, e, i, is_me, w):
        """One ranking row rendered once into an opaque sprite (a dozen texts, a flag and a rounded panel per row
        every frame made this screen the slowest one); the key holds everything drawn, so new data redraws it."""
        rk = e.get("rank", i + 1)
        endless = "metres" in e
        key = (w, rk, i % 2, is_me, e.get("country", "GX"), e.get("name", "---"), e.get("levels", 0), e.get("stars", 0),
               e.get("score", 0), e.get("metres"))
        cache = LeaderboardScreen._ROWS
        spr = cache.get(key)
        if spr is not None:
            return spr
        h = self.ROW_H - 12
        spr = gfx.cv(pygame.Surface((w, h)))
        spr.fill((16, 20, 32))                      # the list panel behind the rounded corners
        r = spr.get_rect()
        pygame.draw.rect(spr, (34, 52, 84) if is_me else ((26, 34, 54) if i % 2 == 0 else (20, 27, 42)), r, border_radius=14)
        if is_me:
            pygame.draw.rect(spr, ACCENT_CYAN, r, 2, border_radius=14)
        rc = ACCENT_GOLD if rk == 1 else ((205, 220, 240) if rk == 2 else ((200, 135, 75) if rk == 3 else TEXT_MUTED))
        draw_text(spr, f"{rk}", 36 if rk < 1000 else 28, rc, (r.x + 48, r.centery))
        draw_country_badge(spr, e.get("country", "GX"), r.x + 158, r.centery, width=96, height=42)
        if endless:
            draw_text(spr, e.get("name", "---"), 34, TEXT_WHITE, (r.x + 230, r.centery), anchor="midleft", max_w=330)
            draw_text(spr, fmt_int(e.get("points", e.get("metres", 0))), 34, ACCENT_GOLD, (r.right - 20, r.centery), anchor="midright")
            if len(cache) > 400:
                cache.clear()
            cache[key] = spr
            return spr
        draw_text(spr, e.get("name", "---"), 34, TEXT_WHITE, (r.x + 230, r.centery), anchor="midleft", max_w=220)
        draw_text(spr, f"{e.get('levels', 0)}", 40, ACCENT_CYAN, (r.right - 215, r.centery - 8))
        draw_text(spr, f"{e.get('stars', 0)}", 22, ACCENT_GOLD, (r.right - 205, r.centery + 26), anchor="midleft", bold=False)
        draw_vector_star(spr, r.right - 226, r.centery + 26, radius=9, filled=True)
        draw_text(spr, fmt_int(e.get("score", 0)), 30, ACCENT_GOLD, (r.right - 20, r.centery), anchor="midright")
        if len(cache) > 400:
            cache.clear()
        cache[key] = spr
        return spr

    def draw(self, surface):
        on = self.online
        board = on.boards.get(self.scope) if on else None
        rows = self._rows()
        me_id = self.save_mgr.player_id

        # list
        view = pygame.Rect(30, self.top, VW - 60, VH - self.top - self.bottom_h)
        panel(surface, view, (16, 20, 32), (45, 65, 100), 20, 2)
        surface.set_clip(view.inflate(-4, -4))
        # column header
        hy = self.top + 8
        draw_text(surface, "#", 24, ACCENT_CYAN, (view.x + 60, hy + 22))
        draw_text(surface, t("col_player"), 24, ACCENT_CYAN, (view.x + 250, hy + 22), anchor="midleft")
        if self.scope == "endless":
            draw_text(surface, t("col_height"), 24, ACCENT_CYAN, (view.right - 80, hy + 22))
        else:
            draw_text(surface, t("col_level"), 24, ACCENT_CYAN, (view.right - 220, hy + 22))
            draw_text(surface, t("col_score"), 24, ACCENT_CYAN, (view.right - 80, hy + 22))
        base = hy + 52
        for i, e in enumerate(rows):
            y = int(base + i * self.ROW_H - self.scroll.y)
            if y + self.ROW_H < self.top or y > VH - self.bottom_h:
                continue
            is_me = bool(e.get("me") or e.get("id") == me_id)
            surface.blit(self._row_sprite(e, i, is_me, view.w - 24), (view.x + 12, y))
        surface.set_clip(None)

        if not rows:
            msg = t("loading")
            if on:
                if on.is_loading(self.scope):
                    pass
                elif on.status == "offline":
                    msg = t("offline")
                elif on.status == "disabled":
                    msg = t("online_disabled")
                elif board is not None:
                    msg = t("lb_empty")
            draw_text(surface, msg, 34, TEXT_MUTED, (VW // 2, self.top + 240), max_w=760)

        # own standing (pinned)
        me = board.get("me") if board else None
        by = VH - self.bottom_h + 16
        mp = pygame.Rect(30, by, VW - 60, 100)
        panel(surface, mp, (26, 44, 72), ACCENT_CYAN, 18, 2)
        sm = self.save_mgr
        draw_country_badge(surface, sm.player_country, mp.x + 80, mp.centery, width=96, height=42)
        draw_text(surface, sm.player_name, 34, TEXT_WHITE, (mp.x + 150, mp.centery - 16), anchor="midleft", max_w=250)
        if self.scope == "endless":
            wk = (board or {}).get("week", "")
            mine = (me or {}).get("points") or (me or {}).get("metres") or int(sm.endless.get("best_all", 0))
            draw_text(surface, f"{t('endless_week_short')}  •  {fmt_int(mine or 0)}", 26, ACCENT_GOLD,
                      (mp.x + 150, mp.centery + 22), anchor="midleft", bold=False)
        else:
            # the ranking's own numbers when it has them (a clear it never verified is not in them - see below)
            lv_ = me.get("levels", sm.levels_cleared) if me and me.get("rank") else sm.levels_cleared
            sc_ = me.get("score", sm.total_score) if me and me.get("rank") else sm.total_score
            draw_text(surface, f"{t('col_level')} {lv_}  •  {fmt_int(sc_)}", 26, ACCENT_GOLD,
                      (mp.x + 150, mp.centery + 22), anchor="midleft", bold=False)
        if me and me.get("rank"):
            draw_text(surface, f"#{fmt_int(me['rank'])}", 46, ACCENT_CYAN, (mp.right - 24, mp.centery), anchor="midright")
        else:
            draw_text(surface, "#-", 46, TEXT_MUTED, (mp.right - 24, mp.centery), anchor="midright")
        if self.on_edit_profile:
            self.btn_profile.rect.y = VH - 150
            self.btn_profile.draw(surface)

        pygame.draw.rect(surface, (10, 12, 18), (0, 0, VW, self.top - 10))
        header(surface, t("lb_title"), self.btn_back)
        self.btn_refresh.draw(surface)
        for _, b in self.tabs:
            b.draw(surface)
        if on:
            status = "loading" if on.is_loading(self.scope) else on.status
            st = {"ok": t("status_online"), "loading": t("loading"), "offline": t("status_offline"),
                  "disabled": t("online_disabled"), "idle": ""}.get(status, "")
            col = ACCENT_GREEN if status == "ok" else (255, 160, 90 if status != "loading" else 200)
            draw_text(surface, st, 24, col, (VW // 2, 280), bold=False)


# ================================================================================================ skins
class SkinScreen:
    """Collection browser: 15 catalogues, one per page, 5 skins each from Legendary (top) to Common (bottom)."""
    ROW_H, ROW_GAP, ROWS_Y = 132, 10, 770

    def __init__(self, save_manager, on_back, audio_manager=None, on_shop=None):
        self.save_mgr = save_manager
        self.on_back = on_back
        self.on_shop = on_shop
        self.audio = audio_manager
        self.time_val = 0.0
        self.selected_skin = save_manager.equipped_skin
        self.cat = catalog.theme_index(self.selected_skin)
        self.max_pages = len(catalog.THEMES)
        self.btn_back = back_button(on_back)
        self.equip_button = Button((VW // 2 - 220, 556, 440, 88), "", 34, callback=self._equip_selected)
        self.btn_prev = Button((30, VH - 96, 300, 76), "", 24, callback=self._prev)
        self.btn_next = Button((VW - 330, VH - 96, 300, 76), "", 24, callback=self._next)

    def refresh_texts(self):
        self.btn_back.text = t("back")

    def open_at(self, sid):
        self.selected_skin = sid
        self.cat = catalog.theme_index(sid)

    def _click(self):
        if self.audio:
            self.audio.play_sfx("sfx_click")

    def _prev(self):
        self.cat = (self.cat - 1) % self.max_pages
        self.selected_skin = catalog.THEMES[self.cat][2][0]
        self._click()

    def _next(self):
        self.cat = (self.cat + 1) % self.max_pages
        self.selected_skin = catalog.THEMES[self.cat][2][0]
        self._click()

    def _equip_selected(self):
        sid = self.selected_skin
        sm = self.save_mgr
        if sm.is_skin_unlocked(sid):
            sm.equipped_skin = sid
            if self.audio:
                self.audio.play_sfx("sfx_swap")
            return
        kind, val = catalog.source(sid)
        if kind == "star":
            if sm.spend_star_coins(val):
                sm.grant_skin(sid)
                sm.equipped_skin = sid
                if self.audio:
                    self.audio.play_sfx("sfx_star")
            return
        if kind == "shop":
            if sm.diamonds >= val:
                def paid(ok, _reason, sid=sid):
                    if ok:
                        sm.grant_skin(sid)
                        sm.equipped_skin = sid
                        if self.audio:
                            self.audio.play_sfx("sfx_coin")
                sm.spend("skin:" + sid, val, paid)
            elif self.on_shop:
                self._click()
                self.on_shop()

    def _members(self):
        return catalog.THEMES[self.cat][2]

    def _rect(self, slot):
        return pygame.Rect(40, self.ROWS_Y + slot * (self.ROW_H + self.ROW_GAP), VW - 80, self.ROW_H)

    def update(self, mouse_pos, dt=1.0):
        self.time_val += 0.035 * dt
        for b in (self.btn_back, self.equip_button, self.btn_prev, self.btn_next):
            b.update(mouse_pos, dt)

    def handle_event(self, event):
        if self.btn_back.handle_event(event):
            return self.on_back
        if self.equip_button.handle_event(event):
            return self._equip_selected
        if self.btn_prev.handle_event(event):
            return self._prev
        if self.btn_next.handle_event(event):
            return self._next
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._swipe_from = event.pos
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            start, self._swipe_from = getattr(self, "_swipe_from", None), None
            if start is not None and start[1] > self.ROWS_Y - 80:
                dx, dy = event.pos[0] - start[0], event.pos[1] - start[1]
                if abs(dx) > 110 and abs(dx) > 1.6 * abs(dy):          # a sideways swipe flips the catalogue
                    return self._next if dx < 0 else self._prev
            for slot, sid in enumerate(self._members()):
                if self._rect(slot).collidepoint(event.pos):
                    self.selected_skin = sid
                    return self._click
        return None

    def _source_pill(self, surface, r, sid, un):
        """Right side of a row: owned / level / achievement / diamonds."""
        kind, val = catalog.source(sid)
        pill = pygame.Rect(0, 0, 210, 44)
        pill.midright = (r.right - 22, r.centery + 26)
        if un:
            pygame.draw.rect(surface, (60, 150, 110), pill, border_radius=22)
            draw_text(surface, t("equipped") if self.save_mgr.equipped_skin == sid else t("owned"), 22, (255, 255, 255), pill.center)
        elif kind == "level":
            pygame.draw.rect(surface, (34, 60, 44), pill, border_radius=22)
            pygame.draw.rect(surface, (90, 220, 130), pill, 2, border_radius=22)
            draw_text(surface, t("src_level", n=val), 22, (150, 245, 180), pill.center)
        elif kind == "star":
            pygame.draw.rect(surface, (58, 46, 16), pill, border_radius=22)
            pygame.draw.rect(surface, ACCENT_GOLD, pill, 2, border_radius=22)
            draw_vector_star(surface, pill.centerx - 44, pill.centery, radius=12, filled=True)
            draw_text(surface, f"{val}", 24, (255, 240, 190), (pill.centerx + 6, pill.centery))
        elif kind == "ach":
            a = ach_mod.BY_ID.get(val)
            pygame.draw.rect(surface, (64, 50, 24), pill, border_radius=22)
            pygame.draw.rect(surface, (255, 200, 90), pill, 2, border_radius=22)
            draw_text(surface, ach_mod.title(a) if a else t("src_ach"), 20, (255, 220, 140), pill.center, max_w=196)
        else:
            pygame.draw.rect(surface, (30, 60, 95), pill, border_radius=22)
            pygame.draw.rect(surface, (0, 220, 255), pill, 2, border_radius=22)
            draw_diamond_icon(surface, pill.centerx - 44, pill.centery, 10, (0, 230, 255))
            draw_text(surface, f"{val}", 24, (220, 245, 255), (pill.centerx + 6, pill.centery))

    def draw_dynamic(self, surface):
        sk = SKINS.get(self.selected_skin, SKINS["neon_pulse"])
        cx, cy, d = VW // 2, 292, 100
        p1 = (cx + math.cos(self.time_val) * d, cy + math.sin(self.time_val) * d * 0.8)
        p2 = (cx + math.cos(self.time_val + math.pi) * d, cy + math.sin(self.time_val + math.pi) * d * 0.8)
        draw_tether(surface, p1, p2, sk, self.time_val)
        draw_orb(surface, p1, 26, sk["color1"], sk["glow1"], False, sk, self.time_val)
        draw_orb(surface, p2, 26, sk["color2"], sk["glow2"], True, sk, self.time_val)

    def draw(self, surface):
        sm = self.save_mgr
        lang = get_language()
        star_page = self.cat == catalog.STAR_THEME
        # the star pill is the endless star wallet - shown only on the Yıldız Avcısı page, where stars buy skins
        header(surface, t("skins_title"), self.btn_back, f"{sm.star_coins}" if star_page else None)
        draw_diamond_badge(surface, VW - 225 if star_page else VW - 100, 122, sm.diamonds)
        sid = self.selected_skin
        sk = SKINS.get(sid, SKINS["neon_pulse"])
        tier = catalog.tier(sid)
        tcol = catalog.TIERS[tier]["color"]
        panel_r = pygame.Rect(40, 170, VW - 80, 372)
        surface.blit(neon_halo(panel_r.w, panel_r.h, tcol, 26), (panel_r.x - 12, panel_r.y - 12))
        surface.blit(cockpit_surface(panel_r.w, panel_r.h, (22, 28, 50), (6, 8, 20), tcol, 26), panel_r.topleft)
        cx = VW // 2
        if not getattr(self, "_static", False):
            self.draw_dynamic(surface)
        draw_text(surface, catalog.tier_name(tier, lang), 22, tcol, (cx, 412))
        draw_text(surface, sk["name"], 44, TEXT_WHITE, (cx, 452))
        draw_text(surface, skin_text.desc(sid, sk), 24, TEXT_MUTED, (cx, 500), bold=False, max_w=760)

        unlocked = sm.is_skin_unlocked(sid)
        equipped = sm.equipped_skin == sid
        eb = self.equip_button
        kind, val = catalog.source(sid)
        unit = t("diamonds").upper()
        if equipped:
            eb.text, eb.bg_color, eb.hover_color, eb.text_color = t("equipped"), (35, 200, 120), (80, 230, 160), (255, 255, 255)
        elif unlocked:
            eb.text, eb.bg_color, eb.hover_color, eb.text_color = t("equip"), (96, 140, 255), (140, 176, 255), (255, 255, 255)
        elif kind == "star":
            if sm.star_coins >= val:
                eb.text, eb.bg_color, eb.hover_color, eb.text_color = t("buy_for_stars", n=val), (230, 170, 30), (255, 205, 80), (255, 255, 255)
            else:
                eb.text, eb.bg_color, eb.hover_color, eb.text_color = t("need_stars", n=val - sm.star_coins), (70, 60, 40), (90, 78, 52), (255, 225, 150)
        elif kind == "shop":
            if sm.diamonds >= val:
                eb.text, eb.bg_color, eb.hover_color, eb.text_color = f"{t('buy_for_diamonds')}  {val} {unit}", (0, 180, 220), (40, 220, 255), (255, 255, 255)
            else:
                eb.text, eb.bg_color, eb.hover_color, eb.text_color = f"{val} {unit} • {t('shop_open')}", (255, 170, 40), (255, 205, 100), (255, 255, 255)
        else:
            eb.text, eb.bg_color, eb.hover_color, eb.text_color = t("locked"), (70, 52, 66), (90, 66, 82), (230, 150, 170)
        eb.draw(surface)
        if not unlocked:
            draw_text(surface, sm.unlock_text(sid), 24, (230, 150, 160), (VW // 2, 664), bold=False, max_w=820)

        # catalogue title + rows (Legendary at the top ... Common at the bottom)
        members = self._members()
        owned_n = sum(1 for m in members if sm.is_skin_unlocked(m))
        name = catalog.theme_name(self.cat, lang).upper()
        draw_text(surface, name, 38, ACCENT_CYAN, (VW // 2, 712))
        sub = f"{t('catalog_word')} {self.cat + 1}/{self.max_pages}   •   {owned_n}/5"
        if star_page:
            sub = t("star_page_hint")
        draw_text(surface, sub, 22, ACCENT_GOLD if star_page else TEXT_MUTED, (VW // 2, 746), bold=False, max_w=VW - 80)
        for slot, m in enumerate(members):
            s = SKINS[m]
            r = self._rect(slot)
            un = sm.is_skin_unlocked(m)
            sel = m == sid
            tc = catalog.TIERS[catalog.tier(m)]["color"]
            edge = tc if sel else tuple(int(c * 0.5) for c in tc)
            if sel:
                surface.blit(neon_halo(r.w, r.h, tc, 20), (r.x - 12, r.y - 12))
            surface.blit(cockpit_surface(r.w, r.h, (30, 40, 66) if sel else ((22, 28, 48) if un else (14, 16, 26)),
                                         (8, 10, 22), edge, 20), r.topleft)
            pygame.draw.rect(surface, tc, (r.x + 14, r.y + 18, 6, r.h - 36), border_radius=3)
            draw_text(surface, catalog.tier_name(catalog.tier(m), lang), 18, tc, (r.x + 40, r.y + 28), anchor="midleft", bold=True)
            draw_text(surface, s["name"], 28, TEXT_WHITE if un else (170, 178, 196), (r.x + 40, r.y + 64), anchor="midleft", max_w=300)
            mx, my = r.x + 450, r.centery - 2
            thumb = skin_thumbnail(m, width=150, height=80, radius=18)
            surface.blit(thumb, thumb.get_rect(center=(mx, my)))
            self._source_pill(surface, r, m, un)
        self.btn_prev.text = "<  " + catalog.theme_name((self.cat - 1) % self.max_pages, lang)
        self.btn_next.text = catalog.theme_name((self.cat + 1) % self.max_pages, lang) + "  >"
        self.btn_prev.draw(surface)
        self.btn_next.draw(surface)
        n = self.max_pages
        gap = min(18, 300 // max(1, n))
        x0 = VW // 2 - (n - 1) * gap // 2
        for i in range(n):
            on = i == self.cat
            pygame.draw.circle(surface, ACCENT_CYAN if on else (60, 78, 112), (x0 + i * gap, VH - 74), 6 if on else 4)
        draw_text(surface, f"{self.cat + 1} / {n}", 22, TEXT_MUTED, (VW // 2, VH - 44), bold=False)


# ================================================================================================ shop
def _icon_coffee(s, cx, cy, k):
    pygame.draw.rect(s, (255, 255, 255), (cx - 20 * k, cy - 8 * k, 36 * k, 30 * k), border_radius=int(8 * k))
    pygame.draw.arc(s, (255, 255, 255), (cx + 10 * k, cy - 2 * k, 20 * k, 18 * k), -1.5, 1.5, max(2, int(4 * k)))
    for i in (-10, 0, 10):
        pygame.draw.line(s, (255, 255, 255), (cx + i * k, cy - 14 * k), (cx + (i + 3) * k, cy - 26 * k), max(2, int(3 * k)))


def _icon_cake(s, cx, cy, k):
    pygame.draw.polygon(s, (255, 255, 255), [(cx - 24 * k, cy + 18 * k), (cx + 24 * k, cy + 18 * k), (cx + 24 * k, cy - 6 * k), (cx - 24 * k, cy + 4 * k)])
    pygame.draw.polygon(s, (255, 150, 190), [(cx - 24 * k, cy + 4 * k), (cx + 24 * k, cy - 6 * k), (cx + 24 * k, cy - 1 * k), (cx - 24 * k, cy + 10 * k)])
    pygame.draw.circle(s, (255, 70, 110), (int(cx), int(cy - 12 * k)), max(3, int(6 * k)))


def _icon_rocket(s, cx, cy, k):
    pygame.draw.polygon(s, (255, 255, 255), [(cx, cy - 28 * k), (cx + 12 * k, cy - 6 * k), (cx + 12 * k, cy + 14 * k), (cx - 12 * k, cy + 14 * k), (cx - 12 * k, cy - 6 * k)])
    pygame.draw.polygon(s, (255, 130, 160), [(cx - 12 * k, cy + 4 * k), (cx - 24 * k, cy + 18 * k), (cx - 12 * k, cy + 14 * k)])
    pygame.draw.polygon(s, (255, 130, 160), [(cx + 12 * k, cy + 4 * k), (cx + 24 * k, cy + 18 * k), (cx + 12 * k, cy + 14 * k)])
    pygame.draw.circle(s, (120, 190, 255), (int(cx), int(cy - 6 * k)), max(3, int(6 * k)))
    pygame.draw.polygon(s, (255, 210, 90), [(cx - 6 * k, cy + 14 * k), (cx + 6 * k, cy + 14 * k), (cx, cy + 28 * k)])


class ShopScreen:
    """Diamonds are the shop currency. One scrolling page (1.0.6): the selected skin's preview and buy buttons stay at
    the top, below them every shop skin, the diamond packs and the shield scroll in one list. The list is rendered
    into one surface and only re-rendered when what it shows changes - scrolling just copies a window of it."""
    COLS, CARD_W, CARD_H, GAP_X, GAP_Y = 3, 262, 172, 17, 16      # one catalogue per row, full width
    HEAD_H = 60
    VIEW_Y = 640
    PACK_W, PACK_H, PACK_GAP = 194, 82, 16

    def __init__(self, save_manager, shop, on_back, audio_manager=None):
        self.save_mgr = save_manager
        self.shop = shop
        self.on_back = on_back
        self.audio = audio_manager
        self.time_val = 0.0
        self.skins = catalog.shop_skins()
        self._featured = catalog.featured_skin()
        self.selected = self.skins[0]
        self._scroll = Scroller()
        self.btn_back = back_button(on_back)
        self.buy_button = Button((VW // 2 - 250, 500, 500, 96), "", 36, callback=self._buy_selected)
        # premium skins: diamonds on the left, real money on the right - both always visible
        self.btn_gems = Button((VW // 2 - 330, 500, 320, 96), "", 30, callback=self._buy_selected_gems)
        self.btn_money = Button((VW // 2 + 10, 500, 320, 96), "", 30, bg_color=(255, 170, 40), hover_color=(255, 205, 100),
                                callback=self._buy_selected_money)
        self.btn_restore = Button((VW // 2 - 160, VH - 78, 320, 52), "", 22, bg_color=(120, 150, 215), hover_color=(160, 184, 240),
                                  callback=self._restore)
        # in the scrolling list (list coordinates; tapped through _list_tap)
        self.btn_shield = Button((VW // 2 - 250, 0, 500, 56), "", 25, bg_color=(0, 170, 230), hover_color=(90, 220, 255),
                                 border_color=(60, 220, 255), callback=self._buy_shield)
        # ads (ads.py): a rewarded video for diamonds, and the one-time "remove ads" purchase (set by HoloGame)
        self.ads = None
        self.on_watch_ad = None
        self.btn_ad = Button((VW // 2 - 250, 0, 500, 56), "", 25, bg_color=(150, 70, 235), hover_color=(190, 120, 255),
                             border_color=(200, 150, 255), callback=lambda: self.on_watch_ad and self.on_watch_ad())
        self.btn_noads = Button((VW // 2 - 250, 0, 500, 56), "", 24, bg_color=(255, 170, 40), hover_color=(255, 205, 100),
                                border_color=(255, 220, 140), callback=self._buy_noads)
        self.pack_buttons = []
        self.refresh_texts()

    # ---- layout (list coordinates: 0 = top of the scrolling list): the skins grouped by catalogue, a title row
    # above each catalogue's cards, then the diamond packs and the shield
    def _layout(self):
        lay = getattr(self, "_lay", None)
        if lay is not None:
            import datetime
            if getattr(self, "_feat_day", None) == datetime.date.today().isoformat():
                return lay
            self._lay = None
            self.refresh_texts()                         # pack / shield rows move with the list
            return self._layout()
        x0 = (VW - (self.COLS * self.CARD_W + (self.COLS - 1) * self.GAP_X)) // 2
        cards, heads, y = {}, [], 8
        # today's showcase (the old separate "featured" page) heads the list
        import datetime
        self._feat_day = datetime.date.today().isoformat()
        self._feat = catalog.featured_skins(3, self._feat_day)
        self._feat_rects = {}
        heads.append(("feat", y))
        y += self.HEAD_H
        for i, sid in enumerate(self._feat):
            self._feat_rects[sid] = pygame.Rect(x0 + i * (self.CARD_W + self.GAP_X), y, self.CARD_W, self.CARD_H)
        y += self.CARD_H + self.GAP_Y + 14
        by_theme = {}
        for sid in self.skins:
            by_theme.setdefault(catalog.THEME_OF[sid], []).append(sid)
        for ti in sorted(by_theme):
            heads.append((ti, y))
            y += self.HEAD_H
            for i, sid in enumerate(by_theme[ti]):
                col, row = i % self.COLS, i // self.COLS
                cards[sid] = pygame.Rect(x0 + col * (self.CARD_W + self.GAP_X), y + row * (self.CARD_H + self.GAP_Y),
                                         self.CARD_W, self.CARD_H)
            rows = (len(by_theme[ti]) + self.COLS - 1) // self.COLS
            y += rows * (self.CARD_H + self.GAP_Y) + 14
        self._lay = (cards, heads, y)
        return self._lay

    def _grid_h(self):
        return self._layout()[2]

    def _content_h(self):
        return self._grid_h() + 440

    def _view_h(self):
        return VH - 96 - self.VIEW_Y

    def _card_rect(self, i):
        return self._layout()[0][self.skins[i]]

    def refresh_texts(self):
        self.btn_back.text = t("back")
        self.btn_restore.text = t("shop_restore")
        gy = self._grid_h()
        self.pack_buttons = []
        px0 = (VW - (4 * self.PACK_W + 3 * self.PACK_GAP)) // 2
        for i, pack in enumerate(shop_mod.DIAMOND_PACKS if self.shop.sells_money else ()):
            pid, amt, def_price, lbl = pack
            b = Button((px0 + i * (self.PACK_W + self.PACK_GAP), gy + 70, self.PACK_W, self.PACK_H), "", 24,
                       bg_color=(18, 38, 68), hover_color=(30, 75, 135), border_color=(0, 214, 255),
                       callback=(lambda p=pid: self._buy_pack(p)))
            b.pack = pack
            self.pack_buttons.append(b)
        self.btn_shield.rect.y = gy + (180 if self.shop.sells_money else 30)
        self.btn_ad.rect.y = self.btn_shield.rect.y + 72
        self.btn_noads.rect.y = self.btn_ad.rect.y + 72
        self._sold_money = self.shop.sells_money
        self._content_key = None

    def _click(self):
        if self.audio:
            self.audio.play_sfx("sfx_click")

    def show_top(self):
        """Opened from the menu: the list at the top, the first skin of today's showcase selected."""
        self._layout()
        if self._feat:
            self.selected = self._feat[0]
        self._scroll.y = 0.0
        self._scroll.vel = 0.0

    def select(self, sid):
        """Jump to a skin (used when the skin screen sends the player here)."""
        if sid in self.skins:
            self.selected = sid
            r = self._card_rect(self.skins.index(sid))
            self._scroll.y = max(0.0, min(r.y - self.HEAD_H - 10.0, self._content_h() - self._view_h()))
            self._scroll.vel = 0.0

    def _coin(self):
        return (lambda ok: self.audio and ok and self.audio.play_sfx("sfx_coin"))

    def _buy_selected(self):
        sid = self.selected
        if self.save_mgr.is_skin_unlocked(sid):
            self.save_mgr.equipped_skin = sid
            if self.audio:
                self.audio.play_sfx("sfx_swap")
            return
        cost = self.shop.diamond_cost(sid)
        if self.save_mgr.diamonds >= cost:
            self.shop.buy_skin_with_diamonds(sid, on_done=self._coin())
        elif self.shop.is_premium(sid):
            self.shop.buy_skin(sid, on_done=self._coin())              # real-money route of the premium skins
        else:
            self.shop._say("shop_need_gems")

    def _buy_selected_gems(self):
        sid = self.selected
        if self.save_mgr.diamonds >= self.shop.diamond_cost(sid):
            self.shop.buy_skin_with_diamonds(sid, on_done=self._coin())
        else:
            self.shop._say("shop_need_gems")

    def _buy_selected_money(self):
        self.shop.buy_skin(self.selected, on_done=self._coin())

    def _split_buy(self):
        """Premium skin not owned yet: two buttons (diamonds | money) instead of one (only where money is sold)."""
        sid = self.selected
        return self.shop.sells_money and self.shop.is_premium(sid) and not self.save_mgr.is_skin_unlocked(sid)

    def _buy_pack(self, pid):
        self._click()
        self.shop.buy_diamonds(pid, on_done=self._coin())

    def _buy_shield(self):
        self._click()
        self.shop.buy_shield(on_done=self._coin())

    def _ad_ready(self):
        return bool(self.ads and self.on_watch_ad and self.ads.available("diamonds") and self.shop.ad_diamonds_ready())

    def _noads_offer(self):
        """The remove-ads row: only where money is sold and while there are ads to remove."""
        return self.shop.sells_money and self.ads is not None and self.ads.available_any()

    def _buy_noads(self):
        self._click()
        if not self.save_mgr.no_ads:
            self.shop.buy_remove_ads(on_done=self._coin())

    def _restore(self):
        self._click()
        self.shop.restore()

    def update(self, mouse_pos, dt=1.0):
        self.time_val += 0.035 * dt
        self.shop.poll()
        if self.shop.sells_money != getattr(self, "_sold_money", None):     # iOS: App Store prices arrive later
            self._sold_money = self.shop.sells_money
            self.refresh_texts()
        for b in (self.btn_back, self.buy_button, self.btn_gems, self.btn_money, self.btn_restore):
            b.update(mouse_pos, dt)
        self._scroll.update(self._content_h(), self._view_h(), dt)

    def _in_view(self, pos):
        return self.VIEW_Y <= pos[1] < self.VIEW_Y + self._view_h()

    def _list_tap(self, pos):
        """A tap inside the scrolling list: a skin card, a diamond pack or the shield."""
        lp = (pos[0], pos[1] - self.VIEW_Y + self._scroll.y)
        self._layout()
        for sid, r in self._feat_rects.items():
            if r.collidepoint(lp):
                self.selected = sid
                return self._click
        for i, sid in enumerate(self.skins):
            if self._card_rect(i).collidepoint(lp):
                self.selected = sid
                return self._click
        for b in self.pack_buttons:
            if b.rect.collidepoint(lp):
                return b.callback
        if self.btn_shield.rect.collidepoint(lp):
            return self._buy_shield
        if self._ad_ready() and self.btn_ad.rect.collidepoint(lp):
            return self.btn_ad.callback
        if self._noads_offer() and not self.save_mgr.no_ads and self.btn_noads.rect.collidepoint(lp):
            return self._buy_noads
        return None

    def handle_event(self, event):
        if self.btn_back.handle_event(event):
            return self.on_back
        if self._split_buy():
            if self.btn_gems.handle_event(event):
                return self._buy_selected_gems
            if self.btn_money.handle_event(event):
                return self._buy_selected_money
        elif self.buy_button.handle_event(event):
            return self._buy_selected
        if self.shop.sells_money and self.btn_restore.handle_event(event):
            return self._restore
        if event.type == pygame.MOUSEWHEEL:
            self._scroll.wheel(event.y)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self._in_view(event.pos):
            self._scroll.on_down(event.pos)
        elif event.type == pygame.MOUSEMOTION and event.buttons[0]:
            self._scroll.on_move(event.pos)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            tap = self._scroll.on_up(event.pos)
            if tap is not None and self._in_view(tap):
                return self._list_tap(tap)
        return None

    def draw_dynamic(self, surface):
        """Drawn every frame over the cached screen: the scrolling list window and the animated preview."""
        self._draw_list(surface)
        sk = SKINS[self.selected]
        cx, cy, d = VW // 2, 272, 105
        for k in range(6):
            tw = 0.5 + 0.5 * math.sin(self.time_val * 2.4 + k * 1.3)
            sparkle(surface, cx + (-330 if k % 2 else 330) + (k // 2) * (28 if k % 2 else -28), 200 + k * 34, 6 + 8 * tw, (200, 235, 255))
        p1 = (cx + math.cos(self.time_val) * d, cy + math.sin(self.time_val) * d * 0.55)
        p2 = (cx + math.cos(self.time_val + math.pi) * d, cy + math.sin(self.time_val + math.pi) * d * 0.55)
        draw_tether(surface, p1, p2, sk, self.time_val)
        draw_orb(surface, p1, 34, sk["color1"], sk["glow1"], False, sk, self.time_val)
        draw_orb(surface, p2, 34, sk["color2"], sk["glow2"], True, sk, self.time_val)

    def sig_extra(self):
        return (self.save_mgr.shield_stock, self.save_mgr.rev)

    def _content(self):
        """The whole scrolling list as one opaque surface, rebuilt only when something on it changes."""
        sm = self.save_mgr
        key = (self.selected, getattr(self, "_feat_day", None), tuple(sm.is_skin_unlocked(s) for s in self.skins), sm.shield_stock,
               self._ad_ready(), self._noads_offer(), sm.no_ads, sm.ad_diamonds_left(shop_mod.AD_PER_DAY),
               tuple(self.shop.pack_price(p[0], p[2]) for p in shop_mod.DIAMOND_PACKS), get_language(), VW)
        if getattr(self, "_content_key", None) == key and getattr(self, "_content_img", None) is not None:
            return self._content_img
        img = gfx.cv(pygame.Surface((VW, self._content_h())))
        bg = (10, 14, 26)
        img.fill(bg)
        lang = get_language()
        for ti, hy in self._layout()[1]:
            if ti == "feat":
                section_title(img, hy + 30, t("featured_title"), ACCENT_GOLD, t("shop_featured_tag").replace("✨ ", ""), x0=34)
                continue
            name = catalog.theme_name(ti, lang).upper()
            members = catalog.THEMES[ti][2]
            owned = sum(1 for m in members if sm.is_skin_unlocked(m))
            section_title(img, hy + 30, name, ACCENT_CYAN, f"{owned}/5", x0=34)
        cards = [(sid, self._feat_rects[sid]) for sid in self._feat] + \
                [(sid, self._card_rect(i)) for i, sid in enumerate(self.skins)]
        for sid, r in cards:
            s = SKINS[sid]
            sel = sid == self.selected
            got = sm.is_skin_unlocked(sid)
            prem = self.shop.is_premium(sid)
            tc = catalog.TIERS[catalog.tier(sid)]["color"]
            edge = (0, 230, 255) if sel else ((170, 130, 50) if prem else (46, 68, 108))
            if sel:
                img.blit(neon_halo(r.w, r.h, (0, 230, 255), 22), (r.x - 12, r.y - 12))
            img.blit(cockpit_surface(r.w, r.h, (26, 38, 66) if sel else (20, 28, 50), (8, 12, 26), edge, 22), r.topleft)
            thumb = skin_thumbnail(sid, width=170, height=88, radius=18)
            img.blit(thumb, thumb.get_rect(center=(r.centerx, r.y + 58)))
            pygame.draw.rect(img, tc, (r.x + 22, r.y + r.h - 9, r.w - 44, 3), border_radius=2)   # rarity stripe
            if prem:
                draw_vector_star(img, r.right - 24, r.y + 24, radius=12, filled=True, color=(255, 200, 70))
            if sid == self._featured:
                rib = pygame.Rect(r.x + 10, r.y + 10, 96, 26)
                pygame.draw.rect(img, (35, 200, 140), rib, border_radius=12)
                draw_text(img, t("shop_featured_tag").replace("✨ ", ""), 15, (255, 255, 255), rib.center, max_w=90)
            draw_text(img, s["name"], 24, TEXT_WHITE, (r.centerx, r.y + 116), max_w=r.w - 24)
            pill = pygame.Rect(0, 0, 150, 34)
            pill.center = (r.centerx, r.y + 146)
            if got:
                img.blit(cockpit_surface(pill.w, pill.h, (30, 90, 70), (16, 50, 40), (80, 220, 150), 17), pill.topleft)
                draw_text(img, t("owned"), 20, (235, 255, 245), pill.center)
            else:
                img.blit(cockpit_surface(pill.w, pill.h, (24, 60, 96), (12, 30, 54), (0, 220, 255), 17), pill.topleft)
                draw_diamond_icon(img, pill.centerx - 34, pill.centery, 10, (0, 230, 255))
                draw_text(img, f"{self.shop.diamond_cost(sid)}", 23, (230, 248, 255), (pill.centerx + 10, pill.centery))
        gy = self._grid_h()
        if self.pack_buttons:
            draw_diamond_icon(img, VW // 2 - 150, gy + 36, 14, (0, 230, 255))
            draw_text(img, t("diamond_packs_title"), 28, (0, 230, 255), (VW // 2, gy + 36))
            draw_diamond_icon(img, VW // 2 + 150, gy + 36, 14, (0, 230, 255))
        for b in self.pack_buttons:
            b.draw(img)
            pid, amt, def_price, lbl = b.pack
            price = self.shop.pack_price(pid, def_price)
            draw_diamond_icon(img, b.rect.centerx, b.rect.y + 24, 14, (0, 230, 255))
            draw_text(img, f"{amt} {t('diamonds').upper()}", 24, (255, 255, 255), (b.rect.centerx, b.rect.y + 46))
            draw_text(img, price, 22, (255, 215, 120), (b.rect.centerx, b.rect.y + 68), bold=False)
        full = sm.shield_stock >= sm.SHIELD_STOCK_MAX
        sb = self.btn_shield
        sb.text = t("shield_buy_btn", n=sm.shield_stock, cost=shop_mod.SHIELD_COST)
        sb.bg_color = (45, 52, 60) if full else (0, 170, 230)
        sb.hover_color = (55, 62, 70) if full else (90, 220, 255)
        sb.draw(img)
        if self._ad_ready():
            ab = self.btn_ad
            ab.text = t("ad_watch_btn", n=shop_mod.AD_REWARD, left=sm.ad_diamonds_left(shop_mod.AD_PER_DAY))
            ab.draw(img)
        if self._noads_offer():
            nb = self.btn_noads
            if sm.no_ads:
                nb.text, nb.bg_color, nb.hover_color = t("noads_owned"), (45, 110, 80), (45, 110, 80)
            else:
                nb.text = t("noads_btn", price=self.shop.price_label_product(shop_mod.REMOVE_ADS, shop_mod.REMOVE_ADS_PRICE))
            nb.draw(img)
        self._content_key, self._content_img = key, img
        return img

    def draw(self, surface):
        sm = self.save_mgr
        header(surface, t("shop_title"), self.btn_back, None)
        draw_diamond_badge(surface, VW - 100, 74, sm.diamonds)

        # preview of the selected skin
        sk = SKINS[self.selected]
        premium = self.shop.is_premium(self.selected)
        panel_r = pygame.Rect(40, 160, VW - 80, 320)
        pc = (255, 200, 90) if premium else (0, 200, 240)
        surface.blit(neon_halo(panel_r.w, panel_r.h, pc, 30), (panel_r.x - 12, panel_r.y - 12))
        surface.blit(cockpit_surface(panel_r.w, panel_r.h, (20, 30, 58), (6, 10, 24), pc, 30), panel_r.topleft)
        cx = VW // 2
        if not getattr(self, "_static", False):
            self.draw_dynamic(surface)
        draw_text(surface, sk["name"], 44, TEXT_WHITE, (cx, 384))
        draw_text(surface, skin_text.desc(self.selected, sk), 24, (160, 195, 235), (cx, 426), bold=False, max_w=760)
        if premium:
            draw_text(surface, t("premium_tag"), 20, (255, 210, 110), (cx, 456), bold=True)
        if self.selected == self._featured:
            draw_text(surface, t("shop_featured_tag"), 22, (140, 255, 190), (cx, 484), bold=True)

        owned = sm.is_skin_unlocked(self.selected)
        eb = self.buy_button
        cost = self.shop.diamond_cost(self.selected)
        price = self.shop.price_label(self.selected)
        unit = t("diamonds").upper()
        if sm.equipped_skin == self.selected:
            eb.text, eb.bg_color, eb.hover_color = t("equipped"), (35, 200, 120), (80, 230, 160)
        elif owned:
            eb.text, eb.bg_color, eb.hover_color = t("equip"), (96, 140, 255), (140, 176, 255)
        elif premium and self.shop.sells_money:
            eb = None
            gb, mb = self.btn_gems, self.btn_money
            enough = sm.diamonds >= cost
            gb.text = f"{cost} {unit}"
            gb.bg_color, gb.hover_color = ((0, 190, 235), (40, 225, 255)) if enough else ((70, 76, 96), (90, 96, 116))
            gb.text_color = (255, 255, 255)
            mb.text = price
            mb.text_color = (255, 255, 255)
            gb.draw(surface)
            mb.draw(surface)
        elif sm.diamonds >= cost:
            eb.text, eb.bg_color, eb.hover_color = f"{t('shop_buy')}  {cost} {unit}", (0, 190, 235), (40, 225, 255)
        else:
            eb.text, eb.bg_color, eb.hover_color = f"{cost} {unit}  ({t('gems_short')})", (70, 76, 96), (90, 96, 116)
        if eb is not None:
            eb.text_color = (255, 255, 255)
            eb.draw(surface)
        msg = self.shop.current_message()
        if msg:
            draw_text(surface, t(msg), 26, (255, 232, 160), (VW // 2, 616), max_w=820)
        elif not self.shop.open_for_business and self.shop.sells_money:
            draw_text(surface, t("shop_soon"), 22, (255, 200, 170), (VW // 2, 616), bold=False, max_w=820)
        elif self.shop.billing.name == "dev":
            draw_text(surface, t("shop_test_mode"), 22, (255, 170, 190), (VW // 2, 616), bold=False, max_w=820)

        if not getattr(self, "_static", False):
            self._draw_list(surface)                 # (cached screens get it from draw_dynamic every frame)
        if self.shop.sells_money:
            self.btn_restore.draw(surface)

    def _draw_list(self, surface):
        """The scrolling list: a window of the pre-rendered list (scrolling never redraws the rest of the screen -
        the scroller is a private attribute, so it is not part of the cached screen's signature)."""
        img = self._content()
        vh = self._view_h()
        view = pygame.Rect(0, self.VIEW_Y, VW, vh)
        surface.fill((10, 14, 26), view)
        sy = int(self._scroll.y)
        src_y = max(0, sy)
        dst_y = self.VIEW_Y + max(0, -sy)                  # pulled past the top: the list follows the finger
        h = min(vh - max(0, -sy), img.get_height() - src_y)
        if h > 0:
            surface.blit(img, (0, dst_y), pygame.Rect(0, src_y, VW, h))
        pygame.draw.line(surface, (44, 72, 116), (0, self.VIEW_Y), (VW, self.VIEW_Y), 2)
        pygame.draw.line(surface, (44, 72, 116), (0, self.VIEW_Y + vh - 1), (VW, self.VIEW_Y + vh - 1), 2)
        ch = self._content_h()
        if ch > vh:                                         # scroll bar
            bh = max(40, int(vh * vh / ch))
            by = self.VIEW_Y + int((vh - bh) * max(0.0, min(1.0, self._scroll.y / (ch - vh))))
            pygame.draw.rect(surface, (70, 110, 170), (VW - 10, by, 5, bh), border_radius=3)


# ================================================================================================ profile
class ProfileModal:
    def __init__(self, save_manager, on_save, on_recovery=None):
        self.save_mgr = save_manager
        self.on_save = on_save
        self.on_recovery = on_recovery        # on_recovery("code" | "restore") opens the account recovery modal
        self.name_text = save_manager.player_name
        if self.name_text == "PİLOT" and not save_manager.is_profile_set:
            self.name_text = ""
        self.selected_country = save_manager.player_country
        self.input_active = True
        self.cursor_timer = 0.0
        top = max(120, (VH - 1180) // 2)
        self.box = pygame.Rect(50, top, VW - 100, 1180)
        self.input_rect = pygame.Rect(self.box.x + 60, self.box.y + 230, self.box.w - 120, 100)
        self.cards = []
        cw, ch, gx, gy = 178, 80, 12, 14
        x0 = self.box.x + (self.box.w - (4 * cw + 3 * gx)) // 2
        y0 = self.box.y + 450
        for i, c in enumerate(COUNTRIES):
            self.cards.append((c["code"], c["name"], pygame.Rect(x0 + (i % 4) * (cw + gx), y0 + (i // 4) * (ch + gy), cw, ch)))
        self.btn_confirm = Button((VW // 2 - 300, self.box.bottom - 140, 600, 100), t("profile_confirm"), 38,
                                  bg_color=(25, 70, 50), hover_color=ACCENT_GREEN, callback=self._confirm)
        by, bw = self.box.y + 850, (self.box.w - 120 - 20) // 2
        # account recovery = the pilot linked to a Google account (1.0.5; the old 12-letter codes are gone)
        mail = save_manager.data.get("google_email", "")
        self.btn_code = Button((self.box.x + 60, by, bw, 76), t("google_linked_btn", email=mail) if mail else t("google_link_btn"),
                               22 if mail else 26, callback=lambda: self.on_recovery and self.on_recovery("link"))
        self.btn_restore = Button((self.box.x + 60 + bw + 20, by, bw, 76), t("google_restore_btn"), 24,
                                  callback=lambda: self.on_recovery and self.on_recovery("restore"))
        try:
            pygame.key.start_text_input()
            pygame.key.set_text_input_rect(self.input_rect)
        except Exception:
            pass

    def close(self):
        try:
            pygame.key.stop_text_input()
        except Exception:
            pass

    def _confirm(self):
        name = self.name_text.strip()[:12].upper() or "PİLOT"
        self.save_mgr.player_name = name
        self.save_mgr.player_country = self.selected_country
        self.save_mgr.is_profile_set = True
        self.close()
        if self.on_save:
            self.on_save()

    def _recovery_buttons(self):
        # iOS: no Google sign-in (App Store rule 4.8 would then require Sign in with Apple as well)
        if not self.on_recovery or paths.is_ios():
            return []
        # a code only exists for a pilot that has been set up; restoring is offered from the very first screen on
        return [self.btn_code, self.btn_restore] if self.save_mgr.is_profile_set else [self.btn_restore]

    def dyn_key(self):
        blink = int(self.cursor_timer * 2.5) % 2 == 0 and self.input_active
        return (self.name_text, self.selected_country, blink)

    def update(self, mouse_pos, dt=1.0):
        self.cursor_timer += 0.05 * dt
        self.btn_confirm.update(mouse_pos, dt)
        for b in self._recovery_buttons():
            b.update(mouse_pos, dt)

    def _add_text(self, s):
        for ch in s:
            if len(self.name_text) < 12 and (ch.isalnum() or ch in " -_."):
                self.name_text += ch.upper() if ch != "i" else "İ" if get_language() == "tr" else "I"

    def handle_event(self, event):
        if self.btn_confirm.handle_event(event):
            self._confirm()
            return True
        for b in self._recovery_buttons():
            if b.handle_event(event):
                b.callback()
                return True
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.input_active = self.input_rect.collidepoint(event.pos)
            try:
                if self.input_active:
                    pygame.key.start_text_input()
                else:
                    pygame.key.stop_text_input()     # a tap anywhere else puts the on-screen keyboard away (iOS has
            except Exception:                        # no back key to close it, and it covers the confirm button)
                pass
            for code, _, r in self.cards:
                if r.collidepoint(event.pos):
                    self.selected_country = code
                    return True
        elif event.type == pygame.TEXTINPUT and self.input_active:
            self._add_text(event.text)
            return True
        elif event.type == pygame.KEYDOWN and self.input_active:
            if event.key == pygame.K_RETURN:
                self._confirm()
                return True
            if event.key == pygame.K_BACKSPACE:
                self.name_text = self.name_text[:-1]
                return True
        return None

    def draw(self, surface):
        dim(surface, 232)
        panel(surface, self.box, (18, 24, 38), (45, 65, 105), 28, 2)
        b = self.box
        draw_text(surface, t("profile_title"), 44, ACCENT_CYAN, (VW // 2, b.y + 70), max_w=b.w - 60)
        draw_text(surface, t("profile_sub"), 26, TEXT_MUTED, (VW // 2, b.y + 128), bold=False, max_w=b.w - 60)
        draw_text(surface, t("profile_name_label"), 28, TEXT_WHITE, (self.input_rect.x, self.input_rect.y - 34), anchor="midleft")
        pygame.draw.rect(surface, (25, 33, 52), self.input_rect, border_radius=16)
        pygame.draw.rect(surface, ACCENT_CYAN if self.input_active else (55, 70, 95), self.input_rect, 3, border_radius=16)
        cur = "|" if (int(self.cursor_timer * 2.5) % 2 == 0 and self.input_active) else " "
        if not self.name_text and not self.input_active:
            draw_text(surface, t("pilot_placeholder"), 36, (80, 95, 120), (self.input_rect.x + 24, self.input_rect.centery), anchor="midleft")
        else:
            draw_text(surface, self.name_text + cur, 44, TEXT_WHITE, (self.input_rect.x + 24, self.input_rect.centery), anchor="midleft")
        draw_text(surface, t("profile_flag_label"), 28, TEXT_WHITE, (self.input_rect.x, b.y + 410), anchor="midleft")
        for code, name, r in self.cards:
            sel = code == self.selected_country
            pygame.draw.rect(surface, (32, 45, 70) if sel else (22, 28, 44), r, border_radius=14)
            pygame.draw.rect(surface, ACCENT_CYAN if sel else (50, 60, 80), r, 3 if sel else 1, border_radius=14)
            draw_flag_icon(surface, code, pygame.Rect(r.x + 12, r.centery - 15, 44, 30))
            draw_text(surface, code, 28, ACCENT_GOLD if sel else TEXT_WHITE, (r.x + 68, r.centery), anchor="midleft")
        info = get_country_info(self.selected_country)
        draw_text(surface, f"{info['name']} ({info['code']})", 30, ACCENT_CYAN, (VW // 2, b.bottom - 190))
        rb = self._recovery_buttons()
        if len(rb) == 1:                                   # first run: "restore" alone, centred
            rb[0].rect.centerx = VW // 2
        for btn in rb:
            btn.draw(surface)
        self.btn_confirm.draw(surface)


class RecoveryModal:
    """Account recovery. mode "code": shows this pilot's recovery code (a fresh one from the server);
    mode "restore": takes a code and hands the recovered account to on_restored(payload)."""

    def __init__(self, online, mode, on_close, on_restored):
        self.online = online
        self.mode = mode
        self.on_close = on_close
        self.on_restored = on_restored
        self.code_text = ""
        self.cursor_timer = 0.0
        self.applied = False
        top = max(140, (VH - 900) // 2)
        self.box = pygame.Rect(50, top, VW - 100, 900)
        self.input_rect = pygame.Rect(self.box.x + 60, self.box.y + 380, self.box.w - 120, 110)
        self.btn_close = Button((VW // 2 - 280, self.box.bottom - 130, 560, 96),
                                t("recovery_close") if mode == "code" else t("back"), 34, callback=self._close)
        self.btn_go = Button((VW // 2 - 280, self.box.bottom - 250, 560, 96), t("recovery_restore_go"), 34,
                             bg_color=(25, 70, 50), hover_color=ACCENT_GREEN, callback=self._go)
        if mode == "code":
            online.request_code()
        else:
            online.restore_state = None
            try:
                pygame.key.start_text_input()
                pygame.key.set_text_input_rect(self.input_rect)
            except Exception:
                pass

    def _close(self):
        try:
            pygame.key.stop_text_input()
        except Exception:
            pass
        self.on_close()

    def _normalized(self):
        return "".join(ch for ch in self.code_text.upper() if ch.isalnum())

    def _go(self):
        if len(self._normalized()) == 12 and (self.online.restore_state or {}).get("state") != "wait":
            self.online.restore(self._normalized())

    def update(self, mouse_pos, dt=1.0):
        self.cursor_timer += 0.05 * dt
        self.btn_close.update(mouse_pos, dt)
        if self.mode == "restore":
            self.btn_go.update(mouse_pos, dt)
            st = self.online.restore_state or {}
            if st.get("state") == "ok" and not self.applied:
                self.applied = True
                try:
                    pygame.key.stop_text_input()
                except Exception:
                    pass
                self.on_restored(st["payload"])

    def handle_event(self, event):
        if self.btn_close.handle_event(event):
            self._close()
            return True
        if self.mode != "restore":
            return None
        if self.btn_go.handle_event(event):
            self._go()
            return True
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            try:
                if self.input_rect.collidepoint(event.pos):
                    pygame.key.start_text_input()
                else:
                    pygame.key.stop_text_input()     # tap outside the field: keyboard away
            except Exception:
                pass
        elif event.type == pygame.TEXTINPUT:
            for ch in event.text.upper():
                if ch.isalnum() and len(self._normalized()) < 12:
                    self.code_text += ch
            return True
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_BACKSPACE:
                self.code_text = self.code_text[:-1]
                return True
            if event.key == pygame.K_RETURN:
                self._go()
                return True
        return None

    def _status(self, st):
        reason = st.get("reason")
        return {"offline": t("recovery_offline"), "limit": t("recovery_limit"),
                "unknown": t("recovery_unknown")}.get(reason, t("recovery_offline"))

    def draw(self, surface):
        dim(surface, 232)
        b = self.box
        panel(surface, b, (18, 24, 38), (45, 65, 105), 28, 2)
        title = t("recovery_code_title") if self.mode == "code" else t("recovery_restore_title")
        draw_text(surface, title, 40, ACCENT_CYAN, (VW // 2, b.y + 70), max_w=b.w - 60)
        help_key = "recovery_code_help" if self.mode == "code" else "recovery_restore_help"
        draw_paragraph(surface, t(help_key), 26, TEXT_MUTED, b.x + 60, b.y + 125, b.w - 120, center=True)
        if self.mode == "code":
            st = self.online.recovery or {"state": "wait"}
            box = pygame.Rect(b.x + 60, b.y + 360, b.w - 120, 150)
            pygame.draw.rect(surface, (25, 33, 52), box, border_radius=18)
            pygame.draw.rect(surface, ACCENT_GOLD if st.get("state") == "ok" else (55, 70, 95), box, 3, border_radius=18)
            if st.get("state") == "ok":
                draw_text(surface, st.get("code", ""), 64, ACCENT_GOLD, box.center, max_w=box.w - 30)
                draw_text(surface, t("recovery_code_new"), 24, TEXT_MUTED, (VW // 2, box.bottom + 40), bold=False, max_w=b.w - 60)
            elif st.get("state") == "fail":
                draw_paragraph(surface, self._status(st), 28, (255, 150, 110), box.x + 24, box.y + 30, box.w - 48, center=True)
            else:
                draw_text(surface, t("loading"), 34, TEXT_MUTED, box.center)
        else:
            r = self.input_rect
            pygame.draw.rect(surface, (25, 33, 52), r, border_radius=16)
            pygame.draw.rect(surface, ACCENT_CYAN, r, 3, border_radius=16)
            code = self._normalized()
            shown = "-".join(code[i:i + 4] for i in range(0, len(code), 4))
            cur = "|" if int(self.cursor_timer * 2.5) % 2 == 0 else " "
            draw_text(surface, (shown or "") + cur, 52, TEXT_WHITE, (r.x + 28, r.centery), anchor="midleft", max_w=r.w - 40)
            st = self.online.restore_state or {}
            if st.get("state") == "wait":
                draw_text(surface, t("loading"), 30, TEXT_MUTED, (VW // 2, r.bottom + 60))
            elif st.get("state") == "fail":
                draw_text(surface, self._status(st), 26, (255, 150, 110), (VW // 2, r.bottom + 60), max_w=b.w - 80)
            self.btn_go.draw(surface)
        self.btn_close.draw(surface)


class GoogleModal:
    """Account recovery through a Google account. mode "link": link this pilot; mode "restore": bring back the pilot
    linked to the Google account the player picks (the game imports it through on_restored). The Google account chooser
    itself is Android's; this card shows what is going on and the result."""

    def __init__(self, auth, online, mode, on_close, on_restored, on_linked):
        self.auth, self.online, self.mode = auth, online, mode
        self.on_close, self.on_restored, self.on_linked = on_close, on_restored, on_linked
        self.phase = "pick"                      # pick -> server -> ok / fail
        self.reason = ""
        self.email = ""
        self.applied = False
        top = max(140, (VH - 760) // 2)
        self.box = pygame.Rect(50, top, VW - 100, 760)
        self.btn_close = Button((VW // 2 - 280, self.box.bottom - 130, 560, 96), t("back"), 34, callback=self._close)
        self.btn_again = Button((VW // 2 - 280, self.box.bottom - 250, 560, 96), t("google_try_again"), 32,
                                bg_color=(25, 70, 50), hover_color=ACCENT_GREEN, callback=self.start)
        self.online.google = None
        self.start()

    def start(self):
        self.reason, self.phase, self.detail = "", "pick", ""
        self.online.google = None
        if not self.auth.available():
            self.phase, self.reason = "fail", "unavailable"
            self.detail = str(getattr(self.auth, "error", "") or "")[:60]
        elif not self.auth.request(only_authorized=False):
            self.phase, self.reason = "fail", "unavailable"
            self.detail = str(getattr(self.auth, "error", "") or "")[:60]

    def _close(self):
        self.on_close()

    def dyn_key(self):
        return (self.phase, self.reason, self.email)

    def update(self, mouse_pos, dt=1.0):
        self.btn_close.update(mouse_pos, dt)
        if self.phase == "fail":
            self.btn_again.update(mouse_pos, dt)
        if self.phase == "pick":
            got = self.auth.poll()
            if got is not None:
                kind, val = got
                if kind == "ok":
                    self.phase = "server"
                    (self.online.google_link if self.mode == "link" else self.online.google_restore)(val)
                else:
                    self.phase = "fail"
                    self.detail = str(val)[:60]              # Android's own error name: shown small, for support
                    self.reason = "cancelled" if "Cancel" in val else ("no_account" if "NoCredential" in val else "google")
        elif self.phase == "server":
            g = self.online.google or {}
            if g.get("state") == "ok":
                self.email = g.get("email", "")
                self.phase = "ok"
                if self.mode == "restore" and not self.applied:
                    self.applied = True
                    self.on_restored(g["payload"])
                elif self.mode == "link":
                    self.on_linked(self.email)
            elif g.get("state") == "fail":
                self.phase, self.reason, self.email = "fail", g.get("reason", "error"), g.get("email", "")

    def handle_event(self, event):
        if self.btn_close.handle_event(event):
            self._close()
            return True
        if self.phase == "fail" and self.btn_again.handle_event(event):
            self.start()
            return True
        return None

    def draw(self, surface):
        dim(surface, 232)
        b = self.box
        bg = (18, 24, 38)
        panel(surface, b, bg, (45, 65, 105), 28, 2)
        draw_text(surface, t("google_title"), 40, ACCENT_CYAN, (VW // 2, b.y + 70), max_w=b.w - 60, bg=bg)
        info = t("google_link_info") if self.mode == "link" else t("google_restore_info")
        draw_paragraph(surface, info, 26, TEXT_MUTED, b.x + 60, b.y + 125, b.w - 120, center=True)
        y = b.y + 380
        if self.phase == "pick":
            draw_text(surface, t("google_picking"), 32, TEXT_WHITE, (VW // 2, y), max_w=b.w - 80, bg=bg)
        elif self.phase == "server":
            draw_text(surface, t("loading"), 32, TEXT_MUTED, (VW // 2, y), bg=bg)
        elif self.phase == "ok":
            key = "google_linked_ok" if self.mode == "link" else "google_restored_ok"
            draw_paragraph(surface, t(key, email=self.email), 30, ACCENT_GREEN, b.x + 60, y - 30, b.w - 120, center=True)
        else:
            msg = {"unavailable": "google_unavailable", "cancelled": "google_cancelled", "no_account": "google_no_account",
                   "taken": "google_taken", "not_linked": "google_not_linked", "offline": "recovery_offline",
                   "limit": "recovery_limit"}.get(self.reason, "google_error")
            draw_paragraph(surface, t(msg, email=self.email), 28, (255, 150, 110), b.x + 60, y - 30, b.w - 120, center=True)
            detail = getattr(self, "detail", "") or (self.reason if msg == "google_error" else "")
            if detail:
                draw_text(surface, f"({detail})", 20, TEXT_MUTED, (VW // 2, y + 70), bold=False, max_w=b.w - 80, bg=bg)
            if self.reason not in ("unavailable",):
                self.btn_again.draw(surface)
        self.btn_close.text = t("close") if self.phase == "ok" else t("back")
        self.btn_close.draw(surface)


# ================================================================================================ modals
class PauseModal:
    def __init__(self, on_resume, on_restart, on_settings, on_menu, on_levels=None):
        self.cbs = (on_resume, on_restart, on_levels, on_settings, on_menu)
        self.buttons = []
        self.build()

    def dyn_key(self):
        return ()

    def build(self):
        on_resume, on_restart, on_levels, on_settings, on_menu = self.cbs
        cx = VW // 2
        y = VH // 2 - 250
        w = 560
        self.card_top = VH // 2 - 370
        self.card_h = 720
        specs = [(t("resume"), on_resume, (0, 200, 240)), (t("restart"), on_restart, BTN_NORMAL),
                 (t("level_select_modal_btn"), on_levels, BTN_NORMAL), (t("settings"), on_settings, BTN_NORMAL),
                 (t("menu"), on_menu, (230, 60, 90))]
        self.buttons = []
        for label, cb, bg in specs:
            if cb is None:
                continue
            self.buttons.append(Button((cx - w // 2, y, w, 100), label, 36, bg_color=bg, callback=cb))
            y += 118
        if any(cb is None for _, cb, _ in specs):
            self.card_h -= 118

    def refresh_texts(self):
        self.build()

    def update(self, mouse_pos, dt=1.0):
        for b in self.buttons:
            b.update(mouse_pos, dt)

    def handle_event(self, event):
        for b in self.buttons:
            if b.handle_event(event):
                return b.callback
        return None

    def draw(self, surface):
        dim(surface, 205)
        card = pygame.Rect(150, self.card_top, VW - 300, self.card_h)
        panel(surface, card, (18, 24, 38), (45, 65, 105), 26, 2)
        draw_text(surface, t("paused"), 56, TEXT_WHITE, (VW // 2, card.y + 70))
        for b in self.buttons:
            b.draw(surface)


class SettingsModal:
    def __init__(self, save_manager, audio_manager, on_toggle_fullscreen, on_close, on_language_change=None,
                 on_reset=None, desktop=True):
        self.save_mgr = save_manager
        self.audio = audio_manager
        self.on_close = on_close
        self.on_language_change = on_language_change
        self.on_toggle_fullscreen = on_toggle_fullscreen
        self.desktop = desktop
        s = save_manager.settings
        self.card = pygame.Rect(60, VH // 2 - 650, VW - 120, 1300)
        x, w = self.card.x + 60, self.card.w - 120
        y = self.card.y + 190
        self.music_slider = Slider(x + 300, y, w - 300, 16, 0, 1, s.get("music_volume", 0.6), self._music)
        self.sfx_slider = Slider(x + 300, y + 100, w - 300, 16, 0, 1, s.get("sfx_volume", 0.8), self._sfx)
        self.toggles = [
            Toggle((x, y + 190, w, 70), t("set_shake"), s.get("screen_shake", True), lambda v: self._set("screen_shake", v)),
            Toggle((x, y + 280, w, 70), t("set_particles"), s.get("particles", True), lambda v: self._set("particles", v)),
            Toggle((x, y + 370, w, 70), t("set_online"), s.get("online", True), lambda v: self._set("online", v)),
            Toggle((x, y + 460, w, 70), t("set_ghost"), s.get("ghost_race", True), lambda v: self._set("ghost_race", v)),
            Toggle((x, y + 550, w, 70), t("set_haptics"), s.get("haptics", True), lambda v: self._set("haptics", v)),
            Toggle((x, y + 640, w, 70), t("set_show_fps"), s.get("show_fps", False), lambda v: self._set("show_fps", v)),
        ]
        self.btn_lang = Button((x, y + 745, w, 92), t("lang_toggle"), 34, callback=self._toggle_lang)
        self.btn_fs = Button((x, y + 855, w, 92), t("fullscreen"), 32, callback=on_toggle_fullscreen) if desktop else None
        # phones with ads: Google's privacy options form, required where a consent form was shown (EEA / UK)
        self.privacy = None                 # (required(), show()) set by HoloGame
        self.btn_privacy = Button((x, y + 855, w, 92), t("privacy_options"), 28, bg_color=(90, 100, 140),
                                  callback=lambda: self.privacy and self.privacy[1]())
        self.on_reset = on_reset          # kept for callers; progress reset is no longer offered in the settings
        self.btn_close = Button((VW // 2 - 220, self.card.bottom - 158, 440, 96), t("close"), 38,
                                bg_color=(0, 214, 255), hover_color=(90, 236, 255), text_color=(255, 255, 255), callback=on_close)

    def _set(self, key, val):
        self.save_mgr.settings[key] = val
        self.save_mgr.save()
        if key == "haptics":
            import haptics
            haptics.set_enabled(val)

    def _music(self, v):
        self.save_mgr.settings["music_volume"] = v
        self.audio.set_music_volume(v)

    def _sfx(self, v):
        self.save_mgr.settings["sfx_volume"] = v
        self.audio.set_sfx_volume(v)

    def _toggle_lang(self):
        order = locales.LANGUAGES
        cur = self.save_mgr.language
        nxt = order[(order.index(cur) + 1) % len(order)] if cur in order else "tr"
        self.save_mgr.language = nxt
        self.refresh_texts()
        if self.on_language_change:
            self.on_language_change()

    def refresh_texts(self):
        self.btn_lang.text = t("lang_toggle")
        if self.btn_fs:
            self.btn_fs.text = t("fullscreen")
        self.btn_close.text = t("close")
        self.btn_privacy.text = t("privacy_options")
        for tg, key in zip(self.toggles, ("set_shake", "set_particles", "set_online", "set_ghost", "set_haptics", "set_show_fps")):
            tg.label = t(key)

    def _privacy_on(self):
        return bool(self.btn_fs is None and self.privacy and self.privacy[0]())

    def dyn_key(self):
        return (self.save_mgr.language, self._privacy_on())

    def update(self, mouse_pos, dt=1.0):
        for b in (self.btn_lang, self.btn_fs, self.btn_close, self.btn_privacy if self._privacy_on() else None):
            if b:
                b.update(mouse_pos, dt)

    def handle_event(self, event):
        if self.music_slider.handle_event(event) or self.sfx_slider.handle_event(event):
            return True
        for tg in self.toggles:
            if tg.handle_event(event):
                return True
        if self.btn_lang.handle_event(event):
            return self._toggle_lang
        if self.btn_fs and self.btn_fs.handle_event(event):
            return self.on_toggle_fullscreen
        if self._privacy_on() and self.btn_privacy.handle_event(event):
            return self.btn_privacy.callback
        if self.btn_close.handle_event(event):
            return self.on_close
        if event.type == pygame.MOUSEBUTTONUP and self.save_mgr and self.music_slider.dragging is False:
            pass
        return None

    def save_on_close(self):
        self.save_mgr.save()

    def draw(self, surface):
        dim(surface, 215)
        panel(surface, self.card, (18, 24, 38), (45, 65, 105), 26, 2)
        draw_text(surface, t("settings_title"), 54, TEXT_WHITE, (VW // 2, self.card.y + 80))
        x = self.card.x + 60
        y = self.card.y + 190
        draw_text(surface, t("music_vol"), 32, TEXT_WHITE, (x, y + 8), anchor="midleft")
        self.music_slider.draw(surface)
        draw_text(surface, t("sfx_vol"), 32, TEXT_WHITE, (x, y + 108), anchor="midleft")
        self.sfx_slider.draw(surface)
        for tg in self.toggles:
            tg.draw(surface)
        self.btn_lang.draw(surface)
        if self.btn_fs:
            self.btn_fs.draw(surface)
        elif self._privacy_on():
            self.btn_privacy.draw(surface)
        self.btn_close.draw(surface)
        draw_text(surface, t("privacy_note"), 20, TEXT_MUTED, (VW // 2, self.card.bottom - 34), bold=False, max_w=self.card.w - 60)


class HowToModal:
    """One-time 'how to play' onboarding, shown before level 1: page 1 is the control tutorial, page 2
    introduces the world ranking / shop / daily missions / achievements and hands out a welcome gift."""
    WELCOME_GIFT = 30

    def __init__(self, on_close, save_mgr=None):
        self.on_close = on_close
        self.save_mgr = save_mgr
        self.time_val = 0.0
        self.page = 0
        self.btn = Button((VW // 2 - 240, VH // 2 + 380, 480, 100), "", 40, bg_color=(0, 214, 255), hover_color=(90, 236, 255),
                          text_color=(255, 255, 255), callback=self._advance)
        self.refresh_texts()

    def reset(self):
        self.page = 0
        self.refresh_texts()

    def refresh_texts(self):
        self.btn.text = t("howto_next") if self.page == 0 else t("howto_go")

    def _advance(self):
        if self.page == 0:
            self.page = 1
            self.refresh_texts()
            if self.save_mgr and not self.save_mgr.data.get("welcome_gift_given"):
                self.save_mgr.data["welcome_gift_given"] = True
                self.save_mgr.earn("welcome", "1", self.WELCOME_GIFT)
        else:
            self.on_close()

    def update(self, mouse_pos, dt=1.0):
        self.time_val += 0.04 * dt
        self.btn.update(mouse_pos, dt)

    def handle_event(self, event):
        if self.btn.handle_event(event):
            return self._advance
        return None

    def draw(self, surface):
        if self.page == 0:
            self._draw_page1(surface)
        else:
            self._draw_page2(surface)

    def _draw_page1(self, surface):
        dim(surface, 225)
        card = pygame.Rect(50, VH // 2 - 520, VW - 100, 1040)
        shadow_under(surface, card, 40, 90, 10, 34)
        pygame.draw.rect(surface, (10, 18, 38), card, border_radius=34)
        pygame.draw.rect(surface, (0, 200, 240), card, 3, border_radius=34)
        draw_text(surface, t("howto_title"), 60, (255, 255, 255), (VW // 2, card.y + 78), bg=(10, 18, 38))
        rows = [("tap", t("howto_1")), ("wall", t("howto_2")), ("star", t("howto_3")), ("power", t("howto_4"))]
        y = card.y + 190
        for kind, txt in rows:
            cx, cy = card.x + 110, y + 60
            if kind == "tap":
                a = self.time_val * 2.0
                p1 = (cx + math.cos(a) * 34, cy + math.sin(a) * 34)
                p2 = (cx - math.cos(a) * 34, cy - math.sin(a) * 34)
                pygame.draw.line(surface, (120, 230, 255), p1, p2, 4)
                pygame.draw.circle(surface, (255, 120, 190), (int(p1[0]), int(p1[1])), 16)
                pygame.draw.circle(surface, (100, 220, 255), (int(p2[0]), int(p2[1])), 16)
            elif kind == "wall":
                pygame.draw.rect(surface, (40, 60, 100), (cx - 44, cy - 30, 88, 60), border_radius=10)
                pygame.draw.rect(surface, (0, 210, 255), (cx - 44, cy - 30, 88, 60), 3, border_radius=10)
                pygame.draw.line(surface, (255, 90, 110), (cx - 18, cy - 14), (cx + 18, cy + 14), 6)
                pygame.draw.line(surface, (255, 90, 110), (cx - 18, cy + 14), (cx + 18, cy - 14), 6)
            elif kind == "star":
                draw_vector_star(surface, cx, cy, 34 + 3 * math.sin(self.time_val * 4))
            else:
                for k, (col, dx) in enumerate(((( 60, 255, 140), -46), ((90, 200, 255), 0), ((255, 190, 40), 46))):
                    pygame.draw.circle(surface, col, (cx + dx, cy), 17, 3)
            draw_text_wrapped(surface, txt, 31, (235, 232, 255), (card.x + 190, y + 60), card.w - 250, bg=(10, 18, 38))
            y += 168
        self._dots(surface, card)
        self.btn.draw(surface)

    def _draw_page2(self, surface):
        dim(surface, 225)
        card = pygame.Rect(50, VH // 2 - 520, VW - 100, 1040)
        shadow_under(surface, card, 40, 90, 10, 34)
        pygame.draw.rect(surface, (10, 18, 38), card, border_radius=34)
        pygame.draw.rect(surface, (255, 200, 90), card, 3, border_radius=34)
        draw_text(surface, t("howto_page2_title"), 54, (255, 255, 255), (VW // 2, card.y + 78), bg=(10, 18, 38))
        rows = [("shop", t("howto_p2_1"), (190, 90, 255)), ("world", t("howto_p2_2"), (35, 240, 140)),
                ("daily", t("howto_p2_3"), (255, 170, 40)), ("ach", t("howto_p2_4"), (255, 60, 150))]
        # four rows + the gift box must end above the button (VH // 2 + 380 = card.y + 900)
        y = card.y + 165
        for kind, txt, col in rows:
            cx, cy = card.x + 110, y + 60
            pygame.draw.circle(surface, (20, 28, 48), (cx, cy), 40)
            pygame.draw.circle(surface, col, (cx, cy), 40, 4)
            if kind == "shop":
                draw_diamond_icon(surface, cx, cy, 18, col)
            elif kind == "world":
                pygame.draw.circle(surface, col, (cx, cy), 20, 3)
                pygame.draw.line(surface, col, (cx - 20, cy), (cx + 20, cy), 2)
                pygame.draw.ellipse(surface, col, (cx - 20, cy - 9, 40, 18), 2)
            elif kind == "daily":
                pygame.draw.circle(surface, col, (cx, cy), 18, 3)
                pygame.draw.line(surface, col, (cx, cy), (cx, cy - 12), 3)
                pygame.draw.line(surface, col, (cx, cy), (cx + 9, cy + 4), 3)
            else:
                draw_vector_star(surface, cx, cy, 20, filled=True, color=col)
            draw_text_wrapped(surface, txt, 30, (235, 232, 255), (card.x + 190, y + 60), card.w - 250, bg=(10, 18, 38))
            y += 142
        gift = pygame.Rect(card.x + 60, y + 16, card.w - 120, 124)
        pygame.draw.rect(surface, (40, 30, 10), gift, border_radius=26)
        pygame.draw.rect(surface, (255, 210, 90), gift, 3, border_radius=26)
        draw_diamond_icon(surface, gift.x + 70, gift.centery, 26, (255, 215, 110))
        draw_text(surface, t("howto_gift"), 30, (255, 224, 150), (gift.x + 150, gift.y + 40), anchor="midleft", max_w=gift.w - 180)
        draw_text(surface, t("howto_gift_sub", n=self.WELCOME_GIFT), 26, (255, 255, 255), (gift.x + 150, gift.y + 84), anchor="midleft",
                  bold=False, max_w=gift.w - 180)
        self._dots(surface, card)
        self.btn.draw(surface)

    def _dots(self, surface, card):
        for i in range(2):
            c = (0, 214, 255) if i == self.page else (60, 70, 95)
            pygame.draw.circle(surface, c, (VW // 2 - 14 + i * 28, card.y + 130), 7)


class FailureModal:
    def __init__(self, level_id, progress_pct, stars_collected, combo_mult, attempts, on_retry, on_menu, on_levels=None, best_pct=0,
                 save_mgr=None, shop=None, on_revive=None, revive_cost=20, on_endless=None):
        self.level_id = level_id
        self.progress_pct = max(0, min(99, int(progress_pct)))
        self.best_pct = best_pct
        self.stars = stars_collected
        self.attempts = attempts
        self.anim = 0.0
        self.save_mgr = save_mgr
        self.shop = shop
        self.on_revive = on_revive
        self.revive_cost = revive_cost
        self.waiting = False                 # revive paid, waiting for the server's answer
        cx = VW // 2
        top = VH // 2 - 330
        self.top = top
        self.btn_revive = Button((cx - 320, top + 425, 640, 96), "", 32, bg_color=(0, 190, 235), hover_color=(60, 225, 255),
                                 text_color=(255, 255, 255), callback=self._revive)
        self.pack_buttons = []
        pw, ph, pgap = 310, 78, 20
        for i, pack in enumerate(shop_mod.DIAMOND_PACKS[:2] if (shop is None or shop.sells_money) else ()):
            b = Button((cx - pw - pgap // 2 + i * (pw + pgap), top + 530, pw, ph), "", 22, bg_color=(18, 38, 68),
                      hover_color=(30, 75, 135), border_color=(0, 214, 255), callback=(lambda p=pack[0]: self._buy_pack(p)))
            b.pack = pack
            self.pack_buttons.append(b)
        self.btn_retry = Button((cx - 320, top + 626, 640, 100), t("retry_btn"), 38, bg_color=(255, 70, 100), hover_color=(255, 120, 140),
                                callback=on_retry)
        # set by HoloGame when an ad can pay the revive: (callback, ready())
        self.ad_offer = None
        self.btn_ad = Button((cx - 320, top + 530, 640, 78), "", 28, bg_color=(150, 70, 235), hover_color=(190, 120, 255),
                             border_color=(200, 150, 255), callback=self._ad_continue)
        self.btn_levels = Button((cx - 320, top + 738, 310, 86), t("level_select_modal_btn"), 26, bg_color=(96, 140, 255), callback=on_levels)
        self.btn_menu = Button((cx + 10, top + 738, 310, 86), t("menu"), 30, bg_color=(120, 150, 215), callback=on_menu)
        self.on_retry, self.on_levels, self.on_menu = on_retry, on_levels, on_menu
        if on_levels is None:
            self.btn_levels.visible = False
            self.btn_menu.rect = pygame.Rect(cx - 320, top + 738, 640, 86)
        # stuck (3+ tries): the levels button becomes a way to the endless climb - diamonds and stars to come back with
        self.stuck = on_endless is not None and attempts >= 3
        if self.stuck:
            self.on_levels = on_endless
            self.btn_levels.callback = on_endless
            self.btn_levels.bg_color, self.btn_levels.hover_color = (190, 130, 20), (230, 170, 50)
        self.refresh_texts()

    def refresh_texts(self):
        self.btn_retry.text = t("retry_btn")
        self.btn_levels.text = t("endless_try_btn") if getattr(self, "stuck", False) else t("level_select_modal_btn")
        self.btn_menu.text = t("menu")

    def dyn_key(self):
        return (self.save_mgr.diamonds if self.save_mgr else 0, self.waiting, self._enough(), self._ad_on())

    def _enough(self):
        return bool(self.save_mgr) and self.save_mgr.diamonds >= self.revive_cost

    def _ad_on(self):
        return bool(self.ad_offer and not self.waiting and self.ad_offer[1]())

    def _ad_continue(self):
        if self._ad_on():
            self.ad_offer[0]()

    def _revive(self):
        if self._enough() and self.on_revive and not self.waiting:
            self.on_revive()

    def _buy_pack(self, pid):
        if self.shop:
            self.shop.buy_diamonds(pid)

    def update(self, mouse_pos, dt=1.0):
        self.anim += dt
        buttons = [self.btn_retry, self.btn_levels, self.btn_menu, self.btn_revive]
        if self._ad_on():
            buttons.append(self.btn_ad)
        elif not self._enough():
            buttons += self.pack_buttons
        for b in buttons:
            b.update(mouse_pos, dt)

    def handle_event(self, event):
        cbs = [(self.btn_retry, self.on_retry), (self.btn_levels, self.on_levels), (self.btn_menu, self.on_menu),
              (self.btn_revive, self._revive)]
        if self._ad_on():
            cbs.append((self.btn_ad, self._ad_continue))
        elif not self._enough():
            cbs += [(b, b.callback) for b in self.pack_buttons]
        for b, cb in cbs:
            if b.handle_event(event):
                return cb
        return None

    def draw(self, surface):
        dim(surface, 200, (12, 6, 12))
        card = pygame.Rect(90, self.top, VW - 180, 850)
        panel(surface, card, (24, 16, 24), (200, 40, 65), 26, 2)
        if self.save_mgr:
            draw_diamond_badge(surface, card.right - 80, self.top + 50, self.save_mgr.diamonds)
        draw_text(surface, t("failure_title"), 56, (240, 56, 80), (VW // 2, self.top + 70), max_w=card.w - 40, bg=(24, 16, 24))
        draw_text(surface, t("failure_pct", val=self.progress_pct), 84, (255, 220, 100), (VW // 2, self.top + 180), bg=(24, 16, 24))
        pb = pygame.Rect(card.x + 60, self.top + 250, card.w - 120, 16)
        pygame.draw.rect(surface, (55, 25, 38), pb, border_radius=8)
        fw = int(pb.w * self.progress_pct / 100.0)
        if fw > 0:
            pygame.draw.rect(surface, (255, 60, 85), (pb.x, pb.y, fw, pb.h), border_radius=8)
        draw_text(surface, t("failure_attempts", val=self.attempts), 34, TEXT_WHITE, (VW // 2, self.top + 315), bg=(24, 16, 24))
        for i in range(3):
            draw_vector_star(surface, VW // 2 - 60 + i * 60, self.top + 380, radius=22, filled=i < self.stars, color=(255, 205, 65))

        enough = self._enough()
        eb = self.btn_revive
        eb.bg_color, eb.hover_color = ((0, 190, 235), (60, 225, 255)) if enough else ((55, 60, 72), (65, 70, 84))
        if self.waiting:
            eb.text, eb.icon = ". . .", None
        elif enough:
            eb.text, eb.icon = t("revive_btn", cost=self.revive_cost), "gem"
        else:
            eb.text, eb.icon = t("revive_need", cost=self.revive_cost), None
        eb.draw(surface)
        if self._ad_on():
            self.btn_ad.text = t("ad_continue_btn")
            self.btn_ad.draw(surface)
        elif not enough:
            have = self.save_mgr.diamonds if self.save_mgr else 0
            draw_text(surface, t("revive_short", have=have, cost=self.revive_cost), 22, (255, 200, 160), (VW // 2, self.top + 500), bold=False)
            for b in self.pack_buttons:
                b.draw(surface)
                pid, amt, price, lbl = b.pack
                draw_diamond_icon(surface, b.rect.centerx - 55, b.rect.centery, 13, (0, 230, 255))
                draw_text(surface, f"{amt}", 26, TEXT_WHITE, (b.rect.centerx - 20, b.rect.centery - 12), anchor="midleft")
                draw_text(surface, price, 22, (255, 215, 120), (b.rect.centerx - 20, b.rect.centery + 16), anchor="midleft", bold=False)
        self.btn_retry.draw(surface)
        self.btn_levels.draw(surface)
        self.btn_menu.draw(surface)


class VictoryModal:
    def __init__(self, level_id, result, total_score, pilot_name, pilot_country, on_next, on_replay, on_menu,
                 on_levels=None, new_best=False, attempts=1, online=None, is_last=False, assisted=False):
        self.level_id = level_id
        self.assisted = assisted            # revived / bought shield used: kept locally, never sent to the ranking
        self.r = result
        self.total_score = total_score
        self.pilot_name, self.pilot_country = pilot_name, pilot_country
        self.new_best = new_best
        self.attempts = attempts
        self.online = online
        self.anim = 0.0
        cx = VW // 2
        self.top = max(70, (VH - 1400) // 2)
        by = self.top + 1180
        self.btn_next = Button((cx - 330, by - 10, 660, 112), t("next_level") if not is_last else t("lb_title"), 42,
                               bg_color=(25, 70, 50), hover_color=(40, 220, 120), border_color=(60, 230, 140), callback=on_next)
        self.btn_replay = Button((cx - 330, by + 112, 210, 88), t("retry"), 30, callback=on_replay)
        self.btn_levels = Button((cx - 105, by + 112, 210, 88), t("level_select_modal_btn"), 26, bg_color=(25, 45, 75), callback=on_levels)
        self.btn_menu = Button((cx + 120, by + 112, 210, 88), t("menu"), 30, callback=on_menu)
        self.cbs = (on_next, on_replay, on_levels, on_menu)
        if on_levels is None:
            self.btn_levels.visible = False
            self.btn_replay.rect = pygame.Rect(cx - 330, by + 112, 320, 88)
            self.btn_menu.rect = pygame.Rect(cx + 10, by + 112, 320, 88)

    def dyn_key(self):
        on = self.online
        info = on.last_submit if on else None
        # the stars pop in during the first ~2 s (redrawn every frame), then the card is still
        return (int(self.anim) if self.anim < 150 else -1, repr(info), on.status if on else None,
                on.enabled if on else False)

    def update(self, mouse_pos, dt=1.0):
        self.anim += dt
        for b in (self.btn_next, self.btn_replay, self.btn_levels, self.btn_menu):
            b.update(mouse_pos, dt)

    def handle_event(self, event):
        for b, cb in zip((self.btn_next, self.btn_replay, self.btn_levels, self.btn_menu), self.cbs):
            if b.handle_event(event):
                return cb
        return None

    def draw(self, surface):
        dim(surface, 222)
        card = pygame.Rect(50, self.top, VW - 100, 1400)
        panel(surface, card, (18, 24, 38), (45, 65, 105), 28, 2)
        r = self.r
        top = self.top
        draw_text(surface, t("level_completed", lvl=self.level_id), 52, ACCENT_CYAN, (VW // 2, top + 70), max_w=card.w - 60)
        if self.new_best:
            draw_text(surface, t("new_best"), 30, ACCENT_GOLD, (VW // 2, top + 122))
        for i in range(3):
            delay = 18 * (i + 1)
            act = self.anim >= delay and i < r["stars"]
            sc = 1.0
            if act:
                el = (self.anim - delay) / 60.0
                sc = min(1.35, 1.0 + 0.35 * math.sin(el * 8) * max(0.0, 1.0 - el * 2))
            draw_vector_star(surface, VW // 2 - 110 + i * 110, top + 210, radius=int(42 * sc), filled=act)
        rc = get_rank_color(r["rank"])
        pygame.draw.circle(surface, (28, 36, 56), (VW // 2, top + 340), 70)
        pygame.draw.circle(surface, rc, (VW // 2, top + 340), 70, 5)
        draw_text(surface, r["rank"], 64, rc, (VW // 2, top + 340))

        box = pygame.Rect(card.x + 40, top + 440, card.w - 80, 560)
        panel(surface, box, (24, 32, 50), (40, 52, 78), 18, 1)
        unit = t("pts")
        rows = [
            (t("base_score"), f"+{fmt_int(r['base'])}", TEXT_WHITE),
            (t("time_bonus"), f"+{fmt_int(r['time_bonus'])}  ({r['time']:.1f}s)", (120, 255, 170)),
            (t("swap_bonus"), f"+{fmt_int(r['swap_bonus'])}  ({r['swaps']})", (90, 220, 255)),
            (t("graze_bonus"), f"+{fmt_int(r['near_miss_bonus'])}  ({r['near_miss_count']}x)", (255, 180, 50)),
            (t("star_bonus", stars=r["stars"]), f"+{fmt_int(r['star_bonus'])}  (x{r['star_mult']:.2f})", ACCENT_GOLD),
        ]
        for i, (lab, val, col) in enumerate(rows):
            ry = box.y + 44 + i * 62
            draw_text(surface, lab, 30, TEXT_MUTED, (box.x + 28, ry), anchor="midleft", bold=False, max_w=380)
            draw_text(surface, val, 32, col, (box.right - 28, ry), anchor="midright")
        n = len(rows)
        pygame.draw.line(surface, (50, 70, 105), (box.x + 24, box.y + 44 + n * 62 - 30), (box.right - 24, box.y + 44 + n * 62 - 30), 2)
        draw_text(surface, t("level_total"), 34, TEXT_WHITE, (box.x + 28, box.y + 44 + n * 62 + 14), anchor="midleft")
        draw_text(surface, f"{fmt_int(r['level_total'])} {unit}", 40, ACCENT_CYAN, (box.right - 28, box.y + 44 + n * 62 + 14), anchor="midright")
        draw_text(surface, t("total_score"), 30, TEXT_MUTED, (box.x + 28, box.y + 44 + (n + 1) * 62 + 24), anchor="midleft", bold=False)
        draw_text(surface, f"{fmt_int(self.total_score)}", 38, (255, 230, 100), (box.right - 28, box.y + 44 + (n + 1) * 62 + 24), anchor="midright")

        # world standing
        oy = top + 1040
        info = self.online.last_submit if self.online else None
        if info is not None and info.get("level") not in (None, self.level_id):
            info = None                               # an answer about another level (a retried older run)
        if self.assisted:
            draw_text(surface, t("submit_assisted"), 26, (255, 170, 90), (VW // 2, oy), bold=False, max_w=card.w - 60)
        elif info is None:
            if self.online and self.online.enabled:
                if self.online.status == "offline":
                    draw_text(surface, t("submit_queued"), 26, (255, 170, 90), (VW // 2, oy), bold=False, max_w=card.w - 60)
                else:
                    draw_text(surface, t("submit_wait"), 28, TEXT_MUTED, (VW // 2, oy), bold=False)
        elif info.get("ok"):
            txt = t("rank_world", rank=fmt_int(info.get("world_rank", 0)))
            if info.get("country_rank"):
                txt += f"   •   {t('rank_country', rank=fmt_int(info['country_rank']))}"
            draw_text(surface, txt, 34, ACCENT_GREEN, (VW // 2, oy), max_w=card.w - 60)
        else:
            key = "submit_rejected" if info.get("rejected") else "submit_queued"
            draw_text(surface, t(key), 26, (255, 170, 90), (VW // 2, oy), bold=False, max_w=card.w - 60)
        for b in (self.btn_next, self.btn_replay, self.btn_levels, self.btn_menu):
            b.draw(surface)


# ============================================================================================ endless mode
class EndlessHUD(HUD):
    """Endless climb: pause, the height climbed (big), the player's record and the way to the next diamond."""

    def draw_endless(self, surface, metres, best, shields, sector, week_label="", points=None, stars=0):
        col = SECTOR_COL.get(sector, ACCENT_CYAN)
        points = metres * 10 if points is None else points
        key = (metres, best, shields, sector, points, stars, self.shield_stock, self.shield_active, get_language(), VW)
        if getattr(self, "_ekey", None) != key:
            if getattr(self, "_eimg", None) is None or self._eimg.get_width() != VW:
                self._eimg = gfx.cv(pygame.Surface((VW, HUD_H + 1)))
            img = self._eimg
            pygame.draw.rect(img, (12, 16, 26), (0, 0, VW, HUD_H + 1))
            pygame.draw.line(img, (40, 55, 80), (0, HUD_H - 1), (VW, HUD_H - 1), 2)
            pr = self.pause_rect
            panel(img, pr, (24, 30, 46), (70, 88, 122), 20)
            for dx in (-13, 13):
                pygame.draw.rect(img, TEXT_WHITE, (pr.centerx + dx - 6, pr.centery - 22, 12, 44), border_radius=4)
            self._draw_shield_btn(img)                 # shields can be bought in the climb too (1.0.6)
            draw_text(img, f"{t('endless_title')}  •  {fmt_int(metres)} m", 22, col, (VW // 2 + 40, 30), max_w=400)
            draw_text(img, fmt_int(points), 60, TEXT_WHITE, (VW // 2 + 40, 82), max_w=380)
            draw_text(img, t("endless_record_short"), 20, TEXT_MUTED, (VW - 30, 30), anchor="midright", bold=False)
            draw_text(img, fmt_int(best), 30, ACCENT_GOLD, (VW - 30, 62), anchor="midright")
            draw_vector_star(img, VW - 120, 108, radius=13, filled=True)
            draw_text(img, f"{stars}", 28, (255, 225, 120), (VW - 100, 108), anchor="midleft")
            if shields > 0:
                pygame.draw.circle(img, (80, 220, 255), (VW - 190, 108), 12, 3)
                draw_text(img, f"x{shields}", 24, (120, 235, 255), (VW - 172, 108), anchor="midleft")
            self._ekey = key
        surface.blit(self._eimg, (0, 0))
        # the way to the next diamond (one per DIAMOND_EVERY_M metres of a run)
        from endless import DIAMOND_EVERY_M
        frac = (metres % DIAMOND_EVERY_M) / float(DIAMOND_EVERY_M)
        bar = pygame.Rect(0, HUD_H - 8, VW, 8)
        pygame.draw.rect(surface, (20, 26, 40), bar)
        if frac > 0:
            pygame.draw.rect(surface, (0, 214, 255), (0, HUD_H - 8, int(VW * frac), 8))


class LoginRewardModal:
    """The 7-day login calendar (login_rewards.py): today's box glows, the days already taken in this run of days
    are ticked, day 7 is the weekly prize. Pops up on the menu once a day."""

    def __init__(self, save_mgr, on_claim, on_close):
        import login_rewards as lr
        self.lr = lr
        self.save_mgr, self.on_claim, self.on_close = save_mgr, on_claim, on_close
        self.claimed = None                    # (day, diamonds, stars) once taken
        self.anim = 0.0
        self.top = VH // 2 - 470
        cx = VW // 2
        self.btn_claim = Button((cx - 300, self.top + 760, 600, 104), "", 38, bg_color=(30, 190, 110),
                                hover_color=(70, 225, 150), callback=on_claim)
        self.btn_later = Button((cx - 150, self.top + 880, 300, 64), "", 24, bg_color=(70, 80, 110), callback=on_close)

    def _today(self):
        if self.claimed:
            return self.claimed[0], True
        if not self.lr.claimable(self.save_mgr):
            st = self.lr.state(self.save_mgr)
            return (int(st.get("streak", 1)) - 1) % 7 + 1, True
        return self.lr.next_day(self.save_mgr)[0], False

    def dyn_key(self):
        return (self.claimed, self.save_mgr.diamonds, get_language())

    def refresh_texts(self):
        pass

    def update(self, mouse_pos, dt=1.0):
        self.anim += dt
        self.btn_claim.update(mouse_pos, dt)
        self.btn_later.update(mouse_pos, dt)

    def handle_event(self, event):
        day, taken = self._today()
        if self.btn_claim.handle_event(event):
            return self.on_close if taken else self.on_claim
        if not taken and self.btn_later.handle_event(event):
            return self.on_close
        return None

    def _tile(self, surface, r, day, today, taken):
        gems = self.lr.LOGIN_REWARDS[day - 1]
        done = day < today or (day == today and taken)
        is_today = day == today
        big = day == 7
        gold = ACCENT_GOLD
        if is_today and not taken:
            surface.blit(neon_halo(r.w, r.h, gold, 22), (r.x - 12, r.y - 12))
        edge = gold if (is_today or big) else ((60, 200, 130) if done else (46, 68, 108))
        top = (58, 46, 18) if big else ((18, 44, 40) if done else ((30, 42, 70) if is_today else (20, 28, 48)))
        surface.blit(cockpit_surface(r.w, r.h, top, (10, 12, 24), edge, 22), r.topleft)
        draw_text(surface, t("login_day", n=day), 22, gold if (is_today or big) else (150, 165, 195), (r.centerx, r.y + 28))
        if big:
            draw_vector_gem(surface, r.centerx - 100, r.centery + 4, 24)
            draw_text(surface, f"+{gems}", 40, (130, 235, 255), (r.centerx - 68, r.centery + 4), anchor="midleft")
            draw_vector_star(surface, r.centerx + 52, r.centery + 4, radius=20, filled=True)
            draw_text(surface, f"+{self.lr.WEEKLY_STARS}", 34, (255, 225, 120), (r.centerx + 78, r.centery + 4),
                      anchor="midleft")
            draw_text(surface, t("login_weekly"), 20, gold, (r.centerx, r.bottom - 26))
        else:
            orbit_badge(surface, r.centerx, r.centery + 2, 30, gold if is_today else ACCENT_CYAN, "gem",
                        lit=is_today or done)
            draw_text(surface, f"+{gems}", 30, (130, 235, 255) if (is_today or done) else (150, 170, 200),
                      (r.centerx, r.bottom - 30))
        if done:
            cc = (r.right - 24, r.y + 24)
            pygame.draw.circle(surface, (30, 150, 90), cc, 15)
            pygame.draw.circle(surface, (120, 240, 170), cc, 15, 2)
            pygame.draw.lines(surface, (255, 255, 255), False, [(cc[0] - 7, cc[1]), (cc[0] - 2, cc[1] + 5), (cc[0] + 7, cc[1] - 5)], 3)

    def draw(self, surface):
        dim(surface, 215, (5, 8, 16))
        today, taken = self._today()
        card = pygame.Rect(40, self.top, VW - 80, 960)
        bg = None
        surface.blit(neon_halo(card.w, card.h, ACCENT_GOLD, 30), (card.x - 12, card.y - 12))
        surface.blit(cockpit_surface(card.w, card.h, (24, 30, 52), (8, 10, 22), ACCENT_GOLD, 30), card.topleft)
        draw_text(surface, t("login_title"), 46, ACCENT_GOLD, (VW // 2, self.top + 64), bg=bg, max_w=card.w - 60)
        draw_text(surface, t("login_sub"), 24, TEXT_MUTED, (VW // 2, self.top + 112), bold=False, bg=bg, max_w=card.w - 60)
        tw, th, gap = 176, 200, 16
        x0 = (VW - (4 * tw + 3 * gap)) // 2
        for i in range(4):
            self._tile(surface, pygame.Rect(x0 + i * (tw + gap), self.top + 160, tw, th), i + 1, today, taken)
        for i in range(2):
            self._tile(surface, pygame.Rect(x0 + i * (tw + gap), self.top + 160 + th + gap, tw, th), i + 5, today, taken)
        self._tile(surface, pygame.Rect(x0 + 2 * (tw + gap), self.top + 160 + th + gap, 2 * tw + gap, th), 7, today, taken)
        if self.claimed:
            day, gems, stars = self.claimed
            draw_text(surface, t("login_got", n=gems), 34, (130, 235, 255), (VW // 2, self.top + 640), bg=bg, max_w=card.w - 60)
            if stars:
                draw_vector_star(surface, VW // 2 - 40, self.top + 690, radius=16, filled=True)
                draw_text(surface, f"+{stars}", 30, (255, 225, 120), (VW // 2 - 16, self.top + 690), anchor="midleft", bg=bg)
            self.btn_claim.text = t("login_great")
        elif taken:
            draw_text(surface, t("login_come_back"), 26, TEXT_MUTED, (VW // 2, self.top + 640), bold=False, bg=bg,
                      max_w=card.w - 60)
            self.btn_claim.text = t("close")
        else:
            self.btn_claim.text = t("login_claim", n=self.lr.LOGIN_REWARDS[today - 1])
        self.btn_claim.draw(surface)
        if not taken:
            self.btn_later.text = t("login_later")
            self.btn_later.draw(surface)


class EndlessReviveModal:
    """The climb just ended: continue from a safe point for diamonds (at most endless.MAX_REVIVES per climb) or
    finish it. Works with HoloGame.revive_run like the campaign's failure card (`waiting`, `revive_cost`)."""

    def __init__(self, points, metres, stars, save_mgr, revive_cost, revives_left, on_revive, on_finish, label=None,
                 title_key="endless_paused_title", mode="endless"):
        self.points, self.metres, self.stars = points, metres, stars
        self.label = f"{fmt_int(metres)} m" if label is None else label        # the arena shows its time here
        self.title_key = title_key
        self.mode = mode                                                       # "endless" / "arena": the wording
        self.save_mgr, self.revive_cost, self.revives_left = save_mgr, revive_cost, revives_left
        self.on_revive, self.on_finish = on_revive, on_finish
        self.waiting = False
        self.anim = 0.0
        cx = VW // 2
        self.top = VH // 2 - 300
        self.btn_revive = Button((cx - 320, self.top + 330, 640, 104), "", 34, bg_color=(0, 190, 235),
                                 hover_color=(60, 225, 255), callback=on_revive)
        self.btn_finish = Button((cx - 320, self.top + 460, 640, 90), t(f"{mode}_finish_btn"), 30, bg_color=(120, 150, 215),
                                 callback=on_finish)
        self.ad_offer = None                   # (callback, ready()) set by HoloGame
        self.btn_ad = Button((cx - 320, self.top + 450, 640, 84), "", 28, bg_color=(150, 70, 235), hover_color=(190, 120, 255),
                             border_color=(200, 150, 255), callback=lambda: self._ad_on() and self.ad_offer[0]())

    def _enough(self):
        return self.save_mgr.diamonds >= self.revive_cost

    def dyn_key(self):
        return (self.save_mgr.diamonds, self.waiting, self._ad_on())

    def _ad_on(self):
        return bool(self.ad_offer and not self.waiting and self.ad_offer[1]())

    def refresh_texts(self):
        self.btn_finish.text = t(f"{self.mode}_finish_btn")

    def update(self, mouse_pos, dt=1.0):
        self.anim += dt
        for b in (self.btn_revive, self.btn_finish, self.btn_ad):
            b.update(mouse_pos, dt)

    def _layout(self):
        """With an ad offer the finish button moves down to make room for it."""
        ad = self._ad_on()
        self.btn_finish.rect.y = self.top + (550 if ad else 460)
        return ad

    def handle_event(self, event):
        ad = self._layout()
        if self.btn_revive.handle_event(event) and self._enough() and not self.waiting:
            return self.on_revive
        if ad and self.btn_ad.handle_event(event):
            return self.btn_ad.callback
        if self.btn_finish.handle_event(event):
            return self.on_finish
        return None

    def draw(self, surface):
        dim(surface, 200, (5, 8, 16))
        card = pygame.Rect(80, self.top, VW - 160, 600)
        bg = (14, 20, 34)
        panel(surface, card, bg, ACCENT_CYAN, 26, 2)
        draw_diamond_badge(surface, card.right - 80, self.top + 50, self.save_mgr.diamonds)
        ad = self._layout()
        if ad:
            card.h = 680
            panel(surface, card, bg, ACCENT_CYAN, 26, 2)
            draw_diamond_badge(surface, card.right - 80, self.top + 50, self.save_mgr.diamonds)
            self.btn_ad.text = t("ad_continue_btn")
            self.btn_ad.draw(surface)
        draw_text(surface, t(self.title_key), 40, ACCENT_CYAN, (VW // 2, self.top + 60), bg=bg, max_w=card.w - 200)
        draw_text(surface, fmt_int(self.points), 84, TEXT_WHITE, (VW // 2, self.top + 150), bg=bg)
        draw_text(surface, self.label, 30, (200, 210, 230), (VW // 2 - 40, self.top + 214), anchor="midright", bg=bg)
        draw_vector_star(surface, VW // 2 + 2, self.top + 214, radius=14, filled=True)
        draw_text(surface, f"{self.stars}", 30, (255, 225, 120), (VW // 2 + 24, self.top + 214), anchor="midleft", bg=bg)
        draw_text(surface, t(f"{self.mode}_revives_left", n=self.revives_left), 24, TEXT_MUTED, (VW // 2, self.top + 280),
                  bold=False, bg=bg)
        eb = self.btn_revive
        if self.waiting:
            eb.text, eb.icon = ". . .", None
        elif self._enough():
            eb.text, eb.icon = t("revive_btn", cost=self.revive_cost), "gem"
            eb.bg_color, eb.hover_color = (0, 190, 235), (60, 225, 255)
        else:
            eb.text, eb.icon = t("revive_need", cost=self.revive_cost), None
            eb.bg_color, eb.hover_color = (55, 60, 72), (65, 70, 84)
        eb.draw(surface)
        self.btn_finish.draw(surface)


class EndlessResultModal:
    """End of a climb: height, best, stage, diamonds (as the server grants them) and this week's world rank."""

    def __init__(self, metres, stage, week_best, all_best, new_best, sector, online, on_retry, on_menu, on_board,
                 points=None, stars=0, wallet=0, on_skins=None):
        self.metres, self.stage, self.sector = metres, stage, sector
        self.points = metres * 10 if points is None else points
        self.stars, self.wallet, self.on_skins = stars, wallet, on_skins
        self.week_best, self.all_best, self.new_best = week_best, all_best, new_best
        self.online = online
        self.anim = 0.0
        self.on_retry, self.on_menu, self.on_board = on_retry, on_menu, on_board
        cx = VW // 2
        self.top = VH // 2 - 420
        by = self.top + 640
        self.btn_retry = Button((cx - 320, by, 640, 104), t("endless_again"), 40, bg_color=(0, 190, 235),
                                hover_color=(60, 225, 255), callback=on_retry)
        self.btn_board = Button((cx - 320, by + 120, 310, 88), t("lb_title"), 28, bg_color=(35, 150, 110), callback=on_board)
        self.btn_menu = Button((cx + 10, by + 120, 310, 88), t("menu"), 30, bg_color=(120, 150, 215), callback=on_menu)
        # the star wallet and what it buys
        self.btn_skins = Button((cx - 320, by - 96, 640, 76), t("endless_star_skins"), 26, bg_color=(120, 90, 20),
                                hover_color=(170, 130, 40), border_color=ACCENT_GOLD, callback=on_skins)
        self.btn_skins.visible = on_skins is not None

    def dyn_key(self):
        on = self.online
        return (repr(on.endless_result) if on else None, on.enabled if on else False)

    def refresh_texts(self):
        self.btn_retry.text = t("endless_again")
        self.btn_board.text = t("lb_title")
        self.btn_menu.text = t("menu")

    def update(self, mouse_pos, dt=1.0):
        self.anim += dt
        for b in (self.btn_retry, self.btn_board, self.btn_menu, self.btn_skins):
            b.update(mouse_pos, dt)

    def handle_event(self, event):
        for b, cb in ((self.btn_retry, self.on_retry), (self.btn_board, self.on_board), (self.btn_menu, self.on_menu),
                      (self.btn_skins, self.on_skins)):
            if b.visible and b.handle_event(event):
                return cb
        return None

    def draw(self, surface):
        dim(surface, 205, (5, 8, 16))
        col = SECTOR_COL.get(self.sector, ACCENT_CYAN)
        card = pygame.Rect(80, self.top, VW - 160, 900)
        bg = (14, 20, 34)
        panel(surface, card, bg, col, 26, 2)
        draw_text(surface, t("endless_over"), 44, col, (VW // 2, self.top + 64), max_w=card.w - 40)
        draw_text(surface, fmt_int(self.points), 100, TEXT_WHITE, (VW // 2, self.top + 160), bg=bg)
        draw_text(surface, f"{fmt_int(self.metres)} m", 30, (200, 210, 230), (VW // 2 - 40, self.top + 228), anchor="midright", bg=bg)
        draw_vector_star(surface, VW // 2 + 2, self.top + 228, radius=14, filled=True)
        draw_text(surface, f"{self.stars}", 30, (255, 225, 120), (VW // 2 + 24, self.top + 228), anchor="midleft", bg=bg)
        if self.new_best:
            draw_text(surface, t("endless_new_best"), 34, ACCENT_GOLD, (VW // 2, self.top + 280), bg=bg)
        else:
            draw_text(surface, t("endless_week_best", m=fmt_int(self.week_best)), 28, ACCENT_GOLD, (VW // 2, self.top + 280), bg=bg)
        draw_text(surface, t("endless_star_wallet", n=self.stars, total=fmt_int(self.wallet)), 24, (255, 215, 120),
                  (VW // 2, self.top + 326), bold=False, bg=bg, max_w=card.w - 60)
        # server answer: verified height, diamonds, weekly rank
        info = self.online.endless_result if self.online else None
        y = self.top + 400
        if not (self.online and self.online.enabled):
            draw_text(surface, t("endless_offline"), 26, (255, 170, 90), (VW // 2, y), bold=False, max_w=card.w - 60)
        elif info is None:
            draw_text(surface, t("submit_wait"), 28, TEXT_MUTED, (VW // 2, y), bold=False)
        elif info.get("ok"):
            added = int(info.get("added", 0))
            if added > 0:
                draw_diamond_icon(surface, VW // 2 - 130, y, 16, (0, 230, 255))
                draw_text(surface, t("endless_diamonds", n=added), 34, (120, 235, 255), (VW // 2 - 100, y), anchor="midleft")
            elif info.get("capped"):
                draw_text(surface, t("endless_capped"), 24, TEXT_MUTED, (VW // 2, y), bold=False, max_w=card.w - 60)
            else:
                draw_text(surface, t("endless_next_gem", m=fmt_int(info.get("next_gem", 0))), 24, TEXT_MUTED, (VW // 2, y),
                          bold=False, max_w=card.w - 60)
            if info.get("rank"):
                draw_text(surface, t("endless_rank", rank=fmt_int(info["rank"]), total=fmt_int(info.get("total", 0))), 34,
                          ACCENT_GREEN, (VW // 2, y + 70), max_w=card.w - 60)
        else:
            key = "submit_rejected" if info.get("rejected") else "submit_queued"
            draw_text(surface, t(key), 24, (255, 170, 90), (VW // 2, y), bold=False, max_w=card.w - 60)
        for b in (self.btn_skins, self.btn_retry, self.btn_board, self.btn_menu):
            if b.visible:
                b.draw(surface)


def fmt_clock(secs):
    secs = int(secs)
    return f"{secs // 60}:{secs % 60:02d}"


def draw_core_icon(surface, x, y, r, color=(90, 230, 255)):
    """The arena's energy core (a turned square in a ring) - not the diamond currency."""
    pygame.draw.circle(surface, color, (x, y), r + 4, 2)
    pts = [(x, y - r), (x + r, y), (x, y + r), (x - r, y)]
    pygame.draw.polygon(surface, (210, 250, 255), pts)
    pygame.draw.polygon(surface, color, pts, 2)


class ArenaHUD(HUD):
    """Arena: pause, shield, the clock running down (big, with a bar that turns red when low), the core chain,
    points, record and stars."""

    def draw_arena(self, surface, time_left, max_time, points, best, stars, shields, chain, cores):
        low = time_left < 6.0
        col = (255, 90, 110) if low else (90, 230, 255)
        key = (int(time_left * 10), points, best, stars, shields, chain, cores, self.shield_stock, self.shield_active,
               get_language(), VW)
        if getattr(self, "_akey", None) != key:
            if getattr(self, "_aimg", None) is None or self._aimg.get_width() != VW:
                self._aimg = gfx.cv(pygame.Surface((VW, HUD_H + 1)))
            img = self._aimg
            pygame.draw.rect(img, (12, 16, 26), (0, 0, VW, HUD_H + 1))
            pygame.draw.line(img, (40, 55, 80), (0, HUD_H - 1), (VW, HUD_H - 1), 2)
            pr = self.pause_rect
            panel(img, pr, (24, 30, 46), (70, 88, 122), 20)
            for dx in (-13, 13):
                pygame.draw.rect(img, TEXT_WHITE, (pr.centerx + dx - 6, pr.centery - 22, 12, 44), border_radius=4)
            self._draw_shield_btn(img)
            draw_text(img, f"{t('arena_title')}  •  {fmt_int(points)}", 22, (255, 110, 150), (VW // 2 + 40, 28), max_w=400)
            draw_text(img, f"{time_left:0.1f}", 64, col, (VW // 2 + 40, 80), max_w=300)
            if chain > 1:
                draw_text(img, f"x{chain}", 34, ACCENT_GOLD, (VW // 2 + 170, 82), anchor="midleft")
            draw_text(img, t("arena_record_short"), 20, TEXT_MUTED, (VW - 30, 28), anchor="midright", bold=False)
            draw_text(img, fmt_int(best), 30, ACCENT_GOLD, (VW - 30, 60), anchor="midright")
            draw_vector_star(img, VW - 120, 106, radius=13, filled=True)
            draw_text(img, f"{stars}", 28, (255, 225, 120), (VW - 100, 106), anchor="midleft")
            draw_core_icon(img, VW - 212, 106, 9)
            draw_text(img, f"{cores}", 28, (150, 235, 255), (VW - 192, 106), anchor="midleft")
            if shields > 0:
                pygame.draw.circle(img, (80, 220, 255), (VW // 2 - 90, 126), 10, 3)
                draw_text(img, f"x{shields}", 22, (120, 235, 255), (VW // 2 - 74, 126), anchor="midleft")
            self._akey = key
        surface.blit(self._aimg, (0, 0))
        bar = pygame.Rect(0, HUD_H - 10, VW, 10)                 # the clock as a bar along the HUD's foot
        pygame.draw.rect(surface, (20, 26, 40), bar)
        frac = max(0.0, min(1.0, time_left / max_time))
        if frac > 0:
            pygame.draw.rect(surface, col, (0, HUD_H - 10, int(VW * frac), 10))


class ArenaResultModal:
    """End of an arena run: points, time survived, stars, the record."""

    def __init__(self, points, secs, stars, best, new_best, wallet, on_retry, on_menu, on_skins=None, cores=0,
                 timed_out=False):
        self.points, self.secs, self.stars, self.best, self.new_best = points, secs, stars, best, new_best
        self.cores, self.timed_out = cores, timed_out
        self.wallet = wallet
        self.on_retry, self.on_menu, self.on_skins = on_retry, on_menu, on_skins
        self.anim = 0.0
        cx = VW // 2
        self.top = VH // 2 - 380
        by = self.top + 520
        self.btn_retry = Button((cx - 320, by, 640, 104), t("arena_again"), 40, bg_color=(235, 70, 120),
                                hover_color=(255, 120, 160), callback=on_retry)
        self.btn_menu = Button((cx - 320, by + 120, 640, 88), t("menu"), 30, bg_color=(120, 150, 215), callback=on_menu)
        self.btn_skins = Button((cx - 320, by - 96, 640, 76), t("endless_star_skins"), 26, bg_color=(120, 90, 20),
                                hover_color=(170, 130, 40), border_color=ACCENT_GOLD, callback=on_skins)
        self.btn_skins.visible = on_skins is not None

    def dyn_key(self):
        return (self.wallet,)

    def refresh_texts(self):
        self.btn_retry.text = t("arena_again")
        self.btn_menu.text = t("menu")
        self.btn_skins.text = t("endless_star_skins")

    def update(self, mouse_pos, dt=1.0):
        self.anim += dt
        for b in (self.btn_retry, self.btn_menu, self.btn_skins):
            b.update(mouse_pos, dt)

    def handle_event(self, event):
        for b, cb in ((self.btn_retry, self.on_retry), (self.btn_menu, self.on_menu), (self.btn_skins, self.on_skins)):
            if b.visible and b.handle_event(event):
                return cb
        return None

    def draw(self, surface):
        dim(surface, 205, (5, 8, 16))
        col = (255, 110, 150)
        card = pygame.Rect(80, self.top, VW - 160, 760)
        bg = (14, 20, 34)
        panel(surface, card, bg, col, 26, 2)
        draw_text(surface, t("arena_timeout" if self.timed_out else "arena_over"), 44, col, (VW // 2, self.top + 64),
                  max_w=card.w - 40)
        draw_text(surface, fmt_int(self.points), 100, TEXT_WHITE, (VW // 2, self.top + 164), bg=bg)
        y = self.top + 236                                    # time survived • cores • stars
        draw_text(surface, fmt_clock(self.secs), 32, (200, 210, 230), (VW // 2 - 100, y), anchor="midright", bg=bg)
        draw_core_icon(surface, VW // 2 - 66, y, 10)
        draw_text(surface, f"{self.cores}", 30, (150, 235, 255), (VW // 2 - 48, y), anchor="midleft", bg=bg)
        draw_vector_star(surface, VW // 2 + 62, y, radius=14, filled=True)
        draw_text(surface, f"{self.stars}", 30, (255, 225, 120), (VW // 2 + 84, y), anchor="midleft", bg=bg)
        if self.new_best:
            draw_text(surface, t("arena_new_best"), 36, ACCENT_GOLD, (VW // 2, self.top + 300), bg=bg)
        else:
            draw_text(surface, t("arena_best", p=fmt_int(self.best)), 28, ACCENT_GOLD, (VW // 2, self.top + 300), bg=bg)
        draw_text(surface, t("endless_star_wallet", n=self.stars, total=fmt_int(self.wallet)), 24, (255, 215, 120),
                  (VW // 2, self.top + 350), bold=False, bg=bg, max_w=card.w - 60)
        for b in (self.btn_skins, self.btn_retry, self.btn_menu):
            if b.visible:
                b.draw(surface)


# ============================================================================================ shop showcase
class FeaturedScreen:
    """The shop's front page: three legendary skins of the day on big cards, each bought straight with real money
    (Google Play) or with diamonds. A discount running in the Play Console shows as a sale ribbon with the old price."""
    CARD_H, CARD_GAP, TOP = 330, 22, 168

    def __init__(self, save_manager, shop, on_back, on_all, audio_manager=None):
        self.save_mgr = save_manager
        self.shop = shop
        self.on_back = on_back
        self.on_all = on_all
        self.audio = audio_manager
        self.time_val = 0.0
        self.btn_back = back_button(on_back)
        self.btn_all = Button((VW // 2 - 320, self._card(3).y + 6, 640, 100), t("shop_all_btn"), 32,
                              bg_color=(96, 140, 255), hover_color=(140, 176, 255), callback=on_all)
        self.day = ""
        self.cards = []
        self.skins = []
        self.refresh()

    def _card(self, i):
        return pygame.Rect(40, self.TOP + i * (self.CARD_H + self.CARD_GAP), VW - 80, self.CARD_H)

    def refresh(self):
        import datetime
        day = datetime.date.today().isoformat()
        if day == self.day and self.cards:
            return
        self.day = day
        self.skins = catalog.featured_skins(3, day)
        self.cards = []
        for i, sid in enumerate(self.skins):
            r = self._card(i)
            money = Button((r.x + 330, r.bottom - 104, 236, 84), "", 30, bg_color=(255, 170, 40), hover_color=(255, 205, 100),
                           callback=(lambda s=sid: self._buy_money(s)))
            gems = Button((r.x + 582, r.bottom - 104, 214, 84), "", 28, icon="gem", callback=(lambda s=sid: self._buy_gems(s)))
            equip = Button((r.x + 330, r.bottom - 104, 466, 84), "", 32, bg_color=(96, 140, 255), hover_color=(140, 176, 255),
                           callback=(lambda s=sid: self._equip(s)))
            self.cards.append((sid, money, gems, equip))

    def refresh_texts(self):
        self.btn_back.text = t("back")
        self.btn_all.text = t("shop_all_btn")

    def _coin(self):
        return (lambda ok: self.audio and ok and self.audio.play_sfx("sfx_coin"))

    def _buy_money(self, sid):
        self.shop.buy_skin(sid, on_done=self._coin())

    def _buy_gems(self, sid):
        if self.save_mgr.diamonds >= self.shop.diamond_cost(sid):
            self.shop.buy_skin_with_diamonds(sid, on_done=self._coin())
        else:
            self.shop._say("shop_need_gems")

    def _equip(self, sid):
        self.save_mgr.equipped_skin = sid
        if self.audio:
            self.audio.play_sfx("sfx_swap")

    def _buttons(self):
        out = []
        for sid, money, gems, equip in self.cards:
            out += [equip] if self.save_mgr.is_skin_unlocked(sid) else [money, gems]
        return out

    def sig_extra(self):
        """Prices and sales arrive from Play asynchronously: part of what the (cached) screen shows."""
        return tuple((sid, self.shop.price_label(sid), self.shop.sale(sid), self.save_mgr.is_skin_unlocked(sid),
                      self.save_mgr.equipped_skin == sid) for sid in self.skins)

    def update(self, mouse_pos, dt=1.0):
        self.time_val += 0.035 * dt
        self.refresh()
        self.shop.poll()
        for b in [self.btn_back, self.btn_all] + self._buttons():
            b.update(mouse_pos, dt)

    def handle_event(self, event):
        if self.btn_back.handle_event(event):
            return self.on_back
        if self.btn_all.handle_event(event):
            return self.on_all
        for b in self._buttons():
            if b.handle_event(event):
                return b.callback
        return None

    def draw_dynamic(self, surface):
        for i, card in enumerate(self.cards):
            sk = SKINS[card[0]]
            r = self._card(i)
            cx, cy, d = r.x + 165, r.y + 150, 82
            a = self.time_val + i * 2.1
            p1 = (cx + math.cos(a) * d, cy + math.sin(a) * d * 0.62)
            p2 = (cx + math.cos(a + math.pi) * d, cy + math.sin(a + math.pi) * d * 0.62)
            draw_tether(surface, p1, p2, sk, self.time_val)
            draw_orb(surface, p1, 28, sk["color1"], sk["glow1"], False, sk, self.time_val)
            draw_orb(surface, p2, 28, sk["color2"], sk["glow2"], True, sk, self.time_val)

    def draw(self, surface):
        sm = self.save_mgr
        lang = get_language()
        header(surface, t("featured_title"), self.btn_back, None)
        draw_diamond_badge(surface, VW - 100, 74, sm.diamonds)
        gold = catalog.TIERS[1]["color"]
        bg = (14, 18, 32)
        for i, (sid, money, gems, equip) in enumerate(self.cards):
            sk = SKINS[sid]
            r = self._card(i)
            shadow_under(surface, r, 30, 80, 8, 26)
            pygame.draw.rect(surface, bg, r, border_radius=26)
            pygame.draw.rect(surface, (34, 30, 22), pygame.Rect(r.x + 18, r.y + 18, 294, r.h - 36), border_radius=22)
            pygame.draw.rect(surface, gold, r, 3, border_radius=26)
            x = r.x + 330
            draw_text(surface, catalog.tier_name(1, lang), 22, gold, (x, r.y + 38), anchor="midleft", bg=bg)
            draw_text(surface, sk["name"], 44, TEXT_WHITE, (x, r.y + 84), anchor="midleft", max_w=r.right - x - 24, bg=bg)
            draw_text(surface, skin_text.desc(sid, sk), 22, TEXT_MUTED, (x, r.y + 130), anchor="midleft", bold=False,
                      max_w=r.right - x - 24, bg=bg)
            if sm.is_skin_unlocked(sid):
                on = sm.equipped_skin == sid
                equip.text = t("equipped_btn") if on else t("equip")
                equip.bg_color = (60, 150, 110) if on else (96, 140, 255)
                equip.draw(surface)
                continue
            sale = self.shop.sale(sid)
            money.text = sale[0] if sale else self.shop.price_label(sid)
            cost = self.shop.diamond_cost(sid)
            enough = sm.diamonds >= cost
            gems.text = f"{cost}"
            gems.bg_color, gems.hover_color = ((0, 190, 235), (40, 225, 255)) if enough else ((70, 76, 96), (90, 96, 116))
            money.draw(surface)
            gems.draw(surface)
            draw_text(surface, t("shop_or_gems"), 20, TEXT_MUTED, (gems.rect.centerx, gems.rect.y - 16), bold=False, bg=bg)
            if sale:
                old = sale[1] or ""
                if old:
                    s = draw_text(surface, old, 22, (170, 150, 150), (money.rect.centerx, money.rect.y - 16), bold=False, bg=bg)
                    pygame.draw.line(surface, (255, 90, 100), (s.x - 2, s.centery), (s.right + 2, s.centery), 2)
                rib = pygame.Rect(0, 0, 196, 44)
                rib.topright = (r.right - 18, r.y + 18)
                pygame.draw.rect(surface, (230, 45, 70), rib, border_radius=22)
                draw_text(surface, t("sale_tag", n=sale[2]), 22, (255, 255, 255), rib.center, bg=(230, 45, 70))
        self.btn_all.draw(surface)
        msg = self.shop.current_message()
        y = self.btn_all.rect.bottom + 34
        if msg:
            draw_text(surface, t(msg), 26, (255, 232, 160), (VW // 2, y), max_w=820)
        elif not self.shop.open_for_business:
            draw_text(surface, t("shop_soon"), 22, (255, 200, 170), (VW // 2, y), bold=False, max_w=820)
        elif self.shop.billing.name == "dev":
            draw_text(surface, t("shop_test_mode"), 22, (255, 170, 190), (VW // 2, y), bold=False, max_w=820)
