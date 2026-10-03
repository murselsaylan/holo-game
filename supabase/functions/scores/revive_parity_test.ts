// Revive parity: sim.ts replays runs with revives / bought shields exactly like sim.py.
//   python tools/revive_golden.py && node supabase/functions/scores/revive_parity_test.ts
import { readFileSync } from "node:fs";
import { LevelData, replay } from "./sim.ts";
import { LEVELS, DIGESTS } from "./levels_data.ts";

const golden = JSON.parse(readFileSync(new URL("./revive_golden.json", import.meta.url), "utf-8"));
let bad = 0, maxDiff = 0, revives = 0;
for (const g of golden) {
  const lvl = new LevelData(LEVELS[String(g.level)], DIGESTS[String(g.level)]);
  revives += g.assists.filter((a: any) => a[1] === "R" || a[1] === "R2").length;
  const { sim, result } = replay(lvl, g.taps, 90.0 + 30.0 * g.assists.length, g.assists);
  const p = g.py;
  const probs: string[] = [];
  if (sim.n !== p.n) probs.push(`n ts=${sim.n} py=${p.n}`);
  if (sim.won !== p.won) probs.push(`won ts=${sim.won} py=${p.won}`);
  if (sim.dead !== p.dead) probs.push(`dead ts=${sim.dead} py=${p.dead}`);
  if ((result ? result.level_total : null) !== p.total) probs.push(`total ts=${result?.level_total} py=${p.total}`);
  const o = sim.orbs, pos = [o[0].x, o[0].y, o[1].x, o[1].y];
  for (let i = 0; i < 4; i++) maxDiff = Math.max(maxDiff, Math.abs(pos[i] - p.orbs[i]));
  if (probs.length) { bad++; if (bad <= 8) console.log(`MISMATCH level ${g.level}: ${probs.join("; ")}`); }
}
console.log(`cases=${golden.length} revives=${revives} mismatches=${bad} maxFloatDiff=${maxDiff.toExponential(2)}`);
console.log(bad === 0 && maxDiff < 1e-6 ? "REVIVE PARITY OK" : "REVIVE PARITY FAILED");
if (bad || maxDiff >= 1e-6) process.exit(1);
