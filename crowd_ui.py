"""Shared weekly goal + level of the week (1.0.9): a section of the daily screen (ui.DailyMissionsScreen).
The numbers all come from the server (crowd_online.CrowdClient); nothing here decides a reward."""
import time

import pygame

from locales import t
from theme import ACCENT_CYAN, ACCENT_GOLD, ACCENT_GREEN, TEXT_MUTED, TEXT_WHITE
from ui import Button, VH, VW, dim, draw_text, neon_bar, panel



def _pct(v):
    v = float(v or 0)
    return str(int(v)) if v >= 10 or v == int(v) else f"{v:.1f}"


class CrowdPanel:
    """The body of the ranking screen's team-goal tab, drawn in `view`: the goal's three tiers with their claim buttons,
    my share, and the level of the week."""

    def __init__(self, save_mgr, online, view, on_play_level):
        self.save_mgr, self.online, self.crowd = save_mgr, online, online.crowd
        self.on_play_level = on_play_level
        self.view = pygame.Rect(view)
        self.toast = ("", 0.0)
        v = self.view
        self.btn_tiers = [Button((v.right - 240, v.y + 190 + i * 130, 200, 84), t("cw_claim"), 30, bg_color=(25, 70, 50),
                                 hover_color=ACCENT_GREEN, callback=lambda i=i: self._claim(i + 1)) for i in range(3)]
        self.btn_play = Button((v.x + 40, v.y + 830, v.w - 80, 84), t("cw_wl_play"), 40, bg_color=(0, 150, 200),
                               hover_color=(60, 200, 245), callback=self._play)
        self.btn_wclaim = Button((v.x + 40, v.y + 830, v.w - 80, 84), "", 36, bg_color=(25, 70, 50),
                                 hover_color=ACCENT_GREEN, callback=self._claim_level)

    def refresh(self):
        self.crowd.refresh()

    def _say(self, text, secs=3.0):
        self.toast = (text, secs)

    def _after(self, r):
        if isinstance(r, dict) and r.get("ok"):
            self._say(t("cw_got", n=int(r.get("added") or 0)) if r.get("added") else t("cw_claimed"))
        else:
            self._say(t("cw_offline") if (r or {}).get("error") == "offline" else t("cw_err"))
        self.crowd.refresh()

    def _claim(self, tier):
        self.crowd.claim(tier, self._after)

    def _claim_level(self):
        self.crowd.claim_level(self._after)

    def _play(self):
        w = (self.crowd.data or {}).get("wlevel") or {}
        if w.get("level") and int(w["level"]) <= self.save_mgr.unlocked_level:
            self.on_play_level(int(w["level"]))

    def _tiers(self):
        return (self.crowd.data or {}).get("tiers", [])

    def update(self, mouse_pos, dt=1.0):
        if self.toast[1] > 0:
            self.toast = (self.toast[0], self.toast[1] - dt / 60.0)
        for b in self.btn_tiers + [self.btn_play, self.btn_wclaim]:
            b.update(mouse_pos, dt)

    def handle_event(self, event):
        """True when a button used the event."""
        tiers = self._tiers()
        for i, b in enumerate(self.btn_tiers):
            if i < len(tiers) and tiers[i].get("claimable") and b.handle_event(event):
                b.callback()
                return True
        w = (self.crowd.data or {}).get("wlevel") or {}
        if w.get("cleared") and not w.get("claimed"):
            if self.btn_wclaim.handle_event(event):
                self.btn_wclaim.callback()
                return True
        elif not w.get("cleared") and w.get("level") and int(w["level"]) <= self.save_mgr.unlocked_level:
            if self.btn_play.handle_event(event):
                self.btn_play.callback()
                return True
        return False

    def draw(self, surface):
        v = self.view
        panel(surface, v.inflate(8, 8), (16, 20, 32), (45, 65, 100), 18, 2)
        cx = v.centerx
        d = self.crowd.data
        if not d or "goal" not in d:
            msg = t("cw_loading") if self.crowd.state != "offline" else t("cw_offline")
            draw_text(surface, msg, 30, TEXT_MUTED, (cx, v.y + 300), bold=False)
            return
        goal, total = max(1, int(d["goal"])), int(d["total"])
        draw_text(surface, t("cw_sub"), 24, TEXT_MUTED, (cx, v.y + 36), bold=False, max_w=v.w - 60)
        draw_text(surface, f"{total} / {goal} {t('cw_unit')}", 54, ACCENT_GOLD, (cx, v.y + 94), max_w=v.w - 60)
        bar = pygame.Rect(v.x + 40, v.y + 138, v.w - 80, 34)
        neon_bar(surface, bar, min(1.0, total / goal), ACCENT_CYAN, done=total >= goal)
        for pct in (33, 66):
            x = bar.x + int(bar.w * pct / 100)
            pygame.draw.line(surface, (255, 255, 255), (x, bar.y + 3), (x, bar.bottom - 3), 3)
        mine = int(d.get("mine") or 0)
        need = int(d.get("min_contrib") or 3)
        draw_text(surface, t("cw_mine", n=mine) if mine >= need else t("cw_need", n=need) + f"  ({mine}/{need})", 24,
                  ACCENT_GREEN if mine >= need else TEXT_MUTED, (cx, v.y + 200), bold=False, max_w=v.w - 60)
        for i, tr in enumerate(d.get("tiers", [])):
            y = v.y + 238 + i * 130
            row = pygame.Rect(v.x + 24, y, v.w - 48, 112)
            reached = tr.get("reached")
            pygame.draw.rect(surface, (26, 40, 60) if reached else (22, 28, 42), row, border_radius=18)
            pygame.draw.rect(surface, ACCENT_GREEN if reached else (50, 64, 92), row, 2, border_radius=18)
            draw_text(surface, t("cw_tier", pct=tr["pct"], n=tr["reward"]), 34, TEXT_WHITE if reached else TEXT_MUTED,
                      (row.x + 24, row.y + 38), anchor="midleft", max_w=row.w - 300)
            draw_text(surface, f"{tr['need']} {t('cw_unit')}", 22, TEXT_MUTED, (row.x + 24, row.y + 78), anchor="midleft", bold=False)
            btn = self.btn_tiers[i]
            btn.rect.y = row.y + 14
            if tr.get("claimable"):
                btn.draw(surface)
            else:
                lab = t("cw_claimed") if tr.get("claimed") else (t("cw_wait") if not reached else t("cw_need", n=need))
                draw_text(surface, lab, 26 if len(lab) < 12 else 18, ACCENT_GREEN if tr.get("claimed") else TEXT_MUTED,
                          (row.right - 130, row.centery), max_w=210, bold=False)
        left = max(0, int(d.get("ends") or 0) - int(time.time()))
        draw_text(surface, t("cw_ends", d=left // 86400, h=(left % 86400) // 3600), 22, TEXT_MUTED, (cx, v.y + 640), bold=False)

        # the level of the week
        w = d.get("wlevel") or {}
        card = pygame.Rect(v.x + 24, v.y + 676, v.w - 48, 310)
        panel(surface, card, (24, 20, 30), (255, 150, 60), 24, 2)
        draw_text(surface, t("cw_wl_title"), 30, (255, 170, 80), (cx, card.y + 34), max_w=card.w - 40)
        draw_text(surface, t("cw_wl_level", lvl=w.get("level", "?")), 56, TEXT_WHITE, (cx, card.y + 90), max_w=card.w - 40)
        draw_text(surface, t("cw_wl_pct", pct=_pct(w.get("pct"))) if w.get("pct") else t("cw_wl_none"), 26, TEXT_MUTED,
                  (cx, card.y + 138), bold=False, max_w=card.w - 40)
        draw_text(surface, t("cw_wl_reward", n=w.get("reward", 0)), 24, ACCENT_GOLD, (cx, card.y + 172), bold=False,
                  max_w=card.w - 40)
        by = card.y + 218
        for bt in (self.btn_play, self.btn_wclaim):
            bt.rect.y, bt.rect.height = by, 70
        if w.get("cleared") and not w.get("claimed"):
            self.btn_wclaim.text = t("cw_wl_claim", n=w.get("reward", 0))
            self.btn_wclaim.draw(surface)
        elif w.get("cleared"):
            draw_text(surface, t("cw_wl_done"), 30, ACCENT_GREEN, (cx, by + 35), max_w=card.w - 40)
        elif int(w.get("level") or 999) <= self.save_mgr.unlocked_level:
            self.btn_play.draw(surface)
        else:
            draw_text(surface, t("cw_wl_locked", lvl=w.get("level", "?")), 26, TEXT_MUTED, (cx, by + 35), bold=False,
                      max_w=card.w - 40)
        if self.toast[1] > 0:
            tr_ = pygame.Rect(60, VH // 2 - 50, VW - 120, 100)
            panel(surface, tr_, (20, 44, 34), ACCENT_GREEN, 20, 2)
            draw_text(surface, self.toast[0], 30, TEXT_WHITE, tr_.center, max_w=tr_.w - 40)
