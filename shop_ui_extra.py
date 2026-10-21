"""The shop's extra sections (1.0.9), drawn into ShopScreen's scrolling list below the diamond packs: weekly showcase,
supplies (shield / revive packs), prestige frames and titles, the weekly Star Market and the Star Chest.

Everything that costs something goes to the server (shop_online.ShopClient -> shopx.ts): prices, limits and the weekly
rotation are decided there. The rotation is also computed here from shop_items.py (same code, checked by
tools/shopx_golden.py) so the page shows the items before the answer arrives; the buttons wait for the server.

draw_frame() / title_text() are also used by the ranking rows and the profile.
"""
import time

import pygame

import shop_items as SI
from shop_art import product_art
from prestige_art import frame_art, title_emblem, TITLE_COLORS
from locales import t, get_language

_GOLD = (255, 215, 120)
_CYAN = (0, 230, 255)


# ------------------------------------------------------------------------------------------------ shared helpers
def draw_frame(surface, rect, frame_id, w=4):
    """Shared frame art for shop previews and actual player badges."""
    frame_art(surface, rect, frame_id, w)


def title_text(title_id):
    return t("ti_" + title_id) if title_id in SI.TITLE else ""


def draw_title_badge(surface, rect, title_id, font_size=20):
    import ui
    if title_id not in TITLE_COLORS:
        return
    r = pygame.Rect(rect)
    col = TITLE_COLORS[title_id]
    ui.panel(surface, r, tuple(max(12, v // 12) for v in col), tuple(v // 2 for v in col), min(12, r.h // 3), 1)
    title_emblem(surface, title_id, (r.x + r.h // 2 + 3, r.centery), max(16, r.h - 10))
    ui.draw_text(surface, title_text(title_id), font_size, col,
                 (r.x + r.h + 6, r.centery), anchor="midleft", max_w=r.w - r.h - 16)


def frame_name(frame_id):
    return t("fr_" + frame_id)


def _fmt_left(secs):
    secs = max(0, int(secs))
    d, h, m = secs // 86400, secs % 86400 // 3600, secs % 3600 // 60
    return t("sx_ends", d=d, h=h) if d else t("sx_ends_h", h=h, m=m)


class ShopExtra:
    BLOCK_W = 848
    GAP = 14

    def __init__(self, save_mgr, shop, audio=None, on_change=None):
        self.save_mgr = save_mgr
        self.shop = shop
        self.audio = audio
        self.on_change = on_change or (lambda: None)       # the screen rebuilds its cached list
        self.client = None
        self.sel_week = None                               # a tapped showcase / market card (second tap buys)
        self.item = None                                   # (type, id) of the product shown in the shop top panel
        self.anim = None                                   # the chest opening in progress
        self.busy = False
        self.flash = None                                  # (text, until) of the last chest reward
        self._lay = None

    # ---- server
    def _client(self):
        if self.client is None:
            w = getattr(self.save_mgr, "wallet", None)
            if w is None:
                return None
            from shop_online import ShopClient
            self.client = ShopClient(w)
        return self.client

    def open(self):
        c = self._client()
        if c is not None:
            c.refresh(max_age=15.0)

    def update(self):
        c = self.client
        if c is not None:
            c.poll()

    @property
    def view(self):
        return self.client.view if self.client is not None else None

    def sig(self):
        v = self.view
        stt = self.client.state["view"] if self.client is not None else ""
        sm = self.save_mgr
        return (id(v), stt, self.sel_week, self.item, self.busy, sm.shield_stock, sm.revive_stock, sm.star_coins,
                sm.prestige_frame, sm.prestige_title, len(sm.prestige_owned), int(time.time() // 60),
                bool(self.flash and self.flash[1] > time.time()))

    # ---- layout (relative to the block origin)
    def _layout(self):
        owned = set(self.save_mgr.prestige_owned)
        wf = SI.weekly_frame(time.time())
        frames = [f[0] for f in SI.FRAMES if f[2] == "perm" or (f[0] in owned and f[0] != wf)]
        titles = [x[0] for x in SI.TITLES if x[2] == "perm" or x[0] in owned]
        key = (tuple(frames), tuple(titles))
        if self._lay and self._lay["key"] == key:
            return self._lay
        W, G = self.BLOCK_W, self.GAP
        x0 = (900 - W) // 2
        L = {"key": key, "x0": x0, "frames": frames, "titles": titles}
        y = 0
        L["week_head"] = y; y += 100
        cw = (W - 3 * G) // 4
        L["week"] = [pygame.Rect(x0 + i * (cw + G), y, cw, 214) for i in range(4)]; y += 214 + 40
        L["pack_head"] = y; y += 76
        pw = (W - G) // 2
        L["packs"] = {}
        for i, pid in enumerate(SI.PACKS):
            L["packs"][pid] = pygame.Rect(x0 + (i % 2) * (pw + G), y + (i // 2) * (184 + G), pw, 184)
        y += 2 * 184 + G + 40
        L["pre_head"] = y; y += 100
        L["frames_label"] = y; y += 36
        fw = (W - 2 * 14) // 3
        L["frame_cells"] = {}
        for i, fid in enumerate(frames):
            L["frame_cells"][fid] = pygame.Rect(x0 + (i % 3) * (fw + 14), y + (i // 3) * (178 + 14), fw, 178)
        y += ((len(frames) + 2) // 3) * (178 + 14) + 14
        L["titles_label"] = y; y += 36
        tw = (W - 14) // 2
        L["title_cells"] = {}
        for i, tid in enumerate(titles):
            L["title_cells"][tid] = pygame.Rect(x0 + (i % 2) * (tw + 14), y + (i // 2) * (126 + 14), tw, 126)
        y += ((len(titles) + 1) // 2) * (126 + 14) + 10
        y += 30
        L["mk_head"] = y; y += 100
        mw = (W - 2 * G) // 3
        L["market"] = [pygame.Rect(x0 + i * (mw + G), y, mw, 224) for i in range(3)]; y += 224 + 40
        L["chest_head"] = y; y += 100
        L["chest"] = pygame.Rect(x0, y, W, 280); y += 280 + 90
        L["height"] = y
        self._lay = L
        return L

    def height(self):
        return self._layout()["height"]

    # ---- data (server view first, the local rotation until it arrives)
    def _week_items(self):
        v = self.view
        now = time.time()
        if v:
            return [(s["skin"], s["price"], s["full"], s.get("owned", False)) for s in v["showcase"]], v["frame"]
        sk = [(sid, p, f, self.save_mgr.is_skin_unlocked(sid)) for sid, p, f in SI.weekly_skins(now)]
        fr = SI.weekly_frame(now)
        return sk, {"id": fr, "price": SI.LIMITED_FRAME_PRICE, "owned": fr in self.save_mgr.prestige_owned}

    def _market_items(self):
        v = self.view
        if v:
            return v["market"]
        return [{"id": m[0], "kind": m[1], "payload": m[2], "stars": m[3], "limit": m[4], "left": m[4], "owned": False}
                for m in SI.market(time.time())]

    def _pack_left(self, item):
        v = self.view
        if v:
            return int(v["packs"]["left"].get(item, 0))
        return SI.PACK_UNITS_PER_DAY[item]

    def _chest_left(self):
        v = self.view
        return int(v["chest"]["left"]) if v else SI.CHEST_PER_DAY

    # ---- drawing
    def draw(self, img, y0):
        import ui
        L = self._layout()
        sm = self.save_mgr
        now = time.time()
        end_txt = _fmt_left(SI.week_end(now) - now)
        W, x0 = self.BLOCK_W, L["x0"]

        def head(y, title, col, sub, right=None):
            ui.section_title(img, y0 + y + 30, title, col, right, x0=34)
            if sub:
                ui.draw_text(img, sub, 21, (150, 175, 210), (x0, y0 + y + 74), anchor="midleft", bold=False, max_w=W)

        # -- weekly showcase
        st = self.client.state["view"] if self.client is not None else "offline"
        note = t("sx_unavail") if st == "unavailable" else (t("sx_offline") if st == "offline" and self.view is None else "")
        head(L["week_head"], t("sx_week_title"), (255, 120, 150), t("sx_week_sub", p=int(SI.WEEKLY_OFF * 100)), end_txt)
        if note:                                           # the buttons below cannot work: say why, in plain sight
            ui.draw_text(img, note, 22, (255, 190, 120), (x0 + W, y0 + L["week_head"] + 74), anchor="midright", max_w=W // 2)
        skins, fr = self._week_items()
        for i, (sid, price, full, got) in enumerate(skins):
            r = L["week"][i].move(0, y0)
            sel = self.sel_week == ("skin", sid)
            self._card(img, r, sel)
            from skins import SKINS
            thumb = ui.skin_thumbnail(sid, width=r.w - 28, height=78, radius=14)
            img.blit(thumb, thumb.get_rect(center=(r.centerx, r.y + 62)))
            self._tag(img, r, t("sx_week_tag"), (225, 60, 80))
            ui.draw_text(img, SKINS[sid]["name"], 21, ui.TEXT_WHITE, (r.centerx, r.y + 128), max_w=r.w - 14)
            if got:
                self._pill(img, r, r.y + 176, t("owned"), None, (30, 90, 70), (80, 220, 150))
            else:
                self._pill(img, r, r.y + 176, str(price), "gem", (24, 60, 96), (0, 220, 255), old=full)
        r = L["week"][3].move(0, y0)
        sel = self.item == ("wframe", fr["id"])
        self._card(img, r, sel)
        self._tag(img, r, t("sx_week_tag"), (225, 60, 80))
        self._preview(img, pygame.Rect(0, 0, 118, 62).move(r.centerx - 59, r.y + 38), fr["id"])
        ui.draw_text(img, frame_name(fr["id"]), 21, ui.TEXT_WHITE, (r.centerx, r.y + 128), max_w=r.w - 14)
        if fr["owned"]:
            self._pill(img, r, r.y + 176, t("owned"), None, (30, 90, 70), (80, 220, 150))
        else:
            self._pill(img, r, r.y + 176, str(fr["price"]), "gem", (24, 60, 96), (0, 220, 255))

        # -- supplies
        head(L["pack_head"], t("sx_pack_title"), (0, 200, 240), None)
        for pid, (item, n, price) in SI.PACKS.items():
            r = L["packs"][pid].move(0, y0)
            left = self._pack_left(item)
            ok = left >= n and (sm.shield_stock if item == "shield" else sm.revive_stock) + n <= \
                (sm.SHIELD_STOCK_CAP if item == "shield" else sm.REVIVE_STOCK_CAP)
            unit = 10 if item == "shield" else 20
            save = int(round(100 - 100.0 * price / (unit * n)))
            accent = (25, 224, 255) if item == "shield" else (199, 125, 255)
            if self.item == ("pack", pid):
                img.blit(ui.neon_halo(r.w, r.h, (0, 230, 255), 22), (r.x - 12, r.y - 12))
            img.blit(ui.cockpit_surface(r.w, r.h, (20, 33, 54), (10, 15, 28), accent if ok else (60, 66, 82), 20), r.topleft)
            product_art(img, item, (r.x + 54, r.y + 58), 84)
            ui.draw_text(img, t("sx_pack_shield" if item == "shield" else "sx_pack_revive", n=n), 26, ui.TEXT_WHITE,
                         (r.x + 108, r.y + 38), anchor="midleft", max_w=r.w - 124)
            ui.draw_text(img, t("sx_pack_save", p=save), 19, (140, 255, 190), (r.x + 108, r.y + 74), anchor="midleft", bold=False)
            stock = sm.shield_stock if item == "shield" else sm.revive_stock
            ui.draw_text(img, f"{t('sx_stock', n=stock)}  •  {t('sx_pack_left', n=left)}", 17, (150, 175, 210),
                         (r.x + 18, r.bottom - 23), anchor="midleft", bold=False, max_w=r.w - 36)
            b = pygame.Rect(0, 0, 150, 58)
            b = pygame.Rect(r.x + 18, r.y + 102, r.w - 36, 40)
            ui.panel(img, b, (17, 45, 65) if ok else (35, 39, 50), accent if ok else (80, 86, 102), 14, 2)
            ui.draw_diamond_icon(img, b.x + 28, b.centery, 11, (255, 255, 255))
            ui.draw_text(img, str(price), 25, (255, 255, 255), (b.x + 54, b.centery), anchor="midleft")

        # -- prestige
        head(L["pre_head"], t("sx_prestige_title"), _GOLD, t("sx_prestige_sub"))
        ui.draw_text(img, t("sx_frames"), 22, _CYAN, (L["x0"], y0 + L["frames_label"] + 14), anchor="midleft")
        for fid, c in L["frame_cells"].items():
            r = c.move(0, y0)
            self._prestige_cell(img, r, fid, True)
        ui.draw_text(img, t("sx_titles"), 22, _CYAN, (L["x0"], y0 + L["titles_label"] + 14), anchor="midleft")
        for tid, c in L["title_cells"].items():
            self._prestige_cell(img, c.move(0, y0), tid, False)

        # -- Star Market
        head(L["mk_head"], t("sx_market_title"), (255, 200, 60), t("sx_market_sub"), end_txt)
        for i, m in enumerate(self._market_items()):
            r = L["market"][i].move(0, y0)
            sel = self.item == ("mkt", m["id"])
            self._card(img, r, sel)
            self._market_art(img, r, m)
            ui.draw_text(img, self._market_name(m), 22, ui.TEXT_WHITE, (r.centerx, r.y + 128), max_w=r.w - 16)
            sold = m.get("left", 1) <= 0
            if sold:
                self._pill(img, r, r.y + 178, t("sx_sold") if not m.get("owned") else t("owned"), None, (50, 54, 66), (90, 96, 112))
            else:
                self._pill(img, r, r.y + 178, str(m["stars"]), "star", (70, 56, 20), (255, 200, 60))
                ui.draw_text(img, t("sx_left_week", n=m.get("left", m["limit"])), 16, (170, 180, 200), (r.centerx, r.y + 206), bold=False)

        # -- Star Chest
        head(L["chest_head"], t("sx_chest_title"), (255, 200, 60), t("sx_chest_sub"))
        r = L["chest"].move(0, y0)
        left = self._chest_left()
        can = left > 0 and sm.star_coins >= SI.CHEST_COST
        img.blit(ui.cockpit_surface(r.w, r.h, (37, 32, 42), (11, 16, 29), (255, 200, 60), 24), r.topleft)
        product_art(img, "chest", (r.x + 110, r.y + 118), 178)
        ui.draw_text(img, t("sx_chest_left", n=left) if left else t("sx_chest_none"), 22, (200, 205, 220),
                     (r.x + 210, r.y + 46), anchor="midleft", bold=False)
        stars_have = f"{sm.star_coins}"
        ui.draw_vector_star(img, r.x + 218, r.y + 92, radius=13, filled=True)
        ui.draw_text(img, stars_have, 30, (255, 215, 120), (r.x + 240, r.y + 92), anchor="midleft")
        ui.draw_text(img, t("sx_star_cap", n=SI.STAR_CAP), 16, (140, 150, 175), (r.x + 210, r.y + 136), anchor="midleft", bold=False, max_w=270)
        b = self._chest_button(r)
        ui.panel(img, b, (230, 150, 20) if can else (60, 66, 82), (255, 220, 120) if can else (80, 86, 102), 24, 3)
        ui.draw_text(img, t("sx_chest_btn", cost=f"{SI.CHEST_COST}"), 25, (30, 18, 0) if can else (150, 156, 172), (b.centerx - 14, b.centery), max_w=240)
        ui.draw_vector_star(img, b.right - 38, b.centery, radius=13, filled=True, color=(60, 30, 0) if can else (130, 136, 150))
        pygame.draw.line(img, (68, 59, 44), (r.x + 24, r.y + 182), (r.right - 24, r.y + 182))
        ui.draw_text(img, t("shop_chest_rewards"), 18, (172, 184, 206), (r.x + 26, r.y + 232), anchor="midleft", max_w=190)
        for j, kind in enumerate(("shield", "revive", "gems", "frame")):
            cx = r.x + 280 + j * 145
            if kind == "frame":
                draw_frame(img, pygame.Rect(cx - 21, r.y + 214, 42, 36), "frame_nebula", 2)
            else:
                product_art(img, kind, (cx, r.y + 232), 60)
        if self.flash and self.flash[1] > time.time():
            fl = pygame.Rect(0, 0, 520, 56)
            fl.midtop = (r.centerx, r.bottom + 6)
            ui.panel(img, fl, (30, 70, 50), (120, 255, 190), 20, 2)
            ui.draw_text(img, self.flash[0], 26, (230, 255, 240), fl.center, max_w=500)

    # ---- small drawing helpers
    def _card(self, img, r, sel):
        import ui
        if sel:
            img.blit(ui.neon_halo(r.w, r.h, (0, 230, 255), 22), (r.x - 12, r.y - 12))
        img.blit(ui.cockpit_surface(r.w, r.h, (26, 38, 66) if sel else (20, 28, 50), (8, 12, 26),
                                    (0, 230, 255) if sel else (46, 68, 108), 20), r.topleft)

    def _tag(self, img, r, text, col):
        import ui
        rib = pygame.Rect(r.x + 8, r.y + 8, 84, 22)
        pygame.draw.rect(img, col, rib, border_radius=10)
        ui.draw_text(img, text, 13, (255, 255, 255), rib.center, max_w=78)

    def _pill(self, img, r, cy, text, icon, fill, edge, old=None):
        import ui
        pill = pygame.Rect(0, 0, r.w - 40, 34)
        pill.center = (r.centerx, cy)
        img.blit(ui.cockpit_surface(pill.w, pill.h, fill, tuple(c // 2 for c in fill), edge, 17), pill.topleft)
        if icon == "gem":
            ui.draw_diamond_icon(img, pill.centerx - 30, pill.centery, 10, (0, 230, 255))
            ui.draw_text(img, text, 22, (230, 248, 255), (pill.centerx + 6, pill.centery))
            if old:
                ui.draw_text(img, str(old), 16, (150, 160, 185), (pill.right - 18, pill.centery), anchor="midright", bold=False)
                pygame.draw.line(img, (225, 60, 80), (pill.right - 18 - 8 * len(str(old)), pill.centery),
                                 (pill.right - 18, pill.centery), 2)
        elif icon == "star":
            ui.draw_vector_star(img, pill.centerx - 26, pill.centery, radius=11, filled=True)
            ui.draw_text(img, text, 22, (255, 232, 170), (pill.centerx + 8, pill.centery))
        else:
            ui.draw_text(img, text, 20, (235, 255, 245), pill.center, max_w=pill.w - 10)

    def _preview(self, img, rect, frame_id):
        """The profile badge (flag) inside a frame - what the ranking row will look like."""
        import ui
        ui.draw_country_badge(img, self.save_mgr.player_country, rect.centerx, rect.centery, width=rect.w - 20, height=rect.h - 18)
        draw_frame(img, rect, frame_id)

    def _market_art(self, img, r, m):
        import ui
        cx, cy = r.centerx, r.y + 70
        k = m["kind"]
        if k in ("shield", "revive"):
            product_art(img, k, (cx, cy), 96)
            ui.draw_text(img, f"x{m['payload']}", 19, (225, 240, 255), (cx + 55, cy + 25))
        elif k == "gems":
            ui.draw_diamond_icon(img, cx, cy, 34, (0, 230, 255))
            ui.draw_text(img, f"+{m['payload']}", 24, (255, 255, 255), (cx + 56, cy + 30), anchor="midleft")
        elif k == "frame":
            self._preview(img, pygame.Rect(cx - 59, cy - 31, 118, 62), m["payload"])
        else:                                              # a title: a gold ribbon with two stars
            title_emblem(img, m["payload"], (cx, cy), 70)

    def _market_name(self, m):
        k = m["kind"]
        if k in ("shield", "revive", "gems"):
            return t("sx_mk_" + k, n=m["payload"])
        return frame_name(m["payload"]) if k == "frame" else title_text(m["payload"])

    def _chest_icon(self, img, c):
        product_art(img, "chest", c, 150)

    @staticmethod
    def _chest_button(r):
        return pygame.Rect(r.right - 324, r.y + 63, 300, 84)

    def _prestige_cell(self, img, r, pid, is_frame):
        import ui
        sm = self.save_mgr
        owned = pid in sm.prestige_owned
        equipped = pid == (sm.prestige_frame if is_frame else sm.prestige_title)
        sel = self.item == ("frame" if is_frame else "title", pid)
        self._card(img, r, sel)
        info = SI.FRAME.get(pid) if is_frame else SI.TITLE.get(pid)
        if is_frame:
            self._preview(img, pygame.Rect(r.centerx - 70, r.y + 24, 140, 70), pid)
            ui.draw_text(img, frame_name(pid), 21, ui.TEXT_WHITE, (r.centerx, r.y + 118), max_w=r.w - 20)
            cy = r.y + 151
        else:
            draw_title_badge(img, pygame.Rect(r.x + 16, r.y + 16, r.w - 32, 60), pid, 23)
            cy = r.y + 101
        if equipped:
            ui.draw_text(img, t("sx_equipped"), 16, (120, 255, 190), (r.centerx, cy))
        elif owned:
            ui.draw_text(img, t("sx_owned"), 16, (120, 255, 190), (r.centerx, cy))
        else:
            ui.draw_diamond_icon(img, r.centerx - 26, cy, 8, (0, 230, 255))
            ui.draw_text(img, str(info[1]), 19, (230, 248, 255), (r.centerx - 10, cy), anchor="midleft")

    def _bar_action(self, pid):
        sm = self.save_mgr
        is_frame = pid in SI.FRAME
        info = SI.FRAME.get(pid) or SI.TITLE.get(pid)
        if pid in sm.prestige_owned:
            if pid == (sm.prestige_frame if is_frame else sm.prestige_title):
                return t("sx_unequip"), (110, 70, 90)
            return t("sx_equip"), (96, 140, 255)
        ok = sm.diamonds >= info[1]
        return t("sx_buy", price=info[1]), ((0, 170, 220) if ok else (70, 76, 96))

    # ---- the item preview (the shop's top panel, like a skin): tapping a card only selects it
    def select_item(self, typ, key):
        self._click()
        self.item = (typ, key)
        self.sel_week = None
        self.on_change()

    def clear_item(self):
        if self.item is not None or self.sel_week is not None:
            self.item = None
            self.sel_week = None
            self.on_change()

    def item_info(self):
        """What the top panel shows for the selected product: name, text, art, the buy / equip button."""
        it = self.item
        if not it:
            return None
        typ, key = it
        sm = self.save_mgr
        if typ == "pack":
            item, n, price = SI.PACKS[key]
            stock = sm.shield_stock if item == "shield" else sm.revive_stock
            return {"name": t("sx_pack_shield" if item == "shield" else "sx_pack_revive", n=n), "desc": t("sx_desc_pack_" + item),
                    "art": (item, n), "label": t("sx_buy", price=price), "ok": sm.diamonds >= price, "fn": lambda: self._buy_pack(key),
                    "note": t("sx_stock", n=stock) + "  -  " + t("sx_pack_left", n=self._pack_left(item))}
        if typ == "wframe":
            fr = self._week_items()[1]
            if fr["id"] != key:
                self.item = None
                return None
            owned = key in sm.prestige_owned
            return {"name": frame_name(key), "desc": t("sx_desc_wframe") + "  " + _fmt_left(SI.week_end(time.time()) - time.time()),
                    "art": ("frame", key), "label": t("owned") if owned else t("sx_buy", price=fr["price"]),
                    "ok": (not owned) and sm.diamonds >= fr["price"], "fn": lambda: self._week_frame(fr), "note": ""}
        if typ in ("frame", "title"):
            is_frame = typ == "frame"
            text, col = self._bar_action(key)
            return {"name": frame_name(key) if is_frame else title_text(key), "desc": t("sx_desc_" + typ), "art": (typ, key),
                    "label": text, "ok": key in sm.prestige_owned or sm.diamonds >= (SI.FRAME.get(key) or SI.TITLE.get(key))[1],
                    "fn": lambda: self._bar_press(key), "note": ""}
        if typ == "mkt":
            m = next((x for x in self._market_items() if x["id"] == key), None)
            if m is None:
                self.item = None
                return None
            sold = m.get("left", 1) <= 0
            return {"name": self._market_name(m), "desc": t("sx_desc_mkt"), "art": (m["kind"], m["payload"]),
                    "label": (t("owned") if m.get("owned") else t("sx_sold")) if sold else t("sx_stars", n=m["stars"]),
                    "ok": (not sold) and sm.star_coins >= m["stars"], "fn": lambda: self._market(m),
                    "note": "" if sold else t("sx_left_week", n=m.get("left", m["limit"])), "stars": True}
        return None

    def press(self):
        info = self.item_info()
        if info and not self.busy and self.anim is None:
            info["fn"]()

    def draw_item_art(self, surface, tm):
        """The selected product in the shop's preview panel (drawn every frame, so it can move a little)."""
        import math
        info = self.item_info()
        if not info:
            return
        self.draw_art(surface, info["art"][0], info["art"][1], 450, int(272 + 6 * math.sin(tm * 2.4)), 1.0)

    def draw_art(self, surface, kind, payload, cx, cy, s=1.0):
        import ui
        if kind in ("shield", "revive"):
            product_art(surface, kind, (cx, cy), int(210 * s))
            ui.draw_text(surface, f"x{payload}", int(40 * s), (235, 245, 255), (cx + 100 * s, cy + 80 * s))
        elif kind == "gems":
            ui.draw_diamond_icon(surface, cx, cy, int(70 * s), (0, 230, 255))
            ui.draw_text(surface, f"+{payload}", int(44 * s), (235, 245, 255), (cx + 100 * s, cy + 80 * s))
        elif kind == "chest":
            product_art(surface, "chest", (cx, cy), int(230 * s))
        elif kind == "title":
            title_emblem(surface, payload, (cx, cy), int(170 * s))
        else:                                              # a frame round the player's own flag badge
            rect = pygame.Rect(0, 0, int(300 * s), int(144 * s))
            rect.center = (cx, cy)
            ui.draw_country_badge(surface, self.save_mgr.player_country, cx, cy, width=rect.w - 24, height=rect.h - 20)
            draw_frame(surface, rect, payload, 6)

    # ---- taps (list coordinates; returns a callable or None)
    def tap(self, lp, y0, select_skin):
        L = self._layout()
        p = (lp[0], lp[1] - y0)
        if self.busy or self.anim is not None:
            return None
        skins, fr = self._week_items()
        for i, (sid, price, full, got) in enumerate(skins):
            if L["week"][i].collidepoint(p):
                return lambda s=sid: self._week_skin(s, select_skin)
        if L["week"][3].collidepoint(p):
            return lambda: self.select_item("wframe", fr["id"])
        for pid, r in L["packs"].items():
            if r.collidepoint(p):
                return lambda q=pid: self.select_item("pack", q)
        for fid, r in L["frame_cells"].items():
            if r.collidepoint(p):
                return lambda q=fid: self.select_item("frame", q)
        for tid, r in L["title_cells"].items():
            if r.collidepoint(p):
                return lambda q=tid: self.select_item("title", q)
        for i, m in enumerate(self._market_items()):
            if L["market"][i].collidepoint(p):
                return lambda mm=m: self.select_item("mkt", mm["id"])
        if L["chest"].collidepoint(p):
            return self._open_chest
        return None

    def _click(self):
        if self.audio:
            self.audio.play_sfx("sfx_click")

    def _say(self, text):
        self.shop._say(text, 3.5)
        self.on_change()

    def _fail(self, r, stars=False):
        err = (r or {}).get("error", "")
        code = (r or {}).get("code", 0)
        if err == "offline" or code in (404, 501):
            if code in (404, 501):
                return self._say(t("sx_unavail"))
            return self._say(t("sx_offline"))
        key = {"insufficient": "sx_need_stars" if stars else "not_enough_diamonds", "pack limit": "sx_limit", "chest limit": "sx_limit",
               "market limit": "sx_week_limit", "gone": "sx_gone", "owned": "sx_have_it"}.get(err, "sx_offline" if code == 0 else "sx_gone")
        self._say(t(key))

    def _go(self, op, arg, done, stars=False, on_fail=None):
        c = self._client()
        if c is None:
            if on_fail:
                on_fail()
            return self._say(t("sx_offline"))
        self.busy = True
        self.on_change()

        def cb(r):
            self.busy = False
            if r and r.get("ok"):
                done(r)
            else:
                if on_fail:
                    on_fail()
                self._fail(r, stars)
                c.refresh()                                 # limits / stock the screen showed were stale: fetch the truth
            self.on_change()
        c.act(op, arg, cb)

    def _week_skin(self, sid, select_skin):
        self._click()
        self.item = None
        self.sel_week = ("skin", sid)
        select_skin(sid)                                   # the top panel shows the skin: preview and buy button
        self.on_change()

    def _week_frame(self, fr):
        if fr["owned"]:
            return self._say(t("sx_have_it"))
        if self.save_mgr.diamonds < fr["price"]:
            return self._say(t("not_enough_diamonds"))
        self._go("buy", f"frame:{fr['id']}", lambda r: self._say(t("sx_got_item", name=frame_name(fr["id"]))))

    def _buy_pack(self, pid):
        item, n, price = SI.PACKS[pid]
        sm = self.save_mgr
        cap = sm.SHIELD_STOCK_CAP if item == "shield" else sm.REVIVE_STOCK_CAP
        if (sm.shield_stock if item == "shield" else sm.revive_stock) + n > cap:
            return self._say(t("sx_stock_full"))
        if self._pack_left(item) < n:
            return self._say(t("sx_limit"))
        if sm.diamonds < price:
            return self._say(t("not_enough_diamonds"))
        self._go("buy", f"pack:{pid}", lambda r: self._say(t("sx_got_shield" if item == "shield" else "sx_got_revive", n=n)))

    def _bar_press(self, pid):
        sm = self.save_mgr
        is_frame = pid in SI.FRAME
        slot = "frame" if is_frame else "title"
        if pid in sm.prestige_owned:
            cur = sm.prestige_frame if is_frame else sm.prestige_title
            self._go("equip", f"{slot}:{'' if cur == pid else pid}", lambda r: self._say(t("sx_equipped") if cur != pid else t("sx_unequip")))
            return
        info = SI.FRAME.get(pid) or SI.TITLE.get(pid)
        if info[2] != "perm":
            return self._say(t("sx_gone"))
        if sm.diamonds < info[1]:
            return self._say(t("not_enough_diamonds"))
        self._go("buy", f"{slot}:{pid}", lambda r: self._say(t("sx_bought")))

    def equip(self, slot, item_id, on_done=None):
        """Wear / take off a frame or title (the profile screen). on_done(ok)."""
        self._go("equip", f"{slot}:{item_id}", lambda r: on_done and on_done(True), on_fail=lambda: on_done and on_done(False))

    def _market(self, m):
        if m.get("left", 1) <= 0:
            return self._say(t("sx_have_it") if m.get("owned") else t("sx_week_limit"))
        if self.save_mgr.star_coins < m["stars"]:
            return self._say(t("sx_need_stars"))
        self._go("mkt", m["id"], lambda r: self._say(self._grant_text(r.get("grant") or {})), stars=True)

    def _grant_text(self, g):
        k, n = g.get("kind"), g.get("payload")
        if k == "gems":
            return t("sx_got_gems", n=n)
        if k == "shield":
            return t("sx_got_shield", n=n)
        if k == "revive":
            return t("sx_got_revive", n=n)
        if isinstance(n, str) and n in SI.TITLE:
            return t("sx_got_item", name=title_text(n))
        return t("sx_got_item", name=frame_name(n)) if isinstance(n, str) else t("sx_bought")

    # ---- the chest: an animated opening over the whole screen (drawn by draw_overlay every frame)
    def _open_chest(self):
        self._click()
        if self._chest_left() <= 0:
            return self._say(t("sx_chest_none"))
        if self.save_mgr.star_coins < SI.CHEST_COST:
            return self._say(t("sx_need_stars"))
        self.anim = {"t0": time.time(), "reward": None, "burst": None, "parts": []}

        def done(r):
            if self.anim is not None:
                self.anim["reward"] = r.get("reward") or {}
                self.anim["text"] = self._grant_text(self.anim["reward"])
            self._say(self._grant_text(r.get("reward") or {}))

        def failed():
            self.anim = None
        self._go("chest", "", done, stars=True, on_fail=failed)

    def anim_event(self, event):
        """While the chest opens every touch belongs to it; a tap closes the finished reward."""
        a = self.anim
        if a is None:
            return False
        if a["burst"] is not None and time.time() - a["burst"] > 1.6 and event.type in (pygame.MOUSEBUTTONUP, pygame.KEYDOWN):
            self.anim = None
            self.on_change()
        return True

    _lid = None

    def _chest_sprites(self):
        if ShopExtra._lid is None:
            tmp = pygame.Surface((300, 300), pygame.SRCALPHA)
            product_art(tmp, "chest", (150, 150), 300)
            ShopExtra._lid = (tmp.subsurface(pygame.Rect(0, 0, 300, 138)).copy(), tmp.subsurface(pygame.Rect(0, 138, 300, 162)).copy())
        return ShopExtra._lid

    def draw_overlay(self, surface):
        """Chest opening: shake and swelling glow, then the lid flies open with a flash, rays and sparks, and the
        reward rises out of the chest. Waits (shaking) for the server's answer if it is slow."""
        import math
        import random
        import ui
        a = self.anim
        if a is None:
            return
        now = time.time()
        T = now - a["t0"]
        if a["burst"] is None and a["reward"] is not None and T >= 1.3:
            a["burst"] = now
            a["parts"] = [(random.uniform(0, 6.283), random.uniform(160, 520), random.uniform(3, 8)) for _ in range(46)]
            if self.audio:
                self.audio.play_sfx("sfx_coin")
        B = (now - a["burst"]) if a["burst"] is not None else -1.0
        W, H = surface.get_size()
        dim = pygame.Surface((W, H), pygame.SRCALPHA)
        dim.fill((4, 8, 18, 244))
        surface.blit(dim, (0, 0))
        cx, cy = W // 2, 760
        lid, body = self._chest_sprites()
        swell = min(1.0, T / 1.3) if B < 0 else 1.0
        for k in range(5):                                  # a glow that swells while the chest shakes
            rad = int((90 + 60 * k) * (0.55 + 0.6 * swell))
            gl = pygame.Surface((rad * 2, rad * 2), pygame.SRCALPHA)
            pygame.draw.circle(gl, (255, 200, 70, int(16 + 10 * swell)), (rad, rad), rad)
            surface.blit(gl, (cx - rad, cy - rad))
        if B >= 0:                                          # light rays and the flash
            ang0 = B * 0.8
            alpha = int(120 * max(0.0, 1.0 - B / 1.6))
            if alpha > 0:
                ray = pygame.Surface((W, H), pygame.SRCALPHA)
                ln = 900 * min(1.0, B * 3)
                for k in range(14):
                    a1 = ang0 + k * (6.283 / 14)
                    pygame.draw.polygon(ray, (255, 226, 140, alpha), [(cx, cy - 40),
                                        (cx + math.cos(a1 - 0.06) * ln, cy - 40 + math.sin(a1 - 0.06) * ln),
                                        (cx + math.cos(a1 + 0.06) * ln, cy - 40 + math.sin(a1 + 0.06) * ln)])
                surface.blit(ray, (0, 0))
            fl = max(0.0, 1.0 - B / 0.5)
            if fl > 0:
                f = pygame.Surface((W, H), pygame.SRCALPHA)
                f.fill((255, 250, 225, int(190 * fl)))
                surface.blit(f, (0, 0))
        shake = 0.0 if B >= 0 else math.sin(T * 38) * (3 + 6 * swell)
        bx, by = cx + (0 if B >= 0 else math.sin(T * 31) * (2 + 5 * swell)), cy + 20
        surface.blit(body, body.get_rect(midtop=(bx, by - 8)))
        open_k = 0.0 if B < 0 else min(1.0, B / 0.35)
        open_k = 1 - (1 - open_k) ** 3
        angle = shake + open_k * 70.0                       # the lid turns up and back around its left-bottom corner
        hinge = pygame.math.Vector2(bx - 150, by - 8)
        centre = pygame.math.Vector2(150, -69)
        rot = pygame.transform.rotate(lid, angle)
        pos = hinge + centre.rotate(-angle)
        surface.blit(rot, rot.get_rect(center=(pos.x, pos.y)))
        if B >= 0:                                          # sparks
            for ang, spd, sz in a["parts"]:
                d = spd * (1 - math.exp(-B * 2.2)) / 2.2
                life = max(0.0, 1.0 - B / 1.8)
                if life > 0:
                    ui.sparkle(surface, cx + math.cos(ang) * d, cy - 30 + math.sin(ang) * d + 120 * B * B,
                               sz * (0.4 + life), (255, 236, 170))
        if a["reward"] is not None and B >= 0.25:           # the reward rises and pops
            r = a["reward"]
            u = min(1.0, (B - 0.25) / 0.7)
            ease = 1 - (1 - u) ** 3
            s_ = 0.7 + 0.5 * ease + (0.1 * math.sin(u * 3.14159) if u < 1 else 0.0)
            kind, payload = r.get("kind"), str(r.get("payload"))
            art = "title" if payload.startswith("title_") else ("frame" if payload.startswith("frame_") else kind)
            self.draw_art(surface, art, r.get("payload"), cx, int(cy - 40 - 250 * ease), s_)
            if B >= 0.9:
                ui.draw_text(surface, a.get("text", ""), 48, (255, 232, 160), (cx, cy + 250), max_w=W - 80)
                ui.draw_text(surface, t("sx_tap_close"), 24, (170, 190, 220), (cx, cy + 320), bold=False)
        elif B < 0:
            ui.draw_text(surface, t("sx_chest_opening"), 30, (255, 220, 140), (cx, cy + 250), bold=False)
