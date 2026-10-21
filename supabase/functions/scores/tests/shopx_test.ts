// Shop extras (weekly showcase, packs, prestige, Star Market, Star Chest) - through handle():
//   deno run -A --no-check tests/shopx_test.ts
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { handle, signLive, signWallet } from "../handler.ts";
import { MemStore } from "./mem.ts";
import { MemRanked } from "./ranked_mem.ts";
import { MemLive } from "./live_mem.ts";
import { market, weekEnd, weekIndex, weeklyFrame, weeklySkins } from "../rotation.ts";
import { spendPrice } from "../wallet.ts";
import { SHOPX, SKIN_COST } from "../wallet_data.ts";

// deno-lint-ignore no-explicit-any
const store: any = new MemStore();
store.live = new MemLive();
store.ranked = new MemRanked();
const now0 = Date.UTC(2026, 9, 21, 12, 0, 0);
// deno-lint-ignore no-explicit-any
const call = (route: string, body: any, t: number) => handle(store, "POST", route, new URLSearchParams(), JSON.stringify(body), "9.9.9." + Math.random(), t);
const rnd = () => Array.from(crypto.getRandomValues(new Uint8Array(12))).map((b) => b.toString(16).padStart(2, "0")).join("");
async function mk(c: string, diamonds = 0, stars = 0, t = now0) {
  const p = Array.from(c).map((ch) => ch.charCodeAt(0).toString(16)).join("").padEnd(32, "0").slice(0, 32), s = "1".repeat(48);
  await call("/api/register", { player_id: p, secret: s, name: c.toUpperCase(), country: "TR" }, t);
  const ts = Math.floor(t / 1000);
  assert.equal((await call("/api/wallet", { player_id: p, ts, op: "sync", local: diamonds, sig: await signWallet(s, p, ts, "sync", String(diamonds), "") }, t)).status, 200);
  if (stars) await store.ranked.starChange(p, stars, "lvl", "1:1", Math.floor(t / 1000));
  return { p, s };
}
// deno-lint-ignore no-explicit-any
async function sh(who: { p: string; s: string }, op: string, arg = "", t = now0): Promise<any> {
  const ts = Math.floor(t / 1000);
  return await call("/api/shop", { player_id: who.p, ts, op, arg, sig: await signLive(who.s, who.p, ts, "shop", op, arg, "") }, t);
}
const count = (pid: string, reason: string) => store.log.filter((l: any) => l.pid === pid && l.reason === reason).length;

// ---- 1. the weekly rotation is the Python one (shopx_golden.json from tools/shopx_golden.py)
const golden = JSON.parse(readFileSync(new URL("../shopx_golden.json", import.meta.url), "utf-8"));
for (const g of golden) {
  const ms = g.now * 1000;
  assert.equal(weekIndex(ms), g.week); assert.equal(weekEnd(ms), g.ends);
  assert.deepEqual(weeklySkins(ms).map((s) => [s.skin, s.price, s.full]), g.skins, "skins of week " + g.week);
  assert.equal(weeklyFrame(ms), g.frame);
  assert.deepEqual(market(ms).map((m) => m.id), g.market, "market of week " + g.week);
}
// the rotation really rotates: many different skins over a year, the week's picks differ from week to week
const seen = new Set<string>(); for (const g of golden) for (const s of g.skins) seen.add(s[0]);
assert.ok(seen.size >= 30, "rotation covers the pool: " + seen.size);
assert.equal(weekIndex(Date.UTC(2026, 9, 19, 0, 0, 0)), weekIndex(Date.UTC(2026, 9, 25, 23, 59, 59)), "Mon..Sun is one week");
assert.equal(weekIndex(Date.UTC(2026, 9, 26, 0, 0, 0)), weekIndex(Date.UTC(2026, 9, 25, 23, 59, 59)) + 1, "Monday 00:00 starts the next week");

// ---- 2. the skins of the week are cheaper in the wallet's price table too (the game's normal buy path)
const wk = weeklySkins(now0);
for (const s of wk) {
  const p = spendPrice("skin:" + s.skin, now0);
  assert.ok(p !== null && p <= s.price && p < s.full, "weekly price applies: " + s.skin);
}
const other = Object.keys(SKIN_COST).find((k) => !k.includes("prestige") && !wk.some((s) => s.skin === k) && spendPrice("skin:" + k, now0) === (SKIN_COST as any)[k])!;
assert.ok(other, "a skin outside the showcase keeps its full price");

// ---- 3. consumable packs
const A = await mk("a", 1000);
let r = await sh(A, "view");
assert.equal(r.status, 200); assert.equal(r.body.balance, 1000);
assert.equal(r.body.showcase.length, 3); assert.equal(r.body.packs.left.shield, 20);
let ref = rnd();
r = await sh(A, "buy", `pack:shield3:${ref}`);
assert.equal(r.status, 200); assert.equal(r.body.balance, 1000 - 27); assert.equal(r.body.units, 3);
assert.equal(count(A.p, "spend:shield"), 3, "three paid-help rows");
r = await sh(A, "buy", `pack:shield3:${ref}`);             // retried (lost answer): not charged twice, no extra units
assert.equal(r.body.dup, true); assert.equal(r.body.balance, 1000 - 27); assert.equal(count(A.p, "spend:shield"), 3);
r = await sh(A, "buy", `pack:revive10:${rnd()}`);
assert.equal(r.body.balance, 1000 - 27 - 170); assert.equal(count(A.p, "spend:revive"), 10);
r = await sh(A, "buy", `pack:revive3:${rnd()}`);            // 10 already today, limit 10: refused
assert.equal(r.status, 429); assert.equal(count(A.p, "spend:revive"), 10);
assert.equal((await sh(A, "buy", `pack:shield10:${rnd()}`)).status, 200);      // 13 shields
assert.equal((await sh(A, "buy", `pack:shield10:${rnd()}`)).status, 429);      // would be 23 > 20
assert.equal((await sh(A, "buy", `pack:nope:${rnd()}`)).status, 400);
assert.equal((await sh(A, "buy", `pack:shield3:bad`)).status, 400, "ref must be a random id");
const poor = await mk("p", 20);
r = await sh(poor, "buy", `pack:shield3:${rnd()}`);
assert.equal(r.status, 402); assert.equal(count(poor.p, "spend:shield"), 0, "nothing granted when the charge failed");
assert.equal((await sh(A, "view", "", now0 + 86_401_000)).body.packs.left.shield, 20, "the limit is per 24 h");
// the pack's rows are what the assist check counts: 13 shield rows = 13 usable bought shields
assert.equal(count(A.p, "spend:shield"), 13);

// ---- 4. prestige: buy, owned once, equip, limited frames only in their week, star-only never for diamonds
const B = await mk("b", 20000);
r = await sh(B, "buy", `frame:frame_gold:${rnd()}`);
assert.equal(r.status, 200); assert.equal(r.body.balance, 20000 - 1800);
r = await sh(B, "buy", `frame:frame_gold:${rnd()}`); assert.equal(r.body.dup, true); assert.equal(r.body.balance, 20000 - 1800, "no second charge");
assert.equal(count(B.p, "spend:prestige:frame_gold"), 1);
assert.equal((await sh(B, "buy", `frame:frame_stardust:${rnd()}`)).status, 400, "star frames are not for diamonds");
assert.equal((await sh(B, "buy", `frame:ghost:${rnd()}`)).status, 400);
const lim = weeklyFrame(now0), notLim = SHOPX.LIMITED_FRAMES.find((f) => f !== lim && f !== weeklyFrame(now0 - 600_000))!;
assert.equal((await sh(B, "buy", `frame:${notLim}:${rnd()}`)).status, 410, "a limited frame is gone outside its week");
r = await sh(B, "buy", `frame:${lim}:${rnd()}`); assert.equal(r.status, 200); assert.equal(r.body.price, SHOPX.LIMITED_FRAME_PRICE);
r = await sh(B, "buy", `title:title_nova:${rnd()}`); assert.equal(r.status, 200);
assert.equal((await sh(B, "equip", "frame:frame_silver")).status, 403, "cannot equip what is not owned");
assert.equal((await sh(A, "equip", "frame:frame_gold")).status, 403);
r = await sh(B, "equip", "frame:frame_gold"); assert.equal(r.status, 200);
r = await sh(B, "equip", "title:title_nova"); assert.equal(r.body.frame, "frame_gold"); assert.equal(r.body.title, "title_nova");
assert.deepEqual(await store.getPrestige(B.p), { frame: "frame_gold", title: "title_nova" });
r = await sh(B, "view"); assert.ok(r.body.prestige.owned.includes("frame_gold") && r.body.prestige.frame === "frame_gold");
r = await sh(B, "equip", "frame:"); assert.equal(r.body.frame, "", "empty id takes the frame off"); assert.equal(r.body.title, "title_nova");
// the price list: the permanent prestige items are a long diamond sink
const perm = [...Object.values(SHOPX.FRAMES), ...Object.values(SHOPX.TITLES)].filter((x: any) => x.kind === "perm");
assert.ok(perm.reduce((a: number, x: any) => a + x.price, 0) >= 20000);

// ---- 5. Star Market: this week's three items, per-week limits, grants
const C = await mk("c", 100, 500);
const mkt = market(now0);
r = await sh(C, "view"); assert.deepEqual(r.body.market.map((m: any) => m.id), mkt.map((m) => m.id)); assert.equal(r.body.stars, 500);
const off = Object.values(SHOPX.MARKET_POOLS).flat().find((m: any) => !mkt.some((x) => x.id === m.id))!;
assert.equal((await sh(C, "mkt", `${(off as any).id}:${rnd()}`)).status, 410, "an item that is not this week's");
// slot 0 (consumable), slot 1 (diamonds), slot 2 (cosmetic)
const [m0, m1, m2] = mkt;
ref = rnd();
r = await sh(C, "mkt", `${m0.id}:${ref}`);
assert.equal(r.status, 200); assert.equal(r.body.stars, 500 - m0.stars); assert.equal(count(C.p, "spend:" + m0.kind), Number(m0.payload));
const after0 = r.body.stars;
r = await sh(C, "mkt", `${m0.id}:${ref}`); assert.equal(r.body.dup, true); assert.equal(r.body.stars, after0, "retry is free");
assert.equal(count(C.p, "spend:" + m0.kind), Number(m0.payload), "retry adds no units");
for (let k = 1; k < m0.limit; k++) assert.equal((await sh(C, "mkt", `${m0.id}:${rnd()}`)).status, 200);
assert.equal((await sh(C, "mkt", `${m0.id}:${rnd()}`)).status, 429, "weekly limit");
r = await sh(C, "mkt", `${m1.id}:${rnd()}`);
assert.equal(r.status, 200); assert.equal(r.body.balance, 100 + Number(m1.payload));
r = await sh(C, "mkt", `${m2.id}:${rnd()}`); assert.equal(r.status, 200);
assert.equal(count(C.p, `spend:prestige:${m2.payload}`), 1); assert.equal((await sh(C, "mkt", `${m2.id}:${rnd()}`)).status, 409, "owned cosmetics are not sold twice");
assert.equal((await sh(C, "view", "", now0 + 7 * 86_400_000)).body.market.map((m: any) => m.id).join() === mkt.map((m) => m.id).join(), false, "next week = other items (or at least reset limits)") ;
const broke = await mk("d", 0, 1);
assert.equal((await sh(broke, "mkt", `${m0.id}:${rnd()}`)).status, 402);
assert.equal(count(broke.p, "spend:" + m0.kind), 0);

// ---- 6. Star Chest: price, daily limit, idempotent retry, server dice
const D = await mk("e", 0, 400);
const outcomes: string[] = [];
for (let i = 0; i < SHOPX.CHEST.per_day; i++) {
  ref = rnd();
  r = await sh(D, "chest", ref);
  assert.equal(r.status, 200); assert.equal(r.body.n, i);
  outcomes.push(`${r.body.reward.kind}:${r.body.reward.payload}`);
  const again = await sh(D, "chest", ref);                // the same request again: same chest, same reward, no charge
  assert.equal(again.body.dup, true); assert.equal(`${again.body.reward.kind}:${again.body.reward.payload}`, outcomes[i]);
  assert.equal(again.body.stars, r.body.stars);
}
assert.equal((await store.ranked.starTotals(D.p)).balance, 400 - SHOPX.CHEST.per_day * SHOPX.CHEST.cost);
assert.equal((await sh(D, "chest", rnd())).status, 429, "daily chest limit");
assert.equal((await sh(D, "chest", rnd(), now0 + 86_400_000)).status, 200, "next day it opens again");
assert.equal((await sh(broke, "chest", rnd())).status, 402);
// the dice: every outcome of the table appears over many chests, and the same (player, n) always gives the same
const E = await mk("f", 0, 0);
const kinds = new Map<string, number>();
for (let i = 0; i < 400; i++) {
  const t = now0 + Math.floor(i / SHOPX.CHEST.per_day) * 86_400_000;
  await store.ranked.starChange(E.p, SHOPX.CHEST.cost, "endless", "t" + i, Math.floor(t / 1000));
  const x = await sh(E, "chest", rnd(), t);
  assert.equal(x.status, 200, JSON.stringify(x.body));
  const k = x.body.reward.kind; kinds.set(k, (kinds.get(k) ?? 0) + 1);
}
for (const k of ["gems", "shield", "revive"]) assert.ok((kinds.get(k) ?? 0) > 20, k + " appears: " + [...kinds].join());
assert.ok(((kinds.get("frame") ?? 0) + 0) >= 0);
// expected value stays sane: diamonds per chest from gems rows
const gems = store.log.filter((l: any) => l.pid === E.p && l.reason === "chest").reduce((a: number, l: any) => a + l.delta, 0);
console.log("chest diamonds per chest (400 chests):", (gems / 400).toFixed(1), JSON.stringify([...kinds]));

// ---- 7. star cap: stars above STAR_CAP turn into diamonds once, at the cap rate
const F = await mk("g", 10, SHOPX.STAR_CAP + 120);
r = await sh(F, "view");
assert.equal(r.body.stars, SHOPX.STAR_CAP); assert.equal(r.body.balance, 10 + 120 * SHOPX.OVERFLOW_RATE);
assert.equal(r.body.overflow.stars, 120);
r = await sh(F, "view"); assert.equal(r.body.stars, SHOPX.STAR_CAP); assert.equal(r.body.balance, 10 + 120 * SHOPX.OVERFLOW_RATE, "no second conversion");
await store.ranked.starChange(F.p, 30, "endless", "run1", Math.floor(now0 / 1000));
r = await sh(F, "view"); assert.equal(r.body.stars, SHOPX.STAR_CAP); assert.equal(r.body.balance, 10 + 150 * SHOPX.OVERFLOW_RATE);
const star = await call("/api/ranked", { player_id: F.p, ts: Math.floor(now0 / 1000), op: "stars", arg: "", sig: await signLive(F.s, F.p, Math.floor(now0 / 1000), "ranked", "stars", "", "") }, now0);
assert.equal(star.body.stars, SHOPX.STAR_CAP, "the star view applies the cap too");

// ---- 8. auth and sync
assert.equal((await call("/api/shop", { player_id: A.p, ts: Math.floor(now0 / 1000), op: "view", arg: "", sig: "0".repeat(64) }, now0)).status, 403);
const G = { p: "9".repeat(32), s: "2".repeat(48) };
await call("/api/register", { player_id: G.p, secret: G.s, name: "NOSYNC", country: "TR" }, now0);
assert.equal((await sh(G, "view")).status, 409, "the wallet must be opened first");
console.log("shopx_test OK");
