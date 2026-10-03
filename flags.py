"""Vector country flags for the leaderboard (no emoji fonts needed on Android)."""
import pygame
from save_manager import COUNTRIES
from fonts import get_font
from theme import TEXT_WHITE


def get_country_info(code):
    for c in COUNTRIES:
        if c["code"] == code:
            return c
    return {"code": code, "flag": "🌐", "name": code, "color": (120, 140, 170)}

def draw_flag_icon(surface, country_code, rect):
    x, y, w, h = rect.x, rect.y, rect.width, rect.height
    pygame.draw.rect(surface, (20, 25, 35), rect)

    if country_code == "TR":
        pygame.draw.rect(surface, (227, 10, 23), rect)
        cx, cy = x + w * 0.42, y + h * 0.5
        r = h * 0.32
        pygame.draw.circle(surface, (255, 255, 255), (int(cx), int(cy)), int(r))
        pygame.draw.circle(surface, (227, 10, 23), (int(cx + r * 0.35), int(cy)), int(r * 0.8))
        sx, sy = int(cx + r * 0.85), int(cy)
        pygame.draw.circle(surface, (255, 255, 255), (sx, sy), max(1, int(r * 0.28)))

    elif country_code == "US":
        stripe_h = max(1, h // 5)
        for s in range(5):
            c = (178, 34, 52) if s % 2 == 0 else (255, 255, 255)
            pygame.draw.rect(surface, c, (x, y + s * stripe_h, w, stripe_h))
        pygame.draw.rect(surface, (60, 59, 110), (x, y, int(w * 0.45), int(stripe_h * 3)))
        pygame.draw.circle(surface, (255, 255, 255), (x + int(w * 0.22), y + int(stripe_h * 1.5)), 1)

    elif country_code == "DE":
        sh = h // 3
        pygame.draw.rect(surface, (20, 20, 20), (x, y, w, sh))
        pygame.draw.rect(surface, (221, 0, 0), (x, y + sh, w, sh))
        pygame.draw.rect(surface, (255, 206, 0), (x, y + 2 * sh, w, h - 2 * sh))

    elif country_code == "GB":
        pygame.draw.rect(surface, (1, 33, 105), rect)
        pygame.draw.line(surface, (255, 255, 255), (x, y), (x + w, y + h), 2)
        pygame.draw.line(surface, (255, 255, 255), (x, y + h), (x + w, y), 2)
        pygame.draw.line(surface, (255, 255, 255), (x + w // 2, y), (x + w // 2, y + h), 4)
        pygame.draw.line(surface, (255, 255, 255), (x, y + h // 2), (x + w, y + h // 2), 4)
        pygame.draw.line(surface, (200, 16, 46), (x + w // 2, y), (x + w // 2, y + h), 2)
        pygame.draw.line(surface, (200, 16, 46), (x, y + h // 2), (x + w, y + h // 2), 2)

    elif country_code == "JP":
        pygame.draw.rect(surface, (245, 245, 245), rect)
        pygame.draw.circle(surface, (188, 0, 45), (x + w // 2, y + h // 2), max(2, int(h * 0.28)))

    elif country_code == "KR":
        pygame.draw.rect(surface, (245, 245, 245), rect)
        cx, cy = x + w // 2, y + h // 2
        r = max(2, int(h * 0.28))
        pygame.draw.circle(surface, (205, 46, 58), (cx, cy), r)
        pygame.draw.circle(surface, (0, 71, 160), (cx, cy + r // 2), r // 2)

    elif country_code == "FR":
        sw = w // 3
        pygame.draw.rect(surface, (0, 38, 84), (x, y, sw, h))
        pygame.draw.rect(surface, (245, 245, 245), (x + sw, y, sw, h))
        pygame.draw.rect(surface, (237, 41, 57), (x + 2 * sw, y, w - 2 * sw, h))

    elif country_code == "BR":
        pygame.draw.rect(surface, (0, 156, 59), rect)
        pts = [(x + w // 2, y + 2), (x + w - 2, y + h // 2), (x + w // 2, y + h - 2), (x + 2, y + h // 2)]
        pygame.draw.polygon(surface, (255, 223, 0), pts)
        pygame.draw.circle(surface, (0, 39, 118), (x + w // 2, y + h // 2), max(2, int(h * 0.22)))

    elif country_code == "CA":
        sw = w // 4
        pygame.draw.rect(surface, (216, 6, 33), (x, y, sw, h))
        pygame.draw.rect(surface, (245, 245, 245), (x + sw, y, w - 2 * sw, h))
        pygame.draw.rect(surface, (216, 6, 33), (x + w - sw, y, sw, h))
        pygame.draw.circle(surface, (216, 6, 33), (x + w // 2, y + h // 2), max(2, int(h * 0.22)))

    elif country_code == "AU":
        pygame.draw.rect(surface, (0, 0, 139), rect)
        pygame.draw.rect(surface, (200, 16, 46), (x, y, w // 2, h // 2))
        pygame.draw.line(surface, (255, 255, 255), (x, y + h // 4), (x + w // 2, y + h // 4), 1)
        pygame.draw.line(surface, (255, 255, 255), (x + w // 4, y), (x + w // 4, y + h // 2), 1)
        pygame.draw.circle(surface, (255, 255, 255), (x + int(w * 0.75), y + int(h * 0.4)), 1)
        pygame.draw.circle(surface, (255, 255, 255), (x + int(w * 0.75), y + int(h * 0.7)), 1)

    elif country_code == "IT":
        sw = w // 3
        pygame.draw.rect(surface, (0, 146, 70), (x, y, sw, h))
        pygame.draw.rect(surface, (245, 245, 245), (x + sw, y, sw, h))
        pygame.draw.rect(surface, (206, 43, 55), (x + 2 * sw, y, w - 2 * sw, h))

    elif country_code == "ES":
        sh = h // 4
        pygame.draw.rect(surface, (170, 21, 27), (x, y, w, sh))
        pygame.draw.rect(surface, (241, 191, 0), (x, y + sh, w, sh * 2))
        pygame.draw.rect(surface, (170, 21, 27), (x, y + 3 * sh, w, h - 3 * sh))

    elif country_code == "NL":
        sh = h // 3
        pygame.draw.rect(surface, (174, 28, 40), (x, y, w, sh))
        pygame.draw.rect(surface, (245, 245, 245), (x, y + sh, w, sh))
        pygame.draw.rect(surface, (33, 70, 139), (x, y + 2 * sh, w, h - 2 * sh))

    elif country_code == "AZ":
        sh = h // 3
        pygame.draw.rect(surface, (0, 181, 226), (x, y, w, sh))
        pygame.draw.rect(surface, (239, 51, 64), (x, y + sh, w, sh))
        pygame.draw.rect(surface, (80, 158, 47), (x, y + 2 * sh, w, h - 2 * sh))
        pygame.draw.circle(surface, (255, 255, 255), (x + w // 2, y + h // 2), 2)

    elif country_code == "SE":
        pygame.draw.rect(surface, (0, 106, 167), rect)
        pygame.draw.line(surface, (254, 204, 0), (x + int(w * 0.38), y), (x + int(w * 0.38), y + h), 2)
        pygame.draw.line(surface, (254, 204, 0), (x, y + h // 2), (x + w, y + h // 2), 2)

    else: # GX / Cosmos
        pygame.draw.rect(surface, (35, 15, 60), rect)
        pygame.draw.circle(surface, (0, 240, 255), (x + w // 2, y + h // 2), max(2, int(h * 0.32)), 1)
        pygame.draw.circle(surface, (255, 255, 255), (x + w // 2, y + h // 2), 1)

    pygame.draw.rect(surface, (70, 85, 115), rect, 1)

def draw_country_badge(surface, country_code, center_x, center_y, width=64, height=26):
    info = get_country_info(country_code)
    badge_rect = pygame.Rect(0, 0, width, height)
    badge_rect.center = (center_x, center_y)

    # Dark cybernetic rounded pill background
    pygame.draw.rect(surface, (18, 24, 38), badge_rect, border_radius=6)
    pygame.draw.rect(surface, (50, 65, 95), badge_rect, 1, border_radius=6)

    # Flag icon on left side of badge
    flag_rect = pygame.Rect(badge_rect.left + 5, badge_rect.centery - 7, 21, 14)
    draw_flag_icon(surface, country_code, flag_rect)

    # Text: 2-letter country code
    f = get_font(13, bold=True)
    txt_surf = f.render(info["code"], True, TEXT_WHITE)
    surface.blit(txt_surf, (badge_rect.left + 31, badge_rect.centery - txt_surf.get_height() // 2))

