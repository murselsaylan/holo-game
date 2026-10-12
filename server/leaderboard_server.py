"""HOLO global leaderboard server (stdlib only: http.server + sqlite3).

    python server/leaderboard_server.py --port 8787 --db holo_scores.db

Scores are never trusted: the client uploads the *tap log* of a level clear, the server replays it on the very same
deterministic simulation (sim.py) and computes score / stars itself.  A signed (HMAC) request ties every upload to
the registered player.  Ranking = total of best level scores (desc), then highest level cleared (desc).
"""
import os
import sys
import re
import json
import time
import hmac
import hashlib
import sqlite3
import argparse
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from sim import LevelData, replay, SIM_VERSION, MAX_LEVELS  # noqa: E402

COUNTRIES = {"TR", "US", "DE", "GB", "JP", "KR", "FR", "BR", "CA", "AU", "IT", "ES", "NL", "AZ", "SE", "GX"}
MAX_BODY = 256 * 1024
MIN_TAP_GAP = 4                      # steps (66 ms): faster than any human can tap
MAX_TAPS = 4000
NAME_RE = re.compile(r"^[A-Z0-9İŞĞÜÖÇ _\-.]{1,12}$")

_level_cache = {}
_replay_slots = threading.Semaphore(3)
_db_lock = threading.Lock()
_rate = {}


def get_level(n):
    if n not in _level_cache:
        _level_cache[n] = LevelData.load(n)
    return _level_cache[n]


SCHEMA = [
    """CREATE TABLE IF NOT EXISTS players(
  id TEXT PRIMARY KEY, secret TEXT NOT NULL, name TEXT NOT NULL, country TEXT NOT NULL,
  levels INTEGER NOT NULL DEFAULT 0, score INTEGER NOT NULL DEFAULT 0, stars INTEGER NOT NULL DEFAULT 0,
  created BIGINT NOT NULL, updated BIGINT NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS bests(
  player_id TEXT NOT NULL, level INTEGER NOT NULL, score INTEGER NOT NULL, stars INTEGER NOT NULL,
  "time" DOUBLE PRECISION NOT NULL, swaps INTEGER NOT NULL, "rank" TEXT NOT NULL, taps TEXT NOT NULL, updated BIGINT NOT NULL,
  PRIMARY KEY(player_id, level))""",
    "CREATE INDEX IF NOT EXISTS idx_rank ON players(levels DESC, score DESC)",
    "CREATE INDEX IF NOT EXISTS idx_country ON players(country, levels DESC, score DESC)",
    "CREATE INDEX IF NOT EXISTS idx_score ON players(score DESC, levels DESC)",
    "CREATE TABLE IF NOT EXISTS saves(player_id TEXT PRIMARY KEY, data TEXT NOT NULL, updated BIGINT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS recovery(hash TEXT PRIMARY KEY, player_id TEXT NOT NULL)",
    """CREATE TABLE IF NOT EXISTS endless_bests(week TEXT NOT NULL, player_id TEXT NOT NULL, metres INTEGER NOT NULL,
  steps INTEGER NOT NULL, nonce TEXT NOT NULL, taps TEXT NOT NULL, updated BIGINT NOT NULL, PRIMARY KEY(week, player_id))""",
]


class Store:
    """Persistence. `target` is a sqlite file path, or a postgres:// URL (free hosts have ephemeral disks, so the
    leaderboard lives in an external free Postgres such as Neon / Supabase / Aiven)."""

    def __init__(self, target):
        self.pg = str(target).startswith(("postgres://", "postgresql://"))
        if self.pg:
            import ssl
            from urllib.parse import unquote
            u = urlparse(str(target))
            # libpq semantics: sslmode=require (or absent) = encrypted but certificate not verified (Supabase's pooler uses its own CA);
            # verify-ca / verify-full = full verification (Neon's public certificate works with this too).
            ctx = ssl.create_default_context()
            if parse_qs(u.query).get("sslmode", ["require"])[0] not in ("verify-ca", "verify-full"):
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
            self._pg_args = dict(user=unquote(u.username or ""), password=unquote(u.password or ""), host=u.hostname,
                                 port=u.port or 5432, database=(u.path or "/").lstrip("/") or "postgres",
                                 ssl_context=ctx, timeout=20)
            self.db = None
        else:
            self.db = sqlite3.connect(target, check_same_thread=False)
        for stmt in SCHEMA:
            self._run(lambda cur, st=stmt: self._exec(cur, st))

    # -- plumbing
    def _exec(self, cur, sql, args=()):
        cur.execute(sql.replace("?", "%s") if self.pg else sql, args)

    @staticmethod
    def _rows(cur):
        cols = [(c[0].decode() if isinstance(c[0], bytes) else c[0]) for c in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]

    def _run(self, work):
        with _db_lock:
            if not self.pg:
                cur = self.db.cursor()
                out = work(cur)
                self.db.commit()
                return out
            import pg8000.dbapi
            conn = pg8000.dbapi.connect(**self._pg_args)
            try:
                cur = conn.cursor()
                out = work(cur)
                conn.commit()
                return out
            except Exception:
                try:
                    conn.rollback()
                except Exception:
                    pass
                raise
            finally:
                conn.close()

    def _one(self, sql, args=()):
        def w(cur):
            self._exec(cur, sql, args)
            rows = self._rows(cur)
            return rows[0] if rows else None
        return self._run(w)

    # -- API: account recovery (mirror of supabase/functions/scores store_pg.ts)
    def save_cloud(self, pid, data):
        now = int(time.time())

        def w(cur):
            self._exec(cur, "DELETE FROM saves WHERE player_id=?", (pid,))
            self._exec(cur, "INSERT INTO saves(player_id, data, updated) VALUES(?,?,?)", (pid, data, now))
        self._run(w)

    def set_recovery(self, pid, h):
        def w(cur):
            self._exec(cur, "DELETE FROM recovery WHERE player_id=?", (pid,))
            self._exec(cur, "INSERT INTO recovery(hash, player_id) VALUES(?,?)", (h, pid))
        self._run(w)

    def restore(self, h):
        def w(cur):
            self._exec(cur, "SELECT player_id FROM recovery WHERE hash=?", (h,))
            r = self._rows(cur)
            if not r:
                return None
            pid = r[0]["player_id"]
            self._exec(cur, "SELECT * FROM players WHERE id=?", (pid,))
            pl = self._rows(cur)
            if not pl:
                return None
            self._exec(cur, "SELECT data FROM saves WHERE player_id=?", (pid,))
            sv = self._rows(cur)
            self._exec(cur, 'SELECT level, score, stars, "time", swaps, "rank" FROM bests WHERE player_id=? ORDER BY level', (pid,))
            bests = self._rows(cur)
            return pl[0], (sv[0]["data"] if sv else None), bests
        return self._run(w)

    def player(self, pid):
        return self._one("SELECT * FROM players WHERE id=?", (pid,))

    def register(self, pid, secret, name, country):
        now = int(time.time())

        def w(cur):
            self._exec(cur, "SELECT secret FROM players WHERE id=?", (pid,))
            row = self._rows(cur)
            if not row:
                self._exec(cur, "INSERT INTO players(id,secret,name,country,created,updated) VALUES(?,?,?,?,?,?)",
                           (pid, secret, name, country, now, now))
            elif not hmac.compare_digest(row[0]["secret"], secret):
                return False
            else:
                self._exec(cur, "UPDATE players SET name=?, country=?, updated=? WHERE id=?", (name, country, now, pid))
            return True
        return self._run(w)

    def record(self, pid, level, res, taps):
        now = int(time.time())

        def w(cur):
            self._exec(cur, "SELECT score FROM bests WHERE player_id=? AND level=?", (pid, level))
            cur_row = self._rows(cur)
            improved = not cur_row or res["level_total"] > cur_row[0]["score"]
            if improved:
                self._exec(cur, 'INSERT INTO bests(player_id,level,score,stars,"time",swaps,"rank",taps,updated) '
                                "VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT (player_id, level) DO UPDATE SET "
                                'score=EXCLUDED.score, stars=EXCLUDED.stars, "time"=EXCLUDED."time", swaps=EXCLUDED.swaps, '
                                '"rank"=EXCLUDED."rank", taps=EXCLUDED.taps, updated=EXCLUDED.updated',
                           (pid, level, res["level_total"], res["stars"], res["time"], res["swaps"], res["rank"],
                            json.dumps(taps), now))
            self._exec(cur, "SELECT COALESCE(MAX(level),0) AS c, COALESCE(SUM(score),0) AS s, COALESCE(SUM(stars),0) AS st FROM bests "
                            "WHERE player_id=?", (pid,))
            agg = self._rows(cur)[0]
            c, sc, st = int(agg["c"]), int(agg["s"]), int(agg["st"])
            self._exec(cur, "UPDATE players SET levels=?, score=?, stars=?, updated=? WHERE id=?", (c, sc, st, now, pid))
            return improved, c, sc, st
        return self._run(w)

    def ranks(self, pid):
        def w(cur):
            self._exec(cur, "SELECT * FROM players WHERE id=?", (pid,))
            rows = self._rows(cur)
            if not rows or rows[0]["levels"] == 0:
                return None
            me = rows[0]
            self._exec(cur, "SELECT COUNT(*)+1 AS r FROM players WHERE levels>0 AND (score>? OR (score=? AND levels>?))",
                       (me["score"], me["score"], me["levels"]))
            wr = int(self._rows(cur)[0]["r"])
            self._exec(cur, "SELECT COUNT(*)+1 AS r FROM players WHERE country=? AND levels>0 AND (score>? OR (score=? AND levels>?))",
                       (me["country"], me["score"], me["score"], me["levels"]))
            cr = int(self._rows(cur)[0]["r"])
            return {"rank": wr, "country_rank": cr, "levels": me["levels"], "score": me["score"], "stars": me["stars"]}
        return self._run(w)

    # ---- endless climb (mirror of store_pg.ts; no wallet here, so no diamonds)
    def endless_record(self, pid, week, metres, steps, nonce, taps, now):
        def w(cur):
            self._exec(cur, "SELECT metres FROM endless_bests WHERE week=? AND player_id=?", (week, pid))
            rows = self._rows(cur)
            if rows and int(rows[0]["metres"]) >= metres:
                self._exec(cur, "SELECT MAX(metres) AS m FROM endless_bests WHERE player_id=?", (pid,))
                return int(self._rows(cur)[0]["m"]), False
            if rows:
                self._exec(cur, "UPDATE endless_bests SET metres=?, steps=?, nonce=?, taps=?, updated=? WHERE week=? AND player_id=?",
                           (metres, steps, nonce, json.dumps(taps), now, week, pid))
            else:
                self._exec(cur, "INSERT INTO endless_bests(week, player_id, metres, steps, nonce, taps, updated) VALUES(?,?,?,?,?,?,?)",
                           (week, pid, metres, steps, nonce, json.dumps(taps), now))
            return metres, True
        return self._run(w)

    _BEST = "(SELECT player_id, MAX(metres) AS metres, MIN(updated) AS updated FROM endless_bests GROUP BY player_id)"

    def endless_standing(self, pid, week):
        """All-time (1.0.6): every player's best climb of any week."""
        def w(cur):
            self._exec(cur, f"SELECT metres, updated FROM {self._BEST} b WHERE player_id=?", (pid,))
            rows = self._rows(cur)
            if not rows:
                return None
            m, u = int(rows[0]["metres"]), int(rows[0]["updated"])
            self._exec(cur, f"SELECT COUNT(*)+1 AS r FROM {self._BEST} b WHERE metres>? OR (metres=? AND updated<?)", (m, m, u))
            rk = int(self._rows(cur)[0]["r"])
            self._exec(cur, f"SELECT COUNT(*) AS c FROM {self._BEST} b")
            return {"rank": rk, "metres": m, "points": m, "total": int(self._rows(cur)[0]["c"])}
        return self._run(w)

    def endless_board(self, week, offset, limit):
        def w(cur):
            self._exec(cur, f"SELECT e.player_id AS id, p.name, p.country, e.metres FROM {self._BEST} e JOIN players p ON p.id = e.player_id "
                            "ORDER BY e.metres DESC, e.updated ASC LIMIT ? OFFSET ?", (limit, offset))
            rows = self._rows(cur)
            self._exec(cur, f"SELECT COUNT(*) AS c FROM {self._BEST} b")
            return rows, int(self._rows(cur)[0]["c"])
        rows, total = self._run(w)
        return [{"rank": offset + i + 1, "id": r["id"], "name": r["name"], "country": r["country"], "metres": int(r["metres"]), "points": int(r["metres"])}
                for i, r in enumerate(rows)], total

    def board(self, scope, country, offset, limit):
        where, args = "levels>0", []
        if scope == "country":
            where += " AND country=?"
            args.append(country)

        def w(cur):
            self._exec(cur, f"SELECT * FROM (SELECT id,name,country,levels,score,stars, "
                            f"RANK() OVER (ORDER BY score DESC, levels DESC) AS rk FROM players WHERE {where}) AS t "
                            f"ORDER BY rk, name LIMIT ? OFFSET ?", args + [limit, offset])
            rows = self._rows(cur)
            self._exec(cur, f"SELECT COUNT(*) AS c FROM players WHERE {where}", args)
            return rows, int(self._rows(cur)[0]["c"])
        rows, total = self._run(w)
        return [{"rank": int(r["rk"]), "id": r["id"], "name": r["name"], "country": r["country"], "levels": r["levels"],
                 "score": r["score"], "stars": r["stars"]} for r in rows], total


def clean_name(name):
    name = str(name or "").strip().upper()[:12]
    return name if NAME_RE.match(name) else "PİLOT"


def sign(secret, pid, level, ts, taps):
    msg = f"{pid}|{level}|{ts}|{','.join(str(int(t)) for t in taps)}".encode()
    return hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()


CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
MAX_SAVE = 200 * 1024


def sign_msg(secret, msg):
    return hmac.new(secret.encode(), msg.encode(), hashlib.sha256).hexdigest()


def sign_save(secret, pid, ts, data):
    return sign_msg(secret, f"{pid}|save|{ts}|{hashlib.sha256(data.encode()).hexdigest()}")


def sign_bests(secret, pid, ts):
    return sign_msg(secret, f"{pid}|bests|{ts}")


def sign_code(secret, pid, ts):
    return sign_msg(secret, f"{pid}|code|{ts}")


def norm_code(c):
    return re.sub(r"[^A-Z0-9]", "", str(c or "").upper())


def code_hash(code):
    return hashlib.sha256(("holo-recovery|" + code).encode()).hexdigest()


def limited(key, limit, per=60.0):
    now = time.time()
    hits = [t for t in _rate.get(key, []) if now - t < per]
    if len(_rate) > 5000:                       # keep memory bounded
        _rate.clear()
    if len(hits) >= limit:
        _rate[key] = hits
        return True
    hits.append(now)
    _rate[key] = hits
    return False


def client_ip(forwarded_for, remote):
    """Behind a hosting proxy every request comes from the proxy: use the first X-Forwarded-For hop when trusted."""
    if forwarded_for and os.environ.get("HOLO_TRUST_PROXY", "1") == "1":
        return forwarded_for.split(",")[0].strip()[:64]
    return remote


def dispatch(store, method, path, query, body, ip):
    """Transport independent request handler -> (status, json-able dict). Used by both http.server and WSGI."""
    if method == "GET":
        if path == "/api/health":
            return 200, {"ok": True, "sim": SIM_VERSION, "time": int(time.time())}
        if path == "/api/leaderboard":
            if limited(("g", ip), 120):
                return 429, {"error": "slow down"}
            q = {k: v[0] for k, v in parse_qs(query).items()}
            try:
                limit = max(1, min(100, int(q.get("limit", 50))))
            except ValueError:
                return 400, {"error": "bad request"}
            scope = q.get("scope", "global")
            pid = q.get("player_id", "")[:64]
            me = store.ranks(pid) if pid else None
            country = q.get("country", "")[:4].upper()
            offset = 0
            if scope == "around" and me:
                offset = max(0, me["rank"] - 1 - limit // 2)
                scope_q = "global"
            else:
                scope_q = "country" if scope == "country" else "global"
            if scope_q == "country" and me:
                pl = store.player(pid)
                country = pl["country"] if pl else country
            rows, total = store.board(scope_q, country, offset, limit)
            return 200, {"scope": scope, "rows": rows, "total": total, "me": me or {}}
        if path == "/api/endless/board":
            import endless as E
            q = {k: v[0] for k, v in parse_qs(query).items()}
            week = q.get("week") or E.week_of(time.time())
            limit = max(1, min(100, int(q.get("limit", 100) or 100)))
            pid = q.get("player_id", "")[:64]
            rows, total = store.endless_board(week, 0, limit)
            me = store.endless_standing(pid, week) if pid else None
            return 200, {"scope": "endless", "week": week, "rows": rows, "total": total, "me": me or {}}
        return 404, {"error": "not found"}
    if method == "POST":
        if not body or len(body) > MAX_BODY:
            return 400, {"error": "bad request"}
        try:
            data = json.loads(body.decode())
        except Exception:
            return 400, {"error": "bad request"}
        if path == "/api/register":
            return _register(store, data, ip)
        if path == "/api/submit":
            return _submit(store, data, ip)
        if path == "/api/cloud/save":
            return _cloud_save(store, data, ip)
        if path == "/api/cloud/code":
            return _cloud_code(store, data, ip)
        if path == "/api/cloud/restore":
            return _cloud_restore(store, data, ip)
        if path == "/api/bests":
            return _my_bests(store, data, ip)
        if path == "/api/endless/submit":
            return _endless_submit(store, data, ip)
    return 404, {"error": "not found"}


def _endless_submit(store, d, ip):
    """Mirror of handler.ts endlessSubmit (no wallet: never pays diamonds)."""
    import endless as E
    try:
        week, nonce, end = str(d["week"]), str(d["nonce"]), int(d["end"])
        taps = [int(x) for x in d["taps"]]
    except Exception:
        return 400, {"error": "bad run"}
    if any(b - a < MIN_TAP_GAP for a, b in zip(taps, taps[1:])):
        return 422, {"error": "implausible input"}
    if int(d.get("v", 0)) != E.ENDLESS_VERSION or str(d.get("pool", "")) != E.pool_digest():
        return 409, {"error": "update the game"}
    helps = [[int(a[0]), str(a[1])] for a in (d.get("assists") or [])]
    if any(a[1] not in ("S", "R", "R2", "R3") for a in helps) or sum(1 for a in helps if a[1] != "S") > E.MAX_REVIVES:
        return 400, {"error": "bad assists"}
    digest = hashlib.sha256(E.assist_digest(taps, helps).encode()).hexdigest()
    pl = _authed(store, d, lambda secret, pid, ts: sign_msg(secret, f"{pid}|endless|{week}|{nonce}|{end}|{ts}|{digest}"))
    if pl is None:
        return 403, {"error": "bad signature"}
    run = E.replay(E.seed_of(week, nonce), taps, end, assists=helps)       # (no wallet here: help is not charged)
    best, improved = store.endless_record(pl["id"], week, run.points, run.n, nonce, taps, int(time.time()))  # ranks by points
    st = store.endless_standing(pl["id"], week) or {}
    return 200, {"ok": True, "metres": run.metres, "stars": run.stars, "points": run.points, "best": best, "improved": improved, "rank": st.get("rank", 0),
                 "total": st.get("total", 0), "added": 0, "capped": False, "balance": None,
                 "next_gem": E.DIAMOND_EVERY_M - run.metres % E.DIAMOND_EVERY_M, "steps": run.n}


def _authed(store, d, sig_fn):
    try:
        pid, ts = str(d["player_id"]), int(d["ts"])
    except Exception:
        return None
    if abs(time.time() - ts) > 900:
        return None
    pl = store.player(pid)
    if pl is None or not hmac.compare_digest(str(d.get("sig", "")), sig_fn(pl["secret"], pid, ts)):
        return None
    return pl


def _cloud_save(store, d, ip):
    if limited(("cs", ip), 20):
        return 429, {"error": "slow down"}
    data = d.get("data")
    if not isinstance(data, str) or not data or len(data) > MAX_SAVE:
        return 400, {"error": "bad save"}
    pl = _authed(store, d, lambda sec, pid, ts: sign_save(sec, pid, ts, data))
    if pl is None:
        return 403, {"error": "bad signature"}
    store.save_cloud(pl["id"], data)
    return 200, {"ok": True}


def _cloud_code(store, d, ip):
    if limited(("cc", ip), 10):
        return 429, {"error": "slow down"}
    pl = _authed(store, d, sign_code)
    if pl is None:
        return 403, {"error": "bad signature"}
    code = "".join(CODE_ALPHABET[b & 31] for b in os.urandom(12))
    store.set_recovery(pl["id"], code_hash(code))
    return 200, {"ok": True, "code": f"{code[:4]}-{code[4:8]}-{code[8:]}"}


def _my_bests(store, d, ip):
    if limited(("mb", ip), 20):
        return 429, {"error": "slow down"}
    pl = _authed(store, d, sign_bests)
    if pl is None:
        return 403, {"error": "bad signature"}
    rows = store._run(lambda cur: (store._exec(cur, 'SELECT level, score, stars, "time", swaps, "rank" FROM bests WHERE player_id=? ORDER BY level',
                                               (pl["id"],)), store._rows(cur))[1])
    return 200, {"ok": True, "bests": [{"level": int(b["level"]), "score": int(b["score"]), "stars": int(b["stars"]),
                                         "time": float(b["time"]), "swaps": int(b["swaps"]), "rank": b["rank"]} for b in rows]}


def _cloud_restore(store, d, ip):
    if limited(("cr", ip), 8, per=3600.0):
        return 429, {"error": "slow down"}
    code = norm_code(d.get("code"))
    if len(code) != 12:
        return 400, {"error": "bad code"}
    got = store.restore(code_hash(code))
    if not got:
        return 404, {"error": "unknown code"}
    pl, data, bests = got
    return 200, {"ok": True, "player_id": pl["id"], "secret": pl["secret"], "name": pl["name"], "country": pl["country"],
                 "data": data, "bests": [{"level": int(b["level"]), "score": int(b["score"]), "stars": int(b["stars"]),
                                          "time": float(b["time"]), "swaps": int(b["swaps"]), "rank": b["rank"]} for b in bests]}


def _register(store, d, ip):
    if limited(("r", ip), 30):
        return 429, {"error": "slow down"}
    pid, secret = str(d.get("player_id", "")), str(d.get("secret", ""))
    if not re.fullmatch(r"[0-9a-f]{32}", pid) or not re.fullmatch(r"[0-9a-f]{48}", secret):
        return 400, {"error": "bad identity"}
    country = str(d.get("country", "GX")).upper()[:4]
    country = country if country in COUNTRIES else "GX"
    if not store.register(pid, secret, clean_name(d.get("name")), country):
        return 403, {"error": "identity mismatch"}
    return 200, {"ok": True}


def _submit(store, d, ip):
    if limited(("s", ip), 40):
        return 429, {"error": "slow down"}
    try:
        pid = str(d["player_id"])
        level = int(d["level"])
        ts = int(d["ts"])
        taps = [int(t) for t in d["taps"]]
        sig = str(d["sig"])
    except Exception:
        return 400, {"error": "bad request"}
    pl = store.player(pid)
    if pl is None:
        return 403, {"error": "unknown player"}
    if not hmac.compare_digest(sig, sign(pl["secret"], pid, level, ts, taps)):
        return 403, {"error": "bad signature"}
    if abs(time.time() - ts) > 900:
        return 400, {"error": "stale request"}
    if not (1 <= level <= MAX_LEVELS) or len(taps) > MAX_TAPS or not taps:
        return 400, {"error": "bad level or taps"}
    if any(b - a < MIN_TAP_GAP for a, b in zip(taps, taps[1:])) or taps[0] < 0 or taps[-1] > 60 * 900:
        return 422, {"error": "implausible input"}
    lvl = get_level(level)
    if lvl is None:
        return 400, {"error": "unknown level"}
    claimed = str(d.get("lvl", ""))
    if claimed and claimed != lvl.digest:
        return 409, {"error": "level version mismatch - update the game"}
    with _replay_slots:
        sim, res = replay(lvl, taps, max_seconds=max(90.0, lvl.par_time * 8))
    if res is None:
        return 422, {"error": "replay did not clear the level"}
    improved, levels, score, stars = store.record(pid, level, res, taps)
    ranks = store.ranks(pid) or {}
    return 200, {"ok": True, "level_score": res["level_total"], "stars": res["stars"], "improved": improved,
                 "levels": levels, "score": score, "world_rank": ranks.get("rank"),
                 "country_rank": ranks.get("country_rank")}


class Handler(BaseHTTPRequestHandler):
    store = None
    server_version = "HoloScores/5"

    def log_message(self, fmt, *args):
        if os.environ.get("HOLO_VERBOSE"):
            super().log_message(fmt, *args)

    def _send(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _run(self, method):
        u = urlparse(self.path)
        body = b""
        if method == "POST":
            try:
                n = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                n = 0
            if n > MAX_BODY:
                return self._send(413, {"error": "too large"})
            body = self.rfile.read(n) if n > 0 else b""
        ip = client_ip(self.headers.get("X-Forwarded-For"), self.client_address[0])
        code, obj = dispatch(self.store, method, u.path, u.query, body, ip)
        self._send(code, obj)

    def do_GET(self):
        self._run("GET")

    def do_POST(self):
        self._run("POST")


def make_server(port=8787, db="holo_scores.db", host="0.0.0.0"):
    Handler.store = Store(db)
    return ThreadingHTTPServer((host, port), Handler)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8787)))
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--db", default=os.environ.get("DATABASE_URL") or os.environ.get("HOLO_DB", "holo_scores.db"),
                    help="sqlite file path or postgres:// URL (env DATABASE_URL)")
    a = ap.parse_args()
    srv = make_server(a.port, a.db, a.host)
    print(f"HOLO leaderboard on http://{a.host}:{a.port}  (db: {a.db})")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
