"""Client of the shared weekly goal and the weekly featured level (1.0.9; server: supabase/functions/scores/crowd.ts).

Own worker thread and connection, so it never waits behind a score submit. The server decides everything (the goal, the
tiers, who contributed, what is paid); this file only asks and shows. The game calls crowd.poll() once per frame, which
runs the callbacks on the main thread.
"""
import http.client
import queue
import threading
import time

from online import HTTPError, _Connection, _sign_msg


class CrowdClient:
    def __init__(self, online):
        self.online = online
        self.data = None               # last server answer: {"week", "goal", "total", "mine", "tiers": [...], "wlevel": {...}}
        self.state = "idle"            # idle | loading | ok | offline
        self.fetched = 0.0
        self._busy = False
        self._jobs = queue.Queue()
        self._results = queue.Queue()
        self._started = False

    # ------------------------------------------------------------------ public
    def refresh(self, max_age=0.0):
        """Ask for the status (not more often than every `max_age` seconds)."""
        if self._busy or (max_age and self.data is not None and time.time() - self.fetched < max_age):
            return
        self._busy = True
        if self.data is None:
            self.state = "loading"
        self._put(("status", "", None))

    def claim(self, tier, on_done=None):
        """Claim a goal tier (1..3) of this week; on_done(reply)."""
        self._put(("claim", str(int(tier)), on_done))

    def claim_level(self, on_done=None):
        """Claim the reward of this week's featured level (after clearing it)."""
        self._put(("wclaim", "", on_done))

    def tier_reached(self):
        """Highest tier the whole player base has reached this week (0..3)."""
        n = 0
        for t in (self.data or {}).get("tiers", []):
            if t.get("reached"):
                n = max(n, int(t.get("tier", 0)))
        return n

    def claimable(self):
        """Rewards waiting for me: claimable goal tiers + the featured level's reward."""
        d = self.data or {}
        n = sum(1 for t in d.get("tiers", []) if t.get("claimable"))
        w = d.get("wlevel") or {}
        return n + (1 if w.get("cleared") and not w.get("claimed") else 0)

    # ------------------------------------------------------------------ plumbing
    def _put(self, job):
        if not self.online.enabled:
            self._busy = False
            if job[2]:
                job[2]({"ok": False, "error": "offline"})
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
                    print("crowd callback error:", e)

    def _apply(self, op, r):
        if op == "status":
            self._busy = False
        if isinstance(r, dict) and r.get("ok") and "tiers" in r:
            self.data = r
            self.state = "ok"
            self.fetched = time.time()
            bal = r.get("balance")
            if op in ("claim", "wclaim") and bal is not None and hasattr(self.online.save, "set_server_balance"):
                self.online.save.set_server_balance(int(bal))
        elif self.data is None:
            self.state = "offline" if (isinstance(r, dict) and r.get("error") == "offline") else "ok"

    def _worker(self):
        conn = _Connection(self.online.url)
        while True:
            op, arg, cb = self._jobs.get()
            self._results.put((op, self._call(conn, op, arg), cb))

    def _call(self, conn, op, arg):
        s, on = self.online.save, self.online
        try:
            if not on._registered:
                on._do_register(conn)
        except Exception:
            pass
        for attempt in (0, 1):
            ts = int(time.time() + on._clock_offset)
            body = {"player_id": s.player_id, "ts": ts, "op": op, "arg": arg,
                    "sig": _sign_msg(s.player_secret, f"{s.player_id}|crowd|{ts}|{op}|{arg}|")}
            try:
                r = conn.request("POST", "/api/crowd", body, timeout=10)
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
