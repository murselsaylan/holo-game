// In-memory RankedStore for tests (same semantics as ranked_pg.ts)
import type { DailyRow, DailyRun, RankedStore } from "../ranked.ts";

export class MemRanked implements RankedStore {
  stars: { pid: string; reason: string; ref: string; delta: number; created: number }[] = [];
  constructor(private names: (pid: string) => { name: string; country: string } = () => ({ name: "X", country: "TR" })) {}
  async starTotals(pid: string) {
    const mine = this.stars.filter((s) => s.pid === pid);
    return { balance: mine.reduce((a, s) => a + s.delta, 0), earned: mine.filter((s) => s.delta > 0).reduce((a, s) => a + s.delta, 0) };
  }
  async starChange(pid: string, delta: number, reason: string, ref: string, now: number) {
    const cur = await this.starTotals(pid);
    if (this.stars.some((s) => s.pid === pid && s.reason === reason && s.ref === ref)) return { ok: true, dup: true, ...cur };
    if (cur.balance + delta < 0) return { ok: false, dup: false, ...cur };
    this.stars.push({ pid, reason, ref, delta, created: now });
    return { ok: true, dup: false, balance: cur.balance + delta, earned: cur.earned + Math.max(0, delta) };
  }
  async starSum(pid: string, reason: string, since: number) {
    return this.stars.filter((s) => s.pid === pid && s.reason === reason && s.created >= since).reduce((a, s) => a + s.delta, 0);
  }
  async starRefs(pid: string, reason: string) { return this.stars.filter((s) => s.pid === pid && s.reason === reason).map((s) => s.ref); }
  async starEarnedSince(pid: string, since: number) {
    return this.stars.filter((s) => s.pid === pid && s.delta > 0 && s.created >= since).reduce((a, s) => a + s.delta, 0);
  }


  runs = new Map<string, DailyRun & { pid: string; day: number; taps: number[] }>();
  async dailyStart(day: number, pid: string, level: number, now: number) {
    const k = day + "|" + pid;
    if (this.runs.has(k)) return false;
    this.runs.set(k, { pid, day, level, started: now, finished: 0, score: 0, stars: 0, time: 0, taps: [] });
    return true;
  }
  async dailyRun(day: number, pid: string) { return this.runs.get(day + "|" + pid) ?? null; }
  async dailyFinish(day: number, pid: string, score: number, stars: number, time: number, taps: number[], now: number) {
    const r = this.runs.get(day + "|" + pid);
    if (!r || r.finished > 0) return false;
    Object.assign(r, { finished: now, score, stars, time, taps });
    return true;
  }
  private done(day: number) {
    return [...this.runs.values()].filter((r) => r.day === day && r.finished > 0)
      .sort((a, b) => b.score - a.score || a.time - b.time || a.finished - b.finished);
  }
  async dailyBoard(day: number, limit: number): Promise<DailyRow[]> {
    return this.done(day).slice(0, limit).map((r) => ({ id: r.pid, ...this.names(r.pid), score: r.score, stars: r.stars, time: r.time }));
  }
  async dailyRank(day: number, pid: string) {
    const d = this.done(day), i = d.findIndex((r) => r.pid === pid);
    return i < 0 ? null : { rank: i + 1, total: d.length };
  }
}
