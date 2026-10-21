"""Client of the shop extras (server: supabase/functions/scores/shopx.ts, route /api/shop): the weekly showcase, consumable
packs, prestige frames / titles, the weekly Star Market and the Star Chest.

Same plumbing as the star client (ranked_online.RankedClient: own worker thread, signed requests, callbacks run
on the main thread from poll()). The server prices and limits everything and answers with the new balances; this file
only asks, mirrors the answers into the save (diamonds, stars, shield / revive stock, owned prestige) and shows them.
A request that got no answer is repeated with the SAME ref, so the server never charges it twice.
"""
import secrets

from ranked_online import RankedClient

_ACTIONS = ("buy", "mkt", "chest", "equip")


class ShopClient(RankedClient):
    ROUTE, SIGN = "/api/shop", "shop"

    def __init__(self, online):
        super().__init__(online)
        self.view = None                       # last "view" answer
        self.state = {"view": "idle"}
        self.fetched = {"view": 0.0}
        self._refs = {}                        # what was asked -> the retry ref of a request that has no answer yet

    # ------------------------------------------------------------------ public
    def refresh(self, max_age=0.0):
        import time
        if "view" in self._busy:
            return
        if max_age and self.view is not None and time.time() - self.fetched["view"] < max_age:
            return
        self._busy.add("view")
        if self.view is None:
            self.state["view"] = "loading"
        self._put(("view", "", None, None))

    def act(self, op, arg, on_done=None):
        """op "buy" (arg "pack:<id>" | "frame:<id>" | "title:<id>") | "mkt" (arg "<item>") | "chest" | "equip"
        (arg "frame:<id>" / "title:<id>" / "frame:"). on_done(reply) with reply["ok"]."""
        key = f"{op}|{arg}"
        retry = key in self._refs                      # the earlier try got no answer: a "dup" now still has to be delivered
        ref = self._refs.get(key) or secrets.token_hex(12)
        self._refs[key] = ref
        wire = {"buy": f"{arg}:{ref}", "mkt": f"{arg}:{ref}", "chest": ref, "equip": arg}[op]

        def done(r, _key=key, _cb=on_done):
            if isinstance(r, dict) and r.get("error") != "offline":
                self._refs.pop(_key, None)             # answered (ok or refused for good): the next tap is a new purchase
            if isinstance(r, dict) and r.get("ok") and (retry or not r.get("dup")):
                self._deliver(op, r)
            if _cb:
                _cb(r)
            if isinstance(r, dict) and r.get("ok"):
                self.refresh()                         # owned items, limits and stock left come from the server
        self._put((op, wire, None, done))

    # ------------------------------------------------------------------ plumbing
    def _apply(self, op, r):
        import time
        self._busy.discard(op)
        ok = isinstance(r, dict) and r.get("ok")
        sm = self.online.save
        if isinstance(r, dict):
            if r.get("balance") is not None and hasattr(sm, "set_server_balance"):
                sm.set_server_balance(int(r["balance"]))
            if r.get("stars") is not None and hasattr(sm, "set_star_balance"):
                sm.set_star_balance(int(r["stars"]))
        if not ok:
            if op == "view" and self.view is None:
                # offline = no connection; unavailable = the server answered but has no shop yet (older server version)
                self.state["view"] = ("offline" if r.get("error") == "offline" else
                                      "unavailable" if r.get("code") in (404, 410, 501) else "ok") if isinstance(r, dict) else "ok"
            return
        if op == "view":
            self.view, self.state["view"], self.fetched["view"] = r, "ok", time.time()
            p = r.get("prestige") or {}
            sm.set_prestige(p.get("owned"), p.get("frame"), p.get("title"))
            return
        if op == "equip":
            sm.set_prestige(frame=r.get("frame", ""), title=r.get("title", ""))
        self.fetched["view"] = 0.0                     # the next refresh() fetches fresh limits

    def _deliver(self, op, r):
        """What a purchase brought goes into the local stock (the server logged the matching paid-help rows)."""
        sm = self.online.save
        grant = r.get("grant") or r.get("reward") or ({"kind": r.get("item"), "payload": r.get("units")} if op == "buy" else None)
        if not grant:
            return
        kind, n = grant.get("kind"), grant.get("payload")
        if kind == "shield":
            sm.add_shield(int(n))
        elif kind == "revive":
            sm.add_revive(int(n))
        elif kind in ("frame", "title") or (isinstance(n, str) and n.startswith(("frame_", "title_"))):
            sm.set_prestige(owned=sm.prestige_owned + [str(n)])
