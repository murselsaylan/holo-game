// Postgres side of the shared weekly goal (tables crowd_weeks, crowd_contrib: schema.sql).
import type { CrowdStore } from "./crowd.ts";

// deno-lint-ignore no-explicit-any
type Sql = any;

export class PgLive implements CrowdStore {
  constructor(private sql: Sql) {}

  // ---- shared weekly goal
  async crowdWeek(week: string, goal: number, now: number) {
    await this.sql`INSERT INTO crowd_weeks(week, goal, stars, created) VALUES(${week}, ${goal}, 0, ${now}) ON CONFLICT (week) DO NOTHING`;
    const r = await this.sql`SELECT goal, stars, (SELECT COUNT(*)::int FROM crowd_contrib c WHERE c.week = w.week AND c.stars > 0) AS n
      FROM crowd_weeks w WHERE week = ${week}`;
    return { goal: Number(r[0].goal), stars: Number(r[0].stars), contributors: Number(r[0].n) };
  }
  async crowdTotal(week: string): Promise<number> {
    const r = await this.sql`SELECT stars FROM crowd_weeks WHERE week = ${week}`;
    return r.length ? Number(r[0].stars) : 0;
  }
  async crowdAdd(week: string, pid: string, n: number, cap: number, goal: number, now: number): Promise<number> {
    return await this.sql.begin(async (tx: Sql) => {
      await tx`INSERT INTO crowd_weeks(week, goal, stars, created) VALUES(${week}, ${goal}, 0, ${now}) ON CONFLICT (week) DO NOTHING`;
      await tx`INSERT INTO crowd_contrib(week, player_id, stars) VALUES(${week}, ${pid}, 0) ON CONFLICT DO NOTHING`;
      const cur = await tx`SELECT stars FROM crowd_contrib WHERE week = ${week} AND player_id = ${pid} FOR UPDATE`;
      const add = Math.max(0, Math.min(n, cap - Number(cur[0].stars)));
      if (add > 0) {
        await tx`UPDATE crowd_contrib SET stars = stars + ${add} WHERE week = ${week} AND player_id = ${pid}`;
        await tx`UPDATE crowd_weeks SET stars = stars + ${add} WHERE week = ${week}`;
      }
      return add;
    });
  }
  async crowdMine(week: string, pid: string): Promise<number> {
    const r = await this.sql`SELECT stars FROM crowd_contrib WHERE week = ${week} AND player_id = ${pid}`;
    return r.length ? Number(r[0].stars) : 0;
  }

  // ---- weekly featured level
  async weeklyClear(week: string, pid: string): Promise<void> {
    await this.sql`INSERT INTO weekly_clears(week, player_id) VALUES(${week}, ${pid}) ON CONFLICT DO NOTHING`;
  }
  async weeklyCleared(week: string, pid: string): Promise<boolean> {
    const r = await this.sql`SELECT 1 FROM weekly_clears WHERE week = ${week} AND player_id = ${pid}`;
    return r.length > 0;
  }
  async levelStats(level: number): Promise<{ cleared: number; pilots: number }> {
    const a = await this.sql`SELECT COUNT(*)::int AS n FROM bests WHERE level = ${level}`;
    const b = await this.sql`SELECT COUNT(*)::int AS n FROM players WHERE levels > 0`;
    return { cleared: Number(a[0].n), pilots: Number(b[0].n) };
  }
}
