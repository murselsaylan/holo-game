"""1.0.9 r3 ads: an interstitial after every endless climb, a failed daily try for a rewarded video, the Star Chest for a
rewarded video. The ad SDK and the server are stubbed; this checks the game's wiring."""
import os
import sys
import tempfile

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ.setdefault("HOLO_SERVER", "http://127.0.0.1:1")
os.environ.setdefault("HOLO_SAVE_DIR", tempfile.mkdtemp(prefix="holo_test_"))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
import pygame  # noqa: E402
import holo  # noqa: E402
import ui  # noqa: E402

fails = 0


def check(name, ok):
    global fails
    fails += not ok
    print(("PASS " if ok else "FAIL ") + name)


g = holo.HoloGame(headless=True)
g._present = lambda: None
shown = []
g.ads.available = lambda slot: True
g.ads.show = lambda slot, on_reward=None, on_close=None: shown.append((slot, on_reward, on_close)) or True

# ---- 1. endless: every climb owes an interstitial (before: only every 10th finished level)
sm = g.save_mgr
sm.data["no_ads"] = False
g._ad_due = False
sm.data.update(is_profile_set=True, player_name="T", player_country="TR", howto_seen=True)
for lv in range(1, 141):
    sm.stats[str(lv)] = {"stars": 3, "best_score": 1000}
g.menu_ui.build()
check("endless opens", g.open_endless())
g.online.submit_endless = lambda *a, **k: None
g._endless_over()
check("a climb ends -> an ad is owed", g._ad_due is True)
shown.clear()
g._after_ad(lambda: None)
check("retry shows the interstitial first", [s[0] for s in shown] == ["levels"])
g._ad_due = False

# ---- 2. daily level: a failed try offers an ad, the server gives the try back, the level restarts
g.state = "playing"
g.daily_run = {"level": 105}
g._show_daily_result(False)
m = g.daily_modal
check("failed daily result carries the ad offer", m is not None and m.ad_offer is not None and m._ad_on())
calls = []


def fake_retry(cb):
    calls.append("retry")
    cb({"ok": True, "retries_left": 1})


g.online.ranked.daily_retry = fake_retry
started = []
g._start_daily = lambda level: started.append(level)
shown.clear()
act = m.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=m.btn_ad.rect.center, button=1))
act = m.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=m.btn_ad.rect.center, button=1))
check("the ad button returns its callback", callable(act))
act()
check("a rewarded ad was shown", [s[0] for s in shown] == ["continue"])
shown[0][1]()                                   # the ad was watched
check("server asked for the try back", calls == ["retry"])
check("the daily level restarts", started == [105] and g.daily_modal is None and g._daily_retries_left == 1)
g.daily_run = {"level": 105}
g._daily_retries_left = 0
g._show_daily_result(False)
check("no retries left -> no ad button", not g.daily_modal._ad_on())
g._show_daily_result(True)
check("a cleared run has no ad offer", g.daily_modal.ad_offer is None)

# ---- 3. Star Chest for a video
ex = g.shop_ui.extra
acts = []


class FakeClient:
    view = {"chest": {"left": 0, "cost": 40, "opened": 5, "ad_left": 2}, "market": [], "packs": {"left": {}}, "week": 1}
    state = {"view": "ok"}

    def act(self, op, arg, cb):
        acts.append(op)
        cb({"ok": True, "reward": {"kind": "gems", "payload": 30}, "balance": 100, "stars": 0})

    def refresh(self, *a, **k):
        pass


ex.client = FakeClient()
check("ad chest is on when a video is ready and ad_left > 0", ex._chest_ad_on())
ex.ad_ready = lambda: False
check("...and off without a video", not ex._chest_ad_on())
ex.ad_ready = lambda: True
FakeClient.view["chest"]["ad_left"] = 0
check("...and off when the day's ad chests are used", not ex._chest_ad_on())
FakeClient.view["chest"]["ad_left"] = 2
watched = []
ex.watch_ad = lambda cb: watched.append(cb)
ex._open_chest_ad()
check("the video is asked for before the chest opens", len(watched) == 1 and ex.anim is None and not acts)
watched[0]()                                     # watched to the end
check("then the server opens the chest (chestad)", acts == ["chestad"] and ex.anim is not None and ex.anim["reward"]["kind"] == "gems")
# the layout: both buttons inside the chest card, not overlapping
L = ex._layout()
r = L["chest"]
b, ab = ex._chest_button(r), ex._chest_ad_button(r)
check("buttons inside the card and apart", r.contains(b) and r.contains(ab) and not b.colliderect(ab))
print("FAILS:", fails)
sys.exit(1 if fails else 0)
