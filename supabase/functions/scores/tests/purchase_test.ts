import { handle, setVerifier, signWallet, sha256Hex } from "../handler.ts";
import { accountTag } from "../wallet.ts";
import { MemStore } from "./mem.ts";
import assert from "node:assert/strict";

const store = new MemStore();
const A = "a".repeat(32), SA = "b".repeat(48), B = "c".repeat(32), SB = "d".repeat(48);
const now = Date.now();
const post = async (body: any) => handle(store as any, "POST", "/api/wallet", new URLSearchParams(), JSON.stringify(body), "9.9.9." + Math.random(), now);
async function w(pid: string, sec: string, op: string, extra: any) {
  const ts = Math.floor(now / 1000);
  const key = op === "sync" ? String(extra.local ?? 0) : op === "purchase" ? extra.product : op === "spend" ? extra.item : extra.kind;
  const ref = extra.ref ?? "";
  return post({ player_id: pid, ts, op, ...extra, sig: await signWallet(sec, pid, ts, op, key, ref) });
}
const buy = async (pid: string, sec: string, product: string, token: string) => w(pid, sec, "purchase", { product, token, ref: await sha256Hex(token) });

for (const [p, s] of [[A, SA], [B, SB]]) {
  await handle(store as any, "POST", "/api/register", new URLSearchParams(), JSON.stringify({ player_id: p, secret: s, name: "X", country: "TR" }), "1.1.1.1", now);
  await w(p, s, "sync", { local: 0 });
}
// fake Google: token -> purchase
const play: Record<string, any> = {};
let calls = 0;
setVerifier(async (product, token) => { calls++; if (token === "boom") throw new Error("google down"); return play[token] ?? { state: "cancelled", orderId: "", account: "", consumed: false, test: false }; });
const tagA = await accountTag(A);
play["tok-1"] = { state: "purchased", orderId: "GPA.1", account: tagA, consumed: false, test: true };
let r = await buy(A, SA, "pack_1000", "tok-1");
assert.equal(r.status, 200); assert.equal(r.body.balance, 3000); assert.equal(r.body.dup, false);   // pack_1000 pays 3000 (3x)
r = await buy(A, SA, "pack_1000", "tok-1");                          // the game retries after a lost answer
assert.equal(r.status, 200); assert.equal(r.body.balance, 3000); assert.equal(r.body.dup, true);
r = await buy(B, SB, "pack_1000", "tok-1");                          // someone else replays the token
assert.ok(r.status === 403 || r.status === 409, "token of A refused for B: " + r.status);
play["tok-2"] = { state: "pending", orderId: "GPA.2", account: tagA, consumed: false, test: true };
r = await buy(A, SA, "pack_350", "tok-2"); assert.equal(r.status, 202); assert.equal(r.body.balance, 3000);
play["tok-2"].state = "purchased";                                   // paid later (cash / slow card)
r = await buy(A, SA, "pack_350", "tok-2"); assert.equal(r.body.balance, 4050);
r = await buy(A, SA, "pack_100", "fake-token"); assert.equal(r.status, 410); assert.equal(r.body.balance, 4050);
play["tok-3"] = { state: "purchased", orderId: "GPA.3", account: tagA, consumed: false, test: true };
r = await buy(A, SA, "pack_2500", "tok-3x"); assert.equal(r.status, 410);          // token/product mismatch -> unknown token
r = await buy(A, SA, "skin_big_bang", "tok-3"); assert.equal(r.status, 200); assert.equal(r.body.skin, "big_bang"); assert.equal(r.body.balance, 4050);
r = await buy(A, SA, "skin_angel_halo", "tok-9"); assert.equal(r.status, 400);     // not sold for real money
await assert.rejects(buy(A, SA, "pack_100", "boom"));              // Google down -> index.ts answers 500, the game retries
// ref must be the token's hash (signature covers it)
r = await w(A, SA, "purchase", { product: "pack_100", token: "tok-1", ref: "0".repeat(64) }); assert.equal(r.status, 400);
// unconfigured verification -> 503, purchase stays on the phone
setVerifier(async () => null);
r = await buy(A, SA, "pack_100", "tok-new"); assert.equal(r.status, 503);
// owned skins come back with every sync (reinstall / new phone)
r = await w(A, SA, "sync", { local: 0 });
assert.deepEqual(r.body.skins, ["big_bang"]); assert.equal(r.body.account, tagA);
// dev tokens refused unless the server allows them
r = await buy(A, SA, "pack_100", "dev-123"); assert.equal(r.status, 403);
console.log("ALL PURCHASE TESTS PASSED", calls, "google calls");
