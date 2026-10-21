"""Headless shop layout, section navigation, selection and four-language previews."""
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["HOLO_SAVE_DIR"] = tempfile.mkdtemp(prefix="holo_shop_layout_")
os.environ["HOLO_SERVER"] = "http://127.0.0.1:1"
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pygame
import config
import locales
import shop
import ui
import shop_items as SI
from shop_ui_extra import draw_frame, draw_title_badge
from save_manager import SaveManager

pygame.init()
pygame.display.set_mode((1, 1))
config._CACHE = {"server_url": "http://127.0.0.1:1", "dev_free_purchases": True}
sm = SaveManager()
sm.wallet = None
sm.data["diamonds"] = 750
store = shop.Shop(sm)
screen = ui.ShopScreen(sm, store, lambda: None)
surface = pygame.Surface((ui.VW, ui.VH))
out = ROOT / "screenshots"
out.mkdir(exist_ok=True)


def draw(name=None):
    surface.fill((6, 10, 20))
    screen.draw(surface)
    if name:
        pygame.image.save(surface, str(out / f"shop_redesign_{name}.png"))


def tap(pos):
    screen.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pos))
    cb = screen.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=pos))
    if callable(cb):
        cb()


for lang in ("tr", "en", "de", "es"):
    locales.set_language(lang)
    screen.refresh_texts()
    screen._jump_section(0)
    screen.selected = "inferno_dragon"
    draw(lang)
    assert screen._content() is screen._content(), "list cache must be reused"
    for i in (1, 2, 0):
        balance = sm.diamonds
        tap(screen.nav_buttons[i].rect.center)
        expected = (0, screen._grid_h(), screen._extra_y())[i]
        assert screen._scroll.y == expected, (lang, i, screen._scroll.y, expected)
        assert sm.diamonds == balance, "section navigation must not purchase"
        draw()
    sid, rect = next(iter(screen._feat_rects.items()))
    pos = (rect.centerx, rect.centery + screen.VIEW_Y)
    tap(pos)
    assert screen.selected == sid, "card tap must select the correct skin"
    assert sm.diamonds == 750, "card selection must not purchase"
    for index in (0, len(screen.skins) // 2, len(screen.skins) - 1):
        sid = screen.skins[index]
        screen.select(sid)
        r = screen._card_rect(index)
        assert screen.VIEW_Y <= r.centery - screen._scroll.y + screen.VIEW_Y < ui.VH - 96
        draw()

locales.set_language("tr")
screen.refresh_texts()
screen.selected = "inferno_dragon"
screen._jump_section(1)
draw("diamonds")
screen._jump_section(2)
draw("extras")
# Clean presentation capture; all purchase interaction tests above use DevBilling.
with patch.object(store.billing, "name", "preview"):
    screen._jump_section(0)
    draw("preview")
    sm.data["star_coins"] = 120
    sm.data["shield_stock"] = 2
    sm.data["revive_stock"] = 1
    # Contact sheet from the actual shop surfaces, showing every product family.
    img = screen._content()
    extra_y = screen._extra_y()
    layout = screen.extra._layout()
    parts = [(screen._grid_h(), 355),
             (extra_y + layout["pack_head"], layout["pre_head"] - layout["pack_head"]),
             (extra_y + layout["chest_head"], 390)]
    board = pygame.Surface((ui.VW, sum(h for _, h in parts)))
    offset = 0
    for y, h in parts:
        board.blit(img, (0, offset), pygame.Rect(0, y, ui.VW, h))
        offset += h
    pygame.image.save(board, str(out / "shop_products_preview.png"))
    pre_y = extra_y + layout["pre_head"]
    prestige = img.subsurface(pygame.Rect(0, pre_y, ui.VW, layout["mk_head"] - layout["pre_head"])).copy()
    pygame.image.save(prestige, str(out / "shop_prestige_preview.png"))
    # Selecting a frame/title is separate from purchasing it.
    balance = sm.diamonds
    for group in ("frame_cells", "title_cells"):
        pid, cell = next(iter(layout[group].items()))
        cb = screen.extra.tap(cell.center, 0, lambda sid: None)
        assert callable(cb)
        cb()
        assert screen.extra.item == ("frame" if group == "frame_cells" else "title", pid) and sm.diamonds == balance
    for fid in SI.FRAME:
        for width, height in ((42, 36), (110, 54), (140, 70)):
            probe = pygame.Surface((220, 140))
            probe.fill((17, 23, 38))
            rect = pygame.Rect(20, 20, width, height)
            draw_frame(probe, rect, fid)
            assert probe.get_at(rect.center)[:3] == (17, 23, 38), "frame must not obscure the player's badge"
    cr = layout["chest"]
    callback = screen.extra.tap((cr.right - 170, cr.y + 105), 0, lambda sid: None)
    assert callback == screen.extra._open_chest, "chest action must still target its checkout"
    for lang in ("tr", "en", "de", "es"):
        locales.set_language(lang)
        for tid in SI.TITLE:
            draw_title_badge(surface, pygame.Rect(50, 50, 230, 28), tid, 17)
            draw_title_badge(surface, pygame.Rect(50, 100, 385, 60), tid, 23)
        for stars in (0, 120):
            sm.data["star_coins"] = stars
            screen._content()
    locales.set_language("tr")
store.billing = shop.Billing()
with patch("paths.is_ios", return_value=True):
    screen.refresh_texts()
    screen._jump_section(1)
    draw("no_billing")
    assert not screen.pack_buttons
print("PASS 4 languages, section taps, card selection, scroll-to-skin, list cache and billing-unavailable layout")
