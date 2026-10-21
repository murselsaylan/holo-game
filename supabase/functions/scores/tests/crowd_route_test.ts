// Route /api/crowd through handle() (signatures, rate limits, the submit hook): node tests/duel_route_test.ts
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { handle, sign, signLive, sha256Hex, signWallet } from "../handler.ts";
import { MemStore } from "./mem.ts";
import { MemLive } from "./live_mem.ts";
import { crowdWeekKey } from "../crowd.ts";

// deno-lint-ignore no-explicit-any
const store: any = new MemStore();
store.live = new MemLive();
const A = "a".repeat(32), SA = "1".repeat(48), B = "b".repeat(32), SB = "2".repeat(48);
const now = Date.now(), ts = Math.floor(now / 1000);
// deno-lint-ignore no-explicit-any
const call = (route: string, body: any, t = now) => handle(store, "POST", route, new URLSearchParams(), JSON.stringify(body), "9.9.9." + Math.random(), t);
// deno-lint-ignore no-explicit-any
// deno-lint-ignore no-explicit-any
const crowd = async (pid: string, sec: string, op: string, arg = ""): Promise<any> =>
  await call("/api/crowd", { player_id: pid, ts, op, arg, sig: await signLive(sec, pid, ts, "crowd", op, arg, "") });
for (const [p, s] of [[A, SA], [B, SB]]) {
  await call("/api/register", { player_id: p, secret: s, name: p[0].toUpperCase(), country: "TR" });
  const o = await call("/api/wallet", { player_id: p, ts, op: "sync", local: 0, sig: await signWallet(s, p, ts, "sync", "0", "") });
  assert.equal(o.status, 200);
}
// a clear of level 3 puts its stars into the shared goal and makes level 4 playable
const ref3 = JSON.parse(readFileSync(new URL("../../../../levels/level3.json", import.meta.url), "utf-8")).ref_taps;
const sub = await call("/api/submit", { player_id: A, level: 3, ts, taps: ref3, sig: await sign(SA, A, 3, ts, ref3) });
assert.equal(sub.status, 200);
let st = await crowd(A, SA, "status");
assert.equal(st.status, 200); assert.equal(st.body.week, crowdWeekKey(now));
assert.equal(st.body.total, sub.body.stars, "the run's stars joined the counter");
assert.equal(st.body.mine, sub.body.stars);
// bad signature / unsigned / wrong op
let r = await call("/api/crowd", { player_id: A, ts, op: "status", arg: "", sig: "00" });
assert.equal(r.status, 403);
r = await crowd(A, SA, "nope"); assert.equal(r.status, 400);
console.log("ALL CROWD ROUTE TESTS PASSED");
