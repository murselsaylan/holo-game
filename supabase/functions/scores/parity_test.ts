// Proves sim.ts behaves exactly like sim.py.  Run:  node supabase/functions/scores/parity_test.ts
// (Node >= 22.18 strips the types; Deno can run it too: deno run --allow-read parity_test.ts)
import { readFileSync } from "node:fs";
import { LevelData, replay } from "./sim.ts";
import { LEVELS, DIGESTS } from "./levels_data.ts";

const golden = JSON.parse(readFileSync(new URL("./golden.json", import.meta.url), "utf-8"));
const cache: Record<string, LevelData> = {};
let bad = 0, maxDiff = 0, wins = 0, deaths = 0;
for (const g of golden) {
  const key = String(g.level);
  cache[key] ??= new LevelData(LEVELS[key], DIGESTS[key]);
  const lvl = cache[key];
  const { sim, result } = replay(lvl, g.taps, Math.max(90.0, lvl.parTime * 8));
  const p = g.py;
  const problems: string[] = [];
  const eq = (name: string, a: unknown, b: unknown) => { if (a !== b) problems.push(`${name}: ts=${a} py=${b}`); };
  eq("won", sim.won, p.won); eq("dead", sim.dead, p.dead); eq("n", sim.n, p.n); eq("swaps", sim.swaps, p.swaps);
  eq("stars", sim.starsCollected, p.stars); eq("near", sim.nearCount, p.near); eq("combo", sim.comboPoints, p.combo);
  eq("total", result ? result.level_total : null, p.total); eq("rank", result ? result.rank : null, p.rank);
  const o = sim.orbs;
  const pos = [o[0].x, o[0].y, o[1].x, o[1].y];
  for (let i = 0; i < 4; i++) maxDiff = Math.max(maxDiff, Math.abs(pos[i] - p.orbs[i]));
  maxDiff = Math.max(maxDiff, Math.abs(sim.smooth - p.smooth), Math.abs(sim.t - p.t));
  if (sim.won) wins++; if (sim.dead) deaths++;
  if (problems.length) { bad++; if (bad <= 8) console.log(`MISMATCH level ${g.level} (${g.taps.length} taps): ${problems.join("; ")}`); }
}
console.log(`cases=${golden.length} wins=${wins} deaths=${deaths} mismatches=${bad} maxFloatDiff=${maxDiff.toExponential(2)}`);
for (const k of ["1", "50", "100"]) if (LEVELS[k].id !== Number(k)) { console.log("level table broken"); bad++; }
console.log(bad === 0 ? "PARITY OK" : "PARITY FAILED");
if (bad) process.exit(1);
