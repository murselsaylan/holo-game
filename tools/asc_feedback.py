"""TestFlight feedback through the App Store Connect API: testers' crash reports (with the crash log text) and
screenshot feedback (comments). Run by .github/workflows/ios-store.yml on a feedback-* tag; the output goes to the
ci-logs branch.
"""
import json
import os
import sys

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import asc_store as A  # noqa: E402


def get(path):
    r = requests.get(A.API + path, headers={"Authorization": "Bearer " + A.token()}, timeout=60)
    print(f"GET {path} -> {r.status_code}")
    if r.status_code != 200:
        print(r.text[:800])
        return None
    return r.json()


for kind in ("betaFeedbackCrashSubmissions", "betaFeedbackScreenshotSubmissions"):
    print(f"\n===== {kind}")
    d = get(f"/v1/apps/{A.APP}/{kind}?limit=20")
    if not d:
        continue
    for item in d.get("data", []):
        a = item.get("attributes", {})
        keep = {k: a.get(k) for k in ("createdDate", "comment", "email", "deviceModel", "osVersion", "locale",
                                       "appUptimeInMilliseconds", "batteryPercentage", "connectionType", "architecture",
                                       "deviceFamily", "screenWidthInPoints", "screenHeightInPoints", "appPlatform",
                                       "devicePlatform", "pairedAppleWatch", "timeZone", "buildBundleId") if k in a}
        print(json.dumps(keep, ensure_ascii=False))
        if kind == "betaFeedbackCrashSubmissions":
            log = get(f"/v1/betaFeedbackCrashSubmissions/{item['id']}/crashLog")
            if log:
                text = (log.get("data", {}).get("attributes", {}) or {}).get("logText", "")
                print("----- crash log -----")
                print(text[:20000])
        else:
            for s in a.get("screenshots", []) or []:
                print("    screenshot:", s.get("url", "")[:200])
