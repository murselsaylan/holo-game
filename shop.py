"""Store layer: premium skins and developer tips ("support the developer").

Money only ever moves through a *billing backend*:

  "none"    the default. Prices are shown but the buy buttons say the store is not open yet.
  "dev"     test mode (config "dev_free_purchases": true): every purchase succeeds instantly, nothing is charged.
  "android" Google Play Billing through the Java bridge in android_src/ (see docs/MONETIZATION.md). Needs a Play developer
            account, products created in the Play Console and a build that includes the bridge.

Entitlements are stored in the save file. That is fine for cosmetics; anyone who edits their save can unlock skins, which
is the normal trade-off for a leaderboard-safe cosmetic store (scores are verified server-side and are not affected).
"""
import os
import sys
import time
import secrets
import webbrowser

import config
import paths
import skin_catalog

# Legendary skins can also be bought with real money (Play products skin_<id>); every shop skin can be bought with diamonds
SKIN_PRICE = {sid: "$4.99" for sid in skin_catalog.premium_ids()}
SKIN_PRICE[skin_catalog.PRESTIGE_TOP] = "$14.99"     # the single most expensive item in the game
SKIN_DIAMOND_COST = skin_catalog.COST

DIAMOND_PACKS = [
    ("pack_100", 100, "$0.99", "100 ELMAS"),
    ("pack_350", 350, "$2.99", "350 ELMAS"),
    ("pack_1000", 1000, "$6.99", "1000 ELMAS"),
    ("pack_2500", 2500, "$14.99", "2500 ELMAS"),
]

SHIELD_COST = 10                     # diamonds for one shield (max 5 in stock)


def skin_product(skin_id):
    return "skin_" + skin_id


# ------------------------------------------------------------------------------------------------- backends
# A backend starts checkouts and reports what happened as events from poll():
#   ("buy", product, token, order)   paid: deliver through the server, then finish(token)
#   ("pending", product)             payment not done yet (Play reports "buy" later, even after a restart)
#   ("fail", product or "_")         cancelled / error before paying
# Nothing is consumed or acknowledged before the HOLO server has verified the token with Google and credited it once.
class Billing:
    name = "none"
    label = ""

    def available(self):
        return False

    def price(self, product_id, default=""):
        return default

    def offer(self, product_id):
        """(price, regular price, percent off) while the product is on sale in the store, else None."""
        return None

    def purchase(self, product_id, account_tag=""):
        return False

    def finish(self, token):
        pass

    def refresh(self):
        pass

    def owned_products(self):
        return []

    def poll(self):
        return []


class DevBilling(Billing):
    """Test backend: pretends the payment worked (never charges anything). The server credits "dev-" tokens only when
    it runs with WALLET_DEV_PURCHASES=1, so this can never create real diamonds on the live server."""
    name = "dev"
    label = "TEST"

    def __init__(self):
        self._events = []

    def available(self):
        return True

    def purchase(self, product_id, account_tag=""):
        self._events.append(("buy", product_id, "dev-" + secrets.token_hex(16), "DEV"))
        return True

    def poll(self):
        ev, self._events = self._events, []
        return ev


class AndroidBilling(Billing):
    """Google Play Billing via org.holo.billing.BillingBridge (android_src/). Test it on an internal-testing track with a
    license-tester account before release."""
    name = "android"

    def __init__(self):
        self._bridge = None
        try:
            from jnius import autoclass   # python-for-android
            activity = autoclass("org.kivy.android.PythonActivity").mActivity
            cls = autoclass("org.holo.billing.BillingBridge")
            self._bridge = cls(activity)
        except Exception as e:
            print("Play Billing bridge unavailable:", e)
            self._bridge = None

    def available(self):
        try:
            return bool(self._bridge and self._bridge.isReady())
        except Exception:
            return False

    def price(self, product_id, default=""):
        try:
            p = self._bridge.getPrice(product_id) if self._bridge else ""
            return p or default
        except Exception:
            return default

    def offer(self, product_id):
        """(price, regular price, percent off) of a running Play Console discount, or None."""
        try:
            raw = str(self._bridge.getOffer(product_id) or "") if self._bridge else ""
        except Exception:
            return None
        parts = raw.split("|")
        if len(parts) == 3 and parts[2].isdigit() and int(parts[2]) > 0:
            return parts[0], parts[1], int(parts[2])
        return None

    def purchase(self, product_id, account_tag=""):
        if not self.available():
            return False
        try:
            self._bridge.buy(product_id, account_tag or "")
            return True
        except Exception as e:
            print("Play purchase error:", e)
            return False

    def finish(self, token):
        try:
            if self._bridge:
                self._bridge.finish(token)
        except Exception as e:
            print("Play finish error:", e)          # stays unfinished -> reported again -> server says dup -> finish again

    def refresh(self):
        try:
            if self._bridge:
                self._bridge.refresh()
        except Exception:
            pass

    def owned_products(self):
        try:
            return [p for p in str(self._bridge.ownedProducts()).split(",") if p] if self._bridge else []
        except Exception:
            return []

    def poll(self):
        out = []
        if not self._bridge:
            return out
        for _ in range(20):
            try:
                res = str(self._bridge.pollResult() or "")
            except Exception:
                break
            if not res:
                break
            if res.startswith("BUY|"):
                parts = res.split("|")
                if len(parts) >= 3 and parts[2]:
                    out.append(("buy", parts[1], parts[2], parts[3] if len(parts) > 3 else ""))
            elif res.startswith("PENDING|"):
                out.append(("pending", res[8:]))
            elif res.startswith("DONE|"):
                pass
            elif res.endswith(":FAIL"):
                out.append(("fail", res[:-5]))
        return out


def make_billing():
    kind = str(config.get("billing", "")).lower()
    if not config.get("release_mode", False) and (config.get("dev_free_purchases", False) or os.environ.get("HOLO_DEV_PURCHASES", "") == "1"):
        return DevBilling()
    if kind == "android" and paths.is_android():
        return AndroidBilling()
    return Billing()


# ------------------------------------------------------------------------------------------------- manager
class Shop:
    def __init__(self, save_manager):
        self.save_mgr = save_manager
        self.billing = make_billing()
        self.message = ""
        self.message_until = 0.0
        self._waiting = {}                  # product -> on_done(ok) of a checkout started from a button
        self._owned_synced = False

    # -- catalog ---------------------------------------------------------------------
    def price_label(self, skin_id):
        return self.billing.price(skin_product(skin_id), SKIN_PRICE.get(skin_id, "$0.99"))

    def diamond_cost(self, skin_id):
        return SKIN_DIAMOND_COST.get(skin_id, 200)

    @staticmethod
    def is_premium(skin_id):
        return skin_id in SKIN_PRICE

    def sale(self, skin_id):
        """(price, regular price, percent off) while this skin's Play product is discounted, else None.
        dev builds can fake one with config "dev_sale_pct" (screenshots / UI tests)."""
        s = self.billing.offer(skin_product(skin_id)) if self.is_premium(skin_id) else None
        if s is None and self.billing.name == "dev" and config.get("dev_sale_pct") and skin_id in skin_catalog.featured_skins()[:1]:
            return "$2.99", SKIN_PRICE.get(skin_id, "$4.99"), int(config.get("dev_sale_pct"))
        return s

    def pack_price(self, pack_id, default):
        return self.billing.price(pack_id, default)

    def owned(self, skin_id):
        return self.save_mgr.is_skin_unlocked(skin_id)

    @property
    def open_for_business(self):
        return self.billing.available()

    # -- actions ---------------------------------------------------------------------
    def _say(self, key, seconds=3.5):
        self.message = key
        self.message_until = time.time() + seconds

    def current_message(self):
        return self.message if time.time() < self.message_until else ""

    def buy_skin(self, skin_id, on_done=None):
        if self.owned(skin_id) or not self.is_premium(skin_id):
            return
        self._checkout(skin_product(skin_id), on_done)

    def _checkout(self, product_id, on_done):
        if not self.billing.available():
            self._say("shop_unavailable")
            return
        if product_id in self._waiting:
            return                                     # this product's checkout is already running
        self._waiting[product_id] = on_done
        if not self.billing.purchase(product_id, self.save_mgr.data.get("account_tag", "")):
            self._waiting.pop(product_id, None)
            self._say("shop_unavailable")

    def buy_skin_with_diamonds(self, skin_id, on_done=None):
        if self.owned(skin_id):
            if on_done:
                on_done(True)
            return True
        cost = self.diamond_cost(skin_id)

        def paid(ok, reason):
            if ok:
                self.save_mgr.grant_skin(skin_id)
                self._say("shop_thanks_skin")
            else:
                self._say("need_online" if reason == "offline" else "not_enough_diamonds")
            if on_done:
                on_done(ok)

        self.save_mgr.spend("skin:" + skin_id, cost, paid)
        return None                                    # the answer arrives through on_done

    def buy_diamonds(self, pack_id, on_done=None):
        if any(p[0] == pack_id for p in DIAMOND_PACKS):
            self._checkout(pack_id, on_done)

    def buy_shield(self, on_done=None):
        """10 diamonds -> one shield in stock (used from the failure screen: 'retry with shield')."""
        if self.save_mgr.shield_stock >= self.save_mgr.SHIELD_STOCK_MAX:
            self._say("shield_full")
            if on_done:
                on_done(False)
            return False
        def paid(ok, reason):
            if ok:
                self.save_mgr.add_shield(1)
                self._say("shield_bought")
            else:
                self._say("need_online" if reason == "offline" else "not_enough_diamonds")
            if on_done:
                on_done(ok)

        self.save_mgr.spend("shield", SHIELD_COST, paid)
        return None                                    # the answer arrives through on_done

    def watch_ad(self, on_done=None):
        if self.save_mgr.can_watch_ad():
            self.save_mgr.record_ad_watched()
            self.save_mgr.earn("ad", secrets.token_hex(12), 3)
            self._say("ad_reward_msg")
            if on_done:
                on_done(True)
            return True
        else:
            rem = self.save_mgr.seconds_until_ad()
            self._say("ad_cooldown_msg")
            if on_done:
                on_done(False)
            return False

    def restore(self):
        """Ask Play for unfinished purchases and the server for everything this account owns."""
        self.billing.refresh()
        if self.save_mgr.wallet is not None:
            self.save_mgr.wallet.wallet_sync()
        self._say("shop_restored")

    def poll(self):
        """Every frame: Play events -> saved as unfinished purchases and sent to the server for delivery."""
        if not self._owned_synced and self.billing.available():
            self._owned_synced = True
            for pid in self.billing.owned_products():  # skins bought and acknowledged by an older version
                if pid.startswith("skin_"):
                    self.save_mgr.grant_skin(pid[len("skin_"):])
            self.billing.refresh()                      # paid but never delivered (app closed, no internet ...)
        for ev in self.billing.poll():
            kind = ev[0]
            if kind == "buy":
                _, pid, token, order = ev
                if self.save_mgr.wallet is None:        # no server in this build: deliver locally (tools / tests)
                    self._deliver_local(pid)
                    self.billing.finish(token)
                    self._done(pid, True)
                    continue
                self.save_mgr.add_iap(pid, token, order)
                self._say("iap_verifying", 8.0)
            elif kind == "pending":
                self._say("iap_pending", 6.0)
            elif kind == "fail":
                pid = ev[1]
                if pid == "_":
                    for p in list(self._waiting):
                        self._done(p, False)
                else:
                    self._done(pid, False)
                self._say("shop_cancelled")

    def purchase_result(self, pid, token, status, body):
        """The server's answer for a purchase: "ok" (credited now or earlier), "rejected" (not a valid purchase),
        "wait" (Google not reachable / payment still pending - kept and retried)."""
        if status == "ok":
            self.billing.finish(token)                   # only now: consume the pack / acknowledge the skin
            skin = (body or {}).get("skin")
            if skin:
                self.save_mgr.grant_skin(skin)
            self._say("shop_thanks_skin" if skin else "shop_thanks_diamonds")
            self._done(pid, True)
        elif status == "rejected":
            self._say("iap_failed", 5.0)
            self._done(pid, False)
        elif pid in self._waiting:
            self._say("iap_verifying", 8.0)

    def _deliver_local(self, pid):
        if pid.startswith("skin_"):
            self.save_mgr.grant_skin(pid[len("skin_"):])
        else:
            pack = next((p for p in DIAMOND_PACKS if p[0] == pid), None)
            if pack:
                self.save_mgr.add_diamonds(pack[1])

    def _done(self, pid, ok):
        cb = self._waiting.pop(pid, None)
        if cb:
            try:
                cb(ok)
            except Exception as e:
                print("shop callback error:", e)
