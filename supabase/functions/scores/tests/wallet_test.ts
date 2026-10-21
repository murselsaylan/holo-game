import { handle, signWallet } from "../handler.ts";
import { dailyDeal, dailyReward } from "../wallet.ts";
import { weeklySkins } from "../rotation.ts";
import { SKIN_COST } from "../wallet_data.ts";
import { MemStore } from "./mem.ts";
import assert from "node:assert/strict";

const store = new MemStore();
const pid = "a".repeat(32), secret = "b".repeat(48);
let now = Date.UTC(2026, 8, 25, 18, 0, 0);
const post = async (route: string, body: any) => (await handle(store as any, "POST", "/functions/v1/scores" + route, new URLSearchParams(), JSON.stringify(body), "1.2.3.4", now));
const w = async (op: string, extra: any, sec = secret) => {
  const ts = Math.floor(now / 1000);
  const key = op === "sync" ? String(Math.trunc(extra.local ?? 0)) : op === "earn" ? extra.kind : extra.item;
  const ref = extra.ref ?? "";
  return post("/api/wallet", { player_id: pid, ts, op, ...extra, sig: await signWallet(sec, pid, ts, op, key, ref) });
};
const rnd = () => Array.from(crypto.getRandomValues(new Uint8Array(12))).map((b) => b.toString(16).padStart(2, "0")).join("");

assert.equal((await post("/api/register", { player_id: pid, secret, name: "Test", country: "TR" })).status, 200);
// earn before sync -> 409
assert.equal((await w("earn", { kind: "welcome", ref: "" })).status, 409);
// bad signature
assert.equal((await w("sync", { local: 50 }, "c".repeat(48))).status, 403);
// first sync imports the old balance as it is (no limit)
let r = await w("sync", { local: 31275 });
assert.equal(r.status, 200); assert.equal(r.body.balance, 31275); assert.equal(r.body.imported, 31275);
// second sync does not import again
r = await w("sync", { local: 5 }); assert.equal(r.body.balance, 31275); assert.equal(r.body.imported, null);
// gift
store.players.get(pid).gift = 1000;
r = await w("sync", { local: 0 }); assert.equal(r.body.balance, 32275); assert.equal(r.body.gift, 1000);
r = await w("sync", { local: 0 }); assert.equal(r.body.gift, 0); assert.equal(r.body.balance, 32275);
// welcome once
r = await w("earn", { kind: "welcome", ref: "" }); assert.equal(r.body.balance, 32305); assert.equal(r.body.added, 30);
r = await w("earn", { kind: "welcome", ref: "" }); assert.equal(r.body.balance, 32305); assert.equal(r.body.added, 0);
// achievements: known id once, unknown rejected
r = await w("earn", { kind: "ach", ref: "rookie" }); assert.equal(r.body.balance, 32310);
r = await w("earn", { kind: "ach", ref: "rookie" }); assert.equal(r.body.balance, 32310);
assert.equal((await w("earn", { kind: "ach", ref: "free_money" })).status, 400);
// daily: matches the python pool, once, expired rejected
const mid = "2026-09-25_2";
r = await w("earn", { kind: "daily", ref: mid }); assert.equal(r.body.added, dailyReward(mid));
r = await w("earn", { kind: "daily", ref: mid }); assert.equal(r.body.added, 0);
assert.equal((await w("earn", { kind: "daily", ref: "2026-09-10_0" })).status, 400);
// ads: cooldown + daily cap
r = await w("earn", { kind: "ad", ref: rnd() }); assert.equal(r.body.added, 50);
assert.equal((await w("earn", { kind: "ad", ref: rnd() })).status, 429);          // 15 s: no video is shorter
for (let k = 0; k < 40; k++) { now += 16_000; await w("earn", { kind: "ad", ref: rnd() }); }
now += 16_000;
assert.equal((await w("earn", { kind: "ad", ref: rnd() })).status, 429);           // the 30 a day safety cap
// "watch an ad to continue": pays exactly one revive, 10 per day
r = await w("earn", { kind: "adrevive", ref: rnd() }); assert.equal(r.body.added, 20);
for (let k = 0; k < 9; k++) await w("earn", { kind: "adrevive", ref: rnd() });
assert.equal((await w("earn", { kind: "adrevive", ref: rnd() })).status, 429);
// packs can't be claimed as an "earn" (only through the verified purchase op)
assert.equal((await w("earn", { kind: "pack", ref: "pack_1000:tok" })).status, 400);
// spend: server price, idempotent ref, insufficient
let bal = (await w("sync", { local: 0 })).body.balance as number;
const ref1 = rnd();
r = await w("spend", { item: "revive", ref: ref1 }); assert.equal(r.body.balance, bal - 20);
r = await w("spend", { item: "revive", ref: ref1 }); assert.equal(r.body.balance, bal - 20);   // retried request
// a 500-diamond skin outside this week's showcase and today's deal costs its full price; one in the showcase costs the weekly price
const wkSkins = weeklySkins(now), dealSkin = dailyDeal(now).skin;
const full500 = Object.keys(SKIN_COST).find((k) => (SKIN_COST as any)[k] === 500 && !k.includes("prestige") && k !== dealSkin && !wkSkins.some((x) => x.skin === k))!;
r = await w("spend", { item: "skin:" + full500, ref: rnd() }); assert.equal(r.body.price, 500);
r = await w("spend", { item: "skin:" + wkSkins[0].skin, ref: rnd() }); assert.ok(r.body.price <= wkSkins[0].price && r.body.price < wkSkins[0].full, "weekly showcase price");
assert.equal((await w("spend", { item: "skin:nope", ref: rnd() })).status, 400);
assert.equal((await w("spend", { item: "revive", ref: "short" })).status, 400);
// the day's first shield is free (once per UTC day, a retried ref is not charged); the next one costs SHIELD_COST
assert.equal((await w("sync", { local: 0 })).body.free_shield, true, "free shield offered");
bal = (await w("sync", { local: 0 })).body.balance as number;
const sref = rnd();
r = await w("spend", { item: "shield", ref: sref }); assert.equal(r.status, 200); assert.equal(r.body.price, 0); assert.equal(r.body.free, true); assert.equal(r.body.balance, bal);
r = await w("spend", { item: "shield", ref: sref }); assert.equal(r.body.balance, bal, "retried free request is not charged");
assert.equal((await w("sync", { local: 0 })).body.free_shield, false, "used up for today");
r = await w("spend", { item: "shield", ref: rnd() }); assert.equal(r.body.price, 10); assert.equal(r.body.balance, bal - 10);
store.players.get(pid).diamonds = 5;
r = await w("spend", { item: "shield", ref: rnd() }); assert.equal(r.status, 402); assert.equal(r.body.balance, 5);
// stale timestamp
const ts = Math.floor(now / 1000) - 2000;
r = await post("/api/wallet", { player_id: pid, ts, op: "sync", local: 0, sig: await signWallet(secret, pid, ts, "sync", "0", "") });
assert.equal(r.status, 403);
// daily reward table equals the python game (checked against values printed by python)
console.log("daily", ["2026-09-25_0", "2026-09-25_1", "2026-09-25_2", "2026-09-26_2", "2026-09-27_1"].map(dailyReward).join(","));
console.log("ALL WALLET TESTS PASSED");
