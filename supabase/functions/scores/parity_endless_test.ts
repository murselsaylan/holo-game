// Endless parity: endless.ts replays Python's golden climbs exactly.
//   python tools/endless_golden.py && deno run -A --no-check supabase/functions/scores/parity_endless_test.ts
// endless_golden_v5.json = the current code (zones, events); endless_golden.json (v4, 1.0.8 games) and
// endless_golden_v3.json (v3, 1.0.7 games on the maps they shipped with) are FROZEN: the server must keep replaying them.
import { readFileSync } from "node:fs";
import { poolDigest, replayEndless, worldPlan } from "./endless.ts";
import { ENDLESS_POOL } from "./endless_data.ts";
import { ENDLESS_POOL_V5 } from "./endless_data_v5.ts";

const load = (n: string) => JSON.parse(readFileSync(new URL(`./${n}`, import.meta.url), "utf-8"));
const all = load("endless_golden_v5.json").concat(load("endless_golden.json")).concat(load("endless_golden_v3.json"));
const golden = all.filter((g: any) => g.py);
const plans = all.filter((g: any) => g.plans).flatMap((g: any) => g.plans);
let bad = 0, maxDiff = 0, stages = 0;
const t0 = Date.now();
if (poolDigest(5) !== ENDLESS_POOL_V5.digest) { console.log(`v5 pool digest ts=${poolDigest(5)} py=${ENDLESS_POOL_V5.digest}`); bad++; }
if (poolDigest(4) !== ENDLESS_POOL.digest) { console.log(`v4 pool digest ts=${poolDigest(4)} py=${ENDLESS_POOL.digest}`); bad++; }
for (const g of golden) {
  const run = replayEndless(g.seed, g.taps, g.end, undefined, g.assists ?? [], g.v ?? 3);
  const p = g.py, probs: string[] = [];
  for (const [k, a, b] of [["n", run.n, p.n], ["dead", run.dead, p.dead], ["metres", run.metres, p.metres], ["stars", run.stars, p.stars],
                           ["points", run.points, p.points], ["w0", run.w0, p.w0],
                           ["stage", run.stage, p.stage]] as [string, unknown, unknown][]) if (a !== b) probs.push(`${k} ts=${a} py=${b}`);
  const o = run.sim.orbs, pos = [o[0].x, o[0].y, o[1].x, o[1].y];
  for (let i = 0; i < 4; i++) maxDiff = Math.max(maxDiff, Math.abs(pos[i] - p.orbs[i]));
  stages = Math.max(stages, run.stage);
  if (probs.length) { bad++; if (bad <= 8) console.log(`MISMATCH ${g.seed}: ${probs.join("; ")}`); }
}
let evSeen = 0;
for (const pl of plans) {
  const ts = worldPlan(pl.seed, pl.plan.length, pl.v);
  for (let k = 0; k < ts.length; k++) {
    if (ts[k].join() !== pl.plan[k].join()) { bad++; if (bad <= 8) console.log(`PLAN MISMATCH ${pl.seed} stage ${k}: ts=${ts[k]} py=${pl.plan[k]}`); break; }
    if (ts[k][2]) evSeen++;
  }
}
console.log(`cases=${golden.length} plans=${plans.length} events=${evSeen} maxStage=${stages} mismatches=${bad} maxFloatDiff=${maxDiff.toExponential(2)} ${Date.now() - t0}ms`);
console.log(bad === 0 && maxDiff < 1e-6 ? "ENDLESS PARITY OK" : "ENDLESS PARITY FAILED");
if (bad || maxDiff >= 1e-6) process.exit(1);
