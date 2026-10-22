"""The friends window (1.0.9): my invite code, adding a friend by code, requests, gifts / pokes / challenges waiting for
me and friends who are stuck on a level ("YOLLA" sends them a shield or a revive). Everything a friend receives is
decided by the server (supabase/functions/scores/friends.ts) - this file only shows the state and sends taps."""
import pygame

import name_filter
from locales import t
from theme import ACCENT_CYAN, ACCENT_GOLD, ACCENT_GREEN, TEXT_MUTED, TEXT_WHITE
from ui import (Button, Scroller, VH, VW, dim, draw_paragraph, draw_text, friend_text, panel)

ROW_H = 118
CODE_LEN = 8


class FriendsModal:
    def __init__(self, save_mgr, online, on_close):
        self.save_mgr = save_mgr
        self.online = online
        self.on_close = on_close
        self.code_text = ""
        self.cursor_timer = 0.0
        self.toast = ("", 0.0)
        self.scroll = Scroller()
        self.box = pygame.Rect(30, 90, VW - 60, VH - 180)
        b = self.box
        self.input_rect = pygame.Rect(b.x + 30, b.y + 290, b.w - 60 - 200, 84)
        self.btn_add = Button((self.input_rect.right + 12, self.input_rect.y, 176, 84), t("fr_add_go"), 30,
                              bg_color=(25, 70, 50), hover_color=ACCENT_GREEN, callback=self._add)
        self.view = pygame.Rect(b.x + 16, b.y + 440, b.w - 32, b.h - 440 - 130)
        self.btn_close = Button((VW // 2 - 280, b.bottom - 112, 560, 92), t("back"), 34, callback=self._close)
        self._rows = []             # [(key, title, sub, [Button])]
        self._rows_key = None
        try:
            pygame.key.start_text_input()
            pygame.key.set_text_input_rect(self.input_rect)
        except Exception:
            pass
        online.friends_refresh()

    # ---------------------------------------------------------------- actions
    def _close(self):
        try:
            pygame.key.stop_text_input()
        except Exception:
            pass
        self.on_close()

    def _say(self, text, secs=3.0):
        self.toast = (text, secs)

    def _code(self):
        return "".join(ch for ch in self.code_text.upper() if ch.isalnum())[:CODE_LEN]

    def _add(self):
        code = self._code()
        if len(code) != CODE_LEN:
            self._say(t("fr_err_unknown"))
            return

        def done(r):
            if isinstance(r, dict) and r.get("ok") and "error" not in r:
                self.code_text = ""
                self._say(t("fr_added_ok" if r.get("state") == "accepted" else "fr_added_pending", name=r.get("name", "")))
            else:
                self._say(friend_text(r, "fr_added_ok"))
        self.online.friends_op("add", code, done)

    def _claim(self, m):
        def done(r):
            if isinstance(r, dict) and r.get("ok") and "error" not in r:
                if r.get("item") == "shield":
                    self._say(t("fr_claimed_shield"))
                elif r.get("item") == "challenge" or m.get("kind") == "challenge":
                    self._say(t("fr_claimed", n=int(r.get("added") or 0)))
                else:
                    self._say(t("fr_claimed", n=int(r.get("added") or 0)) if r.get("added") else t("fr_poke_ok"))
            else:
                self._say(friend_text(r, "fr_claimed"))
        self.online.friends_op("claim", str(m.get("id")), done)

    def _send_help(self, m):
        def done(r):
            if isinstance(r, dict) and r.get("ok") and "error" not in r:
                self._say(t("fr_help_sent", n=int(r.get("added") or 0)))
            else:
                self._say(friend_text(r, "fr_help_sent"))
        self.online.friends_op("help_send", str(m.get("id")), done)

    def _simple(self, op, pid, ok_key):
        self.online.friends_op(op, pid, lambda r: self._say(friend_text(r, ok_key)))

    # ---------------------------------------------------------------- rows
    def _name(self, pid, name):
        return name_filter.shown_name(self.save_mgr, pid, name) or t("lb_hidden_pilot")

    def _build_rows(self):
        f = self.online.friends or {}
        rows = []
        for m in f.get("help", []):
            rows.append((f"h{m['id']}", self._name(m.get("from"), m.get("from_name", "?")),
                         t("fr_row_help", level=m.get("level", 0)), [("fr_send", (45, 95, 190), lambda m=m: self._send_help(m))]))
        for m in f.get("inbox", []):
            kind = m.get("kind")
            if kind == "gift":
                sub = t("fr_row_gift_shield") if m.get("item") == "shield" else t("fr_row_gift_diamond", n=m.get("amount", 0))
                btn = "fr_claim"
            elif kind == "challenge":
                sub, btn = t("fr_row_challenge", level=m.get("level", 0)), "fr_claim"
            else:
                sub, btn = t("fr_row_poke"), "fr_ok"
            rows.append((f"m{m['id']}", self._name(m.get("from"), m.get("from_name", "?")), sub,
                         [(btn, (30, 120, 90), lambda m=m: self._claim(m))]))
        for x in f.get("friends", []):
            if x.get("status") == "incoming":
                rows.append((f"r{x['id']}", self._name(x["id"], x.get("name", "?")), t("fr_row_request"),
                             [("fr_accept", (30, 120, 90), lambda x=x: self._simple("accept", x["id"], "fr_added_ok")),
                              ("fr_decline", (150, 40, 60), lambda x=x: self._simple("remove", x["id"], "fr_removed"))]))
        for x in f.get("friends", []):
            if x.get("status") == "outgoing":
                rows.append((f"o{x['id']}", self._name(x["id"], x.get("name", "?")), t("fr_row_waiting"),
                             [("fr_decline", (150, 40, 60), lambda x=x: self._simple("remove", x["id"], "fr_removed"))]))
        return rows

    def _refresh_rows(self):
        f = self.online.friends
        key = (id(f), t("back"))
        if key == self._rows_key:
            return
        self._rows_key = key
        self._rows = []
        for rk, title, sub, btns in self._build_rows():
            bs = []
            for k, col, cb in btns:
                b = Button((0, 0, 150 if len(btns) == 2 else 190, 76), t(k), 26, bg_color=col, callback=cb)
                bs.append(b)
            self._rows.append((rk, title, sub, bs))

    def _layout(self):
        v = self.view
        for i, (_k, _t, _s, bs) in enumerate(self._rows):
            y = v.y + 8 + i * ROW_H - self.scroll.y
            x = v.right - 14
            for b in reversed(bs):
                b.rect.size = (b.rect.w, 76)
                x -= b.rect.w
                b.rect.topleft = (int(x), int(y + (ROW_H - 12 - 76) // 2))
                x -= 12

    # ---------------------------------------------------------------- loop
    def update(self, mouse_pos, dt=1.0):
        self.cursor_timer += 0.05 * dt
        if self.toast[1] > 0:
            self.toast = (self.toast[0], self.toast[1] - dt / 60.0)
        self._refresh_rows()
        self.btn_close.update(mouse_pos, dt)
        self.btn_add.update(mouse_pos, dt)
        self.scroll.update(len(self._rows) * ROW_H + 16, self.view.h, dt)
        self._layout()
        for _k, _t, _s, bs in self._rows:
            for b in bs:
                b.update(mouse_pos, dt)

    def handle_event(self, event):
        if self.btn_close.handle_event(event):
            self._close()
            return True
        if self.btn_add.handle_event(event):
            self._add()
            return True
        if event.type == pygame.TEXTINPUT:
            for ch in event.text.upper():
                if ch.isalnum() and len(self._code()) < CODE_LEN:
                    self.code_text += ch
            return True
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_BACKSPACE:
                self.code_text = self.code_text[:-1]
                return True
            if event.key == pygame.K_RETURN:
                self._add()
                return True
        if event.type == pygame.MOUSEWHEEL:
            self.scroll.wheel(event.y)
            return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.view.collidepoint(event.pos):
            self.scroll.on_down(event.pos)
        elif event.type == pygame.MOUSEMOTION and event.buttons[0]:
            self.scroll.on_move(event.pos)
        dragged = self.scroll.dragging
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.scroll.on_up(event.pos)
            try:
                if self.input_rect.collidepoint(event.pos):
                    pygame.key.start_text_input()
                elif not dragged:
                    pygame.key.stop_text_input()     # a tap anywhere else puts the on-screen keyboard away
            except Exception:
                pass
        for _k, _t, _s, bs in self._rows:
            for b in bs:
                if self.view.collidepoint(b.rect.center) and b.handle_event(event) and not dragged:
                    b.callback()
                    return True
        return None

    def draw(self, surface):
        dim(surface, 235)
        b = self.box
        panel(surface, b, (18, 24, 38), (45, 65, 105), 28, 2)
        draw_text(surface, t("fr_title"), 44, ACCENT_CYAN, (VW // 2, b.y + 55), max_w=b.w - 60)
        draw_text(surface, t("fr_my_code"), 24, TEXT_MUTED, (VW // 2, b.y + 118), bold=False)
        cr = pygame.Rect(b.x + 30, b.y + 140, b.w - 60, 100)
        pygame.draw.rect(surface, (25, 33, 52), cr, border_radius=18)
        pygame.draw.rect(surface, ACCENT_GOLD, cr, 3, border_radius=18)
        code = (self.online.friends or {}).get("code") or "- - -"
        draw_text(surface, code, 58, ACCENT_GOLD, cr.center, max_w=cr.w - 30)
        draw_text(surface, t("fr_code_help"), 22, TEXT_MUTED, (VW // 2, b.y + 262), bold=False, max_w=b.w - 60)

        r = self.input_rect
        pygame.draw.rect(surface, (25, 33, 52), r, border_radius=16)
        pygame.draw.rect(surface, ACCENT_CYAN, r, 3, border_radius=16)
        code_in = self._code()
        shown = code_in[:4] + ("-" + code_in[4:] if len(code_in) > 4 else "")
        cur = "|" if int(self.cursor_timer * 2.5) % 2 == 0 else " "
        if shown:
            draw_text(surface, shown + cur, 44, TEXT_WHITE, (r.x + 24, r.centery), anchor="midleft", max_w=r.w - 36)
        else:
            draw_text(surface, t("fr_enter_code"), 28, TEXT_MUTED, (r.x + 24, r.centery), anchor="midleft", bold=False, max_w=r.w - 36)
        self.btn_add.draw(surface)

        cr_ = (self.online.credits or {}) if self.online else {}
        draw_text(surface, t("fr_credits", s=cr_.get("shield", 0), r=cr_.get("revive", 0)), 24, ACCENT_GREEN,
                  (VW // 2, b.y + 408), bold=False, max_w=b.w - 60)

        v = self.view
        pygame.draw.rect(surface, (14, 18, 28), v, border_radius=18)
        surface.set_clip(v.inflate(-4, -4))
        for i, (_k, title, sub, bs) in enumerate(self._rows):
            y = int(v.y + 8 + i * ROW_H - self.scroll.y)
            if y + ROW_H < v.y or y > v.bottom:
                continue
            rr = pygame.Rect(v.x + 8, y, v.w - 16, ROW_H - 12)
            pygame.draw.rect(surface, (26, 34, 54) if i % 2 == 0 else (20, 27, 42), rr, border_radius=14)
            tw = rr.w - 24 - sum(b_.rect.w + 12 for b_ in bs)
            draw_text(surface, title, 32, TEXT_WHITE, (rr.x + 18, rr.y + 32), anchor="midleft", max_w=tw)
            draw_text(surface, sub, 22, TEXT_MUTED, (rr.x + 18, rr.y + 72), anchor="midleft", bold=False, max_w=tw)
            for b_ in bs:
                b_.draw(surface)
        surface.set_clip(None)
        if not self._rows:
            f = self.online.friends
            msg = t("loading") if f is None and self.online.friends_status != "offline" else (
                t("fr_err_offline") if f is None else t("fr_nothing"))
            draw_paragraph(surface, msg, 28, TEXT_MUTED, v.x + 30, v.y + 80, v.w - 60, center=True)
        self.btn_close.draw(surface)
        if self.toast[1] > 0:
            tr = pygame.Rect(60, VH // 2 - 50, VW - 120, 100)
            panel(surface, tr, (20, 44, 34), ACCENT_GREEN, 20, 2)
            draw_text(surface, self.toast[0], 28, TEXT_WHITE, tr.center, max_w=tr.w - 40)
