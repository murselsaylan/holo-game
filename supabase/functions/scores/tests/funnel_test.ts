// First-run funnel route (/api/funnel) and the tutorial reward.  Run: deno run -A --no-check tests/funnel_test.ts
import { handle, FUNNEL_STEPS, FUNNEL_MAX_N } from "../handler.ts";
import { earnClaim, TUTORIAL_REWARD } from "../wallet.ts";

let failed = 0;
function check(name: string, ok: boolean, extra: unknown = "") {
  console.log(`${ok ? "PASS" : "FAIL"} ${name}`, extra);
  if (!ok) failed++;
}

class FunnelStore {
  rows = new Map<string, { n: number; first: number; last: number; platform: string; version: string }>();
  async ensure() {}
  async funnel(pid: string, events: { step: string; n: number }[], platform: string, version: string, now: number) {
    for (const e of events) {
      const k = pid + "|" + e.step, cur = this.rows.get(k);
      if (cur) { cur.n += e.n; cur.last = now; }
      else this.rows.set(k, { n: e.n, first: now, last: now, platform, version });
    }
  }
}

const pid = "a".repeat(32);
const post = (store: unknown, body: unknown, ip = "1.2.3.4", now = 1_800_000_000_000) =>
  handle(store as never, "POST", "/functions/v1/scores/api/funnel", new URLSearchParams(), JSON.stringify(body), ip, now);

const st = new FunnelStore();
let r = await post(st, { player_id: pid, platform: "android", version: "1.1.0",
                         events: [{ s: "app_open" }, { s: "tut_start" }, { s: "tut_death", n: 3 }, { s: "tut_death", n: 2 }] });
check("valid upload accepted", r.status === 200 && r.body.n === 3, r);
check("counts merged per step", st.rows.get(pid + "|tut_death")?.n === 5, st.rows.get(pid + "|tut_death"));
check("platform / version kept", st.rows.get(pid + "|app_open")?.version === "1.1.0");
r = await post(st, { player_id: pid, events: [{ s: "app_open", n: 2 }] }, "1.2.3.4", 1_800_000_060_000);
check("second upload adds up", st.rows.get(pid + "|app_open")?.n === 3 && st.rows.get(pid + "|app_open")?.first === 1_800_000_000);

check("unknown step refused", (await post(st, { player_id: pid, events: [{ s: "drop table" }] })).status === 400);
check("bad player id refused", (await post(st, { player_id: "XYZ", events: [{ s: "app_open" }] })).status === 400);
check("empty list refused", (await post(st, { player_id: pid, events: [] })).status === 400);
check("too many events refused", (await post(st, { player_id: pid, events: Array(21).fill({ s: "app_open" }) })).status === 400);
check("negative / fractional n refused",
      (await post(st, { player_id: pid, events: [{ s: "l1_fail", n: -4 }] })).status === 400
      && (await post(st, { player_id: pid, events: [{ s: "l1_fail", n: 1.5 }] })).status === 400);
await post(st, { player_id: pid, events: [{ s: "l1_fail", n: 9999 }] }, "9.9.9.9");
check("huge n capped", st.rows.get(pid + "|l1_fail")?.n === FUNNEL_MAX_N, st.rows.get(pid + "|l1_fail"));

let limitedAt = -1;
for (let i = 0; i < 40; i++) {
  const x = await post(st, { player_id: pid, events: [{ s: "app_open" }] }, "5.5.5.5");
  if (x.status === 429) { limitedAt = i; break; }
}
check("rate limited per address (30 a minute)", limitedAt === 30, limitedAt);

// an old store without the method (a server deployed before the table exists in tests) still answers ok
r = await post({ ensure: async () => {} }, { player_id: pid, events: [{ s: "app_open" }] }, "7.7.7.7");
check("store without funnel(): ok, nothing stored", r.status === 200);
check("every step name is short and plain", [...FUNNEL_STEPS].every((s) => /^[a-z0-9_]{1,24}$/.test(s)));

const c = await earnClaim({} as never, pid, "tutorial", "whatever", Date.now());
check("tutorial reward: fixed amount, one ref per account", "amount" in c && c.amount === TUTORIAL_REWARD && c.ref === "1" && c.reason === "tutorial", c);

if (failed) { console.log(`${failed} FUNNEL TESTS FAILED`); Deno.exit(1); }
console.log("ALL FUNNEL TESTS PASSED");
