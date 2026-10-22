"""The daily level (1.0.9): its body inside the daily screen (ui.DailyMissionsScreen, section "daily"), and the result
card of the daily run. The numbers all come from the server (ranked_online.RankedClient); nothing here decides a reward.

The bodies are drawn once into a tall surface (rebuilt only when the server data, the tab or a toast changes) and
scrolled by blitting a slice, so the panel costs a few blits per frame on a phone."""
import time

import pygame

import gfx
from flags import draw_country_badge
from locales import t
from theme import ACCENT_CYAN, ACCENT_GOLD, ACCENT_GREEN, TEXT_MUTED, TEXT_WHITE
from ui import Button, Scroller, VH, VW, dim, draw_text, draw_vector_star, fmt_int, panel



class RankedPanel:
    """The body of the daily screen's daily-level section, drawn in `view`. `on_play_daily(level)` starts the daily
    run once the server has handed out today's one try."""

    def __init__(self, save_mgr, online, view, on_play_daily):
        self.save_mgr, self.online, self.rk = save_mgr, online, online.ranked
        self.on_play_daily = on_play_daily
        self.view = pygame.Rect(view)
        self.cw = self.view.w                        # width of the content surface
        self.scroll = Scroller()
        self.toast = ("", 0.0)
        self.hits = []                               # [(Rect in content coords, callback)] of the drawn tab body
        self._cache = None                           # (key, surface)
        self._down = None
        self.busy = False
        self.confirm = False                         # "one try only - ready?" card of the daily level
        self.btn_go = Button((VW // 2 - 330, VH // 2 + 40, 300, 92), t("rk_dl_go"), 34, bg_color=(0, 150, 200),
                             hover_color=(60, 200, 245), callback=self._go_daily)
        self.btn_no = Button((VW // 2 + 30, VH // 2 + 40, 300, 92), t("back"), 34, callback=self._no)

    # ---------------------------------------------------------------- state
    def _say(self, text, secs=3.0):
        self.toast = (text, secs)
        self._cache = None

    def refresh(self):
        self.rk.refresh("daily")

    def _data(self):
        return self.rk.daily

    def _state(self):
        return self.rk.state["daily"]

    # ---------------------------------------------------------------- actions
    def _ask_daily(self):
        self.confirm = True

    def _no(self):
        self.confirm = False

    def _go_daily(self):
        if self.busy:
            return
        self.busy = True

        def done(r):
            self.busy = False
            self.confirm = False
            if isinstance(r, dict) and r.get("ok") and r.get("first"):
                self.on_play_daily(int(r.get("level") or 0))
            elif isinstance(r, dict) and r.get("ok"):
                self._say(t("rk_dl_used"))
            else:
                self._say(t("rk_dl_noconn"))

        self.rk.daily_start(done)

    # ---------------------------------------------------------------- events
    def update(self, mouse_pos, dt=1.0):
        if self.toast[1] > 0:
            self.toast = (self.toast[0], self.toast[1] - dt / 60.0)
            if self.toast[1] <= 0:
                self._cache = None
        if self.confirm:
            self.btn_go.update(mouse_pos, dt)
            self.btn_no.update(mouse_pos, dt)
            return
        h = self._cache[1].get_height() if self._cache else self.view.h
        self.scroll.update(h, self.view.h, dt)

    def handle_event(self, event):
        """True when the event was used (the one-try card swallows everything while it is open)."""
        if self.confirm:
            if self.btn_go.handle_event(event):
                self.btn_go.callback()
            elif self.btn_no.handle_event(event):
                self.btn_no.callback()
            return True
        view = self.view
        if event.type == pygame.MOUSEWHEEL:
            self.scroll.wheel(event.y)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and view.collidepoint(event.pos):
            self.scroll.on_down(event.pos)
            self._down = event.pos
        elif event.type == pygame.MOUSEMOTION and event.buttons[0]:
            self.scroll.on_move(event.pos)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.scroll.on_up(event.pos)
            d, self._down = self._down, None
            if d and abs(event.pos[0] - d[0]) + abs(event.pos[1] - d[1]) < 24 and view.collidepoint(event.pos):
                p = (event.pos[0] - view.x, event.pos[1] - view.y + int(self.scroll.y))
                for rect, cb in self.hits:
                    if rect.collidepoint(p):
                        cb()
                        return True
        return False

    # ---------------------------------------------------------------- content surface
    def _key(self):
        d = self._data()
        return (id(d), self._state(), self.toast[1] > 0, self.cw, int(time.time() // 30),
                self.busy)

    def _body(self):
        key = self._key()
        if self._cache is None or self._cache[0] != key:
            self.hits = []
            d = self._data()
            if not d:
                surf = gfx.cv(pygame.Surface((self.cw, self.view.h)))
                surf.fill((16, 20, 32))
                msg = t("rk_offline") if self._state() == "offline" else t("rk_loading")
                draw_text(surf, msg, 30, TEXT_MUTED, (self.cw // 2, 200), bold=False)
            else:
                surf = self._daily(d)
            self._cache = (key, surf)
        return self._cache[1]

    def _new(self, h):
        s = gfx.cv(pygame.Surface((self.cw, max(h, self.view.h))))
        s.fill((16, 20, 32))
        return s

    # ---- daily level
    def _daily(self, d):
        board = d.get("board", [])
        h = 620 + len(board) * 80 + 80
        s = self._new(h)
        r = pygame.Rect(0, 8, self.cw, 470)
        panel(s, r, (24, 20, 30), (255, 150, 60), 24, 3)
        draw_text(s, t("rk_dl_title"), 34, (255, 170, 80), (self.cw // 2, r.y + 40), max_w=self.cw - 40)
        draw_text(s, t("rk_dl_level", n=d.get("level", "?")), 66, TEXT_WHITE, (self.cw // 2, r.y + 112), max_w=self.cw - 40)
        draw_text(s, t("rk_dl_sub"), 22, TEXT_MUTED, (self.cw // 2, r.y + 166), bold=False, max_w=self.cw - 40)
        draw_text(s, t("rk_dl_reward", a=d.get("reward", 10), b=d.get("reward_3", 5)), 22, ACCENT_GOLD, (self.cw // 2, r.y + 200),
                  bold=False, max_w=self.cw - 40)
        left = max(0, int(d.get("ends") or 0) - int(time.time()))
        draw_text(s, t("rk_dl_ends", h=left // 3600, m=(left % 3600) // 60), 22, TEXT_MUTED, (self.cw // 2, r.y + 232), bold=False)
        st = d.get("state")
        by = r.y + 262
        if st == "open":
            bt = pygame.Rect(40, by, self.cw - 80, 110)
            panel(s, bt, (0, 150, 200) if not self.busy else (40, 46, 62), (90, 220, 255), 22, 3)
            draw_text(s, t("rk_dl_play"), 40, TEXT_WHITE, bt.center, max_w=bt.w - 30)
            self.hits.append((bt, self._ask_daily))
        elif st == "done" and d.get("run"):
            run = d["run"]
            draw_text(s, t("rk_dl_done", s=fmt_int(run.get("score", 0))), 32, ACCENT_GREEN, (self.cw // 2, by + 30), max_w=self.cw - 40)
            for i in range(3):
                draw_vector_star(s, self.cw // 2 + (i - 1) * 56, by + 90, radius=20, filled=i < int(run.get("stars", 0)))
            if d.get("rank"):
                draw_text(s, t("rk_dl_rank", r=d["rank"], n=d.get("total", 0)), 28, ACCENT_GOLD, (self.cw // 2, by + 150), max_w=self.cw - 40)
        else:
            draw_text(s, t("rk_dl_failed"), 28, (255, 140, 120), (self.cw // 2, by + 70), max_w=self.cw - 60)
        y = 500
        draw_text(s, t("rk_dl_board"), 28, ACCENT_CYAN, (self.cw // 2, y + 20), max_w=self.cw - 30)
        y += 60
        for e in board:
            rk = int(e.get("rank", 0))
            r = pygame.Rect(0, y, self.cw, 72)
            pygame.draw.rect(s, (34, 52, 84) if e.get("me") else (24, 32, 52), r, border_radius=14)
            if e.get("me"):
                pygame.draw.rect(s, ACCENT_CYAN, r, 2, border_radius=14)
            rc = ACCENT_GOLD if rk == 1 else ((205, 220, 240) if rk == 2 else ((200, 135, 75) if rk == 3 else TEXT_MUTED))
            draw_text(s, f"{rk}", 30, rc, (42, r.centery))
            draw_country_badge(s, e.get("country", "GX"), 130, r.centery, width=78, height=36)
            draw_text(s, e.get("name", "---"), 28, TEXT_WHITE, (190, r.centery), anchor="midleft", max_w=290)
            draw_text(s, f"{e.get('time', 0):.1f}s", 20, TEXT_MUTED, (self.cw - 200, r.centery), anchor="midright", bold=False)
            draw_text(s, fmt_int(e.get("score", 0)), 28, ACCENT_GOLD, (self.cw - 20, r.centery), anchor="midright")
            y += 80
        if not board:
            draw_text(s, t("rk_dl_empty"), 26, TEXT_MUTED, (self.cw // 2, y + 40), bold=False)
        return s

    # ---------------------------------------------------------------- draw
    def draw(self, surface):
        view = self.view
        body = self._body()
        top = max(0, min(int(self.scroll.y), max(0, body.get_height() - view.h)))
        self.scroll.y = float(top)
        panel(surface, view.inflate(8, 8), (16, 20, 32), (45, 65, 100), 18, 2)
        surface.blit(body, view.topleft, pygame.Rect(0, top, self.cw, view.h))
        if self.toast[1] > 0:
            tr_ = pygame.Rect(60, VH // 2 - 50, VW - 120, 100)
            panel(surface, tr_, (20, 44, 34), ACCENT_GREEN, 20, 2)
            draw_text(surface, self.toast[0], 30, TEXT_WHITE, tr_.center, max_w=tr_.w - 40)
        if self.confirm:
            dim(surface, 200)
            c = pygame.Rect(60, VH // 2 - 200, VW - 120, 400)
            panel(surface, c, (24, 20, 30), (255, 150, 60), 24, 3)
            draw_text(surface, t("rk_dl_title"), 36, (255, 170, 80), (VW // 2, c.y + 56), max_w=c.w - 40)
            draw_text(surface, t("rk_dl_warn"), 30, TEXT_WHITE, (VW // 2, c.y + 130), max_w=c.w - 60)
            self.btn_go.text, self.btn_no.text = t("rk_dl_go"), t("back")
            self.btn_go.draw(surface)
            self.btn_no.draw(surface)


class DailyResultModal:
    """After the daily run: waits for the server's verdict (replay, rank, reward), then says it. One button."""

    def __init__(self, ok, on_close):
        self.ok = ok
        self.reply = None                    # the server's answer once it arrives
        self.failed_send = False
        self.on_close = on_close
        self.btn = Button((VW // 2 - 220, VH // 2 + 230, 440, 92), t("rk_dr_ok"), 36, bg_color=(0, 150, 200),
                          hover_color=(60, 200, 245), callback=on_close)
        self.ad_offer = None                 # (callback, ready()) set by HoloGame on a failed run: an ad gives the try back
        self.btn_ad = Button((VW // 2 - 320, VH // 2 + 110, 640, 92), t("rk_dr_retry_ad"), 30, bg_color=(150, 70, 235),
                             hover_color=(190, 120, 255), border_color=(200, 150, 255), callback=lambda: None)

    def _ad_on(self):
        return bool(not self.ok and self.ad_offer and self.ad_offer[1]())

    def set_reply(self, r):
        if isinstance(r, dict) and r.get("ok"):
            self.reply = r
        else:
            self.failed_send = True

    def update(self, mouse_pos, dt=1.0):
        self.btn.update(mouse_pos, dt)
        self.btn_ad.update(mouse_pos, dt)

    def handle_event(self, event):
        if self._ad_on() and self.btn_ad.handle_event(event):
            return self.ad_offer[0]
        if self.btn.handle_event(event):
            return self.on_close
        return None

    def draw(self, surface):
        dim(surface, 215)
        c = pygame.Rect(50, VH // 2 - 330, VW - 100, 700)
        panel(surface, c, (24, 20, 30), ACCENT_GREEN if self.ok else (220, 80, 90), 26, 3)
        draw_text(surface, t("rk_dr_win") if self.ok else t("rk_dr_fail"), 64, ACCENT_GREEN if self.ok else (255, 130, 130),
                  (VW // 2, c.y + 80), max_w=c.w - 40)
        y = c.y + 170
        if not self.ok:
            draw_text(surface, t("rk_dr_fail_sub"), 28, TEXT_WHITE, (VW // 2, y + 40), max_w=c.w - 60)
        elif self.reply:
            r = self.reply
            run = r.get("run") or {}
            draw_text(surface, t("rk_dl_done", s=fmt_int(run.get("score", r.get("score", 0)))), 34, ACCENT_GOLD, (VW // 2, y), max_w=c.w - 40)
            for i in range(3):
                draw_vector_star(surface, VW // 2 + (i - 1) * 60, y + 70, radius=22, filled=i < int(run.get("stars", r.get("stars", 0))))
            if r.get("rank"):
                draw_text(surface, t("rk_dl_rank", r=r["rank"], n=r.get("total", 0)), 30, TEXT_WHITE, (VW // 2, y + 140), max_w=c.w - 40)
            if r.get("added"):
                draw_text(surface, t("rk_got", n=r["added"]), 36, ACCENT_CYAN, (VW // 2, y + 200), max_w=c.w - 40)
        elif self.failed_send:
            draw_text(surface, t("rk_dr_unsent"), 28, (255, 140, 120), (VW // 2, y + 60), max_w=c.w - 60)
        else:
            draw_text(surface, t("rk_dr_sending"), 28, TEXT_MUTED, (VW // 2, y + 60), bold=False, max_w=c.w - 60)
        if self._ad_on():
            self.btn_ad.draw(surface)
        self.btn.draw(surface)
