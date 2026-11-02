// 1.0.11: the daily level fits the pilot - a pool per band, the week's level never doubles as the day's.
import { dailyLevel, dailyStreak } from "../ranked.ts";
import { RANKED } from "../wallet_data.ts";
import assert from "node:assert/strict";

const bands = RANKED.DAILY_BANDS as readonly (readonly number[])[];
for (const [first, last, need] of bands) {
  const seen = new Set<number>();
  for (let d = 20000; d < 20200; d++) {
    const l = dailyLevel(d, need);
    assert.ok(l >= first && l <= last, `band ${first}-${last}: day ${d} gave ${l}`);
    seen.add(l);
  }
  assert.ok(seen.size >= Math.min(8, last - first), `band ${first}-${last} varies from day to day`);
}
// a pilot with 4 levels cleared never gets a level he cannot reach; one with 80 gets a hard one
for (let d = 20000; d < 20100; d++) {
  assert.ok(dailyLevel(d, 4) <= 12);
  assert.ok(dailyLevel(d, 80) >= 61);
}
// unknown progress -> the old single pool (old callers)
for (let d = 20000; d < 20100; d++) { const l = dailyLevel(d); assert.ok(l >= RANKED.DAILY_FIRST && l <= RANKED.DAILY_LAST); }
console.log("daily_band_test OK");

// the streak: unbroken days ending yesterday (or today once cleared)
assert.equal(dailyStreak([], 100, false), 0);
assert.equal(dailyStreak(["99", "98", "97"], 100, false), 3, "yesterday and the two before");
assert.equal(dailyStreak(["100", "99", "98"], 100, true), 3, "today counts once cleared");
assert.equal(dailyStreak(["98", "97"], 100, false), 2, "one missed day is forgiven (the cushion)");
assert.equal(dailyStreak(["97", "96"], 100, false), 0, "two missed days in a row break it");
assert.equal(dailyStreak(["100", "98"], 100, true), 2, "100, forgiven 99, 98");
assert.equal(dailyStreak(["100", "98", "96"], 100, true), 2, "a second gap within a week breaks it");
assert.equal(dailyStreak(["100", "98", "91"], 100, true), 2, "97 and 96 are missed in a row: it ends at 98");
console.log("streak OK");
