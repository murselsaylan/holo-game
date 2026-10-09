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


# ---------------------------------------------------------------------------------------------- AdMob (ads.py)
ADMOB_ZIP = "https://dl.google.com/googleadmobadssdk/googlemobileadssdkios.zip"
# Google's SKAdNetwork ids (developers.google.com/admob/ios/quick-start - "Update your Info.plist")
SKADNETWORK_IDS = """cstr6suwn9 4fzdc2evr5 2fnua5tdw4 ydx93a7ass p78axxw29g v72qych5uu ludvb6z3bs cp8zw746q7 3sh42y64q3
c6k4g5qg8m s39g8k73mm wg4vff78zm 3qy4746246 f38h382jlk hs6bdukanm mlmmfzh3r3 v4nxqhlyqp wzmmz9fp6w su67r6k2v3 yclnxrl5pm
t38b2kh725 7ug5zh24hu gta9lk7p23 vutu7akeur y5ghdn5j9k v9wttpbfk9 n38lu8286q 47vhws6wlr kbd757ywx3 9t245vhmpl a2p9lx4jpn
22mmun2rn5 44jx6755aq k674qkevps 4468km3ulz 2u9pt9hc89 8s468mfl3y klf5c3l5u5 ppxm28t8ap kbmxgpxpgc uw77j35x4d 578prtvx9j
4dzt52r2t5 tl55sbb4fm c3frkrj4fj e5fvkxwrpn 8c4e2ghe7u 3rd42ekr43 97r2b46745 3qcr597p9d""".split()


def fetch_admob():
    """Google Mobile Ads SDK + UMP (consent) xcframeworks into the template's Support/ folder. Returns their names."""
    import urllib.request
    import zipfile
    cache = os.path.join(OUT, "admob_sdk.zip")
    if not os.path.isfile(cache):
        os.makedirs(OUT, exist_ok=True)
        with urllib.request.urlopen(ADMOB_ZIP, timeout=300) as r:
            open(cache, "wb").write(r.read())
    names = []
    with zipfile.ZipFile(cache) as z:
        tops = sorted({n.split("/")[1] for n in z.namelist() if n.count("/") >= 2 and n.split("/")[1].endswith(".xcframework")})
        print("AdMob SDK zip:", z.namelist()[0].split("/")[0], tops)
        for top in tops:
            for n in z.namelist():
                parts = n.split("/")
                if len(parts) > 2 and parts[1] == top and not n.endswith("/"):
                    dst = os.path.join(TEMPLATE, "Support", *parts[1:])
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    with z.open(n) as src, open(dst, "wb") as out:
                        out.write(src.read())
            names.append(top)
    # zip extraction loses the symlinks / exec bits some framework layouts use: make binaries executable again
    for base, dirs, files in os.walk(os.path.join(TEMPLATE, "Support")):
        for f in files:
            if base.endswith(".framework") and "." not in f:
                os.chmod(os.path.join(base, f), 0o755)
    return names


def _pbx_id(seed):
    import hashlib
    return hashlib.md5(("holo-" + seed).encode()).hexdigest()[:24].upper()


def _insert_after_block_list(pbx, block_marker, list_key, line):
    i = pbx.index(block_marker)
    j = pbx.index(list_key, i) + len(list_key)
    return pbx[:j] + line + pbx[j:]


def add_xcframework(pbx, name):
    """Links (and, when it is dynamic, embeds) Support/<name> in the app target, like the template's own SDL2."""
    binary = None
    for base, dirs, files in os.walk(os.path.join(TEMPLATE, "Support", name)):
        for f in files:
            if f == name.replace(".xcframework", "") and "simulator" not in base:
                binary = os.path.join(base, f)
    static = bool(binary) and open(binary, "rb").read(8) == b"!<arch>\n"
    fid, bid, eid = _pbx_id(name + ":ref"), _pbx_id(name + ":link"), _pbx_id(name + ":embed")
    pbx = pbx.replace("/* Begin PBXFileReference section */\n", "/* Begin PBXFileReference section */\n"
                      f"\t\t{fid} /* {name} */ = {{isa = PBXFileReference; lastKnownFileType = wrapper.xcframework; "
                      f"name = {name}; path = Support/{name}; sourceTree = \"<group>\"; }};\n", 1)
    build = f"\t\t{bid} /* {name} in Frameworks */ = {{isa = PBXBuildFile; fileRef = {fid} /* {name} */; }};\n"
    if not static:
        build += (f"\t\t{eid} /* {name} in Embed Frameworks */ = {{isa = PBXBuildFile; fileRef = {fid} /* {name} */; "
                  f"settings = {{ATTRIBUTES = (CodeSignOnCopy, RemoveHeadersOnCopy, ); }}; }};\n")
    pbx = pbx.replace("/* Begin PBXBuildFile section */\n", "/* Begin PBXBuildFile section */\n" + build, 1)
    pbx = _insert_after_block_list(pbx, "60796EDF19190F4100A9926B /* Frameworks */ = {", "files = (\n",
                                   f"\t\t\t\t{bid} /* {name} in Frameworks */,\n")
    pbx = _insert_after_block_list(pbx, "60796EE419190F4100A9926B /* Frameworks */ = {", "children = (\n",
                                   f"\t\t\t\t{fid} /* {name} */,\n")
    if not static:
        pbx = _insert_after_block_list(pbx, "6060E7A12AF8BF4400C04AE0 /* Embed Frameworks */ = {", "files = (\n",
                                       f"\t\t\t\t{eid} /* {name} in Embed Frameworks */,\n")
    print(f"linked {name} ({'static' if static else 'dynamic, embedded'})")
    return pbx


def add_admob(pbx, info):
    cfg = json.load(open(os.path.join(ROOT, "config.json"), encoding="utf-8"))
    app_id = ((cfg.get("admob") or {}).get("ios") or {}).get("app_id", "")
    if not app_id or os.environ.get("HOLO_NO_ADMOB"):
        print("AdMob: not added")
        return pbx
    for name in fetch_admob():
        pbx = add_xcframework(pbx, name)
    # -ObjC: load the SDK's categories; the Swift paths: parts of the SDK are Swift, the app target is not
    flags = ('OTHER_LDFLAGS = ("$(inherited)", "-ObjC", );\n\t\t\t\t'
             'LIBRARY_SEARCH_PATHS = ("$(inherited)", "$(SDKROOT)/usr/lib/swift", '
             '"$(TOOLCHAIN_DIR)/usr/lib/swift/$(PLATFORM_NAME)", );\n\t\t\t\t')
    pbx = pbx.replace(f"PRODUCT_BUNDLE_IDENTIFIER = {BUNDLE_ID};", flags + f"PRODUCT_BUNDLE_IDENTIFIER = {BUNDLE_ID};")
    info["GADApplicationIdentifier"] = app_id
    info["SKAdNetworkItems"] = [{"SKAdNetworkIdentifier": f"{x}.skadnetwork"} for x in SKADNETWORK_IDS]
    print("AdMob: app id", app_id)
    return pbx


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
    # SDL links CoreBluetooth for wireless game controllers: App Store Connect wants a purpose string (ITMS-90683),
    # although HOLO never asks for Bluetooth
    info["NSBluetoothAlwaysUsageDescription"] = "HOLO can be played with a Bluetooth game controller."
    info["NSBluetoothPeripheralUsageDescription"] = "HOLO can be played with a Bluetooth game controller."

    pbx_path = os.path.join(TEMPLATE, "pygame-ios.xcodeproj", "project.pbxproj")
    pbx = open(pbx_path, encoding="utf-8").read()
    pbx = re.sub(r"PRODUCT_BUNDLE_IDENTIFIER = [^;]*;", f"PRODUCT_BUNDLE_IDENTIFIER = {BUNDLE_ID};", pbx)
    pbx = re.sub(r'TARGETED_DEVICE_FAMILY = [^;]*;', 'TARGETED_DEVICE_FAMILY = 1;', pbx)      # iPhone only (portrait game)
    pbx = re.sub(r'IPHONEOS_DEPLOYMENT_TARGET = [^;]*;', 'IPHONEOS_DEPLOYMENT_TARGET = 15.0;', pbx)
    pbx = add_admob(pbx, info)
    with open(info_path, "wb") as f:
        plistlib.dump(info, f)
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
    # the launch screen: the template's (white, a small framed picture) -> the game's loading picture over the whole
    # screen on its own dark colour, exactly what the game draws first (HoloGame._boot_tick) - no visible switch
    with open(os.path.join(APP_DIR, "Launch Screen.storyboard"), "w", encoding="utf-8") as f:
        f.write(LAUNCH_STORYBOARD)
    print("configured", APP_NAME, BUNDLE_ID, version.__version__)


LAUNCH_STORYBOARD = """<?xml version="1.0" encoding="UTF-8"?>
<document type="com.apple.InterfaceBuilder3.CocoaTouch.Storyboard.XIB" version="3.0" toolsVersion="32700.99.1234" targetRuntime="iOS.CocoaTouch" propertyAccessControl="none" useAutolayout="YES" launchScreen="YES" useTraitCollections="YES" useSafeAreas="YES" colorMatched="YES" initialViewController="01J-lp-oVM">
    <device id="retina6_1" orientation="portrait" appearance="dark"/>
    <dependencies>
        <deployment identifier="iOS"/>
        <plugIn identifier="com.apple.InterfaceBuilder.IBCocoaTouchPlugin" version="22684"/>
        <capability name="Safe area layout guides" minToolsVersion="9.0"/>
        <capability name="documents saved in the Xcode 8 format" minToolsVersion="8.0"/>
    </dependencies>
    <scenes>
        <scene sceneID="EHf-IW-A2E">
            <objects>
                <viewController id="01J-lp-oVM" sceneMemberID="viewController">
                    <view key="view" contentMode="scaleToFill" id="Ze5-6b-2t3">
                        <rect key="frame" x="0.0" y="0.0" width="414" height="896"/>
                        <autoresizingMask key="autoresizingMask" widthSizable="YES" heightSizable="YES"/>
                        <subviews>
                            <imageView clipsSubviews="YES" userInteractionEnabled="NO" contentMode="scaleAspectFit" image="Splash" translatesAutoresizingMaskIntoConstraints="NO" id="993-d8-iHn">
                                <rect key="frame" x="0.0" y="0.0" width="414" height="896"/>
                            </imageView>
                        </subviews>
                        <viewLayoutGuide key="safeArea" id="Bcu-3y-fUS"/>
                        <color key="backgroundColor" red="0.0392" green="0.0471" blue="0.0706" alpha="1" colorSpace="custom" customColorSpace="sRGB"/>
                        <constraints>
                            <constraint firstItem="993-d8-iHn" firstAttribute="leading" secondItem="Ze5-6b-2t3" secondAttribute="leading" id="FUL-JQ-Kxu"/>
                            <constraint firstItem="993-d8-iHn" firstAttribute="top" secondItem="Ze5-6b-2t3" secondAttribute="top" id="dFF-ek-zRv"/>
                            <constraint firstItem="993-d8-iHn" firstAttribute="trailing" secondItem="Ze5-6b-2t3" secondAttribute="trailing" id="f3h-U5-02m"/>
                            <constraint firstItem="993-d8-iHn" firstAttribute="bottom" secondItem="Ze5-6b-2t3" secondAttribute="bottom" id="kxX-UK-khH"/>
                        </constraints>
                    </view>
                </viewController>
                <placeholder placeholderIdentifier="IBFirstResponder" id="iYj-Kq-Ea1" userLabel="First Responder" sceneMemberID="firstResponder"/>
            </objects>
            <point key="canvasLocation" x="52" y="375"/>
        </scene>
    </scenes>
    <resources>
        <image name="Splash" width="360" height="640"/>
    </resources>
</document>
"""


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
