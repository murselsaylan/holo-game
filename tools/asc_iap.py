"""In-App Purchases in App Store Connect via the API (run by .github/workflows/ios-store.yml on an "iap-*" tag).

    python tools/asc_iap.py            (--reshot: replace the review screenshots too)

Creates whatever is missing of the products the game sells (shop.py: diamond packs, legendary skins, remove_ads) with
their names (tr + en), price, availability in every country and the review screenshot. Safe to run again: existing
products are only completed, never duplicated. Needs the Paid Apps agreement to be active, and the same API key as
asc_store.py. The first products go to App Review together with the next app version.
"""
import hashlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from asc_store import APP, FAILED, ROOT, call, step   # noqa: E402

import requests                                         # noqa: E402

SHOTS = os.path.join(ROOT, "store_assets", "ios_iap")      # tools/make_iap_shots.py: skin.png, packs.png
RESHOT = "--reshot" in sys.argv                            # replace review screenshots that are already there
REVIEW_NOTE = ("Bought in the game's shop (main menu > SHOP). Diamonds are credited by our server after it checks the "
               "transaction with the App Store; skins appear in the SKINS screen; Remove Ads stops the ads between "
               "levels. Restore Purchases is at the bottom of the shop.")


def products():
    """[(product id, type, USD price, {locale: (name, description)})] - names max 30, descriptions max 45 chars."""
    import skin_catalog
    import skins
    import shop
    out = []
    for pid, n, price, _ in shop.DIAMOND_PACKS:
        out.append((pid, "CONSUMABLE", price[1:], {"en-US": (f"{n} Diamonds", f"{n} diamonds for skins, shields, revives"),
                                                   "tr": (f"{n} Elmas", f"Kostüm, kalkan ve can için {n} elmas")}))
    for sid in skin_catalog.premium_ids():
        name = str(skins.SKINS[sid].get("name", sid))[:24]
        out.append((shop.skin_product(sid), "NON_CONSUMABLE", shop.SKIN_PRICE[sid][1:],
                    {"en-US": (f"{name} Skin"[:30], "A legendary skin for your orbs"),
                     "tr": (f"{name} Kostümü"[:30], "Kürelerin için efsanevi bir kostüm")}))
    out.append((shop.REMOVE_ADS, "NON_CONSUMABLE", shop.REMOVE_ADS_PRICE[1:],
                {"en-US": ("Remove Ads", "No more ads between levels"),
                 "tr": ("Reklamları Kaldır", "Bölüm aralarında reklam yok")}))
    return out


def existing():
    out, path = {}, f"/v1/apps/{APP}/inAppPurchasesV2?limit=200"
    while path:
        r = call("GET", path)
        for d in r["data"]:
            out[d["attributes"]["productId"]] = d
        nxt = (r.get("links") or {}).get("next")
        path = nxt.replace("https://api.appstoreconnect.apple.com", "") if nxt else None
    return out


def price_point(iap_id, usd):
    path = f"/v2/inAppPurchases/{iap_id}/pricePoints?filter[territory]=USA&limit=200"
    while path:
        r = call("GET", path)
        for p in r["data"]:
            if abs(float(p["attributes"]["customerPrice"]) - float(usd)) < 0.001:
                return p["id"]
        nxt = (r.get("links") or {}).get("next")
        path = nxt.replace("https://api.appstoreconnect.apple.com", "") if nxt else None
    raise RuntimeError(f"no USA price point {usd}")


_TERR = []


def territories():
    if not _TERR:
        path = "/v1/territories?limit=200"
        while path:
            r = call("GET", path)
            _TERR.extend(t["id"] for t in r["data"])
            nxt = (r.get("links") or {}).get("next")
            path = nxt.replace("https://api.appstoreconnect.apple.com", "") if nxt else None
    return _TERR


def ensure(pid, kind, usd, locs, have):
    @step(f"{pid} ({kind}, ${usd})")
    def run():
        iap = have.get(pid)
        if iap is None:
            iap = call("POST", "/v2/inAppPurchases", {"data": {"type": "inAppPurchases", "attributes": {
                "name": pid, "productId": pid, "inAppPurchaseType": kind, "reviewNote": REVIEW_NOTE,
                "familySharable": False}, "relationships": {"app": {"data": {"type": "apps", "id": APP}}}}})["data"]
            print("    created", iap["id"])
        iid = iap["id"]
        state = iap["attributes"].get("state", "")
        print("    state", state or "new")
        have_locs = {x["attributes"]["locale"]: x for x in call("GET", f"/v2/inAppPurchases/{iid}/inAppPurchaseLocalizations")["data"]}
        for loc, (name, desc) in locs.items():
            if loc in have_locs:
                continue
            call("POST", "/v1/inAppPurchaseLocalizations", {"data": {"type": "inAppPurchaseLocalizations", "attributes": {
                "locale": loc, "name": name, "description": desc[:45]}, "relationships": {"inAppPurchaseV2": {"data": {
                    "type": "inAppPurchases", "id": iid}}}}})
            print("    text", loc, name)
        sched = call("GET", f"/v2/inAppPurchases/{iid}/iapPriceSchedule?include=manualPrices", ok=(200, 404))
        if not (sched.get("data") and (sched["data"].get("relationships", {}).get("manualPrices", {}).get("data"))):
            pp = price_point(iid, usd)
            call("POST", "/v1/inAppPurchasePriceSchedules", {
                "data": {"type": "inAppPurchasePriceSchedules", "relationships": {
                    "inAppPurchase": {"data": {"type": "inAppPurchases", "id": iid}},
                    "baseTerritory": {"data": {"type": "territories", "id": "USA"}},
                    "manualPrices": {"data": [{"type": "inAppPurchasePrices", "id": "${p}"}]}}},
                "included": [{"type": "inAppPurchasePrices", "id": "${p}", "attributes": {"startDate": None},
                              "relationships": {"inAppPurchasePricePoint": {"data": {
                                  "type": "inAppPurchasePricePoints", "id": pp}}}}]})
            print("    price", usd, "USD (other countries: Apple's equivalents)")
        av = call("GET", f"/v2/inAppPurchases/{iid}/inAppPurchaseAvailability", ok=(200, 404))
        if not av.get("data"):
            call("POST", "/v1/inAppPurchaseAvailabilities", {"data": {"type": "inAppPurchaseAvailabilities",
                 "attributes": {"availableInNewTerritories": True}, "relationships": {
                     "inAppPurchase": {"data": {"type": "inAppPurchases", "id": iid}},
                     "availableTerritories": {"data": [{"type": "territories", "id": t} for t in territories()]}}}})
            print("    available in", len(territories()), "countries")
        shot = call("GET", f"/v2/inAppPurchases/{iid}/appStoreReviewScreenshot", ok=(200, 404))
        if shot.get("data") and RESHOT:
            call("DELETE", f"/v1/inAppPurchaseAppStoreReviewScreenshots/{shot['data']['id']}")
            shot = {}
        if not shot.get("data"):
            blob = open(os.path.join(SHOTS, "skin.png" if pid.startswith("skin_") else "packs.png"), "rb").read()
            s = call("POST", "/v1/inAppPurchaseAppStoreReviewScreenshots", {"data": {
                "type": "inAppPurchaseAppStoreReviewScreenshots", "attributes": {"fileName": "shop.png", "fileSize": len(blob)},
                "relationships": {"inAppPurchaseV2": {"data": {"type": "inAppPurchases", "id": iid}}}}})["data"]
            for op in s["attributes"]["uploadOperations"]:
                h = {x["name"]: x["value"] for x in op.get("requestHeaders", [])}
                r = requests.request(op["method"], op["url"], data=blob[op["offset"]:op["offset"] + op["length"]],
                                     headers=h, timeout=120)
                if r.status_code >= 300:
                    raise RuntimeError(f"screenshot upload {r.status_code} {r.text[:300]}")
            call("PATCH", f"/v1/inAppPurchaseAppStoreReviewScreenshots/{s['id']}", {"data": {
                "type": "inAppPurchaseAppStoreReviewScreenshots", "id": s["id"],
                "attributes": {"uploaded": True, "sourceFileChecksum": hashlib.md5(blob).hexdigest()}}})
            print("    review screenshot uploaded")
    run()


def main():
    have = existing()
    print("already in App Store Connect:", sorted(have))
    for pid, kind, usd, locs in products():
        ensure(pid, kind, usd, locs, have)
    print("\nstates:", {k: v["attributes"].get("state") for k, v in existing().items()})
    if FAILED:
        print("\nFAILED:", FAILED)
        sys.exit(1)


if __name__ == "__main__":
    main()
