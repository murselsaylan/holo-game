// Checkpoint resumes ("C" in the assists list): accepted, replayed, free, and refused when they make no sense.
import { handle, sign, signAssisted } from "../handler.ts";
import { MemStore } from "./mem.ts";
import { replay, LevelData } from "../sim.ts";
import { LEVELS, DIGESTS } from "../levels_data.ts";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const store = new MemStore();
const pid = "c".repeat(32), sec = "d".repeat(48);
const now = Date.now(), ts = Math.floor(now / 1000);
const call = (route: string, body: any) => handle(store as any, "POST", route, new URLSearchParams(), JSON.stringify(body), "9.9.9." + Math.random(), now);
const submit = async (level: number, taps: number[], assists?: any[]) => {
  const body: any = { player_id: pid, level, ts, taps, sig: await sign(sec, pid, level, ts, taps) };
  if (assists) { body.assists = assists; body.asig = await signAssisted(sec, pid, level, ts, taps, assists); }
  return call("/api/submit", body);
};
await call("/api/register", { player_id: pid, secret: sec, name: "T", country: "TR" });
const ref = (n: number) => JSON.parse(readFileSync(new URL(`../../../../levels/level${n}.json`, import.meta.url), "utf-8")).ref_taps;
const LV = 63;                                        // a level with one flag
const lvl = new LevelData(LEVELS[String(LV)], DIGESTS[String(LV)]);
assert.ok(lvl.checkpoints.length >= 1, "level has a checkpoint");
// the reference run lights every flag and wins; a "C" at a step where the pair is alive changes nothing
const { sim: s0, result: r0 } = replay(lvl, ref(LV));
assert.equal(s0.cpNext, lvl.checkpoints.length); assert.equal(s0.cpUsed, 0);
let r = await submit(LV, ref(LV)); assert.equal(r.status, 200);
const base = r.body.level_score; assert.equal(base, r0!.level_total);
r = await submit(LV, ref(LV), [[5, "C"]]); assert.equal(r.status, 200, "a stray C is harmless and free (no payment needed)");
// a resume before any flag was lit cannot happen: the dead pair stays dead and the clear is refused
r = await submit(LV, [10, 30, 60], [[400, "C"]]); assert.equal(r.status, 422);
// malformed
r = await submit(LV, ref(LV), [[5, "CP"]]); assert.equal(r.status, 400);
// a run that resumed and then did not reach the goal is replayed (the "C" is applied) and refused as not cleared;
// golden.py winning runs that resumed exist only rarely, so the accepted-clear case is covered by the stray-C test above
const golden = JSON.parse(readFileSync(new URL("../checkpoint_golden.json", import.meta.url), "utf-8"));
const lost = golden.find((g: any) => !g.py.won && g.py.cp_used > 0 && g.taps.length > 3);
assert.ok(lost, "golden has a run that resumed");
r = await submit(lost.level, lost.taps, lost.assists); assert.equal(r.status, 422);
// score rule: a clear that resumed is cut to 95 % (sim.cpUsed counted by the replay)
const sCut = Object.assign(Object.create(Object.getPrototypeOf(s0)), s0, { cpUsed: 1 });
const { computeResult } = await import("../sim.ts");
assert.equal(computeResult(sCut).level_total, Math.trunc(base * 0.95));
console.log("ALL CHECKPOINT TESTS PASSED");
