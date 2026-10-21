"""Preview images of the share cards + the victory screen with its share buttons (headless):
python tools/share_shots.py [out_dir] [lang ...]"""
import os
import sys
import tempfile

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["HOLO_SAVE_DIR"] = tempfile.mkdtemp(prefix="holo_shots_")
os.environ["HOLO_SERVER"] = "http://127.0.0.1:1"

import pygame  # noqa: E402
import holo  # noqa: E402
import locales  # noqa: E402
import share_card  # noqa: E402

out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "store_assets", "share_ui")
langs = sys.argv[2:] or ["tr"]
os.makedirs(out, exist_ok=True)
g = holo.HoloGame(headless=True)
sm = g.save_mgr
sm.data["is_profile_set"] = True
for lang in langs:
    locales.set_language(lang)
    g.on_language_change()
    for variant, level, stars, att in (("record", 42, 3, 1), ("hard", 118, 2, 9), ("weekly", 77, 3, 4)):
        for shape in ("story", "square"):
            p = share_card.make(variant, level, stars, 48210, 31.4, att, size=shape, out_dir=out)
            os.replace(p, os.path.join(out, f"{variant}_{shape}_{lang}.png"))
# the victory screen with the buttons
locales.set_language(langs[0])
g.on_language_change()
g.online.crowd.data = {"wlevel": {"level": 5}, "tiers": []}
g.load_and_play_level(5)
g.sim.won = True
g._on_win()
for _ in range(3):
    g.update(1 / 60.0, (450, 800))
    g.draw()
pygame.image.save(g.frame, os.path.join(out, f"victory_share_{langs[0]}.png"))
print("share buttons:", [s for _, s in g.victory_modal.share_btns])
print("saved to", out)
