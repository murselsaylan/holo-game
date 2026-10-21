"""Small vector product illustrations sharing HOLO's energy-orb vocabulary."""
import pygame
from render_cache import SurfaceCache

_CACHE = SurfaceCache(2 * 1024 * 1024)


def product_art(dst, kind, center, size=88, level=1):
    size = max(16, int(size))
    key = (kind, size, level)
    img = _CACHE.get(key)
    if img is None:
        img = pygame.Surface((size, size), pygame.SRCALPHA)
        c, r = size / 2, size * .39
        col = (255, 202, 75) if kind == "chest" else (199, 125, 255) if kind == "revive" else (25, 224, 255)
        light = tuple(min(255, v + 75) for v in col)
        dark = tuple(max(12, v // 7) for v in col)
        w = max(1, size // 36)

        def pt(x, y):
            return (round(c + x * r), round(c + y * r))

        def poly(points, fill, edge=None):
            points = [pt(x, y) for x, y in points]
            pygame.draw.polygon(img, fill, points)
            if edge:
                pygame.draw.polygon(img, edge, points, w)

        def line(points, color=col, width=w):
            pygame.draw.lines(img, color, False, [pt(x, y) for x, y in points], width)

        def orb(x, y, rr, color=col):
            p = pt(x, y)
            pygame.draw.circle(img, tuple(v // 5 for v in color), p, max(1, round(rr * r)))
            pygame.draw.circle(img, color, p, max(1, round(rr * r)), max(1, w))
            pygame.draw.circle(img, light, pt(x - rr * .23, y - rr * .23), max(1, round(rr * r * .2)))

        if kind == "shield":
            from ui import draw_shield_icon
            draw_shield_icon(img, round(c), round(c), r * .9)
        elif kind == "revive":
            rr = r * .8
            pygame.draw.arc(img, col, (c - rr, c - rr, 2 * rr, 2 * rr), -.6, 4.6, max(2, w * 2))
            poly([(.1, -1.03), (-.3, -.8), (.1, -.57)], col)
        elif kind == "chest":
            pygame.draw.circle(img, (*col, 14), (round(c), round(c)), round(r * 1.2))
            # Faceted energy vault, with a lit seam and charged centre lock.
            poly([(-1, -.45), (-.65, -.9), (.65, -.9), (1, -.45), (.85, .78), (-.85, .78)], dark, col)
            poly([(-1, -.45), (1, -.45), (.65, -.9), (-.65, -.9)], (66, 48, 25), light)
            line([(-1, -.25), (1, -.25)], light, max(2, w))
            for sign in (-1, 1):
                line([(sign * .65, -.8), (sign * .65, .63)], col, max(2, w))
                line([(sign * .95, .45), (sign * .7, .7)], light)
            orb(0, -.1, .32, col)
            poly([(0, -.32), (.14, -.1), (0, .12), (-.14, -.1)], light)
            for x in (-.35, .35):
                line([(x, -1.02), (x * .7, -1.2)], col)
        else:
            from ui import draw_diamond_icon
            draw_diamond_icon(img, round(c), round(c), round(r * .9))
        _CACHE.put(key, img)
    dst.blit(img, (round(center[0] - size / 2), round(center[1] - size / 2)))
