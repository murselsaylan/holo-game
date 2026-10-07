"""Headless UI/logic test: screens, skin catalogue, shop (test billing), shield, achievements rewards, how-to card, music.

    python tools/ui_test.py
"""
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
check("85 skins in 17 catalogues of 5", len(skins.SKINS) == 85 and len(C.THEMES) == 17 and all(len(t[2]) == 5 for t in C.THEMES))
check("every catalogue skin exists exactly once", sorted(C.ORDER) == sorted(skins.SKINS) and len(set(C.ORDER)) == 85)
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

# ---- music follows the place -----------------------------------------------------------------------------------------
g.load_and_play_level(2)
frames(2)
check("sector track while playing", g._music_track == "bgm_synthwave")
g.state = "menu"
frames(2)
check("menu track in menus", g._music_track == "bgm_menu")

print("\nFAILED:" if fails else "\nALL OK", fails or "")
sys.exit(1 if fails else 0)
