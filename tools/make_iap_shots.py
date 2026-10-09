"""App Review screenshots for the In-App Purchases (tools/asc_iap.py): the iOS shop with StoreKit prices.

    python tools/make_iap_shots.py

store_assets/ios_iap/skin.png   a legendary skin selected: its App Store price button
store_assets/ios_iap/packs.png  the bottom of the list: diamond packs and Remove Ads
"""
import os
import sys
import tempfile

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["HOLO_SAVE_DIR"] = tempfile.mkdtemp(prefix="holo_iapshots_")
os.environ["HOLO_SERVER"] = "http://127.0.0.1:1"
PANEL = (1290, 2796)

import pygame  # noqa: E402
import paths  # noqa: E402
import safe_area  # noqa: E402

paths.is_mobile = lambda: True
paths.is_ios = lambda: True
safe_area.insets_px = lambda h: (0, 0)
pygame.init()


class _Panel:
    current_w, current_h = PANEL


pygame.display.Info = lambda: _Panel()
import holo  # noqa: E402
import locales  # noqa: E402
import shop as shop_mod  # noqa: E402
import skin_catalog as C  # noqa: E402


class StorePrices(shop_mod.Billing):
    """What IOSBilling shows once the App Store answered (US prices)."""
    name = "ios"

    def available(self):
        return True


OUT = os.path.join(ROOT, "store_assets", "ios_iap")
os.makedirs(OUT, exist_ok=True)
g = holo.HoloGame(headless=True)
sm = g.save_mgr
sm.data.update(is_profile_set=True, player_name="NOVA", player_country="US", howto_seen=True)
sm.language = "en"
locales.set_language("en")
g.on_language_change()
sm.data["diamonds"] = 640
g.shop.billing = StorePrices()


class AdsShown:
    """The remove-ads row needs ads in the build."""
    def available(self, slot):
        return False

    def available_any(self):
        return True

    def poll(self):
        pass


g.ads = g.shop_ui.ads = AdsShown()
g.toasts = []


def frames(n=4):
    for _ in range(n):
        g.update(1 / 60.0, (450, 900))
        g.draw()


def save(name):
    g.toasts = []
    f = g.frame
    out = pygame.transform.smoothscale(f, PANEL) if f.get_size() != PANEL else f
    pygame.image.save(out, os.path.join(OUT, name))
    print("saved", name, f.get_size())


g.open_shop(top=True)
ui = g.shop_ui
legend = C.premium_ids()[0]
ui.selected = legend
frames()
save("skin.png")
ui._scroll.y = float(max(0, ui._content_h() - ui._view_h()))
ui._scroll.vel = 0.0
frames()
save("packs.png")
