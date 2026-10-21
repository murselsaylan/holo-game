// Shared weekly goal (1.0.9, "Ortak Hedef"): every verified clear adds the stars it earned to one counter for the
// whole player base. At 33 / 66 / 100 % of the week's goal everyone who helped (>= CROWD_MIN_CONTRIB stars) can claim a
// server-priced diamond reward, once per (player, week, tier) - the wallet log's unique (reason, ref) keeps it single.
// The client only ever names a tier; the amount, the thresholds and the contribution all come from here.
import type { WalletStore } from "./wallet.ts";
import { isoWeek } from "./wallet.ts";
import { MAX_LEVELS } from "./sim.ts";

// Weekly hard level ("Haftanin bolumu", 1.0.9): one level of the later sectors is featured each week; clearing it that
// week pays a small server reward once (wallet_log reason "wlevel", ref = week). The pick is a pure function of the week.
export const WLEVEL_FIRST = 61;
export const WLEVEL_REWARD = 15;
export function weeklyLevel(week: string): number {
  const m = /^(\d{4})-W(\d{2})$/.exec(week);
  const idx = m ? Number(m[1]) * 53 + Number(m[2]) : 0;
  const n = MAX_LEVELS - WLEVEL_FIRST + 1;
  return WLEVEL_FIRST + ((idx * 7919 + 13) % n);
}

export const CROWD_TIERS = [{ pct: 33, reward: 10 }, { pct: 66, reward: 20 }, { pct: 100, reward: 40 }] as const;
export const CROWD_MIN_CONTRIB = 3;            // stars a player must have added to share in the rewards
export const CROWD_PLAYER_CAP = 150;           // stars one player can add a week (one account cannot carry the goal alone)
export const CROWD_MIN_GOAL = 1500;
export const CROWD_MAX_GOAL = 500_000;
export const CROWD_GROWTH = 1.15;              // next week's goal = last week's total x this (clamped)
export const CROWD_CLAIM_GRACE_S = 3 * 86_400; // tiers reached can still be claimed three days after the week ends

export interface CrowdStore {
  /** The week's row; created with `goal` if it does not exist yet. */
  crowdWeek(week: string, goal: number, now: number): Promise<{ goal: number; stars: number; contributors: number }>;
  /** Total stars of a week (0 if unknown). */
  crowdTotal(week: string): Promise<number>;
  /** Adds up to `n` stars for the player, never past `cap` for the week; returns the stars really added. */
  crowdAdd(week: string, pid: string, n: number, cap: number, goal: number, now: number): Promise<number>;
  crowdMine(week: string, pid: string): Promise<number>;
  /** The player cleared this week's featured level (recorded by the verified submit). */
  weeklyClear(week: string, pid: string): Promise<void>;
  weeklyCleared(week: string, pid: string): Promise<boolean>;
  /** How many pilots cleared `level` ever, and how many pilots have cleared anything (for the "x % passed" line). */
  levelStats(level: number): Promise<{ cleared: number; pilots: number }>;
}

export const crowdWeekKey = (nowMs: number) => {
  const [y, w] = isoWeek(nowMs);
  return `${y}-W${String(w).padStart(2, "0")}`;
};
const WEEK_MS = 7 * 86_400_000;
export const crowdWeekEnd = (nowMs: number) => {                // unix seconds of the next ISO week's Monday 00:00 UTC
  const d = new Date(nowMs);
  const day = (d.getUTCDay() + 6) % 7;
  return Math.floor(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate() - day) / 1000) + 7 * 86_400;
};

/** This week's goal: fixed once the week row exists; the first caller of a week sets it from the week before. */
async function goalFor(cs: CrowdStore, week: string, nowMs: number) {
  const prev = crowdWeekKey(nowMs - WEEK_MS);
  const seed = Math.round((await cs.crowdTotal(prev)) * CROWD_GROWTH);
  const goal = Math.max(CROWD_MIN_GOAL, Math.min(CROWD_MAX_GOAL, Math.round(seed / 50) * 50));
  return await cs.crowdWeek(week, goal, Math.floor(nowMs / 1000));
}

/** Called after a verified clear / endless climb: its stars join the shared counter. Never throws into the caller. */
export async function crowdAdd(cs: CrowdStore | undefined, pid: string, stars: number, nowMs: number): Promise<number> {
  try {
    if (!cs || !Number.isInteger(stars) || stars <= 0) return 0;
    const week = crowdWeekKey(nowMs);
    const w = await goalFor(cs, week, nowMs);
    return await cs.crowdAdd(week, pid, Math.min(stars, 3), CROWD_PLAYER_CAP, w.goal, Math.floor(nowMs / 1000));
  } catch (e) {
    console.error("crowd add failed", e);
    return 0;
  }
}

/** Called after a verified clear: this week's featured level counts for the weekly reward. Never throws. */
export async function weeklyClear(cs: CrowdStore | undefined, pid: string, level: number, nowMs: number): Promise<void> {
  try {
    const week = crowdWeekKey(nowMs);
    if (cs && level === weeklyLevel(week)) await cs.weeklyClear(week, pid);
  } catch (e) {
    console.error("weekly clear failed", e);
  }
}

let statCache: { at: number; level: number; v: { cleared: number; pilots: number } } | null = null;
async function passPct(cs: CrowdStore, level: number, nowMs: number): Promise<number> {
  if (!statCache || statCache.level !== level || nowMs - statCache.at > 300_000) {
    statCache = { at: nowMs, level, v: await cs.levelStats(level) };
  }
  const { cleared, pilots } = statCache.v;
  return pilots > 0 ? Math.round(1000 * Math.min(cleared, pilots) / pilots) / 10 : 0;
}

const need = (goal: number, pct: number) => Math.ceil(goal * pct / 100);

export interface CReply { status: number; body: Record<string, unknown> }
const R = (status: number, body: Record<string, unknown>): CReply => ({ status, body });

/** {op: "status" | "claim", arg: tier 1..3 for claim}. */
export async function crowdOp(cs: CrowdStore, ws: WalletStore, pid: string, op: string, arg: string, nowMs: number): Promise<CReply> {
  const now = Math.floor(nowMs / 1000);
  let week = crowdWeekKey(nowMs);
  if (op === "claim") {
    // a tier the week just closed on can still be claimed for a few days: arg "tier" or "tier@week"
    const [t, wk] = arg.split("@");
    if (wk) {
      if (!/^\d{4}-W\d{2}$/.test(wk)) return R(400, { error: "bad week" });
      week = wk;
      if (week !== crowdWeekKey(nowMs) && week !== crowdWeekKey(nowMs - WEEK_MS)) return R(410, { error: "week closed" });
      if (week !== crowdWeekKey(nowMs) && now - crowdWeekEnd(nowMs - WEEK_MS) > CROWD_CLAIM_GRACE_S) return R(410, { error: "week closed" });
    }
    arg = t;
  }
  const w = week === crowdWeekKey(nowMs) ? await goalFor(cs, week, nowMs) : await cs.crowdWeek(week, 0, now);
  const mine = await cs.crowdMine(week, pid);
  const since = now - 21 * 86_400;
  const claimedRefs = new Set(await ws.walletRefs(pid, "crowd", since));
  const tiers = CROWD_TIERS.map((t, i) => {
    const n = need(w.goal, t.pct);
    const reached = w.goal > 0 && w.stars >= n;
    const claimed = claimedRefs.has(`${week}:${i + 1}`);
    return { tier: i + 1, pct: t.pct, need: n, reward: t.reward, reached, claimed, claimable: reached && !claimed && mine >= CROWD_MIN_CONTRIB };
  });
  const wl = weeklyLevel(week);
  const wCleared = await cs.weeklyCleared(week, pid);
  const wlevel = { level: wl, pct: await passPct(cs, wl, nowMs), cleared: wCleared, reward: WLEVEL_REWARD,
                   claimed: (await ws.walletRefs(pid, "wlevel", since)).includes(week) };
  const view = { week, goal: w.goal, total: w.stars, contributors: w.contributors, mine, min_contrib: CROWD_MIN_CONTRIB,
                 ends: crowdWeekEnd(nowMs), tiers, wlevel };
  if (op === "status") return R(200, { ok: true, ...view });
  if (op === "wclaim") {
    if (week !== crowdWeekKey(nowMs)) return R(400, { error: "bad week" });
    const bal0 = await ws.walletBalance(pid);
    if (bal0 === null) return R(409, { error: "sync first" });
    if (!wCleared) return R(409, { error: "not cleared this week", ...view });
    const r = await ws.walletChange(pid, WLEVEL_REWARD, "wlevel", week, now);
    return R(200, { ok: true, ...view, wlevel: { ...wlevel, claimed: true }, added: r.dup ? 0 : WLEVEL_REWARD, balance: r.balance, dup: r.dup });
  }
  if (op !== "claim") return R(400, { error: "bad op" });

  const tier = Math.trunc(Number(arg));
  if (!(tier >= 1 && tier <= CROWD_TIERS.length)) return R(400, { error: "bad tier" });
  const bal = await ws.walletBalance(pid);
  if (bal === null) return R(409, { error: "sync first" });
  const t = tiers[tier - 1];
  if (!t.reached) return R(409, { error: "tier not reached", ...view });
  if (mine < CROWD_MIN_CONTRIB) return R(403, { error: "no contribution", ...view });
  const r = await ws.walletChange(pid, t.reward, "crowd", `${week}:${tier}`, now);
  const done = tiers.map((x) => (x.tier === tier ? { ...x, claimed: true, claimable: false } : x));
  return R(200, { ok: true, ...view, tiers: done, added: r.dup ? 0 : t.reward, balance: r.balance, dup: r.dup });
}
