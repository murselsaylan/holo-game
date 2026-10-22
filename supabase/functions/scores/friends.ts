// Friends (1.0.9): invite codes, friend requests, a free daily gift, "I am stuck" help requests, pokes and level
// challenges. Everything a friend can receive is generated HERE (the client only names a friend / a request): gifts and
// rewards come from the tables below, are written once per (player, reason, ref) in wallet_log and are capped per day.
// A sender's own wallet is never touched by a gift. Shield / revive "credits" are zero-delta wallet_log rows
// (reason fcredit:<item>) that the spend op consumes before it charges diamonds (see handler.ts wallet()).
import type { WalletStore } from "./wallet.ts";
import { MAX_LEVELS } from "./sim.ts";

export const MAX_FRIENDS = 30;               // accepted + pending, per player
export const GIFT_DIAMONDS = 5;              // a diamond gift; the other kind is a shield credit
export const GIFTS_SENT_PER_DAY = 10;
export const GIFT_RECV_DIAMONDS_PER_DAY = 30;  // diamonds one player can collect from gifts a day (the rest waits)
export const POKES_PER_DAY = 20;
export const HELP_ASKS_PER_DAY = 3;
export const HELP_MAX_AGE_S = 86_400;
export const HELPER_REWARD = 5;              // the friend who answers a help request ...
export const HELPER_DAY_CAP = 25;
export const ASKER_REWARD = 3;               // ... and the one who asked
export const ASKER_DAY_CAP = 9;
export const CHALLENGE_REWARD = 5;           // both sides when the challenged friend clears the level
export const CHALLENGE_DAY_CAP = 20;
export const CHALLENGES_PER_DAY = 5;
export const MSG_KEEP_S = 7 * 86_400;
// invite reward: whoever redeems a friend code as a brand-new pilot (no verified clear yet) is an invitee - once per account
// (friend_invites.invitee is the key). Paid when the invitee's FIRST verified level clear is recorded: invitee + inviter.
export const INVITEE_REWARD = 30;
export const INVITER_REWARD = 50;
export const INVITER_DAY_CAP = 3;            // paid invites per inviter per UTC day
export const INVITER_TOTAL_CAP = 10;         // ... and in total

export interface FriendRow { id: string; name: string; country: string; levels: number; score: number; stars: number;
                             frame?: string; title?: string;
                             status: "friend" | "incoming" | "outgoing" }
export interface Msg { id: number; from: string; from_name: string; to: string; kind: "gift" | "poke" | "challenge" | "help";
                       level: number; item: string; amount: number; day: number; created: number; claimed: number; answered_by: string }
export interface Sent { to: string; kind: string }

export interface FriendStore extends WalletStore {
  /** The player's invite code (made on first call). */
  friendCode(pid: string): Promise<string>;
  playerByCode(code: string): Promise<{ id: string; name: string } | null>;
  /** Every relation of the player (friends, requests received, requests sent) joined with the other player's standing. */
  friendLinks(pid: string): Promise<FriendRow[]>;
  /** Asks b to be a's friend; if b already asked a they become friends. */
  friendAsk(a: string, b: string, now: number): Promise<"pending" | "accepted" | "exists" | "full">;
  friendAccept(me: string, other: string): Promise<boolean>;
  friendRemove(me: string, other: string): Promise<void>;
  areFriends(a: string, b: string): Promise<boolean>;
  /** Stores a message; null when that (from, to, kind, day) already exists (the daily limit). */
  msgAdd(m: { from: string; to: string; kind: Msg["kind"]; level: number; item: string; amount: number; day: number; created: number }): Promise<number | null>;
  msg(id: number): Promise<Msg | null>;
  /** Unclaimed messages for `to` (not help requests), newest first. */
  inbox(to: string, since: number): Promise<Msg[]>;
  /** Marks a message claimed (only if it still is not). */
  msgClaim(id: number, now: number): Promise<boolean>;
  /** What `from` sent on `day` (to whom, which kind). */
  sentOn(from: string, day: number): Promise<Sent[]>;
  /** Open help requests (unanswered, newer than `since`) of the player's accepted friends. */
  helpOpen(pid: string, since: number): Promise<Msg[]>;
  /** Answers a request once: the first helper wins. Returns the request, or null if it was taken / is gone. */
  helpAnswer(id: number, helper: string, now: number): Promise<Msg | null>;
  /** Shield / revive credits left (granted by friends, not used yet). */
  friendCredits(pid: string, item: "shield" | "revive"): Promise<number>;
  hasBest(pid: string, level: number): Promise<boolean>;
  /** Records that `invitee` came through `inviter`'s code; false when the invitee already has an invite row. */
  inviteSet(invitee: string, inviter: string, now: number): Promise<boolean>;
  inviteGet(invitee: string): Promise<{ inviter: string; paid: number } | null>;
  /** Marks the invite paid (once, atomically). */
  invitePay(invitee: string, now: number): Promise<boolean>;
  /** The best clean runs of the player's accepted friends on a level, best first. */
  friendBests(pid: string, level: number, n: number): Promise<{ id: string; name: string; score: number; taps: number[] }[]>;
}

export interface FReply { status: number; body: Record<string, unknown> }
const R = (status: number, body: Record<string, unknown>): FReply => ({ status, body });

const CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
export const normFriendCode = (c: unknown) => String(c ?? "").toUpperCase().replace(/[^A-Z0-9]/g, "");
export function newFriendCode(): string {
  const b = crypto.getRandomValues(new Uint8Array(8));
  return Array.from(b).map((x) => CODE_ALPHABET[x & 31]).join("");
}
export const showCode = (c: string) => `${c.slice(0, 4)}-${c.slice(4)}`;

export const dayOf = (nowMs: number) => Math.floor(nowMs / 86_400_000);

async function digestByte(s: string): Promise<number> {
  const h = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s));
  return new Uint8Array(h)[0];
}

/** What a gift holds, decided by the server alone: one in three is a shield, the rest are GIFT_DIAMONDS. */
export async function pickGift(from: string, to: string, day: number): Promise<{ item: "diamond" | "shield"; amount: number }> {
  const b = await digestByte(`holo-gift|${from}|${to}|${day}`);
  return b % 3 === 0 ? { item: "shield", amount: 1 } : { item: "diamond", amount: GIFT_DIAMONDS };
}

/** What a help request grants the asker: a shield or a revive (server's pick, 1 revive in 3). */
export async function pickHelp(from: string, level: number, day: number): Promise<"shield" | "revive"> {
  return (await digestByte(`holo-help|${from}|${level}|${day}`)) % 3 === 0 ? "revive" : "shield";
}

const msgView = (m: Msg) => ({ id: m.id, from: m.from, from_name: m.from_name, kind: m.kind, level: m.level, item: m.item,
                               amount: m.amount, created: m.created });

/** Pays a capped friend reward once: `reason` is capped per UTC day, (reason, ref) is unique. Returns diamonds added. */
async function capped(store: FriendStore, pid: string, amount: number, cap: number, reason: string, ref: string,
                      now: number): Promise<{ added: number; balance: number | null }> {
  const bal = await store.walletBalance(pid);
  if (bal === null) return { added: 0, balance: null };                 // never opened a wallet: no phantom wallet
  const today = await store.walletSum(pid, reason, Math.floor(now / 86_400) * 86_400);
  const n = Math.max(0, Math.min(amount, cap - today));
  if (n <= 0) return { added: 0, balance: bal };
  const r = await store.walletChange(pid, n, reason, ref, now);
  return { added: r.dup ? 0 : n, balance: r.balance };
}

export interface Ctx { store: FriendStore; pid: string; name: string; now: number }

/** The player's whole friends state: code, relations, what waits in the inbox, open help requests, credits. */
export async function overview(c: Ctx): Promise<Record<string, unknown>> {
  const { store, pid, now } = c;
  const day = Math.floor(now / 86_400);
  const [code, links, sent, inbox, help, shield, revive] = await Promise.all([
    store.friendCode(pid), store.friendLinks(pid), store.sentOn(pid, day), store.inbox(pid, now - MSG_KEEP_S),
    store.helpOpen(pid, now - HELP_MAX_AGE_S), store.friendCredits(pid, "shield"), store.friendCredits(pid, "revive"),
  ]);
  const sentBy = new Map<string, string[]>();
  for (const s of sent) sentBy.set(s.to, [...(sentBy.get(s.to) ?? []), s.kind]);
  return {
    ok: true, code: showCode(code), max: MAX_FRIENDS,
    friends: links.map((f) => ({ ...f, sent: sentBy.get(f.id) ?? [] })),
    inbox: inbox.map(msgView), help: help.map(msgView),
    credits: { shield, revive }, asked_today: sent.filter((s) => s.kind === "help").length,
  };
}

/** Pays the invite reward once the invitee has a verified clear (called after a recorded run and on wallet sync).
 *  Nothing is paid (and the invite stays open) while either wallet was never opened. */
export async function settleInvite(store: FriendStore, invitee: string, levels: number, now: number): Promise<{ added: number } | null> {
  if (levels < 1 || typeof store.inviteGet !== "function") return null;      // (minimal test stores have no invites)
  const inv = await store.inviteGet(invitee);
  if (!inv || inv.paid || inv.inviter === invitee) return null;
  if ((await store.walletBalance(invitee)) === null || (await store.walletBalance(inv.inviter)) === null) return null;
  if (!(await store.invitePay(invitee, now))) return null;                      // someone else settled it first
  const me = await store.walletChange(invitee, INVITEE_REWARD, "finvited", "once", now);
  const dayStart = Math.floor(now / 86_400) * 86_400;
  const total = (await store.walletCount(inv.inviter, "finvite", 0)).n;
  const today = (await store.walletCount(inv.inviter, "finvite", dayStart)).n;
  if (total < INVITER_TOTAL_CAP && today < INVITER_DAY_CAP) {
    await store.walletChange(inv.inviter, INVITER_REWARD, "finvite", invitee, now);
  }
  return { added: me.dup ? 0 : INVITEE_REWARD };
}

export async function friendsOp(store: FriendStore, pl: { id: string; name: string; levels?: number }, op: string, arg: string,
                                nowMs: number): Promise<FReply> {
  const now = Math.floor(nowMs / 1000), day = dayOf(nowMs);
  const c: Ctx = { store, pid: pl.id, name: pl.name, now };
  if (op === "list") return R(200, await overview(c));

  if (op === "add") {
    const code = normFriendCode(arg);
    if (code.length !== 8) return R(400, { error: "bad code" });
    const other = await store.playerByCode(code);
    if (!other) return R(404, { error: "unknown code" });
    if (other.id === pl.id) return R(400, { error: "that is your own code" });
    const st = await store.friendAsk(pl.id, other.id, now);
    if (st === "full") return R(409, { error: "friend list full" });
    // a pilot with no verified clear yet who redeems a code is an invitee (one inviter per account, ever)
    const invite = (pl.levels ?? 1) === 0 && await store.inviteSet(pl.id, other.id, now);
    return R(200, { ok: true, state: st, name: other.name, invite });
  }
  if (op === "accept" || op === "remove") {
    if (!/^[0-9a-f]{32}$/.test(arg)) return R(400, { error: "bad player" });
    if (op === "accept") {
      if (!(await store.friendAccept(pl.id, arg))) return R(404, { error: "no such request" });
    } else {
      await store.friendRemove(pl.id, arg);
    }
    return R(200, { ok: true });
  }

  if (op === "gift" || op === "poke") {
    if (!/^[0-9a-f]{32}$/.test(arg)) return R(400, { error: "bad player" });
    if (!(await store.areFriends(pl.id, arg))) return R(403, { error: "not friends" });
    const sent = await store.sentOn(pl.id, day);
    if (sent.filter((s) => s.kind === op).length >= (op === "gift" ? GIFTS_SENT_PER_DAY : POKES_PER_DAY)) {
      return R(429, { error: "daily limit" });
    }
    const g = op === "gift" ? await pickGift(pl.id, arg, day) : { item: "", amount: 0 };
    const id = await store.msgAdd({ from: pl.id, to: arg, kind: op, level: 0, item: g.item, amount: g.amount, day, created: now });
    if (id === null) return R(409, { error: "already sent today" });
    return R(200, { ok: true, id });
  }

  if (op === "challenge") {
    const m = /^([0-9a-f]{32}):(\d{1,4})$/.exec(arg);
    if (!m) return R(400, { error: "bad challenge" });
    const level = Number(m[2]);
    if (level < 1 || level > MAX_LEVELS) return R(400, { error: "bad level" });
    if (!(await store.areFriends(pl.id, m[1]))) return R(403, { error: "not friends" });
    if (!(await store.hasBest(pl.id, level))) return R(403, { error: "clear the level first" });
    if (await store.hasBest(m[1], level)) return R(409, { error: "friend already cleared it" });
    const sent = await store.sentOn(pl.id, day);
    if (sent.filter((s) => s.kind === "challenge").length >= CHALLENGES_PER_DAY) return R(429, { error: "daily limit" });
    const id = await store.msgAdd({ from: pl.id, to: m[1], kind: "challenge", level, item: "", amount: CHALLENGE_REWARD, day, created: now });
    if (id === null) return R(409, { error: "already sent today" });
    return R(200, { ok: true, id });
  }

  if (op === "claim") {
    const id = Number(arg);
    const msg = Number.isInteger(id) && id > 0 ? await store.msg(id) : null;
    if (!msg || msg.to !== pl.id || msg.kind === "help") return R(404, { error: "no such message" });
    if (msg.claimed) return R(200, { ok: true, added: 0, dup: true, balance: await store.walletBalance(pl.id) });
    if (now - msg.created > MSG_KEEP_S) return R(410, { error: "expired" });
    const bal = await store.walletBalance(pl.id);
    if (bal === null) return R(409, { error: "sync first" });
    if (msg.kind === "poke") {
      await store.msgClaim(id, now);
      return R(200, { ok: true, added: 0, balance: bal });
    }
    if (msg.kind === "gift") {
      // the contents were fixed when it was sent; the amounts below are the server's, never the message's say-so
      if (msg.item === "shield") {
        const r = await store.walletChange(pl.id, 0, "fcredit:shield", `m${id}`, now);
        await store.msgClaim(id, now);
        return R(200, { ok: true, item: "shield", added: 0, balance: r.balance });
      }
      const r = await capped(store, pl.id, GIFT_DIAMONDS, GIFT_RECV_DIAMONDS_PER_DAY, "fgift", `m${id}`, now);
      if (r.added === 0 && !(await store.walletRefs(pl.id, "fgift", now - MSG_KEEP_S)).includes(`m${id}`)) {
        return R(429, { error: "daily limit", balance: r.balance });         // stays in the inbox for tomorrow
      }
      await store.msgClaim(id, now);
      return R(200, { ok: true, item: "diamond", added: r.added, balance: r.balance });
    }
    if (msg.kind === "challenge") {
      if (!(await store.hasBest(pl.id, msg.level))) return R(409, { error: "level not cleared yet", balance: bal });
      const mine = await capped(store, pl.id, CHALLENGE_REWARD, CHALLENGE_DAY_CAP, "fchal", `m${id}`, now);
      await capped(store, msg.from, CHALLENGE_REWARD, CHALLENGE_DAY_CAP, "fchal", `m${id}`, now);
      await store.msgClaim(id, now);
      return R(200, { ok: true, item: "challenge", added: mine.added, balance: mine.balance });
    }
    return R(400, { error: "bad message" });
  }

  if (op === "help_ask") {
    const level = Number(arg);
    if (!Number.isInteger(level) || level < 1 || level > MAX_LEVELS) return R(400, { error: "bad level" });
    const links = await store.friendLinks(pl.id);
    if (!links.some((f) => f.status === "friend")) return R(409, { error: "no friends" });
    const sent = await store.sentOn(pl.id, day);
    if (sent.filter((s) => s.kind === "help").length >= HELP_ASKS_PER_DAY) return R(429, { error: "daily limit" });
    const item = await pickHelp(pl.id, level, day);
    const id = await store.msgAdd({ from: pl.id, to: "", kind: "help", level, item, amount: 1, day, created: now });
    if (id === null) return R(409, { error: "already asked for this level today" });
    return R(200, { ok: true, id, item });
  }

  if (op === "help_send") {
    const id = Number(arg);
    const open = (await store.helpOpen(pl.id, now - HELP_MAX_AGE_S)).find((m) => m.id === id);
    if (!open) return R(404, { error: "request gone" });                      // not a friend's, answered, or too old
    if ((await store.walletBalance(open.from)) === null) return R(409, { error: "request gone" });   // no wallet to credit
    const taken = await store.helpAnswer(id, pl.id, now);
    if (!taken) return R(409, { error: "someone already helped" });
    const item = taken.item === "revive" ? "revive" : "shield";
    // the asker gets the credit and a small reward, the helper a small reward - each once, each capped per day
    await store.walletChange(taken.from, 0, `fcredit:${item}`, `h${id}`, now);
    const asker = await capped(store, taken.from, ASKER_REWARD, ASKER_DAY_CAP, "fhelped", `h${id}`, now);
    const mine = await capped(store, pl.id, HELPER_REWARD, HELPER_DAY_CAP, "fhelp", `h${id}`, now);
    return R(200, { ok: true, item, added: mine.added, balance: mine.balance, asker_added: asker.added });
  }

  return R(400, { error: "bad op" });
}
