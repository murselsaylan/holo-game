// Invite reward: a brand-new pilot who redeems a code and clears a first level pays both sides once (friends.ts settleInvite).
import { handle, sign, signFriends, signWallet } from "../handler.ts";
import { INVITEE_REWARD, INVITER_REWARD, INVITER_DAY_CAP } from "../friends.ts";
import { MemStore } from "./mem.ts";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const store = new MemStore();
const now = Date.UTC(2026, 9, 21, 12, 0, 0);
const hex = (c: string, n: number) => c.repeat(n);
const ids: string[] = [], sec: Record<string, string> = {};
const mk = (i: number) => { const id = String(i).repeat(32).slice(0, 32); sec[id] = String(i).repeat(48).slice(0, 48); return id; };
const post = (route: string, body: any) => handle(store as any, "POST", route, new URLSearchParams(), JSON.stringify(body), "5.5.5." + Math.random(), now);
const ts = Math.floor(now / 1000);
const fr = async (who: string, op: string, arg = "") => post("/api/friends", { player_id: who, ts, op, arg, sig: await signFriends(sec[who], who, ts, op, arg) });
const sync = async (who: string) => (await post("/api/wallet", { player_id: who, ts, op: "sync", local: 0, ref: "", sig: await signWallet(sec[who], who, ts, "sync", "0", "") })).body.balance as number;
const refTaps = JSON.parse(readFileSync(new URL(`../../../../levels/level1.json`, import.meta.url), "utf-8")).ref_taps;
const clear = async (who: string) => post("/api/submit", { player_id: who, level: 1, ts, taps: refTaps, sig: await sign(sec[who], who, 1, ts, refTaps) });
const reg = async (i: number) => { const id = mk(i); ids.push(id); await post("/api/register", { player_id: id, secret: sec[id], name: "P" + i, country: "TR" }); await sync(id); return id; };

const inviter = await reg(1);
const code = String((await fr(inviter, "list")).body.code);
const fresh = await reg(2);
assert.equal((await fr(fresh, "add", code)).body.invite, true, "a brand-new pilot redeeming a code is an invitee");
assert.equal((await fr(fresh, "add", code)).body.invite, false, "once per account");
const b0 = await sync(inviter), f0 = await sync(fresh);
assert.equal(await sync(fresh), f0, "nothing is paid before the first clear");
assert.equal((await clear(fresh)).status, 200);
assert.equal(await sync(fresh), f0 + INVITEE_REWARD, "invitee paid");
assert.equal(await sync(inviter), b0 + INVITER_REWARD, "inviter paid");
await clear(fresh); await post("/api/submit", { player_id: fresh, level: 1, ts, taps: refTaps, sig: await sign(sec[fresh], fresh, 1, ts, refTaps) });
assert.equal(await sync(fresh), f0 + INVITEE_REWARD, "never paid twice");
assert.equal(await sync(inviter), b0 + INVITER_REWARD);

// a pilot who already cleared a level is not an invitee; an own code is refused
const old = await reg(3);
assert.equal((await clear(old)).status, 200);
assert.equal((await fr(old, "add", code)).body.invite, false);
assert.equal((await fr(inviter, "add", code)).status, 400);

// the inviter is paid for at most INVITER_DAY_CAP invites a day (the invitees still get theirs)
let paidInviter = 0, inv0 = await sync(inviter);
for (let k = 4; k < 4 + INVITER_DAY_CAP + 2; k++) {
  const p = await reg(k);
  await fr(p, "add", code);
  const before = await sync(p);
  await clear(p);
  assert.equal(await sync(p), before + INVITEE_REWARD);
}
paidInviter = (await sync(inviter) - inv0) / INVITER_REWARD;
assert.equal(paidInviter, INVITER_DAY_CAP - 1, "daily cap counts the invite already paid today");
// an open invite waits for the wallet: not paid while the inviter has no wallet
const ghostInviter = String(8).repeat(32); sec[ghostInviter] = String(8).repeat(48);
store.players.set(ghostInviter, { id: ghostInviter, secret: sec[ghostInviter], name: "G", country: "TR", levels: 0, score: 0, stars: 0, diamonds: null, gift: 0, friend_code: "GHOSTGHO" });
const late = await reg(9);
assert.equal((await fr(late, "add", "GHOSTGHO")).body.invite, true);
const l0 = await sync(late);
await clear(late);
assert.equal(await sync(late), l0, "open while the inviter's wallet never opened");
console.log("invite_test OK", hex("x", 1));
