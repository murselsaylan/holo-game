"""Video mock-up: doodle Olo on the real failure screen - still poses that pop from one to the next, a speech
bubble at the bottom, hand-drawn line boil. Also writes the pose sheet.

    python tools/olo_doodle_video.py [lang]  -> store_assets/olo_doodle_<lang>.mp4, store_assets/olo_doodle_sheet.png
"""
import math
import os
import sys
import tempfile

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["HOLO_SAVE_DIR"] = tempfile.mkdtemp(prefix="holo_doodle_")
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
import olo_doodle as od  # noqa: E402

LANG = sys.argv[1] if len(sys.argv) > 1 else "tr"
STICKERS = os.path.join(ROOT, "store_assets", "olo_stickers")
USE_STICKERS = os.path.isdir(STICKERS) and "--drawn" not in sys.argv
# sticker files for the drawn pose names (from tools/olo_stickers_cut.py on the AI sheet)
STICKER_OF = {"film": "s02", "laugh": "s01", "dead": "s07", "smug": "s11", "devil": "s06", "bored": "s05",
              "shock": "s03", "angry": "s14", "clap": "s08", "cry": "s09"}
SCRIPT = {   # (start s, pose, text)
    "tr": [(0.4, "film", "Dur dur dur... kaydediyorum."),
           (2.6, "laugh", "HAHAHA. Bu klip patlar."),
           (4.8, "dead", "−1000 aura. Sen değil, ben öldüm gülmekten."),
           (7.0, "clap", "Tebrikler. Bugün 14. ölüm."),
           (9.0, "smug", "Skill issue kanka."),
           (11.2, "bored", "zzz... Tekrar dene'ye bas da uyanayım.")],
    "en": [(0.4, "film", "Wait wait wait... recording."),
           (2.6, "laugh", "HAHAHA. This clip is going viral."),
           (4.8, "dead", "-1000 aura. Not you, I'm dead from laughing."),
           (7.0, "clap", "Congrats. Death number 14 today."),
           (9.0, "smug", "Skill issue, bro."),
           (11.2, "bored", "zzz... Hit try again and wake me up.")],
}[LANG]
FPS, SECONDS = 30, 13.5

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


def bubble(surf, rect, text, shown):
    """Speech bubble along the bottom: white, ink outline, a tail pointing at Olo on the left."""
    pygame.draw.polygon(surf, (255, 255, 255), [(rect.x + 30, rect.y + 60), (rect.x - 34, rect.y + 96), (rect.x + 30, rect.y + 110)])
    pygame.draw.rect(surf, (255, 255, 255), rect, border_radius=30)
    pygame.draw.rect(surf, od.INK, rect, 5, border_radius=30)
    pygame.draw.lines(surf, od.INK, False, [(rect.x + 2, rect.y + 62), (rect.x - 34, rect.y + 96), (rect.x + 2, rect.y + 110)], 5)
    f = pygame.font.SysFont("comicsansms,segoeprint,arial", 38, bold=True)
    words, lines, cur = text[:shown].split(" "), [], ""
    for w_ in words:
        nxt = (cur + " " + w_).strip()
        if f.size(nxt)[0] > rect.w - 60 and cur:
            lines.append(cur)
            cur = w_
        else:
            cur = nxt
    lines.append(cur)
    for i, l in enumerate(lines[:3]):
        surf.blit(f.render(l, True, od.INK), (rect.x + 30, rect.y + 26 + i * 52))


def pop_scale(dt):
    """A pose change: squash down, overshoot, settle (0.25 s)."""
    if dt < 0.07:
        return 0.86, 1.10
    if dt < 0.16:
        return 1.12, 0.92
    if dt < 0.25:
        return 0.97, 1.03
    return 1.0, 1.0


STICKER_IMG = {}
if USE_STICKERS:
    for name in sorted(os.listdir(STICKERS)):
        if name.endswith(".png"):
            im = pygame.image.load(os.path.join(STICKERS, name)).convert_alpha() if pygame.display.get_surface()                 else pygame.image.load(os.path.join(STICKERS, name))
            k = 290 / max(im.get_size())
            STICKER_IMG[name[:-4]] = pygame.transform.smoothscale(im, (int(im.get_width() * k), int(im.get_height() * k)))


def render():
    import imageio_ffmpeg
    out = os.path.join(ROOT, "store_assets", f"olo_doodle_{LANG}.mp4")
    ow, oh = 540, 1170
    wr = imageio_ffmpeg.write_frames(out, (ow, oh), fps=FPS, quality=8, macro_block_size=2)
    wr.send(None)
    size = 300
    sprite = pygame.Surface((size * 2, size * 2), pygame.SRCALPHA)
    for fi in range(int(FPS * SECONDS)):
        t = fi / FPS
        scene = BASE.copy()
        cur = None
        for start, pose, text in SCRIPT:
            if t >= start:
                cur = (start, pose, text)
        # Olo, drawn into a sprite so a pose change can squash and stretch it
        sprite.fill((0, 0, 0, 0))
        boil = int(t * 8) % 3                                       # hand-drawn line boil, 8 drawings a second
        pose = cur[1] if cur else "smug"
        if USE_STICKERS:
            st = STICKER_IMG[STICKER_OF.get(pose, "s00")]
            wob = math.sin(t * 2.2) * 2.0                           # alive while still: a slow sway and breath
            im = pygame.transform.rotozoom(st, wob, 1.0 + 0.015 * math.sin(t * 3.1))
            sprite.blit(im, im.get_rect(midbottom=(size, size * 2 - 10)))
        else:
            od.draw(sprite, pose, size, size + 20, size, boil=boil)
        sx, sy = pop_scale(t - cur[0]) if cur else (1, 1)
        enter = min(1.0, t / 0.35)                                  # slides in from the left at the very start
        img = pygame.transform.smoothscale(sprite, (int(size * 2 * sx), int(size * 2 * sy)))
        base_x = int(-260 + 420 * (1 - (1 - enter) ** 3))
        foot = (base_x + 30, H - 128)                                   # stands in the free strip under the window
        shadow = pygame.Surface((220, 40), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0, 0, 0, 90), shadow.get_rect())
        scene.blit(shadow, shadow.get_rect(center=(foot[0], foot[1] - 6)))
        scene.blit(img, img.get_rect(midbottom=foot))
        if cur:
            shown = int((t - cur[0]) * 28)
            bubble(scene, pygame.Rect(320, H - 372, W - 350, 190), cur[2], shown)
        frame = pygame.transform.smoothscale(scene, (ow, oh))
        wr.send(np.ascontiguousarray(pygame.surfarray.array3d(frame).swapaxes(0, 1)))
    wr.close()
    print("saved", out)


def sheet():
    s = pygame.Surface((1500, 680))
    s.fill((255, 255, 255))
    f = pygame.font.SysFont("arial", 22, True)
    for i, p in enumerate(od.POSES):
        x, y = 150 + (i % 5) * 300, 190 + (i // 5) * 320
        od.draw(s, p, x, y, 200)
        tl = f.render(p, True, (130, 130, 130))
        s.blit(tl, tl.get_rect(center=(x, y + 140)))
    pygame.image.save(s, os.path.join(ROOT, "store_assets", "olo_doodle_sheet.png"))


sheet()
render()
