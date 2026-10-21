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
import threading
import time
import zlib

import pygame

import config
import perfstat
import paths
from fonts import get_font
from locales import get_language
from olo_lines import R

ASSETS = paths.asset("olo")
BEAT_S = 3.0                      # one pose + line
TYPE_CPS = 32                     # letters per second
HIDE = 46                         # how much of him is behind the window's top edge
EDGE = (0, 214, 255)
SIZES = (250, 230)                # the sticker heights used (failure / victory windows, the menu peek)
SQUASH = ((1.12, 0.84), (0.93, 1.10), (1.02, 0.98))    # the hop onto a new pose, pre-made (no per-frame transform)


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
        self._lock = threading.Lock()
        self._conv = set()
        self._loading = set()
        self._wraps = {}                  # (font, line, width) -> wrapped lines
        self._pane = None                 # (key, surface): the talk box with its text, redrawn only when it changes
        self._tag = None
        self.bob = 0
        self._prep = 0

    SHIELD_TIP_TRIES = 3                  # from the 3rd death Olo now and then points at the shield button

    def react(self, attempts, pct, best_pct, alive_s, shield_tip=False):
        """The failure screen: the kind of crash picks the lines. `shield_tip`: the window has a shield button."""
        kind = kind_of(attempts, pct, best_pct, alive_s)
        if shield_tip and attempts >= self.SHIELD_TIP_TRIES and kind not in ("quick",) and random.random() < 0.5:
            self.say("shield_tip", "fail", n=attempts, pct=pct)             # his own pool (olo_lines_shield.py)
            return "shield_tip"
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
        self._load([st for st, _ in self.beats])                    # ready before the window has landed
        self._prep = 0
        self.kind, self.where, self.delay = kind, where, delay
        self._letters, self._beat_i, self.blip = 0, -1, None
        self.t = 0.0
        self.active = True

    def hide(self):
        self.active = False

    def update(self, dt):
        if self.active:
            self.t += dt
            if self._prep < len(self.beats):                       # one line's text layout per frame, before he
                f = get_font(28, bold=True)                         # shows: no font measuring on his first frame
                line = self.beats[self._prep][1]
                for w in (364, 404):
                    self._wrap(f, line, w)
                self._prep += 1

    @staticmethod
    def _make(name, h):
        """The sticker at height h and its three hop variants (loaded and scaled off the main thread)."""
        try:
            im = pygame.image.load(os.path.join(ASSETS, name + ".png"))
        except Exception:
            im = pygame.Surface((10, 10), pygame.SRCALPHA)
        k = h / im.get_height()
        if im.get_width() * k > h * 1.5:                       # lying / sleeping poses: limit by width
            k = h * 1.5 / im.get_width()
        base = pygame.transform.smoothscale(im, (max(1, int(im.get_width() * k)), max(1, int(im.get_height() * k))))
        hops = [pygame.transform.smoothscale(base, (max(1, int(base.get_width() * sx)), max(1, int(base.get_height() * sy))))
                for sx, sy in SQUASH]
        out = [base] + hops
        if pygame.display.get_surface():                       # display format here too, not on the first frame
            out = [x.convert_alpha() for x in out]
        return out

    def _load(self, names):
        """Prepares these stickers in a thread: the first frame Olo shows no longer reads and scales a PNG (that
        was a 60+ ms hitch on phones, again on every new pose)."""
        todo = [(n, h) for n in names for h in SIZES if (n, h) not in self._img and (n, h) not in self._loading]
        if not todo:
            return
        self._loading.update(todo)

        def work():
            perfstat.busy("olo", True)
            try:
                _work()
            finally:
                perfstat.busy("olo", False)

        def _work():
            for key in todo:
                try:
                    surfs = self._make(*key)
                except Exception:
                    surfs = [pygame.Surface((10, 10), pygame.SRCALPHA)] * 4
                with self._lock:
                    self._img[key] = surfs
                    self._loading.discard(key)
                    self._conv.add(key)
        threading.Thread(target=work, daemon=True).start()

    def _sticker(self, name, h):
        """[base, hop1, hop2, hop3] at height h, or None while it is still being prepared."""
        h = SIZES[0] if h >= SIZES[0] else (SIZES[1] if h >= SIZES[1] - 5 else int(h // 10 * 10))
        key = (name, h)
        with self._lock:
            got = self._img.get(key)
        if got is None:
            if key in self._loading:
                return None
            if h in SIZES:                                         # not asked for yet: ask now, show next frame
                self._load([name])
                return None
            got = self._make(name, h)                              # an unusual size: made here (rare)
            with self._lock:
                self._img[key] = got
        if key not in self._conv and pygame.display.get_surface():
            got = [g.convert_alpha() for g in got]                 # display format once, on the main thread
            with self._lock:
                self._img[key] = got
            self._conv.add(key)
        return got

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
        surfs = self._sticker(sticker, size)
        if surfs is None:                                          # still being prepared: he shows a frame later
            return None
        img = surfs[0]
        # hop on every new pose: squash, overshoot, settle (pre-made); a slow bob keeps a still drawing alive
        im = surfs[1] if bt < 0.07 else surfs[2] if bt < 0.16 else surfs[3] if bt < 0.26 else img
        self.bob = int(round(math.sin(self.t * 2.2) * 3))
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
        surf.blit(im, im.get_rect(midbottom=(foot[0], foot[1] + self.bob)))
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
        surf.blit(im, im.get_rect(midbottom=(foot[0], foot[1] + self.bob)))
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
        key = (box.size, shown)
        if self._pane is None or self._pane[0] != key:            # redrawn only when a letter appears
            pane = pygame.Surface(box.size, pygame.SRCALPHA)
            pygame.draw.rect(pane, (10, 16, 30, 238), pane.get_rect(), border_radius=18)
            pygame.draw.rect(pane, EDGE + (255,), pane.get_rect(), 3, border_radius=18)
            for k, l in enumerate(typed[:4]):
                pane.blit(f.render(l, True, (235, 245, 255)), (18, 18 + k * 36))
            self._pane = (key, pane)
        surf.blit(self._pane[1], box.topleft)
        pygame.draw.polygon(surf, (10, 16, 30), tail)
        pygame.draw.lines(surf, EDGE, False, tail, 3)
        if self._tag is None:
            self._tag = get_font(20, bold=True).render("OLO", True, (8, 14, 24))
        tag = self._tag
        tr = pygame.Rect(box.x + 16, box.y - 14, tag.get_width() + 22, 28)
        pygame.draw.rect(surf, EDGE, tr, border_radius=14)
        surf.blit(tag, tag.get_rect(center=tr.center))

    def _wrap(self, f, text, width):
        key = (id(f), text, width)
        got = self._wraps.get(key)
        if got is not None:
            return got
        if len(self._wraps) > 256:
            self._wraps.clear()
        self._wraps[key] = got = self._wrap_now(f, text, width)
        return got

    @staticmethod
    def _wrap_now(f, text, width):
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
