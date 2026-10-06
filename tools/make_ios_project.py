"""Builds the iOS Xcode project (pygame-ios template: Python 3.13 + pygame-ce, BeeWare's iOS support).

    python tools/make_ios_project.py [template.zip]      -> build_ios/HOLO/pygame-ios-template/pygame-ios.xcodeproj

Needs `pip install pygame-ios requests`. Without a template zip the matching one is downloaded from GitHub.
The Xcode build itself needs macOS (.github/workflows/ios.yml runs it on GitHub's Mac machines and boots the result in
the iOS simulator). What this script does:
  1. stages the game files (same selection as the Android release, billing off: no StoreKit yet)
  2. runs the pygame-ios CLI (template + game files, main.py becomes the package's __main__.py)
  3. installs certifi next to pygame (HTTPS to the ranking server)
  4. names the app: HOLO, com.hologame.holo, version from version.py, portrait only, the game's icon and splash
"""
import json
import os
import plistlib
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

PYGAME_CE = "2.5.6"                       # a version pygame-ios ships a template for (patches/pygame-ce.json)
BUNDLE_ID = "com.hologame.holo"
APP_NAME = "HOLO"
OUT = os.path.join(ROOT, "build_ios")
STAGE = os.path.join(OUT, "HOLO")
TEMPLATE = os.path.join(STAGE, "pygame-ios-template")
APP_DIR = os.path.join(TEMPLATE, "pygame-ios")

SKIP_DIRS = {".venv", "__pycache__", "screenshots", "store_assets", "levelgen", "server", "tools", "legacy", "bin",
             ".buildozer", "build", "build_ios", "dist", "supabase", "docs", ".git", ".github", ".claude", ".codex",
             ".agents", "node_modules", "social", "android_src", "android_optional", "android_recipes"}
SKIP_EXT = (".zip", ".whl", ".db", ".md", ".ipynb", ".spec", ".bak", ".corrupt", ".jks", ".keystore", ".aab", ".apk",
            ".log", ".pyc", ".bat", ".ps1", ".mp4", ".txt", ".html", ".xml", ".ico")


def stage():
    shutil.rmtree(STAGE, ignore_errors=True)
    os.makedirs(STAGE)
    n = 0
    for base, dirs, names in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith((".", "_"))]
        rel = os.path.relpath(base, ROOT)
        for name in names:
            r = os.path.normpath(os.path.join(rel, name)).replace("\\", "/")
            if name.startswith(("save_data", "holo-keystore", "requirements", ".")) or name.endswith(SKIP_EXT):
                continue
            if r.startswith("levels/") and not ((name.startswith("level") or name == "endless_pool.json")
                                                and name.endswith(".json")):
                continue
            if "/" not in r and not name.endswith((".py", ".json")):
                continue                                  # loose top-level files (spec, notebooks, ...)
            dst = os.path.join(STAGE, r)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(os.path.join(base, name), dst)
            n += 1
    cfg = json.load(open(os.path.join(ROOT, "config.json"), encoding="utf-8"))
    for k in ("test_tools", "dev_unlock_all", "dev_free_purchases"):
        cfg.pop(k, None)
    cfg["billing"] = ""                                   # no StoreKit yet: real-money items show "soon"
    cfg["release_mode"] = True
    with open(os.path.join(STAGE, "config.json"), "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
    print("staged", n, "files")


TEMPLATE_URL = ("https://github.com/seekerluke/pygame-ios-templates/releases/download/v0.0.3/"
                f"pygame-ios-template-{PYGAME_CE}.zip")


def run_cli(template_zip):
    # a pinned template, downloaded directly: the CLI's own lookup asks the GitHub API for the latest release, which is
    # rate-limited on shared CI machines (403) - and a pinned version can't change under us either
    if not template_zip:
        template_zip = os.path.join(OUT, f"pygame-ios-template-{PYGAME_CE}.zip")
        if not os.path.isfile(template_zip):
            import urllib.request
            print("downloading", TEMPLATE_URL)
            urllib.request.urlretrieve(TEMPLATE_URL, template_zip + ".part")
            os.replace(template_zip + ".part", template_zip)
    args = [sys.executable, "-m", "pygame_ios", STAGE, "main.py", PYGAME_CE, os.path.abspath(template_zip)]
    subprocess.run(args, check=True)


def add_packages():
    for plat in ("iphoneos", "iphonesimulator"):
        target = os.path.join(APP_DIR, f"app_packages.{plat}")
        subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "--no-deps", "--upgrade", "--target", target,
                        "certifi"], check=True)
        # numpy ships with the template but the game never imports it: ~40 MB less in the app
        for extra in os.listdir(target):
            if extra.startswith("numpy"):
                shutil.rmtree(os.path.join(target, extra), ignore_errors=True)
        # meson build leftovers inside the pygame-ce package (object files, static libs, *.dylib.p folders):
        # the App Store export refuses to sign them ("operation inapplicable ... for this type of code")
        removed = 0
        for base, dirs, files in os.walk(target, topdown=True):
            for d in [d for d in dirs if d.endswith(".p")]:
                shutil.rmtree(os.path.join(base, d), ignore_errors=True)
                dirs.remove(d)
                removed += 1
            for f in files:
                if f.endswith((".o", ".a", ".pyx", ".pxd", ".c", ".h")) or f == "meson.build":
                    os.remove(os.path.join(base, f))
                    removed += 1
        print("removed", removed, "build leftovers from", os.path.basename(target))


def configure():
    import version
    info_path = os.path.join(APP_DIR, "pygame-ios-Info.plist")
    with open(info_path, "rb") as f:
        info = plistlib.load(f)
    info["CFBundleDisplayName"] = APP_NAME
    info["CFBundleShortVersionString"] = version.__version__
    info["CFBundleVersion"] = version.__version__
    info["UISupportedInterfaceOrientations"] = ["UIInterfaceOrientationPortrait"]
    info["UISupportedInterfaceOrientations~ipad"] = ["UIInterfaceOrientationPortrait",
                                                     "UIInterfaceOrientationPortraitUpsideDown"]
    info["UIStatusBarHidden"] = True
    info["UIApplicationSupportsIndirectInputEvents"] = True     # iPad trackpad / mouse taps
    info["UIViewControllerBasedStatusBarAppearance"] = False
    info["ITSAppUsesNonExemptEncryption"] = False       # HTTPS only (exempt)
    with open(info_path, "wb") as f:
        plistlib.dump(info, f)

    pbx_path = os.path.join(TEMPLATE, "pygame-ios.xcodeproj", "project.pbxproj")
    pbx = open(pbx_path, encoding="utf-8").read()
    pbx = re.sub(r"PRODUCT_BUNDLE_IDENTIFIER = [^;]*;", f"PRODUCT_BUNDLE_IDENTIFIER = {BUNDLE_ID};", pbx)
    pbx = re.sub(r'TARGETED_DEVICE_FAMILY = [^;]*;', 'TARGETED_DEVICE_FAMILY = 1;', pbx)      # iPhone only (portrait game)
    pbx = re.sub(r'IPHONEOS_DEPLOYMENT_TARGET = [^;]*;', 'IPHONEOS_DEPLOYMENT_TARGET = 15.0;', pbx)
    # unsigned archive (App Store signature comes at export): the template's "Sign Python Binary Modules" phase
    # would run codesign with an empty identity and fail - fall back to an ad-hoc signature, replaced at export
    pbx = pbx.replace('--sign \\\"$EXPANDED_CODE_SIGN_IDENTITY\\\"', '--sign \\\"${EXPANDED_CODE_SIGN_IDENTITY:--}\\\"')
    open(pbx_path, "w", encoding="utf-8").write(pbx)
    _write_scheme(pbx)

    import pygame
    assets = os.path.join(APP_DIR, "Images.xcassets")
    icon = pygame.image.load(os.path.join(ROOT, "assets", "icon.png"))
    flat = pygame.Surface((1024, 1024))                 # App Store icons must not have transparency
    flat.fill((10, 12, 18))
    flat.blit(pygame.transform.smoothscale(icon, (1024, 1024)), (0, 0))
    pygame.image.save(flat, os.path.join(assets, "AppIcon.appiconset", "pygame_ce_powered.png"))
    splash = pygame.image.load(os.path.join(ROOT, "assets", "presplash.png"))
    splash_dir = os.path.join(assets, "Splash.imageset")
    for name in os.listdir(splash_dir):
        if name.endswith(".png"):
            pygame.image.save(splash, os.path.join(splash_dir, name))
    print("configured", APP_NAME, BUNDLE_ID, version.__version__)


def _write_scheme(pbx):
    """A shared scheme, so `xcodebuild archive -scheme pygame-ios` works on a machine that never opened the project."""
    m = re.search(r"(\w{24}) /\* pygame-ios \*/ = \{\s*isa = PBXNativeTarget;", pbx)
    if not m:
        print("scheme: target id not found")
        return
    ref = (f'<BuildableReference BuildableIdentifier = "primary" BlueprintIdentifier = "{m.group(1)}" '
           'BuildableName = "pygame-ios.app" BlueprintName = "pygame-ios" ReferencedContainer = "container:pygame-ios.xcodeproj">'
           '</BuildableReference>')
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n<Scheme LastUpgradeVersion = "1600" version = "1.7">\n'
           '<BuildAction parallelizeBuildables = "YES" buildImplicitDependencies = "YES"><BuildActionEntries>'
           '<BuildActionEntry buildForTesting = "YES" buildForRunning = "YES" buildForProfiling = "YES" buildForArchiving = "YES" '
           f'buildForAnalyzing = "YES">{ref}</BuildActionEntry></BuildActionEntries></BuildAction>\n'
           f'<LaunchAction buildConfiguration = "Debug"><BuildableProductRunnable runnableDebuggingMode = "0">{ref}'
           '</BuildableProductRunnable></LaunchAction>\n'
           '<ArchiveAction buildConfiguration = "Release" revealArchiveInOrganizer = "YES"></ArchiveAction>\n</Scheme>\n')
    d = os.path.join(TEMPLATE, "pygame-ios.xcodeproj", "xcshareddata", "xcschemes")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "pygame-ios.xcscheme"), "w", encoding="utf-8") as f:
        f.write(xml)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    stage()
    run_cli(sys.argv[1] if len(sys.argv) > 1 else None)
    add_packages()
    configure()
    print("Xcode project:", os.path.join(TEMPLATE, "pygame-ios.xcodeproj"))
