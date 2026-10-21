import { handle, signWallet } from "../handler.ts";
import { dailyReward } from "../wallet.ts";
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
assert.equal((await post("/api/register", { player_id: pid, secret, name: "Streak", country: "TR" })).status, 200);
let r: any = await w("sync", { local: 0 });
assert.equal(r.status, 200); assert.deepEqual(r.body.skins, []);
const iso = (k: number) => new Date(Date.UTC(2026, 9, 1 + k)).toISOString().slice(0, 10);
const login = async (k: number) => { now = Date.UTC(2026, 9, 1 + k, 18, 0, 0); return await w("earn", { kind: "login", ref: iso(k) }); };
const skins = async () => (await w("sync", { local: 0 })).body.skins.slice().sort();
for (let k = 0; k < 6; k++) { r = await login(k); assert.equal(r.status, 200); assert.equal(r.body.weeks, undefined); }
assert.deepEqual(await skins(), []);                                      // days 1-6: no Seri skin yet
r = await login(6);                                                       // day 7: the first full run
assert.equal(r.body.added, 40); assert.equal(r.body.weeks, 1); assert.deepEqual(r.body.skins, ["streak_spark"]);
assert.deepEqual(await skins(), ["streak_spark"]);
r = await login(6); assert.equal(r.body.added, 0); assert.equal(r.body.weeks, 1);          // a retried claim counts once
assert.deepEqual(await skins(), ["streak_spark"]);
for (let k = 7; k < 13; k++) await login(k);
assert.deepEqual(await skins(), ["streak_spark"]);                        // week 2 not done yet
r = await login(13); assert.equal(r.body.weeks, 2);
assert.deepEqual(await skins(), ["streak_ember", "streak_spark"]);        // 2 full weeks
// a broken run does not count: skip a day, then 6 more logins = no new week
for (let k = 15; k < 21; k++) await login(k);
assert.deepEqual(await skins(), ["streak_ember", "streak_spark"]);
// the Seri skins cannot be bought with diamonds
r = await w("spend", { item: "skin:streak_flame", ref: rnd() }); assert.equal(r.status, 400);
// and another player never gets them
const other = "d".repeat(32);
assert.equal((await post("/api/register", { player_id: other, secret, name: "Other", country: "TR" })).status, 200);
console.log("ALL STREAK SKIN TESTS PASSED");
