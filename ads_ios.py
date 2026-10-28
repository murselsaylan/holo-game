"""iOS side of ads.py: the same small interface as android_src/org/holo/ads/AdsBridge.java (ready / show / pollResult /
privacyOptionsRequired / showPrivacyOptions, plus tick), over the Google Mobile Ads SDK + UMP that
tools/make_ios_project.py links into the app, through rubicon-objc.

Every SDK callback is delivered on the main thread while SDL pumps its events (inside pygame.event.get), so plain
Python lists and dicts are enough - nothing here runs concurrently with the game loop.
"""
import ctypes
import time

from rubicon.objc import Block, NSObject, ObjCClass, ObjCInstance, objc_method
from rubicon.objc.runtime import objc_id

KINDS = {"diamonds": "GADRewardedAd", "continue": "GADRewardedInterstitialAd", "levels": "GADInterstitialAd"}
RETRY_S = (5, 15, 30, 60, 120, 300)
UMP_PRIVACY_REQUIRED = 1                # UMPPrivacyOptionsRequirementStatusRequired

_bridge = None                          # the one AdsBridgeIOS (the delegate below reports to it)


def _p(obj, name):
    """A property value (rubicon exposes some properties as methods)."""
    v = getattr(obj, name)
    return v() if callable(v) else v


def _inst(ptr):
    return ObjCInstance(ptr) if ptr else None


def _why(err):
    try:
        return str(_p(err, "localizedDescription"))
    except Exception:
        return "error"


def _root_vc():
    app = _p(ObjCClass("UIApplication"), "sharedApplication")
    win = _p(app, "keyWindow") or _p(_p(app, "windows"), "firstObject")
    vc = _p(win, "rootViewController")
    while True:                         # present over whatever is on top already (a consent form, ...)
        top = _p(vc, "presentedViewController")
        if top is None:
            return vc
        vc = top


class HoloAdDelegate(NSObject):
    """GADFullScreenContentDelegate: tells the bridge when the ad on screen is gone."""

    @objc_method
    def adDidDismissFullScreenContent_(self, ad: objc_id) -> None:
        if _bridge is not None:
            _bridge._gone("CLOSED")

    @objc_method
    def ad_didFailToPresentFullScreenContentWithError_(self, ad: objc_id, error: objc_id) -> None:
        if _bridge is not None:
            _bridge._gone("FAIL|" + _why(_inst(error)))


class AdsBridgeIOS:
    def __init__(self, diamonds, cont, levels):
        global _bridge
        _bridge = self
        self.units = {"diamonds": diamonds, "continue": cont, "levels": levels}
        self.ads = {}                   # slot -> loaded ad object
        self.loading = set()
        self.fails = {}                 # slot -> failures in a row
        self.next_try = {}              # slot -> time.monotonic() of the next load attempt
        self.results = []               # "slot|REWARD" / "slot|CLOSED" / "slot|FAIL|why"
        self.showing = None             # (slot, ad) on screen
        self.started = False
        self._keep = []                 # blocks the SDK holds until it calls them
        self._last_tick = 0.0
        self.delegate = HoloAdDelegate.alloc().init()
        self.att_wait = True            # the system tracking prompt (ATT) is still to be answered: no ads before it
        self._att_next = None
        self._att_due = time.monotonic() + 2.5      # the prompt needs the app active: ask a moment after the first frames

    # ------------------------------------------------------------------ ATT (system prompt) -> consent (UMP) -> SDK start
    def _att(self):
        """App Tracking Transparency comes first (App Review 5.1.2(i)): the system asks before the consent form is shown
        and before any ad is requested. An answer of 'not allowed' still lets ads run (without the advertising id)."""
        try:
            mgr = ObjCClass("ATTrackingManager")
            status = int(_p(mgr, "trackingAuthorizationStatus"))
        except Exception as e:
            print("ads (iOS): ATT unavailable:", e)
            self.att_wait = False
            self._consent()
            return
        if status != 0:                 # already answered (0 = not determined)
            self.att_wait = False
            self._consent()
            return
        try:
            mgr.requestTrackingAuthorizationWithCompletionHandler_(self._block(self._att_done, ctypes.c_ulong))
            print("ads (iOS): ATT prompt requested")
        except Exception as e:
            print("ads (iOS): ATT request failed:", e)
            self.att_wait = False
            self._consent()

    def _att_done(self, status):
        self._att_next = "consent"      # the next tick() (the game's main thread) goes on with the consent form

    # ------------------------------------------------------------------ consent (UMP) -> SDK start
    def _block(self, fn, *argtypes):
        b = Block(fn, None, *argtypes)
        self._keep.append(b)
        del self._keep[:-24]
        return b

    def _consent(self):
        try:
            info = _p(ObjCClass("UMPConsentInformation"), "sharedInstance")
            params = ObjCClass("UMPRequestParameters").alloc().init()
            info.requestConsentInfoUpdateWithParameters_completionHandler_(
                params, self._block(self._consent_info, objc_id))
        except Exception as e:
            print("ads (iOS): consent unavailable:", e)
        self._start_if_allowed()        # consent from an earlier run is enough to start right away

    def _consent_info(self, err):
        if err:
            print("ads (iOS): consent info:", _why(_inst(err)))
        try:
            ObjCClass("UMPConsentForm").loadAndPresentIfRequiredFromViewController_completionHandler_(
                _root_vc(), self._block(self._consent_done, objc_id))
        except Exception as e:
            print("ads (iOS): consent form:", e)
            self._start_if_allowed()

    def _consent_done(self, err):
        if err:
            print("ads (iOS): consent form:", _why(_inst(err)))
        self._start_if_allowed()

    def _can_request(self):
        try:
            return bool(_p(_p(ObjCClass("UMPConsentInformation"), "sharedInstance"), "canRequestAds"))
        except Exception:
            return True                 # no UMP in the build: Google's own defaults apply

    def _start_if_allowed(self):
        if self.started or self.att_wait or not self._can_request():
            return
        self.started = True
        try:
            _p(ObjCClass("GADMobileAds"), "sharedInstance").startWithCompletionHandler_(
                self._block(lambda status: None, objc_id))
            print("ads (iOS): started")
        except Exception as e:
            print("ads (iOS): start failed:", e)
            self.started = False
            return
        for slot in self.units:
            self._load(slot)

    # ------------------------------------------------------------------ loading
    def _load(self, slot):
        unit = self.units.get(slot)
        if not unit or slot in self.ads or slot in self.loading or not self.started:
            return
        self.loading.add(slot)
        try:
            req = ObjCClass("GADRequest").request()
            ObjCClass(KINDS[slot]).loadWithAdUnitID_request_completionHandler_(
                unit, req, self._block(lambda ad, err, s=slot: self._loaded(s, ad, err), objc_id, objc_id))
        except Exception as e:
            print("ads (iOS): load", slot, e)
            self._loaded(slot, None, None)

    def _loaded(self, slot, ad, err):
        self.loading.discard(slot)
        ad = _inst(ad)
        if ad is None:
            n = self.fails.get(slot, 0)
            self.fails[slot] = n + 1
            self.next_try[slot] = time.monotonic() + RETRY_S[min(n, len(RETRY_S) - 1)]
            print("ads (iOS): no", slot, "ad:", _why(_inst(err)) if err else "?")
            return
        self.fails[slot] = 0
        try:
            ad.fullScreenContentDelegate = self.delegate
        except Exception:
            ad.setFullScreenContentDelegate_(self.delegate)
        self.ads[slot] = ad
        print("ads (iOS):", slot, "ad loaded")

    def tick(self):
        """Called every frame by ads.Ads.poll: retries the slots whose last load failed."""
        now = time.monotonic()
        if self._att_due and now >= self._att_due:
            self._att_due = 0.0
            self._att()
            return
        if self._att_next == "consent":
            self._att_next = None
            self.att_wait = False
            self._consent()
            return
        if now - self._last_tick < 1.0:
            return
        self._last_tick = now
        if self.att_wait:
            return                      # waiting for the player's answer to the tracking prompt
        if not self.started:
            self._start_if_allowed()
            return
        for slot in self.units:
            if slot not in self.ads and slot not in self.loading and now >= self.next_try.get(slot, 0):
                self._load(slot)

    # ------------------------------------------------------------------ the AdsBridge interface
    def ready(self, slot):
        return self.showing is None and slot in self.ads

    def show(self, slot):
        ad = self.ads.pop(slot, None)
        if ad is None or self.showing is not None:
            self.results.append(f"{slot}|FAIL|not ready")
            return
        self.showing = (slot, ad)
        vc = _root_vc()
        if slot == "levels":
            ad.presentFromRootViewController_(vc)
        else:
            ad.presentFromRootViewController_userDidEarnRewardHandler_(
                vc, self._block(lambda s=slot: self.results.append(f"{s}|REWARD")))

    def _gone(self, what):
        if self.showing is None:
            return
        slot = self.showing[0]
        self.showing = None
        self.results.append(f"{slot}|{what}")
        self.next_try[slot] = 0
        self._load(slot)                # the next one is ready by the time it is wanted

    def pollResult(self):
        return self.results.pop(0) if self.results else ""

    def privacyOptionsRequired(self):
        try:
            info = _p(ObjCClass("UMPConsentInformation"), "sharedInstance")
            return int(_p(info, "privacyOptionsRequirementStatus")) == UMP_PRIVACY_REQUIRED
        except Exception:
            return False

    def showPrivacyOptions(self):
        ObjCClass("UMPConsentForm").presentPrivacyOptionsFormFromViewController_completionHandler_(
            _root_vc(), self._block(lambda err: self._start_if_allowed(), objc_id))
