// Postgres store (Supabase). Uses postgres.js; all counts are cast to int because int8 comes back as string.
import type { Best, EndlessRow, Ghost, EndlessStanding, Player, Ranks, Restored, Row, Store } from "./handler.ts";
import type { PurchaseResult, WalletChange, WalletOpen } from "./wallet.ts";
import type { Assist, Result } from "./sim.ts";

// deno-lint-ignore no-explicit-any
type Sql = any;

export class PgStore implements Store {
  constructor(private sql: Sql) {}

  // The tables and indexes are created once by supabase/schema.sql. Running that DDL here cost six extra round
  // trips (and ALTER TABLE takes an exclusive lock) on every cold start - i.e. on nearly every request.
  async ensure(): Promise<void> {}

  async saveCloud(pid: string, data: string, now: number): Promise<void> {
    await this.sql`INSERT INTO saves(player_id, data, updated) VALUES(${pid}, ${data}, ${now})
                   ON CONFLICT (player_id) DO UPDATE SET data = EXCLUDED.data, updated = EXCLUDED.updated`;
  }

  async setRecovery(pid: string, hash: string): Promise<void> {
    await this.sql`UPDATE players SET recovery = ${hash} WHERE id = ${pid}`;
  }

  async playerBests(pid: string): Promise<Best[]> {
    const b = await this.sql`SELECT level, score, stars, "time", swaps, "rank" FROM bests WHERE player_id = ${pid} ORDER BY level`;
    return b.map((r: Sql) => ({ level: Number(r.level), score: Number(r.score), stars: Number(r.stars), time: Number(r.time),
                                swaps: Number(r.swaps), rank: String(r.rank) }));
  }

  async linkGoogle(pid: string, googleHash: string, email: string): Promise<"ok" | "taken"> {
    return await this.sql.begin(async (tx: Sql) => {
      const other = await tx`SELECT id FROM players WHERE google = ${googleHash} AND id <> ${pid}`;
      if (other.length) return "taken";
      await tx`UPDATE players SET google = ${googleHash}, google_email = ${email} WHERE id = ${pid}`;
      return "ok";
    });
  }

  async restoreGoogle(googleHash: string): Promise<Restored | null> {
    const p = await this.sql`SELECT id, secret, name, country, levels, score, stars FROM players WHERE google = ${googleHash}`;
    return p.length ? await this.restored(p) : null;
  }

  async restore(hash: string): Promise<Restored | null> {
    const p = await this.sql`SELECT id, secret, name, country, levels, score, stars FROM players WHERE recovery = ${hash}`;
    return p.length ? await this.restored(p) : null;
  }

  private async restored(p: Sql): Promise<Restored> {
    const pid = p[0].id;
    const s = await this.sql`SELECT data FROM saves WHERE player_id = ${pid}`;
    const b = await this.sql`SELECT level, score, stars, "time", swaps, "rank" FROM bests WHERE player_id = ${pid} ORDER BY level`;
    return {
      player: { ...p[0], levels: Number(p[0].levels), score: Number(p[0].score), stars: Number(p[0].stars) } as Player,
      data: s.length ? String(s[0].data) : null,
      bests: b.map((r: Sql) => ({ level: Number(r.level), score: Number(r.score), stars: Number(r.stars), time: Number(r.time),
                                  swaps: Number(r.swaps), rank: String(r.rank) })) as Best[],
    };
  }

  async player(pid: string): Promise<Player | null> {
    const rows = await this.sql`SELECT id, secret, name, country, levels, score, stars FROM players WHERE id = ${pid}`;
    return rows.length ? (rows[0] as Player) : null;
  }

  async register(pid: string, secret: string, name: string, country: string): Promise<boolean> {
    const now = Math.floor(Date.now() / 1000);
    return await this.sql.begin(async (tx: Sql) => {
      const rows = await tx`SELECT secret FROM players WHERE id = ${pid}`;
      if (!rows.length) {
        await tx`INSERT INTO players(id, secret, name, country, created, updated) VALUES(${pid}, ${secret}, ${name}, ${country}, ${now}, ${now})`;
        return true;
      }
      if (rows[0].secret !== secret) return false;
      await tx`UPDATE players SET name = ${name}, country = ${country}, updated = ${now} WHERE id = ${pid}`;
      return true;
    });
  }

  async record(pid: string, level: number, res: Result, taps: number[], assists: Assist[] = []) {
    const now = Math.floor(Date.now() / 1000);
    return await this.sql.begin(async (tx: Sql) => {
      const cur = await tx`SELECT score FROM bests WHERE player_id = ${pid} AND level = ${level}`;
      const improved = cur.length === 0 || res.level_total > Number(cur[0].score);
      const r = assists.filter((a) => a[1] === "R" || a[1] === "R2").length, s = assists.filter((a) => a[1] === "S").length;
      if (improved && (r || s)) {
        // every revive / bought shield in the run must be one the player paid for and has not used in a ranked run yet
        const c = await tx`SELECT assist_revives_used AS ru, assist_shields_used AS su,
            (SELECT COUNT(*) FROM wallet_log w WHERE w.player_id = p.id AND w.reason = 'spend:revive')::int AS rp,
            (SELECT COUNT(*) FROM wallet_log w WHERE w.player_id = p.id AND w.reason = 'spend:shield')::int AS sp
          FROM players p WHERE p.id = ${pid} FOR UPDATE`;
        if (!c.length || Number(c[0].rp) - Number(c[0].ru) < r || Number(c[0].sp) - Number(c[0].su) < s) {
          return { improved: false, levels: 0, score: 0, stars: 0, unpaid: true };
        }
        await tx`UPDATE players SET assist_revives_used = assist_revives_used + ${r},
                   assist_shields_used = assist_shields_used + ${s} WHERE id = ${pid}`;
      }
      if (improved) {
        await tx`INSERT INTO bests(player_id, level, score, stars, "time", swaps, "rank", taps, assists, updated)
                 VALUES(${pid}, ${level}, ${res.level_total}, ${res.stars}, ${res.time}, ${res.swaps}, ${res.rank}, ${JSON.stringify(taps)},
                        ${assists.length ? JSON.stringify(assists) : ""}, ${now})
                 ON CONFLICT (player_id, level) DO UPDATE SET score = EXCLUDED.score, stars = EXCLUDED.stars,
                   "time" = EXCLUDED."time", swaps = EXCLUDED.swaps, "rank" = EXCLUDED."rank", taps = EXCLUDED.taps,
                   assists = EXCLUDED.assists, updated = EXCLUDED.updated`;
      }
      // levels = the highest level cleared (not the count: a clear that was never uploaded must not hide the progress)
      const agg = await tx`SELECT COALESCE(MAX(level),0)::int AS c, COALESCE(SUM(score),0)::int AS s, COALESCE(SUM(stars),0)::int AS st FROM bests WHERE player_id = ${pid}`;
      const a = agg[0];
      await tx`UPDATE players SET levels = ${a.c}, score = ${a.s}, stars = ${a.st}, updated = ${now} WHERE id = ${pid}`;
      return { improved, levels: Number(a.c), score: Number(a.s), stars: Number(a.st) };
    });
  }

  async ranks(pid: string): Promise<Ranks | null> {
    // one round trip: the player and both positions
    const me = await this.sql`SELECT p.levels, p.score, p.stars, p.country,
        (SELECT COUNT(*) + 1 FROM players q WHERE q.levels > 0 AND (q.score > p.score OR (q.score = p.score AND q.levels > p.levels)))::int AS r,
        (SELECT COUNT(*) + 1 FROM players q WHERE q.country = p.country
           AND q.levels > 0 AND (q.score > p.score OR (q.score = p.score AND q.levels > p.levels)))::int AS cr
      FROM players p WHERE p.id = ${pid}`;
    if (!me.length || Number(me[0].levels) === 0) return null;
    const m = me[0];
    return { rank: Number(m.r), country_rank: Number(m.cr), levels: Number(m.levels), score: Number(m.score), stars: Number(m.stars),
             country: String(m.country) };
  }

  async ghost(level: number): Promise<Ghost | null> {
    // clean runs only: a run with revives / bought shields (or a pre-1.0.5 'legacy' row) cannot be replayed as is
    const g = await this.sql`SELECT b.player_id, p.name, b.score, b.taps FROM bests b JOIN players p ON p.id = b.player_id
      WHERE b.level = ${level} AND COALESCE(b.assists, '') = '' AND b.taps LIKE '[%' ORDER BY b.score DESC, b.updated LIMIT 1`;
    if (!g.length) return null;
    let taps: number[];
    try { taps = JSON.parse(g[0].taps); } catch { return null; }
    if (!Array.isArray(taps) || !taps.length) return null;
    return { id: String(g[0].player_id), name: String(g[0].name), score: Number(g[0].score), taps };
  }

  async board(scope: string, country: string, offset: number, limit: number): Promise<{ rows: Row[]; total: number }> {
    const sql = this.sql;
    // rows and the total in one round trip (the total rides along as a window count)
    const rows = scope === "country"
      ? await sql`SELECT * FROM (SELECT id, name, country, levels, score, stars, (RANK() OVER (ORDER BY score DESC, levels DESC))::int AS rk,
                    (COUNT(*) OVER ())::int AS total
                  FROM players WHERE levels > 0 AND country = ${country}) AS t ORDER BY rk, name LIMIT ${limit} OFFSET ${offset}`
      : await sql`SELECT * FROM (SELECT id, name, country, levels, score, stars, (RANK() OVER (ORDER BY score DESC, levels DESC))::int AS rk,
                    (COUNT(*) OVER ())::int AS total
                  FROM players WHERE levels > 0) AS t ORDER BY rk, name LIMIT ${limit} OFFSET ${offset}`;
    let total = rows.length ? Number(rows[0].total) : 0;
    if (!rows.length && offset > 0) {
      const tot = scope === "country"
        ? await sql`SELECT COUNT(*)::int AS c FROM players WHERE levels > 0 AND country = ${country}`
        : await sql`SELECT COUNT(*)::int AS c FROM players WHERE levels > 0`;
      total = Number(tot[0].c);
    }
    return {
      total,
      rows: rows.map((r: Sql) => ({ rank: Number(r.rk), id: r.id, name: r.name, country: r.country, levels: Number(r.levels),
                                    score: Number(r.score), stars: Number(r.stars) })),
    };
  }

  // ---- diamond wallet (see wallet.ts) -----------------------------------------------------------------------
  async walletOpen(pid: string, local: number, cap: number, now: number): Promise<WalletOpen> {
    return await this.sql.begin(async (tx: Sql) => {
      const rows = await tx`SELECT diamonds, gift FROM players WHERE id = ${pid} FOR UPDATE`;
      if (!rows.length) return { balance: 0, imported: null, gift: 0 };
      let bal = rows[0].diamonds === null ? null : Number(rows[0].diamonds);
      let imported: number | null = null;
      if (bal === null) {
        imported = Math.max(0, Math.min(cap, Math.trunc(local)));
        bal = imported;
        await tx`INSERT INTO wallet_log(player_id, delta, balance, reason, ref, created)
                 VALUES(${pid}, ${imported}, ${bal}, 'import', '1', ${now}) ON CONFLICT DO NOTHING`;
      }
      const gift = Number(rows[0].gift ?? 0);
      if (gift > 0) {
        bal += gift;
        await tx`INSERT INTO wallet_log(player_id, delta, balance, reason, ref, created)
                 VALUES(${pid}, ${gift}, ${bal}, 'gift', ${String(now) + "-" + String(gift)}, ${now})
                 ON CONFLICT DO NOTHING`;
      }
      await tx`UPDATE players SET diamonds = ${bal}, gift = 0 WHERE id = ${pid}`;
      return { balance: bal, imported, gift: Math.max(0, gift) };
    });
  }

  async walletBalance(pid: string): Promise<number | null> {
    const rows = await this.sql`SELECT diamonds FROM players WHERE id = ${pid}`;
    return rows.length && rows[0].diamonds !== null ? Number(rows[0].diamonds) : null;
  }

  async walletChange(pid: string, delta: number, reason: string, ref: string, now: number): Promise<WalletChange> {
    return await this.sql.begin(async (tx: Sql) => {
      const cur = await tx`SELECT diamonds FROM players WHERE id = ${pid} FOR UPDATE`;
      const bal = cur.length && cur[0].diamonds !== null ? Number(cur[0].diamonds) : 0;
      const seen = await tx`SELECT 1 FROM wallet_log WHERE player_id = ${pid} AND reason = ${reason} AND ref = ${ref}`;
      if (seen.length) return { ok: true, balance: bal, dup: true };
      if (bal + delta < 0) return { ok: false, balance: bal, dup: false };
      const nb = bal + delta;
      await tx`UPDATE players SET diamonds = ${nb} WHERE id = ${pid}`;
      await tx`INSERT INTO wallet_log(player_id, delta, balance, reason, ref, created)
               VALUES(${pid}, ${delta}, ${nb}, ${reason}, ${ref}, ${now})`;
      return { ok: true, balance: nb, dup: false };
    });
  }

  async walletSum(pid: string, reason: string, since: number): Promise<number> {
    const r = await this.sql`SELECT COALESCE(SUM(delta), 0)::int AS s FROM wallet_log
                             WHERE player_id = ${pid} AND reason = ${reason} AND created >= ${since}`;
    return Number(r[0].s);
  }

  // ---- endless climb (table endless_bests, see schema.sql)
  async endlessRecord(pid: string, week: string, metres: number, steps: number, nonce: string, taps: number[],
                      now: number): Promise<{ best: number; improved: boolean }> {
    const r = await this.sql`INSERT INTO endless_bests(week, player_id, metres, steps, nonce, taps, updated)
        VALUES(${week}, ${pid}, ${metres}, ${steps}, ${nonce}, ${JSON.stringify(taps)}, ${now})
        ON CONFLICT (week, player_id) DO UPDATE SET metres = EXCLUDED.metres, steps = EXCLUDED.steps, nonce = EXCLUDED.nonce,
          taps = EXCLUDED.taps, updated = EXCLUDED.updated WHERE endless_bests.metres < EXCLUDED.metres
        RETURNING metres`;
    // the ranking is all-time (1.0.6): the player's best over every week
    const b = await this.sql`SELECT COALESCE(MAX(metres), 0)::int AS m FROM endless_bests WHERE player_id = ${pid}`;
    const best = Number(b[0].m);
    return { best, improved: r.length > 0 && Number(r[0].metres) >= best };
  }

  async useAssists(pid: string, revives: number, shields: number, ref: string, now: number): Promise<boolean> {
    return await this.sql.begin(async (tx: Sql) => {
      const c = await tx`SELECT p.diamonds, assist_revives_used AS ru, assist_shields_used AS su,
          (SELECT COUNT(*) FROM wallet_log w WHERE w.player_id = p.id AND w.reason = 'spend:revive')::int AS rp,
          (SELECT COUNT(*) FROM wallet_log w WHERE w.player_id = p.id AND w.reason = 'spend:shield')::int AS sp,
          (SELECT COUNT(*) FROM wallet_log w WHERE w.player_id = p.id AND w.reason = 'assist:endless' AND w.ref = ${ref})::int AS seen
        FROM players p WHERE p.id = ${pid} FOR UPDATE`;
      if (!c.length) return false;
      if (Number(c[0].seen) > 0) return true;
      if (Number(c[0].rp) - Number(c[0].ru) < revives || Number(c[0].sp) - Number(c[0].su) < shields) return false;
      await tx`UPDATE players SET assist_revives_used = assist_revives_used + ${revives},
                 assist_shields_used = assist_shields_used + ${shields} WHERE id = ${pid}`;
      await tx`INSERT INTO wallet_log(player_id, delta, balance, reason, ref, created)
               VALUES(${pid}, 0, ${Number(c[0].diamonds ?? 0)}, 'assist:endless', ${ref}, ${now})`;
      return true;
    });
  }

  // all-time standing (1.0.6): each player's best climb of any week; `week` is kept for the interface only
  async endlessStanding(pid: string, _week: string): Promise<EndlessStanding | null> {
    const r = await this.sql`WITH b AS (SELECT DISTINCT ON (player_id) player_id, metres, updated FROM endless_bests
                                        ORDER BY player_id, metres DESC, updated ASC)
      SELECT e.metres,
        (SELECT COUNT(*) + 1 FROM b q WHERE q.metres > e.metres OR (q.metres = e.metres AND q.updated < e.updated))::int AS rk,
        (SELECT COUNT(*) FROM b)::int AS total
      FROM b e WHERE e.player_id = ${pid}`;
    if (!r.length) return null;
    return { rank: Number(r[0].rk), metres: Number(r[0].metres), points: Number(r[0].metres), total: Number(r[0].total) };
  }

  async endlessBoard(_week: string, offset: number, limit: number): Promise<{ rows: EndlessRow[]; total: number }> {
    const rows = await this.sql`WITH b AS (SELECT DISTINCT ON (player_id) player_id, metres, updated FROM endless_bests
                                           ORDER BY player_id, metres DESC, updated ASC)
      SELECT e.player_id AS id, p.name, p.country, e.metres,
        (ROW_NUMBER() OVER (ORDER BY e.metres DESC, e.updated ASC))::int AS rk, (COUNT(*) OVER ())::int AS total
      FROM b e JOIN players p ON p.id = e.player_id
      ORDER BY e.metres DESC, e.updated ASC LIMIT ${limit} OFFSET ${offset}`;
    return { rows: rows.map((r: Sql) => ({ rank: Number(r.rk), id: String(r.id), name: String(r.name), country: String(r.country),
                                           metres: Number(r.metres), points: Number(r.metres) })),
             total: rows.length ? Number(rows[0].total) : 0 };
  }

  async walletRefs(pid: string, reason: string, since: number): Promise<string[]> {
    const r = await this.sql`SELECT ref FROM wallet_log WHERE player_id = ${pid} AND reason = ${reason} AND created >= ${since}`;
    return r.map((x: Sql) => String(x.ref));
  }

  async walletCount(pid: string, reason: string, since: number): Promise<{ n: number; last: number }> {
    const r = await this.sql`SELECT COUNT(*)::int AS n, COALESCE(MAX(created), 0)::bigint AS last FROM wallet_log
                             WHERE player_id = ${pid} AND reason = ${reason} AND created >= ${since}`;
    return { n: Number(r[0].n), last: Number(r[0].last) };
  }

  async walletPurchase(pid: string, tokenHash: string, product: string, orderId: string, diamonds: number,
                       now: number): Promise<PurchaseResult> {
    return await this.sql.begin(async (tx: Sql) => {
      const cur = await tx`SELECT diamonds FROM players WHERE id = ${pid} FOR UPDATE`;
      const bal = cur.length && cur[0].diamonds !== null ? Number(cur[0].diamonds) : 0;
      const seen = await tx`SELECT player_id FROM purchases WHERE token_hash = ${tokenHash}`;
      if (seen.length) return { status: seen[0].player_id === pid ? "dup" : "other_player", balance: bal };
      await tx`INSERT INTO purchases(token_hash, player_id, product, order_id, diamonds, created)
               VALUES(${tokenHash}, ${pid}, ${product}, ${orderId}, ${diamonds}, ${now})`;
      if (diamonds <= 0) return { status: "ok", balance: bal };
      const nb = bal + diamonds;
      await tx`UPDATE players SET diamonds = ${nb} WHERE id = ${pid}`;
      await tx`INSERT INTO wallet_log(player_id, delta, balance, reason, ref, created)
               VALUES(${pid}, ${diamonds}, ${nb}, 'purchase', ${tokenHash}, ${now})`;
      return { status: "ok", balance: nb };
    });
  }

  async walletSkins(pid: string): Promise<string[]> {
    const rows = await this.sql`SELECT substr(product, 6) AS s FROM purchases WHERE player_id = ${pid} AND starts_with(product, 'skin_')
                                UNION SELECT substr(reason, 12) FROM wallet_log WHERE player_id = ${pid} AND starts_with(reason, 'spend:skin:')`;
    return rows.map((r: Sql) => String(r.s));
  }
}
