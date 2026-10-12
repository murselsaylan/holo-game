"""Olo - the mascot who mocks you (1.0.8): on the failure and victory windows, the endless climb's windows and,
once a session, on the main menu - never while you play.

A doodle alien (stickers in assets/olo/, built from the developer's sticker sheets by tools/olo_assets.py) who sits
on a window's top edge - his lower half hidden behind it - with a small talk box beside him, or on the menu peeks up
from the bottom of the screen with the box above his head: a couple of still poses that hop from one to the next,
each with a line typed out. What he says depends on what happened (olo_lines.py, olo_lines_places.py).

On with config "olo" (since 1.0.8) or HOLO_OLO=1, and the player's setting "olo" (default on).
"""
import math
import os
import random
import time
import zlib

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
        self.beats = []
        self.t = 0.0
        self.active = False
        self.kind = ""
        self.where = ""
        self.delay = 0.3
        self.store = None                 # the save's data dict: which lines were said (kept across sessions)
        self.blip = None                  # a letter just typed that wants a voice blip (HoloGame plays it)
        self._letters = 0
        self._beat_i = -1
        self._used = {}

    def react(self, attempts, pct, best_pct, alive_s):
        """The failure screen: the kind of crash picks the lines."""
        kind = kind_of(attempts, pct, best_pct, alive_s)
        pool = R[kind]
        hour = time.localtime().tm_hour                 # night owls and early birds get their own lines now and then
        clock = "night" if hour < 5 else ("morning" if 6 <= hour < 10 else None)
        if clock and kind in ("fail", "repeat") and random.random() < 0.25:
            pool = R[clock]
        self.say(kind, "fail", bag=clock if pool is not R[kind] else None, n=attempts, pct=pct)
        return kind

    def _pick(self, bag, skip=None):
        """A random reaction from R[bag] that has not been said yet: every line comes once, in a random order, before
        any comes again (a shuffle bag, kept in the save so a new session does not start over). Reactions whose
        English text contains `skip` (a placeholder that would read oddly now, like {m} at 0 m) are left out."""
        pool = R[bag]
        ok = [i for i, r in enumerate(pool) if not (skip and any(skip in tx["en"] for _, tx in r))] or \
            list(range(len(pool)))
        used_all = self.store.setdefault("olo_used", {}) if self.store is not None else self._used
        keys = [zlib.crc32(r[0][1]["en"].encode()) & 0xFFFFFF for r in pool]
        said = [k for k in used_all.get(bag, []) if k in keys]
        fresh = [i for i in ok if keys[i] not in said]
        if not fresh:                                  # all said: a new round, not opening with the last few
            last, said = said[-3:], []
            fresh = [i for i in ok if keys[i] not in last] or ok
        i = random.choice(fresh)
        used_all[bag] = said + [keys[i]]
        return pool[i]

    def say(self, kind, where="fail", delay=0.3, bag=None, **vals):
        """Starts a reaction of `kind` (from the pool `bag`, default the kind's own); `where` is the screen it
        belongs to (HoloGame._draw_olo)."""
        pick = self._pick(bag or kind, "{m}" if "m" in vals and vals["m"] < 10 else None)
        lang = get_language()
        fmt = dict(n=0, pct=0, m=0, lvl=1, d=0, name="", h=0)
        fmt.update(vals)
        self.beats = [(st, (txt.get(lang) or txt["en"]).format(**fmt)) for st, txt in pick]
        self.kind, self.where, self.delay = kind, where, delay
        self._letters, self._beat_i, self.blip = 0, -1, None
        self.t = 0.0
        self.active = True

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

    def _pose(self, size):
        """The current beat: (base sticker, hopping + swaying sticker, time shown, time into the beat, line) or None."""
        if not self.active or not self.beats:
            return None
        t = self.t - self.delay                                    # a breath after the window lands
        if t < 0:
            return None
        i = min(len(self.beats) - 1, int(t // BEAT_S))
        bt = t - i * BEAT_S
        sticker, line = self.beats[i]
        if i != self._beat_i:                                      # a new pose: its line starts typing from 0
            self._beat_i, self._letters = i, 0
        img = self._sticker(sticker, size)
        # hop on every new pose: squash, overshoot, settle; a slow sway keeps a still drawing alive
        if bt < 0.07:
            sx, sy = 1.12, 0.84
        elif bt < 0.16:
            sx, sy = 0.93, 1.10
        elif bt < 0.26:
            sx, sy = 1.02, 0.98
        else:
            sx, sy = 1.0, 1.0
        im = pygame.transform.rotozoom(img, math.sin(self.t * 2.2) * 1.6, 1.0)
        im = pygame.transform.smoothscale(im, (max(1, int(im.get_width() * sx)), max(1, int(im.get_height() * sy))))
        return img, im, t, bt, line

    def draw(self, surf, window):
        """window: a modal's rect; Olo sits on its top edge (left part), the talk box to his right. With little room
        above the window he shrinks; with too little he stays away."""
        size = min(250, window.y - 8 + HIDE)
        if size < 170:
            return
        pose = self._pose(size)
        if pose is None:
            return
        img, im, t, bt, line = pose
        rise = min(1.0, t / 0.28)                                  # first appearance: rises from behind the window
        foot = (window.x + 40 + img.get_width() // 2, window.y + HIDE + int((1 - rise) * (img.get_height() - HIDE)))
        clip = surf.get_clip()
        surf.set_clip(pygame.Rect(0, 0, surf.get_width(), window.y + 3))
        surf.blit(im, im.get_rect(midbottom=foot))
        surf.set_clip(clip)
        f = get_font(28, bold=True)
        bx = window.x + 40 + img.get_width() + 14
        bw = min(window.right - bx - 6, 400)
        if bw < 200:
            return
        lines = self._wrap(f, line, bw - 36)                       # the box fits the whole line; the text types in
        bh = 30 + 36 * len(lines)
        box = pygame.Rect(bx, max(18, window.y - 34 - bh), bw, bh)
        ty = box.y + min(40, box.h - 18)
        self._box(surf, box, [(box.x + 2, ty - 13), (box.x - 18, ty), (box.x + 2, ty + 13)], line, bt)

    def draw_peek(self, surf, cx, bottom, stay=2.0):
        """The menu: he peeks up from the bottom edge at cx, the talk box above his head; after the last line
        (+ `stay` s) he sinks back down and is gone."""
        pose = self._pose(230)
        if pose is None:
            return
        img, im, t, bt, line = pose
        end = len(self.beats) * BEAT_S + stay
        if t > end + 0.35:
            self.active = False
            return
        show = min(1.0, t / 0.28, max(0.0, (end + 0.3 - t) / 0.3))
        foot = (cx, bottom + HIDE + int((1 - show) * (img.get_height() - HIDE)))
        clip = surf.get_clip()
        surf.set_clip(pygame.Rect(0, 0, surf.get_width(), bottom))
        surf.blit(im, im.get_rect(midbottom=foot))
        surf.set_clip(clip)
        if t > end:
            return
        f = get_font(28, bold=True)
        bw = min(surf.get_width() - 40, 440)
        bh = 30 + 36 * len(self._wrap(f, line, bw - 36))
        head = bottom + HIDE - img.get_height()
        box = pygame.Rect(cx - bw // 2, head - 26 - bh, bw, bh)
        tail = [(cx - 14, box.bottom - 2), (cx + 4, box.bottom + 20), (cx + 14, box.bottom - 2)]
        self._box(surf, box, tail, line, bt)

    def _box(self, surf, box, tail, line, bt):
        """Dark glass, neon edge, the OLO tag, the line typed out."""
        f = get_font(28, bold=True)
        shown = line[:max(0, int((bt - 0.15) * TYPE_CPS))]
        typed = self._wrap(f, shown, box.w - 36) if shown else []
        letters = [c for c in shown if c.isalnum()]
        if len(letters) > self._letters:                           # his voice: a blip every second letter
            if len(letters) // 2 > self._letters // 2:
                self.blip = letters[-1]
            self._letters = len(letters)
        pane = pygame.Surface(box.size, pygame.SRCALPHA)
        pygame.draw.rect(pane, (10, 16, 30, 238), pane.get_rect(), border_radius=18)
        pygame.draw.rect(pane, EDGE + (255,), pane.get_rect(), 3, border_radius=18)
        surf.blit(pane, box.topleft)
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
