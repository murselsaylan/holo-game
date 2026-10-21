"""The share card (1.0.9): after a record, a hard level or the level of the week, one tap makes a picture with Olo, the
level, the stars and the store link text - 1080x1920 (stories) and 1080x1080 (square) - and hands it to the phone's share
sheet (share.py). Drawn with pygame only; the numbers come from the clear that just happened (the server is not involved:
a card is a picture, it earns nothing).

    make("record", level, stars, score, seconds, attempts, size="story") -> path of a png
"""
import os
import random

import pygame

import paths
import ui
from locales import get_language, t

PLAY_URL = "https://play.google.com/store/apps/details?id=com.hologame.holo"
APPLE_URL = "https://apps.apple.com/app/id6819440077"
SIZES = {"story": (1080, 1920), "square": (1080, 1080)}
STICKER = {"record": "hooray", "hard": "flex", "weekly": "party"}
COLORS = {"record": (255, 215, 60), "hard": (255, 120, 90), "weekly": (255, 170, 80)}
VARIANTS = tuple(STICKER)


def store_text():
    """The store line printed on the card (and the link text sent with it) for this platform."""
    if paths.is_ios():
        return "App Store", APPLE_URL
    return "Google Play", PLAY_URL


def message(variant, level):
    """The text that travels with the picture into the share sheet."""
    name, url = store_text()
    return f"{t('sh_head_' + variant)}  HOLO - {t('cw_wl_level', lvl=level)}\n{url}"


def _background(size, seed):
    w, h = size
    surf = pygame.Surface(size)
    top, bot = (8, 12, 28), (46, 20, 78)
    for y in range(h):
        k = y / max(1, h - 1)
        pygame.draw.line(surf, tuple(int(top[i] + (bot[i] - top[i]) * k) for i in range(3)), (0, y), (w, y))
    rnd = random.Random(seed)
    for _ in range(int(w * h / 9000)):
        x, y, r = rnd.randrange(w), rnd.randrange(h), rnd.choice((1, 1, 1, 2, 2, 3))
        c = rnd.choice(((200, 220, 255), (255, 236, 170), (150, 190, 255)))
        pygame.draw.circle(surf, tuple(int(v * rnd.uniform(0.35, 0.9)) for v in c), (x, y), r)
    return surf


def _orbit_pair(surf, center, rad, col1=(255, 70, 160), col2=(0, 220, 255)):
    """The game's two orbs on their tether: a small logo ornament."""
    cx, cy = center
    p1, p2 = (cx - rad, cy), (cx + rad, cy)
    pygame.draw.line(surf, (160, 220, 255), p1, p2, 6)
    for p, c in ((p1, col1), (p2, col2)):
        glow = pygame.Surface((rad, rad), pygame.SRCALPHA)
        pygame.draw.circle(glow, c + (70,), (rad // 2, rad // 2), rad // 2)
        surf.blit(glow, (p[0] - rad // 2, p[1] - rad // 2))
        pygame.draw.circle(surf, c, p, rad // 5)
        pygame.draw.circle(surf, (255, 255, 255), p, rad // 5, 3)


def _sticker(name, height):
    path = paths.asset("olo", f"{name}.png")
    try:
        im = pygame.image.load(path).convert_alpha()
    except Exception:
        return None
    w, h = im.get_size()
    return pygame.transform.smoothscale(im, (max(1, int(w * height / h)), height))


def _bubble(surf, rect, text, size):
    pygame.draw.rect(surf, (236, 242, 255), rect, border_radius=36)
    pygame.draw.rect(surf, (90, 120, 190), rect, 5, border_radius=36)
    tail = [(rect.centerx - 30, rect.bottom - 4), (rect.centerx + 30, rect.bottom - 4), (rect.centerx, rect.bottom + 46)]
    pygame.draw.polygon(surf, (236, 242, 255), tail)
    pygame.draw.lines(surf, (90, 120, 190), False, [tail[0], tail[2], tail[1]], 5)
    f = ui.get_font(size, True)
    words, lines, cur = text.split(), [], ""
    for wd in words:
        cand = (cur + " " + wd).strip()
        if cur and f.size(cand)[0] > rect.w - 70:
            lines.append(cur)
            cur = wd
        else:
            cur = cand
    lines.append(cur)
    lh = f.get_linesize()
    y0 = rect.centery - (len(lines) - 1) * lh / 2
    for i, line in enumerate(lines[:3]):
        ui.draw_text(surf, line, size, (20, 28, 60), (rect.centerx, int(y0 + i * lh)), max_w=rect.w - 60)


def _stars(surf, cx, cy, n, r):
    for i in range(3):
        ui.draw_vector_star(surf, cx + (i - 1) * int(r * 2.6), cy, radius=r, filled=i < n)


def _facts(variant, level, score, seconds, attempts):
    parts = [t("cw_wl_level", lvl=level)]
    if score:
        parts.append(f"{ui.fmt_int(score)} {t('pts')}")
    if seconds:
        parts.append(f"{seconds:.1f}s")
    line = "  -  ".join(parts)
    extra = t("sh_tries", n=attempts) if attempts and attempts >= 3 and variant != "record" else ""
    return line, extra


def make(variant, level, stars, score=0, seconds=0.0, attempts=1, size="story", out_dir=None, language=None):
    """Draws the card and writes it as a png; returns the path."""
    if variant not in STICKER:
        variant = "record"
    w, h = SIZES[size]
    surf = _background((w, h), seed=level * 31 + len(variant))
    col = COLORS[variant]
    store, url = store_text()
    facts, extra = _facts(variant, level, score, seconds, attempts)
    olo_line = t("sh_olo_" + variant)
    story = size == "story"
    head_size = 92 if story else 74

    if story:
        ui.draw_text(surf, "HOLO", 190, (255, 255, 255), (w // 2, 190))
        _orbit_pair(surf, (w // 2, 330), 90)
        y = 520
        for line in _wrap(t("sh_head_" + variant), head_size, w - 140):
            ui.draw_text(surf, line, head_size, col, (w // 2, y), max_w=w - 120)
            y += head_size + 14
        ui.draw_text(surf, facts, 54, (255, 255, 255), (w // 2, y + 50), max_w=w - 120)
        _stars(surf, w // 2, y + 160, stars, 52)
        if extra:
            ui.draw_text(surf, extra, 40, (190, 205, 235), (w // 2, y + 250), bold=False, max_w=w - 120)
        st = _sticker(STICKER[variant], 620)
        by = 1080
        _bubble(surf, pygame.Rect(w // 2 - 380, by, 760, 190), olo_line, 44)
        if st:
            surf.blit(st, st.get_rect(midtop=(w // 2, by + 250)))
        foot = pygame.Rect(0, h - 210, w, 210)
    else:
        ui.draw_text(surf, "HOLO", 120, (255, 255, 255), (250, 100))
        _orbit_pair(surf, (250, 200), 62)
        y = 330
        for line in _wrap(t("sh_head_" + variant), head_size, 590):
            ui.draw_text(surf, line, head_size, col, (330, y), max_w=600)
            y += head_size + 8
        ui.draw_text(surf, facts, 40, (255, 255, 255), (330, y + 36), max_w=600)
        _stars(surf, 330, y + 118, stars, 40)
        if extra:
            ui.draw_text(surf, extra, 32, (190, 205, 235), (330, y + 190), bold=False, max_w=600)
        st = _sticker(STICKER[variant], 440)
        _bubble(surf, pygame.Rect(590, 70, 440, 190), olo_line, 34)
        if st:
            surf.blit(st, st.get_rect(midbottom=(790, h - 170 + 36)))
        foot = pygame.Rect(0, h - 170, w, 170)

    # the store strip: where to get it
    pygame.draw.rect(surf, (10, 14, 30), foot)
    pygame.draw.line(surf, col, (0, foot.y), (w, foot.y), 4)
    ui.draw_text(surf, t("sh_try"), 52 if story else 44, (255, 255, 255), (w // 2, foot.y + (62 if story else 48)), max_w=w - 100)
    ui.draw_text(surf, f"{store}:  {url.replace('https://', '')}", 30 if story else 26, (150, 215, 255),
                 (w // 2, foot.y + (134 if story else 112)), bold=False, max_w=w - 80)

    out_dir = out_dir or os.path.join(paths.user_dir(), "share")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"holo_{variant}_{level}_{size}.png")
    pygame.image.save(surf, path)
    return path


def _wrap(text, size, max_w):
    f = ui.get_font(size, True)
    lines, cur = [], ""
    for wd in text.split():
        cand = (cur + " " + wd).strip()
        if cur and f.size(cand)[0] > max_w:
            lines.append(cur)
            cur = wd
        else:
            cur = cand
    lines.append(cur)
    return lines[:3]
