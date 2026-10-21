// Endless climb endpoints: node supabase/functions/scores/tests/endless_test.ts  (after python tools/endless_golden.py)
import { readFileSync } from "node:fs";
import assert from "node:assert/strict";
import { handle, sha256Hex, signEndless, signWallet } from "../handler.ts";
import { MemStore } from "./mem.ts";
import { ENDLESS_VERSION, DIAMONDS_PER_DAY, DIAMOND_EVERY_M, GOALS, poolDigest, replayEndless, weekOf } from "../endless.ts";

const golden = JSON.parse(readFileSync(new URL("../endless_golden_v5.json", import.meta.url), "utf-8")).filter((g: any) => g.py);
const store = new MemStore();
const pid = "a".repeat(32), sec = "b".repeat(48);
const now = Date.now(), ts = Math.floor(now / 1000);
const week = weekOf(ts);
const post = (route: string, body: any, at = now) =>
  handle(store as any, "POST", route, new URLSearchParams(), JSON.stringify(body), "9.9.9." + Math.random(), at);
const get = (route: string, q: Record<string, string>) =>
  handle(store as any, "GET", route, new URLSearchParams(q), "", "9.9.8." + Math.random(), now);

// the golden climbs belong to other seeds: take the longest one's nonce and taps, re-measured for this week's seed
const best = golden.reduce((a: any, g: any) => (g.py.metres > a.py.metres ? g : a));
const nonce = String(best.seed).split("|").pop();
const taps: number[] = best.taps;
const end: number = best.end ?? best.py.n;
const expected = replayEndless(`HOLO-ENDLESS|${week}|v${ENDLESS_VERSION}|${nonce}`, taps, end);

async function submit(extra: any = {}, at = now) {
  const t = Math.floor(at / 1000);
  const body: any = { player_id: pid, week, nonce, taps, end, ts: t, v: ENDLESS_VERSION, pool: poolDigest(), ...extra };
  body.sig = extra.sig ?? await signEndless(sec, pid, body.week, body.nonce, body.end, t, await sha256Hex(body.taps.join(",")));
  return post("/api/endless/submit", body, at);
}

await post("/api/register", { player_id: pid, secret: sec, name: "CLIMBER", country: "TR" });
let r = await submit({ sig: "00" });
assert.equal(r.status, 403, "bad signature");
r = await submit({ pool: "deadbeef" });
assert.equal(r.status, 409, "outdated pool");
r = await submit({ week: "2020-W01" });
assert.equal(r.status, 410, "closed week");
r = await submit({ taps: [10, 12] });
assert.equal(r.status, 422, "taps faster than a human");

// no wallet yet: ranked, no diamonds
r = await submit();
assert.equal(r.status, 200, JSON.stringify(r.body));
assert.equal(r.body.metres, expected.metres, "server height = replay");
assert.equal(r.body.points, expected.points, "server points = replay (height + stars)");
assert.equal(r.body.rank, 1);
assert.equal(r.body.added, 0);

// wallet open: the same run pays nothing twice, a new nonce pays floor(m / 500) (capped per day)
await post("/api/wallet", { player_id: pid, ts, op: "sync", local: 0, ref: "",
                            sig: await signWallet(sec, pid, ts, "sync", "0", "") });
const earn = Math.floor(expected.metres / DIAMOND_EVERY_M);
r = await submit();
assert.equal(r.status, 200);
assert.equal(r.body.added, Math.min(DIAMONDS_PER_DAY, earn), "first paid submit");
const again = await submit();
assert.equal(again.body.added, 0, "same run is paid once");
// daily cap: pretend 20 were already paid today
store.log.push({ pid, reason: "endless", ref: "x", delta: DIAMONDS_PER_DAY, created: ts });
const capped = await submit({ nonce: "1234abcd" });
assert.equal(capped.status, 200);
assert.equal(capped.body.added, 0);
if (Math.floor(capped.body.metres / DIAMOND_EVERY_M) > 0) assert.equal(capped.body.capped, true);

// a second player below the first: board order + standing
const pid2 = "c".repeat(32), sec2 = "d".repeat(48);
await post("/api/register", { player_id: pid2, secret: sec2, name: "SECOND", country: "DE" });
const b2: any = { player_id: pid2, week, nonce: "00000001", taps: [], end: 60, ts, v: ENDLESS_VERSION, pool: poolDigest() };
b2.sig = await signEndless(sec2, pid2, week, b2.nonce, b2.end, ts, await sha256Hex(""));
r = await post("/api/endless/submit", b2);
assert.equal(r.status, 200, JSON.stringify(r.body));
const board = await get("/api/endless/board", { week, player_id: pid2, limit: "10" });
assert.equal(board.status, 200);
assert.equal(board.body.rows[0].name, "CLIMBER");
assert.equal(board.body.total, 2);
assert.equal(board.body.me.rank, 2);
// v5 metre goals: paid once per player and week, by the measured height; v4 games get none
{
  const saved = GOALS.splice(0, GOALS.length, [1, 3], [2, 4]);          // tiny goals any climb reaches
  const pid3 = "e".repeat(32), sec3 = "f".repeat(48);
  await post("/api/register", { player_id: pid3, secret: sec3, name: "GOALIE", country: "TR" });
  await post("/api/wallet", { player_id: pid3, ts, op: "sync", local: 0, ref: "", sig: await signWallet(sec3, pid3, ts, "sync", "0", "") });
  const run = async (nonce: string, v: number) => {
    const b: any = { player_id: pid3, week, nonce, taps, end, ts, v, pool: poolDigest(v) };
    b.sig = await signEndless(sec3, pid3, week, nonce, end, ts, await sha256Hex(taps.join(",")));
    return post("/api/endless/submit", b);
  };
  if (expected.metres >= 2) {
    const g1 = await run("0000aaaa", 5);
    assert.equal(g1.status, 200, JSON.stringify(g1.body));
    assert.deepEqual(g1.body.goals, [[1, 3], [2, 4]], "both goals paid");
    const g2 = await run("0000bbbb", 5);
    assert.deepEqual(g2.body.goals, [], "goals are paid once per week");
    const bal = (await post("/api/wallet", { player_id: pid3, ts, op: "sync", local: 0, ref: "", sig: await signWallet(sec3, pid3, ts, "sync", "0", "") })).body.balance;
    assert.ok(bal >= 7, "goal diamonds are in the wallet: " + bal);
  }
  const v4 = await run("0000cccc", 4);
  assert.equal(v4.status, 200, "v4 games are still replayed: " + JSON.stringify(v4.body));
  assert.deepEqual(v4.body.goals, [], "v4 games get no goals");
  GOALS.splice(0, GOALS.length, ...saved);
}
console.log("ALL ENDLESS TESTS PASSED", { metres: expected.metres, paid: Math.min(DIAMONDS_PER_DAY, earn) });
