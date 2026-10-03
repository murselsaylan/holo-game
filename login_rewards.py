"""Daily login rewards (1.0.6): a 7-day calendar. Opening the game on consecutive days walks it day 1 -> 7 (day 7 is
the weekly prize, then it starts again); missing a day restarts it at day 1. The diamonds are claimed through the
server wallet (kind "login", ref = the local date); the server recounts the streak from its own log, so the amount
cannot be faked - supabase/functions/scores/wallet.ts earnClaim mirrors LOGIN_REWARDS (tools/gen_wallet_data.py).
"""
import datetime

LOGIN_REWARDS = [5, 5, 10, 10, 15, 20, 40]     # diamonds on day 1 ... 7
WEEKLY_STARS = 20                               # day 7 also fills the star wallet (Yıldız Avcısı skins)


def today_str(now=None):
    return (now or datetime.date.today()).isoformat()


def _prev(date_str):
    y, m, d = (int(x) for x in date_str.split("-"))
    return (datetime.date(y, m, d) - datetime.timedelta(days=1)).isoformat()


def state(save):
    return save.data.setdefault("login", {"last": "", "streak": 0, "days": 0, "best": 0})


def claimable(save, today=None):
    return state(save).get("last") != (today or today_str())


def next_day(save, today=None):
    """Which calendar day (1..7) today's claim is, and its streak length."""
    st = state(save)
    today = today or today_str()
    streak = int(st.get("streak", 0)) + 1 if st.get("last") == _prev(today) else 1
    return (streak - 1) % 7 + 1, streak


def claim(save, today=None):
    """Claim today's reward: returns (day, diamonds, stars) or None when it was already claimed today."""
    today = today or today_str()
    if not claimable(save, today):
        return None
    day, streak = next_day(save, today)
    st = state(save)
    st.update(last=today, streak=streak, days=int(st.get("days", 0)) + 1, best=max(int(st.get("best", 0)), streak))
    gems = LOGIN_REWARDS[day - 1]
    stars = WEEKLY_STARS if day == 7 else 0
    save.earn("login", today, gems)
    if stars:
        save.add_star_coins(stars)
    save.save()
    return day, gems, stars
