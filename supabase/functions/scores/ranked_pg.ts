// Postgres side of the star wallet and the daily level (tables star_log, daily_runs: schema.sql).
import type { DailyRow, DailyRun, RankedStore } from "./ranked.ts";

// deno-lint-ignore no-explicit-any
type Sql = any;

export class PgRanked implements RankedStore {
  constructor(private sql: Sql) {}

  // ---- stars
  async starChange(pid: string, delta: number, reason: string, ref: string, now: number) {
    return await this.sql.begin(async (tx: Sql) => {
      await tx`SELECT pg_advisory_xact_lock(hashtext(${"star|" + pid}))`;
      const dup = await tx`SELECT 1 FROM star_log WHERE player_id = ${pid} AND reason = ${reason} AND ref = ${ref}`;
      const r = await tx`SELECT COALESCE(SUM(delta), 0)::int AS b, COALESCE(SUM(delta) FILTER (WHERE delta > 0), 0)::int AS e
        FROM star_log WHERE player_id = ${pid}`;
      const cur = { balance: Number(r[0].b), earned: Number(r[0].e) };
      if (dup.length) return { ok: true, dup: true, ...cur };
      if (cur.balance + delta < 0) return { ok: false, dup: false, ...cur };
      await tx`INSERT INTO star_log(player_id, reason, ref, delta, created) VALUES(${pid}, ${reason}, ${ref}, ${delta}, ${now})`;
      return { ok: true, dup: false, balance: cur.balance + delta, earned: cur.earned + Math.max(0, delta) };
    });
  }
  async starTotals(pid: string) {
    const r = await this.sql`SELECT COALESCE(SUM(delta), 0)::int AS b, COALESCE(SUM(delta) FILTER (WHERE delta > 0), 0)::int AS e
      FROM star_log WHERE player_id = ${pid}`;
    return { balance: Number(r[0].b), earned: Number(r[0].e) };
  }
  async starSum(pid: string, reason: string, since: number) {
    const r = await this.sql`SELECT COALESCE(SUM(delta), 0)::int AS s FROM star_log WHERE player_id = ${pid} AND reason = ${reason} AND created >= ${since}`;
    return Number(r[0].s);
  }
  async starRefs(pid: string, reason: string) {
    const r = await this.sql`SELECT ref FROM star_log WHERE player_id = ${pid} AND reason = ${reason}`;
    return r.map((x: Sql) => String(x.ref));
  }
  async starEarnedSince(pid: string, since: number) {
    const r = await this.sql`SELECT COALESCE(SUM(delta), 0)::int AS s FROM star_log WHERE player_id = ${pid} AND delta > 0 AND created >= ${since}`;
    return Number(r[0].s);
  }

  // ---- daily level
  async dailyStart(day: number, pid: string, level: number, now: number) {
    const r = await this.sql`INSERT INTO daily_runs(day, player_id, level, started) VALUES(${day}, ${pid}, ${level}, ${now}) ON CONFLICT DO NOTHING RETURNING 1`;
    return r.length > 0;
  }
  async dailyRestart(day: number, pid: string, now: number) {
    const r = await this.sql`UPDATE daily_runs SET started = ${now} WHERE day = ${day} AND player_id = ${pid} AND finished = 0 RETURNING 1`;
    return r.length > 0;
  }
  async dailyRun(day: number, pid: string): Promise<DailyRun | null> {
    const r = await this.sql`SELECT level, started, finished, score, stars, "time" FROM daily_runs WHERE day = ${day} AND player_id = ${pid}`;
    if (!r.length) return null;
    return { level: Number(r[0].level), started: Number(r[0].started), finished: Number(r[0].finished), score: Number(r[0].score),
             stars: Number(r[0].stars), time: Number(r[0].time) };
  }
  async dailyFinish(day: number, pid: string, score: number, stars: number, time: number, taps: number[], now: number) {
    const r = await this.sql`UPDATE daily_runs SET finished = ${now}, score = ${score}, stars = ${stars}, "time" = ${time}, taps = ${taps.join(",")}
      WHERE day = ${day} AND player_id = ${pid} AND finished = 0 RETURNING 1`;
    return r.length > 0;
  }
  async dailyBoard(day: number, limit: number): Promise<DailyRow[]> {
    const r = await this.sql`SELECT d.player_id AS id, p.name, p.country, d.score, d.stars, d."time" FROM daily_runs d
      JOIN players p ON p.id = d.player_id WHERE d.day = ${day} AND d.finished > 0 ORDER BY d.score DESC, d."time" ASC, d.finished ASC LIMIT ${limit}`;
    return r.map((x: Sql) => ({ id: String(x.id), name: String(x.name), country: String(x.country), score: Number(x.score),
                                stars: Number(x.stars), time: Number(x.time) }));
  }
  async dailyRank(day: number, pid: string) {
    const me = await this.sql`SELECT score, "time" FROM daily_runs WHERE day = ${day} AND player_id = ${pid} AND finished > 0`;
    if (!me.length) return null;
    const a = await this.sql`SELECT COUNT(*)::int AS n FROM daily_runs WHERE day = ${day} AND finished > 0
      AND (score > ${me[0].score} OR (score = ${me[0].score} AND "time" < ${me[0].time}))`;
    const t = await this.sql`SELECT COUNT(*)::int AS n FROM daily_runs WHERE day = ${day} AND finished > 0`;
    return { rank: Number(a[0].n) + 1, total: Number(t[0].n) };
  }
}
