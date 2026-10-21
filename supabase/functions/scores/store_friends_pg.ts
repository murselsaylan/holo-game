// Postgres side of the friends feature (friends.ts). PgStore mixes these methods in: `this.sql` is its postgres.js handle.
import { MAX_FRIENDS, newFriendCode } from "./friends.ts";
import type { FriendRow, Msg, Sent } from "./friends.ts";

// deno-lint-ignore no-explicit-any
type Sql = any;

export class PgFriends {
  constructor(protected sql: Sql) {}

  async friendCode(pid: string): Promise<string> {
    const cur = await this.sql`SELECT friend_code FROM players WHERE id = ${pid}`;
    if (cur.length && cur[0].friend_code) return String(cur[0].friend_code);
    for (let i = 0; i < 8; i++) {                                      // a unique-index clash just draws another code
      const code = newFriendCode();
      try {
        const r = await this.sql`UPDATE players SET friend_code = ${code} WHERE id = ${pid} AND friend_code IS NULL RETURNING friend_code`;
        if (r.length) return String(r[0].friend_code);
        const again = await this.sql`SELECT friend_code FROM players WHERE id = ${pid}`;
        if (again.length && again[0].friend_code) return String(again[0].friend_code);
      } catch { /* unique clash: next code */ }
    }
    throw new Error("no friend code");
  }

  async playerByCode(code: string): Promise<{ id: string; name: string } | null> {
    const r = await this.sql`SELECT id, name FROM players WHERE friend_code = ${code}`;
    return r.length ? { id: String(r[0].id), name: String(r[0].name) } : null;
  }

  async friendLinks(pid: string): Promise<FriendRow[]> {
    const r = await this.sql`SELECT p.id, p.name, p.country, p.levels, p.score, p.stars, f.status, f.requester
      FROM friendships f JOIN players p ON p.id = CASE WHEN f.low = ${pid} THEN f.high ELSE f.low END
      WHERE f.low = ${pid} OR f.high = ${pid}`;
    return r.map((x: Sql) => ({
      id: String(x.id), name: String(x.name), country: String(x.country), levels: Number(x.levels), score: Number(x.score),
      stars: Number(x.stars), status: x.status === "accepted" ? "friend" : (x.requester === pid ? "outgoing" : "incoming"),
    }));
  }

  async friendAsk(a: string, b: string, now: number): Promise<"pending" | "accepted" | "exists" | "full"> {
    const [low, high] = a < b ? [a, b] : [b, a];
    return await this.sql.begin(async (tx: Sql) => {
      const cur = await tx`SELECT requester, status FROM friendships WHERE low = ${low} AND high = ${high} FOR UPDATE`;
      if (cur.length) {
        if (cur[0].status === "accepted" || cur[0].requester === a) return "exists";
        await tx`UPDATE friendships SET status = 'accepted' WHERE low = ${low} AND high = ${high}`;   // they had asked first
        return "accepted";
      }
      for (const who of [a, b]) {
        const n = await tx`SELECT COUNT(*)::int AS n FROM friendships WHERE low = ${who} OR high = ${who}`;
        if (Number(n[0].n) >= MAX_FRIENDS) return "full";
      }
      await tx`INSERT INTO friendships(low, high, requester, status, created) VALUES(${low}, ${high}, ${a}, 'pending', ${now})`;
      return "pending";
    });
  }

  async friendAccept(me: string, other: string): Promise<boolean> {
    const [low, high] = me < other ? [me, other] : [other, me];
    const r = await this.sql`UPDATE friendships SET status = 'accepted' WHERE low = ${low} AND high = ${high}
                             AND status = 'pending' AND requester <> ${me} RETURNING low`;
    return r.length > 0;
  }

  async friendRemove(me: string, other: string): Promise<void> {
    const [low, high] = me < other ? [me, other] : [other, me];
    await this.sql`DELETE FROM friendships WHERE low = ${low} AND high = ${high}`;
  }

  async areFriends(a: string, b: string): Promise<boolean> {
    const [low, high] = a < b ? [a, b] : [b, a];
    const r = await this.sql`SELECT 1 FROM friendships WHERE low = ${low} AND high = ${high} AND status = 'accepted'`;
    return r.length > 0;
  }

  async msgAdd(m: { from: string; to: string; kind: Msg["kind"]; level: number; item: string; amount: number; day: number;
                    created: number }): Promise<number | null> {
    const r = await this.sql`INSERT INTO friend_msgs(from_id, to_id, kind, level, item, amount, day, created)
        VALUES(${m.from}, ${m.to}, ${m.kind}, ${m.level}, ${m.item}, ${m.amount}, ${m.day}, ${m.created})
        ON CONFLICT DO NOTHING RETURNING id`;
    return r.length ? Number(r[0].id) : null;
  }

  private msgRow(x: Sql): Msg {
    return {
      id: Number(x.id), from: String(x.from_id), from_name: String(x.from_name ?? ""), to: String(x.to_id), kind: x.kind,
      level: Number(x.level), item: String(x.item), amount: Number(x.amount), day: Number(x.day), created: Number(x.created),
      claimed: Number(x.claimed), answered_by: String(x.answered_by),
    };
  }

  async msg(id: number): Promise<Msg | null> {
    const r = await this.sql`SELECT m.*, p.name AS from_name FROM friend_msgs m JOIN players p ON p.id = m.from_id WHERE m.id = ${id}`;
    return r.length ? this.msgRow(r[0]) : null;
  }

  async inbox(to: string, since: number): Promise<Msg[]> {
    const r = await this.sql`SELECT m.*, p.name AS from_name FROM friend_msgs m JOIN players p ON p.id = m.from_id
        WHERE m.to_id = ${to} AND m.claimed = 0 AND m.created >= ${since} ORDER BY m.created DESC LIMIT 60`;
    return r.map((x: Sql) => this.msgRow(x));
  }

  async msgClaim(id: number, now: number): Promise<boolean> {
    const r = await this.sql`UPDATE friend_msgs SET claimed = ${now} WHERE id = ${id} AND claimed = 0 RETURNING id`;
    return r.length > 0;
  }

  async sentOn(from: string, day: number): Promise<Sent[]> {
    const r = await this.sql`SELECT to_id, kind FROM friend_msgs WHERE from_id = ${from} AND day = ${day}`;
    return r.map((x: Sql) => ({ to: String(x.to_id), kind: String(x.kind) }));
  }

  async helpOpen(pid: string, since: number): Promise<Msg[]> {
    const r = await this.sql`SELECT m.*, p.name AS from_name FROM friend_msgs m JOIN players p ON p.id = m.from_id
        JOIN friendships f ON f.status = 'accepted' AND f.low = LEAST(${pid}::text, m.from_id) AND f.high = GREATEST(${pid}::text, m.from_id)
        WHERE m.kind = 'help' AND m.answered_by = '' AND m.created >= ${since} AND m.from_id <> ${pid}
        ORDER BY m.created DESC LIMIT 30`;
    return r.map((x: Sql) => this.msgRow(x));
  }

  async helpAnswer(id: number, helper: string, now: number): Promise<Msg | null> {
    const r = await this.sql`UPDATE friend_msgs SET answered_by = ${helper}, claimed = ${now}
        WHERE id = ${id} AND kind = 'help' AND answered_by = '' RETURNING *`;
    return r.length ? this.msgRow({ ...r[0], from_name: "" }) : null;
  }

  async friendCredits(pid: string, item: "shield" | "revive"): Promise<number> {
    const r = await this.sql`SELECT
        (SELECT COUNT(*) FROM wallet_log WHERE player_id = ${pid} AND reason = ${"fcredit:" + item})::int AS got,
        (SELECT COUNT(*) FROM wallet_log WHERE player_id = ${pid} AND reason = ${"spend:" + item} AND delta = 0)::int AS used`;
    return Math.max(0, Number(r[0].got) - Number(r[0].used));
  }

  async inviteSet(invitee: string, inviter: string, now: number): Promise<boolean> {
    const r = await this.sql`INSERT INTO friend_invites(invitee, inviter, created) VALUES(${invitee}, ${inviter}, ${now})
                             ON CONFLICT DO NOTHING RETURNING invitee`;
    return r.length > 0;
  }

  async inviteGet(invitee: string): Promise<{ inviter: string; paid: number } | null> {
    const r = await this.sql`SELECT inviter, paid FROM friend_invites WHERE invitee = ${invitee}`;
    return r.length ? { inviter: String(r[0].inviter), paid: Number(r[0].paid) } : null;
  }

  async invitePay(invitee: string, now: number): Promise<boolean> {
    const r = await this.sql`UPDATE friend_invites SET paid = ${now} WHERE invitee = ${invitee} AND paid = 0 RETURNING invitee`;
    return r.length > 0;
  }

  async hasBest(pid: string, level: number): Promise<boolean> {
    const r = await this.sql`SELECT 1 FROM bests WHERE player_id = ${pid} AND level = ${level}`;
    return r.length > 0;
  }

  async friendBests(pid: string, level: number, n: number): Promise<{ id: string; name: string; score: number; taps: number[] }[]> {
    const rows = await this.sql`SELECT b.player_id, p.name, b.score, b.taps FROM bests b JOIN players p ON p.id = b.player_id
        JOIN friendships f ON f.status = 'accepted' AND f.low = LEAST(${pid}::text, b.player_id) AND f.high = GREATEST(${pid}::text, b.player_id)
        WHERE b.level = ${level} AND COALESCE(b.assists, '') = '' AND b.taps LIKE '[%' ORDER BY b.score DESC, b.updated LIMIT ${n}`;
    const out: { id: string; name: string; score: number; taps: number[] }[] = [];
    for (const g of rows) {
      let taps: number[];
      try { taps = JSON.parse(g.taps); } catch { continue; }
      if (Array.isArray(taps) && taps.length) out.push({ id: String(g.player_id), name: String(g.name), score: Number(g.score), taps });
    }
    return out;
  }
}
