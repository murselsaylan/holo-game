"""When the game asks for a store rating (review.py): milestone first clears only, once each, a week apart."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import review  # noqa: E402

fails = 0


def check(name, got, want):
    global fails
    ok = got == want
    fails += not ok
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f" (got {got!r}, want {want!r})"))


DAY = 86400
d = {}
check("level 9 first clear: no", review.should_ask(d, 9, True, False, now=0), False)
check("level 10 replay (not first clear): no", review.should_ask(d, 10, False, False, now=0), False)
check("level 10 with a paid revive: no", review.should_ask(d, 10, True, True, now=0), False)
check("level 10 first clean clear: yes", review.should_ask(d, 10, True, False, now=10 * DAY), True)
review.mark_asked(d, 10, now=10 * DAY)
check("level 10 again: no", review.should_ask(d, 10, True, False, now=40 * DAY), False)
check("level 25 three days later: no (a week apart)", review.should_ask(d, 25, True, False, now=13 * DAY), False)
check("level 25 eight days later: yes", review.should_ask(d, 25, True, False, now=18 * DAY), True)
review.mark_asked(d, 25, now=18 * DAY)
check("level 50 later: yes", review.should_ask(d, 50, True, False, now=60 * DAY), True)
check("level 60: no milestone", review.should_ask(d, 60, True, False, now=90 * DAY), False)
check("saved record", d["review_asked"]["levels"], [10, 25])
check("desktop ask() does nothing", review.ask(), False)
print("ALL OK" if not fails else f"{fails} FAILED")
sys.exit(1 if fails else 0)
