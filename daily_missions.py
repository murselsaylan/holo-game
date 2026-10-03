"""Three small daily goals that reset every calendar day and pay out diamonds.

Deterministic by date (no server round-trip): every player sees the same three missions on the same
day, one easy / one medium / one hard, drawn from a small pool and rotated by the date's ordinal.
Progress is tracked in SaveManager (`bump_daily`, see save_manager.py) against two simple counters
that are already produced by a normal level clear: `levels_played` and `stars_earned`.
"""
import datetime

# (metric, i18n label key, target, diamond reward)
POOL_EASY = [
    ("levels_played", "daily_levels", 1, 5),
]
POOL_MEDIUM = [
    ("levels_played", "daily_levels", 3, 10),
    ("stars_earned", "daily_stars", 6, 15),
]
POOL_HARD = [
    ("levels_played", "daily_levels", 5, 20),
    ("stars_earned", "daily_stars", 12, 25),
]


def _day_index(date_str):
    y, m, d = (int(x) for x in date_str.split("-"))
    return datetime.date(y, m, d).toordinal()


def missions_for(date_str=None):
    """3 missions for that calendar date (id, metric, label_key, target, reward)."""
    if not date_str:
        date_str = datetime.date.today().isoformat()
    idx = _day_index(date_str)
    picks = [POOL_EASY[idx % len(POOL_EASY)], POOL_MEDIUM[idx % len(POOL_MEDIUM)], POOL_HARD[(idx // 3) % len(POOL_HARD)]]
    out = []
    for i, (metric, key, target, reward) in enumerate(picks):
        out.append({"id": f"{date_str}_{i}", "metric": metric, "label_key": key, "target": target, "reward": reward})
    return out


def total_reward(date_str=None):
    return sum(m["reward"] for m in missions_for(date_str))
