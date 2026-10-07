// Transport-independent request handler of the HOLO leaderboard (port of server/leaderboard_server.py).
import { LevelData, replay, SIM_VERSION, MAX_LEVELS } from "./sim.ts";
import type { Assist, Result } from "./sim.ts";
import { LEVELS, DIGESTS } from "./levels_data.ts";
import { DIAMOND_EVERY_M, DIAMONDS_PER_DAY, ENDLESS_VERSIONS, MAX_STEPS as ENDLESS_MAX_STEPS, poolDigest, replayEndless, seedOf, weekOf, weekStart, assistDigest, MAX_REVIVES as ENDLESS_MAX_REVIVES } from "./endless.ts";
import { accountTag, earnClaim, IMPORT_CAP, productValue, spendPrice } from "./wallet.ts";
import { devPurchases, googleVerifier } from "./play.ts";
import { googleConfigured, maskEmail, verifyGoogleIdToken } from "./google_id.ts";
import type { Verifier } from "./play.ts";
import type { WalletStore } from "./wallet.ts";

export const COUNTRIES = new Set(["TR", "US", "DE", "GB", "JP", "KR", "FR", "BR", "CA", "AU", "IT", "ES", "NL", "AZ", "SE", "GX"]);
const MAX_BODY = 256 * 1024;
const MIN_TAP_GAP = 4;       // steps (66 ms): faster than any human can tap
const MAX_TAPS = 4000;
const NAME_RE = /^[A-Z0-9İŞĞÜÖÇ _\-.]{1,12}$/u;

export interface Player { id: string; secret: string; name: string; country: string; levels: number; score: number; stars: number }
export interface Ranks { rank: number; country_rank: number; levels: number; score: number; stars: number; country?: string }
export interface Row { rank: number; id: string; name: string; country: string; levels: number; score: number; stars: number }

export interface Best { level: number; score: number; stars: number; time: number; swaps: number; rank: string }
export interface EndlessRow { rank: number; id: string; name: string; country: string; metres: number; points?: number }
export interface EndlessStanding { rank: number; metres: number; points?: number; total: number }
export interface Restored { player: Player; data: string | null; bests: Best[] }

export type Ghost = { id: string; name: string; score: number; taps: number[] };

export interface Store extends WalletStore {
  ensure(): Promise<void>;
  /** Cloud save of the whole local save file (account recovery). */
  saveCloud(pid: string, data: string, now: number): Promise<void>;
  /** Stores the hash of the player's recovery code (replacing an older one). */
  setRecovery(pid: string, hash: string): Promise<void>;
  restore(hash: string): Promise<Restored | null>;
  /** Links the Google account (hash of its id) to the pilot; "taken" when another pilot already has it. */
  linkGoogle(pid: string, googleHash: string, email: string): Promise<"ok" | "taken">;
  restoreGoogle(googleHash: string): Promise<Restored | null>;
  /** The player's verified best of every level (the game aligns its local scores with them). */
  playerBests(pid: string): Promise<Best[]>;
  player(pid: string): Promise<Player | null>;
  register(pid: string, secret: string, name: string, country: string): Promise<boolean>;
  /** `assists` (revives / bought shields) must be covered by what the player paid for (wallet_log) - else unpaid. */
  record(pid: string, level: number, res: Result, taps: number[], assists?: Assist[]):
    Promise<{ improved: boolean; levels: number; score: number; stars: number; unpaid?: boolean }>;
  ranks(pid: string): Promise<Ranks | null>;
  /** The best clean (no paid help) verified run of a level - its taps are the ghost every player can race. */
  ghost(level: number): Promise<Ghost | null>;
  /** A crash report from a player's device (kind "fault" = native crash stack, "crash" = Python traceback). */
  report(pid: string, kind: string, platform: string, version: string, text: string, now: number): Promise<void>;
  board(scope: string, country: string, offset: number, limit: number): Promise<{ rows: Row[]; total: number }>;
  /** Endless best of the week (kept only when higher); `best` / `improved` are about the player's all-time best. */
  endlessRecord(pid: string, week: string, metres: number, steps: number, nonce: string, taps: number[], now: number):
    Promise<{ best: number; improved: boolean }>;
  /** Paid help of one endless climb (ref = week:nonce): every revive / shield must be paid for and unused; a ref
   *  already accepted is ok again (a retried upload is not charged twice). */
  useAssists(pid: string, revives: number, shields: number, ref: string, now: number): Promise<boolean>;
  endlessStanding(pid: string, week: string): Promise<EndlessStanding | null>;
  endlessBoard(week: string, offset: number, limit: number): Promise<{ rows: EndlessRow[]; total: number }>;
}

export interface Reply { status: number; body: Record<string, unknown> }
const R = (status: number, body: Record<string, unknown>): Reply => ({ status, body });

// ---- helpers -----------------------------------------------------------------------------------------------
const rate = new Map<string, number[]>();
function limited(key: string, limit: number, now: number, per = 60_000): boolean {
  if (rate.size > 5000) rate.clear();
  const hits = (rate.get(key) ?? []).filter((t) => now - t < per);
  if (hits.length >= limit) { rate.set(key, hits); return true; }
  hits.push(now);
  rate.set(key, hits);
  return false;
}

export function cleanName(name: unknown): string {
  const n = Array.from(String(name ?? "").trim().toUpperCase()).slice(0, 12).join("");
  return NAME_RE.test(n) ? n : "PİLOT";
}

const enc = new TextEncoder();
export async function sign(secret: string, pid: string, level: number, ts: number, taps: number[]): Promise<string> {
  const key = await crypto.subtle.importKey("raw", enc.encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const mac = await crypto.subtle.sign("HMAC", key, enc.encode(`${pid}|${level}|${ts}|${taps.join(",")}`));
  return Array.from(new Uint8Array(mac)).map((b) => b.toString(16).padStart(2, "0")).join("");
}

async function hmacHex(secret: string, msg: string): Promise<string> {
  const key = await crypto.subtle.importKey("raw", enc.encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const mac = await crypto.subtle.sign("HMAC", key, enc.encode(msg));
  return Array.from(new Uint8Array(mac)).map((b) => b.toString(16).padStart(2, "0")).join("");
}

export async function sha256Hex(s: string): Promise<string> {
  const h = await crypto.subtle.digest("SHA-256", enc.encode(s));
  return Array.from(new Uint8Array(h)).map((b) => b.toString(16).padStart(2, "0")).join("");
}

/** Signatures of the account endpoints (the submit one stays as it is). */
export const signSave = async (secret: string, pid: string, ts: number, data: string) =>
  hmacHex(secret, `${pid}|save|${ts}|${await sha256Hex(data)}`);
export const signCode = (secret: string, pid: string, ts: number) => hmacHex(secret, `${pid}|code|${ts}`);
/** Runs with paid help carry a second signature that also covers the help list. */
export const assistKey = (assists: Assist[]) => assists.map((a) => `${a[0]}${a[1]}`).join(",");
export const signAssisted = (secret: string, pid: string, level: number, ts: number, taps: number[], assists: Assist[]) =>
  hmacHex(secret, `${pid}|${level}|${ts}|${taps.join(",")}|${assistKey(assists)}`);
const MAX_ASSISTS = 400;

export const signBests = (secret: string, pid: string, ts: number) => hmacHex(secret, `${pid}|bests|${ts}`);
export const signEndless = (secret: string, pid: string, week: string, nonce: string, end: number, ts: number, tapsDigest: string) =>
  hmacHex(secret, `${pid}|endless|${week}|${nonce}|${end}|${ts}|${tapsDigest}`);
export const signGoogleLink = (secret: string, pid: string, ts: number, tokenDigest: string) =>
  hmacHex(secret, `${pid}|glink|${ts}|${tokenDigest}`);
export const googleHash = (sub: string) => sha256Hex("holo-google|" + sub);
export const signWallet = (secret: string, pid: string, ts: number, op: string, key: string, ref: string) =>
  hmacHex(secret, `${pid}|wallet|${ts}|${op}|${key}|${ref}`);

// Recovery codes: 12 characters from a 32-letter alphabet without look-alikes (0/O, 1/I) = 60 random bits.
const CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
const MAX_SAVE = 200 * 1024;
export const normCode = (c: unknown) => String(c ?? "").toUpperCase().replace(/[^A-Z0-9]/g, "");
export const codeHash = (code: string) => sha256Hex("holo-recovery|" + code);

function newCode(): string {
  const b = crypto.getRandomValues(new Uint8Array(12));
  return Array.from(b).map((x) => CODE_ALPHABET[x & 31]).join("");
}

function safeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let d = 0;
  for (let i = 0; i < a.length; i++) d |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return d === 0;
}

const levelCache = new Map<number, LevelData | null>();
function getLevel(n: number): LevelData | null {
  if (!levelCache.has(n)) {
    const d = LEVELS[String(n)];
    levelCache.set(n, d ? new LevelData(d, DIGESTS[String(n)]) : null);
  }
  return levelCache.get(n) ?? null;
}

// ---- routing -------------------------------------------------------------------------------------------------
export async function handle(store: Store, method: string, path: string, query: URLSearchParams, rawBody: string,
                             ip: string, nowMs = Date.now()): Promise<Reply> {
  const i = path.lastIndexOf("/api/");                 // works behind /functions/v1/<name>/ prefixes
  const route = i >= 0 ? path.slice(i) : path;
  await store.ensure();

  if (method === "GET") {
    if (route === "/api/health") return R(200, { ok: true, sim: SIM_VERSION, time: Math.floor(nowMs / 1000) });
    if (route === "/api/leaderboard") {
      if (limited(`g|${ip}`, 120, nowMs)) return R(429, { error: "slow down" });
      const lim = Number(query.get("limit") ?? 50);
      if (!Number.isFinite(lim)) return R(400, { error: "bad request" });
      const limit = Math.max(1, Math.min(100, Math.trunc(lim)));
      const scope = query.get("scope") ?? "global";
      const pid = (query.get("player_id") ?? "").slice(0, 64);
      const me = pid ? await store.ranks(pid) : null;
      let country = (query.get("country") ?? "").slice(0, 4).toUpperCase();
      let offset = 0;
      let scopeQ: string;
      if (scope === "around" && me) {
        offset = Math.max(0, me.rank - 1 - Math.trunc(limit / 2));
        scopeQ = "global";
      } else {
        scopeQ = scope === "country" ? "country" : "global";
      }
      if (scopeQ === "country" && me) {
        if (me.country) country = me.country;
        else {
          const pl = await store.player(pid);
          if (pl) country = pl.country;
        }
      }
      const { rows, total } = await store.board(scopeQ, country, offset, limit);
      return R(200, { scope, rows, total, me: me ?? {} });
    }
    if (route === "/api/ghost") {
      if (limited(`gh|${ip}`, 120, nowMs)) return R(429, { error: "slow down" });
      const level = Math.trunc(Number(query.get("level")));
      if (!Number.isFinite(level) || level < 1 || level > 10_000) return R(400, { error: "bad level" });
      const g = await store.ghost(level);
      return R(200, g ? { level, ...g } : { level });
    }
    if (route === "/api/endless/board") {
      if (limited(`eb|${ip}`, 120, nowMs)) return R(429, { error: "slow down" });
      const week = String(query.get("week") ?? weekOf(nowMs / 1000));
      if (!WEEK_RE.test(week)) return R(400, { error: "bad week" });
      const lim = Math.max(1, Math.min(100, Math.trunc(Number(query.get("limit") ?? 100)) || 100));
      const pid = (query.get("player_id") ?? "").slice(0, 64);
      const me = pid ? await store.endlessStanding(pid, week) : null;
      const { rows, total } = await store.endlessBoard(week, 0, lim);
      return R(200, { scope: "endless", week, rows, total, me: me ?? {} });
    }
    return R(404, { error: "not found" });
  }

  if (method === "POST") {
    if (!rawBody || rawBody.length > MAX_BODY) return R(400, { error: "bad request" });
    let d: Record<string, unknown>;
    try { d = JSON.parse(rawBody); } catch { return R(400, { error: "bad request" }); }
    if (typeof d !== "object" || d === null) return R(400, { error: "bad request" });
    if (route === "/api/register") return await register(store, d, ip, nowMs);
    if (route === "/api/report") {
      if (limited(`rp|${ip}`, 6, nowMs)) return R(429, { error: "slow down" });
      const pid = String(d.player_id ?? "").slice(0, 64), kind = String(d.kind ?? "").slice(0, 16);
      const text = String(d.text ?? "");
      if (!/^[0-9a-f]{16,64}$/.test(pid) || !["fault", "crash"].includes(kind) || !text || text.length > 12000) {
        return R(400, { error: "bad report" });
      }
      await store.report(pid, kind, String(d.platform ?? "").slice(0, 16), String(d.version ?? "").slice(0, 16), text,
                         Math.floor(nowMs / 1000));
      return R(200, { ok: true });
    }
    if (route === "/api/cloud/save") return await cloudSave(store, d, ip, nowMs);
    if (route === "/api/cloud/code") return await cloudCode(store, d, ip, nowMs);
    if (route === "/api/bests") return await myBests(store, d, ip, nowMs);
    if (route === "/api/cloud/restore") return await cloudRestore(store, d, ip, nowMs);
    if (route === "/api/submit") return await submit(store, d, ip, nowMs);
    if (route === "/api/wallet") return await wallet(store, d, ip, nowMs);
    if (route === "/api/endless/submit") return await endlessSubmit(store, d, ip, nowMs);
    if (route === "/api/account/google/link") return await googleLink(store, d, ip, nowMs);
    if (route === "/api/account/google/restore") return await googleRestore(store, d, ip, nowMs);
  }
  return R(404, { error: "not found" });
}

async function authed(store: Store, d: Record<string, unknown>, nowMs: number, sig: (secret: string) => Promise<string>) {
  const pid = String(d.player_id ?? "");
  const ts = Number(d.ts);
  if (!Number.isInteger(ts) || Math.abs(nowMs / 1000 - ts) > 900) return null;
  const pl = await store.player(pid);
  if (!pl || !safeEqual(String(d.sig ?? ""), await sig(pl.secret))) return null;
  return pl;
}

async function cloudSave(store: Store, d: Record<string, unknown>, ip: string, nowMs: number): Promise<Reply> {
  if (limited(`cs|${ip}`, 20, nowMs)) return R(429, { error: "slow down" });
  const data = d.data;
  if (typeof data !== "string" || data.length === 0 || data.length > MAX_SAVE) return R(400, { error: "bad save" });
  const pl = await authed(store, d, nowMs, (secret) => signSave(secret, String(d.player_id), Number(d.ts), data));
  if (!pl) return R(403, { error: "bad signature" });
  await store.saveCloud(pl.id, data, Math.floor(nowMs / 1000));
  return R(200, { ok: true });
}

async function cloudCode(store: Store, d: Record<string, unknown>, ip: string, nowMs: number): Promise<Reply> {
  if (limited(`cc|${ip}`, 10, nowMs)) return R(429, { error: "slow down" });
  const pl = await authed(store, d, nowMs, (secret) => signCode(secret, String(d.player_id), Number(d.ts)));
  if (!pl) return R(403, { error: "bad signature" });
  const code = newCode();
  await store.setRecovery(pl.id, await codeHash(code));
  return R(200, { ok: true, code: `${code.slice(0, 4)}-${code.slice(4, 8)}-${code.slice(8)}` });
}

async function myBests(store: Store, d: Record<string, unknown>, ip: string, nowMs: number): Promise<Reply> {
  if (limited(`mb|${ip}`, 20, nowMs)) return R(429, { error: "slow down" });
  const pl = await authed(store, d, nowMs, (secret) => signBests(secret, String(d.player_id), Number(d.ts)));
  if (!pl) return R(403, { error: "bad signature" });
  return R(200, { ok: true, bests: await store.playerBests(pl.id) });
}

async function cloudRestore(store: Store, d: Record<string, unknown>, ip: string, nowMs: number): Promise<Reply> {
  // guessing 60-bit codes is hopeless, and each address gets only a few tries per hour anyway
  if (limited(`cr|${ip}`, 8, nowMs, 3_600_000)) return R(429, { error: "slow down" });
  const code = normCode(d.code);
  if (code.length !== 12) return R(400, { error: "bad code" });
  const got = await store.restore(await codeHash(code));
  if (!got) return R(404, { error: "unknown code" });
  const p = got.player;
  return R(200, { ok: true, player_id: p.id, secret: p.secret, name: p.name, country: p.country, data: got.data, bests: got.bests });
}

// ---- account recovery through a Google account (1.0.5) -----------------------------------------------------------
async function googleLink(store: Store, d: Record<string, unknown>, ip: string, nowMs: number): Promise<Reply> {
  if (limited(`gl|${ip}`, 10, nowMs)) return R(429, { error: "slow down" });
  if (!googleConfigured()) return R(503, { error: "google sign-in not configured" });
  const token = String(d.id_token ?? "");
  const pl = await authed(store, d, nowMs, async (secret) => signGoogleLink(secret, String(d.player_id), Number(d.ts), await sha256Hex(token)));
  if (!pl) return R(403, { error: "bad signature" });
  const who = await verifyGoogleIdToken(token, nowMs);
  if (!who) return R(401, { error: "bad google token" });
  const email = maskEmail(who.email);
  if ((await store.linkGoogle(pl.id, await googleHash(who.sub), email)) === "taken") {
    return R(409, { error: "google account linked to another pilot", email });
  }
  return R(200, { ok: true, email });
}

async function googleRestore(store: Store, d: Record<string, unknown>, ip: string, nowMs: number): Promise<Reply> {
  if (limited(`gr|${ip}`, 10, nowMs)) return R(429, { error: "slow down" });
  if (!googleConfigured()) return R(503, { error: "google sign-in not configured" });
  const who = await verifyGoogleIdToken(String(d.id_token ?? ""), nowMs);
  if (!who) return R(401, { error: "bad google token" });
  const got = await store.restoreGoogle(await googleHash(who.sub));
  if (!got) return R(404, { error: "no pilot linked", email: maskEmail(who.email) });
  const p = got.player;
  return R(200, { ok: true, player_id: p.id, secret: p.secret, name: p.name, country: p.country, data: got.data, bests: got.bests,
                  email: maskEmail(who.email) });
}

async function register(store: Store, d: Record<string, unknown>, ip: string, nowMs: number): Promise<Reply> {
  if (limited(`r|${ip}`, 30, nowMs)) return R(429, { error: "slow down" });
  const pid = String(d.player_id ?? ""), secret = String(d.secret ?? "");
  if (!/^[0-9a-f]{32}$/.test(pid) || !/^[0-9a-f]{48}$/.test(secret)) return R(400, { error: "bad identity" });
  let country = String(d.country ?? "GX").toUpperCase().slice(0, 4);
  if (!COUNTRIES.has(country)) country = "GX";
  if (!(await store.register(pid, secret, cleanName(d.name), country))) return R(403, { error: "identity mismatch" });
  return R(200, { ok: true });
}

async function submit(store: Store, d: Record<string, unknown>, ip: string, nowMs: number): Promise<Reply> {
  if (limited(`s|${ip}`, 40, nowMs)) return R(429, { error: "slow down" });
  const pid = String(d.player_id ?? "");
  const level = Number(d.level), ts = Number(d.ts), sig = String(d.sig ?? "");
  const tapsRaw = d.taps;
  if (!Array.isArray(tapsRaw) || !Number.isInteger(level) || !Number.isInteger(ts)) return R(400, { error: "bad request" });
  const taps = tapsRaw.map((x) => Number(x));
  if (taps.some((x) => !Number.isInteger(x))) return R(400, { error: "bad request" });
  const pl = await store.player(pid);
  if (!pl) return R(403, { error: "unknown player" });
  if (!safeEqual(sig, await sign(pl.secret, pid, level, ts, taps))) return R(403, { error: "bad signature" });
  if (Math.abs(nowMs / 1000 - ts) > 900) return R(400, { error: "stale request" });
  if (!(level >= 1 && level <= MAX_LEVELS) || taps.length > MAX_TAPS || taps.length === 0) return R(400, { error: "bad level or taps" });
  for (let k = 1; k < taps.length; k++) if (taps[k] - taps[k - 1] < MIN_TAP_GAP) return R(422, { error: "implausible input" });
  if (taps[0] < 0 || taps[taps.length - 1] > 60 * 900) return R(422, { error: "implausible input" });
  const lvl = getLevel(level);
  if (!lvl) return R(400, { error: "unknown level" });
  const claimed = String(d.lvl ?? "");
  if (claimed && claimed !== lvl.digest) return R(409, { error: "level version mismatch - update the game" });
  // paid help (1.0.4+): [[step, "S"|"R"|"R2"], ...] (R2 = the 1.0.6 slow-spin shielded revive) - replayed exactly, and it must have been paid for in diamonds
  let assists: Assist[] = [];
  if (d.assists !== undefined) {
    if (!Array.isArray(d.assists) || d.assists.length > MAX_ASSISTS) return R(400, { error: "bad assists" });
    for (const a of d.assists) {
      if (!Array.isArray(a) || a.length !== 2 || !Number.isInteger(a[0]) || a[0] < 0 || (a[1] !== "S" && a[1] !== "R" && a[1] !== "R2")) {
        return R(400, { error: "bad assists" });
      }
    }
    assists = (d.assists as [number, "S" | "R" | "R2"][]).map((a) => [a[0], a[1]] as Assist);
    if (assists.length && !safeEqual(String(d.asig ?? ""), await signAssisted(pl.secret, pid, level, ts, taps, assists))) {
      return R(403, { error: "bad signature" });
    }
  }
  const revives = assists.filter((a) => a[1] === "R" || a[1] === "R2").length;
  const limitS = Math.max(90.0, lvl.parTime * 8) + revives * 30.0;          // each revive may add a retry's worth of time
  const { result } = replay(lvl, taps, limitS, assists);
  if (!result) return R(422, { error: "replay did not clear the level" });
  const rec = await store.record(pid, level, result, taps, assists);
  if (rec.unpaid) return R(402, { error: "help not paid" });
  const ranks = (await store.ranks(pid)) ?? ({} as Partial<Ranks>);
  return R(200, {
    ok: true, level_score: result.level_total, stars: result.stars, improved: rec.improved, levels: rec.levels,
    score: rec.score, world_rank: ranks.rank ?? null, country_rank: ranks.country_rank ?? null,
  });
}

let verifier: Verifier = googleVerifier;
/** Tests swap the Google Play check for a fake one. */
export function setVerifier(v: Verifier) { verifier = v; }

// ---- endless climb ----------------------------------------------------------------------------------------------
const WEEK_RE = /^\d{4}-W\d{2}$/;
const NONCE_RE = /^[0-9a-f]{8,16}$/;
const MAX_ENDLESS_TAPS = 30000;

// {week, nonce, taps, end, v, pool} -> the server rebuilds that climb's world, replays it and ranks the height;
// 1 diamond per DIAMOND_EVERY_M metres of the run, at most DIAMONDS_PER_DAY a (UTC) day, each run paid once.
async function endlessSubmit(store: Store, d: Record<string, unknown>, ip: string, nowMs: number): Promise<Reply> {
  if (limited(`es|${ip}`, 20, nowMs)) return R(429, { error: "slow down" });
  const week = String(d.week ?? ""), nonce = String(d.nonce ?? "");
  const end = Number(d.end);
  const taps = d.taps;
  if (!WEEK_RE.test(week) || !NONCE_RE.test(nonce)) return R(400, { error: "bad run" });
  if (!Number.isInteger(end) || end < 1 || end > ENDLESS_MAX_STEPS) return R(400, { error: "bad run" });
  if (!Array.isArray(taps) || taps.length > MAX_ENDLESS_TAPS || !taps.every((x) => Number.isInteger(x))) return R(400, { error: "bad taps" });
  const ts_ = taps as number[];
  for (let k = 1; k < ts_.length; k++) if (ts_[k] - ts_[k - 1] < MIN_TAP_GAP) return R(422, { error: "implausible input" });
  if (ts_.length && (ts_[0] < 0 || ts_[ts_.length - 1] > end)) return R(422, { error: "implausible input" });
  const ev = Number(d.v);                     // v2 (1.0.6) and v3 (1.0.7+, faster start) are both replayed
  if (!ENDLESS_VERSIONS.includes(ev) || String(d.pool ?? "") !== poolDigest()) return R(409, { error: "update the game" });
  const now = Math.floor(nowMs / 1000);
  const current = weekOf(now), previous = weekOf(now - 7 * 86_400);
  if (week !== current && !(week === previous && now - weekStart(now) < 12 * 3600)) return R(410, { error: "week closed" });
  // paid help (1.0.6+): [[step, "S"|"R"|"R2"], ...], at most MAX_REVIVES revives; covered by the signature
  let assists: [number, string][] = [];
  if (d.assists !== undefined) {
    if (!Array.isArray(d.assists) || d.assists.length > 60) return R(400, { error: "bad assists" });
    for (const a of d.assists) {
      if (!Array.isArray(a) || a.length !== 2 || !Number.isInteger(a[0]) || a[0] < 0 || a[0] > end ||
          (a[1] !== "S" && a[1] !== "R" && a[1] !== "R2")) return R(400, { error: "bad assists" });
    }
    assists = (d.assists as [number, string][]).map((a) => [a[0], a[1]] as [number, string]);
  }
  const revives = assists.filter((a) => a[1] !== "S").length, shields = assists.length - revives;
  if (revives > ENDLESS_MAX_REVIVES) return R(422, { error: "too many revives" });
  const digest = await sha256Hex(assistDigest(ts_, assists));
  const pl = await authed(store, d, nowMs, (secret) => signEndless(secret, String(d.player_id), week, nonce, end, Number(d.ts), digest));
  if (!pl) return R(403, { error: "bad signature" });
  if (assists.length && !(await store.useAssists(pl.id, revives, shields, `${week}:${nonce}`, now))) {
    return R(402, { error: "help not paid" });
  }
  const run = replayEndless(seedOf(week, nonce, ev), ts_, end, ENDLESS_MAX_STEPS, assists, ev);
  const metres = run.metres, stars = run.stars, points = run.points;
  // the ranking sorts by points (height + stars; stored in endless_bests.metres since endless v2), diamonds follow height
  const rec = await store.endlessRecord(pl.id, week, points, run.n, nonce, ts_, now);
  let added = 0, capped = false;
  let balance: number | null = await store.walletBalance(pl.id);
  const earned = Math.floor(metres / DIAMOND_EVERY_M);
  if (balance !== null && earned > 0) {
    const today = await store.walletSum(pl.id, "endless", Math.floor(now / 86_400) * 86_400);
    const n = Math.min(earned, DIAMONDS_PER_DAY - today);
    if (n > 0) {
      const r = await store.walletChange(pl.id, n, "endless", `${week}:${nonce}:${digest.slice(0, 16)}`, now);
      added = r.dup ? 0 : n;
      balance = r.balance;
    } else {
      capped = true;
    }
  }
  const st = await store.endlessStanding(pl.id, week);
  return R(200, { ok: true, metres, stars, points, best: rec.best, improved: rec.improved, rank: st?.rank ?? 0, total: st?.total ?? 0,
                  added, capped, balance, next_gem: DIAMOND_EVERY_M - (metres % DIAMOND_EVERY_M), steps: run.n });
}

// ---- diamond wallet -------------------------------------------------------------------------------------------
// op "sync":  {local}        -> opens the wallet on first use (imports the old local balance, capped), pays out gifts
// op "earn":  {kind, ref}    -> ach:<id> | welcome | daily:<date>_<i> | ad:<random> | pack:<id>:<token>
// op "spend": {item, ref}    -> revive | shield | skin:<id>; ref is a random id so a retried request is not charged twice
// op "purchase": {product, token, ref=sha256(token)} -> a Google Play purchase: verified with Google, credited once per
//                token; the game consumes / acknowledges it on the phone only after this answered ok
async function wallet(store: Store, d: Record<string, unknown>, ip: string, nowMs: number): Promise<Reply> {
  if (limited(`w|${ip}`, 120, nowMs)) return R(429, { error: "slow down" });
  const op = String(d.op ?? "");
  const ref = String(d.ref ?? "").slice(0, 80);
  const key = op === "sync" ? String(Math.trunc(Number(d.local ?? 0)) || 0) : op === "earn" ? String(d.kind ?? "")
    : op === "purchase" ? String(d.product ?? "") : String(d.item ?? "");
  const pl = await authed(store, d, nowMs, (secret) => signWallet(secret, String(d.player_id), Number(d.ts), op, key, ref));
  if (!pl) return R(403, { error: "bad signature" });
  const now = Math.floor(nowMs / 1000);
  if (op === "sync") {
    const local = Math.max(0, Math.trunc(Number(d.local ?? 0)) || 0);
    const w = await store.walletOpen(pl.id, local, IMPORT_CAP, now);
    return R(200, { ok: true, balance: w.balance, gift: w.gift, imported: w.imported, skins: await store.walletSkins(pl.id),
                    account: await accountTag(pl.id) });
  }
  const bal = await store.walletBalance(pl.id);
  if (bal === null) return R(409, { error: "sync first" });
  if (op === "purchase") return await purchase(store, pl.id, key, String(d.token ?? ""), ref, bal, now);
  if (op === "earn") {
    const c = await earnClaim(store, pl.id, key, ref, nowMs);
    if ("error" in c) return R(c.status, { error: c.error, balance: bal });
    const r = await store.walletChange(pl.id, c.amount, c.reason, c.ref, now);
    return R(200, { ok: true, balance: r.balance, added: r.dup ? 0 : c.amount });
  }
  if (op === "spend") {
    const price = spendPrice(key);
    if (price === null) return R(400, { error: "unknown item", balance: bal });
    if (!/^[0-9a-f]{16,32}$/.test(ref)) return R(400, { error: "bad ref", balance: bal });
    const r = await store.walletChange(pl.id, -price, "spend:" + key, ref, now);
    if (!r.ok) return R(402, { error: "insufficient", balance: r.balance });
    return R(200, { ok: true, balance: r.balance, price });
  }
  return R(400, { error: "bad op" });
}

async function purchase(store: Store, pid: string, product: string, token: string, ref: string, bal: number,
                        now: number): Promise<Reply> {
  const value = productValue(product);
  if (!value) return R(400, { error: "unknown product", balance: bal });
  if (!token || token.length > 4096 || ref !== await sha256Hex(token)) return R(400, { error: "bad token", balance: bal });
  let orderId: string;
  if (token.startsWith("dev-")) {                       // test builds without Play (only when the server allows it)
    if (!devPurchases()) return R(403, { error: "dev purchases disabled", balance: bal });
    orderId = "DEV." + ref.slice(0, 12);
  } else {
    const p = await verifier(product, token);           // throws -> 500 -> the game keeps the purchase and retries
    if (p === null) return R(503, { error: "verification not configured", balance: bal });
    if (p.state === "pending") return R(202, { ok: false, pending: true, balance: bal });
    if (p.state !== "purchased") return R(410, { error: "not purchased", balance: bal });
    if (p.account && p.account !== await accountTag(pid)) return R(403, { error: "other account", balance: bal });
    orderId = p.orderId;
  }
  const r = await store.walletPurchase(pid, ref, product, orderId, value.diamonds, now);
  if (r.status === "other_player") return R(409, { error: "token used by another account", balance: bal });
  return R(200, { ok: true, balance: r.balance, dup: r.status === "dup", diamonds: value.diamonds, skin: value.skin });
}
