// Day 7 of the login calendar and an event tier put stars into the star wallet (once): deno run -A --no-check tests/login_stars_test.ts
import { handle, signWallet } from "../handler.ts";
import { MemStore } from "./mem.ts";
import { MemRanked } from "./ranked_mem.ts";
import { LOGIN_STARS, EVENTS } from "../wallet_data.ts";
import assert from "node:assert/strict";

// deno-lint-ignore no-explicit-any
const store: any = new MemStore();
store.ranked = new MemRanked();
const pid = "a".repeat(32), secret = "b".repeat(48);
let now = Date.UTC(2026, 9, 1, 18, 0, 0);
// deno-lint-ignore no-explicit-any
const post = async (route: string, body: any) => await handle(store, "POST", route, new URLSearchParams(), JSON.stringify(body), "1.2.3.4", now);
// deno-lint-ignore no-explicit-any
const w = async (op: string, extra: any) => {
  const ts = Math.floor(now / 1000);
  const key = op === "sync" ? String(Math.trunc(extra.local ?? 0)) : extra.kind;
  return await post("/api/wallet", { player_id: pid, ts, op, ...extra, sig: await signWallet(secret, pid, ts, op, key, extra.ref ?? "") });
};
await post("/api/register", { player_id: pid, secret, name: "S", country: "TR" });
await w("sync", { local: 0 });
const iso = (k: number) => new Date(Date.UTC(2026, 9, 1 + k)).toISOString().slice(0, 10);
for (let k = 0; k < 7; k++) { now = Date.UTC(2026, 9, 1 + k, 18, 0, 0); await w("earn", { kind: "login", ref: iso(k) }); }
assert.equal((await store.ranked.starTotals(pid)).balance, LOGIN_STARS, "day 7 pays its stars");
await w("earn", { kind: "login", ref: iso(6) });
assert.equal((await store.ranked.starTotals(pid)).balance, LOGIN_STARS, "a retried claim pays once");
// an event tier with stars (the current event table decides which)
const [id, ev] = Object.entries(EVENTS as Record<string, { start: string; stars: number[] }>)[0];
const i = ev.stars.findIndex((s) => s > 0);
if (i >= 0) {
  const [y, m, d] = ev.start.split("-").map(Number);
  now = Date.UTC(y, m - 1, d, 12, 0, 0);
  const r = await w("earn", { kind: "event", ref: `${id}_${i}` });
  assert.equal(r.status, 200);
  assert.equal((await store.ranked.starTotals(pid)).balance, LOGIN_STARS + ev.stars[i], "event tier stars");
}
console.log("ALL LOGIN STARS TESTS PASSED");
