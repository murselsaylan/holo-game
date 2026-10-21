// In-memory CrowdStore for tests (same semantics as live_pg.ts)
import type { CrowdStore } from "../crowd.ts";

export class MemLive implements CrowdStore {
  weeks = new Map<string, { goal: number; stars: number }>();
  contrib = new Map<string, number>();
  async crowdWeek(week: string, goal: number, _now: number) {
    if (!this.weeks.has(week)) this.weeks.set(week, { goal, stars: 0 });
    const w = this.weeks.get(week)!;
    return { goal: w.goal, stars: w.stars, contributors: [...this.contrib.entries()].filter(([k, v]) => k.startsWith(week + "|") && v > 0).length };
  }
  async crowdTotal(week: string) { return this.weeks.get(week)?.stars ?? 0; }
  async crowdAdd(week: string, pid: string, n: number, cap: number, goal: number, now: number) {
    await this.crowdWeek(week, goal, now);
    const k = week + "|" + pid, cur = this.contrib.get(k) ?? 0, add = Math.max(0, Math.min(n, cap - cur));
    this.contrib.set(k, cur + add);
    this.weeks.get(week)!.stars += add;
    return add;
  }
  async crowdMine(week: string, pid: string) { return this.contrib.get(week + "|" + pid) ?? 0; }
  wclears = new Set<string>();
  stats = { cleared: 0, pilots: 0 };
  async weeklyClear(week: string, pid: string) { this.wclears.add(week + "|" + pid); }
  async weeklyCleared(week: string, pid: string) { return this.wclears.has(week + "|" + pid); }
  async levelStats(_level: number) { return this.stats; }
}
