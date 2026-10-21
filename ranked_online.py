"""Client of the star wallet and the daily level (1.0.9; server:
supabase/functions/scores/ranked.ts).

Own worker thread and connection, like crowd_online. The server decides everything (star balance, what the road and the
today's level, the replay check of the daily run); this file only asks and
shows. The game calls ranked.poll() once per frame, which runs the callbacks on the main thread.
"""
import hashlib
import http.client
import queue
import threading
import time

from online import HTTPError, _Connection, _sign_msg


class RankedClient:
    ROUTE, SIGN = "/api/ranked", "ranked"      # shop_online.ShopClient talks to /api/shop the same way
    def __init__(self, online):
        self.online = online
        self.stars = None              # last "stars" answer: {"stars", "earned", "shield_cost", ...}
        self.daily = None              # last "daily" answer
        self.state = {"stars": "idle", "daily": "idle"}      # idle | loading | ok | offline
        self.fetched = {"stars": 0.0, "daily": 0.0}
        self._busy = set()
        self._jobs = queue.Queue()
        self._results = queue.Queue()
        self._started = False

    # ------------------------------------------------------------------ public
    def refresh(self, which, max_age=0.0):
        """Ask for "stars" | "daily" (not more often than every `max_age` seconds)."""
        if which in self._busy:
            return
        if max_age and getattr(self, which) is not None and time.time() - self.fetched[which] < max_age:
            return
        self._busy.add(which)
        if getattr(self, which) is None:
            self.state[which] = "loading"
        self._put((which, "", None, None))

    def buy_shield(self, on_done=None):
        """One-attempt start shield for stars; on_done(reply) - the caller adds it to the shield stock when ok."""
        self._put(("spend", "shield:" + hashlib.sha256(str(time.time()).encode()).hexdigest()[:24], None, on_done))

    def buy_skin(self, skin_id, on_done=None):
        self._put(("spend", f"skin:{skin_id}", None, on_done))

    def daily_start(self, on_done=None):
        """Uses today's one try (server side). on_done(reply): reply["first"] is True only for the very first start."""
        self._put(("daily_start", "", None, on_done))

    def daily_submit(self, taps, digest, on_done=None):
        self._put(("daily_submit", "", {"taps": [int(x) for x in taps], "lvl": digest}, on_done))

    # ------------------------------------------------------------------ plumbing
    def _put(self, job):
        cb = job[3]
        if not self.online.enabled:
            self._busy.discard(job[0])
            if cb:
                cb({"ok": False, "error": "offline"})
            return
        if not self._started:
            self._started = True
            threading.Thread(target=self._worker, daemon=True).start()
        self._jobs.put(job)

    def poll(self):
        while True:
            try:
                op, reply, cb = self._results.get_nowait()
            except queue.Empty:
                return
            self._apply(op, reply)
            if cb is not None:
                try:
                    cb(reply)
                except Exception as e:                      # a screen's callback must never break the frame
                    print("ranked callback error:", e)

    def _apply(self, op, r):
        self._busy.discard(op)
        ok = isinstance(r, dict) and r.get("ok")
        if not ok:
            for k in self.state:
                if k == op and getattr(self, k) is None:
                    self.state[k] = "offline" if (isinstance(r, dict) and r.get("error") == "offline") else "ok"
            return
        now = time.time()
        sm = self.online.save
        if "shield_cost" in r:
            self.stars, self.state["stars"], self.fetched["stars"] = r, "ok", now
            if hasattr(sm, "set_star_balance"):
                sm.set_star_balance(int(r.get("stars", 0)), int(r.get("earned", 0)))
        if "board" in r and "level" in r:
            self.daily, self.state["daily"], self.fetched["daily"] = r, "ok", now
        if op == "spend" and "stars" in r and hasattr(sm, "set_star_balance") and "shield_cost" not in r:
            sm.set_star_balance(int(r["stars"]))
        if r.get("balance") is not None and hasattr(sm, "set_server_balance"):
            sm.set_server_balance(int(r["balance"]))

    def _worker(self):
        conn = _Connection(self.online.url)
        while True:
            op, arg, extra, cb = self._jobs.get()
            wire = {"stars": "stars", "daily": "daily"}.get(op, op)
            self._results.put((op, self._call(conn, wire, arg, extra), cb))

    def _call(self, conn, op, arg, extra):
        s, on = self.online.save, self.online
        try:
            if not on._registered:
                on._do_register(conn)
        except Exception:
            pass
        digest = hashlib.sha256(",".join(str(x) for x in extra["taps"]).encode()).hexdigest() if extra else ""
        for attempt in (0, 1):
            ts = int(time.time() + on._clock_offset)
            body = {"player_id": s.player_id, "ts": ts, "op": op, "arg": arg,
                    "sig": _sign_msg(s.player_secret, f"{s.player_id}|{self.SIGN}|{ts}|{op}|{arg}|{digest}")}
            if extra:
                body.update(extra)
            try:
                r = conn.request("POST", self.ROUTE, body, timeout=15)
            except HTTPError as e:
                err = on._err(e)
                if e.code >= 500 or e.code == 408:
                    return {"ok": False, "error": "offline"}
                return {"ok": False, "error": err.get("error", "error"), "code": e.code}
            except (OSError, ValueError, TimeoutError, http.client.HTTPException):
                if attempt == 0:
                    conn.close()
                    continue
                return {"ok": False, "error": "offline"}
            return r if isinstance(r, dict) else {"ok": False, "error": "error"}
        return {"ok": False, "error": "offline"}
