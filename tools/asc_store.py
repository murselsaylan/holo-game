"""App Store Connect product page via the official API (run by .github/workflows/ios-store.yml, where the API key is).

    python tools/asc_store.py            # texts, screenshots, categories, age rating, price, build
    python tools/asc_store.py --submit   # ... and send the version to App Review

Reads store_assets/appstore.json. Needs ASC_KEY_ID, ASC_ISSUER_ID and ASC_KEY_P8 (the .p8 text) in the environment.
Every step prints what it did; a step that fails prints Apple's answer and the script goes on with the next one,
so one run shows everything that is still missing. Exit code 1 if any step failed.
"""
import hashlib
import json
import os
import sys
import time

import jwt
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API = "https://api.appstoreconnect.apple.com"
CFG = json.load(open(os.path.join(ROOT, "store_assets", "appstore.json"), encoding="utf-8"))
APP = CFG["app_id"]
FAILED = []


def token():
    now = int(time.time())
    return jwt.encode({"iss": os.environ["ASC_ISSUER_ID"], "iat": now, "exp": now + 1100, "aud": "appstoreconnect-v1"},
                      os.environ["ASC_KEY_P8"], algorithm="ES256", headers={"kid": os.environ["ASC_KEY_ID"], "typ": "JWT"})


def call(method, path, body=None, ok=(200, 201, 204)):
    r = requests.request(method, API + path, json=body, timeout=60,
                         headers={"Authorization": "Bearer " + token(), "Content-Type": "application/json"})
    if r.status_code not in ok:
        raise RuntimeError(f"{method} {path} -> {r.status_code}: {r.text[:1500]}")
    return r.json() if r.text else {}


def step(name):
    def wrap(fn):
        def run(*a, **k):
            print(f"\n== {name}", flush=True)
            try:
                return fn(*a, **k)
            except Exception as e:
                print("   FAILED:", e, flush=True)
                FAILED.append(name)
        return run
    return wrap


def version():
    r = call("GET", f"/v1/apps/{APP}/appStoreVersions?filter[platform]=IOS&limit=10")
    for v in r["data"]:
        if v["attributes"]["appStoreState"] in ("PREPARE_FOR_SUBMISSION", "DEVELOPER_REJECTED", "REJECTED",
                                                 "METADATA_REJECTED", "WAITING_FOR_REVIEW", "READY_FOR_REVIEW"):
            return v
    raise RuntimeError("no editable iOS version: " + json.dumps([(v["attributes"]["versionString"],
                                                                  v["attributes"]["appStoreState"]) for v in r["data"]]))


def app_info():
    r = call("GET", f"/v1/apps/{APP}/appInfos")
    for i in r["data"]:
        if i["attributes"].get("appStoreState", i["attributes"].get("state")) not in ("READY_FOR_SALE", "READY_FOR_DISTRIBUTION"):
            return i
    return r["data"][0]


@step("version number, copyright")
def set_version(v):
    a = {"copyright": CFG["copyright"]}
    if v["attributes"]["versionString"] != CFG["version"]:
        a["versionString"] = CFG["version"]
    call("PATCH", f"/v1/appStoreVersions/{v['id']}", {"data": {"type": "appStoreVersions", "id": v["id"], "attributes": a}})
    print("   ", a)


@step("version texts per language")
def set_texts(v):
    have = {l["attributes"]["locale"]: l for l in call("GET", f"/v1/appStoreVersions/{v['id']}/appStoreVersionLocalizations")["data"]}
    out = {}
    for loc, m in CFG["locales"].items():
        a = {"description": m["description"], "keywords": m["keywords"], "promotionalText": m["promotional_text"],
             "supportUrl": CFG["support_url"]}
        if loc in have:
            lid = have[loc]["id"]
            call("PATCH", f"/v1/appStoreVersionLocalizations/{lid}",
                 {"data": {"type": "appStoreVersionLocalizations", "id": lid, "attributes": a}})
        else:
            a["locale"] = loc
            lid = call("POST", "/v1/appStoreVersionLocalizations", {"data": {
                "type": "appStoreVersionLocalizations", "attributes": a,
                "relationships": {"appStoreVersion": {"data": {"type": "appStoreVersions", "id": v["id"]}}}}})["data"]["id"]
        out[loc] = lid
        print("   ", loc, "ok")
    return out


@step("app name / subtitle / privacy URL per language")
def set_info_texts(info):
    have = {l["attributes"]["locale"]: l for l in call("GET", f"/v1/appInfos/{info['id']}/appInfoLocalizations")["data"]}
    for loc, m in CFG["locales"].items():
        a = {"subtitle": m["subtitle"], "privacyPolicyUrl": CFG["privacy_url"]}
        if "name" in m:
            a["name"] = m["name"]
        if loc in have:
            lid = have[loc]["id"]
            call("PATCH", f"/v1/appInfoLocalizations/{lid}", {"data": {"type": "appInfoLocalizations", "id": lid, "attributes": a}})
        else:
            a["locale"] = loc
            a.setdefault("name", have[next(iter(have))]["attributes"]["name"] if have else "HOLO")
            call("POST", "/v1/appInfoLocalizations", {"data": {
                "type": "appInfoLocalizations", "attributes": a,
                "relationships": {"appInfo": {"data": {"type": "appInfos", "id": info["id"]}}}}})
        print("   ", loc, a.get("name", have.get(loc, {}).get("attributes", {}).get("name")), "/", a["subtitle"])


@step("categories")
def set_categories(info):
    cats = CFG["categories"]
    rel = {"primaryCategory": {"data": {"type": "appCategories", "id": cats[0]}}}
    for key, cid in zip(("primarySubcategoryOne", "primarySubcategoryTwo"), cats[1:]):
        rel[key] = {"data": {"type": "appCategories", "id": cid}}
    call("PATCH", f"/v1/appInfos/{info['id']}", {"data": {"type": "appInfos", "id": info["id"], "relationships": rel}})
    print("   ", cats)


@step("age rating (no objectionable content -> 4+)")
def set_age(info):
    d = call("GET", f"/v1/appInfos/{info['id']}/ageRatingDeclaration")["data"]
    attrs = {}
    for k, val in d["attributes"].items():
        if k in ("ageRatingOverride", "ageRatingOverrideV2", "koreaAgeRatingOverride", "kidsAgeBand",
                 "developerAgeRatingInfoUrl", "gracRatingClassificationNumber"):
            continue
        if k == "contests":
            attrs[k] = "NONE"
        elif isinstance(val, bool) or k in ("gambling", "unrestrictedWebAccess", "lootBox", "messagingAndChat",
                                            "parentalControls", "ageAssurance", "userGeneratedContent", "advertising",
                                            "healthOrWellnessTopics", "seventeenPlus", "socialMedia",
                                            "socialMediaAgeRestricted"):
            attrs[k] = False
        else:
            attrs[k] = "NONE"
    print("    fields:", sorted(attrs))
    call("PATCH", f"/v1/ageRatingDeclarations/{d['id']}", {"data": {"type": "ageRatingDeclarations", "id": d["id"], "attributes": attrs}})


@step("content rights (no third-party content)")
def set_rights():
    call("PATCH", f"/v1/apps/{APP}", {"data": {"type": "apps", "id": APP,
                                               "attributes": {"contentRightsDeclaration": "DOES_NOT_USE_THIRD_PARTY_CONTENT"}}})


@step("price: free")
def set_price():
    pts = call("GET", f"/v1/apps/{APP}/appPricePoints?filter[territory]=USA&limit=200")["data"]
    free = next(p for p in pts if float(p["attributes"]["customerPrice"]) == 0.0)
    call("POST", "/v1/appPriceSchedules", {
        "data": {"type": "appPriceSchedules", "relationships": {
            "app": {"data": {"type": "apps", "id": APP}},
            "baseTerritory": {"data": {"type": "territories", "id": "USA"}},
            "manualPrices": {"data": [{"type": "appPrices", "id": "${free}"}]}}},
        "included": [{"type": "appPrices", "id": "${free}", "attributes": {"startDate": None},
                      "relationships": {"appPricePoint": {"data": {"type": "appPricePoints", "id": free["id"]}}}}]})
    print("    free from now on")


@step("screenshots")
def set_shots(locs):
    kind = CFG["screenshot_type"]
    for loc, lid in (locs or {}).items():
        folder = os.path.join(ROOT, CFG["locales"][loc]["screens"])
        files = sorted(f for f in os.listdir(folder) if f.endswith(".png"))
        sets = call("GET", f"/v1/appStoreVersionLocalizations/{lid}/appScreenshotSets")["data"]
        sset = next((s for s in sets if s["attributes"]["screenshotDisplayType"] == kind), None)
        if sset is None:
            sset = call("POST", "/v1/appScreenshotSets", {"data": {"type": "appScreenshotSets", "attributes": {
                "screenshotDisplayType": kind}, "relationships": {"appStoreVersionLocalization": {"data": {
                    "type": "appStoreVersionLocalizations", "id": lid}}}}})["data"]
        for old in call("GET", f"/v1/appScreenshotSets/{sset['id']}/appScreenshots")["data"]:
            call("DELETE", f"/v1/appScreenshots/{old['id']}")
        for name in files[:10]:
            blob = open(os.path.join(folder, name), "rb").read()
            shot = call("POST", "/v1/appScreenshots", {"data": {"type": "appScreenshots", "attributes": {
                "fileName": name, "fileSize": len(blob)}, "relationships": {"appScreenshotSet": {"data": {
                    "type": "appScreenshotSets", "id": sset["id"]}}}}})["data"]
            for op in shot["attributes"]["uploadOperations"]:
                part = blob[op["offset"]:op["offset"] + op["length"]]
                h = {x["name"]: x["value"] for x in op.get("requestHeaders", [])}
                r = requests.request(op["method"], op["url"], data=part, headers=h, timeout=120)
                if r.status_code >= 300:
                    raise RuntimeError(f"upload {name}: {r.status_code} {r.text[:300]}")
            call("PATCH", f"/v1/appScreenshots/{shot['id']}", {"data": {"type": "appScreenshots", "id": shot["id"],
                 "attributes": {"uploaded": True, "sourceFileChecksum": hashlib.md5(blob).hexdigest()}}})
            print("   ", loc, name, "uploaded")


@step("build")
def set_build(v):
    r = call("GET", f"/v1/builds?filter[app]={APP}&filter[preReleaseVersion.version]={CFG['version']}"
                    f"&sort=-uploadedDate&limit=5")
    builds = [b for b in r["data"] if b["attributes"].get("processingState") == "VALID"]
    print("    builds of", CFG["version"], [(b["attributes"]["version"], b["attributes"].get("processingState")) for b in r["data"]])
    if not builds:
        raise RuntimeError("no processed build of " + CFG["version"] + " yet")
    b = max(builds, key=lambda b: int(b["attributes"]["version"]))
    call("PATCH", f"/v1/appStoreVersions/{v['id']}/relationships/build", {"data": {"type": "builds", "id": b["id"]}})
    print("    build", b["attributes"]["version"], "attached")


@step("App Review details: no sign-in needed")
def set_review(v):
    d = call("GET", f"/v1/appStoreVersions/{v['id']}/appStoreReviewDetail")["data"]
    call("PATCH", f"/v1/appStoreReviewDetails/{d['id']}", {"data": {"type": "appStoreReviewDetails", "id": d["id"],
         "attributes": {"demoAccountRequired": False}}})
    a = d["attributes"]
    print("    contact:", a.get("contactFirstName"), a.get("contactLastName"), "| email set:", bool(a.get("contactEmail")),
          "| phone set:", bool(a.get("contactPhone")))


@step("submit for review")
def submit(v):
    open_ = call("GET", f"/v1/reviewSubmissions?filter[app]={APP}&filter[platform]=IOS&filter[state]=READY_FOR_REVIEW")["data"]
    sub = open_[0] if open_ else call("POST", "/v1/reviewSubmissions", {"data": {"type": "reviewSubmissions",
          "attributes": {"platform": "IOS"}, "relationships": {"app": {"data": {"type": "apps", "id": APP}}}}})["data"]
    items = call("GET", f"/v1/reviewSubmissions/{sub['id']}/items")["data"]
    if not items:
        call("POST", "/v1/reviewSubmissionItems", {"data": {"type": "reviewSubmissionItems", "relationships": {
            "reviewSubmission": {"data": {"type": "reviewSubmissions", "id": sub["id"]}},
            "appStoreVersion": {"data": {"type": "appStoreVersions", "id": v["id"]}}}}})
    call("PATCH", f"/v1/reviewSubmissions/{sub['id']}", {"data": {"type": "reviewSubmissions", "id": sub["id"],
         "attributes": {"submitted": True}}})
    print("    sent to App Review")


if __name__ == "__main__":
    v = version()
    print("version", v["attributes"]["versionString"], v["attributes"]["appStoreState"])
    info = app_info()
    set_version(v)
    locs = set_texts(v)
    set_info_texts(info)
    set_categories(info)
    set_age(info)
    set_rights()
    set_price()
    set_shots(locs)
    set_build(v)
    set_review(v)
    if "--submit" in sys.argv:
        if FAILED:
            print("\nnot submitting, failed steps:", FAILED)
        else:
            submit(v)
    print("\nFAILED:" if FAILED else "\nALL STEPS OK", FAILED or "")
    sys.exit(1 if FAILED else 0)
