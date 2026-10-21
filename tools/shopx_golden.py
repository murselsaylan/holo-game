"""Writes supabase/functions/scores/shopx_golden.json: the weekly rotation of shop_items.py for 120 weeks, so the
TypeScript copy (rotation.ts) can be checked against it (tests/shopx_test.ts).

    python tools/shopx_golden.py
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import shop_items as S  # noqa: E402

out = []
t0 = 1_790_000_000                      # 2026-09, a bit before the first weeks that matter
for k in range(120):
    now = t0 + k * 7 * 86400 + (k * 37_000) % (7 * 86400)         # a different weekday / hour every sample
    out.append({
        "now": now, "week": S.week_index(now), "ends": S.week_end(now),
        "skins": [list(x) for x in S.weekly_skins(now)], "frame": S.weekly_frame(now),
        "market": [m[0] for m in S.market(now)],
    })
path = os.path.join(ROOT, "supabase", "functions", "scores", "shopx_golden.json")
with open(path, "w", encoding="utf-8") as f:
    json.dump(out, f)
print("wrote", path, len(out), "weeks")
