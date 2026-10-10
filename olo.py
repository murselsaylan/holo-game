"""Olo - the mascot who mocks you on the failure screen (1.0.9).

A doodle alien (stickers in assets/olo/, made from the developer's sticker sheets by tools/olo_assets.py) that pops
up in the free strip under the failure window: a couple of still poses that hop from one to the next, and a line in
the game's own talk-box style along the bottom. What he says depends on how you crashed (straight away, close to
the end, the umpteenth time on the same level, a new personal best that still failed...).

Switched on by config "olo" (off until 1.0.9) and by the player's setting "olo" (on by default).
"""
import math
import os
import random

import pygame

import config
import paths
from fonts import get_font
from locales import get_language

ASSETS = paths.asset("olo")
BEAT_S = 2.9                      # one pose + line
TYPE_CPS = 30                     # letters per second

# Each reaction is a short sequence of beats: (sticker, {lang: line}). {n} = tries on this level, {pct} = progress.
_R = {
    "quick": [   # died in the first seconds
        [("film", {"tr": "Dur dur dur, kaydediyorum...", "en": "Wait wait wait, I'm recording..."}),
         ("laugh_point", {"tr": "HAHAHA. 2 saniye. Rekor.", "en": "HAHAHA. 2 seconds. A record."})],
        [("shock", {"tr": "Daha başlamadık ki?!", "en": "We didn't even start?!"}),
         ("dead", {"tr": "Ben bile bu kadar hızlı ölemem.", "en": "Even I can't die that fast."})],
        [("coffee", {"tr": "Kahvemi koyamadan bitti.", "en": "Over before I poured my coffee."}),
         ("smug", {"tr": "Isınma turu sayalım. Yalan.", "en": "Let's call it a warm-up. Lie."})],
        [("thumbs_down", {"tr": "Speedrun mı bu? Ters yönde ama.", "en": "Is this a speedrun? The wrong way."})],
        [("selfie", {"tr": "Arkada sen ölüyorsun, ben selfie çekiyorum.", "en": "You dying in the back, me taking a selfie."}),
         ("laugh_point", {"tr": "Story'e attım bile.", "en": "Already posted it."})],
    ],
    "near": [    # crashed close to the end
        [("shock", {"tr": "%{pct}?! Bu kadar yakın?!", "en": "{pct}%?! THAT close?!"}),
         ("laugh_point", {"tr": "...Neyse, ben gülüyorum.", "en": "...Anyway, I'm laughing."})],
        [("stress", {"tr": "Dur. Nefes al. Az kalmıştı.", "en": "Stop. Breathe. You were so close."}),
         ("devil", {"tr": "Hehe. Az kalmıştı ama kalmadı.", "en": "Hehe. So close, yet no."})],
        [("think", {"tr": "Fizik dersinde bunu anlatmıyorlar mı?", "en": "Don't they teach this in physics?"}),
         ("smug", {"tr": "Son metrede ölmek bir sanat.", "en": "Dying at the last metre is an art."})],
        [("cry_tissue", {"tr": "Ağlıyorum. Senin yerine.", "en": "I'm crying. For you."}),
         ("clap", {"tr": "Bu acıyı alkışlıyorum.", "en": "I applaud this pain."})],
    ],
    "repeat": [  # the same level again (3-5 tries)
        [("thumbs_down", {"tr": "{n}. deneme. Duvar senden bıktı.", "en": "Try {n}. The wall is tired of you."}),
         ("smug", {"tr": "Skill issue kanka.", "en": "Skill issue, bro."})],
        [("film", {"tr": "Aynı yerde, aynı ölüm. Montaj hazır.", "en": "Same spot, same death. Montage ready."}),
         ("laugh_point", {"tr": "Bu klip patlar.", "en": "This clip is going viral."})],
        [("ramen", {"tr": "Ben bir şey yiyeyim, sen devam et.", "en": "I'll grab a bite, you keep going."}),
         ("shrug", {"tr": "NPC gibi aynı duvara gidiyorsun.", "en": "Walking into the same wall like an NPC."})],
        [("clap", {"tr": "Tebrikler. {n}. ölüm. Tutarlısın.", "en": "Congrats. Death {n}. Consistent."}),
         ("smug", {"tr": "-1000 aura.", "en": "-1000 aura."})],
        [("dead", {"tr": "Ben öldüm. Gülmekten.", "en": "I'm dead. From laughing."}),
         ("devil", {"tr": "Bir daha bas. Hadi. Bekliyorum.", "en": "Hit it again. Go on. I'm waiting."})],
    ],
    "many": [    # stuck (6+ tries): still teasing, then a hand
        [("sad_knees", {"tr": "{n} deneme... Ben bile üzüldüm.", "en": "{n} tries... Even I feel bad."}),
         ("idea", {"tr": "Tamam, al: reklam izle, kaldığın yerden devam.", "en": "Fine, here: watch an ad, continue where you were."})],
        [("stress", {"tr": "Bu bölüm seni yedi bitirdi.", "en": "This level ate you alive."}),
         ("idea", {"tr": "İpucu: kalkan al, rahat geç. Kimseye söylemem.", "en": "Tip: grab a shield. I won't tell anyone."})],
        [("cry_tissue", {"tr": "Mendil ister misin? Ben istiyorum.", "en": "Need a tissue? I do."}),
         ("thumbs_up", {"tr": "Hadi. Bu sefer olacak. (Olmayacak.)", "en": "Come on. This time. (It won't.)"})],
        [("sleep", {"tr": "zzz... Uyandır beni geçince.", "en": "zzz... Wake me when you pass it."}),
         ("idea", {"tr": "Sonsuz moda bir bak, kafan dağılsın.", "en": "Try endless mode, clear your head."})],
    ],
    "best": [    # a new personal best on this level, still a crash
        [("shock", {"tr": "Bu sefer daha uzağa gittin?!", "en": "You got further this time?!"}),
         ("finger_guns", {"tr": "Gelişim var. Az ama var.", "en": "Progress. Tiny, but progress."})],
        [("think", {"tr": "%{pct}. Kendi rekorun. Hâlâ öldün ama.", "en": "{pct}%. Your best. Still dead though."}),
         ("money", {"tr": "Bir dahakine bahse girerim geçersin. Az parayla.", "en": "I'd bet you pass next time. A small bet."})],
    ],
    "fail": [    # everything else
        [("laugh_point", {"tr": "HAHAHA. Bu neydi?", "en": "HAHAHA. What was that?"}),
         ("smug", {"tr": "Parmağın mı kaydı, beynin mi?", "en": "Did your finger slip, or your brain?"})],
        [("film", {"tr": "Kaydettim. Herkes görecek.", "en": "Recorded. Everyone will see."}),
         ("selfie", {"tr": "Ben ve senin rezaletin. Güzel kare.", "en": "Me and your disaster. Nice shot."})],
        [("dead", {"tr": "Öldün. Ben de öldüm. Gülmekten.", "en": "You died. Me too. From laughing."})],
        [("angry", {"tr": "O duvar orada duruyordu be!", "en": "That wall was RIGHT THERE!"}),
         ("shrug", {"tr": "Duvar yerinden oynamadı, sen oynadın.", "en": "The wall didn't move. You did."})],
        [("thumbs_down", {"tr": "Puanım: 2/10. 2'si cesaretine.", "en": "My rating: 2/10. The 2 is for courage."})],
        [("coffee", {"tr": "Sabah sabah bunu mu izleyecektim?", "en": "Is this what I'm watching this early?"}),
         ("smug", {"tr": "Bro gerçekten geçeceğini düşündü.", "en": "Bro really thought he'd make it."})],
        [("run", {"tr": "Kaçıyorum, utanç bulaşıcı.", "en": "Running away, shame is contagious."})],
        [("devil", {"tr": "Bir daha dene. Kamera açık.", "en": "Try again. The camera is rolling."})],
        [("shock", {"tr": "Oha. Yine mi?", "en": "Whoa. Again?"}),
         ("laugh_point", {"tr": "Yine. Hem de nasıl.", "en": "Again. And how."})],
        [("hooray", {"tr": "YAŞASIN! ...Pardon, senin için değil.", "en": "YAY! ...Sorry, not for you."})],
        [("think", {"tr": "Bir saniye... Sen bu oyunu biliyor musun?", "en": "Wait... do you know this game?"})],
        [("money", {"tr": "Senin yanmana bahis oynadım. Zengin oldum.", "en": "I bet on you crashing. I'm rich."})],
        [("cheer", {"tr": "Bravo! Duvara tam isabet!", "en": "Bravo! Perfect hit on the wall!"})],
        [("ramen", {"tr": "Mısır bitti, ramen açtım. Devam et.", "en": "Out of popcorn, opened ramen. Go on."})],
    ],
}


def enabled(save_mgr):
    return bool(config.get("olo", False) or os.environ.get("HOLO_OLO") == "1") and \
        bool(save_mgr.settings.get("olo", True))


class Olo:
    def __init__(self):
        self._img = {}
        self._recent = []
        self.beats = []
        self.t = 0.0
        self.active = False

    # ------------------------------------------------------------------ choosing what to say
    def react(self, attempts, pct, best_pct, alive_s):
        if alive_s < 2.5 or pct < 8:
            kind = "quick"
        elif pct >= 75:
            kind = "near"
        elif attempts >= 6:
            kind = "many"
        elif best_pct and pct > best_pct and attempts > 1:
            kind = "best"
        elif attempts >= 3:
            kind = "repeat"
        else:
            kind = "fail"
        pool = [r for r in _R[kind] if id(r) not in self._recent] or _R[kind]
        pick = random.choice(pool)
        self._recent = (self._recent + [id(pick)])[-12:]
        lang = get_language()
        self.beats = [(st, (txt.get(lang) or txt["en"]).format(n=attempts, pct=pct)) for st, txt in pick]
        self.t = 0.0
        self.active = True
        return kind

    def hide(self):
        self.active = False

    # ------------------------------------------------------------------ drawing
    def _sticker(self, name, h):
        key = (name, h)
        if key not in self._img:
            try:
                im = pygame.image.load(os.path.join(ASSETS, name + ".png"))
                im = im.convert_alpha() if pygame.display.get_surface() else im
            except Exception:
                im = pygame.Surface((10, 10), pygame.SRCALPHA)
            k = h / im.get_height()
            if im.get_width() * k > h * 1.35:                      # wide poses (lying, sleeping) get the width
                k = h * 1.35 / im.get_width()
            self._img[key] = pygame.transform.smoothscale(im, (max(1, int(im.get_width() * k)), max(1, int(im.get_height() * k))))
        return self._img[key]

    def update(self, dt):
        if self.active:
            self.t += dt

    def draw(self, surf, area):
        """area: the free strip under the failure window (virtual coordinates)."""
        if not self.active or not self.beats or area.h < 120:
            return
        t = self.t - 0.25                                          # a breath after the window lands
        if t < 0:
            return
        i = min(len(self.beats) - 1, int(t // BEAT_S))
        bt = t - i * BEAT_S
        sticker, line = self.beats[i]
        h = int(min(area.h - 20, 300))
        img = self._sticker(sticker, h)
        # hop: squash on arrival, overshoot, settle; then a slow sway so a still drawing looks alive
        if bt < 0.07:
            sx, sy = 1.12, 0.84
        elif bt < 0.16:
            sx, sy = 0.92, 1.10
        elif bt < 0.26:
            sx, sy = 1.02, 0.98
        else:
            sx, sy = 1.0, 1.0
        enter = min(1.0, t / 0.3)
        sway = math.sin(self.t * 2.3) * 1.8
        im = pygame.transform.rotozoom(img, sway, 1.0)
        im = pygame.transform.smoothscale(im, (max(1, int(im.get_width() * sx)), max(1, int(im.get_height() * sy))))
        foot_x = area.x + 20 + img.get_width() // 2 - int((1 - (1 - enter) ** 3) * 0) - int((1 - enter) * 320)
        foot = (foot_x, area.bottom - 6)
        shadow = pygame.Surface((int(img.get_width() * 0.8), 26), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0, 0, 0, 110), shadow.get_rect())
        surf.blit(shadow, shadow.get_rect(center=(foot[0], foot[1] - 4)))
        surf.blit(im, im.get_rect(midbottom=foot))
        # the talk box in the game's style: dark glass, neon edge, OLO tag, typed text
        bx = area.x + 20 + img.get_width() + 18
        box = pygame.Rect(bx, area.bottom - 176, area.right - bx - 10, 160)
        if box.w < 220:
            return
        pane = pygame.Surface(box.size, pygame.SRCALPHA)
        pygame.draw.rect(pane, (12, 18, 32, 236), pane.get_rect(), border_radius=22)
        pygame.draw.rect(pane, (0, 214, 255, 255), pane.get_rect(), 3, border_radius=22)
        surf.blit(pane, box.topleft)
        tail = [(box.x + 2, box.y + 58), (box.x - 20, box.y + 78), (box.x + 2, box.y + 96)]
        pygame.draw.polygon(surf, (12, 18, 32), tail)
        pygame.draw.lines(surf, (0, 214, 255), False, tail, 3)
        tf = get_font(24, bold=True)
        tag = tf.render("OLO", True, (8, 14, 24))
        tr = pygame.Rect(box.x + 22, box.y - 18, tag.get_width() + 28, 34)
        pygame.draw.rect(surf, (0, 214, 255), tr, border_radius=17)
        surf.blit(tag, tag.get_rect(center=tr.center))
        shown = line[:max(0, int((bt - 0.12) * TYPE_CPS))]
        f = get_font(32, bold=True)
        words, lines, cur = shown.split(" "), [], ""
        for w in words:
            nxt = (cur + " " + w).strip()
            if f.size(nxt)[0] > box.w - 40 and cur:
                lines.append(cur)
                cur = w
            else:
                cur = nxt
        lines.append(cur)
        for k, l in enumerate(lines[:3]):
            surf.blit(f.render(l, True, (235, 245, 255)), (box.x + 22, box.y + 28 + k * 40))
