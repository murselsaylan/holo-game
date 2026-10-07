import os
import json
import time
import uuid
import secrets
import shutil
import datetime
import threading

import locales
import paths
import config
import skin_catalog
import daily_missions as dm
import weekly_missions as wm

SAVE_FILE = os.path.join(paths.user_dir(), "save_data.json")
SAVE_VERSION = 2
from sim import MAX_LEVELS, LevelData  # noqa: E402  (the level count lives in sim.py)
from endless import UNLOCK_LEVEL as ENDLESS_UNLOCK  # noqa: E402
from arena import UNLOCK_LEVEL as ARENA_UNLOCK  # noqa: E402

COUNTRIES = [
    {"code": "TR", "flag": "🇹🇷", "name": "Türkiye", "color": (235, 45, 55)},
    {"code": "US", "flag": "🇺🇸", "name": "USA", "color": (50, 100, 220)},
    {"code": "DE", "flag": "🇩🇪", "name": "Germany", "color": (255, 200, 30)},
    {"code": "GB", "flag": "🇬🇧", "name": "UK", "color": (210, 45, 65)},
    {"code": "JP", "flag": "🇯🇵", "name": "Japan", "color": (245, 60, 80)},
    {"code": "KR", "flag": "🇰🇷", "name": "Korea", "color": (50, 140, 240)},
    {"code": "FR", "flag": "🇫🇷", "name": "France", "color": (45, 85, 225)},
    {"code": "BR", "flag": "🇧🇷", "name": "Brazil", "color": (40, 200, 80)},
    {"code": "CA", "flag": "🇨🇦", "name": "Canada", "color": (235, 50, 50)},
    {"code": "AU", "flag": "🇦🇺", "name": "Australia", "color": (35, 85, 190)},
    {"code": "IT", "flag": "🇮🇹", "name": "Italy", "color": (50, 200, 90)},
    {"code": "ES", "flag": "🇪🇸", "name": "Spain", "color": (245, 185, 30)},
    {"code": "NL", "flag": "🇳🇱", "name": "Netherlands", "color": (255, 125, 20)},
    {"code": "AZ", "flag": "🇦🇿", "name": "Azerbaijan", "color": (0, 185, 235)},
    {"code": "SE", "flag": "🇸🇪", "name": "Sweden", "color": (35, 125, 225)},
    {"code": "GX", "flag": "🌌", "name": "Cosmos", "color": (170, 65, 255)},
]

DEFAULT_SETTINGS = {
    "music_volume": 0.6,
    "sfx_volume": 0.8,
    "screen_shake": True,
    "particles": True,
    "fullscreen": False,
    "language": "en",
    "online": True,
    "ghost_race": True,                  # race a ghost (the world #1 of the level, else my best) - on (1.0.7)
    "haptics": True,
}


def _merge_settings(saved):
    """Saved settings over the defaults. 1.0.7 turns the ghost race on once for everybody (it was opt-in before,
    so most saves carry ghost_race False only because that was the default); later choices are kept."""
    merged = dict(DEFAULT_SETTINGS)
    merged.update(saved if isinstance(saved, dict) else {})
    if not merged.get("ghost_on_107"):
        merged["ghost_race"] = True
        merged["ghost_on_107"] = True
    return merged


def _default_save():
    return {
        "save_version": SAVE_VERSION,
        "player_id": uuid.uuid4().hex,
        "player_secret": secrets.token_hex(24),
        "player_name": "",
        "player_country": "TR",
        "is_profile_set": False,
        "campaign_level": 1,
        "level_stats": {},          # "12": {stars, best_score, best_time, best_swaps, rank}
        "unlocked_skins": ["neon_pulse"],
        "equipped_skin": "neon_pulse",
        "diamonds": 20,
        "last_ad_watch": 0.0,
        "pending_runs": [],         # proofs not yet accepted by the server
        "settings": dict(DEFAULT_SETTINGS),
    }


class SaveManager:
    def __init__(self):
        self._lock = threading.RLock()
        self.cloud_dirty = False        # changed since the last cloud copy (see export_cloud)
        self.data = self._load()
        self._check_skin_unlocks()
        locales.set_language(self.language)

    # ------------------------------------------------------------------ io
    def _load(self):
        if not os.path.exists(SAVE_FILE):
            return _default_save()
        try:
            with open(SAVE_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
        except Exception as e:
            print("Save file load warning:", e)
            try:
                shutil.copy(SAVE_FILE, SAVE_FILE + ".corrupt")
            except Exception:
                pass
            return _default_save()

        result = _default_save()
        if loaded.get("save_version", 1) < SAVE_VERSION:
            # v1 -> v2: levels were redesigned, so campaign progress restarts; keep identity, skins and settings.
            try:
                shutil.copy(SAVE_FILE, os.path.join(os.path.dirname(SAVE_FILE), "save_data.v1.backup.json"))
            except Exception:
                pass
            for k in ("player_name", "player_country", "is_profile_set", "unlocked_skins", "equipped_skin"):
                if k in loaded:
                    result[k] = loaded[k]
        else:
            result.update(loaded)
        result["settings"] = _merge_settings(loaded.get("settings", {}))
        result["save_version"] = SAVE_VERSION
        return result

    rev = 0                          # bumped on every change that is saved: cached screens redraw when it moves

    def save(self):
        self.rev += 1
        try:
            with self._lock:
                tmp = SAVE_FILE + ".tmp"
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(self.data, f, indent=1, ensure_ascii=False)
                os.replace(tmp, SAVE_FILE)
            self.cloud_dirty = True
        except Exception as e:
            print("Save file write error:", e)

    # ------------------------------------------------------------------ identity
    @property
    def player_id(self):
        return self.data["player_id"]

    @property
    def player_secret(self):
        return self.data["player_secret"]

    @property
    def player_name(self):
        val = self.data.get("player_name", "").strip()
        return val if val else "PİLOT"

    @player_name.setter
    def player_name(self, val):
        self.data["player_name"] = str(val).strip()[:12]
        self.save()

    @property
    def player_country(self):
        return self.data.get("player_country", "TR")

    @player_country.setter
    def player_country(self, val):
        self.data["player_country"] = str(val).strip()[:4]
        self.save()

    @property
    def is_profile_set(self):
        return self.data.get("is_profile_set", False)

    @is_profile_set.setter
    def is_profile_set(self, val):
        self.data["is_profile_set"] = bool(val)
        self.save()

    # ------------------------------------------------------------------ campaign
    @property
    def stats(self):
        return self.data.setdefault("level_stats", {})

    @property
    def levels_cleared(self):
        return len(self.stats)

    @property
    def highest_cleared(self):
        return max((int(k) for k in self.stats), default=0)

    @property
    def unlocked_level(self):
        if config.dev_unlock_all():
            return MAX_LEVELS
        return min(MAX_LEVELS, self.highest_cleared + 1)

    @property
    def campaign_level(self):
        return min(MAX_LEVELS, max(1, self.data.get("campaign_level", 1)))

    @campaign_level.setter
    def campaign_level(self, lvl):
        self.data["campaign_level"] = max(1, min(MAX_LEVELS, lvl))
        self.save()

    @property
    def total_score(self):
        return sum(s.get("best_score", 0) for s in self.stats.values())

    # ------------------------------------------------------------------ endless climb
    @property
    def endless_unlocked(self):
        return config.dev_unlock_all() or self.highest_cleared >= ENDLESS_UNLOCK

    @property
    def endless(self):
        e = self.data.get("endless")
        if not isinstance(e, dict):
            e = self.data["endless"] = {"best_all": 0, "week": "", "week_best": 0, "runs": 0}
        return e

    def endless_week_best(self, week):
        e = self.endless
        return int(e.get("week_best", 0)) if e.get("week") == week else 0

    def record_endless(self, week, points, metres=0, stars=0):
        """A finished climb (points = height + stars, what the ranking sorts by). Its stars go to the star wallet.
        Returns True when it is this week's new best."""
        with self._lock:
            e = self.endless
            if e.get("v") != 2:                        # endless v1 kept metres here - start the points records afresh
                e.update(v=2, week_best=0, best_all=0)
            if e.get("week") != week:
                e["week"], e["week_best"] = week, 0
            if points > int(e.get("week_best", 0)):
                e["week_best"] = int(points)
            new_best = points > int(e.get("best_all", 0))          # the ranking is all-time (1.0.6)
            e["best_all"] = max(int(e.get("best_all", 0)), int(points))
            e["best_m"] = max(int(e.get("best_m", 0)), int(metres))
            e["runs"] = int(e.get("runs", 0)) + 1
        self.save()
        self.add_star_coins(stars)
        return new_best

    def queue_endless(self, run):
        """A climb's proof for the server ({id, week, taps, end}); the newest few are kept while offline."""
        with self._lock:
            q = self.data.setdefault("endless_runs", [])
            q.append(run)
            del q[:-5]
        self.save()

    def drop_endless(self, rid):
        with self._lock:
            q = self.data.setdefault("endless_runs", [])
            q[:] = [r for r in q if r.get("id") != rid]
        self.save()

    # ------------------------------------------------------------------ arena (survival)
    @property
    def arena_unlocked(self):
        return config.dev_unlock_all() or self.highest_cleared >= ARENA_UNLOCK

    @property
    def arena(self):
        a = self.data.get("arena")
        if not isinstance(a, dict):
            a = self.data["arena"] = {"best": 0, "best_secs": 0, "runs": 0}
        return a

    def record_arena(self, points, secs, stars=0):
        """A finished arena run. Its stars go to the star wallet. Returns True on a new best."""
        with self._lock:
            a = self.arena
            new_best = points > int(a.get("best", 0))
            a["best"] = max(int(a.get("best", 0)), int(points))
            a["best_secs"] = max(int(a.get("best_secs", 0)), int(secs))
            a["runs"] = int(a.get("runs", 0)) + 1
        self.save()
        self.add_star_coins(stars)
        return new_best

    # ---- stars collected in the endless climb: spent on the Yıldız Avcısı skins (kept in the save / cloud copy)
    @property
    def star_coins(self):
        return int(self.data.get("star_coins", 0))

    def add_star_coins(self, n):
        n = int(n)
        if n <= 0:
            return self.star_coins
        with self._lock:
            self.data["star_coins"] = self.star_coins + n
            self.data["star_coins_total"] = int(self.data.get("star_coins_total", 0)) + n
        self.save()
        return self.star_coins

    def spend_star_coins(self, n):
        n = int(n)
        with self._lock:
            if self.star_coins < n:
                return False
            self.data["star_coins"] = self.star_coins - n
        self.save()
        return True

    def get_total_stars(self):
        return sum(s.get("stars", 0) for s in self.stats.values())

    def get_level_stars(self, level_id):
        return self.stats.get(str(level_id), {}).get("stars", 0)

    def get_level_best_time(self, level_id):
        return self.stats.get(str(level_id), {}).get("best_time")

    def get_level_best_swaps(self, level_id):
        return self.stats.get(str(level_id), {}).get("best_swaps")

    def get_best_taps(self, level_id):
        return self.stats.get(str(level_id), {}).get("best_taps")

    @property
    def unranked_levels(self):
        """Levels cleared on this phone that the ranking has no verified run of (see sync_bests)."""
        return list(self.data.get("unranked", []))

    def level_attempts(self, level_id):
        """The try counter of a level (kept until the level is cleared, across leaving it and restarts)."""
        return max(1, int(self.data.get("attempts", {}).get(str(level_id), 1)))

    def set_level_attempts(self, level_id, n):
        a = self.data.setdefault("attempts", {})
        if n <= 1:
            a.pop(str(level_id), None)
        else:
            a[str(level_id)] = int(n)
        self.save()

    def get_level_best_score(self, level_id):
        return self.stats.get(str(level_id), {}).get("best_score", 0)

    def get_best_assists(self, level_id):
        return self.stats.get(str(level_id), {}).get("best_assists") or []

    def record_level_clear(self, level_id, result, taps=None, assists=None):
        """`result` comes from sim.compute_result. Returns True when the level score is a new best.
        The best run's taps (and its paid help, if any) are kept: the ghost replays clean ones, and a best the server
        never recorded can be sent again (sync_bests)."""
        key = str(level_id)
        st = self.stats.setdefault(key, {})
        improved = result["level_total"] > st.get("best_score", 0)
        st["stars"] = max(st.get("stars", 0), result["stars"])
        if improved:
            st["best_score"] = result["level_total"]
            st["rank"] = result["rank"]
            if taps:
                st["best_taps"] = [int(x) for x in taps]
                if assists:
                    st["best_assists"] = [[int(a[0]), str(a[1])] for a in assists]
                else:
                    st.pop("best_assists", None)
        if st.get("best_time") is None or result["time"] < st["best_time"]:
            st["best_time"] = round(result["time"], 2)
        if st.get("best_swaps") is None or result["swaps"] < st["best_swaps"]:
            st["best_swaps"] = result["swaps"]
        if level_id >= self.data.get("campaign_level", 1):
            self.data["campaign_level"] = min(MAX_LEVELS, level_id + 1)
        self._check_skin_unlocks()
        self.save()
        return improved

    def sync_bests(self, rows):
        """Take the server's verified level bests (same scoring the ranking uses) as this device's level scores.

        A clean clear the server never recorded (sent while the server was on another version, or lost offline) or
        recorded with fewer stars is queued again from its saved replay - once per level version, so a run the server
        refuses is not re-sent forever. Returns the number of runs queued."""
        changed = False
        resend = []
        with self._lock:
            stats = self.stats
            server = {}
            for b in rows or []:
                lv = int(b["level"])
                server[lv] = b
                st = stats.setdefault(str(lv), {})
                score, stars = int(b.get("score", 0)), int(b.get("stars", 0))
                if st.get("best_score") != score:
                    st["best_score"] = score
                    st["rank"] = str(b.get("rank", st.get("rank", "A")))
                    changed = True
                if stars > st.get("stars", 0):
                    st["stars"] = stars
                    changed = True
            tried = self.data.setdefault("resync_tried", {})
            queued = {r["level"] for r in self.data.get("pending_runs", [])}
            unranked = []
            for key, st in stats.items():
                lv = int(key)
                if not 1 <= lv <= MAX_LEVELS or lv in queued:
                    continue
                b = server.get(lv)
                if b is not None and int(b.get("stars", 0)) >= st.get("stars", 0):
                    continue
                taps = st.get("best_taps")
                if not taps:
                    # cleared on this phone but no replay was kept (older versions dropped runs with paid help):
                    # the ranking cannot count it until the level is cleared again
                    if b is None and st.get("best_score", 0) > 0:
                        unranked.append(lv)
                    continue
                resend.append((lv, taps, st.get("best_assists")))
            unranked.sort()
            if unranked != self.data.get("unranked", []):
                self.data["unranked"] = unranked
                changed = True
        n = 0
        for lv, taps, helps in resend:
            try:
                digest = LevelData.load(lv).digest
            except Exception:
                continue
            if self.data["resync_tried"].get(str(lv)) == digest:
                continue
            self.data["resync_tried"][str(lv)] = digest
            self.queue_run(lv, taps, digest, bg=True, assists=helps)
            n += 1
        if changed and not n:
            self.save()
        return n

    # ------------------------------------------------------------------ account recovery (cloud copy)
    def export_cloud(self):
        """The save as sent to the server for account recovery (the cached leaderboards are left out)."""
        with self._lock:
            d = {k: v for k, v in self.data.items() if k != "lb_cache"}
            return json.dumps(d, ensure_ascii=False, separators=(",", ":"))

    def import_cloud(self, payload):
        """Replace this device's save with a recovered account (server reply of /api/cloud/restore). Accounts without a
        cloud copy (from before 1.0.2) get their campaign rebuilt from their verified leaderboard bests."""
        result = _default_save()
        loaded = None
        try:
            loaded = json.loads(payload["data"]) if payload.get("data") else None
        except Exception:
            loaded = None
        if isinstance(loaded, dict):
            result.update(loaded)
            result["settings"] = _merge_settings(loaded.get("settings", {}))
        else:
            stats = {}
            for b in payload.get("bests", []):
                st = {"stars": int(b.get("stars", 0)), "best_score": int(b.get("score", 0)), "rank": str(b.get("rank", "A"))}
                if float(b.get("time", 0)) > 0:
                    st["best_time"] = round(float(b["time"]), 2)
                if int(b.get("swaps", 0)) > 0:
                    st["best_swaps"] = int(b["swaps"])
                stats[str(int(b["level"]))] = st
            result["level_stats"] = stats
            result["campaign_level"] = min(MAX_LEVELS, max((int(k) for k in stats), default=0) + 1)
            result["settings"] = dict(self.data.get("settings", DEFAULT_SETTINGS))
        result["player_id"] = str(payload["player_id"])
        result["player_secret"] = str(payload["secret"])
        result["player_name"] = str(payload.get("name") or result.get("player_name") or "PİLOT")
        result["player_country"] = str(payload.get("country") or result.get("player_country") or "GX")
        result["is_profile_set"] = True
        result["pending_runs"] = []
        result["endless_runs"] = []
        result["wallet_ops"] = []
        result["iap_pending"] = list(self.data.get("iap_pending", []))   # a purchase made on this phone still counts
        result["account_tag"] = ""
        result["wallet_synced"] = False          # the recovered account's balance comes from the server
        result["save_version"] = SAVE_VERSION
        with self._lock:
            self.data = result
        self._check_skin_unlocks()
        locales.set_language(self.language)
        self.save()

    def reset_campaign_run(self):
        self.data["campaign_level"] = 1
        self.save()

    # ------------------------------------------------------------------ pending online proofs
    def queue_run(self, level_id, taps, digest="", bg=False, assists=None):
        """`bg`: a re-sent old best (see sync_bests), not the run just played. `assists`: paid help of the run."""
        with self._lock:
            q = self.data.setdefault("pending_runs", [])
            q[:] = [r for r in q if r["level"] != level_id]
            run = {"level": level_id, "taps": list(taps), "ts": int(time.time()), "lvl": digest, "bg": bool(bg)}
            if assists:
                run["assists"] = [[int(a[0]), str(a[1])] for a in assists]
            q.append(run)
            del q[:-30]
        self.save()

    def drop_run(self, level_id):
        with self._lock:
            q = self.data.setdefault("pending_runs", [])
            q[:] = [r for r in q if r["level"] != level_id]
        self.save()

    # ------------------------------------------------------------------ skins & settings
    @property
    def equipped_skin(self):
        return self.data.get("equipped_skin", "neon_pulse")

    @equipped_skin.setter
    def equipped_skin(self, skin_id):
        self.data["equipped_skin"] = skin_id
        self.save()

    @property
    def unlocked_skins(self):
        return self.data.get("unlocked_skins", ["neon_pulse"])

    @property
    def settings(self):
        return self.data["settings"]

    def hint_seen(self, key):
        return key in self.data.get("hints_seen", [])

    def mark_hint(self, key):
        seen = self.data.setdefault("hints_seen", [])
        if key not in seen:
            seen.append(key)
            self.save()

    def unlock_skin(self, skin_id):
        skins = self.data.setdefault("unlocked_skins", ["neon_pulse"])
        if skin_id not in skins:
            skins.append(skin_id)
            self.save()

    def is_skin_unlocked(self, skin_id):
        if config.dev_unlock_all():
            from skins import PREMIUM_SKINS
            if skin_id not in PREMIUM_SKINS:              # paid skins stay behind the (test) shop
                return True
        self._check_skin_unlocks()
        return skin_id in self.data.get("unlocked_skins", ["neon_pulse"])

    # ------------------------------------------------------------------ shop
    def grant_skin(self, skin_id):
        self.unlock_skin(skin_id)

    @property
    def language(self):
        return self.settings.get("language", "tr")

    @language.setter
    def language(self, lang):
        self.settings["language"] = lang
        locales.set_language(lang)
        self.save()

    def unlock_text(self, skin_id):
        """One line telling the player how to get a skin."""
        tr = locales.get_language() == "tr"
        kind, val = skin_catalog.source(skin_id)
        if kind == "level":
            return f"{val}. bölüme ulaşınca açılır" if tr else f"Unlocks when you reach level {val}"
        if kind == "star":
            return (f"Sonsuz modda toplanan {val} yıldızla alınır" if tr
                    else f"Buy with {val} stars collected in the endless climb")
        if kind == "ach":
            import achievements
            a = achievements.BY_ID.get(val)
            name = achievements.title(a) if a else val
            return f"Başarım ödülü: {name}" if tr else f"Achievement reward: {name}"
        return f"Mağazadan {val} elmasla alınır" if tr else f"Buy in the shop for {val} diamonds"

    def _check_skin_unlocks(self):
        """Level skins open by themselves when the level is reached (achievement / shop skins never do)."""
        lvl = self.highest_cleared
        skins = self.data.setdefault("unlocked_skins", ["neon_pulse"])
        changed = False
        for skin_id, need in skin_catalog.LEVEL.items():
            if lvl >= need and skin_id not in skins:
                skins.append(skin_id)
                changed = True
        return changed

    # ------------------------------------------------------------------ diamonds / economy
    @property
    def diamonds(self):
        return int(self.data.get("diamonds", 20))

    def get_diamonds(self):
        return self.diamonds

    def add_diamonds(self, amount):
        with self._lock:
            cur = self.diamonds
            self.data["diamonds"] = max(0, cur + int(amount))
        self.save()
        return self.data["diamonds"]

    def spend_diamonds(self, amount):
        with self._lock:
            cur = self.diamonds
            if cur < amount:
                return False
            self.data["diamonds"] = cur - int(amount)
        self.save()
        return True

    # ------------------------------------------------------------------ server wallet (1.0.3)
    # The server owns the diamond balance (players.diamonds). data["diamonds"] is only the last known server balance
    # plus earnings that are still on their way; every spend waits for the server's yes.
    wallet = None                   # OnlineClient, attached by the game; None = old local behaviour (tools, tests)

    def earn(self, kind, ref, amount):
        """Claim diamonds the server can check: ("ach", <id>), ("welcome", "1"), ("daily", <mission id>),
        ("ad", <random>), ("pack", "<pack>:<token>"). Shown at once, confirmed (or taken back) by the server."""
        if self.wallet is None:
            return self.add_diamonds(amount)
        with self._lock:
            ops = self.data.setdefault("wallet_ops", [])
            if not any(o.get("kind") == kind and o.get("ref") == ref for o in ops):
                ops.append({"kind": kind, "ref": str(ref), "amount": int(amount)})
                self.data["diamonds"] = self.diamonds + int(amount)
        self.save()
        self.wallet.wallet_flush()
        return self.diamonds

    def pending_earnings(self):
        return sum(int(o.get("amount", 0)) for o in self.data.get("wallet_ops", []))

    def set_server_balance(self, balance):
        self.rev += 1
        with self._lock:
            self.data["diamonds"] = max(0, int(balance)) + self.pending_earnings()
            self.data["wallet_synced"] = True
        self.save()

    def drop_wallet_op(self, kind, ref):
        with self._lock:
            ops = self.data.get("wallet_ops", [])
            self.data["wallet_ops"] = [o for o in ops if not (o.get("kind") == kind and o.get("ref") == ref)]

    # ---- Google Play purchases waiting for the server (kept in the save until the server has answered)
    def add_iap(self, product, token, order=""):
        with self._lock:
            lst = self.data.setdefault("iap_pending", [])
            if not any(x.get("token") == token for x in lst):
                lst.append({"product": str(product), "token": str(token), "order": str(order or "")})
        self.save()
        if self.wallet is not None:
            self.wallet.wallet_flush()

    def drop_iap(self, token):
        with self._lock:
            self.data["iap_pending"] = [x for x in self.data.get("iap_pending", []) if x.get("token") != token]
        self.save()

    def set_server_skins(self, skins, account_tag=""):
        self.rev += 1
        """Skins the server knows this account owns (bought for diamonds or money): back after a reinstall."""
        for sid in skins or []:
            if not self.is_skin_unlocked(sid):
                self.grant_skin(sid)
        if account_tag and self.data.get("account_tag") != account_tag:
            with self._lock:
                self.data["account_tag"] = account_tag
            self.save()

    def spend(self, item, cost, on_done):
        """Pay `cost` diamonds for `item` ("revive", "shield", "skin:<id>"). The server decides; on_done(ok, reason)
        is called on the main thread, reason "" / "insufficient" / "offline"."""
        if self.wallet is None:
            ok = self.spend_diamonds(cost)
            on_done(ok, "" if ok else "insufficient")
            return
        if self.diamonds < cost:
            on_done(False, "insufficient")
            return
        self.wallet.wallet_spend(item, cost, on_done)

    SHIELD_STOCK_MAX = 5

    @property
    def shield_stock(self):
        return int(self.data.get("shield_stock", 0))

    def add_shield(self, n=1):
        with self._lock:
            self.data["shield_stock"] = max(0, min(self.SHIELD_STOCK_MAX, self.shield_stock + int(n)))
        self.save()
        return self.data["shield_stock"]

    def use_shield(self):
        with self._lock:
            if self.shield_stock <= 0:
                return False
            self.data["shield_stock"] = self.shield_stock - 1
        self.save()
        return True

    def can_watch_ad(self, cooldown=30.0):
        last = float(self.data.get("last_ad_watch", 0.0))
        return (time.time() - last) >= cooldown

    def seconds_until_ad(self, cooldown=30.0):
        last = float(self.data.get("last_ad_watch", 0.0))
        rem = cooldown - (time.time() - last)
        return max(0, int(rem))

    def record_ad_watched(self):
        with self._lock:
            self.data["last_ad_watch"] = time.time()
        self.save()

    # ------------------------------------------------------------------ daily missions
    def _daily(self):
        """Rolls the 3 daily missions over at local midnight; keeps a claimed-all-3 streak counter."""
        d = self.data.setdefault("daily", {"date": "", "progress": {}, "claimed": [], "streak": 0})
        today = datetime.date.today().isoformat()
        if d.get("date") != today:
            if d.get("date"):
                prev_missions = dm.missions_for(d["date"])
                if len(d.get("claimed", [])) >= len(prev_missions):
                    d["streak"] = d.get("streak", 0) + 1
                else:
                    d["streak"] = 0
            d["date"] = today
            d["progress"] = {}
            d["claimed"] = []
            self.save()
        return d

    def bump_daily(self, metric, amount=1):
        if amount == 0:
            return
        d = self._daily()
        d["progress"][metric] = d["progress"].get(metric, 0) + amount
        self.save()

    def daily_missions(self):
        """-> (missions, progress dict, claimed ids, streak)"""
        d = self._daily()
        return dm.missions_for(d["date"]), d["progress"], d["claimed"], d.get("streak", 0)

    def claim_daily(self, mission_id):
        d = self._daily()
        m = next((x for x in dm.missions_for(d["date"]) if x["id"] == mission_id), None)
        if not m or mission_id in d["claimed"] or d["progress"].get(m["metric"], 0) < m["target"]:
            return False
        d["claimed"].append(mission_id)
        c = self.data.setdefault("counters", {})
        c["daily_done"] = int(c.get("daily_done", 0)) + 1
        self.save()
        self.earn("daily", mission_id, m["reward"])
        return True

    # ---- weekly missions (weekly_missions.py): same idea as the daily ones, per ISO week
    def _weekly(self):
        w = self.data.setdefault("weekly", {"week": "", "progress": {}, "claimed": []})
        key = wm.week_key()
        if w.get("week") != key:
            w.update(week=key, progress={}, claimed=[])
        return w

    def bump_weekly(self, metric, amount=1):
        if amount:
            w = self._weekly()
            w["progress"][metric] = w["progress"].get(metric, 0) + amount
            self.save()

    def weekly_missions(self):
        w = self._weekly()
        return wm.missions_for(w["week"]), w["progress"], w["claimed"]

    def claim_weekly(self, mission_id):
        w = self._weekly()
        m = next((x for x in wm.missions_for(w["week"]) if x["id"] == mission_id), None)
        if not m or mission_id in w["claimed"] or w["progress"].get(m["metric"], 0) < m["target"]:
            return False
        w["claimed"].append(mission_id)
        self.save()
        self.earn("weekly", mission_id, m["reward"])
        return True

    def weekly_claimable_count(self):
        missions, progress, claimed = self.weekly_missions()
        return sum(1 for m in missions if m["id"] not in claimed and progress.get(m["metric"], 0) >= m["target"])

    def goals_claimable_count(self):
        """Everything waiting on the missions screen: daily + weekly missions and event tiers."""
        import events
        missions, progress, claimed = self.weekly_missions()
        weekly = sum(1 for m in missions if m["id"] not in claimed and progress.get(m["metric"], 0) >= m["target"])
        return self.daily_claimable_count() + weekly + len(events.claimable(self))

    def daily_claimable_count(self):
        missions, progress, claimed, _ = self.daily_missions()
        return sum(1 for m in missions if m["id"] not in claimed and progress.get(m["metric"], 0) >= m["target"])

    def reset_progress(self):
        """A true fresh start: campaign, stats, diamonds, skins, shields, achievements, daily missions - everything
        except identity (so the leaderboard entry / pilot name survive) and device settings (volume, language)."""
        keep = {k: self.data[k] for k in ("player_id", "player_secret", "player_name", "player_country",
                                          "is_profile_set", "settings")}
        self.data = _default_save()
        self.data.update(keep)
        self.save()
        locales.set_language(self.language)
