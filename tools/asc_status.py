"""Where the app stands in App Store Connect (run by .github/workflows/ios-store.yml on a "status-*" tag): every iOS
version with its state, the review submissions, the newest builds and the In-App Purchases. Reads only."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from asc_store import APP, call   # noqa: E402

for v in call("GET", f"/v1/apps/{APP}/appStoreVersions?filter[platform]=IOS&limit=5")["data"]:
    a = v["attributes"]
    print("version", a["versionString"], a["appStoreState"], a.get("appVersionState", ""), a.get("createdDate", ""))
for s in call("GET", f"/v1/reviewSubmissions?filter[app]={APP}&limit=5")["data"]:
    a = s["attributes"]
    print("review submission", s["id"], a.get("state"), a.get("submittedDate"))
for b in call("GET", f"/v1/builds?filter[app]={APP}&sort=-uploadedDate&limit=4")["data"]:
    a = b["attributes"]
    print("build", a["version"], a["processingState"], a["uploadedDate"])
iaps = call("GET", f"/v1/apps/{APP}/inAppPurchasesV2?limit=200")["data"]
states = {}
for i in iaps:
    states.setdefault(i["attributes"].get("state"), []).append(i["attributes"]["productId"])
print("in-app purchases:", {k: len(v) for k, v in states.items()}, states if len(states) > 1 else "")
