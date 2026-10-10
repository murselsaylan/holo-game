"""A short video of Olo (v3 design idea) on the real failure screen - for deciding how he should look and move.

    python tools/olo_video.py [lang]   -> store_assets/olo_video_<lang>.mp4
"""
import math
import os
import sys
import tempfile

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["HOLO_SAVE_DIR"] = tempfile.mkdtemp(prefix="holo_olovid_")
os.environ["HOLO_SERVER"] = "http://127.0.0.1:1"
PANEL = (1080, 2340)

import numpy as np  # noqa: E402
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
SCRIPT = {
    "tr": [(1.5, "Oha. Yine mi o duvar?", "write"),
           (4.2, "Deftere yazdım: bugün 14. ölüm.", "write"),
           (7.0, "Olo bu bölümü gözü kapalı geçerdi.", "lie"),
           (10.0, "...Ne bakıyorsun? Bas tekrar dene'ye.", "smirk")],
    "en": [(1.5, "Oh wow. That wall again?", "write"),
           (4.2, "Noted: death number 14 today.", "write"),
           (7.0, "Olo beat this level blindfolded.", "lie"),
           (10.0, "...What? Hit try again already.", "smirk")],
}[LANG]
FPS, SECONDS = 30, 12.5

# ------------------------------------------------------------------------------------------- the failure screen
g = holo.HoloGame(headless=True)
sm = g.save_mgr
sm.data.update(is_profile_set=True, player_name="NOVA", player_country="TR", howto_seen=True)
sm.language = LANG
locales.set_language(LANG)
g.on_language_change()
for lvl in range(1, 5):
    sm.stats[str(lvl)] = {"stars": 3, "best_score": 5000, "best_time": 12.0, "best_swaps": 6, "rank": "S"}
sm.data["campaign_level"] = 5
g.load_and_play_level(5)
for _ in range(50):
    g.update(1 / 60.0, (450, 900))
g.sim.dead = True
g.state, g.death_timer = "dying", 0.01
for _ in range(90):
    g.update(1 / 60.0, (450, 900))
g.toasts = []
g.draw()
BASE = g.frame.copy()
W, H = BASE.get_size()

INK, G, G2, BELLY = (23, 52, 4), (151, 196, 89), (99, 153, 34), (192, 221, 151)
AMB, RED, GREY = (239, 159, 39), (226, 75, 74), (95, 94, 90)


def quad(p0, c, p1, n=14):
    return [((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * c[0] + t * t * p1[0],
             (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * c[1] + t * t * p1[1]) for t in (i / n for i in range(n + 1))]


def qpath(start, segs):
    pts, cur = [start], start
    for c, end in segs:
        pts += quad(cur, c, end)[1:]
        cur = end
    return pts


def olo(surf, cx, cy, s, t, mood, tallies, writing, blink):
    """Olo drawn from the character sheet's coordinates (SVG units, origin 196,200), scaled by s."""
    bob = math.sin(t * 3.0) * 4
    def P(x, y):
        return (cx + (x - 196) * s, cy + (y - 200) * s + bob)
    def poly(pts, col, w=0):
        pygame.draw.polygon(surf, col, [P(*p) for p in pts], w)
    def line(a, b, col, w):
        pygame.draw.line(surf, col, P(*a), P(*b), max(1, int(w * s)))
    def circ(c, r, col, w=0):
        pygame.draw.circle(surf, col, P(*c), max(1, int(r * s)), max(0, int(w * s)) if w else 0)
    # scarf, waving
    wv = math.sin(t * 6.0) * 10
    scarf = qpath((232, 196), [((300, 176 + wv), (338, 206 + wv)), ((314, 214 + wv), (330, 230 + wv * 1.3)),
                               ((292, 226), (268, 236))])
    poly(scarf, RED)
    poly(scarf, (163, 45, 45), 3)
    # antennae: the left one works (amber, or blinking red while he lies), the right one bent and burnt
    line((176, 70), (162, 36), INK, 5)
    ball = RED if mood == "lie" and int(t * 6) % 2 == 0 else (AMB if mood != "lie" else (255, 120, 110))
    circ((160, 31), 11 if mood == "lie" else 9, ball)
    circ((160, 31), 11 if mood == "lie" else 9, INK, 3)
    if mood == "lie":
        for a in range(0, 360, 45):
            r1, r2 = 15, 30 + 6 * math.sin(t * 12)
            line((160 + r1 * math.cos(math.radians(a)), 31 + r1 * math.sin(math.radians(a))),
                 (160 + r2 * math.cos(math.radians(a)), 31 + r2 * math.sin(math.radians(a))), RED, 5)
        ef = get_font(max(14, int(46 * s)), bold=True)                  # a jumping "!" above the lying antenna
        ex = ef.render("!", True, RED)
        surf.blit(ex, ex.get_rect(center=P(118, 22 - abs(math.sin(t * 7)) * 10)))
    pygame.draw.lines(surf, INK, False, [P(214, 72), P(226, 44), P(252, 38)], max(2, int(5 * s)))
    circ((256, 37), 7, GREY)
    circ((256, 37), 7, INK, 3)
    line((252, 31), (260, 43), (44, 44, 42), 1.5)
    line((260, 31), (252, 43), (44, 44, 42), 1.5)
    # body
    body = qpath((120, 270), [((108, 150), (150, 98)), ((190, 64), (236, 92)), ((282, 140), (272, 270)),
                              ((262, 304), (196, 308)), ((130, 304), (120, 270))])
    poly(body, G)
    poly(body, INK, 5)
    for c, r in (((140, 160), 7), ((132, 196), 5), ((262, 214), 6)):
        circ(c, r, G2)
    pygame.draw.ellipse(surf, BELLY, pygame.Rect(*P(156, 220), 88 * s, 68 * s))
    f = get_font(max(12, int(26 * s)), bold=True)
    num = f.render("1", True, (59, 109, 17))
    surf.blit(num, num.get_rect(center=P(200, 256)))
    band = [(236, 252), (262, 240), (267, 251), (241, 263)]
    poly(band, (250, 238, 218))
    poly(band, (133, 79, 11), 2)
    # aviator cap with the H1 badge
    poly(qpath((126, 104), [((196, 56), (268, 106))]) + [(272, 122)] + list(reversed(qpath((122, 120), [((196, 92), (272, 122))]))),
         (133, 79, 11))
    poly(qpath((122, 120), [((196, 92), (272, 122))]) + [(266, 134)] + list(reversed(qpath((128, 132), [((196, 110), (266, 134))]))),
         (99, 56, 6))
    pygame.draw.rect(surf, (250, 199, 117), pygame.Rect(*P(186, 94), 20 * s, 14 * s), border_radius=3)
    hf = get_font(max(10, int(11 * s)), bold=True)
    hb = hf.render("H1", True, (65, 36, 2))
    surf.blit(hb, hb.get_rect(center=P(196, 101)))
    # the eye; the pupil darts left-right while he lies
    circ((200, 168), 42, (255, 255, 255))
    dx = (math.sin(t * 9) * 8) if mood == "lie" else 0
    circ((208 + dx, 174), 17, (186, 117, 23))
    circ((210 + dx, 175), 9, INK)
    circ((214 + dx, 170), 3.5, (255, 255, 255))
    lid_low = 162 + (52 if blink else 0)
    poly([(158, 126), (244, 126), (242, lid_low), (200, lid_low + 10), (158, lid_low - 2)], G)
    line((158, lid_low - 2), (242, lid_low), INK, 3)
    circ((200, 168), 42, INK, 5)
    brow_up = -8 if mood == "lie" else 0
    pygame.draw.lines(surf, INK, False, [P(*p) for p in qpath((156, 136 + brow_up), [((196, 120 + brow_up), (246, 132))])],
                      max(2, int(6 * s)))
    # cracked goggle ring and straps
    circ((200, 168), 50, GREY, 7)
    pygame.draw.lines(surf, (180, 178, 169), False, [P(226, 128), P(232, 146), P(222, 152), P(230, 168)], max(1, int(2 * s)))
    line((150, 168), (124, 160), GREY, 5)
    line((250, 168), (272, 158), GREY, 5)
    # mouth: smirk with a fang (opens while talking)
    talk = writing == "talk"
    open_ = (abs(math.sin(t * 18)) * 10) if talk else 0
    pygame.draw.lines(surf, INK, False, [P(*p) for p in qpath((170, 232), [((190, 246 + open_), (214, 236))])],
                      max(2, int(5 * s)))
    line((214, 236), (232, 222), INK, 5)
    poly([(214, 236), (222, 234), (218, 246)], (255, 255, 255))
    if mood == "lie":                                                   # a nervous sweat drop
        poly([(268, 150), (262, 166), (274, 166)], (120, 200, 255))
        circ((268, 168), 6, (120, 200, 255))
    # left arm holding the Shame Notebook; tallies appear as he writes
    arm = [(124, 226), (100, 230), (78, 248), (72, 266), (86, 272), (96, 256), (112, 248), (128, 246)]
    poly(arm, G)
    poly(arm, INK, 4)
    shake = math.sin(t * 30) * 2 if writing == "write" else 0
    nb = [(34 + shake, 252), (88 + shake, 242), (98 + shake, 310), (44 + shake, 320)]
    poly(nb, (241, 239, 232))
    poly(nb, (44, 44, 42), 3)
    for i in range(tallies):
        x0 = 46 + shake + (i % 5) * 8 + (i // 5) * 2
        y0 = 268 + (i // 5) * 22
        if i % 5 == 4:
            line((x0 - 34, y0 + 14), (x0 + 2, y0 + 4), (163, 45, 45), 2.5)
        else:
            line((x0, y0), (x0 + 2, y0 + 18), (163, 45, 45), 2.5)
    if writing == "write":                                             # the pencil scribbling
        px, py = 70 + math.sin(t * 25) * 12, 280 + math.cos(t * 19) * 6
        line((px, py), (px + 26, py - 30), (239, 159, 39), 5)
        line((px, py), (px + 4, py - 5), (44, 44, 42), 4)
    # right arm (waves on "smirk")
    ang = math.sin(t * 8) * 0.4 if mood == "smirk" else 0
    ex, ey = 296 + 30 * math.sin(ang), 276 - 20 * math.cos(ang) + 20
    pygame.draw.lines(surf, INK, False, [P(274, 230), P(300, 250), P(ex, ey)], max(3, int(10 * s)))
    pygame.draw.lines(surf, G, False, [P(274, 230), P(300, 250), P(ex, ey)], max(2, int(5 * s)))
    # sneakers
    for x in (166, 232):
        pygame.draw.ellipse(surf, (230, 241, 251), pygame.Rect(*P(x - 26, 303), 52 * s, 22 * s))
        pygame.draw.ellipse(surf, INK, pygame.Rect(*P(x - 26, 303), 52 * s, 22 * s), max(1, int(4 * s)))
        line((x - 20, 314), (x + 20, 314), RED, 3)


def talk_box(surf, rect, text, shown, t):
    box = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.rect(box, (12, 24, 10, 238), box.get_rect(), border_radius=26)
    pygame.draw.rect(box, (151, 196, 89, 255), box.get_rect(), 4, border_radius=26)
    surf.blit(box, rect.topleft)
    nf = get_font(26, bold=True)
    tag = nf.render("OLO  •  H-1", True, INK)
    tr = pygame.Rect(rect.x + 330, rect.y - 22, tag.get_width() + 34, 44)
    pygame.draw.rect(surf, G, tr, border_radius=22)
    surf.blit(tag, tag.get_rect(center=tr.center))
    tf = get_font(34, bold=True)
    words, lines, cur = text[:shown].split(" "), [], ""
    for w_ in words:                                                   # wrap to the box
        nxt = (cur + " " + w_).strip()
        if tf.size(nxt)[0] > rect.w - 370 and cur:
            lines.append(cur)
            cur = w_
        else:
            cur = nxt
    lines.append(cur)
    for i, l in enumerate(lines[:3]):
        surf.blit(tf.render(l, True, (245, 250, 235)), (rect.x + 330, rect.y + 40 + i * 46))
    if shown >= len(text) and int(t * 3) % 2 == 0:
        pygame.draw.polygon(surf, G, [(rect.right - 46, rect.bottom - 40), (rect.right - 26, rect.bottom - 40),
                                      (rect.right - 36, rect.bottom - 28)])


def ease_out_back(x):
    c1, c3 = 1.70158, 2.70158
    x = min(1.0, max(0.0, x))
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2


def render():
    import imageio_ffmpeg
    out = os.path.join(ROOT, "store_assets", f"olo_video_{LANG}.mp4")
    ow, oh = 540, 1170
    wr = imageio_ffmpeg.write_frames(out, (ow, oh), fps=FPS, quality=8, macro_block_size=2)
    wr.send(None)
    box_full = pygame.Rect(30, H - 330, W - 60, 190)
    tallies = 12
    for fi in range(int(FPS * SECONDS)):
        t = fi / FPS
        scene = BASE.copy()
        # which line is on
        cur = None
        for start, text, mood in SCRIPT:
            if t >= start:
                cur = (start, text, mood)
        mood = cur[2] if cur else "smirk"
        shown = int((t - cur[0]) * 24) if cur else 0
        talking = cur is not None and shown < len(cur[1])
        if cur and cur[2] == "write" and t - cur[0] > 1.3 and "14" in cur[1] and tallies < 14:
            tallies = 13 if t - cur[0] < 1.7 else 14
        # talk box slides up after Olo lands
        k = ease_out_back((t - 1.0) / 0.45)
        if t > 1.0:
            box = box_full.move(0, int((1 - k) * 260))
            talk_box(scene, box, cur[1] if cur else "", shown, t)
        # Olo jumps in from below the screen
        j = ease_out_back((t - 0.3) / 0.6)
        cy = (H - 300) + (1 - j) * 520
        blink = (t % 2.6) < 0.12 and mood != "lie"
        writing = "write" if (cur and cur[2] == "write" and t - cur[0] < 2.0) else ("talk" if talking else "")
        olo(scene, 200, cy + 30, 1.18, t, mood, tallies, writing, blink)
        frame = pygame.transform.smoothscale(scene, (ow, oh))
        wr.send(np.ascontiguousarray(pygame.surfarray.array3d(frame).swapaxes(0, 1)))
    wr.close()
    print("saved", out)


render()
