[app]
title = HOLO
package.name = holo
package.domain = com.hologame

source.dir = .
source.include_exts = py,png,wav,ttf,json,txt
source.include_patterns = assets/*,assets/*/*,levels/level*.json,config.json
source.exclude_dirs = .venv,__pycache__,screenshots,levelgen,server,tools,legacy,bin,.buildozer,_upload_tmp,supabase,social,_yedek_menu_intro,_yedek_wallet
source.exclude_patterns = _inspect*/*,_yedek*/*,save_data*.json,levels/_*.json,*.db,*.md,holo-keystore*,*/holo-keystore*,*.jks,*.keystore

# version comes from version.py (the in-game footer shows the same string)
version.regex = __version__ = ["'](.*)["']
version.filename = %(source.dir)s/version.py
# Play only needs the build number (versionCode) to keep rising; 5.1.0/5.1.1 went up as 102450100/102450101.
# The name users see restarts at 1.x - bump both for every Play upload.
android.numeric_version = 102450112
requirements = python3==3.11.9,hostpython3==3.11.9,pygame==2.6.1,pyjnius,certifi

icon.filename = %(source.dir)s/assets/icon.png
presplash.filename = %(source.dir)s/assets/presplash.png
# Adaptive launcher icon: crisp on every launcher mask and on the Android 12+ system splash (which shrinks a
# plain square icon into a small blurry circle - the "low quality logo" before the game starts)
icon.adaptive_foreground.filename = %(source.dir)s/assets/icon_fg.png
icon.adaptive_background.filename = %(source.dir)s/assets/icon_bg.png
android.presplash_color = #0a0c12

orientation = portrait
fullscreen = 1
android.permissions = INTERNET,VIBRATE,POST_NOTIFICATIONS,com.google.android.gms.permission.AD_ID
android.api = 36
android.minapi = 24
android.ndk = 28c
android.ndk_api = 24
android.archs = arm64-v8a, armeabi-v7a
# Google auto backup of the save file, restored when the game is reinstalled on the same Google account
android.allow_backup = True
android.backup_rules = backup_rules.xml
android.accept_sdk_license = True

# --- Google Play store (paid skins / tips): enable ONLY after the Play Console setup in docs/MONETIZATION.md ---
# (Play Billing + "Sign in with Google" through Credential Manager, for account recovery)
# android.gradle_dependencies = com.android.billingclient:billing:8.3.0, androidx.credentials:credentials:1.3.0, androidx.credentials:credentials-play-services-auth:1.3.0, com.google.android.libraries.identity.googleid:googleid:1.1.1, androidx.work:work-runtime:2.10.0, com.google.android.gms:play-services-ads:24.4.0, com.google.android.ump:user-messaging-platform:3.1.0, com.google.guava:guava:33.3.1-android, com.google.android.play:review:2.0.2
android.enable_androidx = True
# android.add_src = android_src
# AdMob app id (ads.py / android_src/org/holo/ads): the ads SDK ends the app at start without it, so it is switched on
# together with the gradle dependencies above (tools/make_apk_zip.py --release)
# android.meta_data = com.google.android.gms.ads.APPLICATION_ID=ca-app-pub-2665053543428530~7934980621

# python-for-android's SDL2 bootstrap runs main.py; SDL maps touches to mouse events, which the game uses.
p4a.bootstrap = sdl2
p4a.local_recipes = ./android_recipes

[buildozer]
log_level = 2
warn_on_root = 0
