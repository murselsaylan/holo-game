"""Olo - the mascot who mocks you on the failure screen (1.0.9).

A doodle alien (stickers in assets/olo/, built from the developer's sticker sheets by tools/olo_assets.py) who sits
on the top edge of the failure window - his lower half hidden behind it - with a small talk box beside him: a couple
of still poses that hop from one to the next, each with a line typed out. What he says depends on how you crashed
(olo_lines.py).

On with config "olo" (off until 1.0.9) or HOLO_OLO=1, and the player's setting "olo" (default on).
"""
import math
import os
import random

import pygame

import config
import paths
from fonts import get_font
from locales import get_language
from olo_lines import R

ASSETS = paths.asset("olo")
BEAT_S = 3.0                      # one pose + line
TYPE_CPS = 32                     # letters per second
HIDE = 46                         # how much of him is behind the window's top edge
EDGE = (0, 214, 255)


def enabled(save_mgr):
    return bool(config.get("olo", False) or os.environ.get("HOLO_OLO") == "1") and \
        bool(save_mgr.settings.get("olo", True))


def kind_of(attempts, pct, best_pct, alive_s):
    if alive_s < 2.5 or pct < 8:
        return "quick"
    if pct >= 75:
        return "near"
    if attempts >= 6:
        return "many"
    if best_pct and pct > best_pct and attempts > 1:
        return "best"
    if attempts >= 3:
        return "repeat"
    return "fail"


class Olo:
    def __init__(self):
        self._img = {}
        self._recent = []
        self.beats = []
        self.t = 0.0
        self.active = False
        self.kind = ""

    def react(self, attempts, pct, best_pct, alive_s):
        self.kind = kind_of(attempts, pct, best_pct, alive_s)
        pool = R[self.kind]
        fresh = [r for r in pool if id(r) not in self._recent] or pool
        pick = random.choice(fresh)
        self._recent = (self._recent + [id(pick)])[-30:]
        lang = get_language()
        self.beats = [(st, (txt.get(lang) or txt["en"]).format(n=attempts, pct=pct)) for st, txt in pick]
        self.t = 0.0
        self.active = True
        return self.kind

    def hide(self):
        self.active = False

    def update(self, dt):
        if self.active:
            self.t += dt

    def _sticker(self, name, h):
        key = (name, h)
        if key not in self._img:
            try:
                im = pygame.image.load(os.path.join(ASSETS, name + ".png"))
                im = im.convert_alpha() if pygame.display.get_surface() else im
            except Exception:
                im = pygame.Surface((10, 10), pygame.SRCALPHA)
            k = h / im.get_height()
            if im.get_width() * k > h * 1.5:                       # lying / sleeping poses: limit by width
                k = h * 1.5 / im.get_width()
            self._img[key] = pygame.transform.smoothscale(im, (max(1, int(im.get_width() * k)), max(1, int(im.get_height() * k))))
        return self._img[key]

    def draw(self, surf, window):
        """window: the failure window's rect; Olo sits on its top edge (left part), the talk box to his right."""
        if not self.active or not self.beats:
            return
        t = self.t - 0.3                                           # a breath after the window lands
        if t < 0:
            return
        i = min(len(self.beats) - 1, int(t // BEAT_S))
        bt = t - i * BEAT_S
        sticker, line = self.beats[i]
        img = self._sticker(sticker, 250)
        # hop on every new pose: squash, overshoot, settle; a slow sway keeps a still drawing alive
        if bt < 0.07:
            sx, sy = 1.12, 0.84
        elif bt < 0.16:
            sx, sy = 0.93, 1.10
        elif bt < 0.26:
            sx, sy = 1.02, 0.98
        else:
            sx, sy = 1.0, 1.0
        rise = min(1.0, t / 0.28)                                  # first appearance: rises from behind the window
        im = pygame.transform.rotozoom(img, math.sin(self.t * 2.2) * 1.6, 1.0)
        im = pygame.transform.smoothscale(im, (max(1, int(im.get_width() * sx)), max(1, int(im.get_height() * sy))))
        foot = (window.x + 40 + img.get_width() // 2, window.y + HIDE + int((1 - rise) * (img.get_height() - HIDE)))
        clip = surf.get_clip()
        surf.set_clip(pygame.Rect(0, 0, surf.get_width(), window.y + 3))
        surf.blit(im, im.get_rect(midbottom=foot))
        surf.set_clip(clip)
        # talk box: dark glass, neon edge, OLO tag, the line typed out
        f = get_font(28, bold=True)
        bx = window.x + 40 + img.get_width() + 14
        bw = min(window.right - bx - 6, 400)
        if bw < 200:
            return
        shown = line[:max(0, int((bt - 0.15) * TYPE_CPS))]
        lines = self._wrap(f, line, bw - 36)                       # the box fits the whole line; the text types in
        typed = self._wrap(f, shown, bw - 36) if shown else []
        bh = 30 + 36 * len(lines)
        box = pygame.Rect(bx, window.y - 34 - bh, bw, bh)
        pane = pygame.Surface(box.size, pygame.SRCALPHA)
        pygame.draw.rect(pane, (10, 16, 30, 238), pane.get_rect(), border_radius=18)
        pygame.draw.rect(pane, EDGE + (255,), pane.get_rect(), 3, border_radius=18)
        surf.blit(pane, box.topleft)
        ty = box.y + min(40, box.h - 18)
        tail = [(box.x + 2, ty - 13), (box.x - 18, ty), (box.x + 2, ty + 13)]
        pygame.draw.polygon(surf, (10, 16, 30), tail)
        pygame.draw.lines(surf, EDGE, False, tail, 3)
        tf = get_font(20, bold=True)
        tag = tf.render("OLO", True, (8, 14, 24))
        tr = pygame.Rect(box.x + 16, box.y - 14, tag.get_width() + 22, 28)
        pygame.draw.rect(surf, EDGE, tr, border_radius=14)
        surf.blit(tag, tag.get_rect(center=tr.center))
        for k, l in enumerate(typed[:4]):
            surf.blit(f.render(l, True, (235, 245, 255)), (box.x + 18, box.y + 18 + k * 36))

    @staticmethod
    def _wrap(f, text, width):
        words, lines, cur = text.split(" "), [], ""
        for w in words:
            nxt = (cur + " " + w).strip()
            if f.size(nxt)[0] > width and cur:
                lines.append(cur)
                cur = w
            else:
                cur = nxt
        lines.append(cur)
        return lines
