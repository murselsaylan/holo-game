"""Leaderboard client: registers the pilot, submits verified run proofs, fetches rankings.

All network work happens on two worker threads - one for register/submit (the server replays each run, which can
take a moment) and one for leaderboard reads, so a ranking never waits behind a submit. The game polls `poll()`
once per frame. Nothing here can block or crash the game: any failure just flips `status` to "offline" and queued
proofs are retried later.

Speed: every worker keeps one HTTPS connection alive (no TLS handshake per request), and requests carry the
`x-region` header so the server function runs next to its database instead of next to the player - otherwise
every query crosses the globe. The last boards are kept in the save and shown at once while a fresh copy loads.
"""
import os
import sys
import json
import time
import hmac
import hashlib
import threading
import queue
import http.client
import urllib.parse
import ssl
import secrets


def _config():
    try:
        base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(base, "config.json"), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


_CFG = _config()
# HOLO_SERVER env var wins, then config.json next to the game (the only option on Android)
SERVER_URL = os.environ.get("HOLO_SERVER", "").strip() or str(_CFG.get("server_url", "")).strip() or "http://127.0.0.1:8787"
SERVER_REGION = os.environ.get("HOLO_SERVER_REGION", str(_CFG.get("server_region", ""))).strip()
TIMEOUT = 20.0
SUBMIT_TIMEOUT = 60.0     # the server replays the whole run before answering
BOARD_SCOPES_KEPT = ("global", "country", "around")


def _ssl_context():
    """HTTPS with a bundled CA list (certifi) - Android's python has no system certificate store."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


_SSL = _ssl_context()


def _sign(secret, player_id, level, ts, taps):
    msg = f"{player_id}|{level}|{ts}|{','.join(str(int(t)) for t in taps)}".encode()
    return hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()


def _sign_msg(secret, msg):
    return hmac.new(secret.encode(), msg.encode(), hashlib.sha256).hexdigest()


class HTTPError(Exception):
    def __init__(self, code, body):
        super().__init__(f"HTTP {code}")
        self.code = code
        self.body = body


class _Connection:
    """One persistent HTTP(S) connection (keep-alive), reopened transparently when the server closed it."""

    _RETRYABLE = (http.client.RemoteDisconnected, http.client.CannotSendRequest, http.client.BadStatusLine,
                  BrokenPipeError, ConnectionResetError, ConnectionAbortedError)

    def __init__(self, url):
        u = urllib.parse.urlsplit(url)
        self.https = u.scheme == "https"
        self.host = u.hostname or "127.0.0.1"
        self.port = u.port
        self.base = u.path.rstrip("/")
        self.conn = None

    def _open(self, timeout):
        if self.https:
            self.conn = http.client.HTTPSConnection(self.host, self.port, timeout=timeout, context=_SSL)
        else:
            self.conn = http.client.HTTPConnection(self.host, self.port, timeout=timeout)

    def close(self):
        if self.conn is not None:
            try:
                self.conn.close()
            except Exception:
                pass
        self.conn = None

    def request(self, method, path, body=None, timeout=TIMEOUT):
        data = json.dumps(body).encode() if body is not None else None
        headers = {"Content-Type": "application/json", "User-Agent": "holo-client/6", "Connection": "keep-alive"}
        if SERVER_REGION:
            headers["x-region"] = SERVER_REGION
        for attempt in (0, 1):
            reused = self.conn is not None
            if not reused:
                self._open(timeout)
            else:
                self.conn.timeout = timeout
                if self.conn.sock is not None:
                    self.conn.sock.settimeout(timeout)
            try:
                self.conn.request(method, self.base + path, body=data, headers=headers)
                r = self.conn.getresponse()
                raw = r.read()
            except self._RETRYABLE:
                self.close()
                if reused and attempt == 0:
                    continue                    # the idle keep-alive connection was closed by the server: retry once
                raise
            except Exception:
                self.close()
                raise
            if r.getheader("Connection", "").lower() == "close":
                self.close()
            if r.status >= 400:
                raise HTTPError(r.status, raw)
            return json.loads(raw.decode())
        raise OSError("unreachable")


class OnlineClient:
    def __init__(self, save_manager, server_url=None):
        self.save = save_manager
        self.url = (server_url or SERVER_URL).rstrip("/")
        self.status = "idle"            # idle | ok | offline | disabled  (per board: is_loading(scope))
        cache = self.save.data.get("lb_cache")
        self.boards = dict(cache) if isinstance(cache, dict) else {}   # scope -> {"rows": [...], "me": {...}}
        self.last_submit = None         # last submit response (for the victory screen)
        me = (self.boards.get("around") or {}).get("me") or {}
        self.rank_info = me if me.get("rank") else None     # {"rank": .., "country_rank": ..} of the local player
        self._submit_jobs = queue.Queue()
        self._fetch_jobs = queue.Queue()
        self._results = queue.Queue()
        self._fetch_lock = threading.Lock()
        self._fetch_pending = {}        # scope -> limit, a board request already waiting (no duplicates)
        self._registered = False        # only touched by the submit worker
        self._clock_offset = 0.0
        self._cache_saved = {}          # scope -> when its board was last written to the save
        self._cloud_lock = threading.Lock()
        self._cloud_blob = None         # newest save copy waiting for upload (older ones are simply replaced)
        self.recovery = None            # {"state": "wait"|"ok"|"fail", "code"|"reason": ...}  (my recovery code)
        self.restore_state = None       # {"state": "wait"|"ok"|"fail", "payload"|"reason": ...}
        # diamond wallet (the server owns the balance, see supabase/functions/scores/wallet.ts)
        self._wallet_lock = threading.Lock()
        self._spends = []               # [(item, ref, on_done)] waiting for the server
        self._wallet_queued = False
        self._wallet_open = False       # synced once in this session (only touched by the submit worker)
        self.gift_notice = 0            # diamonds gifted by the developer, for the game to announce
        self.on_purchase = None         # shop.purchase_result(product, token, "ok"|"rejected"|"wait", body)
        self.endless_result = None      # server answer for the endless climb just finished (result screen)
        self.google = None              # {"state": "wait"|"ok"|"fail", ...} of the last Google link / restore
        self._endless_current = None    # id of that climb
        self.ghosts = {}                # level -> {"id", "name", "score", "taps"} of the world's best clean run ({} = none)
        self.ghost_new = False          # a ghost just arrived (the game installs it if that level is being played)
        for jobs in (self._submit_jobs, self._fetch_jobs):
            threading.Thread(target=self._worker, args=(jobs,), daemon=True).start()

    # ---------------------------------------------------------------- public api
    @property
    def enabled(self):
        return bool(self.save.settings.get("online", True))

    def register(self):
        if not self.enabled:
            return
        self._submit_jobs.put(("register", None))

    def submit(self, level_id, taps, digest="", assists=None):
        """Queue a proof of a level clear (with its paid help). Persisted in the save so it survives being offline."""
        self.save.queue_run(level_id, taps, digest, assists=assists)
        self.last_submit = None
        if self.enabled:
            self._submit_jobs.put(("flush", None))

    def flush_pending(self):
        if self.enabled and self.save.data.get("pending_runs"):
            self._submit_jobs.put(("flush", None))
        if self.enabled and self.save.data.get("endless_runs"):
            self._submit_jobs.put(("endless", None))

    # ---- account recovery through Google (1.0.5)
    def google_link(self, id_token):
        """Link this pilot to the Google account of `id_token` -> self.google {"state": "ok", "email"} / "fail"."""
        self.google = {"state": "wait", "mode": "link"}
        self._submit_jobs.put(("glink", str(id_token)))

    def google_restore(self, id_token):
        """The pilot linked to that Google account -> self.google {"state": "ok", "payload"} (the game imports it)."""
        self.google = {"state": "wait", "mode": "restore"}
        self._submit_jobs.put(("grestore", str(id_token)))

    # ---- endless climb
    def submit_endless(self, week, nonce, taps, end_step, assists=None):
        """Queue a finished climb (the server rebuilds its map from week + nonce, replays it with its paid help,
        ranks it, pays diamonds)."""
        rid = secrets.token_hex(8)
        run = {"id": rid, "week": week, "nonce": nonce, "taps": [int(x) for x in taps], "end": int(end_step)}
        if assists:
            run["assists"] = [[int(a[0]), str(a[1])] for a in assists]
        self.save.queue_endless(run)
        self.endless_result = None
        self._endless_current = rid
        if self.enabled:
            self._submit_jobs.put(("endless", None))
        return rid

    # ---- account recovery
    def cloud_save(self, blob):
        """Upload the save (a JSON string) as this account's recovery copy; newer calls replace a waiting one."""
        if not self.enabled:
            return
        with self._cloud_lock:
            waiting = self._cloud_blob is not None
            self._cloud_blob = blob
        if not waiting:
            self._submit_jobs.put(("cloud_save", None))

    def request_code(self):
        """Ask the server for a (new) recovery code of this account -> self.recovery."""
        self.recovery = {"state": "wait"}
        self._submit_jobs.put(("code", None))

    def restore(self, code):
        """Look an account up by its recovery code -> self.restore_state (the caller imports the payload)."""
        self.restore_state = {"state": "wait"}
        self._submit_jobs.put(("restore", str(code)))

    # ---- diamond wallet
    def wallet_sync(self):
        """Fetch the balance (first time: bring the old local balance over) and collect any gift."""
        if self.enabled:
            self._wallet_open = False
            self._queue_wallet()

    def wallet_flush(self):
        """Send earnings still waiting in the save."""
        if self.enabled:
            self._queue_wallet()

    def wallet_spend(self, item, cost, on_done):
        """Ask the server to take `cost` diamonds for `item`; on_done(ok, reason) runs in poll()."""
        if not self.enabled:
            on_done(False, "offline")
            return
        with self._wallet_lock:
            self._spends.append((item, secrets.token_hex(12), on_done))
        self._queue_wallet()

    def _queue_wallet(self):
        with self._wallet_lock:
            if self._wallet_queued:
                return
            self._wallet_queued = True
        self._submit_jobs.put(("wallet", None))

    def fetch(self, scope="global", limit=100):
        if not self.enabled:
            self.status = "disabled"
            return
        with self._fetch_lock:
            waiting = scope in self._fetch_pending
            self._fetch_pending[scope] = max(limit, self._fetch_pending.get(scope, 0))
        if not waiting:
            self._fetch_jobs.put(("fetch", scope))

    def fetch_ghost(self, level):
        """The world's best clean run of `level`, raced as the ghost (once per session per level)."""
        if self.enabled and level not in self.ghosts:
            self.ghosts[level] = None                   # asked
            self._fetch_jobs.put(("ghost", level))

    def is_loading(self, scope):
        """A fresh copy of this board is on its way (a cached one, if any, stays on screen meanwhile)."""
        with self._fetch_lock:
            return scope in self._fetch_pending

    def poll(self):
        """Apply finished worker results on the main thread."""
        while True:
            try:
                kind, payload = self._results.get_nowait()
            except queue.Empty:
                break
            if kind == "board":
                scope, data = payload
                self.boards[scope] = data
                with self._fetch_lock:
                    self._fetch_pending.pop(scope, None)
                if scope in BOARD_SCOPES_KEPT:
                    lock = getattr(self.save, "_lock", None)
                    with lock if lock is not None else threading.Lock():
                        cache = self.save.data.setdefault("lb_cache", {})
                        if isinstance(cache, dict):
                            cache[scope] = data
                    now = time.time()
                    if now - self._cache_saved.get(scope, 0.0) > 30.0 and hasattr(self.save, "save"):
                        self._cache_saved[scope] = now      # so the next start shows these rows at once
                        self.save.save()
                me = data.get("me")
                if me and me.get("rank"):
                    self.rank_info = me
                self.status = "ok"
            elif kind == "submit":
                if not payload.get("bg"):                 # a re-sent old best is not the run on the victory screen
                    self.last_submit = payload
                if payload.get("ok"):
                    self.status = "ok"
                    self.rank_info = {"rank": payload.get("world_rank"), "country_rank": payload.get("country_rank")}
                    self.save.drop_run(payload["level"])
                    # the ranking just changed: refresh what the player has seen (and the menu's own position)
                    for scope in set(self.boards) | {"around"}:
                        self.fetch(scope, limit=11 if scope == "around" else 100)
            elif kind == "endless":
                rid = payload.get("id")
                if payload.get("ok") or payload.get("rejected"):
                    self.save.drop_endless(rid)
                if rid == self._endless_current:
                    self.endless_result = payload
                if payload.get("balance") is not None:
                    self.save.set_server_balance(payload["balance"])
                if payload.get("ok"):
                    self.status = "ok"
                    self.fetch("endless", limit=100)
            elif kind == "ghost":
                level, data = payload
                self.ghosts[level] = data
                self.ghost_new = True
            elif kind == "bests":
                if hasattr(self.save, "sync_bests") and self.save.sync_bests(payload):
                    self.flush_pending()                  # local bests the server never got are sent again
            elif kind == "code":
                self.recovery = {"state": "ok", "code": payload}
            elif kind == "code_fail":
                self.recovery = {"state": "fail", "reason": payload}
            elif kind == "restored":
                self.restore_state = {"state": "ok", "payload": payload}
                self._registered = False                    # a different identity from now on
            elif kind == "restore_fail":
                self.restore_state = {"state": "fail", "reason": payload}
            elif kind == "google":
                self.google = payload
                if payload.get("state") == "ok" and payload.get("mode") == "restore":
                    self._registered = False                # a different identity from now on
            elif kind == "wallet":
                self.save.set_server_balance(payload["balance"])
                self.save.set_server_skins(payload.get("skins"), payload.get("account", ""))
                if payload.get("gift"):
                    self.gift_notice += int(payload["gift"])
            elif kind == "purchase":
                product, token, status, body = payload
                if status in ("ok", "rejected"):
                    self.save.drop_iap(token)
                if body and body.get("balance") is not None:
                    self.save.set_server_balance(body["balance"])
                if self.on_purchase:
                    try:
                        self.on_purchase(product, token, status, body)
                    except Exception as e:
                        print("purchase callback error:", e)
            elif kind == "earned":
                k, ref, balance = payload
                self.save.drop_wallet_op(k, ref)
                if balance is not None:
                    self.save.set_server_balance(balance)
            elif kind == "spent":
                on_done, ok, reason, balance = payload
                if balance is not None:
                    self.save.set_server_balance(balance)
                try:
                    on_done(ok, reason)
                except Exception as e:
                    print("wallet callback error:", e)
            elif kind == "offline":
                self.status = "offline"

    # ---------------------------------------------------------------- worker
    def _worker(self, jobs):
        conn = _Connection(self.url)
        while True:
            kind, arg = jobs.get()
            try:
                if kind == "register":
                    self._do_register(conn)
                elif kind == "flush":
                    self._do_flush(conn)
                elif kind in ("cloud_save", "code", "restore"):
                    self._do_account(conn, kind, arg)
                elif kind in ("glink", "grestore"):
                    self._do_google(conn, kind, arg)
                elif kind == "wallet":
                    self._do_wallet(conn)
                elif kind == "endless":
                    self._do_endless(conn)
                elif kind == "ghost":
                    r = conn.request("GET", "/api/ghost?" + urllib.parse.urlencode({"level": arg}))
                    taps = r.get("taps")
                    ok = isinstance(taps, list) and taps and all(isinstance(x, int) for x in taps)
                    self._results.put(("ghost", (arg, {"id": str(r.get("id", "")), "name": str(r.get("name", ""))[:16],
                                                       "score": int(r.get("score") or 0), "taps": sorted(taps)}
                                                 if ok else {})))
                elif kind == "fetch":
                    with self._fetch_lock:
                        limit = self._fetch_pending.get(arg, 100)
                    try:
                        self._do_fetch(conn, arg, limit)       # the pending mark is cleared when poll() applies it
                    except BaseException:
                        with self._fetch_lock:
                            self._fetch_pending.pop(arg, None)
                        raise
            except (HTTPError, OSError, ValueError, TimeoutError, http.client.HTTPException):
                conn.close()
                self._results.put(("offline", None))
            except Exception as e:  # never kill the worker
                print("online worker error:", e)
                conn.close()
                self._results.put(("offline", None))

    def _do_account(self, conn, kind, arg):
        s = self.save
        if kind == "restore":
            try:
                r = conn.request("POST", "/api/cloud/restore", {"code": arg})
                self._results.put(("restored", r))
            except HTTPError as e:
                self._results.put(("restore_fail", "limit" if e.code == 429 else "unknown"))
            except (OSError, ValueError, http.client.HTTPException):
                conn.close()
                self._results.put(("restore_fail", "offline"))
            return
        try:
            if not self._registered:
                self._do_register(conn)
            ts = int(time.time() + self._clock_offset)
            if kind == "code":
                r = conn.request("POST", "/api/cloud/code", {"player_id": s.player_id, "ts": ts,
                                                            "sig": _sign_msg(s.player_secret, f"{s.player_id}|code|{ts}")})
                self._results.put(("code", r.get("code", "")))
                return
            with self._cloud_lock:
                blob, self._cloud_blob = self._cloud_blob, None
            if blob:
                digest = hashlib.sha256(blob.encode()).hexdigest()
                conn.request("POST", "/api/cloud/save", {"player_id": s.player_id, "ts": ts, "data": blob,
                                                         "sig": _sign_msg(s.player_secret, f"{s.player_id}|save|{ts}|{digest}")})
        except HTTPError as e:
            if kind == "code":
                self._results.put(("code_fail", "limit" if e.code == 429 else "error"))
            elif e.code in (408, 429) or e.code >= 500:
                s.cloud_dirty = True                        # try again with the next scheduled upload
        except (OSError, ValueError, http.client.HTTPException):
            conn.close()
            if kind == "code":
                self._results.put(("code_fail", "offline"))
            else:
                s.cloud_dirty = True

    def _do_google(self, conn, kind, token):
        s = self.save
        mode = "link" if kind == "glink" else "restore"
        try:
            if kind == "glink":
                if not self._registered:
                    self._do_register(conn)
                ts = int(time.time() + self._clock_offset)
                digest = hashlib.sha256(token.encode()).hexdigest()
                r = conn.request("POST", "/api/account/google/link", {
                    "player_id": s.player_id, "ts": ts, "id_token": token,
                    "sig": _sign_msg(s.player_secret, f"{s.player_id}|glink|{ts}|{digest}")})
                self._results.put(("google", {"state": "ok", "mode": mode, "email": r.get("email", "")}))
            else:
                r = conn.request("POST", "/api/account/google/restore", {"id_token": token})
                self._results.put(("google", {"state": "ok", "mode": mode, "payload": r, "email": r.get("email", "")}))
        except HTTPError as e:
            err = self._err(e)
            reason = {409: "taken", 404: "not_linked", 401: "bad_token", 429: "limit", 503: "unavailable"}.get(e.code, "error")
            self._results.put(("google", {"state": "fail", "mode": mode, "reason": reason, "email": err.get("email", "")}))
        except (OSError, ValueError, http.client.HTTPException):
            conn.close()
            self._results.put(("google", {"state": "fail", "mode": mode, "reason": "offline"}))

    def _wallet_req(self, conn, op, key, ref, extra):
        s = self.save
        ts = int(time.time() + self._clock_offset)
        body = {"player_id": s.player_id, "ts": ts, "op": op, "ref": ref,
                "sig": _sign_msg(s.player_secret, f"{s.player_id}|wallet|{ts}|{op}|{key}|{ref}")}
        body.update(extra)
        return conn.request("POST", "/api/wallet", body)

    @staticmethod
    def _err(e):
        try:
            return json.loads(e.body.decode())
        except Exception:
            return {}

    def _do_wallet(self, conn):
        s = self.save
        with self._wallet_lock:
            self._wallet_queued = False
        try:
            if not self._registered:
                self._do_register(conn)
            if not self._wallet_open:
                local = 0 if s.data.get("wallet_synced") else max(0, int(s.data.get("diamonds", 0)) - s.pending_earnings())
                r = self._wallet_req(conn, "sync", str(local), "", {"local": local})
                self._wallet_open = True
                self._results.put(("wallet", {"balance": r["balance"], "gift": r.get("gift", 0),
                                              "skins": r.get("skins", []), "account": r.get("account", "")}))
            for op in list(s.data.get("wallet_ops", [])):
                kind, ref = op.get("kind", ""), op.get("ref", "")
                try:
                    r = self._wallet_req(conn, "earn", kind, ref, {"kind": kind})
                    self._results.put(("earned", (kind, ref, r.get("balance"))))
                except HTTPError as e:
                    err = self._err(e)
                    if e.code in (408, 409) or e.code >= 500 and e.code != 501 or err.get("error") == "slow down":
                        raise                                   # temporary: try again later
                    self._results.put(("earned", (kind, ref, err.get("balance"))))   # refused for good: take it back
            for iap in list(s.data.get("iap_pending", [])):
                product, token = iap.get("product", ""), iap.get("token", "")
                ref = hashlib.sha256(token.encode()).hexdigest()
                try:
                    r = self._wallet_req(conn, "purchase", product, ref, {"product": product, "token": token})
                    if r.get("pending"):                    # 202: paid by a slow method, not settled yet
                        self._results.put(("purchase", (product, token, "wait", r)))
                    else:
                        self._results.put(("purchase", (product, token, "ok", r)))
                except HTTPError as e:
                    err = self._err(e)
                    if e.code in (400, 403, 410) or (e.code == 409 and err.get("error") != "sync first"):
                        self._results.put(("purchase", (product, token, "rejected", err)))
                    elif e.code in (408, 429) or e.code >= 500 or e.code == 409:
                        self._results.put(("purchase", (product, token, "wait", err)))   # kept, retried later
                    else:
                        raise
            while True:
                with self._wallet_lock:
                    if not self._spends:
                        break
                    item, ref, on_done = self._spends[0]
                try:
                    r = self._wallet_req(conn, "spend", item, ref, {"item": item})
                    res = (on_done, True, "", r.get("balance"))
                except HTTPError as e:
                    err = self._err(e)
                    if e.code in (408, 409, 429) or e.code >= 500:
                        raise
                    res = (on_done, False, "insufficient" if e.code == 402 else "error", err.get("balance"))
                with self._wallet_lock:
                    self._spends.pop(0)
                self._results.put(("spent", res))
        except (HTTPError, OSError, ValueError, TimeoutError, http.client.HTTPException):
            # no answer: nothing waiting may hang - every pending purchase fails as "offline" (the money stays)
            with self._wallet_lock:
                waiting, self._spends = self._spends, []
            for _item, _ref, on_done in waiting:
                self._results.put(("spent", (on_done, False, "offline", None)))
            raise

    def _do_register(self, conn):
        s = self.save
        try:
            t0 = time.time()
            srv = conn.request("GET", "/api/health").get("time")
            if srv:
                self._clock_offset = float(srv) - (t0 + time.time()) / 2.0
        except (HTTPError, OSError, ValueError, http.client.HTTPException):
            pass
        r = conn.request("POST", "/api/register", {
            "player_id": s.player_id, "secret": s.player_secret,
            "name": s.player_name, "country": s.player_country})
        if r.get("ok"):
            self._registered = True
            self._fetch_my_bests(conn)
            self._send_reports(conn)

    def _send_reports(self, conn):
        """A crash on the last run (fault_last.log: native crash stack, crash.log: Python traceback) goes to the
        developer once - players can't reach these files on a phone."""
        import paths
        import sys as _sys
        from version import __version__
        plat = "ios" if paths.is_ios() else ("android" if paths.is_android() else _sys.platform)
        for name, kind in (("fault_last.log", "fault"), ("crash.log", "crash")):
            path = os.path.join(paths.user_dir(), name)
            try:
                if not os.path.isfile(path) or os.path.getsize(path) == 0:
                    continue
                with open(path, encoding="utf-8", errors="replace") as f:
                    text = f.read()[-12000:]
                r = conn.request("POST", "/api/report", {"player_id": self.save.player_id, "kind": kind,
                                                         "platform": plat, "version": __version__, "text": text})
                if r.get("ok"):
                    os.replace(path, path + ".sent")
            except Exception as e:
                print("report not sent:", e)

    def _fetch_my_bests(self, conn):
        """The server's verified best of every level: the game shows the same level scores as the ranking."""
        s = self.save
        try:
            ts = int(time.time() + self._clock_offset)
            r = conn.request("POST", "/api/bests", {"player_id": s.player_id, "ts": ts,
                                                    "sig": _sign_msg(s.player_secret, f"{s.player_id}|bests|{ts}")})
            self._results.put(("bests", r.get("bests", [])))
        except (HTTPError, OSError, ValueError, http.client.HTTPException):
            pass

    def _do_flush(self, conn):
        s = self.save
        if not s.data.get("pending_runs"):
            return
        if not self._registered:
            self._do_register(conn)
        for run in list(s.data.get("pending_runs", [])):
            ts = int(time.time() + self._clock_offset)
            body = {"player_id": s.player_id, "level": run["level"], "ts": ts, "taps": run["taps"], "lvl": run.get("lvl", ""),
                    "sig": _sign(s.player_secret, s.player_id, run["level"], ts, run["taps"])}
            helps = run.get("assists") or []
            if helps:
                # revives / bought shields: replayed by the server and checked against what was paid (signed too)
                key = ",".join(f"{int(a[0])}{a[1]}" for a in helps)
                body["assists"] = [[int(a[0]), str(a[1])] for a in helps]
                body["asig"] = _sign_msg(s.player_secret, f"{s.player_id}|{run['level']}|{ts}|"
                                         f"{','.join(str(int(t)) for t in run['taps'])}|{key}")
            try:
                r = conn.request("POST", "/api/submit", body, timeout=SUBMIT_TIMEOUT)
            except HTTPError as e:
                # a definitive rejection: drop it so it is not retried forever
                try:
                    err = json.loads(e.body.decode())
                except Exception:
                    err = {"error": str(e.code)}
                if 400 <= e.code < 500 and e.code not in (408, 429):
                    self._results.put(("submit", {"ok": False, "rejected": True, "level": run["level"], "bg": run.get("bg", False),
                                                  "error": err.get("error", "rejected")}))
                    s.drop_run(run["level"])
                    continue
                raise
            r["level"] = run["level"]
            r["bg"] = run.get("bg", False)
            self._results.put(("submit", r))

    def _do_endless(self, conn):
        s = self.save
        runs = list(s.data.get("endless_runs", []))
        if not runs:
            return
        if not self._registered:
            self._do_register(conn)
        import endless as E
        for run in runs:
            ts = int(time.time() + self._clock_offset)
            helps = run.get("assists") or []
            digest = hashlib.sha256(E.assist_digest(run["taps"], helps).encode()).hexdigest()
            nonce = run.get("nonce", "")
            body = {"player_id": s.player_id, "week": run["week"], "nonce": nonce, "taps": run["taps"], "end": run["end"],
                    "ts": ts, "v": E.ENDLESS_VERSION, "pool": E.pool_digest(),
                    "sig": _sign_msg(s.player_secret, f"{s.player_id}|endless|{run['week']}|{nonce}|{run['end']}|{ts}|{digest}")}
            if helps:
                body["assists"] = helps
            try:
                r = conn.request("POST", "/api/endless/submit", body, timeout=SUBMIT_TIMEOUT)
            except HTTPError as e:
                if 400 <= e.code < 500 and e.code not in (408, 429):
                    err = self._err(e)
                    self._results.put(("endless", {"ok": False, "rejected": True, "id": run["id"],
                                                   "error": err.get("error", "rejected")}))
                    continue
                raise
            r["id"] = run["id"]
            self._results.put(("endless", r))

    def _do_fetch(self, conn, scope, limit):
        s = self.save
        if scope == "endless":
            import endless as E
            week = E.week_of(time.time() + self._clock_offset)
            q = urllib.parse.urlencode({"week": week, "limit": limit, "player_id": s.player_id})
            r = conn.request("GET", "/api/endless/board?" + q)
            r["week"] = week
            self._results.put(("board", (scope, r)))
            return
        q = urllib.parse.urlencode({"scope": scope, "limit": limit, "player_id": s.player_id,
                                    "country": s.player_country})
        r = conn.request("GET", "/api/leaderboard?" + q)
        self._results.put(("board", (scope, r)))
