"""Distinct neon frame silhouettes and title insignia, shared by shop and ranking."""
import math
import pygame
import shop_items as SI

TITLE_COLORS = {
    "title_pilot": (80, 210, 255), "title_comet": (115, 180, 255),
    "title_orbit": (70, 240, 195), "title_nova": (255, 150, 80),
    "title_void": (180, 125, 255), "title_legend": (255, 210, 80),
    "title_pulse": (255, 100, 170), "title_collector": (255, 231, 150),
    "title_hunter": (120, 225, 255),
}


def frame_art(surface, rect, frame_id, w=3):
    info = SI.FRAME.get(frame_id)
    if info is None:
        return
    r = pygame.Rect(rect)
    c1, c2 = info[3:5]
    w = max(1, min(w, max(1, r.h // 12)))
    x, y, rw, rh = r.x, r.y, r.w, r.h
    bevel = max(4, min(12, rh // 5))
    pts = [(x + bevel, y), (r.right - bevel, y), (r.right, y + bevel),
           (r.right, r.bottom - bevel), (r.right - bevel, r.bottom),
           (x + bevel, r.bottom), (x, r.bottom - bevel), (x, y + bevel)]
    pygame.draw.polygon(surface, tuple(v // 4 for v in c2), pts, max(w + 2, 3))
    pygame.draw.polygon(surface, c1, pts, w)

    def line(points, col=c1, width=w):
        pygame.draw.lines(surface, col, False, points, width)

    def gem(cx, cy, rr, col=c1):
        pygame.draw.polygon(surface, col, [(cx, cy - rr), (cx + rr, cy), (cx, cy + rr), (cx - rr, cy)])

    if frame_id == "frame_bronze":
        for xx in (x + bevel, r.right - bevel):
            for yy in (y + 3, r.bottom - 3):
                pygame.draw.circle(surface, c1, (xx, yy), max(1, w))
        line([(x + rw * .25, r.bottom - 3), (x + rw * .75, r.bottom - 3)], c2)
    elif frame_id == "frame_silver":
        for sign, xx in ((1, x), (-1, r.right)):
            line([(xx + sign * 3, y + rh * .2), (xx + sign * 7, y + rh * .4),
                  (xx + sign * 3, y + rh * .6)], c2)
        line([(x + bevel, y + 4), (r.right - bevel, y + 4)], c2, 1)
        line([(x + bevel, r.bottom - 4), (r.right - bevel, r.bottom - 4)], c2, 1)
    elif frame_id == "frame_gold":
        for xx in (x + rw * .25, r.centerx, x + rw * .75):
            gem(xx, y, max(2, w + 1))
        line([(x + 4, r.centery + 4), (x - 4, r.centery), (x + 4, r.centery - 4)])
        line([(r.right - 4, r.centery + 4), (r.right + 4, r.centery), (r.right - 4, r.centery - 4)])
    elif frame_id == "frame_nebula":
        for j in range(3):
            xx = x + rw * (.2 + j * .3)
            line([(xx - 5, y - 2), (xx, y + 2), (xx + 7, y - 2)], c2)
            gem(xx, r.bottom, max(1, w), c2)
        line([(x, y + rh * .3), (x - 3, r.centery), (x, y + rh * .7)], c2)
    elif frame_id == "frame_diamond":
        for xx, yy in ((x + bevel, y), (r.right - bevel, y), (x + bevel, r.bottom), (r.right - bevel, r.bottom)):
            gem(xx, yy, max(3, w + 1), c2)
        pygame.draw.polygon(surface, c2, [(x + bevel + 4, y + 4), (r.right - bevel - 4, y + 4),
                                          (r.right - 4, y + bevel), (r.right - 4, r.bottom - bevel),
                                          (r.right - bevel - 4, r.bottom - 4), (x + bevel + 4, r.bottom - 4),
                                          (x + 4, r.bottom - bevel), (x + 4, y + bevel)], 1)
    elif frame_id in ("frame_stardust", "frame_comet"):
        for j in range(5):
            xx = x + rw * (.12 + j * .18)
            yy = y if j % 2 else r.bottom
            if frame_id == "frame_comet":
                line([(xx - 7, yy - 3), (xx + 3, yy)], c2, 1)
            gem(xx, yy, max(2, w), c1)
    else:
        # Limited frames have recognisable border rhythms, not palette swaps.
        for j in range(5):
            xx = x + rw * (.12 + j * .19)
            for yy, sign in ((y, -1), (r.bottom, 1)):
                if frame_id == "lim_ember":
                    line([(xx - 4, yy), (xx, yy + sign * 5), (xx + 3, yy)], c2)
                elif frame_id == "lim_frost":
                    line([(xx - 4, yy - 3), (xx + 4, yy + 3)], c2, 1)
                    line([(xx - 4, yy + 3), (xx + 4, yy - 3)], c1, 1)
                elif frame_id == "lim_toxic":
                    line([(xx - 4, yy + 2), (xx + 4, yy - 2)], c2, max(2, w))
                elif frame_id == "lim_rose":
                    pygame.draw.circle(surface, c2, (round(xx), yy), max(2, w + 1))
                    gem(xx, yy, max(1, w - 1), c1)
                elif frame_id == "lim_ion":
                    line([(xx - 5, yy), (xx - 1, yy - 3), (xx + 1, yy + 3), (xx + 5, yy)], c2, 1)
                else:
                    line([(xx - 5, yy), (xx + 5, yy)], c2, max(2, w))


def title_emblem(surface, title_id, center, size=32):
    if title_id not in TITLE_COLORS:
        return
    col = TITLE_COLORS[title_id]
    cx, cy = center
    r = size * .4
    w = max(1, size // 15)

    def p(a, b):
        return (round(cx + a * r), round(cy + b * r))

    def line(pts, width=w):
        pygame.draw.lines(surface, col, False, [p(a, b) for a, b in pts], width)

    if title_id == "title_pilot":
        for b in (-.6, 0, .6):
            line([(-.8, b), (0, b + .4), (.8, b)])
    elif title_id == "title_comet":
        pygame.draw.circle(surface, col, p(.4, .35), max(2, round(r * .42)), w)
        line([(-1, -.8), (.2, 0)])
        line([(-1, -.2), (-.1, .4)], 1)
    elif title_id == "title_orbit":
        pygame.draw.ellipse(surface, col, (cx - r, cy - r * .45, r * 2, r * .9), w)
        pygame.draw.circle(surface, col, (round(cx), round(cy)), max(2, round(r * .32)))
        pygame.draw.circle(surface, col, p(.8, -.28), max(1, w))
    elif title_id == "title_nova":
        pts = [p(math.cos(j * math.pi / 4) * (1 if j % 2 == 0 else .35),
                 math.sin(j * math.pi / 4) * (1 if j % 2 == 0 else .35)) for j in range(8)]
        pygame.draw.polygon(surface, col, pts, w)
    elif title_id == "title_void":
        pygame.draw.circle(surface, col, (round(cx), round(cy)), max(2, round(r * .65)), w)
        pygame.draw.arc(surface, col, (cx - r, cy - r, r * 2, r * 2), .1, 2.4, w)
    elif title_id == "title_legend":
        line([(-1, -.5), (-.65, .7), (.65, .7), (1, -.5), (.4, 0), (0, -.8), (-.4, 0), (-1, -.5)])
        line([(-.55, 1), (.55, 1)])
    elif title_id == "title_pulse":
        line([(-1.1, 0), (-.5, 0), (-.2, -.8), (.1, .8), (.4, -.3), (.6, 0), (1.1, 0)])
    elif title_id == "title_collector":
        for a, b in ((-.6, .4), (0, -.45), (.6, .4)):
            line([(a - .23, b), (a + .23, b)])
            line([(a, b - .23), (a, b + .23)])
    else:
        line([(-.7, -.7), (.7, .7)])
        line([(-.7, .7), (.7, -.7)])
        pygame.draw.circle(surface, col, (round(cx), round(cy)), max(2, round(r * .65)), w)
