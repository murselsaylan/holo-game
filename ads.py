"""Ads (Google AdMob) - three places, see docs/ADS.md:

    "diamonds"  rewarded ad the player chooses to watch in the shop -> diamonds (server wallet kind "ad", capped per day)
    "continue"  rewarded interstitial on the crash screen -> one revive (server wallet kind "adrevive" pays its price)
    "levels"    interstitial after every LEVELS_PER_AD finished levels - gone for good with the "remove_ads" purchase

Android only for now (android_src/org/holo/ads/AdsBridge.java, Google Mobile Ads SDK + UMP consent). Ad unit ids come
from config.json "admob"; builds that are not release builds use Google's public test ids, so testing never touches
the real units. Without the bridge (desktop, iOS for now, debug APKs) available() is always False and the game shows
no ad buttons.
"""
import config
import paths

LEVELS_PER_AD = 10

# Google's public sample units: always fill, never pay (https://developers.google.com/admob/android/test-ads)
_TEST_IDS = {
    "android": {"diamonds": "ca-app-pub-3940256099942544/5224354917",
                "continue": "ca-app-pub-3940256099942544/5354046379",
                "levels": "ca-app-pub-3940256099942544/1033173712"},
    "ios": {"diamonds": "ca-app-pub-3940256099942544/1712485313",
            "continue": "ca-app-pub-3940256099942544/6978759866",
            "levels": "ca-app-pub-3940256099942544/4411468910"},
}


def unit_ids():
    """{slot: ad unit id} for this platform (real ids only in release builds)."""
    plat = "ios" if paths.is_ios() else "android"
    if not config.get("release_mode", False) or config.get("ads_test", False):
        return dict(_TEST_IDS[plat])
    real = (config.get("admob", {}) or {}).get(plat, {}) or {}
    return {"diamonds": real.get("rewarded_diamonds", ""), "continue": real.get("rewarded_interstitial_continue", ""),
            "levels": real.get("interstitial_levels", "")}


class Ads:
    def __init__(self):
        self._bridge = None
        self._wait = {}                     # slot -> (on_reward, on_close)
        if not paths.is_android() or config.get("ads_off", False):
            return
        ids = unit_ids()
        try:
            from jnius import autoclass     # python-for-android only
            activity = autoclass("org.kivy.android.PythonActivity").mActivity
            self._bridge = autoclass("org.holo.ads.AdsBridge")(activity, ids["diamonds"], ids["continue"], ids["levels"])
        except Exception as e:
            print("ads unavailable:", e)
            self._bridge = None

    def available(self, slot):
        """An ad of this slot can be shown right now (SDK in the build, consent given where needed, one loaded)."""
        if self._bridge is None or slot in self._wait:
            return False
        try:
            return bool(self._bridge.ready(slot))
        except Exception:
            return False

    def available_any(self):
        """Ads are part of this build at all (the remove-ads offer only makes sense then)."""
        return self._bridge is not None

    def show(self, slot, on_reward=None, on_close=None):
        """Shows the ad; on_reward() once if it was watched to the end (rewarded slots), on_close() when it is gone
        (also after a failure - the game always gets control back)."""
        if not self.available(slot):
            return False
        self._wait[slot] = (on_reward, on_close)
        try:
            self._bridge.show(slot)
            return True
        except Exception as e:
            print("ad error:", e)
            self._wait.pop(slot, None)
            return False

    def privacy_options_required(self):
        try:
            return self._bridge is not None and bool(self._bridge.privacyOptionsRequired())
        except Exception:
            return False

    def show_privacy_options(self):
        if self._bridge is not None:
            try:
                self._bridge.showPrivacyOptions()
            except Exception as e:
                print("privacy options error:", e)

    def poll(self):
        """Every frame: runs the callbacks of the ads that finished."""
        if self._bridge is None or not self._wait:
            return
        for _ in range(4):
            try:
                raw = str(self._bridge.pollResult() or "")
            except Exception:
                raw = ""
            if not raw:
                return
            slot, _, what = raw.partition("|")
            cbs = self._wait.get(slot)
            if cbs is None:
                continue
            on_reward, on_close = cbs
            if what == "REWARD":
                if on_reward:
                    on_reward()
                self._wait[slot] = (None, on_close)          # paid once
            else:                                            # CLOSED / FAIL|...
                self._wait.pop(slot, None)
                if on_close:
                    on_close()
