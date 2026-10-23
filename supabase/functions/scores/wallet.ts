// Server-side diamond wallet. The balance lives in players.diamonds; every change goes through here with a server
// price / reward table and is logged once per (player, reason, ref) in wallet_log, so retries never double-count.
import { weeklySkinPrice } from "./rotation.ts";
import { ACH_IDS, DAILY, EVENTS, LOGIN_REWARDS, PACKS, PREMIUM_SKINS, SHIELD_COST, SKIN_COST, STREAK_WEEKS, WEEKLY } from "./wallet_data.ts";

export const REVIVE_COST = 20;
export const WELCOME_GIFT = 30;
export const TUTORIAL_REWARD = 20;           // 1.1.0: finishing the first-run tutorial (Level 0), once per account
export const ACH_REWARD = 5;
export const AD_REWARD = 50;                 // 1.0.8: the developer's choice - 50 a video, watch as many as you like
export const AD_MAX_PER_DAY = 30;             // only a safety cap: the claim comes from the game, a forged one cannot mint more
export const ADREVIVE_MAX_PER_DAY = 10;       // "watch an ad to continue": pays one revive (REVIVE_COST), then spent
export const AD_MIN_GAP_S = 15;               // no video is shorter
/** The old local balance moves into the wallet on the first sync as it is (no limit, by the developer's choice);
 *  only clamped far below the INTEGER range so later additions can never overflow. WALLET_IMPORT_CAP overrides. */
export const IMPORT_CAP = Number((globalThis as any).Deno?.env?.get?.("WALLET_IMPORT_CAP") ?? 1_000_000_000) || 1_000_000_000;

export interface WalletOpen { balance: number; imported: number | null; gift: number }
export interface WalletChange { ok: boolean; balance: number; dup: boolean }

export type PurchaseResult = { status: "ok" | "dup" | "other_player"; balance: number };

export interface WalletStore {
  /** First call imports `local` (capped) into an empty wallet; every call hands out a pending gift. */
  walletOpen(pid: string, local: number, cap: number, now: number): Promise<WalletOpen>;
  /** Balance or null while the wallet was never opened. */
  walletBalance(pid: string): Promise<number | null>;
  /** Atomic +/- delta; refuses to go below zero; (reason, ref) already logged -> dup, nothing changes. */
  walletChange(pid: string, delta: number, reason: string, ref: string, now: number): Promise<WalletChange>;
  /** How many `reason` entries since `since` (unix s) and the newest one's time. */
  walletCount(pid: string, reason: string, since: number): Promise<{ n: number; last: number }>;
  /** The refs of the `reason` entries since `since` (unix s) - e.g. the dates of the recent daily logins. */
  walletRefs(pid: string, reason: string, since: number): Promise<string[]>;
  /** Sum of the `reason` deltas since `since` (unix s) - e.g. endless diamonds paid out today. */
  walletSum(pid: string, reason: string, since: number): Promise<number>;
  /** Records a verified store purchase once per token (hash) and credits `diamonds` (0 for skins), atomically. */
  walletPurchase(pid: string, tokenHash: string, product: string, orderId: string, diamonds: number,
                 now: number): Promise<PurchaseResult>;
  /** Skins this account owns on the server (bought for diamonds or real money). */
  walletSkins(pid: string): Promise<string[]>;
}

/** What the game puts into BillingFlowParams.setObfuscatedAccountId: ties a purchase to one player account. */
export async function accountTag(pid: string): Promise<string> {
  const h = await crypto.subtle.digest("SHA-256", new TextEncoder().encode("holo-account|" + pid));
  return Array.from(new Uint8Array(h)).map((b) => b.toString(16).padStart(2, "0")).join("");
}

/** The one-time "remove ads" purchase: no interstitials between levels on this account (kept like a skin). */
export const REMOVE_ADS = "remove_ads";

export function productValue(product: string): { diamonds: number; skin: string | null; noads?: boolean } | null {
  if (product in PACKS) return { diamonds: (PACKS as Record<string, number>)[product], skin: null };
  if (product === REMOVE_ADS) return { diamonds: 0, skin: null, noads: true };
  if (product.startsWith("skin_") && (PREMIUM_SKINS as readonly string[]).includes(product.slice(5))) {
    return { diamonds: 0, skin: product.slice(5) };
  }
  return null;
}

const DAY_MS = 86_400_000;

function dayOrdinal(dateStr: string): number | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(dateStr);
  if (!m) return null;
  const t = Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
  if (!Number.isFinite(t)) return null;
  // Python's date.toordinal(): 0001-01-01 is day 1; 1970-01-01 is 719163
  return Math.floor(t / DAY_MS) + 719163;
}

/** Same three missions as daily_missions.missions_for() in the game. */
export function dailyReward(missionId: string): number | null {
  const m = /^(\d{4}-\d{2}-\d{2})_([0-2])$/.exec(missionId);
  if (!m) return null;
  const idx = dayOrdinal(m[1]);
  if (idx === null) return null;
  const picks = [DAILY.easy[idx % DAILY.easy.length], DAILY.medium[idx % DAILY.medium.length],
                 DAILY.hard[Math.floor(idx / 3) % DAILY.hard.length]];
  return Number(picks[Number(m[2])][3]);
}

/** Today's deal (1.0.8): one diamond skin a (UTC) day at DEAL_OFF off - the same pick on the game (shop.daily_deal). */
export const DEAL_OFF = 0.3;
export function dailyDeal(nowMs: number): { skin: string; price: number; full: number } {
  const pool = Object.keys(SKIN_COST).filter((k) => !k.includes("prestige")).sort();
  const day = Math.floor(nowMs / DAY_MS);
  const skin = pool[(day * 7919) % pool.length];
  const full = (SKIN_COST as Record<string, number>)[skin];
  return { skin, price: Math.round(full * (1 - DEAL_OFF) / 5) * 5, full };
}

/** The day's first shield costs nothing (1.0.9): its marker row's ref is this UTC date. */
export function freeShieldDay(nowMs: number): string {
  return new Date(nowMs).toISOString().slice(0, 10);
}

export function spendPrice(item: string, nowMs = 0): number | null {
  if (item === "revive") return REVIVE_COST;
  if (item === "shield") return SHIELD_COST;
  if (item.startsWith("skin:")) {
    const c = (SKIN_COST as Record<string, number>)[item.slice(5)];
    if (typeof c !== "number" || c <= 0) return null;
    // today's deal - or the one that just ended (10 minutes of grace for a purchase made just before midnight) - and
    // the skins of the week (rotation.ts, 1.0.9): the cheapest applies
    let best = c;
    for (const t of [nowMs, nowMs - 600_000]) {
      const d = dailyDeal(t);
      if (nowMs && d.skin === item.slice(5)) best = Math.min(best, d.price);
    }
    const wk = nowMs ? weeklySkinPrice(item.slice(5), nowMs) : null;
    return wk === null ? best : Math.min(best, wk);
  }
  return null;
}

/** ISO week of a unix-ms instant as [year, week] (UTC). */
export function isoWeek(ms: number): [number, number] {
  const d = new Date(ms);
  const day = (d.getUTCDay() + 6) % 7;                       // Mon = 0
  const thu = Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate() - day + 3);
  const y = new Date(thu).getUTCFullYear();
  return [y, 1 + Math.floor((thu - Date.UTC(y, 0, 1)) / (7 * DAY_MS))];
}

/** The diamonds of weekly mission `ref` ("YYYY-Www_i", weekly_missions.missions_for) or null. */
export function weeklyReward(ref: string): number | null {
  const m = /^(\d{4})-W(\d{2})_([0-2])$/.exec(ref);
  if (!m) return null;
  const idx = Number(m[1]) * 53 + Number(m[2]);
  const pool = WEEKLY[Number(m[3])][0] as readonly number[];
  return pool[idx % pool.length];
}

/** The "Seri" skins a player has earned after `weeks` completed 7-day login runs (skin_catalog.STREAK_WEEKS). */
export function streakSkins(weeks: number): string[] {
  return Object.entries(STREAK_WEEKS as Record<string, number>).filter(([, need]) => weeks >= need).map(([id]) => id);
}

/** `week` = this login completes a 7-day run (day 7): the handler counts it and grants the Seri skins. */
export type EarnCheck = { amount: number; reason: string; ref: string; week?: boolean } | { error: string; status: number };

/** Validates an earning claim; `now` in ms. */
export async function earnClaim(store: WalletStore, pid: string, kind: string, ref: string, nowMs: number): Promise<EarnCheck> {
  if (kind === "ach") {
    if (!(ACH_IDS as readonly string[]).includes(ref)) return { error: "unknown achievement", status: 400 };
    return { amount: ACH_REWARD, reason: "ach", ref };
  }
  if (kind === "welcome") return { amount: WELCOME_GIFT, reason: "welcome", ref: "1" };
  if (kind === "tutorial") return { amount: TUTORIAL_REWARD, reason: "tutorial", ref: "1" };
  if (kind === "daily") {
    const reward = dailyReward(ref);
    if (reward === null) return { error: "bad mission", status: 400 };
    const day = dayOrdinal(ref.slice(0, 10))!;
    const today = Math.floor(nowMs / DAY_MS) + 719163;
    if (day < today - 2 || day > today + 1) return { error: "mission expired", status: 400 };   // time zones + offline play
    return { amount: reward, reason: "daily", ref };
  }
  if (kind === "login") {
    // daily login calendar: ref = the player's local date; the day of the 7-day run (and so the amount) is counted
    // here from the logins already in the wallet log - consecutive dates before this one
    const day = /^\d{4}-\d{2}-\d{2}$/.test(ref) ? dayOrdinal(ref) : null;
    if (day === null) return { error: "bad date", status: 400 };
    const today = Math.floor(nowMs / DAY_MS) + 719163;
    if (day < today - 1 || day > today + 1) return { error: "login expired", status: 400 };
    const refs = await store.walletRefs(pid, "login", Math.floor(nowMs / 1000) - 400 * 86_400);   // the whole run (a 10-day window mis-read day 14+ of a run)
    const days = new Set(refs.map((r) => dayOrdinal(r)).filter((d) => d !== null));
    let streak = 0;
    for (let d = day - 1; days.has(d); d--) streak++;
    return { amount: LOGIN_REWARDS[streak % LOGIN_REWARDS.length], reason: "login", ref,
             week: streak % LOGIN_REWARDS.length === LOGIN_REWARDS.length - 1 };
  }
  if (kind === "weekly") {
    const reward = weeklyReward(ref);
    if (reward === null) return { error: "bad mission", status: 400 };
    // this week's or last week's missions (a claim made just after the week turned over)
    const ok = [0, -1, 1].some((k) => {
      const [y, w] = isoWeek(nowMs + k * 7 * DAY_MS);
      return ref.startsWith(`${y}-W${String(w).padStart(2, "0")}_`);
    });
    if (!ok) return { error: "mission expired", status: 400 };
    return { amount: reward, reason: "weekly", ref };
  }
  if (kind === "event") {
    const m = /^([a-z0-9]+)_(\d)$/.exec(ref);
    const ev = m ? (EVENTS as Record<string, { start: string; end: string; gems: readonly number[] }>)[m[1]] : undefined;
    const gems = ev?.gems[Number(m![2])];
    if (!ev || gems === undefined) return { error: "bad event", status: 400 };
    const today = Math.floor(nowMs / DAY_MS) + 719163;
    if (today < dayOrdinal(ev.start)! - 1 || today > dayOrdinal(ev.end)! + 3) return { error: "event over", status: 400 };
    return { amount: gems, reason: "event", ref };
  }
  if (kind === "ad") {
    if (!/^[0-9a-f]{16,32}$/.test(ref)) return { error: "bad ref", status: 400 };
    const now = Math.floor(nowMs / 1000);
    const { n, last } = await store.walletCount(pid, "ad", now - 86_400);
    if (n >= AD_MAX_PER_DAY) return { error: "ad limit", status: 429 };
    if (now - last < AD_MIN_GAP_S) return { error: "ad cooldown", status: 429 };
    return { amount: AD_REWARD, reason: "ad", ref };
  }
  if (kind === "adrevive") {
    if (!/^[0-9a-f]{16,32}$/.test(ref)) return { error: "bad ref", status: 400 };
    const now = Math.floor(nowMs / 1000);
    const { n } = await store.walletCount(pid, "adrevive", now - 86_400);
    if (n >= ADREVIVE_MAX_PER_DAY) return { error: "ad limit", status: 429 };
    return { amount: REVIVE_COST, reason: "adrevive", ref };
  }
  if (kind === "pack") {
    // Real-money packs need a Google Play receipt check on the server before they can be credited here.
    if (!(ref.split(":")[0] in PACKS)) return { error: "unknown pack", status: 400 };
    return { error: "use the purchase op", status: 400 };
  }
  return { error: "unknown kind", status: 400 };
}
