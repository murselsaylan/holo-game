// Endless climb, mirror of endless.py (keep them identical: parity_endless_test.ts replays Python's golden runs).
// The server rebuilds the run's world from its seed (week + the run's nonce), replays the taps and measures the height.
import { ARENA_W, LevelData, Sim } from "./sim.ts";
import { LEGACY, LEVELS } from "./levels_data.ts";
import { ENDLESS_POOL } from "./endless_data.ts";
import { ENDLESS_POOL_V5 } from "./endless_data_v5.ts";

export const ENDLESS_VERSION = 5;
/** Versions the server still replays: v2 clients (1.0.6) start at 0.95, v3 (1.0.7) at the 1.10 floor, v4 (1.0.8+) the
 *  same climb built from the 1.0.8 campaign maps (slower, small spinners). v2 / v3 games carry the maps they shipped
 *  with: their stages are built from those (LEGACY, one shipped version per changed level). */
export const ENDLESS_VERSIONS = [2, 3, 4, 5];
/** v5 (1.0.9): every stage is a zone drawn from one campaign sector (look, music, hazard mix), some stages carry an
 *  event (star rain / shield drop / calm bubble), the sector 6 / 7 fields are in play, metre goals pay diamonds. v2-v4
 *  keep their own pool (endless_data.ts, frozen) and rules. */
// deno-lint-ignore no-explicit-any
const SHIPPED: Record<string, any> = {};
for (const e of Object.values(LEGACY)) SHIPPED[String(e.level)] = e.data;
export const Y_BASE = 10_000_000.0;
export const GAP = 640.0;
export const TUNNEL = 340.0;
export const SIDE = 45.0;
export const WINDOW = 4;
export const PX_PER_M = 10.0;
export const MAX_STEPS = 60 * 60 * 25;
export const POINTS_PER_M = 10;
export const POINTS_PER_STAR = 100;
export const DIAMOND_EVERY_M = 100;               // 1.0.8: a diamond every 100 m (was 500), up to 60 a day (was 20)
export const DIAMONDS_PER_DAY = 60;
/** Metre goals (v5): [metres, diamonds], each paid once per player and week (reason "endless_goal"). */
export const GOALS: [number, number][] = [[250, 5], [500, 10], [1000, 20], [2000, 40], [3000, 60]];
/** Weekly climb prize (1.0.8): the top 10 of last week's climbs, paid once on the next wallet sync. */
export const WEEK_PRIZES = [150, 120, 100, 50, 50, 50, 50, 50, 50, 50];

// the same insertion order as endless.py FAMILY_TIER (the barrier walls go with "barriers")
const FAMILY_TIER: [string, number][] = [
  ["reverse_walls", 1], ["moving_walls", 1], ["circles", 2],
  ["growth_zones", 3], ["breakables", 3], ["barriers", 3], ["shields", 3],
  ["shrink_zones", 4], ["boost_pads", 4], ["chasers", 4], ["lasers", 5], ["spinners", 5],
  ["slow_zones", 3], ["stretch_zones", 5],
];
const RECT_KEYS = ["walls", "reverse_walls", "breakables", "barriers"];
const POINT_KEYS = ["circles", "growth_zones", "shrink_zones", "boost_pads", "shields", "slow_zones", "stretch_zones"];
const PI = 3.141592653589793;

export const tierOf = (k: number) => (k >= 20 ? 7 : Math.min(6, Math.floor(k / 2)));
export const stageSpeed = (k: number, v = ENDLESS_VERSION) =>
  Math.min(1.50, v >= 3 ? Math.max(1.10, 0.95 + 0.022 * k) : 0.95 + 0.022 * k);

const enc = new TextEncoder();
export function fnv1a(text: string): number {
  let h = 0x811C9DC5;
  for (const b of enc.encode(text)) {
    h ^= b;
    h = Math.imul(h, 0x01000193) >>> 0;
  }
  return h >>> 0;
}

/** ISO week of a unix time (UTC), e.g. "2026-W39" (Python date.isocalendar()). */
export function weekOf(unixS: number): string {
  const d = new Date(Math.floor(unixS) * 1000);
  const day = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()));
  const dow = day.getUTCDay() || 7;                       // Monday 1 .. Sunday 7
  day.setUTCDate(day.getUTCDate() + 4 - dow);             // the Thursday of this week decides the ISO year
  const y = day.getUTCFullYear();
  const w = Math.ceil(((day.getTime() - Date.UTC(y, 0, 1)) / 86_400_000 + 1) / 7);
  return `${y}-W${String(w).padStart(2, "0")}`;
}

/** Monday 00:00 UTC of the week that contains unixS (seconds). */
export function weekStart(unixS: number): number {
  const d = new Date(Math.floor(unixS) * 1000);
  const dow = d.getUTCDay() || 7;
  return Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate() - (dow - 1)) / 1000;
}

export function seedOf(week: string, nonce = "", v = ENDLESS_VERSION): string {
  const base = `HOLO-ENDLESS|${week}|v${v}`;
  return nonce ? `${base}|${nonce}` : base;
}

// deno-lint-ignore no-explicit-any
const dataOf = (v: number): any => (v >= 5 ? ENDLESS_POOL_V5 : ENDLESS_POOL);
const POOLS: Record<number, Record<number, number[]>> = {};
const poolOf = (v: number): Record<number, number[]> => {
  const key = v >= 5 ? 5 : 4;
  return POOLS[key] ??= Object.fromEntries(
    Object.entries(dataOf(v).tiers).map(([k, x]) => [Number(k), (x as number[]).slice()]));
};

// deno-lint-ignore no-explicit-any
const starsRaw = (v: number): Record<string, Record<string, number[][]>> => (dataOf(v) as any).stars ?? {};
// deno-lint-ignore no-explicit-any
const slotsRaw = (v: number): Record<string, Record<string, number[][]>> => (dataOf(v) as any).slots ?? {};
// deno-lint-ignore no-explicit-any
const sectorsRaw = (v: number): Record<string, number> => (dataOf(v) as any).sectors ?? {};

/** The collectable stars of a stage (stage coordinates), as placed by tools/endless_pool.py. */
export function poolStars(tier: number, levelId: number, v = ENDLESS_VERSION): number[][] {
  return (starsRaw(v)[String(tier)]?.[String(levelId)] ?? []).map((p) => p.slice());
}
/** Clear spots of a stage where a zone event may drop something (v5). */
export function poolSlots(tier: number, levelId: number, v = ENDLESS_VERSION): number[][] {
  return (slotsRaw(v)[String(tier)]?.[String(levelId)] ?? []).map((p) => p.slice());
}
export const sectorOf = (levelId: number, v = ENDLESS_VERSION): number => sectorsRaw(v)[String(levelId)] ?? 1;

function nestedJson(raw: Record<string, Record<string, number[][]>>): string {
  const per: Record<string, Record<string, number[][]>> = {};
  for (const tr of Object.keys(raw).map(Number).sort((a, b) => a - b)) {
    per[String(tr)] = {};
    for (const lid of Object.keys(raw[String(tr)]).map(Number).sort((a, b) => a - b)) {
      per[String(tr)][String(lid)] = raw[String(tr)][String(lid)];
    }
  }
  return JSON.stringify(per);
}

/** Same as endless.py pool_digest(): the game sends it, a different pool (outdated game) is refused. */
export function poolDigest(v = ENDLESS_VERSION): string {
  const POOL = poolOf(v);
  const obj: Record<string, number[]> = {};
  for (const k of Object.keys(POOL).map(Number).sort((a, b) => a - b)) obj[String(k)] = POOL[k];
  let txt = JSON.stringify(obj);
  if (Object.keys(starsRaw(v)).length) txt += "|" + nestedJson(starsRaw(v));
  if (v >= 5) {
    if (Object.keys(slotsRaw(v)).length) txt += "|" + nestedJson(slotsRaw(v));
    const sec = sectorsRaw(v);
    const ks = Object.keys(sec).map(Number).sort((a, b) => a - b);
    if (ks.length) txt += "|" + JSON.stringify(Object.fromEntries(ks.map((k) => [String(k), sec[String(k)]])));
  }
  return fnv1a(txt).toString(16).padStart(8, "0");
}

export const RAMP_STAGES = 24;
export const NO_REPEAT = 6;
const ZONE_SECTORS: [number, number[]][] = [[0, [1]], [1, [1, 2]], [3, [2, 3]], [5, [2, 3, 4]], [7, [3, 4, 5]], [10, [3, 4, 5, 6]], [14, [4, 5, 6, 7]]];
function zoneSectors(k: number): number[] {
  let out = ZONE_SECTORS[0][1];
  for (const [first, secs] of ZONE_SECTORS) if (k >= first) out = secs;
  return out;
}

/** Same as endless.py plan(): v5 first picks the stage's zone sector, then a map of it; the pick window slides from
 *  the tier's easiest maps to its hardest. */
export function plan(seed: string, count: number, prev: number[] = [], v = ENDLESS_VERSION): number[] {
  const out = prev.slice();
  const POOL = poolOf(v);
  for (let k = out.length; k < count; k++) {
    let choices = POOL[tierOf(k)];
    if (v >= 5) {
      const tierPool = choices;
      let secs = zoneSectors(k).filter((s) => tierPool.some((l) => sectorOf(l, v) === s));
      if (!secs.length) secs = [sectorOf(tierPool[0], v)];
      if (secs.length > 1 && out.length) {
        const f = secs.filter((s) => s !== sectorOf(out[out.length - 1], v));
        if (f.length) secs = f;
      }
      const sec = secs[fnv1a(`${seed}|z${k}`) % secs.length];
      const sub = tierPool.filter((l) => sectorOf(l, v) === sec);
      choices = sub.length ? sub : tierPool;
    }
    const n = choices.length;
    const center = Math.min(n - 1, Math.floor(((n - 1) * k) / RAMP_STAGES));
    const lo = Math.max(0, center - Math.floor((3 * n) / 10));
    const wide = seed.includes("|v5|") ? Math.floor((n * 11) / 20) : Math.floor(n / 5);
    const hi = Math.min(n, Math.max(lo + 1, center + wide + 1));
    const w = hi - lo;
    const i0 = fnv1a(`${seed}|${k}`) % w;
    const recent = out.slice(-NO_REPEAT);
    let pick = choices[lo + i0];
    for (let j = 0; j < w; j++) {
      const c = choices[lo + ((i0 + j) % w)];
      if (!recent.includes(c)) { pick = c; break; }
    }
    out.push(pick);
  }
  return out;
}

export const EV_NONE = 0, EV_STARS = 1, EV_SHIELD = 2, EV_BUBBLE = 3;
export const BUBBLE_R = 130.0;
/** Same as endless.py event_of(): never on stage 0, never twice in a row, only where the stage has clear spots. */
export function eventOf(seed: string, k: number, levelId: number, tier: number, prev: number, v = ENDLESS_VERSION): number {
  if (v < 5 || k === 0 || prev !== EV_NONE) return EV_NONE;
  const n = poolSlots(tier, levelId, v).length;
  if (n === 0) return EV_NONE;
  const h = fnv1a(`${seed}|ev${k}`) % 100;
  if (h < 16 && n >= 2) return EV_STARS;
  if (h < 28) return EV_SHIELD;
  if (h < 40) return EV_BUBBLE;
  return EV_NONE;
}
export function eventSlot(seed: string, k: number, levelId: number, tier: number, v = ENDLESS_VERSION): number[] {
  const sl = poolSlots(tier, levelId, v);
  return sl[fnv1a(`${seed}|es${k}`) % sl.length];
}

// ---------------------------------------------------------------------------------------------- stage geometry
function subRect(rect: number[], cut: number[]): number[][] {
  const [x, y, w, h] = rect;
  const [cx, cy, cw, ch] = cut;
  const ix0 = Math.max(x, cx), iy0 = Math.max(y, cy);
  const ix1 = Math.min(x + w, cx + cw), iy1 = Math.min(y + h, cy + ch);
  if (ix0 >= ix1 || iy0 >= iy1) return [rect.slice()];
  const out: number[][] = [];
  if (y < iy0) out.push([x, y, w, iy0 - y]);
  if (iy1 < y + h) out.push([x, iy1, w, y + h - iy1]);
  if (x < ix0) out.push([x, iy0, ix0 - x, iy1 - iy0]);
  if (ix1 < x + w) out.push([ix1, iy0, x + w - ix1, iy1 - iy0]);
  return out.filter((p) => p[2] > 1.0 && p[3] > 1.0);
}

const overlap = (r: number[], c: number[]) => r[0] < c[0] + c[2] && c[0] < r[0] + r[2] && r[1] < c[1] + c[3] && c[1] < r[1] + r[3];
const isBarrierWall = (w: number[], barriers: number[][]) =>
  barriers.some((bb) => [0, 1, 2, 3].every((i) => Math.abs(w[i] - bb[i]) <= 1.0));

// deno-lint-ignore no-explicit-any
function flip(d: any) {
  const h = Number(d.height);
  const pt = (p: number[]) => [p[0], h - p[1], ...p.slice(2)];
  const rc = (r: number[]) => [r[0], h - r[1] - r[3], r[2], r[3], ...r.slice(4)];
  d.start = pt(d.start);
  d.end = pt(d.end);
  d.waypoints = (d.waypoints ?? []).map(pt);
  for (const key of RECT_KEYS) d[key] = (d[key] ?? []).map(rc);
  for (const key of [...POINT_KEYS, "stars"]) d[key] = (d[key] ?? []).map(pt);
  d.lasers = (d.lasers ?? []).map((l: number[]) => [l[0], h - l[1], l[2], h - l[3], ...l.slice(4)]);
  d.spinners = (d.spinners ?? []).map((s: number[]) =>
    s.length > 4 ? [s[0], h - s[1], s[2], -s[3], -s[4], ...s.slice(5)] : [s[0], h - s[1], s[2], -s[3]]);
  d.moving_walls = (d.moving_walls ?? []).map((m0: number[]) => {
    const m = m0.length < 8 ? m0.concat(new Array(8 - m0.length).fill(0.0)) : m0.slice();
    let q = rc(m);
    if (q.length > 10 && q[10] === 1.0) {        // rectangle loop mirrored: the other way round, from P(c - s)
      q[7] = q[7] - q[8] * 6.283185307179586 * (4.0 * q[4] + 2.0 * q[5]) / (4.0 * (q[4] + q[5]));
      q[8] = -q[8];
    } else if (q.length > 8) q[9] = q[9] + PI;
    else q = [...q.slice(0, 8), q[6], q[7] + PI];
    return q;
  });
  d.chasers = (d.chasers ?? []).map((c0: number[]) => {
    const c = c0.concat(new Array(Math.max(0, 11 - c0.length)).fill(0.0));
    const q = rc(c);
    q[5] = -q[5];
    q[7] = h - c[7] - c[9];
    return q;
  });
}

// deno-lint-ignore no-explicit-any
export function buildStage(levelId: number, tier: number, first = false, v = ENDLESS_VERSION): any {
  const d = structuredClone((v < 4 && SHIPPED[String(levelId)]) || LEVELS[String(levelId)]);
  for (const [key, t] of FAMILY_TIER) {
    if (tier < t) {
      if (key === "barriers" && d.barriers && d.barriers.length) {
        d.walls = (d.walls ?? []).filter((w: number[]) => !isBarrierWall(w, d.barriers));
      }
      d[key] = [];
    }
  }
  d.stars = [];
  if (d.end[1] > d.start[1]) flip(d);
  const h = Number(d.height);
  const [sx, sy] = d.start, [ex, ey] = d.end;
  const cuts = [[ex - TUNNEL / 2, -10.0, TUNNEL, ey + 120.0]];
  if (!first) cuts.push([sx - TUNNEL / 2, sy - 110.0, TUNNEL, h - sy + 120.0]);
  const bars: number[][] = d.barriers ?? [];
  d.barriers = bars.filter((b) => !cuts.some((c) => overlap(b, c)));
  const walls: number[][] = [];
  for (const w of (d.walls ?? []) as number[][]) {
    if (isBarrierWall(w, bars)) {
      if (isBarrierWall(w, d.barriers)) walls.push(w.slice());
      continue;
    }
    let pieces = [w.slice()];
    for (const c of cuts) pieces = pieces.flatMap((q) => subRect(q, c));
    walls.push(...pieces);
  }
  d.walls = walls;
  for (const key of ["reverse_walls", "breakables"]) d[key] = (d[key] ?? []).filter((r: number[]) => !cuts.some((c) => overlap(r, c)));
  d.circles = (d.circles ?? []).filter((z: number[]) => !cuts.some((c) => overlap([z[0] - z[2], z[1] - z[2], 2 * z[2], 2 * z[2]], c)));
  const ld = new LevelData(d);
  d.spinners = ld.spinners.map((s) => s.slice());
  d.chasers = ld.chasers.map((c) => c.slice());
  d.pre_adjusted = true;
  return d;
}

class Stage {
  k: number; level: number; tier: number; top: number; bottom: number; height: number; speed: number;
  // deno-lint-ignore no-explicit-any
  d: any;
  counts: { breakables: number; chasers: number; shields: number; stars: number };

  sector: number; event: number;

  constructor(k: number, levelId: number, bottom: number, v = ENDLESS_VERSION, event = EV_NONE, slot: number[] | null = null) {
    this.k = k;
    this.sector = sectorOf(levelId, v);
    this.event = event;
    this.level = levelId;
    this.tier = tierOf(k);
    const local = buildStage(levelId, this.tier, k === 0, v);
    this.height = Number(local.height);
    this.bottom = bottom;
    this.top = bottom - this.height;
    this.speed = stageSpeed(k, v);
    const oy = this.top;
    // deno-lint-ignore no-explicit-any
    const d: any = { start: [local.start[0], local.start[1] + oy], end: [local.end[0], local.end[1] + oy] };
    for (const key of RECT_KEYS) d[key] = (local[key] ?? []).map((r: number[]) => [r[0], r[1] + oy, ...r.slice(2)]);
    for (const key of POINT_KEYS) d[key] = (local[key] ?? []).map((p: number[]) => [p[0], p[1] + oy, ...p.slice(2)]);
    d.moving_walls = (local.moving_walls ?? []).map((m: number[]) => [m[0], m[1] + oy, ...m.slice(2)]);
    d.lasers = (local.lasers ?? []).map((l: number[]) => [l[0], l[1] + oy, l[2], l[3] + oy, ...l.slice(4)]);
    d.spinners = (local.spinners ?? []).map((s: number[]) => [s[0], s[1] + oy, ...s.slice(2)]);
    d.chasers = (local.chasers ?? []).map((c: number[]) => [c[0], c[1] + oy, ...c.slice(2, 6), c[6], c[7] + oy, ...c.slice(8)]);
    // collectable stars: the stage's own, plus one in the open chamber below it (on the way into its tunnel)
    const stars = poolStars(this.tier, levelId, v);
    if (k > 0) stars.push([local.start[0], this.height + GAP * 0.45]);
    if (event === EV_STARS) stars.push(...poolSlots(this.tier, levelId, v));
    d.stars = stars.map((p: number[]) => [p[0], p[1] + oy]);
    if (event === EV_SHIELD && slot) d.shields.push([slot[0], slot[1] + oy]);
    else if (event === EV_BUBBLE && slot) d.slow_zones.push([slot[0], slot[1] + oy, BUBBLE_R]);
    this.d = d;
    this.counts = { breakables: d.breakables.length, chasers: d.chasers.length, shields: d.shields.length, stars: d.stars.length };
  }
}

class World {
  seed: string;
  ids: number[] = [];
  stages = new Map<number, Stage>();
  private bottoms: number[] = [Y_BASE];

  v: number;

  events: number[] = [];

  constructor(seed: string, v = ENDLESS_VERSION) { this.seed = seed; this.v = v; }

  private event(k: number): number {
    while (this.events.length <= k) {
      const j = this.events.length;
      this.events.push(eventOf(this.seed, j, this.ids[j], tierOf(j), j ? this.events[j - 1] : EV_NONE, this.v));
    }
    return this.events[k];
  }

  private make(k: number, bottom: number): Stage {
    const ev = this.event(k);
    const slot = ev === EV_SHIELD || ev === EV_BUBBLE ? eventSlot(this.seed, k, this.ids[k], tierOf(k), this.v) : null;
    return new Stage(k, this.ids[k], bottom, this.v, ev, slot);
  }

  stage(k: number): Stage {
    const s = this.stages.get(k);
    if (s) return s;
    if (this.ids.length <= k) this.ids = plan(this.seed, k + 1, this.ids, this.v);
    while (this.bottoms.length <= k) {
      const j = this.bottoms.length - 1;
      let sj = this.stages.get(j);
      if (!sj) {
        sj = this.make(j, this.bottoms[j]);
        this.stages.set(j, sj);
      }
      this.bottoms.push(sj.top - GAP);
    }
    const ns = this.make(k, this.bottoms[k]);
    this.stages.set(k, ns);
    return ns;
  }

  forgetBelow(k: number) {
    for (const j of [...this.stages.keys()]) if (j < k) this.stages.delete(j);
  }

  windowData(w0: number, count = WINDOW): LevelData {
    const st: Stage[] = [];
    for (let k = w0; k < w0 + count; k++) st.push(this.stage(k));
    // deno-lint-ignore no-explicit-any
    const d: any = {
      id: 0, title: "ENDLESS", height: st[0].bottom, speed: st[0].speed, ramp: 0.0, par_time: 9999.0, par_swaps: 9999,
      waypoints: [], stars: [], pre_adjusted: true, start: st[0].d.start.slice(), end: [ARENA_W / 2.0, 60.0],
    };
    for (const key of [...RECT_KEYS, ...POINT_KEYS, "moving_walls", "lasers", "spinners", "chasers", "stars"]) {
      d[key] = st.flatMap((s) => s.d[key].map((v: number[]) => v.slice()));
    }
    for (const s of st.slice(0, -1)) {
      const y = s.top - GAP;
      d.walls.push([0.0, y, SIDE, GAP], [ARENA_W - SIDE, y, SIDE, GAP]);
    }
    d.reverse_walls.push([-600.0, 0.0, 10.0, 10.0]);       // keeps every window on the sub-step swing path
    return new LevelData(d);
  }
}

/** [level, sector, event] of stages 0..count-1 - the parity test compares it with Python's World (zones + events). */
export function worldPlan(seed: string, count: number, v = ENDLESS_VERSION): number[][] {
  const w = new World(seed, v);
  const out: number[][] = [];
  for (let k = 0; k < count; k++) { const st = w.stage(k); out.push([st.level, st.sector, st.event]); }
  return out;
}

export class EndlessRun {
  world: World;
  w0 = 0;
  sim: Sim;
  startY: number;
  bestY: number;
  starsBanked = 0;          // stars collected in stages that already left the window

  constructor(seed: string, v = ENDLESS_VERSION) {
    this.world = new World(seed, v);
    this.sim = new Sim(this.world.windowData(0));
    this.startY = this.pivotY();
    this.bestY = this.startY;
  }

  pivotY(): number { return this.sim.orbs[this.sim.piv].y; }
  get n(): number { return this.sim.n; }
  get dead(): boolean { return this.sim.dead; }
  get metres(): number { return Math.trunc((this.startY - this.bestY) / PX_PER_M); }
  get stars(): number { return this.starsBanked + this.sim.stars.filter((x) => x).length; }
  get points(): number { return this.metres * POINTS_PER_M + this.stars * POINTS_PER_STAR; }

  stageAt(y: number): number {
    let k = this.w0;
    while (k < this.w0 + WINDOW - 1 && y < this.world.stage(k).top - GAP * 0.5) k++;
    return k;
  }

  get stage(): number { return this.stageAt(this.pivotY()); }

  swap() { this.sim.swap(); }

  step() {
    const s = this.sim;
    if (s.dead) return;
    const k = this.stageAt(this.pivotY());
    s.lvl.speed = this.world.stage(k).speed;
    s.step();
    const py = this.pivotY();
    if (py < this.bestY) this.bestY = py;
    if (!s.dead && this.stageAt(py) >= this.w0 + 2) this.advance();
  }

  private advance() {
    const s = this.sim;
    const old = this.world.stage(this.w0);
    this.w0 += 1;
    const nw = this.world.stage(this.w0 + WINDOW - 1);
    const lvl = this.world.windowData(this.w0);
    lvl.speed = s.lvl.speed;
    s.broken = s.broken.slice(old.counts.breakables).concat(new Array(nw.counts.breakables).fill(false));
    s.chaseT0 = s.chaseT0.slice(old.counts.chasers).concat(new Array(nw.counts.chasers).fill(null));
    s.shieldTaken = s.shieldTaken.slice(old.counts.shields).concat(new Array(nw.counts.shields).fill(false));
    this.starsBanked += s.stars.slice(0, old.counts.stars).filter((x) => x).length;
    s.stars = s.stars.slice(old.counts.stars).concat(new Array(nw.counts.stars).fill(false));
    s.lvl = lvl;
    this.world.forgetBelow(this.w0);
  }
}

/** Replay a climb: until death, `endStep` (the player quit) or maxSteps (mirror of endless.py replay). */
export const MAX_REVIVES = 3;

/** Same as endless.py assist_digest(): taps, plus the paid help when there is any. */
export function assistDigest(taps: number[], assists: [number, string][] = []): string {
  let txt = taps.map((x) => String(Math.trunc(x))).join(",");
  if (assists.length) {
    txt += "|" + assists.slice().sort((a, b) => a[0] - b[0]).map((a) => `${Math.trunc(a[0])}${a[1]}`).join(",");
  }
  return txt;
}

export function replayEndless(seed: string, tapsIn: number[], endStep: number | null = null, maxSteps = MAX_STEPS,
                              assists: [number, string][] = [], v = ENDLESS_VERSION): EndlessRun {
  const run = new EndlessRun(seed, v);
  const taps = tapsIn.slice().sort((a, b) => a - b);
  const helps = assists.map((a) => [Number(a[0]), String(a[1])] as [number, string]).sort((a, b) => a[0] - b[0]);
  const limit = endStep === null ? maxSteps : Math.min(maxSteps, Math.trunc(endStep));
  let i = 0, hi = 0;
  while (run.n < limit) {
    while (hi < helps.length && helps[hi][0] <= run.n && (helps[hi][1] === "S" || run.dead)) {
      if (helps[hi][1] === "S") run.sim.addShield(); else run.sim.revive(helps[hi][1] === "R2" || helps[hi][1] === "R3", helps[hi][1] === "R3");
      hi++;
    }
    if (run.dead) break;
    while (i < taps.length && taps[i] <= run.n) {
      run.swap();
      i++;
    }
    run.step();
  }
  return run;
}
