// Weekly missions + seasonal events on the server: node supabase/functions/scores/tests/goals_test.ts
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { earnClaim, isoWeek, weeklyReward } from "../wallet.ts";
import { MemStore } from "./mem.ts";

const golden = JSON.parse(readFileSync(new URL("./weekly_golden.json", import.meta.url), "utf-8"));
for (const [date, key, rewards] of golden) {
  const [y, w] = isoWeek(Date.parse(date + "T12:00:00Z"));
  assert.equal(`${y}-W${String(w).padStart(2, "0")}`, key, date);
  assert.deepEqual([0, 1, 2].map((i) => weeklyReward(`${key}_${i}`)), rewards, key);
}
const store: any = new MemStore();
const now = Date.parse("2026-10-02T12:00:00Z");
const ok: any = await earnClaim(store, "p", "weekly", "2026-W40_1", now);
assert.ok(ok.amount > 0, "this week's mission pays");
assert.ok("error" in (await earnClaim(store, "p", "weekly", "2026-W30_1", now)), "old week refused");
assert.ok("error" in (await earnClaim(store, "p", "weekly", "2026-W40_3", now)), "bad slot refused");
assert.equal(((await earnClaim(store, "p", "event", "autumn26_3", now)) as any).amount, 150);
assert.ok("error" in (await earnClaim(store, "p", "event", "frost26_0", now)), "future event refused");
assert.ok("error" in (await earnClaim(store, "p", "event", "autumn26_9", now)), "bad tier refused");
assert.ok("amount" in (await earnClaim(store, "p", "event", "autumn26_0", Date.parse("2026-11-02T12:00:00Z"))), "grace days");
assert.ok("error" in (await earnClaim(store, "p", "event", "autumn26_0", Date.parse("2026-11-06T12:00:00Z"))), "after grace");
console.log("ALL GOALS TESTS PASSED", golden.length);
