// Checkpoint parity: sim.ts replays runs that light flags, die and resume from the latest flag ("C") exactly like sim.py.
//   python tools/checkpoint_golden.py && deno run -A --no-check supabase/functions/scores/checkpoint_parity_test.ts
import { readFileSync } from "node:fs";
import { LevelData, replay } from "./sim.ts";
import { LEVELS, DIGESTS } from "./levels_data.ts";

const golden = JSON.parse(readFileSync(new URL("./checkpoint_golden.json", import.meta.url), "utf-8"));
let bad = 0, maxDiff = 0, resumes = 0;
for (const g of golden) {
  const lvl = new LevelData(LEVELS[String(g.level)], DIGESTS[String(g.level)]);
  resumes += g.assists.filter((a: any) => a[1] === "C").length;
  const { sim, result } = replay(lvl, g.taps, 100.0, g.assists);
  const p = g.py;
  const probs: string[] = [];
  if (sim.n !== p.n) probs.push(`n ts=${sim.n} py=${p.n}`);
  if (sim.won !== p.won) probs.push(`won ts=${sim.won} py=${p.won}`);
  if (sim.dead !== p.dead) probs.push(`dead ts=${sim.dead} py=${p.dead}`);
  if (sim.cpNext !== p.cp_next) probs.push(`cp_next ts=${sim.cpNext} py=${p.cp_next}`);
  if (sim.cpUsed !== p.cp_used) probs.push(`cp_used ts=${sim.cpUsed} py=${p.cp_used}`);
  if (sim.starsCollected !== p.stars) probs.push(`stars ts=${sim.starsCollected} py=${p.stars}`);
  if (sim.shields !== p.shields) probs.push(`shields ts=${sim.shields} py=${p.shields}`);
  if ((result ? result.level_total : null) !== p.total) probs.push(`total ts=${result?.level_total} py=${p.total}`);
  const o = sim.orbs, pos = [o[0].x, o[0].y, o[1].x, o[1].y];
  for (let i = 0; i < 4; i++) maxDiff = Math.max(maxDiff, Math.abs(pos[i] - p.orbs[i]));
  if (probs.length) { bad++; if (bad <= 8) console.log(`MISMATCH level ${g.level}: ${probs.join("; ")}`); }
}
console.log(`cases=${golden.length} resumes=${resumes} mismatches=${bad} maxFloatDiff=${maxDiff.toExponential(2)}`);
console.log(bad === 0 && maxDiff < 1e-6 ? "CHECKPOINT PARITY OK" : "CHECKPOINT PARITY FAILED");
if (bad || maxDiff >= 1e-6) process.exit(1);
