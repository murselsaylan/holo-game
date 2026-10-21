// 1.0.9 shop extras: the weekly showcase, consumable packs, prestige frames / titles, the weekly Star Market and the
// Star Chest. Route /api/shop. The client only names an item and a retry ref; prices, limits, the weekly rotation and
// the chest's dice are all decided here (shop_items.py -> wallet_data.ts SHOPX, rotation.ts).
//
// Everything is logged once per (player, reason, ref): a charge in wallet_log / star_log and, for consumables, one
// zero-delta "spend:shield" / "spend:revive" row per unit - the very rows the assist check (store.record /
// useAssists) counts as "paid help", so a stock bought in a pack is usable in a run exactly like a single purchase.
import type { WalletStore } from "./wallet.ts";
import type { RankedStore } from "./ranked.ts";
import { market, weekEnd, weekIndex, weeklyFrame, weeklySkins } from "./rotation.ts";
import { SHOPX } from "./wallet_data.ts";

const X = SHOPX;
const DAY_S = 86_400;
const REF_RE = /^[0-9a-f]{16,32}$/;

export interface ShopStore extends WalletStore {
  /** The reasons in this player's wallet log that start with `prefix` (e.g. every "spend:prestige:<id>"). */
  walletReasons(pid: string, prefix: string): Promise<string[]>;
  getPrestige(pid: string): Promise<{ frame: string; title: string }>;
  setPrestige(pid: string, frame: string, title: string): Promise<void>;
}
export interface ShopCtx { rs: RankedStore; ws: ShopStore; salt: string; sha256(s: string): Promise<string> }
export interface SReply { status: number; body: Record<string, unknown> }
const R = (status: number, body: Record<string, unknown>): SReply => ({ status, body });

const frameInfo = (id: string) => (X.FRAMES as Record<string, { price: number; kind: string }>)[id];
const titleInfo = (id: string) => (X.TITLES as Record<string, { price: number; kind: string }>)[id];
const prestigeInfo = (id: string) => frameInfo(id) ?? titleInfo(id);
/** The prestige items a player owns. */
async function ownedPrestige(ws: ShopStore, pid: string): Promise<Set<string>> {
  const p = "spend:prestige:";
  return new Set((await ws.walletReasons(pid, p)).map((r) => r.slice(p.length)));
}

/** Stars above STAR_CAP turn into diamonds (OVERFLOW_RATE each) - the one place that stops stars piling up for good.
 *  The ref is the player's lifetime star total, so every turn-over happens once. Never throws. */
export async function starOverflow(rs: RankedStore | undefined, ws: WalletStore, pid: string, now: number):
    Promise<{ stars: number; gems: number }> {
  try {
    if (!rs) return { stars: 0, gems: 0 };
    const t = await rs.starTotals(pid);
    if (t.balance <= X.STAR_CAP || (await ws.walletBalance(pid)) === null) return { stars: 0, gems: 0 };
    const excess = t.balance - X.STAR_CAP;
    const r = await rs.starChange(pid, -excess, "spend:overflow", String(t.earned), now);
    if (!r.ok || r.dup) return { stars: 0, gems: 0 };
    await ws.walletChange(pid, excess * X.OVERFLOW_RATE, "overflow", String(t.earned), now);
    return { stars: excess, gems: excess * X.OVERFLOW_RATE };
  } catch (e) {
    console.error("star overflow failed", e);
    return { stars: 0, gems: 0 };
  }
}

/** One zero-delta paid-help row per unit; idempotent, so a retried request fills in whatever is missing. */
async function grantUnits(ws: WalletStore, pid: string, item: string, units: number, base: string, now: number) {
  for (let i = 0; i < units; i++) await ws.walletChange(pid, 0, `spend:${item}`, `${base}:${i}`, now);
}

const startOfDay = (now: number) => Math.floor(now / DAY_S) * DAY_S;

async function packUnitsToday(ws: WalletStore, pid: string, item: string, now: number): Promise<number> {
  let units = 0;
  for (const [id, p] of Object.entries(X.PACKS as Record<string, { item: string; units: number }>)) {
    if (p.item === item) units += (await ws.walletCount(pid, `spend:pack:${id}`, now - DAY_S)).n * p.units;
  }
  return units;
}

async function view(ctx: ShopCtx, pid: string, nowMs: number): Promise<Record<string, unknown>> {
  const { rs, ws } = ctx;
  const now = Math.floor(nowMs / 1000);
  const ov = await starOverflow(rs, ws, pid, now);
  const st = await rs.starTotals(pid);
  const skins = new Set(await ws.walletSkins(pid));
  const own = await ownedPrestige(ws, pid);
  const wk = weekIndex(nowMs);
  const frame = weeklyFrame(nowMs);
  const packs: Record<string, number> = {};
  for (const item of Object.keys(X.PACK_UNITS_PER_DAY)) {
    packs[item] = Math.max(0, (X.PACK_UNITS_PER_DAY as Record<string, number>)[item] - await packUnitsToday(ws, pid, item, now));
  }
  const mk = [];
  for (const m of market(nowMs)) {
    const used = (await rs.starRefs(pid, `spend:mkt:${m.id}`)).filter((r) => r.startsWith(`${wk}:`)).length;
    const owned = (m.kind === "frame" || m.kind === "title") && own.has(String(m.payload));
    mk.push({ ...m, left: owned ? 0 : Math.max(0, m.limit - used), owned });
  }
  const chests = (await rs.starRefs(pid, "spend:chest")).length;
  const today = -(await rs.starSum(pid, "spend:chest", startOfDay(now))) / X.CHEST.cost;
  const eq = await ws.getPrestige(pid);
  return {
    ok: true, balance: await ws.walletBalance(pid), stars: st.balance, earned: st.earned,
    week: wk, ends: weekEnd(nowMs),
    showcase: weeklySkins(nowMs).map((s) => ({ ...s, owned: skins.has(s.skin) })),
    frame: { id: frame, price: (frameInfo(frame)).price, owned: own.has(frame) },
    packs: { left: packs, table: X.PACKS, stock_cap: X.STOCK_CAP },
    market: mk,
    chest: { cost: X.CHEST.cost, left: Math.max(0, X.CHEST.per_day - Math.round(today)), opened: chests },
    prestige: { owned: [...own], frame: eq.frame, title: eq.title },
    star_cap: X.STAR_CAP, overflow: ov.stars > 0 ? ov : null,
  };
}

export async function shopOp(ctx: ShopCtx, pid: string, op: string, arg: string, nowMs: number): Promise<SReply> {
  const { rs, ws } = ctx;
  const now = Math.floor(nowMs / 1000);
  const bal = await ws.walletBalance(pid);
  if (bal === null) return R(409, { error: "sync first" });
  if (op === "view") return R(200, await view(ctx, pid, nowMs));
  const parts = arg.split(":");

  if (op === "buy") {
    const kind = parts[0], id = parts[1] ?? "", ref = parts[2] ?? "";
    if (!REF_RE.test(ref)) return R(400, { error: "bad ref", balance: bal });
    if (kind === "pack") {
      const p = (X.PACKS as Record<string, { item: string; units: number; price: number }>)[id];
      if (!p) return R(400, { error: "unknown item", balance: bal });
      const reason = `spend:pack:${id}`;
      const retry = (await ws.walletRefs(pid, reason, now - DAY_S)).includes(ref);
      if (!retry && (await packUnitsToday(ws, pid, p.item, now)) + p.units
          > (X.PACK_UNITS_PER_DAY as Record<string, number>)[p.item]) return R(429, { error: "pack limit", balance: bal });
      const r = await ws.walletChange(pid, -p.price, reason, ref, now);
      if (!r.ok) return R(402, { error: "insufficient", balance: r.balance });
      await grantUnits(ws, pid, p.item, p.units, `pk:${ref}`, now);
      return R(200, { ok: true, balance: r.balance, price: p.price, item: p.item, units: p.units, dup: r.dup });
    }
    if (kind === "frame" || kind === "title") {
      const info = kind === "frame" ? frameInfo(id) : titleInfo(id);
      if (!info || info.kind === "star") return R(400, { error: "unknown item", balance: bal });
      if (info.kind === "limited") {
        // only while it is the frame of the week (10 minutes of grace after the turn-over)
        if (weeklyFrame(nowMs) !== id && weeklyFrame(nowMs - 600_000) !== id) return R(410, { error: "gone", balance: bal });
      }
      if ((await ownedPrestige(ws, pid)).has(id)) return R(200, { ok: true, balance: bal, price: 0, dup: true });
      const r = await ws.walletChange(pid, -info.price, `spend:prestige:${id}`, "own", now);
      if (!r.ok) return R(402, { error: "insufficient", balance: r.balance });
      return R(200, { ok: true, balance: r.balance, price: info.price, dup: r.dup });
    }
    return R(400, { error: "unknown item", balance: bal });
  }

  if (op === "mkt") {
    const id = parts[0], ref = parts[1] ?? "";
    if (!REF_RE.test(ref)) return R(400, { error: "bad ref" });
    // this week's market - or the one that just ended
    const at = [nowMs, nowMs - 600_000].find((t) => market(t).some((m) => m.id === id));
    if (at === undefined) return R(410, { error: "gone" });
    const m = market(at).find((x) => x.id === id)!;
    const wk = weekIndex(at);
    const reason = `spend:mkt:${id}`, full = `${wk}:${ref}`;
    const refs = (await rs.starRefs(pid, reason)).filter((r) => r.startsWith(`${wk}:`));
    const retry = refs.includes(full);
    if (!retry && (m.kind === "frame" || m.kind === "title") && (await ownedPrestige(ws, pid)).has(String(m.payload))) {
      return R(409, { error: "owned" });
    }
    if (!retry && refs.length >= m.limit) return R(429, { error: "market limit" });
    const r = await rs.starChange(pid, -m.stars, reason, full, now);
    if (!r.ok) return R(402, { error: "insufficient", stars: r.balance });
    let balance = bal;
    if (m.kind === "shield" || m.kind === "revive") await grantUnits(ws, pid, m.kind, Number(m.payload), `mk:${wk}:${ref}`, now);
    else if (m.kind === "gems") balance = (await ws.walletChange(pid, Number(m.payload), "mkt", `${wk}:${id}:${ref}`, now)).balance;
    else await ws.walletChange(pid, 0, `spend:prestige:${m.payload}`, "own", now);
    return R(200, { ok: true, stars: r.balance, balance, price: m.stars, dup: r.dup,
                    grant: { kind: m.kind, payload: m.payload } });
  }

  if (op === "chest") {
    const ref = parts[0] ?? "";
    if (!REF_RE.test(ref)) return R(400, { error: "bad ref" });
    await starOverflow(rs, ws, pid, now);
    const refs = await rs.starRefs(pid, "spend:chest");
    const mine = refs.find((r) => r.endsWith(`:${ref}`));
    const n = mine ? Number(mine.slice(0, mine.indexOf(":"))) : refs.length;
    if (!mine) {
      const today = Math.round(-(await rs.starSum(pid, "spend:chest", startOfDay(now))) / X.CHEST.cost);
      if (today >= X.CHEST.per_day) return R(429, { error: "chest limit" });
      const r = await rs.starChange(pid, -X.CHEST.cost, "spend:chest", `${n}:${ref}`, now);
      if (!r.ok) return R(402, { error: "insufficient", stars: r.balance });
    }
    const h = await ctx.sha256(`${ctx.salt}|${pid}|${n}`);
    const roll = parseInt(h.slice(0, 8), 16) % 100, roll2 = parseInt(h.slice(8, 16), 16);
    let acc = 0, row = X.CHEST.table[X.CHEST.table.length - 1];
    for (const t of X.CHEST.table) { acc += t.w; if (roll < acc) { row = t; break; } }
    let kind: string = row.kind, payload: string | number = row.payload;
    let balance = bal;
    if (kind === "frame") {
      // a cosmetic of the star pool, picked by the dice; one already owned pays diamonds instead. A retried request
      // (mine) must land on the same answer: it was converted if a "chest" diamond row for this index exists.
      const all = [...X.STAR_FRAMES, ...X.STAR_TITLES];
      const cand = all[roll2 % all.length];
      const converted = (await ws.walletRefs(pid, "chest", 0)).includes(String(n));
      if (converted || (!mine && (await ownedPrestige(ws, pid)).has(cand))) {
        kind = "gems"; payload = X.CHEST.dup_frame_gems;
        balance = (await ws.walletChange(pid, Number(payload), "chest", String(n), now)).balance;
      } else {
        payload = cand;
        await ws.walletChange(pid, 0, `spend:prestige:${cand}`, "own", now);
      }
    } else if (kind === "gems") {
      balance = (await ws.walletChange(pid, Number(payload), "chest", String(n), now)).balance;
    } else {
      await grantUnits(ws, pid, kind, Number(payload), `ch:${n}`, now);
    }
    return R(200, { ok: true, stars: (await rs.starTotals(pid)).balance, balance, n, dup: !!mine, reward: { kind, payload } });
  }

  if (op === "equip") {
    const slot = parts[0], id = parts[1] ?? "";
    if (slot !== "frame" && slot !== "title") return R(400, { error: "bad slot" });
    if (id && !(slot === "frame" ? frameInfo(id) : titleInfo(id))) return R(400, { error: "unknown item" });
    if (id && !(await ownedPrestige(ws, pid)).has(id)) return R(403, { error: "not owned" });
    const cur = await ws.getPrestige(pid);
    const next = slot === "frame" ? { frame: id, title: cur.title } : { frame: cur.frame, title: id };
    await ws.setPrestige(pid, next.frame, next.title);
    return R(200, { ok: true, ...next });
  }
  return R(400, { error: "bad op" });
}
