"""Headless UI/logic test: screens, skin catalogue, shop (test billing), shield, achievements rewards, how-to card, music.

    python tools/ui_test.py
"""
import json
import os
import sys
import tempfile

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["HOLO_SAVE_DIR"] = tempfile.mkdtemp(prefix="holo_uitest_")
os.environ["HOLO_SERVER"] = "http://127.0.0.1:1"
os.environ["HOLO_DEV_PURCHASES"] = "1"

import pygame  # noqa: E402
import holo  # noqa: E402
import ui  # noqa: E402
import config  # noqa: E402
import achievements as ach  # noqa: E402
import skin_catalog as C  # noqa: E402
import skins  # noqa: E402
import shop as shop_mod  # noqa: E402
import locales  # noqa: E402

fails = []


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


# ---- catalogue data ---------------------------------------------------------------------------------------------
check("90 skins in 18 catalogues of 5", len(skins.SKINS) == 90 and len(C.THEMES) == 18 and all(len(t[2]) == 5 for t in C.THEMES))
check("every catalogue skin exists exactly once", sorted(C.ORDER) == sorted(skins.SKINS) and len(set(C.ORDER)) == 90)
check("rarity order 1..5 inside each catalogue", all([C.tier(s) for s in t[2]] == [1, 2, 3, 4, 5] for t in C.THEMES))
from collections import Counter  # noqa: E402
src = Counter(C.source(s)[0] for s in C.ORDER)
check("sources: 15 level / 8 achievement / 57 shop / 5 endless-star", (src["level"], src["ach"], src["shop"], src["star"]) == (15, 8, 57, 5))
check("legendary = the 16 premium skins with a real-money price", set(skins.PREMIUM_SKINS) == set(shop_mod.SKIN_PRICE) and len(skins.PREMIUM_SKINS) == 16)
check("achievement rewards point at real achievements", all(a in ach.BY_ID for a in C.ACH.values()))
check("no tip / donate left", not hasattr(shop_mod, "TIPS") and not hasattr(shop_mod.Shop, "tip") and not hasattr(shop_mod.Shop, "open_donate_page"))
check("default language is English", __import__("save_manager").DEFAULT_SETTINGS["language"] == "en" and locales.ACTIVE_LANG == "en")
check("4 complete languages (tr/en/de/es, same key set)", set(locales.LANGUAGES) == {"tr", "en", "de", "es"} and
      all(set(locales.STRINGS[lg].keys()) == set(locales.STRINGS["en"].keys()) for lg in locales.LANGUAGES))
check("shop showcase always picks a legendary skin", C.featured_skin() in C.premium_ids())

config._CACHE = {"server_url": "x", "dev_free_purchases": True}   # dev config: DevBilling active, shipping flags unset
g = holo.HoloGame(headless=True)
sm = g.save_mgr
# the server-owned wallet is covered by supabase/functions/scores/tests (wallet/purchase/assist); here the UI runs on the
# local wallet so every purchase / spend resolves at once
sm.wallet = None
sm.data["is_profile_set"] = True
sm.data["player_name"] = "TESTER"


def frames(n=3):
    for _ in range(n):
        g.update(1 / 60.0, (450, 800))
        g.draw()


for state in ("menu", "leaderboard", "skins", "shop", "achievements"):
    g.state = state
    frames()
check("screens draw without errors", True)
g.open_skins()
for k in range(len(C.THEMES)):                                   # every catalogue page renders
    g.skin_ui.cat = k
    g.skin_ui.selected_skin = C.THEMES[k][2][0]
    frames(1)
check("all 16 catalogue pages render", True)

# ---- sources -----------------------------------------------------------------------------------------------------
check("only neon_pulse is owned at the start", [s for s in skins.SKINS if sm.is_skin_unlocked(s)] == ["neon_pulse"])
sm.stats["5"] = {"stars": 3, "best_score": 1, "best_time": 1.0, "best_swaps": 1, "rank": "A"}
check("reaching level 5 unlocks its common skin", sm.is_skin_unlocked("mars_rover") and not sm.is_skin_unlocked("stardust_dream"))

# ---- shop with the test billing ---------------------------------------------------------------------------------
sm.data["diamonds"] = 600
g.shop.buy_skin_with_diamonds("cosmic_void")
check("diamond purchase of a rare skin", sm.diamonds == 350 and sm.is_skin_unlocked("cosmic_void"))
g.shop.buy_skin("supernova")
g.shop.poll()                                   # the store answers on the next frame
check("test purchase of a legendary skin with money", sm.is_skin_unlocked("supernova"))
check("commons/achievement skins cannot be bought", (g.shop.buy_skin("stardust_dream") or True) and not sm.is_skin_unlocked("stardust_dream"))
g.shop.buy_diamonds("pack_100")
g.shop.poll()
check("diamond pack adds diamonds", sm.diamonds == 450)
before = sm.diamonds
g.shop.buy_shield()
check("shield costs 10 diamonds", sm.diamonds == before - 10 and sm.shield_stock == 1)
sm.data["shield_stock"] = 5
check("shield stock is capped", g.shop.buy_shield() is False and sm.shield_stock == 5)
sm.data["shield_stock"] = 0

plain = shop_mod.Shop(sm)
plain.billing = shop_mod.Billing()
plain.buy_diamonds("pack_350")
check("closed shop gives no diamonds", sm.diamonds == before - 10 and plain.current_message() == "shop_unavailable")

# ---- daily missions ------------------------------------------------------------------------------------------
missions, progress, claimed, streak = sm.daily_missions()
check("3 daily missions generated", len(missions) == 3 and len(set(m["id"] for m in missions)) == 3)
m0 = missions[0]
check("mission not claimable before its target is reached", not sm.claim_daily(m0["id"]))
sm.bump_daily(m0["metric"], m0["target"])
d_before = sm.diamonds
check("finished mission is claimable and pays its diamond reward", sm.claim_daily(m0["id"]) and sm.diamonds == d_before + m0["reward"])
check("a claimed mission cannot be claimed twice", not sm.claim_daily(m0["id"]))
check("main menu shows a daily-missions button", g.menu_ui.btn_daily is not None)
def _tap_progress():
    r = g.menu_ui.progress_rect
    for typ in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
        cb = g.menu_ui.handle_event(pygame.event.Event(typ, pos=r.center, button=1))
    return cb


check("main menu: tapping the progress bar opens the level select (replay cleared levels)",
      _tap_progress() == g.open_level_select)
check("level select never reveals levels ahead of real progress",
      sm.unlocked_level == sm.highest_cleared + 1 and sm.unlocked_level < holo.MAX_LEVELS)

# ---- language cycle (settings): tr -> en -> de -> es -> tr -------------------------------------------------------
sm.language = "tr"
seen = []
for _ in range(4):
    seen.append(sm.language)
    g.settings_modal._toggle_lang()
check("language button cycles through all 4 languages and back to tr", seen == ["tr", "en", "de", "es"] and sm.language == "tr")

# ---- achievements give skins ----------------------------------------------------------------------------------------
ach.bump(sm, "smash", 10)
g._ach_next = 0.0                               # achievements are checked 4x a second
frames(2)
check("achievement 'smasher' rewards pixel_probe", sm.is_skin_unlocked("pixel_probe") and "smasher" in ach.unlocked_ids(sm))
check("achievement pays +5 diamonds", sm.diamonds >= before - 10 + 5)

# ---- onboarding: 2-page how-to + one-time welcome gift ---------------------------------------------------------------
g.attempts = 2
g.load_and_play_level(1)
check("how-to shown on first launch", g.state == "howto")
check("onboarding opens on page 1 (controls)", g.howto_ui.page == 0)
gift_before = sm.diamonds
g.howto_ui._advance()
check("page 2 introduces shop/ranking/daily/achievements and grants the welcome gift",
      g.howto_ui.page == 1 and sm.diamonds == gift_before + g.howto_ui.WELCOME_GIFT)
g.howto_ui._advance()
check("finishing onboarding returns to gameplay", g.state == "playing")
regift_before = sm.diamonds
g.howto_ui.reset()
g.howto_ui._advance()
check("the welcome gift is granted only once, ever", sm.diamonds == regift_before)

# ---- failure screen: pay-to-continue (revive) -----------------------------------------------------------------------
sm.data["diamonds"] = 5
g.sim.dead = True
g.state = "dying"
g.death_timer = 0.0
for _ in range(80):
    g.update(1 / 60.0, (0, 0))
check("failure modal shows a revive button", g.state == "failed" and hasattr(g.failure_modal, "btn_revive"))
check("revive is blocked with too few diamonds", not g.revive_run() and g.sim.dead and sm.diamonds == 5)
sm.data["diamonds"] = 50
check("revive with enough diamonds resumes in place and spends the cost",
      g.revive_run() and g.state == "playing" and not g.sim.dead and sm.diamonds == 50 - holo.REVIVE_COST and g.assisted)

# ---- a shield armed before the first swap survives a restart --------------------------------------------------------
g.restart_level()
g.sim.shields = 2
g.run_bought = 2
check("sim reports no swaps yet (precondition)", g.sim.swaps == 0)
g.restart_level()
check("an unused pre-swap shield carries over into the fresh attempt", g.sim.shields == 2 and g.run_bought == 2)
g.sim.swap()
g.restart_level()
check("a shield after the first swap does NOT carry over (it was already in play)", g.sim.shields == 0 and g.run_bought == 0)

# ---- settings: progress can no longer be reset from the settings (removed on request) ------------------------------
check("settings offer no progress reset", not hasattr(g.settings_modal, "btn_reset") and not hasattr(g.settings_modal, "_reset_tap"))

# ---- friends (1.0.9) ---------------------------------------------------------------------------------------------
import friends_ui  # noqa: E402

lb = g.leaderboard_ui
check("leaderboard tabs: general / endless / friends - no league, world or star road tab",
      [k for k, _ in lb.tabs] == ["global", "endless", "friends"])
check("3 ranking tabs sit in one row, tall enough to tap, not overlapping",
      all(b.rect.h >= 60 and b.rect.right <= ui.VW for _, b in lb.tabs)
      and not any(a.rect.colliderect(b.rect) for i, (_, a) in enumerate(lb.tabs) for _, b in lb.tabs[i + 1:]))
check("[WORLD | MY COUNTRY] is one full-width control under the tabs, two touching halves 64+ px tall",
      lb._seg_visible() and lb.btn_world.rect.x == 40 and lb.btn_country.rect.right == ui.VW - 40
      and lb.btn_world.rect.right == lb.btn_country.rect.x and lb.btn_world.rect.h >= 64
      and lb.btn_world.rect.y >= max(b.rect.bottom for _, b in lb.tabs))
check("[WORLD | MY COUNTRY] is a two-way switch: world is on, country off", not lb.country_only)
lb.btn_country.callback()
check("pressing MY COUNTRY selects it (board key country)", lb.country_only and lb.board_key == "country")
lb.btn_country.callback()
check("pressing it again keeps it (a switch, not a toggle)", lb.country_only)
lb.btn_world.callback()
check("pressing WORLD goes back to the world board", not lb.country_only and lb.board_key == "global")
lb.set_scope("country")
check("'my country' is a button on the list: world + country filter", lb.scope == "global" and lb.country_only and lb.board_key == "country")
lb.set_scope("endless")
check("country filter also applies to the endless board", lb.board_key == "endless_country")
lb.toggle_country()
check("country button toggles off again", lb.board_key == "endless")
lb.set_scope("global")

calls = []
real_op = g.online.friends_op
g.online.friends_op = lambda op, arg="", on_done=None: calls.append((op, arg, on_done))
sm.data["level_stats"] = {str(n): {"stars": 3, "best_score": 1000 * n, "best_time": 1.0, "best_swaps": 1, "rank": "A"} for n in range(1, 9)}
g.online.friends = {"ok": True, "code": "ABCD-EFGH", "max": 30, "credits": {"shield": 0, "revive": 0}, "asked_today": 0,
                    "friends": [
                        {"id": "f" * 32, "name": "BOB", "country": "TR", "levels": 3, "score": 99999999, "stars": 9, "status": "friend", "sent": ["poke"]},
                        {"id": "e" * 32, "name": "CARA", "country": "DE", "levels": 12, "score": 5, "stars": 1, "status": "friend", "sent": []},
                        {"id": "d" * 32, "name": "DAN", "country": "TR", "levels": 1, "score": 1, "stars": 0, "status": "incoming", "sent": []},
                        {"id": "c" * 32, "name": "EVE", "country": "TR", "levels": 1, "score": 1, "stars": 0, "status": "outgoing", "sent": []}],
                    "inbox": [{"id": 11, "from": "f" * 32, "from_name": "BOB", "kind": "gift", "item": "diamond", "amount": 5, "level": 0},
                              {"id": 12, "from": "f" * 32, "from_name": "BOB", "kind": "poke", "item": "", "amount": 0, "level": 0},
                              {"id": 13, "from": "e" * 32, "from_name": "CARA", "kind": "challenge", "item": "", "amount": 5, "level": 4}],
                    "help": [{"id": 21, "from": "e" * 32, "from_name": "CARA", "kind": "help", "item": "shield", "amount": 1, "level": 9}]}
g.online.friends_status = "ok"
lb.set_scope("friends")
rows = lb._rows()
check("friends tab = me + accepted friends only (pending ones are not on the board)", len(rows) == 3 and sum(1 for r in rows if r.get("me")) == 1)
check("friends are ranked by score like the world list", [r["rank"] for r in rows] == [1, 2, 3] and rows[0]["name"] == "BOB")
check("the world / country control is hidden on the friends tab", not lb._seg_visible())
check("tab shows a dot while things wait for me", lb.friends_waiting() == 1 + 3 + 1)
g.state = "leaderboard"
frames(2)
lb._open_row(rows[0])
labels = [b.text for b in lb.sel_btns]
check("tapping a friend opens gift / poke / challenge / remove / close", len(labels) == 5 and not lb.sel_btns[1].enabled and lb.sel_btns[0].enabled)
frames(2)
lb.sel_btns[0].callback()
check("gift button asks the server for a gift to that friend", calls[-1][:2] == ("gift", "f" * 32))
lb._open_row(rows[0])
lb.sel_btns[2].callback()
check("challenge picks the lowest level I cleared and the friend did not (level 4)", calls[-1][:2] == ("challenge", "f" * 32 + ":4"))
calls[-1][2]({"ok": True})
check("a successful answer shows a toast", lb.toast[1] > 0 and lb.toast[0] != "")
lb._open_row(rows[0])
lb.sel_btns[3].callback()
check("remove button removes the friend", calls[-1][:2] == ("remove", "f" * 32))
calls.clear()

g.open_friends()
check("friends window opens", g.state == "friends" and g.friends_modal is not None)
calls.clear()
frames(3)
fm = g.friends_modal
keys = [r[0] for r in fm._rows]
check("window lists help request, inbox, requests (help first)", keys[0] == "h21" and "m11" in keys and "m12" in keys and "m13" in keys
      and "r" + "d" * 32 in keys and "o" + "c" * 32 in keys and len(keys) == 6)
calls.clear()
fm._rows[0][3][0].callback()
check("YOLLA sends help_send for that request", calls[-1][:2] == ("help_send", "21"))
calls[-1][2]({"ok": True, "added": 5, "item": "shield"})
check("help answer toast mentions the reward", fm.toast[1] > 0 and "5" in fm.toast[0])
for k, op in (("m11", "claim"), ("r" + "d" * 32, "accept")):
    row = next(r for r in fm._rows if r[0] == k)
    row[3][0].callback()
    check(f"{k} button -> {op}", calls[-1][0] == op)
fm.code_text = "abcdefgh"
fm._add()
check("typing a code and pressing ADD sends it", calls[-1][:2] == ("add", "ABCDEFGH"))
calls[-1][2]({"ok": True, "state": "pending", "name": "ZED"})
check("add answer says the request went out", "ZED" in fm.toast[0])
fm.code_text = "abc"
n = len(calls)
fm._add()
check("a short code is not sent", len(calls) == n)
g.close_friends()
check("closing returns to the leaderboard", g.state == "leaderboard" and g.friends_modal is None)

# the failure screen: 'ask for help' only from the 3rd try and only with friends
asked = []
fmod = ui.FailureModal(5, 40, 0, 1, 3, lambda: None, lambda: None, save_mgr=sm, shop=g.shop, on_revive=lambda: None)
fmod.on_help = lambda: asked.append(1)
fmod.help_probe = lambda: (True, False)
check("help button shows from the 3rd try with friends", fmod._help_state() is False)
fmod.help_probe = lambda: (True, True)
check("... and reads 'request sent' after asking", fmod._help_state() is True)
fmod.help_probe = lambda: (False, False)
check("... and is hidden without friends", fmod._help_state() is None)
fmod2 = ui.FailureModal(5, 40, 0, 1, 2, lambda: None, lambda: None, save_mgr=sm, shop=g.shop, on_revive=lambda: None)
fmod2.on_help, fmod2.help_probe = lambda: None, lambda: (True, False)
check("... and hidden before the 3rd try", fmod2._help_state() is None)
fmod.help_probe = lambda: (True, False)
fmod._help()
check("tapping it asks", asked == [1])
surf = pygame.Surface((900, 1620))
fmod.draw(surf)

# free shields / revives from friends are used before diamonds: spending needs no balance for them
class _W:
    credits = {"shield": 0, "revive": 1}
    sent = []
    def wallet_spend(self, item, cost, on_done):
        self.sent.append(item)
        on_done(True, "")
sm.wallet = _W()
sm.data["diamonds"] = 0
res = []
sm.spend("revive", 20, lambda ok, why: res.append(ok))
check("a friend's revive can be used with 0 diamonds", res == [True] and sm.wallet.sent == ["revive"])
res.clear()
sm.spend("shield", 10, lambda ok, why: res.append((ok, why)))
check("... but a shield still costs diamonds when none was gifted", res == [(False, "insufficient")])
sm.wallet = None

# ---- the failure screen's shield button (1.0.9) --------------------------------------------------------------------
class _WS:
    credits = {"shield": 0, "revive": 0}
    free_shield = True
    sent = []

    def wallet_flush(self):
        pass

    def wallet_spend(self, item, cost, on_done):
        self.sent.append((item, cost))
        if item == "shield" and self.free_shield:
            self.free_shield = False                    # the server's "daily" answer
        elif sm.diamonds < cost:
            return on_done(False, "insufficient")
        else:
            sm.data["diamonds"] = sm.diamonds - cost
        on_done(True, "")


def _fmod(tries):
    m = ui.FailureModal(5, 40, 0, 1, tries, lambda: None, lambda: None, save_mgr=sm, shop=g.shop, on_revive=lambda: None)
    m.on_shield = lambda: None
    return m


sm.wallet = _WS()
sm.data["shield_stock"] = 0
sm.data["diamonds"] = 0
m3 = _fmod(3)
check("shield button: today's free shield wins over everything", m3.shield_mode() == "free")
sm.wallet.free_shield = False
check("... with 0 diamonds and no stock it is 'short' (greyed)", m3.shield_mode() == "short")
sm.data["diamonds"] = shop_mod.SHIELD_COST
check("... with SHIELD_COST diamonds it is 'buy'", m3.shield_mode() == "buy")
sm.data["shield_stock"] = 2
check("... with a stock it is 'stock' (free)", m3.shield_mode() == "stock")
m_none = ui.FailureModal(5, 40, 0, 1, 3, lambda: None, lambda: None, save_mgr=sm, shop=g.shop, on_revive=lambda: None)
check("no button without the game's callback", m_none.shield_mode() is None)
check("the buy label carries no gem glyph (drawn icon only)", "💎" not in ui.shield_label(sm, "buy")[0] and ui.shield_label(sm, "buy")[1] == "gem")
m3.draw(pygame.Surface((900, 1620)))
check("button text for stock / buy / free / short exist in 4 languages",
      all(locales.STRINGS[l].get(k) for l in ("tr", "en", "de", "es")
          for k in ("shield_retry_stock", "shield_retry_free", "shield_retry_buy", "shield_retry_need", "shield_free_tag",
                    "shield_short_toast")))
check("client price equals the server table", shop_mod.SHIELD_COST == 10)

# in the game: dying, tapping it starts the next attempt with the shield on the pair (assist S at step 0)
sm.data["shield_stock"] = 0
sm.wallet = _WS()
sm.data["diamonds"] = 50
g.load_and_play_level(5)
g.state = "playing"
g.swap_pivot()
frames(30)
g.sim.dead = True
g.state, g.death_timer = "dying", 0.01
frames(3)
fm = g.failure_modal
check("the death screen has the shield button (free today)", isinstance(fm, ui.FailureModal) and fm.shield_mode() == "free")
fm.draw(pygame.Surface((900, 1620)))
att0 = g.attempts
g._ad_due = False
fm._shield()
frames(3)
check("tapping it plays the next attempt with a shield on", g.state == "playing" and g.sim.shields == 1 and g.attempts == att0 + 1)
check("... recorded as bought help (assist S at step 0) and in the stock", [0, "S"] in g.assists and sm.shield_stock == 1)
check("... the free shield was asked of the server at price 10 (server charges 0)", sm.wallet.sent[-1] == ("shield", 10))
check("... and no diamonds were taken (an achievement may add)", sm.diamonds >= 50)
sm.wallet = None
sm.data["shield_stock"] = 0

# endless: the result card offers a new climb with a shield (assist S at step 0, the server replays it)
sm.wallet = _WS()
sm.data["shield_stock"] = 1
sm.data["diamonds"] = 50
_unl, config.dev_unlock_all = config.dev_unlock_all, (lambda: True)        # endless unlocked
g.open_endless()
g.state = "playing"
g.swap_pivot()
frames(40)
g.sim.dead = True
g.state, g.death_timer = "dying", 0.01
frames(3)
for _ in range(3):                                   # revive card first (if shown): finish the climb
    if isinstance(g.failure_modal, ui.EndlessReviveModal):
        g.failure_modal.on_finish()
    frames(3)
em = g.failure_modal
check("endless result card has the shield button", isinstance(em, ui.EndlessResultModal) and em.shield_mode() == "stock")
em.draw(pygame.Surface((900, 1620)))
em._shield()
frames(3)
check("a new shielded climb starts: shield on the pair, assist S at 0, stock used for the run",
      g.endless_run is not None and g.state == "playing" and g.sim.shields >= 1 and [0, "S"] in g.assists)
import endless as E_  # noqa: E402
r_ = E_.replay(g.endless_run.seed, [], assists=[[0, "S"]], max_steps=60)
check("the endless replay accepts the S assist", r_ is not None)
g._leave_endless()
config.dev_unlock_all = _unl
sm.wallet = None
sm.data["shield_stock"] = 0

# friend ghost beats the world's #1
g.online.friend_ghosts[3] = {"id": "f" * 32, "name": "BOB", "score": 100, "taps": [50, 120, 200]}
g.online.ghosts[3] = {"id": "9" * 32, "name": "WORLD", "score": 200, "taps": [60, 130]}
g.load_and_play_level(3)
frames(2)
check("a friend's run is the ghost (labelled friend) instead of the world #1", g.ghost is not None and g.ghost_friend and g.ghost_name == "BOB")
g.online.friend_ghosts[3] = {}
g._install_ghost()
check("without a friend run the world #1 is the ghost again", g.ghost is not None and not g.ghost_friend and g.ghost_name == "WORLD")
g.online.friends_op = real_op
g.state = "menu"
frames(2)

# ---- music follows the place -----------------------------------------------------------------------------------------
g.load_and_play_level(2)
frames(2)
check("sector track while playing", g._music_track == "bgm_synthwave")
g.state = "menu"
frames(2)
check("menu track in menus", g._music_track == "bgm_menu")

# ---- shared weekly goal + level of the week (1.0.9) -------------------------------------------------------------------
import time as _time  # noqa: E402
import olo_lines  # noqa: E402
import crowd_ui  # noqa: E402
cw = g.online.crowd
cw.refresh = lambda *a, **k: None
cw.data = {"ok": True, "week": "2026-W43", "goal": 3000, "total": 1710, "contributors": 9, "mine": 18, "min_contrib": 3,
           "ends": int(_time.time()) + 90000,
           "tiers": [{"tier": 1, "pct": 33, "need": 990, "reward": 10, "reached": True, "claimed": False, "claimable": True},
                     {"tier": 2, "pct": 66, "need": 1980, "reward": 20, "reached": False, "claimed": False, "claimable": False},
                     {"tier": 3, "pct": 100, "need": 3000, "reward": 40, "reached": False, "claimed": False, "claimable": False}],
           "wlevel": {"level": 3, "pct": 40.0, "cleared": False, "claimed": False, "reward": 15}}
cw.state = "ok"
sm.data["level_stats"] = {str(n): {"stars": 3, "best_score": 1000, "best_time": 1.0, "best_swaps": 1, "rank": "A"} for n in range(1, 6)}
check("claimable count = tier waiting", cw.claimable() == 1 and cw.tier_reached() == 1)
g.state = "menu"
g.menu_ui.set_enter(1.0)
frames(3)
check("the menu has no team-goal strip, no star road button and no weekly card any more",
      not hasattr(g.menu_ui, "crowd_provider") and not g.menu_ui.callbacks.get("stars")
      and not hasattr(crowd_ui, "STRIP") and not hasattr(crowd_ui, "draw_strip"))
check("endless is the only mode button: full width", len(g.menu_ui.buttons) == 2 and g.menu_ui.buttons[1].rect.w == 600)
check("menu badge: a claimable team-goal tier shows on the DAILY button", g.menu_ui._extra() == 1
      and g.menu_ui._daily_badge() >= 1)
b0 = g.menu_ui._daily_badge()
cw.data["tiers"][0]["claimable"] = False
check("the badge goes away once nothing is claimable", g.menu_ui._daily_badge() == b0 - 1)
cw.data["tiers"][0]["claimable"] = True
g.open_crowd()
frames(2)
check("open_crowd opens the daily screen on the team-goal section (no separate page)",
      g.state == "daily" and g.daily_ui.tab == "crowd" and not hasattr(g, "crowd_modal"))
sent = []
cw.claim = lambda tier, on_done=None: sent.append(("claim", tier))
cw.claim_level = lambda on_done=None: sent.append(("wclaim",))
m = g.daily_ui._panel()
check("the section body is the crowd panel", type(m).__name__ == "CrowdPanel")


def tap(btn):
    for ty in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
        g.daily_ui.handle_event(pygame.event.Event(ty, pos=btn.rect.center, button=1))


tap(m.btn_tiers[0])
check("claim button sends the tier number only", sent == [("claim", 1)])
tap(m.btn_tiers[1])
check("a tier that is not claimable has no live button", sent == [("claim", 1)])
played = []
m.on_play_level = lambda lv: played.append(lv)
frames(2)
tap(m.btn_play)
check("PLAY starts the level of the week (unlocked)", played == [3])
cw.data["wlevel"]["level"] = 99
frames(2)
played.clear()
tap(m.btn_play)
check("a locked weekly level cannot be started from the window", played == [])
cw.data["wlevel"].update(level=3, cleared=True)
frames(2)
tap(m.btn_wclaim)
check("cleared weekly level: the reward button claims it", sent[-1] == ("wclaim",))
g.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, mod=0, unicode="", scancode=0))
check("back key leaves the missions page to the menu", g.state == "menu")
for kind in ("crowd_t1", "crowd_t2", "crowd_t3", "crowd_go", "wlevel_new", "wlevel_clear"):
    check(f"Olo has {kind} lines in all 4 languages", kind in olo_lines.R and all(
        all(lg in tx for _, tx in r for lg in ("tr", "en", "de", "es")) for r in olo_lines.R[kind]))
# Olo speaks about the goal once per week and kind
g.olo.active = False
cw.data["tiers"][0]["claimable"] = True
cw.data["wlevel"].update(cleared=False)
sm.data["crowd_olo"] = []
said = []
g._olo_say = lambda kind, **kw: said.append(kind)
import olo as _olo_mod  # noqa: E402
_real_en = _olo_mod.enabled
_olo_mod.enabled = lambda s: True
g._crowd_tick("menu")
g._crowd_tick("menu")
_olo_mod.enabled = _real_en
check("Olo mentions a claimable tier once", said == ["crowd_t1"])

# ---- share card (1.0.9) ------------------------------------------------------------------------------------------------
import share_card  # noqa: E402
import share as share_mod  # noqa: E402
_dir = tempfile.mkdtemp(prefix="holo_cards_")
_sizes = {}
for _lg in ("tr", "en", "de", "es"):
    locales.set_language(_lg)
    for _v in share_card.VARIANTS:
        for _shape in ("story", "square"):
            _p = share_card.make(_v, 99, 3, 12345, 20.5, 6, size=_shape, out_dir=_dir)
            _sizes[(_lg, _v, _shape)] = pygame.image.load(_p).get_size()
locales.set_language("en")
check("cards: 1080x1920 story and 1080x1080 square, 3 variants x 4 languages",
      len(_sizes) == 24 and all(s == ((1080, 1920) if k[2] == "story" else (1080, 1080)) for k, s in _sizes.items()))
check("card text names the store link", "play.google.com/store/apps/details?id=com.hologame.holo" in share_card.message("record", 7))
check("share sheet is not available on the desktop (card is only saved)", share_mod.send(os.path.join(_dir, "x.png"), "x") is False)
g.online.crowd.data = {"wlevel": {"level": 9}, "tiers": []}
g.assisted = False
g.attempts = 1
check("level of the week -> weekly card", g._share_variant(9, False, True) == "weekly")
check("a better score on a level cleared before -> record card", g._share_variant(4, True, False) == "record")
check("first clear, no records, few tries -> no card", g._share_variant(4, False, True) is None)
g.attempts = 6
check("six tries on one level -> hard-level card", g._share_variant(4, False, True) == "hard")
g.assisted = True
check("a run with paid help gets no card", g._share_variant(4, True, False) is None)
g.assisted = False
g.attempts = 1
g.load_and_play_level(9)
g.sim.won = True
g._on_win()
frames(2)
check("victory screen of the weekly level offers both card shapes", [s for _, s in g.victory_modal.share_btns] == ["story", "square"])
_made = []
g._share_card = lambda variant, lid, res, attempts, shape: _made.append((variant, lid, shape))
g._offer_share(9, {"stars": 1, "level_total": 1, "time": 1.0}, False, True)
for _b, _s in g.victory_modal.share_btns:
    if _s == "square":
        for _ty in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
            _act = g.victory_modal.handle_event(pygame.event.Event(_ty, pos=_b.rect.center, button=1))
        _act()
check("tapping SHARE . SQUARE makes the weekly square card", _made == [("weekly", 9, "square")])

# ---- daily level (1.0.9) ----------------------------------------------------------------------
import ranked_ui  # noqa: E402
import star_road  # noqa: E402

_rk = g.online.ranked
_rk.stars = {"ok": True, "stars": 62, "earned": 90, "shield_cost": 12, "shields_left": 5, "campaign_cap": 300, "campaign": 80}
_rk.daily = {"ok": True, "day": 20000, "level": 37, "ends": 4102444800, "reward": 10, "reward_3": 5, "state": "open", "claimed": False,
             "run": None, "rank": 0, "total": 3, "board": [{"rank": i + 1, "name": "ACE%d" % i, "country": "DE", "score": 52000 - i * 700,
                                                          "stars": 3, "time": 21.5 + i, "me": False} for i in range(3)]}
for _k in ("stars", "daily"):
    _rk.state[_k] = "ok"
    _rk.fetched[_k] = 9e18                                     # fresh: the tab switch does not hit the network
_rk.refresh = lambda *a, **k: None
sm.data["level_stats"] = {str(n): {"stars": 3, "best_score": 1000 * n, "best_time": 1.0, "best_swaps": 1, "rank": "A"} for n in range(1, 6)}
check("the daily level opens after level 3", sm.stars_unlocked)
check("no star road left: no client calls, no panel, no texts",
      not hasattr(_rk, "claim_road") and not hasattr(_rk, "claim_chest") and not hasattr(_rk, "road_claimable")
      and not hasattr(ui.LeaderboardScreen, "_road_ready") and not hasattr(star_road, "ROAD") and not hasattr(star_road, "CHEST_STARS")
      and locales.t("rk_stars_have") == "rk_stars_have")
_rk.stars_reply = {"ok": True, "stars": 62, "earned": 90, "shield_cost": 12}
_rk._apply("stars", dict(_rk.stars_reply))
check("a stars answer still syncs the star wallet (Star Hunter skins)", sm.star_coins == 62)
_calls = []
g.open_ranked("daily")
frames(2)
check("daily level opens on the daily screen", g.state == "daily" and g.daily_ui.tab == "daily")
_m = g.daily_ui._panel()
_m._body()
check("daily tab offers PLAY while the try is open", len(_m.hits) == 1)
_m._ask_daily()
check("the one-try card asks first", _m.confirm)
_m.draw(g.frame)
_started = []
g._start_daily = lambda lv: _started.append(lv)
_m.on_play_daily = g._start_daily
_rk.daily_start = lambda cb=None: cb({"ok": True, "first": True, "level": 37})
_m._go_daily()
check("START spends the try on the server, then plays the level", _started == [37])
check("no league any more: no league scope, card or client state",
      not hasattr(lb, "toggle_league") and not hasattr(lb, "_has_card") and not hasattr(_rk, "league") and "league" not in _rk.state
      and not hasattr(star_road, "LEAGUE_REWARDS") and locales.t("rk_lg_rank") == "rk_lg_rank")
lb.set_scope("endless")
check("the list starts right under the world / country switch", lb._lt() == lb.top + lb.SEG_H)
lb.set_scope("global")
# ---- the three new tabs: each one draws, the entries reach them, the old windows are gone ------------------------------
import ranked_ui as _rui  # noqa: E402
check("the old modal classes are gone", not hasattr(_rui, "RankedModal") and not hasattr(crowd_ui, "CrowdModal"))
for _sc in ("daily", "crowd", "missions"):
    g.state = "menu"
    g._open_daily_missions(_sc)
    frames(3)
    _px = pygame.transform.average_color(g.frame, pygame.Rect(40, 260, ui.VW - 80, 400))
    check(f"daily screen section {_sc} draws (body not blank)", g.state == "daily" and g.daily_ui.tab == _sc and sum(_px[:3]) > 30)
check("the daily screen has 3 sections in one row, tappable and not overlapping",
      [k for k, _ in g.daily_ui.tab_btns] == ["missions", "daily", "crowd"]
      and all(b.rect.h >= 60 and b.rect.right <= ui.VW for _, b in g.daily_ui.tab_btns)
      and not any(a.rect.colliderect(b.rect) for i, (_, a) in enumerate(g.daily_ui.tab_btns) for _, b in g.daily_ui.tab_btns[i + 1:]))
for _sc in ("daily", "crowd", "missions"):
    g.daily_ui.set_tab(_sc)
    check(f"section button {_sc} is the highlighted one",
          [k for k, b in g.daily_ui.tab_btns if b.border_color == ui.ACCENT_CYAN] == [_sc])
g.state = "menu"
g.open_ranked("global")
check("open_ranked(scope) opens the ranking on that scope", g.state == "leaderboard" and lb.scope == "global")
g.daily_ui.set_tab("missions")
_unlocked = sm.data.get("level_stats")
sm.data["level_stats"] = {}
check("the daily level is locked before level 3", not sm.stars_unlocked)
g.daily_ui.set_tab("daily")
check("a locked daily section stays on the missions and says why", g.daily_ui.tab == "missions" and g.daily_ui.toast[1] > 0)
sm.data["level_stats"] = _unlocked
lb.set_scope("global")
_calls.clear()
# the daily run itself: no retry, shield, revive; a win does not touch campaign progress
g.state = "menu"
_hi = sm.highest_cleared
g.__class__._start_daily(g, 37)
frames(2)
check("daily level loads with no progress side effects", g.daily_run == {"level": 37} and g.state == "playing" and g.sim is not None)
_sim0 = g.sim
g.restart_level()
g.retry_after_fail()
g.use_hud_shield()
check("daily: restart / retry / shield are ignored", g.sim is _sim0 and not g.sim.shields)
g.sim.won = True
g._on_win()
check("daily win shows the result card, saves no clear", g.state == "daily_result" and sm.highest_cleared == _hi
      and "37" not in sm.stats)
g.daily_modal.set_reply({"ok": True, "state": "done", "run": {"score": 51000, "stars": 3, "time": 20.0}, "rank": 2, "total": 9, "added": 15})
frames(2)
check("result card takes the server reply", g.daily_modal.reply["rank"] == 2)
g.daily_modal.draw(g.frame)
g.state = "menu"
g.daily_run = None


# ---- shop extras: weekly showcase, supplies, prestige, Star Market, Star Chest (shop_items.py / shop_ui_extra.py) -------
import shop_items as SI  # noqa: E402
import shop_ui_extra  # noqa: E402

_wd = open(os.path.join(ROOT, "supabase", "functions", "scores", "wallet_data.ts"), encoding="utf-8").read()
check("wallet_data.ts carries SHOPX (python tools/gen_wallet_data.py is current)",
      "export const SHOPX = " + json.dumps(SI.server_table(), ensure_ascii=False) + " as const;" in _wd)
for _lang in locales.LANGUAGES:
    _miss = [k for k in [f"fr_{f[0]}" for f in SI.FRAMES] + [f"ti_{x[0]}" for x in SI.TITLES] if k not in locales.STRINGS[_lang]]
    check(f"every frame / title has a name in {_lang}", not _miss)
_t0 = 1_792_000_000
_w1 = SI.weekly_skins(_t0)
check("the weekly showcase is 3 distinct diamond skins, 20 % off", len({x[0] for x in _w1}) == 3 and all(
    x[1] < x[2] and "prestige" not in x[0] and x[0] in C.COST for x in _w1))
_mon = (SI.week_index(_t0) + 1) * 7 * 86400 - 3 * 86400            # the next Monday 00:00 UTC
check("the showcase turns over on Monday 00:00 UTC (and only then)",
      SI.week_index(_mon - 1) == SI.week_index(_t0) and SI.week_index(_mon) == SI.week_index(_t0) + 1 and
      SI.weekly_skins(_t0) != SI.weekly_skins(_mon) and SI.week_end(_t0) == _mon and
      __import__("datetime").datetime.utcfromtimestamp(_mon).weekday() == 0)
check("a week's three market slots come from their pools", all(m[0] in SI.MARKET for m in SI.market(_t0)) and
      [m[1] for m in SI.market(_t0)][1] == "gems")
check("pack prices are cheaper than singles", all(price < n * (10 if item == "shield" else 20) for item, n, price in SI.PACKS.values()))
check("chest weights add up to 100 and the star cap fits the dearest star item",
      sum(w for w, _k, _p in SI.CHEST_TABLE) == 100 and SI.STAR_CAP >= max(C.STAR_COST.values()))
check("long-term diamond sink: the permanent prestige items cost 20000+",
      sum(f[1] for f in SI.FRAMES if f[2] == "perm") + sum(x[1] for x in SI.TITLES if x[2] == "perm") >= 20000)
sm.data["revive_stock"] = 0
sm.data["shield_stock"] = 0
sm.add_revive(99)
sm.add_shield(99)
check("stock caps hold", sm.revive_stock == sm.REVIVE_STOCK_CAP == SI.STOCK_CAP["revive"] and
      sm.shield_stock == sm.SHIELD_STOCK_CAP == SI.STOCK_CAP["shield"])
check("a stocked revive is used up one at a time", sm.use_revive() and sm.revive_stock == sm.REVIVE_STOCK_CAP - 1)
sm.data["shield_stock"] = 0
sm.data["revive_stock"] = 0
g.open_shop(top=True)
frames(3)
_ex = g.shop_ui.extra
check("the shop page grew by the five sections", g.shop_ui._content_h() > g.shop_ui._extra_y() + 1500)
for _off in range(0, int(g.shop_ui._content_h()), 700):
    g.shop_ui._scroll.y = float(_off)
    frames(1)
check("the whole shop list scrolls and draws", True)
_ex._buy_pack("shield3")
frames(1)
check("offline (no wallet in this test): a pack buy charges nothing and gives nothing", sm.shield_stock == 0)
sm.set_prestige(owned=["frame_gold"], frame="frame_gold", title="")
g.leaderboard_ui._row_sprite({"id": "x", "name": "A", "country": "TR", "levels": 3, "stars": 3, "score": 9, "rank": 1,
                              "frame": "frame_gold", "title": "title_nova"}, 0, False, 820)
check("a ranking row with prestige renders", True)

print("\nFAILED:" if fails else "\nALL OK", fails or "")
sys.exit(1 if fails else 0)
