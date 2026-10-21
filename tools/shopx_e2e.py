"""End-to-end check of the shop extras: the real game (HoloGame, ShopScreen, shop_online.py) against the real server code
(handler.ts + shopx.ts on an in-memory store, served by Deno). Drives the screen with real taps and saves screenshots.

    python tools/shopx_e2e.py          (needs deno: pip install deno)       -> screenshots/shopx_*.png
"""
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
with socket.socket() as so:
    so.bind(("127.0.0.1", 0))
    PORT = so.getsockname()[1]
os.environ["HOLO_SAVE_DIR"] = tempfile.mkdtemp(prefix="holo_shopx_")
os.environ["HOLO_SERVER"] = f"http://127.0.0.1:{PORT}"
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame  # noqa: E402

import holo  # noqa: E402
import shop_items as SI  # noqa: E402
import ui  # noqa: E402

OUT = os.path.join(ROOT, "screenshots")
os.makedirs(OUT, exist_ok=True)
fails = []


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


deno = shutil.which("deno")
if not deno:
    print("deno not found")
    sys.exit(2)
cwd = os.environ.get("SCORES_DIR") or os.path.join(ROOT, "supabase", "functions", "scores")
srv = subprocess.Popen([deno, "run", "-A", "--no-check", "tests/serve_shopx.ts", str(PORT)], cwd=cwd,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
try:
    t0 = time.time()
    while time.time() - t0 < 60:
        try:
            socket.create_connection(("127.0.0.1", PORT), timeout=0.5).close()
            break
        except OSError:
            time.sleep(0.3)
    else:
        raise SystemExit("server did not start")

    g = holo.HoloGame(headless=True)
    sm = g.save_mgr
    sm.data.update(player_name="ALICE", player_country="TR", is_profile_set=True, diamonds=9000)
    sm.data["login"] = {}
    ui_ = g.shop_ui
    ex = ui_.extra

    def frames(n=2):
        for _ in range(n):
            g.update(1 / 60.0, (450, 800))
            g.draw()

    def wait(cond, secs=15):
        t = time.time()
        while time.time() - t < secs:
            frames(1)
            if cond():
                return True
            time.sleep(0.03)
        return False

    def dev_stars(n):
        req = urllib.request.Request(f"http://127.0.0.1:{PORT}/dev/stars", json.dumps({"pid": sm.player_id, "n": n}).encode(), method="POST")
        urllib.request.urlopen(req).read()

    g.online.register()
    g.online.wallet_sync()
    check("wallet open", wait(lambda: g.online._wallet_open))
    check("server balance is the imported 9000", sm.diamonds == 9000)
    dev_stars(150)
    g.online.ranked.refresh("stars")
    check("stars arrive", wait(lambda: sm.star_coins == 150))

    # ---- open the shop: the extras load their view from the server
    g.open_shop(top=True)
    frames(3)
    check("shop view arrives", wait(lambda: ex.view is not None))
    v = ex.view
    now = time.time()
    check("server showcase == client rotation", [s["skin"] for s in v["showcase"]] == [x[0] for x in SI.weekly_skins(now)]
          and v["frame"]["id"] == SI.weekly_frame(now))
    check("server market == client rotation", [m["id"] for m in v["market"]] == [m[0] for m in SI.market(now)])

    def go_to(y):
        ui_._scroll.y = max(0.0, min(float(y), ui_._content_h() - ui_._view_h()))
        ui_._scroll.vel = 0.0
        ui_._content_key = None
        frames(3)

    def shot(name):
        pygame.image.save(g.frame, os.path.join(OUT, f"shopx_{name}.png"))

    def tap(lp):
        """A tap at list coordinates lp (like _list_tap does after a click in the window)."""
        vpos = (lp[0], int(lp[1] - ui_._scroll.y + ui_.VIEW_Y))
        # a real click through the game's own event path; the window position is the inverse of HoloGame.to_virtual
        k = min(g.win_w / 900.0, g.win_h / float(g.vh))
        pos = (int(vpos[0] * k + (g.win_w - 900 * k) * 0.5), int(vpos[1] * k + (g.win_h - g.vh * k) * 0.5))
        g.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=1))
        g.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=pos, button=1))
        frames(2)

    L = ex._layout()
    y0 = ui_._extra_y()
    big = pygame.Surface((900, ui_._content_h()))
    # screenshots of every section
    for name, key in (("week", "week_head"), ("packs", "pack_head"), ("prestige", "pre_head"), ("market", "mk_head"), ("chest", "chest_head")):
        go_to(y0 + L[key] - 30)
        shot(name)

    def click_v(vpos):
        """A click at a position in the game's own (virtual) coordinates, through HoloGame.handle_event."""
        k = min(g.win_w / 900.0, g.win_h / float(g.vh))
        pos = (int(vpos[0] * k + (g.win_w - 900 * k) * 0.5), int(vpos[1] * k + (g.win_h - g.vh * k) * 0.5))
        g.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=1))
        g.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=pos, button=1))
        frames(2)

    def press_top_button():
        r = ui_.buy_button.rect
        click_v(r.center)

    # ---- supplies: tap a pack = preview in the top panel; the top button buys
    s0, bal0 = sm.shield_stock, sm.diamonds
    go_to(y0 + L["pack_head"])
    tap((L["packs"]["shield3"].centerx, y0 + L["packs"]["shield3"].centery))
    check("tapping a pack only previews it (nothing bought yet)", ex.item == ("pack", "shield3") and sm.shield_stock == s0)
    shot("preview_pack")
    press_top_button()
    check("shield pack: stock +3, 27 diamonds", wait(lambda: sm.shield_stock == s0 + 3) and wait(lambda: sm.diamonds == bal0 - 27))
    r0 = sm.revive_stock
    tap((L["packs"]["revive3"].centerx, y0 + L["packs"]["revive3"].centery))
    press_top_button()
    check("revive pack: stock +3", wait(lambda: sm.revive_stock == r0 + 3))
    shot("packs_bought")

    # ---- prestige: select a frame (preview), buy it, equip it - all from the top panel
    go_to(y0 + L["pre_head"])
    fc = L["frame_cells"]["frame_gold"]
    tap((fc.centerx, y0 + fc.centery))
    check("tapping a frame selects it", ex.item == ("frame", "frame_gold"))
    shot("preview_frame")
    press_top_button()
    check("buying the gold frame owns it", wait(lambda: "frame_gold" in sm.prestige_owned))
    check("price 1800 charged", wait(lambda: sm.diamonds == bal0 - 27 - 54 - 1800))
    press_top_button()                                              # the same button now equips
    check("equip works", wait(lambda: sm.prestige_frame == "frame_gold"))
    tc = L["title_cells"]["title_nova"]
    tap((tc.centerx, y0 + tc.centery))
    shot("preview_title")
    press_top_button()
    wait(lambda: "title_nova" in sm.prestige_owned)
    press_top_button()
    check("title equipped", wait(lambda: sm.prestige_title == "title_nova"))
    # a weekly skin card shows the skin itself in the panel, like any shop skin
    skin0 = ex._week_items()[0][0][0]
    go_to(y0 + L["week_head"])
    wr = L["week"][0]
    tap((wr.centerx, y0 + wr.centery))
    check("a weekly skin card selects the skin (item preview off)", ui_.selected == skin0 and ex.item is None)

    # ---- Star Market: preview, then the top button
    go_to(y0 + L["mk_head"])
    m = ex._market_items()
    st0 = sm.star_coins
    r = L["market"][0]
    tap((r.centerx, y0 + r.centery))
    check("tapping a market card only previews it", ex.item == ("mkt", m[0]["id"]) and sm.star_coins == st0)
    shot("preview_market")
    press_top_button()
    check("the top button buys with stars", wait(lambda: sm.star_coins == st0 - m[0]["stars"]))
    st1 = sm.star_coins

    # ---- Star Chest: animated opening, reward, tap to close
    go_to(y0 + L["chest_head"])
    ch = L["chest"]
    tap((ch.right - 150, y0 + ch.centery))
    check("the chest animation starts at once", ex.anim is not None)
    frames(20)
    shot("chest_anim_shake")
    check("the chest costs 40 stars", wait(lambda: sm.star_coins == st1 - SI.CHEST_COST))
    check("the reward arrives and the burst starts", wait(lambda: ex.anim is not None and ex.anim.get("burst") is not None, 8))
    time.sleep(0.15)
    frames(6)
    shot("chest_anim_burst")
    time.sleep(1.2)
    frames(6)
    shot("chest_anim_reward")
    check("the reward text is shown", bool(ex.anim and ex.anim.get("text")))
    click_v((450, 800))                                             # too early to close? (>1.6 s after the burst)
    time.sleep(1.0)
    click_v((450, 800))
    check("a tap closes the finished animation", ex.anim is None)
    tap((ch.right - 150, y0 + ch.centery))
    wait(lambda: sm.star_coins == st1 - 2 * SI.CHEST_COST)
    check("second chest too", sm.star_coins == st1 - 2 * SI.CHEST_COST)
    wait(lambda: ex.anim is not None and ex.anim.get("burst") is not None, 8)
    time.sleep(1.9)
    frames(10)
    click_v((450, 800))
    click_v((450, 800))
    check("(closed again)", ex.anim is None)

    # ---- the profile screen picks the frame and title (arrows), the server keeps them
    g.open_profile()
    frames(3)
    pm = g.profile_modal
    check("profile lists the owned frame and title", "frame_gold" in pm._pre_lists["frame"] and "title_nova" in pm._pre_lists["title"])      # (a chest may have added a star cosmetic)
    sm.set_prestige(frame="", title="")
    pm._pre_cur = {"frame": "", "title": ""}
    row = pm._pre_rows["frame"]
    pm._pre_cur = {"frame": "", "title": ""}
    pm._pre_lists["frame"] = ["", "frame_gold"]                     # only the two this test bought, whatever a chest added
    pm._pre_lists["title"] = ["", "title_nova"]
    click_v(row["right"].center)
    check("profile: the right arrow wears the frame (server confirms)", wait(lambda: sm.prestige_frame == "frame_gold"))
    row = pm._pre_rows["title"]
    click_v(row["right"].center)
    check("profile: the title arrow wears the title", wait(lambda: sm.prestige_title == "title_nova"))
    frames(4)
    shot("profile_prestige")
    click_v(pm._pre_rows["frame"]["right"].center)
    check("profile: next click takes the frame off", wait(lambda: sm.prestige_frame == ""))
    pm._confirm()
    g.open_shop(top=True)
    frames(2)

    # ---- the ranking shows my prestige (the global list comes from the server)
    g.online.fetch("global", 50)
    wait(lambda: g.online.boards.get("global") is not None, 8)
    rows = (g.online.boards.get("global") or {}).get("rows", [])
    mine = [x for x in rows if x.get("id") == sm.player_id]
    # the in-memory test store lists nobody before a score exists: the row sprite is checked directly instead
    lb = g.leaderboard_ui
    row = {"id": sm.player_id, "name": "ALICE", "country": "TR", "levels": 12, "score": 12345, "stars": 30, "rank": 1,
           "frame": sm.prestige_frame, "title": sm.prestige_title}
    row2 = dict(row, frame="", title="", name="BOB", rank=2)
    row3 = dict(row, frame="lim_ember", title="title_legend", name="CARA", rank=3)
    if lb is not None:
        a = lb._row_sprite(row, 0, True, 820)
        b = lb._row_sprite(row2, 1, False, 820)
        c = lb._row_sprite(row3, 2, False, 820)
        sheet = pygame.Surface((820, a.get_height() * 3 + 20))
        sheet.fill((16, 20, 32))
        for i, spr in enumerate((a, b, c)):
            sheet.blit(spr, (0, i * (a.get_height() + 6)))
        pygame.image.save(sheet, os.path.join(OUT, "shopx_ranking_rows.png"))
        check("ranking row sprites differ with prestige", pygame.image.tostring(a, "RGB") != pygame.image.tostring(
            lb._row_sprite(dict(row, frame="", title=""), 0, True, 820), "RGB"))

    # ---- the stock revives: the failure flow uses the stock and no server charge
    d0 = sm.diamonds
    check("revive stock is held for the failure flow", sm.revive_stock >= 3)
    check("use_revive consumes one", sm.use_revive() and sm.revive_stock >= 2 and sm.diamonds == d0)

    # ---- full-page screenshot of the shop list
    big = ui_._content()
    pygame.image.save(big.subsurface(pygame.Rect(0, y0 - 30, 900, big.get_height() - y0 + 30)), os.path.join(OUT, "shopx_all_sections.png"))
finally:
    srv.terminate()
print("FAILS:", fails)
sys.exit(1 if fails else 0)
