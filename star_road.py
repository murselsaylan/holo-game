"""Star economy (wallet, shield / skin prices) and the daily level (1.0.9) - the numbers.

The server (supabase/functions/scores/ranked.ts) is the authority: tools/gen_wallet_data.py copies this module into
wallet_data.ts (RANKED), so the game shows exactly what the server pays and charges. Change a number here, regenerate,
redeploy.
"""
CAMPAIGN_STAR_CAP = 300            # campaign stars that can ever enter the wallet (1 per star, first time only)
ENDLESS_STARS_PER_DAY = 150        # safety cap of the stars verified endless climbs can add a (UTC) day

# star spending
SHIELD_STARS = 12                  # one-attempt start shield (same shield as the diamond one)
SHIELD_STARS_PER_DAY = 5

# daily level: one level for everybody (UTC day), one try
DAILY_FIRST, DAILY_LAST = 10, 100                       # the old single pool (kept for old tests / clients)
# 1.0.11: the day's level fits the pilot - [first level, last level, levels cleared needed]; each band has its own ranking
DAILY_BANDS = [[3, 12, 0], [13, 30, 15], [31, 60, 35], [61, 100, 65]]
DAILY_REWARD = 25                  # diamonds for clearing it
DAILY_REWARD_3STAR = 15
DAILY_STREAK_STEP = 5               # extra diamonds per day of an unbroken daily-level streak (the 2nd day pays 1 step ...)
DAILY_STREAK_MAX = 6                # ... up to this many steps (the 7th day on)            # extra for three stars
