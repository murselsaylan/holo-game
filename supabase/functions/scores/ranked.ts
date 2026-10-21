// 1.0.9 "ranked" layer: the star wallet and the daily level.
//
// Stars live in star_log (one row per (player, reason, ref), UNIQUE - a retry never counts twice); the balance is the sum
// of the deltas and the "earned" total (what the star road looks at) the sum of the positive ones, so spending never
// undoes progress. The client only ever names a thing (a tier, a chest, an item); amounts, thresholds and prices all
// come from here (star_road.py -> wallet_data.ts RANKED).
import type { WalletStore } from "./wallet.ts";
import { LOGIN_STARS, RANKED, STAR_COST } from "./wallet_data.ts";
import { starOverflow } from "./shopx.ts";
import { weeklyLevel, crowdWeekKey, crowdWeekEnd } from "./crowd.ts";
import { LevelData, replay } from "./sim.ts";
import type { Result } from "./sim.ts";

const K = RANKED;
const DAY_MS = 86_400_000;

// ---- store ------------------------------------------------------------------------------------------------
export interface DailyRun { level: number; started: number; finished: number; score: number; stars: number; time: number }
export interface DailyRow { id: string; name: string; country: string; score: number; stars: number; time: number }

export interface RankedStore {
  /** +/- stars; refuses to go below zero; (reason, ref) already logged -> dup and nothing changes. */
  starChange(pid: string, delta: number, reason: string, ref: string, now: number):
    Promise<{ ok: boolean; dup: boolean; balance: number; earned: number }>;
  starTotals(pid: string): Promise<{ balance: number; earned: number }>;
  /** Sum of the `reason` deltas since `since` (unix s). */
  starSum(pid: string, reason: string, since: number): Promise<number>;
  starRefs(pid: string, reason: string): Promise<string[]>;
  /** Stars logged from `since` (unix s), positive entries only. */
  starEarnedSince(pid: string, since: number): Promise<number>;

  /** True when the attempt was created now; false when the player already used today's. */
  dailyStart(day: number, pid: string, level: number, now: number): Promise<boolean>;
  dailyRun(day: number, pid: string): Promise<DailyRun | null>;
  /** Stores the finished run once (false when already finished). */
  dailyFinish(day: number, pid: string, score: number, stars: number, time: number, taps: number[], now: number): Promise<boolean>;
  dailyBoard(day: number, limit: number): Promise<DailyRow[]>;
  dailyRank(day: number, pid: string): Promise<{ rank: number; total: number } | null>;
}

export interface RankedCtx {
  rs: RankedStore;
  ws: WalletStore & { playerBests(pid: string): Promise<{ level: number; stars: number }[]> };
  level(n: number): LevelData | null;
  /** hex sha256 */
  sha256(s: string): Promise<string>;
}

// ---- pure rules -----------------------------------------------------------------------------------------------
export const utcDay = (nowMs: number) => Math.floor(nowMs / DAY_MS);
const dayStartS = (day: number) => day * 86_400;

/** The level everybody plays on a (UTC) day; never the week's featured level. */
export function dailyLevel(day: number): number {
  const n = K.DAILY_LAST - K.DAILY_FIRST + 1;
  const pick = (d: number) => K.DAILY_FIRST + ((d * 7919 + 17) % n);
  let lv = pick(day);
  const week = crowdWeekKey(day * DAY_MS);
  if (lv === weeklyLevel(week)) lv = K.DAILY_FIRST + ((lv - K.DAILY_FIRST + 1) % n);
  return lv;
}

// ---- star wallet ------------------------------------------------------------------------------------------------
export interface RReply { status: number; body: Record<string, unknown> }
const R = (status: number, body: Record<string, unknown>): RReply => ({ status, body });

/** A verified campaign clear: its stars (1 each, first time only, `CAMPAIGN_STAR_CAP` in all) join the wallet. */
export async function campaignStars(rs: RankedStore | undefined, pid: string, level: number, stars: number, now: number): Promise<number> {
  try {
    if (!rs || !Number.isInteger(level) || level < 1 || !Number.isInteger(stars) || stars <= 0) return 0;
    let room = K.CAMPAIGN_STAR_CAP - (await rs.starSum(pid, "lvl", 0));
    let added = 0;
    for (let k = 1; k <= Math.min(3, stars) && room > 0; k++) {
      const r = await rs.starChange(pid, 1, "lvl", `${level}:${k}`, now);
      if (!r.dup) { added++; room--; }
    }
    return added;
  } catch (e) {
    console.error("campaign stars failed", e);
    return 0;
  }
}

/** A verified endless climb: its stars join the wallet (safety cap per day), once per run. */
export async function endlessStars(rs: RankedStore | undefined, pid: string, runRef: string, stars: number, now: number): Promise<number> {
  try {
    if (!rs || !Number.isInteger(stars) || stars <= 0) return 0;
    const today = await rs.starSum(pid, "endless", Math.floor(now / 86_400) * 86_400);
    const n = Math.min(stars, K.ENDLESS_STARS_PER_DAY - today);
    if (n <= 0) return 0;
    const r = await rs.starChange(pid, n, "endless", runRef, now);
    return r.dup ? 0 : n;
  } catch (e) {
    console.error("endless stars failed", e);
    return 0;
  }
}

/** Stars that ride on a wallet claim (7th login day, event tier). Never throws. */
export async function bonusStars(rs: RankedStore | undefined, pid: string, kind: string, ref: string, amount: number, now: number) {
  try {
    if (rs && amount > 0) await rs.starChange(pid, amount, kind, ref, now);
  } catch (e) {
    console.error("bonus stars failed", e);
  }
}
export { LOGIN_STARS };

// ---- ops --------------------------------------------------------------------------------------------------------
/** Brings the campaign stars of every verified best into the wallet (old pilots, lost hooks) - idempotent. */
async function backfill(ctx: RankedCtx, pid: string, now: number) {
  const bests = (await ctx.ws.playerBests(pid)).sort((a, b) => a.level - b.level);
  for (const b of bests) await campaignStars(ctx.rs, pid, b.level, b.stars, now);
}

async function starView(ctx: RankedCtx, pid: string, now: number) {
  const { rs, ws } = ctx;
  const t = await rs.starTotals(pid);
  const shieldsToday = await rs.starSum(pid, "spend:shield", now - 86_400);
  return { stars: t.balance, earned: t.earned, shield_cost: K.SHIELD_STARS,
           shields_left: Math.max(0, K.SHIELD_STARS_PER_DAY - Math.round(-shieldsToday / K.SHIELD_STARS)),
           campaign_cap: K.CAMPAIGN_STAR_CAP, campaign: await rs.starSum(pid, "lvl", 0) };
}

async function dailyView(ctx: RankedCtx, pid: string, nowMs: number) {
  const { rs, ws } = ctx;
  const day = utcDay(nowMs);
  const run = await rs.dailyRun(day, pid);
  const rank = run && run.finished > 0 ? await rs.dailyRank(day, pid) : null;
  const board = await rs.dailyBoard(day, 20);
  const claimed = (await ws.walletRefs(pid, "dlevel", dayStartS(day) - 86_400)).includes(String(day));
  return {
    day, level: dailyLevel(day), ends: dayStartS(day + 1), reward: K.DAILY_REWARD, reward_3: K.DAILY_REWARD_3STAR,
    state: !run ? "open" : run.finished > 0 ? "done" : "started", claimed,
    run: run && run.finished > 0 ? { score: run.score, stars: run.stars, time: run.time } : null,
    rank: rank?.rank ?? 0, total: rank?.total ?? 0,
    board: board.map((r, i) => ({ rank: i + 1, name: r.name, country: r.country, score: r.score, stars: r.stars, time: r.time, me: r.id === pid })),
  };
}

const MAX_DAILY_TAPS = 4000;
const MIN_TAP_GAP = 4;

/** ops: stars | spend | daily | daily_start | daily_submit. `d` is the raw request (taps for daily_submit). */
export async function rankedOp(ctx: RankedCtx, pid: string, op: string, arg: string, d: Record<string, unknown>, nowMs: number): Promise<RReply> {
  const { rs, ws } = ctx;
  const now = Math.floor(nowMs / 1000);
  if (op === "stars") {
    await backfill(ctx, pid, now);
    await starOverflow(rs, ws, pid, now);            // stars above the cap turn into diamonds (shopx.ts, the one place)
    return R(200, { ok: true, ...(await starView(ctx, pid, now)) });
  }
  if (op === "daily") return R(200, { ok: true, ...(await dailyView(ctx, pid, nowMs)) });

  if (op === "spend") {
    // arg: "shield:<ref>" (one-attempt start shield) | "skin:<id>:<ref>" (a Star Hunter skin)
    const parts = arg.split(":");
    const bal = await ws.walletBalance(pid);
    if (bal === null) return R(409, { error: "sync first" });
    if (parts[0] === "shield") {
      const ref = parts[1] ?? "";
      if (!/^[0-9a-f]{16,32}$/.test(ref)) return R(400, { error: "bad ref" });
      const taken = await rs.starRefs(pid, "spend:shield");
      if (!taken.includes(ref)) {
        const used = -(await rs.starSum(pid, "spend:shield", now - 86_400)) / K.SHIELD_STARS;
        if (used >= K.SHIELD_STARS_PER_DAY) return R(429, { error: "shield limit" });
      }
      const r = await rs.starChange(pid, -K.SHIELD_STARS, "spend:shield", ref, now);
      if (!r.ok) return R(402, { error: "insufficient", stars: r.balance });
      // the same paid-help row the diamond shield leaves (zero diamonds), so a ranked run with the shield is covered
      await ws.walletChange(pid, 0, "spend:shield", ref, now);
      return R(200, { ok: true, stars: r.balance, price: K.SHIELD_STARS, dup: r.dup });
    }
    if (parts[0] === "skin") {
      const id = parts[1] ?? "";
      const price = (STAR_COST as Record<string, number>)[id];
      if (typeof price !== "number") return R(400, { error: "unknown item" });
      const owned = (await ws.walletSkins(pid)).includes(id);
      if (owned) return R(200, { ok: true, stars: (await rs.starTotals(pid)).balance, price: 0, dup: true });
      const r = await rs.starChange(pid, -price, "spend:skin:" + id, "star", now);
      if (!r.ok) return R(402, { error: "insufficient", stars: r.balance });
      await ws.walletChange(pid, 0, "spend:skin:" + id, "star", now);       // owned from now on (walletSkins reads it back)
      return R(200, { ok: true, stars: r.balance, price, dup: r.dup });
    }
    return R(400, { error: "unknown item" });
  }

  if (op === "daily_start") {
    const day = utcDay(nowMs), level = dailyLevel(day);
    if (!ctx.level(level)) return R(400, { error: "unknown level" });
    const first = await rs.dailyStart(day, pid, level, now);       // the try is used from this moment on
    return R(200, { ok: true, ...(await dailyView(ctx, pid, nowMs)), first });
  }

  if (op === "daily_submit") {
    const day = utcDay(nowMs), level = dailyLevel(day);
    const run = await rs.dailyRun(day, pid);
    if (!run) return R(409, { error: "not started" });
    if (run.finished > 0) return R(200, { ok: true, ...(await dailyView(ctx, pid, nowMs)), dup: true });
    const taps = d.taps;
    if (!Array.isArray(taps) || !taps.length || taps.length > MAX_DAILY_TAPS || !taps.every((x) => Number.isInteger(x))) {
      return R(400, { error: "bad taps" });
    }
    const t = taps as number[];
    for (let k = 1; k < t.length; k++) if (t[k] - t[k - 1] < MIN_TAP_GAP) return R(422, { error: "implausible input" });
    if (t[0] < 0 || t[t.length - 1] > 60 * 900) return R(422, { error: "implausible input" });
    const lvl = ctx.level(level);
    if (!lvl) return R(400, { error: "unknown level" });
    if (String(d.lvl ?? "") && String(d.lvl) !== lvl.digest) return R(409, { error: "level version mismatch - update the game" });
    const { result } = replay(lvl, t, Math.max(90.0, lvl.parTime * 8));
    if (!result) return R(422, { error: "replay did not clear the level" });
    // a clear cannot arrive faster than it takes to play it (a script that submits instantly gains nothing)
    if (now - run.started < Math.floor(result.time) - 5) return R(422, { error: "too fast" });
    if (now - run.started > 3600) return R(410, { error: "attempt expired" });
    const res = result as Result;
    const fresh = await rs.dailyFinish(day, pid, res.level_total, res.stars, res.time, t, now);
    let added = 0, balance: number | null = await ws.walletBalance(pid);
    if (fresh && balance !== null) {
      const reward = K.DAILY_REWARD + (res.stars >= 3 ? K.DAILY_REWARD_3STAR : 0);
      const r = await ws.walletChange(pid, reward, "dlevel", String(day), now);
      added = r.dup ? 0 : reward;
      balance = r.balance;
    }
    return R(200, { ok: true, ...(await dailyView(ctx, pid, nowMs)), added, balance, score: res.level_total, stars: res.stars });
  }
  return R(400, { error: "bad op" });
}
