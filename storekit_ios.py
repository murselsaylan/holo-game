"""iOS purchases: StoreKit (SKPaymentQueue / SKProductsRequest) through rubicon-objc, behind shop.Billing.

Events (shop.Billing.poll): ("buy", product, "ios:<transactionId>", transactionId) once the App Store has charged -
the HOLO server checks it with Apple (supabase/functions/scores/apple.ts, with the app receipt from receipt()) and only
then finish() closes the transaction. An unfinished transaction is handed to the observer again on the next start,
so a purchase is never lost to a closed app or a missing connection.

StoreKit calls back on the main thread while SDL pumps its events, so plain lists are enough here.
"""
import time

import ctypes

ctypes.CDLL("/System/Library/Frameworks/StoreKit.framework/StoreKit")      # the app binary itself does not link it

from rubicon.objc import NSObject, ObjCClass, ObjCInstance, objc_method
from rubicon.objc.runtime import objc_id

PURCHASING, PURCHASED, FAILED, RESTORED, DEFERRED = range(5)
_store = None


def _p(obj, name):
    v = getattr(obj, name)
    return v() if callable(v) else v


def _items(nsarray):
    return [nsarray.objectAtIndex_(i) for i in range(int(_p(nsarray, "count")))]


class HoloStoreObserver(NSObject):
    """SKPaymentTransactionObserver + SKProductsRequestDelegate."""

    @objc_method
    def paymentQueue_updatedTransactions_(self, queue: objc_id, transactions: objc_id) -> None:
        if _store is not None:
            _store._updated(ObjCInstance(transactions))

    @objc_method
    def paymentQueue_restoreCompletedTransactionsFailedWithError_(self, queue: objc_id, error: objc_id) -> None:
        print("storekit: restore failed")

    @objc_method
    def productsRequest_didReceiveResponse_(self, request: objc_id, response: objc_id) -> None:
        if _store is not None:
            _store._products(ObjCInstance(response))

    @objc_method
    def request_didFailWithError_(self, request: objc_id, error: objc_id) -> None:
        if _store is not None:
            _store._products_failed()


class StoreKit:
    def __init__(self, product_ids):
        global _store
        _store = self
        self.ids = list(product_ids)
        self.products = {}          # id -> SKProduct
        self.prices = {}            # id -> "₺34,99" (the store's own price in the player's currency)
        self.events = []
        self.open = {}              # token -> SKPaymentTransaction waiting for finish()
        self._req = None
        self._tries = 0
        self._next = 0.0
        self.observer = HoloStoreObserver.alloc().init()
        self.queue = _p(ObjCClass("SKPaymentQueue"), "defaultQueue")
        self.queue.addTransactionObserver_(self.observer)
        self.can_pay = bool(_p(ObjCClass("SKPaymentQueue"), "canMakePayments"))
        self.load_products()

    # ------------------------------------------------------------------ products
    def load_products(self):
        if self._req is not None:
            return
        self._tries += 1
        self._next = time.monotonic() + 20.0 * self._tries
        ids = ObjCClass("NSSet").setWithArray_(self.ids)
        self._req = ObjCClass("SKProductsRequest").alloc().initWithProductIdentifiers_(ids)
        self._req.delegate = self.observer
        self._req.start()

    def _products(self, response):
        fmt = ObjCClass("NSNumberFormatter").alloc().init()
        fmt.numberStyle = 2                                   # NSNumberFormatterCurrencyStyle
        for prod in _items(_p(response, "products")):
            pid = str(_p(prod, "productIdentifier"))
            self.products[pid] = prod
            fmt.locale = _p(prod, "priceLocale")
            self.prices[pid] = str(fmt.stringFromNumber_(_p(prod, "price")))
        bad = [str(x) for x in _items(_p(response, "invalidProductIdentifiers"))]
        print(f"storekit: {len(self.products)} products" + (f", unknown {bad}" if bad else ""))
        self._req = None

    def _products_failed(self):
        print("storekit: product request failed")
        self._req = None

    # ------------------------------------------------------------------ the Billing interface
    def ready(self):
        return self.can_pay and bool(self.products)

    def buy(self, pid, account_tag=""):
        prod = self.products.get(pid)
        if prod is None:
            return False
        pay = ObjCClass("SKMutablePayment").paymentWithProduct_(prod)
        if account_tag:
            pay.applicationUsername = account_tag
        self.queue.addPayment_(pay)
        return True

    def _updated(self, transactions):
        for tr in _items(transactions):
            state = int(_p(tr, "transactionState"))
            pid = str(_p(_p(tr, "payment"), "productIdentifier"))
            if state in (PURCHASED, RESTORED):
                tid = str(_p(tr, "transactionIdentifier"))
                token = "ios:" + tid
                self.open[token] = tr
                self.events.append(("buy", pid, token, tid))
            elif state == FAILED:
                self.queue.finishTransaction_(tr)
                self.events.append(("fail", pid))
            elif state == DEFERRED:                           # Ask to Buy: a parent has to approve it
                self.events.append(("pending", pid))

    def finish(self, token):
        tr = self.open.pop(token, None)
        if tr is not None:
            self.queue.finishTransaction_(tr)

    def restore(self):
        self.queue.restoreCompletedTransactions()

    def poll(self):
        if not self.products and self._req is None and self._tries < 8 and time.monotonic() >= self._next:
            self.load_products()
        ev, self.events = self.events, []
        return ev


def receipt():
    """The app's App Store receipt (base64) for the server's check, or ""."""
    try:
        url = _p(_p(ObjCClass("NSBundle"), "mainBundle"), "appStoreReceiptURL")
        data = ObjCClass("NSData").dataWithContentsOfURL_(url) if url is not None else None
        return str(data.base64EncodedStringWithOptions_(0)) if data is not None else ""
    except Exception as e:
        print("storekit: no receipt:", e)
        return ""
