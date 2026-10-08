"""Pack exactly what buildozer needs (upload the zip to a Google Colab notebook).

    python tools/make_apk_zip.py            -> holo_apk_source.zip   current configuration -> HOLO_APK_OLUSTURUCU.ipynb
    python tools/make_apk_zip.py --release  -> holo_release_source.zip   Google Play build: tester tools OFF, unlocked level replay,
                                               Play Billing ON, signed AAB                                            -> HOLO_AAB_OLUSTURUCU.ipynb
"""
import os
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RELEASE = "--release" in sys.argv
OUT = os.path.join(ROOT, "holo_release_source.zip" if RELEASE else "holo_apk_source.zip")
SKIP_DIRS = {".venv", "__pycache__", "screenshots", "store_assets", "levelgen", "server", "tools", "legacy", "bin", ".buildozer",
             "build", "dist", "supabase", "docs", ".git", ".github", ".claude", ".codex", ".agents", "node_modules",
             "_upload_tmp", "social", "build_ios", "ios", "store_assets"}
SKIP_EXT = (".zip", ".whl", ".db", ".md", ".ipynb", ".spec.bak", ".corrupt", ".jks", ".keystore", ".aab", ".apk")

files = []
for base, dirs, names in os.walk(ROOT):
    dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith("_")]   # _upload_tmp, _yedek_*, _inspect_* ...
    rel = os.path.relpath(base, ROOT)
    for n in names:
        if (n.startswith("save_data") or n.endswith(SKIP_EXT) or n.startswith("holo-keystore")   # never ship signing secrets
                or ".zip.part" in n or n.endswith(".log")
                or n in ("holo.spec", "render.yaml", "_audit_raw.txt", "_nbdump.txt") or n.startswith("requirements")):
            continue
        p = os.path.join(base, n)
        r = os.path.normpath(os.path.join(rel, n)).replace("\\", "/")
        if r.startswith("levels/") and not ((n.startswith("level") or n == "endless_pool.json") and n.endswith(".json")):
            continue
        if r.endswith(".pyc"):
            continue
        files.append((p, r))
# android_src is only needed once Play Billing is switched on (commented out in buildozer.spec) - it is small, ship it
for base, dirs, names in os.walk(os.path.join(ROOT, "android_src")):
    for n in names:
        p = os.path.join(base, n)
        files.append((p, os.path.relpath(p, ROOT).replace("\\", "/")))

def _release_config():
    import json
    cfg = json.load(open(os.path.join(ROOT, "config.json"), encoding="utf-8"))
    for k in ("test_tools", "dev_unlock_all", "dev_free_purchases"):
        cfg.pop(k, None)
    cfg["billing"] = "android"
    cfg["ads_test"] = "--ads-test" in sys.argv          # Google's sample ads (for builds the developer plays himself)
    return json.dumps(cfg, indent=2).encode("utf-8")


def _release_spec():
    spec = open(os.path.join(ROOT, "buildozer.spec"), encoding="utf-8").read()
    spec = spec.replace("# android.gradle_dependencies", "android.gradle_dependencies").replace("# android.add_src", "android.add_src")
    spec = spec.replace("# android.meta_data = com.google.android.gms.ads", "android.meta_data = com.google.android.gms.ads")
    if "release_artifact" not in spec:
        spec = spec.replace("[app]\n", "[app]\nandroid.release_artifact = aab\n", 1)
    return spec.encode("utf-8")


with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
    for p, r in sorted(set(files), key=lambda x: x[1]):
        if RELEASE and r == "config.json":
            z.writestr(r, _release_config())
        elif RELEASE and r == "buildozer.spec":
            z.writestr(r, _release_spec())
        else:
            z.write(p, r)
size = os.path.getsize(OUT) / 1e6
print(f"{OUT}: {len(set(files))} files, {size:.1f} MB" + ("  [RELEASE: tester tools off, Play Billing on]" if RELEASE else "  [current config preserved]"))
needed = ["main.py", "holo.py", "sim.py", "endless.py", "levels/endless_pool.json", "buildozer.spec", "config.json", "levels/level1.json", "levels/level100.json", "assets/icon.png", "android_recipes/pygame/__init__.py"]
with zipfile.ZipFile(OUT) as archive:
    missing = [n for n in needed if n not in archive.namelist()]
if missing:
    print("MISSING:", missing)
    sys.exit(1)
