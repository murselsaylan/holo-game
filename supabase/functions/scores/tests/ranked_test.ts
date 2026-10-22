// Star wallet / shield, daily level - through handle():
//   deno run -A --no-check tests/ranked_test.ts
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { handle, sign, signLive, sha256Hex, signWallet } from "../handler.ts";
import { MemStore } from "./mem.ts";
import { MemRanked } from "./ranked_mem.ts";
import { MemLive } from "./live_mem.ts";
import { dailyLevel } from "../ranked.ts";
import { RANKED } from "../wallet_data.ts";
import { crowdWeekKey } from "../crowd.ts";

// deno-lint-ignore no-explicit-any
const store: any = new MemStore();
store.live = new MemLive();
store.ranked = new MemRanked((pid: string) => ({ name: store.players.get(pid)?.name ?? "?", country: "TR" }));
const fake: Record<string, { level: number; stars: number }[]> = {};
store.playerBests = async (pid: string) => fake[pid] ?? [];
const now0 = Date.UTC(2026, 9, 21, 12, 0, 0);           // a Wednesday
// deno-lint-ignore no-explicit-any
const call = (route: string, body: any, t: number) => handle(store, "POST", route, new URLSearchParams(), JSON.stringify(body), "9.9.9." + Math.random(), t);
async function mk(c: string, t = now0) {
  const p = Array.from(c).map((ch) => ch.charCodeAt(0).toString(16)).join("").padEnd(32, "0").slice(0, 32), s = "1".repeat(48);
  await call("/api/register", { player_id: p, secret: s, name: c.toUpperCase(), country: "TR" }, t);
  const ts = Math.floor(t / 1000);
  assert.equal((await call("/api/wallet", { player_id: p, ts, op: "sync", local: 0, sig: await signWallet(s, p, ts, "sync", "0", "") }, t)).status, 200);
  return { p, s };
}
// deno-lint-ignore no-explicit-any
async function rk(who: { p: string; s: string }, op: string, arg = "", t = now0, extra: any = {}): Promise<any> {
  const ts = Math.floor(t / 1000);
  const dg = op === "daily_submit" ? await sha256Hex((extra.taps ?? []).join(",")) : "";
  return await call("/api/ranked", { player_id: who.p, ts, op, arg, ...extra, sig: await signLive(who.s, who.p, ts, "ranked", op, arg, dg) }, t);
}
const lv = (n: number) => JSON.parse(readFileSync(new URL(`../../../../levels/level${n}.json`, import.meta.url), "utf-8"));

// ---- pure rules
for (let d = 20000; d < 20400; d++) { const l = dailyLevel(d); assert.ok(l >= RANKED.DAILY_FIRST && l <= RANKED.DAILY_LAST); }

// ---- 1. star wallet: campaign stars count once, cap 300
const A = await mk("a");
const ref3 = lv(3).ref_taps;
let ts = Math.floor(now0 / 1000);
const sub = await call("/api/submit", { player_id: A.p, level: 3, ts, taps: ref3, sig: await sign(A.s, A.p, 3, ts, ref3) }, now0);
assert.equal(sub.status, 200);
let st = await rk(A, "stars");
assert.equal(st.status, 200);
assert.equal(st.body.stars, sub.body.stars, "the clear's stars entered the wallet");
const again = await call("/api/submit", { player_id: A.p, level: 3, ts, taps: ref3, sig: await sign(A.s, A.p, 3, ts, ref3) }, now0 + 1000);
assert.equal(again.status, 200);
st = await rk(A, "stars");
assert.equal(st.body.stars, sub.body.stars, "replaying the same level gives no more stars");
fake[A.p] = Array.from({ length: 140 }, (_, i) => ({ level: i + 1, stars: 3 }));    // old pilot: backfill from verified bests
st = await rk(A, "stars");
assert.equal(st.body.campaign, 300); assert.equal(st.body.stars, 300); assert.equal(st.body.earned, 300);
let r: any;
const B = await mk("b");
fake[B.p] = [{ level: 1, stars: 3 }, { level: 2, stars: 2 }];                 // 5 stars in sector 1
r = await rk(A, "road", "1"); assert.notEqual(r.status, 200, "the star road is gone");
r = await rk(A, "chest", "1:1"); assert.notEqual(r.status, 200, "the sector chests are gone");
assert.ok(!("road" in (await rk(A, "stars")).body) && !("chests" in (await rk(A, "stars")).body));
// spending never lowers the earned total; the shield needs enough stars and leaves a paid-help row
const ref = "ab".repeat(8);
r = await rk(B, "spend", "shield:" + ref); assert.equal(r.status, 402);                                                    // 5 stars < 12
r = await rk(A, "spend", "shield:" + ref); assert.equal(r.status, 200); assert.equal(r.body.stars, 300 - RANKED.SHIELD_STARS);
r = await rk(A, "spend", "shield:" + ref); assert.equal(r.body.stars, 300 - RANKED.SHIELD_STARS, "a retried ref is not charged twice");
assert.equal(store.log.filter((l: any) => l.pid === A.p && l.reason === "spend:shield").length, 1);
st = await rk(A, "stars");
assert.equal(st.body.earned, 300, "spending did not lower the earned total");
for (let i = 0; i < 6; i++) r = await rk(A, "spend", "shield:" + String(i).repeat(16));
assert.equal(r.status, 429, "daily shield limit");
r = await rk(A, "spend", "skin:star_hunter"); assert.equal(r.status, 402, "600 stars are more than the wallet holds");
const left = (await rk(A, "stars")).body.stars;
r = await rk(A, "spend", "skin:stargazer"); assert.equal(r.status, 200); assert.equal(r.body.stars, left - 40);
r = await rk(A, "spend", "skin:stargazer"); assert.equal(r.body.stars, left - 40, "owned skins are not charged again");
assert.ok((await store.walletSkins(A.p)).includes("stargazer"));
r = await rk(A, "spend", "skin:nope"); assert.equal(r.status, 400);
console.log("STARS OK");

// (the weekly league was removed: the server has no "league" op any more)
r = await rk(A, "league"); assert.equal(r.status, 400, "league op is gone");
console.log("NO LEAGUE OK");

// ---- 3. daily level: one level for all, one try, replay-checked, reward once, ranking
const day = Math.floor(now0 / 86_400_000), dl = dailyLevel(day);
const D = await mk("A"), E = await mk("B");
r = await rk(D, "daily"); assert.equal(r.body.level, dl); assert.equal(r.body.state, "open");
assert.equal((await rk(E, "daily")).body.level, dl, "same level for everybody");
r = await rk(D, "daily_submit", "", now0, { taps: lv(dl).ref_taps }); assert.equal(r.status, 409, "not started");
r = await rk(D, "daily_start"); assert.equal(r.body.first, true); assert.equal(r.body.state, "started");
r = await rk(D, "daily_start"); assert.equal(r.body.first, false, "second start is not a new try");
{ // the ad retry: the failed attempt gets a fresh start; capped per day; idempotent per ref; needs an unfinished attempt
  const x = await mk("rt");
  assert.equal((await rk(x, "daily_retry", "ab".repeat(8))).status, 409, "nothing started yet");
  await rk(x, "daily_start");
  assert.equal((await rk(x, "daily_retry", "zz")).status, 400);
  r = await rk(x, "daily_retry", "ab".repeat(8), now0 + 5000); assert.equal(r.status, 200); assert.equal(r.body.retries_left, 1);
  assert.equal((await store.ranked.dailyRun(Math.floor(now0 / 86_400_000), x.p)).started, Math.floor((now0 + 5000) / 1000), "start time reset");
  r = await rk(x, "daily_retry", "ab".repeat(8), now0 + 6000); assert.equal(r.status, 200); assert.equal(r.body.retries_left, 1, "same ref = no extra charge");
  assert.equal((await rk(x, "daily_retry", "cd".repeat(8), now0 + 7000)).status, 200);
  assert.equal((await rk(x, "daily_retry", "ef".repeat(8), now0 + 8000)).status, 429, "retry limit");
}
const dtaps = lv(dl).ref_taps;
r = await rk(D, "daily_submit", "", now0 + 1000, { taps: dtaps }); assert.equal(r.status, 422, "a clear faster than the level can be played");
r = await rk(D, "daily_submit", "", now0 + 600_000, { taps: [1, 2, 3] }); assert.equal(r.status, 422);
const bd = store.players.get(D.p).diamonds;
r = await rk(D, "daily_submit", "", now0 + 600_000, { taps: dtaps });
assert.equal(r.status, 200, JSON.stringify(r.body)); assert.equal(r.body.state, "done");
const paid = r.body.added; assert.ok(paid >= RANKED.DAILY_REWARD); assert.equal(store.players.get(D.p).diamonds, bd + r.body.added);
r = await rk(D, "daily_submit", "", now0 + 700_000, { taps: dtaps }); assert.equal(r.body.dup, true);
assert.equal(store.players.get(D.p).diamonds, bd + paid, "reward once");
r = await rk(E, "daily_start", "", now0); r = await rk(E, "daily_submit", "", now0 + 600_000, { taps: dtaps });
r = await rk(D, "daily"); assert.equal(r.body.total, 2); assert.equal(r.body.board.length, 2); assert.ok(r.body.board.some((x: any) => x.me));
// tomorrow is a new level and a new try
r = await rk(D, "daily", "", now0 + 86_400_000); assert.equal(r.body.state, "open");
// bad signature / bad op
r = await call("/api/ranked", { player_id: D.p, ts, op: "stars", arg: "", sig: "00" }, now0); assert.equal(r.status, 403);
r = await rk(D, "nope"); assert.equal(r.status, 400);
console.log("DAILY OK");
console.log("ALL RANKED TESTS PASSED");
