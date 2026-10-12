// Route/anti-cheat tests for handler.ts with an in-memory store.  Run: node supabase/functions/scores/handler_test.ts
import { readFileSync } from "node:fs";
import { handle, sign, cleanName, signSave, signCode, signBests, codeHash } from "./handler.ts";
import type { Player, Ranks, Restored, Row, Store } from "./handler.ts";
import { SIM_VERSION } from "./sim.ts";
import type { Result } from "./sim.ts";
import { DIGESTS, LEGACY } from "./levels_data.ts";

class MemStore implements Store {
  players = new Map<string, Player>();
  bests = new Map<string, { score: number; stars: number; taps?: number[] }>();
  saves = new Map<string, string>();
  recovery = new Map<string, string>();         // hash -> pid
  ensure() { return Promise.resolve(); }
  saveCloud(pid: string, data: string, _now: number) { this.saves.set(pid, data); return Promise.resolve(); }
  setRecovery(pid: string, hash: string) {
    for (const [h, p] of this.recovery) if (p === pid) this.recovery.delete(h);
    this.recovery.set(hash, pid);
    return Promise.resolve();
  }
  playerBests(pid: string) {
    return Promise.resolve([...this.bests.entries()].filter(([k]) => k.startsWith(pid + "|"))
      .map(([k, v]) => ({ level: Number(k.split("|")[1]), score: v.score, stars: v.stars, time: 0, swaps: 0, rank: "A" })));
  }
  restore(hash: string): Promise<Restored | null> {
    const pid = this.recovery.get(hash);
    const p = pid ? this.players.get(pid) : undefined;
    if (!p) return Promise.resolve(null);
    const bests = [...this.bests.entries()].filter(([k]) => k.startsWith(pid + "|"))
      .map(([k, v]) => ({ level: Number(k.split("|")[1]), score: v.score, stars: v.stars, time: 0, swaps: 0, rank: "A" }));
    return Promise.resolve({ player: p, data: this.saves.get(pid!) ?? null, bests });
  }
  player(pid: string) { return Promise.resolve(this.players.get(pid) ?? null); }
  register(pid: string, secret: string, name: string, country: string) {
    const p = this.players.get(pid);
    if (!p) this.players.set(pid, { id: pid, secret, name, country, levels: 0, score: 0, stars: 0 });
    else if (p.secret !== secret) return Promise.resolve(false);
    else { p.name = name; p.country = country; }
    return Promise.resolve(true);
  }
  record(pid: string, level: number, res: Result, taps: number[]) {
    const k = `${pid}|${level}`;
    const cur = this.bests.get(k);
    const improved = !cur || res.level_total > cur.score;
    if (improved) this.bests.set(k, { score: res.level_total, stars: res.stars, taps });
    const mine = [...this.bests.entries()].filter(([key]) => key.startsWith(pid + "|"));
    const p = this.players.get(pid)!;
    p.levels = mine.reduce((a, [k]) => Math.max(a, Number(String(k).split("|").pop())), 0); p.score = mine.reduce((a, [, v]) => a + v.score, 0); p.stars = mine.reduce((a, [, v]) => a + v.stars, 0);
    return Promise.resolve({ improved, levels: p.levels, score: p.score, stars: p.stars });
  }
  reports: unknown[] = [];
  report(pid: string, kind: string, platform: string, version: string, text: string, now: number) {
    this.reports.push({ pid, kind, platform, version, text, now });
    return Promise.resolve();
  }
  ghost(level: number) {
    const b = [...this.bests.entries()].filter(([k]) => k.endsWith("|" + level)).sort(([, x], [, y]) => y.score - x.score)[0];
    if (!b) return Promise.resolve(null);
    const id = b[0].split("|")[0];
    return Promise.resolve({ id, name: this.players.get(id)!.name, score: b[1].score, taps: b[1].taps ?? [] });
  }
  ranks(pid: string): Promise<Ranks | null> {
    const me = this.players.get(pid);
    if (!me || me.levels === 0) return Promise.resolve(null);
    const better = (o: Player) => o.levels > 0 && (o.score > me.score || (o.score === me.score && o.levels > me.levels));
    const all = [...this.players.values()];
    return Promise.resolve({ rank: all.filter(better).length + 1, country_rank: all.filter((o) => o.country === me.country && better(o)).length + 1,
                             levels: me.levels, score: me.score, stars: me.stars });
  }
  board(scope: string, country: string, offset: number, limit: number) {
    let all = [...this.players.values()].filter((p) => p.levels > 0);
    if (scope === "country") all = all.filter((p) => p.country === country);
    all.sort((a, b) => b.score - a.score || b.levels - a.levels || a.name.localeCompare(b.name));
    const rows: Row[] = all.map((p) => ({ rank: all.filter((o) => o.score > p.score || (o.score === p.score && o.levels > p.levels)).length + 1,
                                          id: p.id, name: p.name, country: p.country, levels: p.levels, score: p.score, stars: p.stars }));
    return Promise.resolve({ rows: rows.slice(offset, offset + limit), total: all.length });
  }
  // diamond wallet (behaviour covered by the wallet tests; minimal in-memory version here)
  wallet = new Map<string, number>();
  walletLog = new Set<string>();
  walletOpen(pid: string, local: number, cap: number) {
    if (!this.wallet.has(pid)) this.wallet.set(pid, Math.min(cap, local));
    return Promise.resolve({ balance: this.wallet.get(pid)!, imported: null, gift: 0 });
  }
  walletBalance(pid: string) { return Promise.resolve(this.wallet.has(pid) ? this.wallet.get(pid)! : null); }
  walletChange(pid: string, delta: number, reason: string, ref: string) {
    const key = `${pid}|${reason}|${ref}`, bal = this.wallet.get(pid) ?? 0;
    if (this.walletLog.has(key)) return Promise.resolve({ ok: true, balance: bal, dup: true });
    if (bal + delta < 0) return Promise.resolve({ ok: false, balance: bal, dup: false });
    this.walletLog.add(key); this.wallet.set(pid, bal + delta);
    return Promise.resolve({ ok: true, balance: bal + delta, dup: false });
  }
  walletCount() { return Promise.resolve({ n: 0, last: 0 }); }
}

const golden = JSON.parse(readFileSync(new URL("./golden.json", import.meta.url), "utf-8"));
const refTaps = (lvl: number): number[] => golden.find((g: { level: number }) => g.level === lvl).taps.slice();

let ok = true;
const check = (name: string, cond: boolean, extra: unknown = "") => { ok = ok && cond; console.log((cond ? "PASS " : "FAIL ") + name, cond ? "" : JSON.stringify(extra)); };

const store = new MemStore();
const now = Date.now();
const post = (path: string, body: unknown, ip = "1.1.1.1") =>
  handle(store, "POST", "/functions/v1/scores" + path, new URLSearchParams(), JSON.stringify(body), ip, now);
const get = (path: string, q = "", ip = "1.1.1.1") =>
  handle(store, "GET", "/functions/v1/scores" + path, new URLSearchParams(q), "", ip, now);
const hex = (n: number) => Array.from({ length: n }, (_, i) => "0123456789abcdef"[(i * 7 + n) % 16]).join("");

const pid = hex(32), sec = hex(48);
const ts = Math.floor(now / 1000);
const signed = async (level: number, taps: number[], secret = sec, t = ts, extra = {}) =>
  ({ player_id: pid, level, ts: t, taps, sig: await sign(secret, pid, level, t, taps), ...extra });

check("health via prefixed path", (await get("/api/health")).body.sim === SIM_VERSION);
check("register", (await post("/api/register", { player_id: pid, secret: sec, name: "tester", country: "tr" })).status === 200);
const r1 = await post("/api/submit", await signed(1, refTaps(1)));
check("level 1 accepted + rank #1", r1.status === 200 && r1.body.world_rank === 1, r1);
const r2 = await post("/api/submit", await signed(2, refTaps(2)));
check("level 2 accepted, two levels", r2.status === 200 && r2.body.levels === 2, r2);
const pid2 = "c".repeat(32), sec2 = "d".repeat(48);
await post("/api/register", { player_id: pid2, secret: sec2, name: "ROOKIE", country: "JP" });
const t2 = refTaps(1);
const r3 = await post("/api/submit", { player_id: pid2, level: 1, ts, taps: t2, sig: await sign(sec2, pid2, 1, ts, t2) }, "2.2.2.2");
check("second player ranked #2", r3.status === 200 && r3.body.world_rank === 2, r3);
const lb = await get("/api/leaderboard", `scope=global&limit=10&player_id=${pid}`);
check("leaderboard order + me", (lb.body.rows as Row[]).map((r) => r.name).join() === "TESTER,ROOKIE" && (lb.body.me as Ranks).rank === 1, lb.body);
const lc = await get("/api/leaderboard", `scope=country&player_id=${pid}`);
check("country board only TR", (lc.body.rows as Row[]).every((r) => r.country === "TR"));
const la = await get("/api/leaderboard", `scope=around&player_id=${pid2}&limit=5`);
{ const g = await get("/api/ghost", "level=1");
  check("ghost = level 1's best run", g.status === 200 && (g.body.taps as number[]).join() === refTaps(1).join() && !!g.body.name, g.body);
  check("no ghost for an unplayed level", !("taps" in (await get("/api/ghost", "level=50")).body));
  check("bad ghost level (400)", (await get("/api/ghost", "level=x")).status === 400); }
{ const rp = await post("/api/report", { player_id: pid, kind: "fault", platform: "ios", version: "1.0.6", text: "Fatal Python error" }, "7.7.7.7");
  check("crash report stored", rp.status === 200 && store.reports.length === 1, rp.body);
  check("bad report refused", (await post("/api/report", { player_id: "x", kind: "fault", text: "a" }, "7.7.7.7")).status === 400); }
check("around board contains me", (la.body.rows as Row[]).some((r) => r.id === pid2));

check("garbage taps -> replay fails (422)", (await post("/api/submit", await signed(3, [10, 20, 30]))).status === 422);
check("bad signature (403)", (await post("/api/submit", await signed(1, refTaps(1), "0".repeat(48)))).status === 403);
const tampered = await signed(1, refTaps(1)); (tampered.taps as number[])[3] += 500;
check("tampered taps (403)", (await post("/api/submit", tampered)).status === 403);
check("superhuman tap rate (422)", (await post("/api/submit", await signed(1, [5, 6, 7]))).status === 422);
check("stale timestamp (400)", (await post("/api/submit", await signed(1, refTaps(1), sec, ts - 4000))).status === 400);
check("identity hijack (403)", (await post("/api/register", { player_id: pid, secret: "f".repeat(48), name: "HIJACK", country: "US" })).status === 403);
check("level out of range (400)", (await post("/api/submit", await signed(101, refTaps(1)))).status === 400);
{ const rr = await post("/api/submit", await signed(1, refTaps(1), sec, ts, { lvl: "deadbeef00" })); check("stale level digest (409)", rr.status === 409, rr); }
check("matching digest accepted", (await post("/api/submit", await signed(1, refTaps(1), sec, ts, { lvl: DIGESTS["1"] }))).status === 200);
{ // a rebuilt level: games not updated yet still submit runs on its previous version (levelgen/legacy_levels)
  const first = Object.entries(LEGACY)[0];
  if (first) {
    const [dg, e] = first;
    const old = JSON.parse(readFileSync(new URL(`../../../levelgen/legacy_levels/level${e.level}.json`, import.meta.url), "utf-8"));
    const ok = await post("/api/submit", await signed(e.level, old.ref_taps, sec, ts, { lvl: dg }));
    check("previous level version accepted", ok.status === 200, ok);
    const other = e.level === 1 ? 2 : 1;
    check("previous version of another level (409)", (await post("/api/submit", await signed(other, refTaps(other), sec, ts, { lvl: dg }))).status === 409);
  }
}
check("non-integer taps rejected", (await post("/api/submit", { player_id: pid, level: 1, ts, taps: [1.5, 200], sig: "x" })).status === 400);
check("malformed JSON rejected", (await handle(store, "POST", "/api/submit", new URLSearchParams(), "{oops", "1.1.1.1", now)).status === 400);
check("name cleaning", cleanName("  ahmet<script> ") === "PİLOT" && cleanName("ışık") === "IŞIK");

// ---- account recovery: cloud save + recovery code + restore
{
  const blob = JSON.stringify({ diamonds: 123, campaign_level: 7 });
  const sv = await post("/api/cloud/save", { player_id: pid, ts, data: blob, sig: await signSave(sec, pid, ts, blob) }, "3.3.3.3");
  check("cloud save accepted", sv.status === 200, sv);
  const bad = await post("/api/cloud/save", { player_id: pid, ts, data: blob, sig: await signSave("0".repeat(48), pid, ts, blob) }, "3.3.3.3");
  check("cloud save with a wrong key (403)", bad.status === 403);
  const c1 = await post("/api/cloud/code", { player_id: pid, ts, sig: await signCode(sec, pid, ts) }, "3.3.3.3");
  const code1 = String(c1.body.code ?? "");
  check("recovery code issued", c1.status === 200 && /^[A-Z2-9]{4}-[A-Z2-9]{4}-[A-Z2-9]{4}$/.test(code1), c1);
  const rs = await post("/api/cloud/restore", { code: code1.toLowerCase().replace(/-/g, " ") }, "4.4.4.4");
  check("restore by code (any case / separators)", rs.status === 200 && rs.body.player_id === pid && rs.body.secret === sec &&
        rs.body.data === blob && Array.isArray(rs.body.bests) && (rs.body.bests as unknown[]).length >= 1, rs.body);
  const c2 = await post("/api/cloud/code", { player_id: pid, ts, sig: await signCode(sec, pid, ts) }, "3.3.3.3");
  check("a new code replaces the old one", c2.status === 200 && (await post("/api/cloud/restore", { code: code1 }, "4.4.4.4")).status === 404);
  check("restore with a wrong code (404)", (await post("/api/cloud/restore", { code: "AAAA-BBBB-CCCC" }, "4.4.4.4")).status === 404);
  check("restore with a malformed code (400)", (await post("/api/cloud/restore", { code: "12" }, "4.4.4.4")).status === 400);
  check("code hash is stable", (await codeHash("ABCD2345EFGH")) === (await codeHash("ABCD2345EFGH")));
  let rl = 0;
  for (let i = 0; i < 12 && !rl; i++) if ((await post("/api/cloud/restore", { code: "ZZZZ-ZZZZ-ZZZZ" }, "5.5.5.5")).status === 429) rl = i;
  check("restore attempts are rate limited", rl > 0 && rl <= 8, rl);
}

{
  const mb = await post("/api/bests", { player_id: pid, ts, sig: await signBests(sec, pid, ts) }, "6.6.6.6");
  check("my bests", mb.status === 200 && (mb.body.bests as { level: number }[]).some((b) => b.level === 1), mb.body);
  check("my bests need my key", (await post("/api/bests", { player_id: pid, ts, sig: await signBests("0".repeat(48), pid, ts) }, "6.6.6.6")).status === 403);
}

let limitedAt = 0;
for (let i = 0; i < 130 && !limitedAt; i++) if ((await get("/api/leaderboard", "", "9.9.9.9")).status === 429) limitedAt = i;
check("rate limit kicks in (429)", limitedAt > 100, limitedAt);

console.log(ok ? "ALL OK" : "SOME FAILED");
if (!ok) process.exit(1);
