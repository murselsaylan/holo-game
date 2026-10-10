"""Olo, the doodle mascot: a hand-drawn-looking blob alien (wobbly ink lines, stick arms, two antennae) in a set of
meme expressions. Drawn with pygame at any size; `boil` re-jitters the lines slightly so a still pose looks alive.

    draw(surface, pose, cx, cy, size, boil=0)    pose in POSES, (cx, cy) = middle of the body, size = body height
"""
import math
import random

import pygame

INK = (24, 22, 30)
BODY = (255, 255, 255)
GREEN = (120, 210, 70)
RED = (230, 60, 70)
BLUE = (110, 190, 255)
POSES = ("smug", "laugh", "film", "shock", "facepalm", "bored", "devil", "dead", "clap", "cry")


class _Pen:
    """Wobbly ink: every stroke is resampled and nudged by smooth noise (seeded per pose and per boil frame)."""

    def __init__(self, surf, cx, cy, k, seed):
        self.surf, self.cx, self.cy, self.k = surf, cx, cy, k
        self.rng = random.Random(seed)
        self.w = max(2, int(2.2 * k))

    def P(self, x, y):
        return (self.cx + x * self.k, self.cy + y * self.k)

    def _wobble(self, pts, amp):
        ph1, ph2 = self.rng.uniform(0, 6.28), self.rng.uniform(0, 6.28)
        out = []
        n = len(pts)
        for i, (x, y) in enumerate(pts):
            u = i / max(1, n - 1)
            out.append((x + amp * math.sin(u * 5.0 + ph1) + 0.4 * amp * math.sin(u * 13.0 + ph2),
                        y + amp * math.cos(u * 4.0 + ph2) + 0.4 * amp * math.cos(u * 11.0 + ph1)))
        return out

    @staticmethod
    def _resample(pts, step=4.0):
        out = [pts[0]]
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            d = math.hypot(x1 - x0, y1 - y0)
            n = max(1, int(d / step))
            out += [(x0 + (x1 - x0) * j / n, y0 + (y1 - y0) * j / n) for j in range(1, n + 1)]
        return out

    def stroke(self, pts, width=1.0, color=INK, amp=0.7, closed=False):
        pts = self._resample(list(pts) + ([pts[0]] if closed else []))
        pts = self._wobble(pts, amp)
        sp = [self.P(x, y) for x, y in pts]
        w = max(2, int(self.w * width))
        if len(sp) > 1:
            pygame.draw.lines(self.surf, color, False, sp, w)
        for p in sp[:: max(1, len(sp) // 40)] + [sp[0], sp[-1]]:
            pygame.draw.circle(self.surf, color, p, w // 2)

    def fill(self, pts, color):
        pygame.draw.polygon(self.surf, color, [self.P(x, y) for x, y in self._resample(pts, 6)])

    def dot(self, x, y, r, color=INK):
        pygame.draw.circle(self.surf, color, self.P(x, y), max(2, int(r * self.k)))

    def arc(self, cx, cy, rx, ry, a0, a1, width=1.0, color=INK, n=18):
        self.stroke([(cx + rx * math.cos(a0 + (a1 - a0) * i / n), cy + ry * math.sin(a0 + (a1 - a0) * i / n))
                     for i in range(n + 1)], width, color)

    def text(self, s, x, y, size, color=INK, angle=0):
        f = pygame.font.SysFont("comicsansms,segoeprint,arial", max(10, int(size * self.k)), bold=True)
        img = f.render(s, True, color)
        if angle:
            img = pygame.transform.rotate(img, angle)
        self.surf.blit(img, img.get_rect(center=self.P(x, y)))


def _smooth(ctrl, n=10):
    """Closed Catmull-Rom curve through the points: a soft, hand-made blob instead of corners."""
    out, m = [], len(ctrl)
    for i in range(m):
        p0, p1, p2, p3 = ctrl[i - 1], ctrl[i], ctrl[(i + 1) % m], ctrl[(i + 2) % m]
        for j in range(n):
            t = j / n
            t2, t3 = t * t, t * t * t
            out.append(tuple(0.5 * (2 * p1[c] + (-p0[c] + p2[c]) * t + (2 * p0[c] - 5 * p1[c] + 4 * p2[c] - p3[c]) * t2
                                    + (-p0[c] + 3 * p1[c] - 3 * p2[c] + p3[c]) * t3) for c in (0, 1)))
    return out


def _body(p):
    """Tall narrow bean (origin in its middle): slightly lopsided round top, sides widening a touch, flat bottom,
    two short stick legs; thin ink like a quick doodle. Two antennae with green bobbles make him Olo."""
    ctrl = [(-2, -54), (16, -49), (26, -32), (27, -6), (30, 24), (28, 43), (14, 50), (0, 50), (-16, 50), (-29, 44),
            (-30, 22), (-27, -6), (-25, -32), (-17, -48)]
    outline = _smooth(ctrl)
    p.fill(outline, BODY)
    p.stroke(outline, 1.0, closed=True)
    for sx in (-8, 8):                                    # little stick legs
        p.stroke([(sx, 48), (sx + (1 if sx > 0 else -1), 60)], 0.9)
        p.stroke([(sx + (1 if sx > 0 else -1), 60), (sx + (6 if sx > 0 else -6), 60)], 0.9)
    for sx in (-1, 1):                                    # antennae with green bobbles
        p.stroke([(8 * sx, -51), (12 * sx, -62), (15 * sx, -68)], 0.8)
        p.dot(16 * sx, -70, 3.6, GREEN)
    return outline


def _arm(p, pts, width=0.9):
    p.stroke(pts, width)


def draw(surf, pose, cx, cy, size, boil=0):
    k = size / 125.0
    p = _Pen(surf, cx, cy, k, hash((pose, boil)) & 0xFFFF)
    _body(p)
    eye_y, mouth_y = -18, 6
    if pose == "smug":                                    # half-lidded side-eye, smirk, arms crossed
        for x in (-12, 10):
            p.stroke([(x - 7, eye_y), (x + 7, eye_y)], 0.9)
            p.dot(x + 4, eye_y + 4, 3.2)
        p.stroke([(-10, mouth_y + 4), (4, mouth_y + 6), (14, mouth_y)], 0.9)
        _arm(p, [(-31, 18), (-6, 26), (20, 20)])
        _arm(p, [(31, 18), (6, 28), (-18, 22)])
    elif pose == "laugh":                                 # > <, huge open mouth, tears, pointing at you
        p.stroke([(-18, eye_y - 6), (-9, eye_y), (-18, eye_y + 6)], 0.9)
        p.stroke([(18, eye_y - 6), (9, eye_y), (18, eye_y + 6)], 0.9)
        mouth = [(-14, mouth_y - 2), (14, mouth_y - 2), (10, mouth_y + 14), (0, mouth_y + 18), (-10, mouth_y + 14)]
        p.fill(mouth, (60, 20, 30))
        p.stroke(mouth, 0.9, closed=True)
        p.fill([(-6, mouth_y + 12), (6, mouth_y + 12), (3, mouth_y + 17), (-3, mouth_y + 17)], (240, 110, 130))
        for x in (-24, 24):
            p.stroke([(x, eye_y + 6), (x + (2 if x > 0 else -2), eye_y + 16)], 0.8, BLUE)
            p.dot(x + (2 if x > 0 else -2), eye_y + 18, 3, BLUE)
        _arm(p, [(31, 14), (48, 2), (60, -6)])
        p.stroke([(60, -6), (66, -12)], 0.8)
        _arm(p, [(-31, 16), (-40, 30), (-30, 40)])
        for i, (x, y) in enumerate(((-52, -40), (52, -48), (-44, -58))):
            p.text("HA", x, y, 12 + i * 2, INK, angle=(-14 + i * 14))
    elif pose == "film":                                  # filming you with his phone, red REC dot
        p.dot(-12, eye_y, 3.5)
        p.stroke([(4, eye_y - 2), (16, eye_y - 2)], 0.9)
        p.stroke([(-10, mouth_y + 2), (6, mouth_y + 6), (14, mouth_y + 1)], 0.9)
        phone = [(22, -8), (44, -12), (48, 26), (26, 30)]
        p.fill(phone, (40, 44, 60))
        p.stroke(phone, 0.9, closed=True)
        p.dot(30, -4, 3.5, RED)
        p.text("REC", 37, 8, 7, (255, 255, 255))
        _arm(p, [(31, 16), (28, 22)])
        _arm(p, [(-31, 14), (-10, 24), (24, 24)])
    elif pose == "shock":                                 # fake shock: big eyes, little o mouth, ?!
        for x in (-12, 12):
            p.arc(x, eye_y, 7, 8, 0, 6.3, 0.8)
            p.dot(x, eye_y, 2.4)
        p.arc(0, mouth_y + 8, 5, 6, 0, 6.3, 0.8)
        _arm(p, [(-31, 10), (-46, -8), (-50, -22)])
        _arm(p, [(31, 10), (46, -8), (50, -22)])
        p.text("?!", 46, -50, 22)
        for a in (-0.7, 0.0, 0.7):
            p.stroke([(-48 + 10 * math.sin(a), -40 - 6 * math.cos(a)), (-52 + 16 * math.sin(a), -48 - 10 * math.cos(a))], 0.7)
    elif pose == "facepalm":                              # hand over the eyes, deep sigh
        p.stroke([(-8, mouth_y + 8), (8, mouth_y + 8)], 0.9)
        hand = [(-18, eye_y - 10), (18, eye_y - 10), (20, eye_y + 6), (-16, eye_y + 8)]
        p.fill(hand, BODY)
        p.stroke(hand, 0.9, closed=True)
        for x in (-8, 2, 12):
            p.stroke([(x, eye_y - 10), (x, eye_y + 6)], 0.5)
        _arm(p, [(31, 10), (34, -8), (20, -14)])
        _arm(p, [(-31, 18), (-38, 34), (-30, 42)])
        p.text("...", 44, -40, 20)
    elif pose == "bored":                                 # asleep while you play, zzz
        for x in (-12, 12):
            p.arc(x, eye_y + 2, 6, 3, 0.1, 3.0, 0.9)
        p.stroke([(-6, mouth_y + 6), (6, mouth_y + 6)], 0.9)
        p.dot(-2, mouth_y + 14, 2.5, BLUE)
        _arm(p, [(-31, 18), (-40, 34), (-34, 44)])
        _arm(p, [(31, 18), (40, 34), (34, 44)])
        for i in range(3):
            p.text("z", 34 + i * 10, -40 - i * 12, 12 + i * 5)
    elif pose == "devil":                                 # devil horns, evil toothy grin, pitchfork
        for sx in (-1, 1):
            p.fill([(14 * sx, -46), (26 * sx, -58), (24 * sx, -42)], RED)
            p.stroke([(14 * sx, -46), (26 * sx, -58), (24 * sx, -42)], 0.7, closed=True)
        p.stroke([(-20, eye_y - 8), (-6, eye_y - 2)], 0.9)
        p.stroke([(20, eye_y - 8), (6, eye_y - 2)], 0.9)
        p.dot(-11, eye_y + 3, 3)
        p.dot(11, eye_y + 3, 3)
        teeth = [(-16, mouth_y)] + [(-16 + i * 4, mouth_y + (6 if i % 2 else 0)) for i in range(1, 9)] + [(16, mouth_y)]
        p.stroke([(-18, mouth_y - 2), (0, mouth_y + 12), (18, mouth_y - 2)], 0.9)
        p.stroke(teeth, 0.6)
        _arm(p, [(31, 14), (42, 4)])
        p.stroke([(44, 40), (44, -30)], 0.8)
        p.stroke([(36, -24), (36, -34), (44, -30), (52, -34), (52, -24)], 0.8)
        _arm(p, [(-31, 18), (-40, 32), (-32, 40)])
        p.stroke([(26, 46), (40, 56), (36, 64), (46, 62)], 0.7, RED)
    elif pose == "dead":                                  # x x, tongue out (for when YOU crash: "skull")
        for x in (-12, 12):
            p.stroke([(x - 6, eye_y - 6), (x + 6, eye_y + 6)], 0.9)
            p.stroke([(x + 6, eye_y - 6), (x - 6, eye_y + 6)], 0.9)
        p.stroke([(-10, mouth_y + 4), (10, mouth_y + 4)], 0.9)
        p.fill([(2, mouth_y + 4), (10, mouth_y + 4), (8, mouth_y + 14), (3, mouth_y + 13)], (240, 110, 130))
        _arm(p, [(-31, 18), (-46, 30)])
        _arm(p, [(31, 18), (46, 30)])
    elif pose == "clap":                                  # slow sarcastic clap, unimpressed eyes
        for x in (-12, 10):
            p.stroke([(x - 6, eye_y), (x + 6, eye_y)], 0.9)
            p.dot(x, eye_y + 3, 2.6)
        p.stroke([(-8, mouth_y + 6), (8, mouth_y + 6)], 0.9)
        _arm(p, [(-31, 18), (-14, 30), (-2, 26)])
        _arm(p, [(31, 18), (14, 30), (2, 26)])
        for a in (-0.6, 0, 0.6):
            p.stroke([(14 * math.sin(a), 16 - 4 * math.cos(a)), (22 * math.sin(a), 8 - 6 * math.cos(a))], 0.6)
        p.text("clap", -46, -44, 11, angle=12)
        p.text("clap", 48, -50, 11, angle=-12)
    elif pose == "cry":                                   # "ağla" - fake crying for you, streams of tears
        for x in (-12, 12):
            p.arc(x, eye_y, 6, 4, 3.3, 6.1, 0.9)
            p.stroke([(x, eye_y + 2), (x, eye_y + 40)], 1.1, BLUE)
        p.arc(0, mouth_y + 12, 8, 6, 3.3, 6.1, 0.9)
        _arm(p, [(-31, 18), (-44, 4), (-50, -6)])
        p.fill([(-58, -14), (-44, -16), (-42, -2), (-56, 0)], (255, 255, 255))
        p.stroke([(-58, -14), (-44, -16), (-42, -2), (-56, 0)], 0.6, closed=True)
        _arm(p, [(31, 18), (40, 32), (32, 42)])
