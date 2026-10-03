// Daily login calendar on the server: node supabase/functions/scores/tests/login_test.ts
import assert from "node:assert/strict";
import { earnClaim } from "../wallet.ts";
import { LOGIN_REWARDS } from "../wallet_data.ts";
import { MemStore } from "./mem.ts";

const store: any = new MemStore();
const pid = "p1";
const day = (s: string) => Date.parse(s + "T12:00:00Z");
async function claim(date: string) {
  const r: any = await earnClaim(store, pid, "login", date, day(date));
  if ("amount" in r) store.log.push({ pid, reason: "login", ref: date, delta: r.amount, created: Math.floor(day(date) / 1000) });
  return r;
}
const dates = ["2026-10-01", "2026-10-02", "2026-10-03", "2026-10-04", "2026-10-05", "2026-10-06", "2026-10-07", "2026-10-08"];
const got = [];
for (const d of dates) got.push((await claim(d)).amount);
assert.deepEqual(got, [...LOGIN_REWARDS, LOGIN_REWARDS[0]], "7-day run, then it starts again");
assert.equal((await claim("2026-10-10")).amount, LOGIN_REWARDS[0], "a missed day restarts the run");
const bad: any = await earnClaim(store, pid, "login", "2026-09-01", day("2026-10-10"));
assert.ok("error" in bad, "old dates are refused");
console.log("ALL LOGIN TESTS PASSED", got);
