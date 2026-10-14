"""Ads end to end with a fake AdMob bridge (headless): diamonds for a rewarded video, "watch an ad, continue" on the
campaign and endless crash screens, the interstitial after ads.LEVELS_PER_AD finished levels, and the remove-ads
purchase switching the interstitial off.

    python tools/ads_test.py
"""
import os
import sys
import tempfile

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["HOLO_SAVE_DIR"] = tempfile.mkdtemp(prefix="holo_ads_")
os.environ["HOLO_SERVER"] = "http://127.0.0.1:9"

import pygame  # noqa: E402

import ads as ads_mod  # noqa: E402
import holo  # noqa: E402
import shop as shop_mod  # noqa: E402
import ui  # noqa: E402
from sim import SIM_DT  # noqa: E402

ok = True


def check(name, cond, extra=""):
    global ok
    ok &= bool(cond)
    print(("PASS " if cond else "FAIL ") + name, extra)


class FakeBridge:
    """Stands in for org.holo.ads.AdsBridge: every slot is always loaded, show() finishes at the next poll."""

    def __init__(self):
        self.shown = []
        self.queue = []

    def ready(self, slot):
        return True

    def show(self, slot):
        self.shown.append(slot)
        if slot in ("diamonds", "continue"):
            self.queue.append(slot + "|REWARD")
        self.queue.append(slot + "|CLOSED")

    def pollResult(self):
        return self.queue.pop(0) if self.queue else ""

    def privacyOptionsRequired(self):
        return False


g = holo.HoloGame(headless=True)
sm = g.save_mgr
sm.data.update(is_profile_set=True, player_name="ADS", player_country="TR", diamonds=0, howto_seen=True)
sm.wallet = None                                   # local wallet: earn / spend resolve at once
for lv in range(1, 12):
    sm.stats[str(lv)] = {"stars": 3, "best_score": 1000}
bridge = FakeBridge()
g.ads._bridge = bridge


def frames(n=1):
    for _ in range(n):
        g.update(SIM_DT, (450, 900))
        g.draw()


# 1) shop: a rewarded video pays AD_REWARD diamonds, AD_PER_DAY times a day
g.open_shop(top=True)
frames(2)
check("shop offers the ad row", g.shop_ui._ad_ready())
d0 = sm.diamonds
g._watch_ad_diamonds()
frames(2)
check("rewarded video pays diamonds", sm.diamonds == d0 + shop_mod.AD_REWARD, f"{d0} -> {sm.diamonds}")
check("the row is back as soon as the next video is there (no cooldown, 1.0.8)", g.shop_ui._ad_ready() == bool(g.ads.available("diamonds")))

# 2) campaign crash screen: the ad pays the revive
g.load_and_play_level(3)
g.state = "playing"
s = g.sim
g.swap_pivot()
frames(120)
s.dead = True                                      # a crash (the swing itself is tested elsewhere)
g.state, g.death_timer = "dying", 0.01
frames(3)
m = g.failure_modal
check("crash screen offers 'watch an ad, continue'", isinstance(m, ui.FailureModal) and m._ad_on(), type(m).__name__)
before = sm.diamonds
m._ad_continue()
frames(3)
check("the ad revives the pair", g.state == "playing" and not g.sim.dead, g.state)
check("the revive was paid by the ad (balance unchanged)", sm.diamonds == before, f"{before} -> {sm.diamonds}")
check("the revive is recorded as paid help", any(a[1] in ("R2", "R3") for a in g.assists), str(g.assists))

# 3) the interstitial after LEVELS_PER_AD finished levels, shown at the next level change
g.open_menu()
bridge.shown.clear()
sm.data["ad_levels"] = 0
g._ad_due = False
for k in range(ads_mod.LEVELS_PER_AD - 1):
    g._level_finished_for_ad()
check("no interstitial before the 10th level", not g._ad_due)
g._level_finished_for_ad()
check("interstitial owed after the 10th level", g._ad_due)
went = []
g._after_ad(lambda: went.append(1))
check("level change waits for the ad", bridge.shown == ["levels"] and not went)
frames(2)
check("the game continues when the ad closes", went == [1])
g._after_ad(lambda: went.append(2))
check("no second ad right after", went == [1, 2] and bridge.shown == ["levels"])

# 4) remove ads: the server's entitlement switches the interstitial off for good
sm.set_server_skins(["noads"])
check("remove-ads entitlement saved", sm.no_ads)
for k in range(ads_mod.LEVELS_PER_AD * 2):
    g._level_finished_for_ad()
g._after_ad(lambda: went.append(3))
check("no interstitials with remove-ads", went[-1] == 3 and bridge.shown == ["levels"])
check("rewarded ads stay available after remove-ads", g.ads.available("diamonds") and g.ads.available("continue"))

# 5) no bridge (desktop / iOS for now): nothing is offered anywhere
g.ads._bridge = None
check("without the SDK no ad is available", not g.ads.available("diamonds") and not g.ads.available_any())
print("ALL OK" if ok else "SOME FAILED")
sys.exit(0 if ok else 1)
