"""Rewarded video ads (prepared in 1.0.6, switched OFF until the AdMob account exists - see docs/ADS.md).

available() is False unless config.json has "admob_rewarded_id" AND the app was built with
android_optional/org/holo/ads/RewardedBridge.java moved into android_src/. Until then the game shows no ad buttons.
When an ad is watched to the end, on_reward() runs once; the diamonds go through the server wallet (kind "ad",
limited per day by supabase/functions/scores/wallet.ts).
"""
import config


class RewardedAds:
    def __init__(self):
        self.unit_id = str(config.get("admob_rewarded_id", "") or "").strip()
        self._bridge = None
        self._on_reward = None
        if not self.unit_id:
            return
        try:
            from jnius import autoclass   # python-for-android only
            activity = autoclass("org.kivy.android.PythonActivity").mActivity
            self._bridge = autoclass("org.holo.ads.RewardedBridge")(activity, self.unit_id)
        except Exception as e:
            print("rewarded ads unavailable:", e)
            self._bridge = None

    def available(self):
        """An ad can be offered right now (built in, configured and one is loaded)."""
        try:
            return self._bridge is not None and bool(self._bridge.ready())
        except Exception:
            return False

    def show(self, on_reward):
        if not self.available() or self._on_reward is not None:
            return False
        self._on_reward = on_reward
        try:
            self._bridge.show()
            return True
        except Exception as e:
            print("rewarded ad error:", e)
            self._on_reward = None
            return False

    def poll(self):
        """Every frame: pays the reward once the player watched the ad to the end."""
        if self._bridge is None or self._on_reward is None:
            return
        try:
            raw = str(self._bridge.pollResult() or "")
        except Exception:
            raw = "FAIL|bridge"
        if raw == "REWARD":
            cb, self._on_reward = self._on_reward, None
            cb()
        elif raw:                       # closed early / failed: nothing paid
            self._on_reward = None
