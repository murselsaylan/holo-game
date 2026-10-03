"""Account recovery through Google - the game side, with a fake account chooser and fake server answers.

    python tools/google_ui_test.py

(The real chooser only exists on a phone; the server side is tested by supabase/functions/scores/tests/google_link_test.ts.)
"""
import os
import sys
import tempfile

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["HOLO_SAVE_DIR"] = tempfile.mkdtemp(prefix="holo_google_")
os.environ["HOLO_SERVER"] = "http://127.0.0.1:1"

import holo  # noqa: E402
import ui  # noqa: E402

ok = True


def check(name, cond, extra=""):
    global ok
    ok &= bool(cond)
    print(("PASS " if cond else "FAIL ") + name, extra)


class FakeAuth:
    def __init__(self, answer):
        self.answer, self.pending = answer, False

    def available(self):
        return True

    def request(self, only_authorized=False):
        self.pending = True
        return True

    def poll(self):
        if not self.pending:
            return None
        self.pending = False
        return self.answer


g = holo.HoloGame(headless=True)
sm = g.save_mgr
sm.data.update(is_profile_set=True, player_name="NOVA", player_country="TR")
old_id = sm.player_id


def frames(n):
    for _ in range(n):
        g.update(1 / 60.0, (450, 900))
        g.draw()


# link
g.open_profile("menu")
g.google_auth = FakeAuth(("ok", "TOKEN-A"))
sent = {}
g.online.google_link = lambda tok: (sent.setdefault("link", tok), setattr(g.online, "google", {"state": "ok", "mode": "link",
                                                                                                "email": "pi***r@gmail.com"}))
g.open_recovery("link")
check("modal opens", isinstance(g.recovery_modal, ui.GoogleModal) and g.state == "recovery")
frames(3)
check("token goes to the server", sent.get("link") == "TOKEN-A")
check("linked address saved", sm.data.get("google_email") == "pi***r@gmail.com")
check("profile button shows the account", "pi***r@gmail.com" in g.profile_modal.btn_code.text)
g.close_recovery()

# cancelled chooser
g.google_auth = FakeAuth(("fail", "GetCredentialCancellationException"))
g.open_recovery("link")
frames(2)
check("cancel is reported", g.recovery_modal.phase == "fail" and g.recovery_modal.reason == "cancelled")
g.close_recovery()

# restore a different pilot
g.google_auth = FakeAuth(("ok", "TOKEN-B"))
payload = {"ok": True, "player_id": "b" * 32, "secret": "c" * 48, "name": "OLDPILOT", "country": "DE", "data": None,
           "bests": [{"level": 1, "score": 5000, "stars": 3, "time": 10.0, "swaps": 8, "rank": "S"}], "email": "pi***r@gmail.com"}
g.online.google_restore = lambda tok: setattr(g.online, "google", {"state": "ok", "mode": "restore", "payload": payload,
                                                                     "email": "pi***r@gmail.com"})
g.open_recovery("restore")
frames(3)
check("restored pilot takes over", sm.player_id == "b" * 32 and sm.player_name == "OLDPILOT" and g.state == "menu", sm.player_name)
check("its progress came along", sm.stats.get("1", {}).get("stars") == 3)

# no Google on the device
g.google_auth = type("NoAuth", (), {"available": lambda self: False, "request": lambda self, o=False: False,
                                    "poll": lambda self: None})()
g.open_profile("menu")
g.open_recovery("restore")
check("unavailable device says so", g.recovery_modal.phase == "fail" and g.recovery_modal.reason == "unavailable")
frames(2)
print("ALL OK" if ok else "SOME FAILED")
os._exit(0 if ok else 1)
