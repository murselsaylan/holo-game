"""Three bigger goals per ISO week (1.0.6), next to the daily ones on the missions screen.

Deterministic by week (every player gets the same three), one from each pool, rotated by the week number. Progress
lives in SaveManager (`bump_weekly`): levels played / stars earned (same moments as the daily counters) and the
endless climb's metres / stars (at the end of each climb). The server pays a claim only for this or last week's
missions and only once (supabase/functions/scores/wallet.ts earnClaim "weekly", pools from tools/gen_wallet_data.py).
"""
import datetime

# (metric, i18n label key, target, diamond reward)
POOL_A = [
    ("levels_played", "weekly_levels", 15, 40),
    ("stars_earned", "weekly_stars", 30, 45),
]
POOL_B = [
    ("endless_m", "weekly_climb", 1500, 60),
    ("endless_stars", "weekly_endless_stars", 60, 60),
]
POOL_C = [
    ("levels_played", "weekly_levels", 30, 80),
    ("endless_m", "weekly_climb", 4000, 90),
    ("stars_earned", "weekly_stars", 60, 80),
]


def week_key(date=None):
    y, w, _ = (date or datetime.date.today()).isocalendar()
    return f"{y}-W{w:02d}"


def _week_index(key):
    y, w = key.split("-W")
    return int(y) * 53 + int(w)


def missions_for(key=None):
    """3 missions of that ISO week (id, metric, label_key, target, reward)."""
    key = key or week_key()
    idx = _week_index(key)
    picks = [POOL_A[idx % len(POOL_A)], POOL_B[idx % len(POOL_B)], POOL_C[idx % len(POOL_C)]]
    return [{"id": f"{key}_{i}", "metric": metric, "label_key": label, "target": target, "reward": reward}
            for i, (metric, label, target, reward) in enumerate(picks)]


def days_left(date=None):
    d = date or datetime.date.today()
    return 7 - d.isoweekday() + 1
