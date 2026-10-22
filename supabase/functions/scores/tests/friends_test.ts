// Friends (friends.ts): codes + requests, daily gifts, pokes, challenges, help requests, friend ghost, free shields.
import { handle, sign, signFriends, signWallet } from "../handler.ts";
import { GIFT_DIAMONDS, GIFT_RECV_DIAMONDS_PER_DAY, HELPER_REWARD, ASKER_REWARD, CHALLENGE_REWARD, HELP_ASKS_PER_DAY, pickGift } from "../friends.ts";
import { MemStore } from "./mem.ts";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { DIGESTS } from "../levels_data.ts";

const store = new MemStore();
let now = Date.UTC(2026, 9, 20, 12, 0, 0);
const P = (c: string) => c.repeat(32), S = (c: string) => c.repeat(48);
const A = P("a"), B = P("b"), C = P("c"), D = P("d");
const sec: Record<string, string> = { [A]: S("1"), [B]: S("2"), [C]: S("3"), [D]: S("4") };
const post = (route: string, body: any) => handle(store as any, "POST", "/functions/v1/scores" + route, new URLSearchParams(),
  JSON.stringify(body), "9.9.9." + Math.random(), now);
const fr = async (who: string, op: string, arg = "", badSig = false) => {
  const ts = Math.floor(now / 1000);
  return post("/api/friends", { player_id: who, ts, op, arg, sig: badSig ? "00" : await signFriends(sec[who], who, ts, op, arg) });
};
const w = async (who: string, op: string, extra: any = {}) => {
  const ts = Math.floor(now / 1000);
  const key = op === "sync" ? String(extra.local ?? 0) : extra.item ?? extra.kind ?? "";
  return post("/api/wallet", { player_id: who, ts, op, ...extra, sig: await signWallet(sec[who], who, ts, op, key, extra.ref ?? "") });
};
const rnd = () => Array.from(crypto.getRandomValues(new Uint8Array(12))).map((b) => b.toString(16).padStart(2, "0")).join("");
const refTaps = (n: number) => JSON.parse(readFileSync(new URL(`../../../../levels/level${n}.json`, import.meta.url), "utf-8")).ref_taps;
const submit = async (who: string, level: number, taps: number[]) => {
  const ts = Math.floor(now / 1000);
  return post("/api/submit", { player_id: who, level, ts, taps, sig: await sign(sec[who], who, level, ts, taps) });
};

for (const [id, n] of [[A, "ALICE"], [B, "BOB"], [C, "CARA"], [D, "DAN"]]) {
  assert.equal((await post("/api/register", { player_id: id, secret: sec[id], name: n, country: "TR" })).status, 200);
  assert.equal((await w(id, "sync", { local: 100 })).status, 200);
}

// ---- signature + codes + requests ----------------------------------------------------------------------------------
assert.equal((await fr(A, "list", "", true)).status, 403, "friends ops are signed");
let r = await fr(A, "list");
assert.equal(r.status, 200); assert.match(String(r.body.code), /^[A-Z2-9]{4}-[A-Z2-9]{4}$/);
const codeA = String(r.body.code), codeB = String((await fr(B, "list")).body.code);
assert.equal(String((await fr(A, "list")).body.code), codeA, "the code is stable");
assert.equal((await fr(A, "add", "zzzz-zzzz")).status, 404, "unknown code");
assert.equal((await fr(A, "add", "abc")).status, 400, "malformed code");
assert.equal((await fr(A, "add", codeA)).status, 400, "own code");
r = await fr(A, "add", codeB.toLowerCase()); assert.equal(r.status, 200); assert.equal(r.body.state, "pending"); assert.equal(r.body.name, "BOB");
assert.equal((await fr(A, "add", codeB)).body.state, "exists");
let lb = (await fr(B, "list")).body as any;
assert.equal(lb.friends.length, 1); assert.equal(lb.friends[0].status, "incoming"); assert.equal(lb.friends[0].id, A);
assert.equal((await fr(A, "list")).body.friends[0].status, "outgoing");
assert.equal((await fr(A, "accept", B)).status, 404, "the requester cannot accept their own request");
assert.equal((await fr(B, "accept", C)).status, 404, "no request from C");
assert.equal((await fr(B, "accept", "nope")).status, 400);
// nothing can be sent before they are friends
assert.equal((await fr(A, "gift", B)).status, 403); assert.equal((await fr(A, "poke", B)).status, 403);
assert.equal((await fr(B, "accept", A)).status, 200);
assert.equal((await fr(A, "list")).body.friends[0].status, "friend");
// a friend's equipped frame / title travel with the row (the friends board draws them)
(store as any).players.get(B).frame = "frame_gold"; (store as any).players.get(B).title = "title_pilot";
{ const row = (await fr(A, "list")).body.friends[0]; assert.equal(row.frame, "frame_gold"); assert.equal(row.title, "title_pilot"); }
// crossed requests become friends at once
const codeC = String((await fr(C, "list")).body.code), codeD = String((await fr(D, "list")).body.code);
assert.equal((await fr(C, "add", codeD)).body.state, "pending");
assert.equal((await fr(D, "add", codeC)).body.state, "accepted");
// remove works for both sides
assert.equal((await fr(C, "remove", D)).status, 200);
assert.equal((await fr(D, "list")).body.friends.length, 0);
assert.equal((await fr(C, "add", codeD)).body.state, "pending"); assert.equal((await fr(D, "accept", C)).status, 200);

// ---- daily gift ----------------------------------------------------------------------------------------------------
const day = Math.floor(now / 86_400_000);
const expect = await pickGift(A, B, day);
r = await fr(A, "gift", B); assert.equal(r.status, 200); const giftId = Number(r.body.id);
assert.equal((await fr(A, "gift", B)).status, 409, "one gift per friend per day");
assert.equal((await fr(A, "gift", B)).status, 409);
const balA = (await w(A, "sync")).body.balance;
const inbox = (await fr(B, "list")).body.inbox as any[];
assert.equal(inbox.length, 1); assert.equal(inbox[0].kind, "gift"); assert.equal(inbox[0].item, expect.item); assert.equal(inbox[0].from_name, "ALICE");
assert.equal((await fr(C, "claim", String(giftId))).status, 404, "only the addressee can claim");
const balB = (await w(B, "sync")).body.balance as number;
r = await fr(B, "claim", String(giftId)); assert.equal(r.status, 200);
if (expect.item === "diamond") { assert.equal(r.body.added, GIFT_DIAMONDS); assert.equal(r.body.balance, balB + GIFT_DIAMONDS); }
else { assert.equal(r.body.item, "shield"); assert.equal(r.body.balance, balB); assert.equal((await w(B, "sync")).body.credits.shield, 1); }
r = await fr(B, "claim", String(giftId)); assert.equal(r.body.added, 0, "claimed once"); assert.equal(r.body.dup, true);
assert.equal((await w(A, "sync")).body.balance, balA, "the sender's wallet is untouched");
assert.equal((await fr(B, "list")).body.inbox.length, 0);
// next UTC day: another gift is possible
now += 86_400_000;
assert.equal((await fr(A, "gift", B)).status, 200);

// ---- the receiver's daily cap: gifts above it wait for tomorrow ----------------------------------------------------
{
  // write diamond gifts directly so the server's random pick does not matter
  const cap = Math.ceil(GIFT_RECV_DIAMONDS_PER_DAY / GIFT_DIAMONDS);
  const ids: number[] = [];
  for (let k = 0; k < cap + 2; k++) ids.push((await store.msgAdd({ from: A, to: C, kind: "gift", level: 0, item: "diamond", amount: GIFT_DIAMONDS, day: 1000 + k, created: Math.floor(now / 1000) })) as number);
  let paid = 0, refused = 0;
  for (const id of ids) { const x = await fr(C, "claim", String(id)); if (x.status === 200) paid += Number(x.body.added); else if (x.status === 429) refused++; }
  assert.equal(paid, GIFT_RECV_DIAMONDS_PER_DAY, "received gift diamonds are capped per day");
  assert.equal(refused, 2);
  now += 86_400_000;
  assert.equal((await fr(C, "claim", String(ids[ids.length - 1]))).status, 200, "an over-cap gift pays out the next day");
}

// ---- a shield gift becomes a free shield credit --------------------------------------------------------------------
{
  const id = (await store.msgAdd({ from: A, to: B, kind: "gift", level: 0, item: "shield", amount: 1, day: 5000, created: Math.floor(now / 1000) })) as number;
  const before = (await w(B, "sync")).body.credits.shield as number;
  r = await fr(B, "claim", String(id)); assert.equal(r.body.item, "shield");
  assert.equal((await w(B, "sync")).body.credits.shield, before + 1);
  const bal = (await w(B, "sync")).body.balance;
  r = await w(B, "spend", { item: "shield", ref: rnd() }); assert.equal(r.body.price, 0); assert.equal(r.body.balance, bal);
}

// ---- poke -----------------------------------------------------------------------------------------------------------
r = await fr(B, "poke", A); assert.equal(r.status, 200);
assert.equal((await fr(B, "poke", A)).status, 409, "one poke per friend per day");
const pk = ((await fr(A, "list")).body.inbox as any[]).find((m) => m.kind === "poke");
assert.ok(pk && pk.from_name === "BOB");
const balA2 = (await w(A, "sync")).body.balance;
r = await fr(A, "claim", String(pk.id)); assert.equal(r.status, 200); assert.equal(r.body.added, 0);
assert.equal((await w(A, "sync")).body.balance, balA2, "a poke pays nothing");

// ---- level challenge ------------------------------------------------------------------------------------------------
assert.equal((await fr(A, "challenge", `${B}:3`)).status, 403, "the challenger must have cleared the level");
assert.equal((await submit(A, 3, refTaps(3))).status, 200);
assert.equal((await fr(A, "challenge", `${B}:0`)).status, 400);
assert.equal((await fr(A, "challenge", `${C}:3`)).status, 403, "only friends");
r = await fr(A, "challenge", `${B}:3`); assert.equal(r.status, 200); const chId = Number(r.body.id);
assert.equal((await fr(A, "challenge", `${B}:3`)).status, 409, "once a day");
assert.equal((await fr(B, "claim", String(chId))).status, 409, "not cleared yet");
assert.equal((await submit(B, 3, refTaps(3))).status, 200);
const a0 = (await w(A, "sync")).body.balance as number, b0 = (await w(B, "sync")).body.balance as number;
r = await fr(B, "claim", String(chId)); assert.equal(r.status, 200); assert.equal(r.body.added, CHALLENGE_REWARD);
assert.equal((await w(A, "sync")).body.balance, a0 + CHALLENGE_REWARD, "the challenger is paid too");
assert.equal((await w(B, "sync")).body.balance, b0 + CHALLENGE_REWARD);
assert.equal((await fr(B, "claim", String(chId))).body.added, 0);
now += 86_400_000;
assert.equal((await fr(A, "challenge", `${B}:3`)).status, 409, "a friend who cleared it cannot be challenged");

// ---- help request ("I am stuck") ------------------------------------------------------------------------------------
assert.equal((await fr(C, "help_ask", "0")).status, 400);
r = await fr(D, "help_ask", "5"); assert.equal(r.status, 200); const reqId = Number(r.body.id);
assert.ok(r.body.item === "shield" || r.body.item === "revive");
assert.equal((await fr(D, "help_ask", "5")).status, 409, "once per level per day");
for (let lv = 6; lv < 6 + HELP_ASKS_PER_DAY - 1; lv++) assert.equal((await fr(D, "help_ask", String(lv))).status, 200);
assert.equal((await fr(D, "help_ask", "20")).status, 429, "asks per day are limited");
let open = (await fr(C, "list")).body.help as any[];
assert.ok(open.some((m) => m.id === reqId && m.level === 5 && m.from_name === "DAN"), "a friend sees the request");
assert.equal(((await fr(A, "list")).body.help as any[]).length, 0, "a stranger does not");
assert.equal((await fr(A, "help_send", String(reqId))).status, 404);
assert.equal((await fr(D, "help_send", String(reqId))).status, 404, "not for yourself");
const d0 = (await w(D, "sync")).body.balance as number, c0 = (await w(C, "sync")).body.balance as number;
r = await fr(C, "help_send", String(reqId)); assert.equal(r.status, 200); assert.equal(r.body.added, HELPER_REWARD);
assert.equal((await fr(C, "help_send", String(reqId))).status, 404, "answered once");
assert.equal((await w(C, "sync")).body.balance, c0 + HELPER_REWARD);
assert.equal((await w(D, "sync")).body.balance, d0 + ASKER_REWARD);
const credits = (await w(D, "sync")).body.credits;
assert.equal(credits.shield + credits.revive, 1, "the asker got one shield or revive");
// the credit is used before diamonds are charged, and a retried spend is not charged either
const item = credits.shield ? "shield" : "revive";
const sref = rnd();
r = await w(D, "spend", { item, ref: sref }); assert.equal(r.status, 200); assert.equal(r.body.price, 0); assert.equal(r.body.balance, d0 + ASKER_REWARD);
r = await w(D, "spend", { item, ref: sref }); assert.equal(r.body.balance, d0 + ASKER_REWARD);
assert.equal((await w(D, "sync")).body.credits[item], 0);
r = await w(D, "spend", { item, ref: rnd() }); assert.ok(r.body.price > 0, "no credit left: the normal price"); assert.ok(r.body.balance < d0 + ASKER_REWARD);
// a request older than a day is gone
now += 90_000_000;
assert.equal(((await fr(C, "list")).body.help as any[]).length, 0);

// ---- friend ghost ---------------------------------------------------------------------------------------------------
now = Date.now();
{
  const ts = Math.floor(now / 1000);
  assert.equal((await submit(C, 7, refTaps(7))).status, 200);
  r = await fr(D, "ghost", "7|" + DIGESTS["7"]); assert.equal(r.status, 200);
  assert.equal(r.body.id, C, "the friend's best clean run is the ghost");
  assert.ok(Array.isArray(r.body.taps) && r.body.taps.length > 0);
  r = await fr(A, "ghost", "7|" + DIGESTS["7"]); assert.equal(r.body.taps, undefined, "a stranger's run is not offered");
  assert.equal((await fr(D, "ghost", "x")).status, 400);
  assert.ok(ts > 0);
}

// ---- endless board filtered by country ------------------------------------------------------------------------------
{
  const x = await handle(store as any, "GET", "/api/endless/board", new URLSearchParams({ country: "TR" }), "", "1.1.1.1", now);
  assert.equal(x.status, 200);
}
console.log("friends_test OK");
