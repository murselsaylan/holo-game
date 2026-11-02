// 1.0.11: every verified level clear pays LEVEL_WIN diamonds - once per (level, ts), at most LEVEL_WIN_PER_DAY a rolling day.
import { handle, sign, signWallet } from "../handler.ts";
import { LEVEL_WIN, LEVEL_WIN_3STAR, LEVEL_WIN_PER_DAY } from "../wallet.ts";
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
let bonus = r.body.drop?.kind === "gems" ? r.body.drop.payload : 0;       // a lucky clear drops diamonds on top
const win = LEVEL_WIN + (r.body.stars >= 3 ? LEVEL_WIN_3STAR : 0);
assert.equal(r.body.win_diamonds, win, "the clear pays (3 stars pay a little more)");
assert.equal(r.body.balance, b0 + win + bonus, "and the reply carries the new balance");
assert.equal((await clear(ts0)).body.win_diamonds, 0, "the same submission is never paid twice");
assert.equal(await sync(), b0 + win + bonus);

// a replay of the same level later pays again (different ts), until the daily cap
let paid = 1;
for (let k = 1; k < LEVEL_WIN_PER_DAY + 5; k++) {
  now += 1000;
  const x = await clear(Math.floor(now / 1000));
  assert.equal(x.status, 200);
  paid += x.body.win_diamonds > 0 ? 1 : 0;
  if (x.body.drop?.kind === "gems") bonus += x.body.drop.payload;
}
assert.equal(paid, LEVEL_WIN_PER_DAY, "at most LEVEL_WIN_PER_DAY payouts in a rolling day");
assert.equal(await sync(), b0 + win * LEVEL_WIN_PER_DAY + bonus);

// a day later the cap is open again
now += 86_400_000 + 5000;
assert.equal((await clear(Math.floor(now / 1000))).body.win_diamonds, win);
console.log("levelwin_test OK");

// finishing a sector's last level (20) pays SECTOR_WIN once, ever
import { SECTOR_WIN } from "../wallet.ts";
const taps20 = JSON.parse(readFileSync(new URL(`../../../../levels/level20.json`, import.meta.url), "utf-8")).ref_taps;
const clear20 = async (ts: number) => post("/api/submit", { player_id: id, level: 20, ts, taps: taps20, sig: await sign(secret, id, 20, ts, taps20) });
now += 3_600_000;
const s1 = await clear20(Math.floor(now / 1000));
assert.equal(s1.status, 200);
assert.equal(s1.body.sector_diamonds, SECTOR_WIN, "the sector's last level pays the sector bonus");
now += 3_600_000;
assert.equal((await clear20(Math.floor(now / 1000))).body.sector_diamonds, 0, "never twice");
console.log("sector bonus OK");

// back-pay: a pilot with verified clears from before the rewards existed gets them once, on the next wallet sync
const store2 = new MemStore();
const id2 = "c".repeat(32), secret2 = "d".repeat(48);
const post2 = (route: string, body: any) => handle(store2 as any, "POST", route, new URLSearchParams(), JSON.stringify(body), "7.7.7." + Math.random(), now);
await post2("/api/register", { player_id: id2, secret: secret2, name: "OLD", country: "TR" });
const sync2 = async () => (await post2("/api/wallet", { player_id: id2, ts: Math.floor(now / 1000), op: "sync", local: 0, ref: "", sig: await signWallet(secret2, id2, Math.floor(now / 1000), "sync", "0", "") })).body;
await sync2();
(store2 as any).playerBests = async () => [{ level: 1, stars: 3 }, { level: 2, stars: 1 }, { level: 20, stars: 3 }];
const bp = await sync2();
assert.equal(bp.backpay.diamonds, (LEVEL_WIN + LEVEL_WIN_3STAR) * 2 + LEVEL_WIN + SECTOR_WIN, "3 levels + the finished sector 1");
assert.equal(bp.backpay.sectors, 1);
assert.equal((await sync2()).backpay, null, "paid once");
console.log("backpay OK");

// the bonus drop: deterministic per clear, every kind shows up over many clears, expected rates are roughly right
const store3 = new MemStore();
const id3 = "e".repeat(32), secret3 = "f".repeat(48);
const post3 = (route: string, body: any) => handle(store3 as any, "POST", route, new URLSearchParams(), JSON.stringify(body), "8.8.8." + Math.random(), now);
await post3("/api/register", { player_id: id3, secret: secret3, name: "DROP", country: "TR" });
await post3("/api/wallet", { player_id: id3, ts: Math.floor(now / 1000), op: "sync", local: 0, ref: "", sig: await signWallet(secret3, id3, Math.floor(now / 1000), "sync", "0", "") });
const tally: Record<string, number> = { shield: 0, revive: 0, gems: 0, none: 0 };
let clears = 0;
for (let k = 0; k < 400; k++) {
  now += 3_000_000;                            // 50 min apart: under the daily cap of 30 payouts
  const ts3 = Math.floor(now / 1000);
  const x = await post3("/api/submit", { player_id: id3, level: 1, ts: ts3, taps: refTaps, sig: await sign(secret3, id3, 1, ts3, refTaps) });
  if (x.body.win_diamonds > 0) { clears++; tally[x.body.drop ? x.body.drop.kind : "none"]++; }
}
assert.ok(clears > 300, "most clears were paid: " + clears);
assert.ok(tally.shield > 0 && tally.revive > 0 && tally.gems > 0, "every drop kind shows up: " + JSON.stringify(tally));
const dropRate = (tally.shield + tally.revive + tally.gems) / clears;
assert.ok(dropRate > 0.15 && dropRate < 0.50, "a bonus on roughly a third of the 3-star clears: " + dropRate.toFixed(2));
console.log("drops OK", JSON.stringify(tally));
