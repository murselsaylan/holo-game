// Proves sim.ts == sim.py for the slow / stretch fields.  Run: deno run -A --no-check fields_parity_test.ts
import { readFileSync } from "node:fs";
import { LevelData, replay } from "./sim.ts";

const golden = JSON.parse(readFileSync(new URL("./fields_golden.json", import.meta.url), "utf-8"));
const raws: Record<number, any> = {};
for (const g of golden) if (g.raw) raws[g.case] = g.raw;
const cache: Record<number, LevelData> = {};
let bad = 0, maxDiff = 0, stretched = 0;
for (const g of golden) {
  cache[g.case] ??= new LevelData(raws[g.case], "x");
  const { sim } = replay(cache[g.case], g.taps, 40.0);
  const p = g.py, problems: string[] = [];
  const eq = (n: string, a: unknown, b: unknown) => { if (a !== b) problems.push(`${n}: ts=${a} py=${b}`); };
  eq("won", sim.won, p.won); eq("dead", sim.dead, p.dead); eq("n", sim.n, p.n); eq("swaps", sim.swaps, p.swaps);
  const o = sim.orbs, pos = [o[0].x, o[0].y, o[1].x, o[1].y];
  for (let i = 0; i < 4; i++) maxDiff = Math.max(maxDiff, Math.abs(pos[i] - p.orbs[i]));
  maxDiff = Math.max(maxDiff, Math.abs(sim.tether - p.tether), Math.abs(sim.tetherBase - p.base), Math.abs(sim.smooth - p.smooth), Math.abs(sim.t - p.t));
  if (p.base !== 100) stretched++;
  if (problems.length) { bad++; if (bad <= 8) console.log(`MISMATCH case ${g.case}: ${problems.join("; ")}`); }
}
console.log(`cases=${golden.length} ended-with-stretched-tether=${stretched} mismatches=${bad} maxFloatDiff=${maxDiff.toExponential(2)}`);
console.log(bad === 0 && maxDiff < 1e-9 ? "FIELDS PARITY OK" : "FIELDS PARITY FAILED");
if (bad || maxDiff >= 1e-9) process.exit(1);
