// Port of sim.py (HOLO deterministic simulation) for the leaderboard server.
// Keep in sync with sim.py: any physics change must be mirrored here (tools/export_ts_data.py regenerates the
// golden test vectors that prove both implementations agree).

export const SIM_DT = 1.0 / 60.0;
export const ARENA_W = 900.0;
export const ARENA_H = 1470.0;
export const TETHER = 100.0;
export const ORB_R = 15.0;
export const BASE_OMEGA = 0.052 * 60.0;
export const EDGE_MARGIN = 15.0;
export const SPAWN_GRACE = 3.5;
export const BUCKET = 60;
export const RAMP_EXP = 2.2;
export const SIM_VERSION = 10;
export const WALL_SHIELD_INVULN = 0.15;
export const BOUNCE_BOOST = 0.7;
export const SHRINK_TETHER = 62.0;
export const BREAK_R = 21.0;
export const SLOW_EASE = 0.05;
export const SLOW_FACTOR = 0.6;      // slow field: 60 % speed (levels 101+)
export const STRETCH_LONG = 1.6;     // tether stretch field kind +1 (levels 121+)
export const STRETCH_SHORT = 0.6;    // kind -1
export const STRETCH_TIME = 6.0;
export const SHORT_SPIN_MAX = 1.2;
export const TETHER_EASE_SOFT = 0.08;
export const STRETCH_SLOW = 0.15;
export const STRETCH_DECAY = 150;
export const FX_TIME = 10.0;
export const SHIELD_INVULN = 0.8;
export const SNAP_EVERY = 15;     // revive points (mirror of sim.py)
export const SNAP_KEEP = 8;
export const REVIVE_BACK = 60;
export const REVIVE_SAFE = 1.0;
export const REVIVE_CLEAR = 30.0;
export const REVIVE_SPIN_START = 0.12;   // revive R2 (1.0.6): starts turning at 12 % speed ...
export const REVIVE_SPIN_RAMP = 2.5;     // ... full speed again after this many seconds
export const REVIVE_SPIN_RAMP_R3 = 4.0;  // revive R3 (1.0.8): a longer spin-up
export const BARRIER_PASS = 0.8;   // a shield phases the pair through energy barriers only (sim v10)
export const MAX_LEVELS = 140;
export const CP_RADIUS = 60.0;       // checkpoints (1.0.9): either orb this close to the flag lights it
export const CHECKPOINT_SHIELD_S = 1.2;   // resume from a checkpoint (free, light help): every hit bounces for this long (or until the first tap) ...
export const CHECKPOINT_SLOW_S = 1.5;     // ... and the pair spins up from 12 % over this long (paid R3: unlimited shield until the tap, 4 s)
export const CHECKPOINT_FREE_RESUMES = 2; // the 3rd resume in a row from the SAME flag gets neither shield nor slow start
export const CP_PENALTY = 0.95;       // a clear that resumed from a checkpoint scores 95 %
const TWO_PI = Math.PI * 2.0;

// ---- Python float semantics -------------------------------------------------------------------------------
function pymod(a: number, b: number): number {
  let m = a % b;
  if (m !== 0 && (b < 0) !== (m < 0)) m += b;
  return m;
}

function pyfloordiv(a: number, b: number): number {
  const mod = a % b;
  let div = (a - mod) / b;
  if (mod !== 0 && (b < 0) !== (mod < 0)) div -= 1.0;
  if (div !== 0) {
    const fd = Math.floor(div);
    return div - fd > 0.5 ? fd + 1.0 : fd;
  }
  return 0;
}

const hypot = (x: number, y: number): number => Math.sqrt(x * x + y * y);

// ---- geometry ---------------------------------------------------------------------------------------------
function circleRectHit(cx: number, cy: number, r: number, x: number, y: number, w: number, h: number): boolean {
  const px = cx < x ? x : (cx > x + w ? x + w : cx);
  const py = cy < y ? y : (cy > y + h ? y + h : cy);
  const dx = cx - px;
  const dy = cy - py;
  return dx * dx + dy * dy < r * r;
}

/** How deep a circle reaches into a rect (<= 0: apart). Mirror of sim.py rect_penetration (sqrt, not hypot). */
function rectPenetration(cx: number, cy: number, r: number, x: number, y: number, w: number, h: number): number {
  const dx = Math.max(x - cx, 0.0, cx - (x + w));
  const dy = Math.max(y - cy, 0.0, cy - (y + h));
  if (dx === 0.0 && dy === 0.0) return r + Math.min(cx - x, x + w - cx, cy - y, y + h - cy);
  return r - Math.sqrt(dx * dx + dy * dy);
}

function circleSegmentHit(cx: number, cy: number, r: number, x1: number, y1: number, x2: number, y2: number, thickness = 6.0): boolean {
  const dx = x2 - x1;
  const dy = y2 - y1;
  const ll = dx * dx + dy * dy;
  const rr = r + thickness * 0.5;
  if (ll === 0) return (cx - x1) * (cx - x1) + (cy - y1) * (cy - y1) < rr * rr;
  let tt = ((cx - x1) * dx + (cy - y1) * dy) / ll;
  tt = tt < 0 ? 0.0 : (tt > 1 ? 1.0 : tt);
  const ex = x1 + tt * dx - cx;
  const ey = y1 + tt * dy - cy;
  return ex * ex + ey * ey < rr * rr;
}

// j reaches ~170 000 in the endless climb (y ~ 1e7): a million rows per column keeps every key distinct
const bkey = (i: number, j: number) => (i + 1000) * 1_000_000 + (j + 1000);

// ---- level data ---------------------------------------------------------------------------------------------
export class LevelData {
  id: number;
  start: [number, number];
  end: [number, number];
  height: number;
  speed: number;
  ramp: number;
  parTime: number;
  parSwaps: number;
  walls: number[][];
  reverseWalls: number[][];
  movingWalls: number[][];
  lasers: number[][];
  spinners: number[][];
  circles: number[][];
  checkpoints: number[][];     // 1.0.9 flags in route order (not part of the digest)
  stars: number[][];
  growth: number[][];
  shrink: number[][];
  boost: number[][];
  slow: number[][];
  stretch: number[][];
  shields: number[][];
  breakables: number[][];
  chasers: number[][];
  barriers: number[][];
  barrierWalls = new Set<number>();   // indices of the walls that are energy barriers (listed rounded in walls)
  endRect: [number, number, number, number];
  digest: string;
  wallBuckets = new Map<number, number[][]>();
  path: number[][] = [];
  segLen: number[] = [];
  cum: number[] = [0.0];
  pathTotal = 1.0;

  // deno-lint-ignore no-explicit-any
  constructor(d: any, digest = "") {
    this.digest = digest;
    this.id = Math.trunc(d.id ?? 0);
    this.start = [d.start[0], d.start[1]];
    this.end = [d.end[0], d.end[1]];
    this.height = Number(d.height ?? ARENA_H);
    this.speed = Number(d.speed ?? 1.0);
    this.ramp = Number(d.ramp ?? 0.15);
    this.parTime = Number(d.par_time ?? 40.0);
    this.parSwaps = Math.trunc(d.par_swaps ?? 20);
    const wp: number[][] = (d.waypoints ?? []).map((p: number[]) => [p[0], p[1]]);
    this.walls = (d.walls ?? []).map((w: number[]) => w.slice());
    this.reverseWalls = (d.reverse_walls ?? []).map((w: number[]) => w.slice());
    this.movingWalls = (d.moving_walls ?? []).map((m: number[]) => {
      const n = m.length > 8 ? 10 : 8;
      return m.concat(new Array(Math.max(0, n - m.length)).fill(0.0));
    });
    this.lasers = (d.lasers ?? []).map((l: number[]) => l.concat([3.0, 0.4, 0.0].slice(l.length - 4)));
    const pre = Boolean(d.pre_adjusted);          // endless stages: spinners / chasers already adjusted in their own map
    this.spinners = (d.spinners ?? []).map((s: number[]) => {
      const sp = s.concat([10.0].slice(s.length - 5));
      if (pre) return sp;
      const span = this.corridorSpan(sp[0], sp[1]);
      if (span <= 380.0) {
        sp[2] *= 0.5;
      }
      return sp;
    });
    this.circles = (d.circles ?? []).map((c: number[]) => c.slice());
    this.checkpoints = (d.checkpoints ?? []).map((c: number[]) => [Number(c[0]), Number(c[1])]);
    this.stars = (d.stars ?? []).slice(0, pre ? undefined : 3).map((s: number[]) => s.slice());   // endless: every stage's stars
    this.growth = (d.growth_zones ?? []).map((z: number[]) => z.concat([32.0].slice(z.length - 2)));
    this.shrink = (d.shrink_zones ?? []).map((z: number[]) => z.concat([30.0].slice(z.length - 2)));
    this.boost = (d.boost_pads ?? []).map((z: number[]) => z.concat([28.0].slice(z.length - 2)));
    this.slow = (d.slow_zones ?? []).map((z: number[]) => z.slice());
    this.stretch = (d.stretch_zones ?? []).map((z: number[]) => z.concat([1].slice(z.length - 3)));
    this.shields = (d.shields ?? []).map((z: number[]) => z.slice());
    this.breakables = (d.breakables ?? []).map((b: number[]) => b.slice());
    const OFFSET = 85.0;
    const SPEED_MULT = 0.90;
    this.chasers = (d.chasers ?? []).map((raw: number[]) => {
      const c = raw.concat(new Array(Math.max(0, 11 - raw.length)).fill(0.0));
      if (pre) return c;
      let [x, y, w, h, vx, vy, tx, ty, tw, th, maxDist] = c;
      const spd = hypot(vx, vy);
      if (spd > 1e-4) {
        const ux = vx / spd, uy = vy / spd;
        x -= ux * OFFSET;
        y -= uy * OFFSET;
        vx *= SPEED_MULT;
        vy *= SPEED_MULT;
        if (maxDist > 0.0) {
          maxDist = maxDist + OFFSET;
        }
      }
      return [x, y, w, h, vx, vy, tx, ty, tw, th, maxDist];
    });
    this.barriers = (d.barriers ?? []).map((b: number[]) => b.slice());
    this.walls.forEach((w, i) => {
      if (this.barriers.some((b) => w.every((a, k) => Math.abs(a - b[k]) <= 1.0))) this.barrierWalls.add(i);
    });
    this.endRect = [this.end[0] - 25.0, this.end[1] - 25.0, 50.0, 50.0];
    this.buildBuckets();
    this.buildPath(wp);
  }

  private corridorSpan(cx: number, cy: number): number {
    let leftDist = cx;
    let rightDist = ARENA_W - cx;
    let upDist = cy;
    let downDist = this.height - cy;
    for (const [x, y, wW, hH] of [...this.walls, ...this.reverseWalls]) {
      if (y <= cy && cy <= y + hH) {
        if (x + wW <= cx) leftDist = Math.min(leftDist, cx - (x + wW));
        else if (x >= cx) rightDist = Math.min(rightDist, x - cx);
      }
      if (x <= cx && cx <= x + wW) {
        if (y + hH <= cy) upDist = Math.min(upDist, cy - (y + hH));
        else if (y >= cy) downDist = Math.min(downDist, y - cy);
      }
    }
    return Math.min(leftDist + rightDist, upDist + downDist);
  }

  private buildBuckets() {
    for (let idx = 0; idx < this.walls.length; idx++) {
      const [x, y, w, h] = this.walls[idx];
      const barrier = this.barrierWalls.has(idx) ? 1 : 0;
      const i0 = Math.trunc(pyfloordiv(x, BUCKET)), i1 = Math.trunc(pyfloordiv(x + w, BUCKET)) + 1;
      const j0 = Math.trunc(pyfloordiv(y, BUCKET)), j1 = Math.trunc(pyfloordiv(y + h, BUCKET)) + 1;
      for (let i = i0; i < i1; i++) {
        for (let j = j0; j < j1; j++) {
          const k = bkey(i, j);
          let cell = this.wallBuckets.get(k);
          if (!cell) { cell = []; this.wallBuckets.set(k, cell); }
          cell.push([x, y, w, h, barrier]);
        }
      }
    }
  }

  private buildPath(wpIn: number[][]) {
    const wp = wpIn.length >= 2 ? wpIn : [this.start, this.end];
    this.path = wp;
    for (let i = 0; i < wp.length - 1; i++) {
      const l = hypot(wp[i + 1][0] - wp[i][0], wp[i + 1][1] - wp[i][1]);
      this.segLen.push(l);
      this.cum.push(this.cum[this.cum.length - 1] + l);
    }
    this.pathTotal = this.cum[this.cum.length - 1] || 1.0;
  }

  progress(px: number, py: number): number {
    let bestD = 1e18;
    let bestPos = 0.0;
    const wp = this.path;
    for (let i = 0; i < this.segLen.length; i++) {
      const l = this.segLen[i];
      if (l === 0) continue;
      const [x1, y1] = wp[i];
      const [x2, y2] = wp[i + 1];
      const dx = x2 - x1;
      const dy = y2 - y1;
      let tt = ((px - x1) * dx + (py - y1) * dy) / (l * l);
      tt = tt < 0 ? 0.0 : (tt > 1 ? 1.0 : tt);
      const ex = x1 + tt * dx - px;
      const ey = y1 + tt * dy - py;
      const d = ex * ex + ey * ey;
      if (d < bestD) {
        bestD = d;
        bestPos = this.cum[i] + tt * l;
      }
    }
    const p = bestPos / this.pathTotal;
    return p < 0 ? 0.0 : (p > 1 ? 1.0 : p);
  }

  movingRect(m: number[], t: number): number[] {
    if (m.length > 10 && m[10] === 1.0) {        // 1.0.8: round a rectangle at a steady pace (m[8] = +-1 way round)
      const rx = m[4], ry = m[5];
      const u = m[8] * (t * m[6] + m[7]) / TWO_PI;
      const s = (u - Math.floor(u)) * 4.0 * (rx + ry);
      let ox: number, oy: number;
      if (s < 2.0 * rx) { ox = s - rx; oy = -ry; }
      else if (s < 2.0 * rx + 2.0 * ry) { ox = rx; oy = s - 2.0 * rx - ry; }
      else if (s < 4.0 * rx + 2.0 * ry) { ox = 3.0 * rx + 2.0 * ry - s; oy = ry; }
      else { ox = -rx; oy = 4.0 * rx + 3.0 * ry - s; }
      return [m[0] + ox, m[1] + oy, m[2], m[3]];
    }
    if (m.length > 8) {                        // sim v9: independent x/y frequency (Lissajous drift)
      const offx = Math.sin(t * m[6] + m[7]);
      const offy = Math.sin(t * m[8] + m[9]);
      return [m[0] + offx * m[4], m[1] + offy * m[5], m[2], m[3]];
    }
    const off = Math.sin(t * m[6] + m[7]);
    return [m[0] + off * m[4], m[1] + off * m[5], m[2], m[3]];
  }

  chaserRect(c: number[], t0: number | null, t: number): number[] | null {
    if (t0 === null) return null;
    let dt = t - t0;
    if (dt < 0.0) dt = 0.0;
    if (c[10] > 0.0 && hypot(c[4], c[5]) * dt > c[10]) return null;
    return [c[0] + c[4] * dt, c[1] + c[5] * dt, c[2], c[3]];
  }

  laserActive(l: number[], t: number): boolean {
    const cycle = pymod(t + l[6], l[4]);
    return (cycle / l[4]) < l[5];
  }

  spinnerSegment(s: number[], t: number): number[] {
    const a = s[4] + s[3] * t;
    const c = Math.cos(a) * s[2];
    const d = Math.sin(a) * s[2];
    return [s[0] - c, s[1] - d, s[0] + c, s[1] + d];
  }
}

// ---- simulation -----------------------------------------------------------------------------------------------
class Orb {
  x: number; y: number; r = ORB_R; tr = ORB_R; m = 1.0; tm = 1.0;
  constructor(x: number, y: number) { this.x = x; this.y = y; }
}

/** A clean state of the pair's own motion (revive point), mirror of sim.py Sim._snap. */
type Cp = { snap: Snap; stretchSoft: boolean; stretchHold: number; stretchAmp: number; shields: number; stars: boolean[];
            shieldTaken: boolean[]; starPts: number; broken: boolean[]; chaseT0: (number | null)[]; t: number };
type Snap = { n: number; orbs: number[][]; piv: number; ang: number; rotSign: number; tether: number; tetherBase: number;
              fxT: number; boostT: number; smooth: number };

export class Sim {
  lvl: LevelData;
  margin: number;
  n = 0;
  t = 0.0;
  orbs: Orb[];
  piv = 0;
  tether = TETHER;
  tetherBase = TETHER;
  rotSign = 1.0;
  fxT = 0.0;
  stretchSoft = false;
  slowF = 1.0;
  stretchHold = 0;
  stretchAmp = 0.0;
  broken: boolean[];
  chaseT0: (number | null)[];
  smooth: number;
  boostT = 0.0;
  shields = 0;
  invuln = 0.0;
  wallEscaping = false;
  wallEscapeT = 0.0;
  barrierT = 0.0;
  swaps = 0;
  dead = false;
  won = false;
  stars: boolean[];
  shieldTaken: boolean[];
  comboStreak = 0;
  comboMult = 1;
  maxCombo = 1;
  comboPoints = 0;
  lastSwapT = 0.0;
  nearCool = 0.0;
  nearCount = 0;
  lastGrazeX: number | null = null;
  lastGrazeY: number | null = null;
  grazedCells = new Map<string, number>();
  starPts = 0;
  progress = 0.0;
  maxProgress = 0.0;
  reviveT = 0.0;
  guard = false;          // revive R2: every hit bounces (no shield used up) until the next tap
  guardWalls = false;     // revive R3: while guarded, walls stay solid even during a bounce's invulnerability
  spinRampS = REVIVE_SPIN_RAMP;   // seconds of the current revive's spin-up (R3: longer)
  spinRamp = 1.0;         // revive R2: rotation speed ramp 0 -> 1
  snaps: Snap[] = [];
  cpNext = 0;                    // checkpoints lit so far
  cpState: Cp | null = null;     // the pair at the latest lit checkpoint
  cpStreak = 0;                  // resumes in a row from the latest flag
  guardT = 0.0;                  // checkpoint resume: seconds of shield left (0 = no timer)
  cpUsed = 0;                    // deaths resumed from a checkpoint
  ang: number;

  constructor(lvl: LevelData, margin = 0.0) {
    this.lvl = lvl;
    this.margin = margin;
    const [sx, sy] = lvl.start;
    this.orbs = [new Orb(sx, sy), new Orb(sx, sy)];
    this.smooth = lvl.speed;
    this.stars = lvl.stars.map(() => false);
    this.shieldTaken = lvl.shields.map(() => false);
    this.broken = lvl.breakables.map(() => false);
    this.chaseT0 = lvl.chasers.map(() => null);
    this.ang = this.bestStartAngle();
    this.placeRotating();
    this.snaps = [this.snap()];
  }

  private snap(): Snap {
    return { n: this.n, orbs: this.orbs.map((o) => [o.x, o.y, o.r, o.tr, o.m, o.tm]), piv: this.piv, ang: this.ang,
             rotSign: this.rotSign, tether: this.tether, tetherBase: this.tetherBase, fxT: this.fxT, boostT: this.boostT,
             smooth: this.smooth };
  }

  get starsCollected(): number { return this.stars.filter((s) => s).length; }
  get protected(): boolean { return this.invuln > 0 || (this.swaps === 0 && this.t < SPAWN_GRACE); }
  private get pivot(): Orb { return this.orbs[this.piv]; }
  private get rotating(): Orb { return this.orbs[1 - this.piv]; }

  private placeRotating() {
    const p = this.orbs[this.piv];
    const r = this.orbs[1 - this.piv];
    r.x = p.x + Math.cos(this.ang) * this.tether;
    r.y = p.y + Math.sin(this.ang) * this.tether;
  }

  private bestStartAngle(): number {
    const lvl = this.lvl;
    const [sx, sy] = lvl.start;
    let bestA = 0.0, bestC = -1.0;
    for (let i = 0; i < 36; i++) {
      const a = i * (TWO_PI / 36.0);
      const tx = sx + Math.cos(a) * TETHER;
      const ty = sy + Math.sin(a) * TETHER;
      if (!(25 <= tx && tx <= ARENA_W - 25 && 25 <= ty && ty <= lvl.height - 25)) continue;
      let c = 9999.0;
      for (const rects of [lvl.walls, lvl.reverseWalls]) {
        for (const [x, y, w, h] of rects) {
          const px = tx < x ? x : (tx > x + w ? x + w : tx);
          const py = ty < y ? y : (ty > y + h ? y + h : ty);
          c = Math.min(c, hypot(tx - px, ty - py));
        }
      }
      for (const m of lvl.movingWalls) {
        const [x, y, w, h] = lvl.movingRect(m, 0.0);
        const px = tx < x ? x : (tx > x + w ? x + w : tx);
        const py = ty < y ? y : (ty > y + h ? y + h : ty);
        c = Math.min(c, hypot(tx - px, ty - py));
      }
      if (c > bestC) { bestC = c; bestA = a; }
    }
    return bestA;
  }

  // ---- paid help (revive / bought shield), mirror of sim.py; normal physics unchanged
  addShield() { this.shields += 1; }

  /** Back to where the pair safely was at least a second before it died; walls stay solid, moving hazards spare it
   *  for REVIVE_SAFE seconds (mirror of sim.py Sim.revive). */
  revive(guarded = false, walls = false) {
    this.dead = false;
    const target = this.n - REVIVE_BACK;
    let s: Snap | null = null;
    let fallback = this.snaps[0];
    for (let i = this.snaps.length - 1; i >= 0; i--) {         // newest first: the latest point well away from walls
      const c = this.snaps[i];
      if (c.n > target) continue;
      if (fallback === this.snaps[0] && i !== 0) fallback = c;
      if (!c.orbs.some((v) => this.wallHit(v[0], v[1], v[2] + REVIVE_CLEAR, 1))) { s = c; break; }
    }
    if (s === null) s = fallback;
    this.piv = s.piv; this.ang = s.ang; this.rotSign = s.rotSign; this.tether = s.tether; this.tetherBase = s.tetherBase;
    this.fxT = s.fxT; this.boostT = s.boostT; this.smooth = s.smooth;
    for (let i = 0; i < 2; i++) {
      const o = this.orbs[i], v = s.orbs[i];
      o.x = v[0]; o.y = v[1]; o.r = v[2]; o.tr = v[3]; o.m = v[4]; o.tm = v[5];
    }
    this.invuln = 0.0;
    this.wallEscaping = false;
    this.wallEscapeT = 0.0;
    this.barrierT = 0.0;
    this.reviveT = REVIVE_SAFE;
    this.snaps = [s];
    this.guardT = 0.0;
    if (guarded) { this.guard = true; this.spinRamp = 0.0; }
    this.guardWalls = guarded && walls;
    this.spinRampS = guarded && walls ? REVIVE_SPIN_RAMP_R3 : REVIVE_SPIN_RAMP;
  }

  /** A flag lit: remember the pair as it is (mirror of sim.py Sim._take_checkpoint). */
  private takeCheckpoint() {
    this.cpState = {
      snap: this.snap(), stretchSoft: this.stretchSoft, stretchHold: this.stretchHold, stretchAmp: this.stretchAmp,
      shields: this.shields, stars: this.stars.slice(), shieldTaken: this.shieldTaken.slice(), starPts: this.starPts,
      broken: this.broken.slice(), chaseT0: this.chaseT0.slice(), t: this.t,
    };
    this.cpNext += 1;
    this.cpStreak = 0;
  }

  /** Continue after dying from the latest lit checkpoint (free, assist "C"); mirror of sim.py resume_checkpoint. */
  resumeCheckpoint(): boolean {
    const cp = this.cpState;
    if (cp === null || !this.dead) return false;
    this.dead = false;
    const s = cp.snap;
    this.piv = s.piv; this.ang = s.ang; this.rotSign = s.rotSign; this.tether = s.tether; this.tetherBase = s.tetherBase;
    this.fxT = s.fxT; this.boostT = s.boostT; this.smooth = s.smooth;
    for (let i = 0; i < 2; i++) {
      const o = this.orbs[i], v = s.orbs[i];
      o.x = v[0]; o.y = v[1]; o.r = v[2]; o.tr = v[3]; o.m = v[4]; o.tm = v[5];
    }
    this.stretchSoft = cp.stretchSoft; this.stretchHold = cp.stretchHold; this.stretchAmp = cp.stretchAmp;
    this.shields = cp.shields;
    this.stars = cp.stars.slice();
    this.shieldTaken = cp.shieldTaken.slice();
    this.starPts = cp.starPts;
    this.broken = cp.broken.slice();
    const shift = this.t - cp.t;
    this.chaseT0 = cp.chaseT0.map((v) => (v === null ? null : v + shift));
    this.grace = 0.0;
    this.invuln = 0.0;
    this.wallEscaping = false;
    this.wallEscapeT = 0.0;
    this.barrierT = 0.0;
    this.reviveT = REVIVE_SAFE;
    this.snaps = [s];
    this.cpStreak += 1;
    this.cpUsed += 1;
    if (this.cpStreak <= CHECKPOINT_FREE_RESUMES) {
      this.guard = true;
      this.guardT = CHECKPOINT_SHIELD_S;
      this.guardWalls = true;
      this.spinRamp = 0.0;
      this.spinRampS = CHECKPOINT_SLOW_S;
    } else {
      this.guard = false;
      this.guardT = 0.0;
      this.guardWalls = false;
      this.spinRamp = 1.0;
    }
    return true;
  }

  swap() {
    if (this.dead || this.won) return;
    this.guard = false;
    this.guardT = 0.0;
    this.guardWalls = false;
    const since = this.t - this.lastSwapT;
    this.lastSwapT = this.t;
    if (0.28 <= since && since <= 1.35) {
      this.comboStreak += 1;
      const s = this.comboStreak;
      this.comboMult = s >= 8 ? 4 : (s >= 5 ? 3 : (s >= 2 ? 2 : 1));
      if (this.comboMult > this.maxCombo) this.maxCombo = this.comboMult;
    } else {
      this.comboStreak = 0;
      this.comboMult = 1;
    }
    this.tether = this.tetherBase + 3.5 * this.rotating.m;
    this.piv = 1 - this.piv;
    this.ang += Math.PI;
    if (this.ang > TWO_PI) this.ang -= TWO_PI;
    this.swaps += 1;
    this.comboPoints += 100 * this.comboMult;
  }

  step() {
    if (this.dead || this.won) return;
    const dt = SIM_DT;
    const lvl = this.lvl;
    this.n += 1;
    this.t += dt;
    const t = this.t;
    const o0 = this.orbs[0], o1 = this.orbs[1];
    const piv = this.orbs[this.piv];
    const rot = this.orbs[1 - this.piv];
    const ang0 = this.ang;

    for (const o of [o0, o1]) {
      if (o.r !== o.tr) o.r += (o.tr - o.r) * 0.18;
      if (o.m !== o.tm) o.m += (o.tm - o.m) * 0.18;
    }
    if (this.stretchSoft) {
      this.tether += (this.tetherBase - this.tether) * TETHER_EASE_SOFT;
      if (this.tetherBase === TETHER && Math.abs(this.tether - TETHER) < 1.0) this.stretchSoft = false;
    } else {
      this.tether += (this.tetherBase - this.tether) * 0.14;
    }

    const prog = lvl.progress(piv.x, piv.y);
    this.progress = prog;
    if (prog > this.maxProgress) this.maxProgress = prog;

    let target = lvl.speed * (1.0 + lvl.ramp * Math.pow(prog, RAMP_EXP));
    if (this.boostT > 0) {
      this.boostT -= dt;
      target *= 1.35;
    }
    this.smooth += (target - this.smooth) * 0.04;

    let omega = BASE_OMEGA * this.smooth / Math.pow(rot.m, 0.35);
    let slowTarget = 1.0;
    if (lvl.slow.length) {                   // slow field: either orb inside -> the turning factor eases down to SLOW_FACTOR
      for (const z of lvl.slow) {
        if (hypot(o0.x - z[0], o0.y - z[1]) < z[2] + o0.r * 0.5 || hypot(o1.x - z[0], o1.y - z[1]) < z[2] + o1.r * 0.5) {
          slowTarget = SLOW_FACTOR;
          break;
        }
      }
    }
    if (lvl.slow.length || this.slowF !== 1.0) {
      this.slowF += (slowTarget - this.slowF) * SLOW_EASE;
      if (Math.abs(this.slowF - 1.0) < 1e-4) this.slowF = 1.0;
      omega *= this.slowF;
    }
    if (this.stretchHold > 0) omega *= 1.0 - (STRETCH_SLOW * this.stretchHold) / STRETCH_DECAY;
    if (this.spinRamp < 1.0) {               // just revived (R2): turning slowly, easing back to full speed
      omega *= REVIVE_SPIN_START + (1.0 - REVIVE_SPIN_START) * this.spinRamp * this.spinRamp;
      this.spinRamp = Math.min(1.0, this.spinRamp + dt / this.spinRampS);
    }
    const dAng = omega * dt * this.rotSign;
    let sub = dAng / 4.0;

    let mrects = lvl.movingWalls.map((m) => lvl.movingRect(m, t));
    const lasers = lvl.lasers.filter((l) => lvl.laserActive(l, t)).map((l) => [l[0], l[1], l[2], l[3]]);
    const spins = lvl.spinners.map((s) => lvl.spinnerSegment(s, t).concat([s[5]]));
    if (lvl.chasers.length) {
      for (let i = 0; i < lvl.chasers.length; i++) {
        const c = lvl.chasers[i];
        if (this.chaseT0[i] === null && (circleRectHit(o0.x, o0.y, o0.r, c[6], c[7], c[8], c[9]) ||
            circleRectHit(o1.x, o1.y, o1.r, c[6], c[7], c[8], c[9]))) {
          this.chaseT0[i] = t;
        }
      }
      const extra: number[][] = [];
      for (let i = 0; i < lvl.chasers.length; i++) {
        const r_ = lvl.chaserRect(lvl.chasers[i], this.chaseT0[i], t);
        if (r_ !== null) extra.push(r_);
      }
      mrects = mrects.concat(extra);
    }

    const rev = lvl.reverseWalls;
    if (rev.length > 0) {
      // sim v10: bounce whenever a step would take the swinging orb deeper into a bumper (mirror of sim.py)
      const px = piv.x, py = piv.y;
      const rr = rot.r;
      for (let k = 0; k < 4; k++) {
        const prev = this.ang;
        const ox = px + Math.cos(prev) * this.tether;
        const oy = py + Math.sin(prev) * this.tether;
        this.ang += sub;
        const tx = px + Math.cos(this.ang) * this.tether;
        const ty = py + Math.sin(this.ang) * this.tether;
        let bounced = false;
        for (let idx = 0; idx < rev.length; idx++) {
          const [x, y, w, h] = rev[idx];
          const pen = rectPenetration(tx, ty, rr, x, y, w, h);
          if (pen > 0.0 && pen > rectPenetration(ox, oy, rr, x, y, w, h) + 1e-9) {
            this.rotSign = -this.rotSign;
            sub = -sub;
            this.ang = prev;
            if (this.boostT < BOUNCE_BOOST) this.boostT = BOUNCE_BOOST;
            bounced = true;
            break;
          }
        }
        if (bounced) break;
      }
    } else {
      this.ang += dAng;
    }

    if (this.ang > TWO_PI) this.ang -= TWO_PI;
    else if (this.ang < 0) this.ang += TWO_PI;
    rot.x = piv.x + Math.cos(this.ang) * this.tether;
    rot.y = piv.y + Math.sin(this.ang) * this.tether;
    if (this.swaps === 0 && this.t < SPAWN_GRACE && this.wallHit(rot.x, rot.y, rot.r + this.margin)) {
      this.ang = ang0;
      this.rotSign = -this.rotSign;
      rot.x = piv.x + Math.cos(this.ang) * this.tether;
      rot.y = piv.y + Math.sin(this.ang) * this.tether;
    }

    if (lvl.stretch.length) {                       // touching a field stretches the tether once; it then shortens slowly by itself
      let kind = 0;
      for (const z of lvl.stretch) {
        if (hypot(rot.x - z[0], rot.y - z[1]) < z[2] + rot.r * 0.5) kind = z[3] > 0 ? 1 : -1;
      }
      if (kind !== 0) {
        this.stretchAmp = TETHER * ((kind > 0 ? STRETCH_LONG : STRETCH_SHORT) - 1.0);
        this.stretchHold = STRETCH_DECAY;
        this.stretchSoft = true;
        this.tetherBase = TETHER + this.stretchAmp;
      } else if (this.stretchHold > 0) {
        this.stretchHold -= 1;
        this.tetherBase = TETHER + (this.stretchAmp * this.stretchHold) / STRETCH_DECAY;
      }
    }
    if (lvl.growth.length || lvl.shrink.length || lvl.boost.length) {
      for (const orb of [rot, piv]) {
        for (const z of lvl.growth) {
          if (hypot(orb.x - z[0], orb.y - z[1]) < z[2] + orb.r * 0.5) {
            if (orb.tr < 24) { orb.tr = 26.0; orb.tm = 2.2; this.tetherBase = TETHER; }
            this.fxT = FX_TIME;
          }
        }
        for (const z of lvl.shrink) {
          if (hypot(orb.x - z[0], orb.y - z[1]) < z[2] + orb.r * 0.5) {
            if (orb.tr > 11) { orb.tr = 9.0; orb.tm = 0.5; this.tetherBase = SHRINK_TETHER; }
            this.fxT = FX_TIME;
          }
        }
        for (const z of lvl.boost) {
          if (hypot(orb.x - z[0], orb.y - z[1]) < z[2] + orb.r * 0.5 && this.boostT <= 0.2) this.boostT = 1.3;
        }
      }
    }

    if (this.fxT > 0.0) {
      this.fxT -= dt;
      if (this.fxT <= 0.0) {
        this.fxT = 0.0;
        for (const orb of [o0, o1]) { orb.tr = ORB_R; orb.tm = 1.0; }
        this.tetherBase = TETHER;
      }
    }

    for (let i = 0; i < lvl.shields.length; i++) {
      if (!this.shieldTaken[i]) {
        const z = lvl.shields[i];
        for (const orb of [o0, o1]) {
          if (hypot(orb.x - z[0], orb.y - z[1]) < 20 + orb.r) {
            this.shieldTaken[i] = true;
            this.shields = Math.min(3, this.shields + 1);
            break;
          }
        }
      }
    }

    for (let i = 0; i < lvl.stars.length; i++) {
      if (!this.stars[i]) {
        const z = lvl.stars[i];
        for (const orb of [o0, o1]) {
          if (hypot(orb.x - z[0], orb.y - z[1]) < 16 + orb.r) {
            this.stars[i] = true;
            this.starPts += 1500 * this.comboMult;
            break;
          }
        }
      }
    }

    if (this.invuln > 0) this.invuln -= dt;
    if (this.reviveT > 0) this.reviveT -= dt;
    if (this.guardT > 0) {                       // a checkpoint resume's shield runs out on its own
      this.guardT -= dt;
      if (this.guardT <= 0) { this.guard = false; this.guardWalls = false; }
    }
    if (this.barrierT > 0) {
      this.barrierT -= dt;
      if (this.barrierT < 0.2) {
        for (const orb of [o0, o1]) {
          for (const [bx, by, bw, bh] of lvl.barriers) {
            if (circleRectHit(orb.x, orb.y, orb.r + this.margin + 2.0, bx, by, bw, bh)) this.barrierT = 0.2;
          }
        }
      }
    }
    this.nearCool -= dt;

    if (this.nearCool <= 0 && lvl.walls.length) {
      for (const orb of [o0, o1]) {
        if (this.wallHit(orb.x, orb.y, orb.r + 7) && !this.wallHit(orb.x, orb.y, orb.r)) {
          const key = `${Math.trunc(orb.x / 60)},${Math.trunc(orb.y / 60)}`;
          const lastT = this.grazedCells.get(key) ?? -999.0;
          const distOk = this.lastGrazeX === null ||
            hypot(orb.x - this.lastGrazeX, orb.y - this.lastGrazeY) >= 45.0;
          if (this.t - lastT >= 4.0 && distOk) {
            this.nearCount += 1;
            this.nearCool = 0.35;
            this.lastGrazeX = orb.x;
            this.lastGrazeY = orb.y;
            this.grazedCells.set(key, this.t);
            break;
          }
        }
      }
    }

    // wall-escape recovery (sim v8): keep a shield-bounced pair protected until it is truly clear of the wall it
    // bounced off, instead of a fixed timer that can expire while still embedded ("stuck in the wall").
    if (this.wallEscaping) {
      this.wallEscapeT += dt;
      const stillStuck = this.wallHit(o0.x, o0.y, o0.r + this.margin, 1) || this.wallHit(o1.x, o1.y, o1.r + this.margin, 1);
      if (stillStuck && this.wallEscapeT < 1.0) {
        this.invuln = Math.max(this.invuln, 0.05);
      } else {
        this.wallEscaping = false;
      }
    }

    // revive R3: while guarded and invulnerable after a bounce, the swinging orb still may not enter a wall
    // (an orb already inside one - the wall-escape case - is free to move out)
    if (this.guardWalls && this.protected) {
      if (this.wallHit(rot.x, rot.y, rot.r + this.margin, 1)) {
        const ox = piv.x + Math.cos(ang0) * this.tether;
        const oy = piv.y + Math.sin(ang0) * this.tether;
        if (!this.wallHit(ox, oy, rot.r + this.margin, 1)) {
          this.ang = ang0;
          rot.x = ox; rot.y = oy;
          this.rotSign = -this.rotSign;
        }
      }
    }

    if (!this.protected) {
      const phasing = this.barrierT > 0;
      let kind = this.fatal(o0, mrects, lasers, spins, phasing);
      let hit: Orb | null = kind ? o0 : null;
      if (!kind) {
        kind = this.fatal(o1, mrects, lasers, spins, phasing);
        if (kind) hit = o1;
      }
      if (hit) {
        if (this.shields > 0 || this.guard) {
          if (!this.guard) this.shields -= 1;
          if (kind === 2) {
            this.barrierT = BARRIER_PASS;
          } else {
            this.invuln = SHIELD_INVULN;
            this.rotSign = -this.rotSign;
            if (this.wallHit(hit.x, hit.y, hit.r + this.margin + 1.0, 1)) {
              this.ang = ang0;
              rot.x = piv.x + Math.cos(this.ang) * this.tether;
              rot.y = piv.y + Math.sin(this.ang) * this.tether;
              this.wallEscaping = true;
              this.wallEscapeT = 0.0;
              this.invuln = WALL_SHIELD_INVULN;
            }
          }
        } else {
          this.dead = true;
          return;
        }
      }
    }

    const [x, y, w, h] = lvl.endRect;
    if (circleRectHit(o0.x, o0.y, o0.r, x, y, w, h) || circleRectHit(o1.x, o1.y, o1.r, x, y, w, h)) {
      this.won = true;
      return;
    }
    if (this.cpNext < lvl.checkpoints.length && this.invuln <= 0 && !this.wallEscaping && this.barrierT <= 0) {
      const [cx, cy] = lvl.checkpoints[this.cpNext];
      if (hypot(o0.x - cx, o0.y - cy) < CP_RADIUS + o0.r || hypot(o1.x - cx, o1.y - cy) < CP_RADIUS + o1.r) this.takeCheckpoint();
    }
    if (this.n % SNAP_EVERY === 0 && this.invuln <= 0 && !this.wallEscaping && this.barrierT <= 0) {
      this.snaps.push(this.snap());
      if (this.snaps.length > SNAP_KEEP) this.snaps.shift();
    }
  }

  /** mode 0: every wall, 1: solid walls only, 2: energy barriers only. */
  private wallHit(cx: number, cy: number, r: number, mode = 0): boolean {
    const wb = this.lvl.wallBuckets;
    const i0 = Math.trunc(pyfloordiv(cx - r, BUCKET)), i1 = Math.trunc(pyfloordiv(cx + r, BUCKET)) + 1;
    const j0 = Math.trunc(pyfloordiv(cy - r, BUCKET)), j1 = Math.trunc(pyfloordiv(cy + r, BUCKET)) + 1;
    for (let i = i0; i < i1; i++) {
      for (let j = j0; j < j1; j++) {
        const cell = wb.get(bkey(i, j));
        if (cell) {
          for (const [x, y, w, h, b] of cell) {
            if (mode === 1 && b) continue;
            if (mode === 2 && !b) continue;
            if (circleRectHit(cx, cy, r, x, y, w, h)) return true;
          }
        }
      }
    }
    return false;
  }

  /** 0: no hit, 1: ordinary hit, 2: energy barrier (mirror of sim.py _fatal). An orb overlapping a barrier ignores
   *  the solid walls it touches; while phasing, barriers are ignored too. */
  private fatal(o: Orb, mrects: number[][], lasers: number[][], spins: number[][], phasing = false): number {
    const r = o.r + this.margin;
    const x = o.x, y = o.y;
    if (x < EDGE_MARGIN + this.margin || x > ARENA_W - EDGE_MARGIN - this.margin ||
        y < EDGE_MARGIN + this.margin || y > this.lvl.height - EDGE_MARGIN - this.margin) return 1;
    const inBarrier = this.lvl.barrierWalls.size > 0 && this.wallHit(x, y, r, 2);
    if (inBarrier) {
      if (!phasing) return 2;
    } else if (this.wallHit(x, y, r, 1)) return 1;
    for (let idx = 0; idx < this.lvl.breakables.length; idx++) {
      const [bx, by, bw, bh] = this.lvl.breakables[idx];
      if (!this.broken[idx] && circleRectHit(x, y, r, bx, by, bw, bh)) {
        if (o.r >= BREAK_R) this.broken[idx] = true;
        else return 1;
      }
    }
    if (this.reviveT <= 0) {                               // just revived: moving hazards spare the pair
      for (const [mx, my, mw, mh] of mrects) if (circleRectHit(x, y, r, mx, my, mw, mh)) return 1;
      for (const [x1, y1, x2, y2] of lasers) if (circleSegmentHit(x, y, r, x1, y1, x2, y2)) return 1;
      for (const [x1, y1, x2, y2, th] of spins) if (circleSegmentHit(x, y, r, x1, y1, x2, y2, th)) return 1;
    }
    for (const [cx, cy, cr] of this.lvl.circles) if ((x - cx) * (x - cx) + (y - cy) * (y - cy) < (r + cr) * (r + cr)) return 1;
    return 0;
  }
}

// ---- scoring / replay -------------------------------------------------------------------------------------------
export interface Result {
  level_total: number; stars: number; time: number; swaps: number; rank: string;
  base: number; time_bonus: number; swap_bonus: number; combo_bonus: number; near_miss_count: number;
}

export function computeResult(sim: Sim): Result {
  const lvl = sim.lvl;
  const stars = sim.starsCollected;
  const base = lvl.id * 1000;
  const timeBonus = Math.max(0, Math.trunc((lvl.parTime * 1.6 - sim.t) * 120));
  // Fewer swaps = more points (mirror of sim.py compute_result): no points for tapping itself.
  const swapBonus = Math.trunc((3000 + 150 * lvl.id) * lvl.parSwaps / Math.max(sim.swaps, lvl.parSwaps * 0.5, 1.0));
  const comboBonus = 0;
  const grazeBonus = sim.nearCount * 450;
  const starBonus = stars * 2500;
  const starMult = 1.0 + stars * 0.15;
  const subtotal = base + timeBonus + swapBonus + comboBonus + grazeBonus + starBonus;
  let total = Math.trunc(subtotal * starMult);
  if (sim.cpUsed > 0) total = Math.trunc(total * CP_PENALTY);     // resumed from a checkpoint: a small cut
  const tRatio = sim.t / Math.max(1.0, lvl.parTime);
  const sRatio = sim.swaps / Math.max(1, lvl.parSwaps);
  let rank: string;
  if (stars === 3 && tRatio <= 1.05 && sRatio <= 1.2) rank = "S+";
  else if (stars === 3 || (stars >= 2 && tRatio <= 0.95)) rank = "S";
  else if (stars >= 2 || (stars >= 1 && tRatio <= 1.25)) rank = "A";
  else if (stars >= 1) rank = "B";
  else rank = "C";
  return {
    level_total: total, stars, time: Math.round(sim.t * 1000) / 1000, swaps: sim.swaps, rank,
    base, time_bonus: timeBonus, swap_bonus: swapBonus, combo_bonus: comboBonus, near_miss_count: sim.nearCount,
  };
}

export type Assist = [number, "S" | "R" | "R2" | "R3" | "C"];

/** `assists`: paid help, [step, "S"] = a bought shield put on before that step, [step, "R"] = revive after dying at
 *  that step (mirror of sim.py replay). */
export function replay(lvl: LevelData, tapsIn: number[], maxSeconds = 400.0,
                       assists: Assist[] = []): { sim: Sim; result: Result | null } {
  const sim = new Sim(lvl);
  const taps = tapsIn.slice().sort((a, b) => a - b);
  const helps = assists.map((a) => [Number(a[0]), String(a[1])] as [number, string]).sort((a, b) => a[0] - b[0]);
  let ti = 0, hi = 0;
  const maxSteps = Math.trunc(maxSeconds / SIM_DT);
  while (sim.n < maxSteps && !sim.won) {
    while (hi < helps.length && helps[hi][0] <= sim.n && (helps[hi][1] === "S" || sim.dead)) {
      if (helps[hi][1] === "S") sim.addShield();
      else if (helps[hi][1] === "C") sim.resumeCheckpoint();
      else sim.revive(helps[hi][1] === "R2" || helps[hi][1] === "R3", helps[hi][1] === "R3");
      hi++;
    }
    if (sim.dead) break;
    while (ti < taps.length && taps[ti] <= sim.n) { sim.swap(); ti++; }
    sim.step();
  }
  return { sim, result: sim.won ? computeResult(sim) : null };
}
