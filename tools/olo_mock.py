"""Mock-up: the failure screen with Olo (the 1.0.9 mascot idea), rendered from the real game at phone size.

    python tools/olo_mock.py [lang]   -> store_assets/olo_mock_<lang>.png
"""
import math
import os
import sys
import tempfile

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["HOLO_SAVE_DIR"] = tempfile.mkdtemp(prefix="holo_olo_")
os.environ["HOLO_SERVER"] = "http://127.0.0.1:1"
PANEL = (1080, 2340)

import pygame  # noqa: E402
import paths  # noqa: E402
import safe_area  # noqa: E402

paths.is_mobile = lambda: True
safe_area.insets_px = lambda h: (0, 0)
pygame.init()


class _Panel:
    current_w, current_h = PANEL


pygame.display.Info = lambda: _Panel()
import holo  # noqa: E402
import locales  # noqa: E402
from fonts import get_font  # noqa: E402

LANG = sys.argv[1] if len(sys.argv) > 1 else "tr"
LINE = {"tr": ["Bu bölümü benim", "büyükannem geçti."], "en": ["My grandma beat", "this level. Just saying."]}[LANG]

g = holo.HoloGame(headless=True)
sm = g.save_mgr
sm.data.update(is_profile_set=True, player_name="NOVA", player_country="TR", howto_seen=True)
sm.language = LANG
locales.set_language(LANG)
g.on_language_change()
for lvl in range(1, 5):
    sm.stats[str(lvl)] = {"stars": 3, "best_score": 5000, "best_time": 12.0, "best_swaps": 6, "rank": "S"}
sm.data["campaign_level"] = 5
g.toasts = []
g.load_and_play_level(5)
for _ in range(50):
    g.update(1 / 60.0, (450, 900))
g.sim.dead = True
g.state, g.death_timer = "dying", 0.01
for _ in range(90):
    g.update(1 / 60.0, (450, 900))
    g.draw()
g.toasts = []
g.draw()
frame = g.frame.copy()
W, H = frame.get_size()
print("frame", W, H, "state", g.state)


def _poly(surf, color, pts, outline, w):
    pygame.draw.polygon(surf, color, pts)
    pygame.draw.polygon(surf, outline, pts, w)


def olo2(surf, cx, cy, s, mood="laugh"):
    """Olo v2: sticker-style outline, pear body with spots, one big eye with a heavy lid and a cocked brow,
    crooked fanged grin, one straight + one bent antenna, finger pointing at the player, popcorn cup."""
    INK = (18, 34, 8)
    G, G2, G3, BELLY = (140, 200, 70), (98, 156, 40), (70, 120, 26), (196, 230, 140)
    AMB, AMB2 = (255, 170, 40), (255, 214, 120)
    W_ = max(3, int(5 * s))

    def P(x, y):
        return (int(cx + x * s), int(cy + y * s))

    def C(x, y, r, col, o=True, ow=None):
        pygame.draw.circle(surf, col, P(x, y), int(r * s))
        if o:
            pygame.draw.circle(surf, INK, P(x, y), int(r * s), ow or W_)
    # feet
    for fx in (-26, 22):
        pygame.draw.ellipse(surf, G3, (*P(fx - 16, 74), int(32 * s), int(16 * s)))
        pygame.draw.ellipse(surf, INK, (*P(fx - 16, 74), int(32 * s), int(16 * s)), W_)
    # antennae: the left one straight with a glowing ball, the right one bent with a star
    pygame.draw.lines(surf, INK, False, [P(-14, -58), P(-22, -92)], W_ + 2)
    C(-23, -97, 9, AMB)
    C(-26, -100, 3, AMB2, o=False)
    pygame.draw.lines(surf, INK, False, [P(16, -58), P(30, -84), P(48, -82)], W_ + 2)
    star = [P(48 + 10 * math.cos(a) * (1 if i % 2 == 0 else 0.45), -82 + 10 * math.sin(a) * (1 if i % 2 == 0 else 0.45))
            for i, a in enumerate([k * math.pi / 5 - math.pi / 2 for k in range(10)])]
    _poly(surf, AMB, star, INK, max(2, W_ - 1))
    # pear-shaped, slightly lopsided body
    body = [P(x, y) for x, y in [(-50, 60), (-58, 20), (-52, -18), (-36, -50), (-8, -64), (20, -62), (42, -44),
                                  (54, -10), (58, 30), (50, 62), (28, 80), (-4, 84), (-32, 80)]]
    _poly(surf, G, body, INK, W_ + 1)
    pygame.draw.ellipse(surf, BELLY, (*P(-30, 26), int(56 * s), int(48 * s)))
    for sx, sy, r in ((-40, -20, 6), (-44, 8, 4), (40, 10, 5), (30, -36, 4), (-20, -46, 3)):   # spots
        pygame.draw.circle(surf, G2, P(sx, sy), int(r * s))
    # the eye: big, amber iris, heavy lid; brow cocked up on the right
    pygame.draw.ellipse(surf, (255, 255, 255), (*P(-30, -42), int(62 * s), int(50 * s)))
    pygame.draw.ellipse(surf, INK, (*P(-30, -42), int(62 * s), int(50 * s)), W_)
    if mood == "laugh":
        pygame.draw.ellipse(surf, G, (*P(-32, -46), int(66 * s), int(54 * s)))
        pygame.draw.arc(surf, INK, (*P(-24, -30), int(50 * s), int(34 * s)), 0.15, math.pi - 0.15, W_ + 2)
        for tx, ty in ((-38, -4), (36, -6)):                                         # tears of laughter
            pygame.draw.polygon(surf, (120, 200, 255), [P(tx, ty), P(tx - 5, ty + 12), P(tx + 5, ty + 12)])
            pygame.draw.circle(surf, (120, 200, 255), P(tx, ty + 12), int(5 * s))
    else:
        C(6, -16, 15, (200, 140, 20))
        C(8, -16, 8, INK, o=False)
        C(4, -20, 3, (255, 255, 255), o=False)
        pygame.draw.polygon(surf, G, [P(-32, -46), P(34, -46), P(34, -20), P(-32, -24)])     # heavy lid
        pygame.draw.line(surf, INK, P(-30, -24), P(32, -20), W_)
    pygame.draw.line(surf, INK, P(-18, -54), P(30, -62), W_ + 2)                          # cocked brow
    # mouth: wide crooked laugh with one fang and a tongue
    if mood == "laugh":
        mouth = [P(-26, 14), P(30, 8), P(22, 36), P(2, 46), P(-16, 38)]
        _poly(surf, (60, 10, 20), mouth, INK, W_)
        pygame.draw.ellipse(surf, (240, 90, 110), (*P(-8, 30), int(24 * s), int(14 * s)))
        pygame.draw.polygon(surf, (255, 255, 255), [P(14, 9), P(24, 9), P(19, 22)])     # fang
    else:
        pygame.draw.lines(surf, INK, False, [P(-20, 20), P(2, 26), P(28, 14)], W_ + 1)
        pygame.draw.polygon(surf, (255, 255, 255), [P(14, 21), P(22, 18), P(19, 28)])
    # right arm pointing up at the failure window ("look at that!")
    arm = [P(50, 6), P(78, -18), P(96, -40), P(104, -36), P(88, -10), P(56, 26)]
    _poly(surf, G, arm, INK, W_)
    C(101, -42, 7, G, ow=max(2, W_ - 2))
    pygame.draw.line(surf, INK, P(103, -48), P(110, -60), max(3, W_ - 1))               # the pointing finger
    # left arm hugging the popcorn cup
    cup = [P(-84, 18), P(-40, 18), P(-48, 80), P(-76, 80)]
    _poly(surf, (250, 245, 240), cup, INK, W_)
    for xx in (-72, -60, -48):
        pygame.draw.line(surf, (230, 60, 70), P(xx + 2, 20), P(xx, 78), max(3, int(6 * s)))
    pygame.draw.polygon(surf, INK, cup, W_)
    for px, py in ((-80, 12), (-68, 4), (-56, 8), (-44, 12), (-62, -6)):
        C(px, py, 8, (255, 242, 210), ow=2)
    for px, py in ((-100, -30), (-112, 4), (-92, -58), (70, -80)):                     # popcorn flying
        C(px, py, 6, (255, 242, 210), ow=2)
    hand = [P(-36, 30), P(-54, 24), P(-58, 42), P(-40, 46)]
    _poly(surf, G, hand, INK, max(2, W_ - 1))


def dialog(surf, rect, name, text_lines):
    """The talk box along the bottom of the screen."""
    box = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.rect(box, (12, 24, 10, 235), box.get_rect(), border_radius=26)
    pygame.draw.rect(box, (140, 200, 70, 255), box.get_rect(), 4, border_radius=26)
    surf.blit(box, rect.topleft)
    nf, tf = get_font(26, bold=True), get_font(34, bold=True)
    tag = nf.render(name, True, (18, 34, 8))
    tr = pygame.Rect(rect.x + 300, rect.y - 22, tag.get_width() + 34, 44)
    pygame.draw.rect(surf, (140, 200, 70), tr, border_radius=22)
    surf.blit(tag, tag.get_rect(center=tr.center))
    for i, l in enumerate(text_lines):
        surf.blit(tf.render(l, True, (245, 250, 235)), (rect.x + 300, rect.y + 44 + i * 48))


scene = frame.copy()
# Olo stands in the lower-left corner; what he says runs along the bottom in a talk box
box = pygame.Rect(30, H - 330, W - 60, 190)
dialog(scene, box, "OLO", LINE)
olo2(scene, 175, H - 290, 1.5, mood="laugh")
out = pygame.transform.smoothscale(scene, (W, H))
os.makedirs(os.path.join(ROOT, "store_assets"), exist_ok=True)
p = os.path.join(ROOT, "store_assets", f"olo_mock_{LANG}.png")
pygame.image.save(out, p)
pygame.image.save(frame, os.path.join(ROOT, "store_assets", "olo_mock_base.png"))
print("saved", p)
