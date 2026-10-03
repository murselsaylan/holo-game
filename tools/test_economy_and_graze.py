import os
import sys
import tempfile
import math

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["HOLO_SAVE_DIR"] = tempfile.mkdtemp(prefix="holo_econ_test_")
os.environ["HOLO_SERVER"] = "http://127.0.0.1:1"
os.environ["HOLO_DEV_PURCHASES"] = "1"

import pygame
import holo
import skins
from sim import Sim, LevelData, SIM_DT, compute_result

fails = []

def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)

# 1. Check new cute premium skins exist
new_skins = ["sakura_fox", "panda_boba", "sugar_puppy", "starlight_chick"]
for s in new_skins:
    check(f"Skin '{s}' in SKINS", s in skins.SKINS)
    check(f"Skin '{s}' marked premium", s in skins.PREMIUM_SKINS)

# 2. Check skins drawing without errors
dummy_surf = pygame.Surface((300, 300), pygame.SRCALPHA)
for s in new_skins:
    sk = skins.SKINS[s]
    skins.draw_tether(dummy_surf, (50, 50), (150, 150), sk, 1.0)
    skins.draw_orb(dummy_surf, (50, 50), 24, sk["color1"], sk["glow1"], False, sk, 1.0)
    skins.draw_orb(dummy_surf, (150, 150), 24, sk["color2"], sk["glow2"], True, sk, 1.0)
check("New skins render cleanly on surface", True)

# 3. Check Diamond Economy in Game and SaveManager
game = holo.HoloGame(headless=True)
sm = game.save_mgr
shop = game.shop

initial_gems = sm.diamonds
check("Initial diamonds defined (>= 20)", initial_gems >= 20)

# Check level clear does NOT award diamonds
gems_before_clear = sm.diamonds
dummy_result = {
    "level_total": 5000, "stars": 3, "time": 12.0, "swaps": 10, "rank": "S+",
}
sm.record_level_clear(1, dummy_result)
check("Clearing level does NOT award diamonds", sm.diamonds == gems_before_clear)

# Check diamond spend and add
sm.add_diamonds(10)
check("Add diamonds works", sm.diamonds == gems_before_clear + 10)
ok = sm.spend_diamonds(15)
check("Spend diamonds works when sufficient", ok and sm.diamonds == gems_before_clear + 10 - 15)
ok_fail = sm.spend_diamonds(9999)
check("Spend diamonds fails when insufficient", not ok_fail)

# 4. Check Shop with Diamonds and Ads
sm.data["diamonds"] = 20
sm.data["last_ad_watch"] = 0.0
ad_ok = shop.watch_ad()
check("Watch ad awards +3 diamonds", ad_ok and sm.diamonds == 23)
ad_spam = shop.watch_ad()
check("Watch ad cooldown blocks immediate repeat", not ad_spam and sm.diamonds == 23)

# Check skin purchase with diamonds
target_skin = "sakura_fox"
cost = shop.diamond_cost(target_skin)
sm.data["diamonds"] = cost - 10
# Insufficient
bought_fail = shop.buy_skin_with_diamonds(target_skin)
check("Cannot buy skin with insufficient diamonds", not bought_fail and not sm.is_skin_unlocked(target_skin))

sm.data["diamonds"] = cost + 20
bought_ok = shop.buy_skin_with_diamonds(target_skin)
check("Can buy skin with sufficient diamonds", bought_ok and sm.is_skin_unlocked(target_skin) and sm.diamonds == 20)

# 5. Check Revive with Diamonds (Time Rewind & Solid Walls)
game.save_mgr.data["howto_seen"] = True
game.load_and_play_level(1)
game.state = "playing"
for _ in range(40):
    game.update_gameplay(1/60.0)
dead_n = game.sim.n
game.sim.dead = True
game.state = "failed"
sm.data["diamonds"] = 25
game.revive_run()
check("Revive deducts 15 diamonds", sm.diamonds == 10)
check("Revive restores sim.dead to False", game.sim.dead == False)
check("Revive rewinds time/step backward", game.sim.n < dead_n)
check("Revive does NOT grant invulnerability (solid walls)", game.sim.invuln == 0.0)
check("Revive sets state back to playing", game.state == "playing")

# 6. Check Anti-Camping Graze Exploit Prevention
# Create a level where an orb starts grazing a horizontal wall
raw_lvl = {
    "id": 999,
    "width": 900, "height": 1800,
    "start": [100.0, 500.0],
    "end": [800.0, 500.0],
    "walls": [[100, 460, 400, 20]],
    "reverse_walls": [],
    "moving_walls": [],
    "lasers": [],
    "spinners": [],
    "chasers": [],
    "shrink": [], "growth": [], "shields": [], "boost": [],
    "stars": [], "barriers": [], "breakables": [],
    "speed": 0.0,  # stationary
    "par_time": 10.0, "par_swaps": 10
}
lvl_data = LevelData(raw_lvl)
sim = Sim(lvl_data)
# Place orb 0 right in graze zone (wall hit at r+7, not at r)
# Wall is at y=460..480. Orb r=14. At y=495, dist to wall bottom is 15 (14 < 15 < 21).
sim.orbs[0].x = 150.0
sim.orbs[0].y = 495.0
sim.orbs[1].x = 150.0
sim.orbs[1].y = 615.0

# Step physics
sim.near_cool = 0.0
sim.step()
initial_graze_count = sim.near_count
check("First graze awarded", initial_graze_count == 1)

# Now tick 100 times with near_cool forced to 0
for _ in range(100):
    sim.near_cool = 0.0
    sim.step()

check("Stationary orb DOES NOT farm additional grazes", sim.near_count == 1)

# Now move the orb forward by 80px (cell changes and dist >= 45px)
sim.orbs[0].x = 235.0
sim.near_cool = 0.0
sim.step()
check("Graze awarded after moving >= 45px", sim.near_count == 2)

if fails:
    print(f"\nFAILED {len(fails)} checks: {fails}")
    sys.exit(1)
else:
    print("\nALL ECONOMY & GRAZE TESTS PASSED!")
    sys.exit(0)
