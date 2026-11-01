// 1.0.11: every verified level clear pays LEVEL_WIN diamonds - once per (level, ts), at most LEVEL_WIN_PER_DAY a rolling day.
import { handle, sign, signWallet } from "../handler.ts";
import { LEVEL_WIN, LEVEL_WIN_PER_DAY } from "../wallet.ts";
import { MemStore } from "./mem.ts";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const store = new MemStore();
let now = Date.UTC(2026, 10, 2, 12, 0, 0);
const id = "a".repeat(32), secret = "b".repeat(48);
const post = (route: string, body: any) => handle(store as any, "POST", route, new URLSearchParams(), JSON.stringify(body), "6.6.6." + Math.random(), now);
const sync = async (ts = Math.floor(now / 1000)) => (await post("/api/wallet", { player_id: id, ts, op: "sync", local: 0, ref: "", sig: await signWallet(secret, id, ts, "sync", "0", "") })).body.balance as number;
const refTaps = JSON.parse(readFileSync(new URL(`../../../../levels/level1.json`, import.meta.url), "utf-8")).ref_taps;
const clear = async (ts: number) => post("/api/submit", { player_id: id, level: 1, ts, taps: refTaps, sig: await sign(secret, id, 1, ts, refTaps) });

await post("/api/register", { player_id: id, secret, name: "WIN", country: "TR" });
const b0 = await sync();

const ts0 = Math.floor(now / 1000);
const r = await clear(ts0);
assert.equal(r.status, 200);
assert.equal(r.body.win_diamonds, LEVEL_WIN, "the clear pays");
assert.equal(r.body.balance, b0 + LEVEL_WIN, "and the reply carries the new balance");
assert.equal((await clear(ts0)).body.win_diamonds, 0, "the same submission is never paid twice");
assert.equal(await sync(), b0 + LEVEL_WIN);

// a replay of the same level later pays again (different ts), until the daily cap
let paid = 1;
for (let k = 1; k < LEVEL_WIN_PER_DAY + 5; k++) {
  now += 1000;
  const x = await clear(Math.floor(now / 1000));
  assert.equal(x.status, 200);
  paid += x.body.win_diamonds > 0 ? 1 : 0;
}
assert.equal(paid, LEVEL_WIN_PER_DAY, "at most LEVEL_WIN_PER_DAY payouts in a rolling day");
assert.equal(await sync(), b0 + LEVEL_WIN * LEVEL_WIN_PER_DAY);

// a day later the cap is open again
now += 86_400_000 + 5000;
assert.equal((await clear(Math.floor(now / 1000))).body.win_diamonds, LEVEL_WIN);
console.log("levelwin_test OK");
