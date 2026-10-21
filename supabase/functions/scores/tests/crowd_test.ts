// Shared weekly goal on the server: node supabase/functions/scores/tests/crowd_test.ts
import assert from "node:assert/strict";
import { crowdAdd, crowdOp, crowdWeekKey, CROWD_PLAYER_CAP, CROWD_MIN_GOAL } from "../crowd.ts";
import { MemStore } from "./mem.ts";
import { MemLive } from "./live_mem.ts";

const store: any = new MemStore();
const live = new MemLive();
live.stats = { cleared: 25, pilots: 200 };
for (const id of ["a", "b", "c"]) {
  await store.register(id, "s", id.toUpperCase(), "TR");
  await store.walletOpen(id, 0, 1e9, 1);
}
const T0 = Date.parse("2026-10-19T12:00:00Z");
// --- crowd goal
const week = crowdWeekKey(T0);
assert.equal(await crowdAdd(live, "a", 3, T0), 3);
assert.equal(await crowdAdd(live, "a", 0, T0), 0);
assert.equal(await crowdAdd(live, "a", 9, T0), 3, "one clear adds at most 3");
// deno-lint-ignore no-explicit-any
let st: any = (await crowdOp(live, store, "a", "status", "", T0)).body;
assert.equal(st.goal, CROWD_MIN_GOAL); assert.equal(st.total, 6); assert.equal(st.mine, 6);
assert.deepEqual(st.tiers.map((t: { need: number }) => t.need), [495, 990, 1500]);
assert.equal((await crowdOp(live, store, "a", "claim", "1", T0)).status, 409, "tier 1 not reached");
for (let i = 0; i < 80; i++) await crowdAdd(live, "b", 3, T0);
assert.equal(await live.crowdMine(week, "b"), CROWD_PLAYER_CAP, "per-player weekly cap");
for (let i = 0; i < 3; i++) {
  const id = "x" + i;
  await store.register(id, "s", id, "TR");
  await store.walletOpen(id, 0, 1e9, 1);
  for (let k = 0; k < 60; k++) await crowdAdd(live, id, 3, T0);
}
st = (await crowdOp(live, store, "a", "status", "", T0)).body;
assert.ok(st.total >= 495 && st.total < 990, "total " + st.total);
assert.equal(st.tiers[0].claimable, true); assert.equal(st.tiers[1].reached, false);
const a0 = store.players.get("a").diamonds;
// deno-lint-ignore no-explicit-any
let c: any = (await crowdOp(live, store, "a", "claim", "1", T0)).body;
assert.equal(c.added, 10); assert.equal(store.players.get("a").diamonds, a0 + 10);
c = (await crowdOp(live, store, "a", "claim", "1", T0 + 1000)).body;
assert.equal(c.added, 0, "a tier pays once"); assert.equal(store.players.get("a").diamonds, a0 + 10);
assert.equal((await crowdOp(live, store, "a", "claim", "2", T0)).status, 409);
assert.equal((await crowdOp(live, store, "a", "claim", "9", T0)).status, 400);
assert.equal((await crowdOp(live, store, "c", "claim", "1", T0)).status, 403, "no contribution, no reward");
// next week's goal follows this week's total (x1.15, rounded to 50)
const nextWk = T0 + 7 * 86_400_000;
// deno-lint-ignore no-explicit-any
const nst: any = (await crowdOp(live, store, "a", "status", "", nextWk)).body;
assert.equal(nst.goal, Math.max(CROWD_MIN_GOAL, Math.round(Math.round(st.total * 1.15) / 50) * 50));
assert.equal(nst.total, 0);
// last week's reached tiers stay claimable for 3 days
// deno-lint-ignore no-explicit-any
const late: any = (await crowdOp(live, store, "b", "claim", `1@${week}`, nextWk + 86_400_000)).body;
assert.equal(late.added, 10);
assert.equal((await crowdOp(live, store, "b", "claim", `1@${week}`, nextWk + 5 * 86_400_000)).status, 410);
// --- weekly featured level
import { weeklyLevel, weeklyClear, WLEVEL_REWARD } from "../crowd.ts";
const lv = weeklyLevel(week);
assert.ok(lv >= 61 && lv <= 140, "pool " + lv);
const seen = new Set<number>();
for (let w = 1; w <= 52; w++) seen.add(weeklyLevel(`2026-W${String(w).padStart(2, "0")}`));
assert.ok(seen.size >= 30, "varied across weeks: " + seen.size);
let ws: any = (await crowdOp(live, store, "c", "status", "", T0)).body.wlevel;
assert.equal(ws.level, lv); assert.equal(ws.pct, 12.5); assert.equal(ws.cleared, false);
assert.equal((await crowdOp(live, store, "c", "wclaim", "", T0)).status, 409, "must clear it first");
await weeklyClear(live, "c", lv + 1, T0);
assert.equal((await crowdOp(live, store, "c", "wclaim", "", T0)).status, 409, "another level does not count");
await weeklyClear(live, "c", lv, T0);
const c0 = store.players.get("c").diamonds;
let wc: any = (await crowdOp(live, store, "c", "wclaim", "", T0)).body;
assert.equal(wc.added, WLEVEL_REWARD); assert.equal(store.players.get("c").diamonds, c0 + WLEVEL_REWARD);
wc = (await crowdOp(live, store, "c", "wclaim", "", T0 + 5000)).body;
assert.equal(wc.added, 0, "once a week");
ws = (await crowdOp(live, store, "c", "status", "", T0)).body.wlevel;
assert.equal(ws.claimed, true);
console.log("ALL CROWD TESTS PASSED");
