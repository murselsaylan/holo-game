import { handle, sign, signAssisted, signWallet } from "../handler.ts";
import { MemStore } from "./mem.ts";
import assert from "node:assert/strict";

const store = new MemStore();
const pid = "e".repeat(32), sec = "f".repeat(48);
const now = Date.now(), ts = Math.floor(now / 1000);
const call = (route: string, body: any) => handle(store as any, "POST", route, new URLSearchParams(), JSON.stringify(body), "7.7.7." + Math.random(), now);
const w = async (op: string, extra: any) => {
  const key = op === "sync" ? String(extra.local ?? 0) : op === "spend" ? extra.item : extra.kind;
  return call("/api/wallet", { player_id: pid, ts, op, ...extra, sig: await signWallet(sec, pid, ts, op, key, extra.ref ?? "") });
};
const rnd = () => Array.from(crypto.getRandomValues(new Uint8Array(12))).map((b) => b.toString(16).padStart(2, "0")).join("");
const submit = async (level: number, taps: number[], assists?: any[], badAsig = false) => {
  const body: any = { player_id: pid, level, ts, taps, sig: await sign(sec, pid, level, ts, taps) };
  if (assists) { body.assists = assists; body.asig = badAsig ? "00" : await signAssisted(sec, pid, level, ts, taps, assists); }
  return call("/api/submit", body);
};
await call("/api/register", { player_id: pid, secret: sec, name: "T", country: "TR" });
await w("sync", { local: 500 });

// a verified winning run of level 44 (from the live leaderboard), with bought shields put on
const t44 = [309,344,385,447,494,546,606,672,714,761,805,844,875,930,969,1008,1034,1079,1117,1153,1186,1224,1260,1294,1327,1364,1395,1427,1454,1482,1516,1552,1595,1633,1664,1718,1750,1771,1792,1818,1852,1878,1931,1974];
const help = [[0, "S"], [1000, "S"]];
let r = await submit(44, t44, help);
assert.equal(r.status, 402, "shields not paid yet -> refused");
await w("spend", { item: "shield", ref: rnd() }); await w("spend", { item: "shield", ref: rnd() });
r = await submit(44, t44, help, true); assert.equal(r.status, 403, "help list is signed");
r = await submit(44, t44, help); assert.equal(r.status, 200); assert.equal(r.body.level_score, 108806); assert.equal(r.body.levels, 44);
// the two paid shields are used up now: another assisted run needs new payments
const t3 = [139,190,244,308,362,418,475,536,604,654,730,872,924,985];
r = await submit(3, t3, [[0, "S"]]); assert.equal(r.status, 402);
// plain runs work as before
r = await submit(3, t3); assert.equal(r.status, 200); assert.equal(r.body.level_score, 24391);
// revives: the replay applies them; a run that still never reaches the goal is refused
await w("spend", { item: "revive", ref: rnd() });
r = await submit(25, [65, 121], [[200, "R"]]); assert.equal(r.status, 422);
// malformed help
r = await submit(3, t3, [[5, "X"]]); assert.equal(r.status, 400);
console.log("ALL ASSIST TESTS PASSED");
