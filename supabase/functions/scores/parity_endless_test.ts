// Endless parity: endless.ts replays Python's golden climbs exactly.
//   python tools/endless_golden.py && node supabase/functions/scores/parity_endless_test.ts
import { readFileSync } from "node:fs";
import { poolDigest, replayEndless } from "./endless.ts";
import { ENDLESS_POOL } from "./endless_data.ts";

const golden = JSON.parse(readFileSync(new URL("./endless_golden.json", import.meta.url), "utf-8"));
let bad = 0, maxDiff = 0, stages = 0;
const t0 = Date.now();
if (poolDigest() !== ENDLESS_POOL.digest) { console.log(`pool digest ts=${poolDigest()} py=${ENDLESS_POOL.digest}`); bad++; }
for (const g of golden) {
  const run = replayEndless(g.seed, g.taps, g.end, undefined, g.assists ?? []);
  const p = g.py, probs: string[] = [];
  for (const [k, a, b] of [["n", run.n, p.n], ["dead", run.dead, p.dead], ["metres", run.metres, p.metres], ["stars", run.stars, p.stars],
                           ["points", run.points, p.points], ["w0", run.w0, p.w0],
                           ["stage", run.stage, p.stage]] as [string, unknown, unknown][]) if (a !== b) probs.push(`${k} ts=${a} py=${b}`);
  const o = run.sim.orbs, pos = [o[0].x, o[0].y, o[1].x, o[1].y];
  for (let i = 0; i < 4; i++) maxDiff = Math.max(maxDiff, Math.abs(pos[i] - p.orbs[i]));
  stages = Math.max(stages, run.stage);
  if (probs.length) { bad++; if (bad <= 8) console.log(`MISMATCH ${g.seed}: ${probs.join("; ")}`); }
}
console.log(`cases=${golden.length} maxStage=${stages} mismatches=${bad} maxFloatDiff=${maxDiff.toExponential(2)} ${Date.now() - t0}ms`);
console.log(bad === 0 && maxDiff < 1e-6 ? "ENDLESS PARITY OK" : "ENDLESS PARITY FAILED");
if (bad || maxDiff >= 1e-6) process.exit(1);
