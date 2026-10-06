import gc
import sys
import math
import time

import pygame

import paths
import config
import ui
import shop as shop_mod
import achievements as ach_mod
import skin_catalog
import login_rewards
import notify
import events
import haptics
import space_art
import safe_area
from audio_manager import AudioManager
from save_manager import SaveManager
from particles import ParticleSystem
from skins import get_skin, draw_tether, draw_orb, PREMIUM_SKINS, SKINS, trail_kind
from level_manager import Level
import endless as E
from endless_view import EndlessLevel, sector_for_stage
from sim import Sim, SIM_DT, compute_result, MAX_LEVELS, SHIELD_INVULN, MIN_TAP_GAP
from sim import ARENA_W
from locales import t
from online import OnlineClient
from theme import BG_DARK

VW = 900
HUD_H = ui.HUD_H
FOOT_H = 72
REVIVE_COST = 20             # diamonds: continue in place after dying (failure screen)
INTRO_LEN = 2.0              # seconds: start-up logo animation (tap to speed it up)


class HoloGame:
    def __init__(self, headless=False):
        pygame.init()
        pygame.display.set_caption("HOLO")
        self.android = paths.is_mobile()         # phone layout / full screen (Android or iOS)
        self.headless = headless
        self._init_display()

        self.clock = pygame.time.Clock()
        self.running = True
        self.audio = AudioManager()
        self.save_mgr = SaveManager()
        self.settings = self.save_mgr.settings
        self.audio.set_music_volume(self.settings.get("music_volume", 0.6))
        self.audio.set_sfx_volume(self.settings.get("sfx_volume", 0.8))
        self.particles = ParticleSystem(VW, self.vh, quality=1.0 if self.settings.get("particles", True) else 0.0)
        self._render_quality = 1.0
        self.hud = ui.HUD()
        self.endless_hud = ui.EndlessHUD()
        self.online = OnlineClient(self.save_mgr)
        self.save_mgr.wallet = self.online           # diamonds live on the server from 1.0.3 on
        self._wallet_next = 180.0
        self._revive_wait = False

        # gameplay
        self.state = "menu"
        self.prev_state = "menu"
        self.level = None
        self.level_id = self.save_mgr.campaign_level
        self.sim = None
        self.endless_run = None         # the endless climb being played (self.sim is its Sim), else None
        self.endless_week = ""
        self.taps = []
        self.accum = 0.0
        self.resume_timer = 0.0
        self.prev_pos = [(0, 0), (0, 0)]
        self.attempts = 1
        self.death_timer = 0.0
        self.cam_y = 0.0
        self.tut_shown = 0
        self.failure_modal = None
        self.victory_modal = None
        self.profile_modal = None
        self.recovery_modal = None
        self.login_modal = None          # the daily login calendar (state "login")
        self.google_auth = None          # created on first use (Android bridge)
        self._cloud_next = 20.0          # first cloud copy of the save a little after start, then at most every 45 s
        self.prev_profile_state = "menu"
        self.view_h = self.vh - HUD_H - FOOT_H
        self.ghost = None
        self.ghost_taps = []
        self.ghost_i = 0
        self.ghost_name = None          # who the ghost is (the world's #1), None = my own best
        self.heart_timer = 0.0
        self.tick_timer = 0.0
        self.tension = 0.0
        self.hint = None                 # (key, seconds left) contextual power-up tip
        self.toasts = []                 # [title, subtitle, seconds left]
        self.run_bought = 0             # bought shields put on the pair in this attempt (consumed when one pops)
        self.assisted = False           # paid help (revive / bought shield) was used in this attempt
        self.assists = []               # [[sim step, "S"|"R"], ...]: replayed by the server, which checks it was paid for
        self.hint_cool = 0.0
        self.play_clock = 0.0
        self.ui_time = 0.0
        self.rewind_fx_t = 0.0
        self.rewind_cam_start = 0.0
        self._ach_synced = False
        self._make_backdrops()

        haptics.set_enabled(self.settings.get("haptics", True))
        haptics.start()
        self._build_ui()
        self._music_track = None
        self._sync_music()
        if not self.save_mgr.is_profile_set:
            self.open_profile("menu")
        else:
            self.online.register()
            self.online.wallet_sync()
            self.online.flush_pending()
            self.online.fetch("around", limit=11)
            notify.plan(self.save_mgr)               # re-plan the local reminders (Android only)
        if not headless:
            self._warm_up()
        # Start-up intro: picks up exactly where the Android loading image (assets/presplash.png) leaves off -
        # the logo glides to its menu spot, the orbs spin up and the menu fades / slides in.
        self.intro_t = 0.0
        self.intro_speed = 1.0
        self._after_intro = self.state
        self._intro_buf = None
        if not headless and config.get("intro", True):
            self.state = "intro"
            self.menu_ui.set_enter(0.0)
        _settle_gc()

    # ------------------------------------------------------------------ display
    def _init_display(self):
        info = pygame.display.Info()
        self.safe_top = self.safe_bottom = 0          # virtual pixels kept free for the camera cut-out / nav bar
        if self.android:
            aspect = info.current_h / float(max(1, info.current_w))
            px_top, px_bot = safe_area.insets_px(info.current_h)
            k = VW / float(max(1, info.current_w))
            self.safe_top, self.safe_bottom = int(round(px_top * k)), int(round(px_bot * k))
            self.vh = int(max(1620, min(2100, round(VW * aspect) - self.safe_top - self.safe_bottom)))
        else:
            self.vh = 1620
        win_vh = self.vh + self.safe_top + self.safe_bottom
        ui.set_screen_size(VW, self.vh)
        self.scaled = False
        self.vsync = False
        self.window = None
        if self.headless:
            self.window = pygame.display.set_mode((VW // 2, self.vh // 2))
        elif self.android:
            try:
                # vsync stays off (config "vsync": true turns it on): on 90/120 Hz phones it made the uncapped loop
                # chase the panel rate, frames alternated between one and two refreshes and everything stuttered
                # (1.0.3). A steady 60 fps cap (1.0.1 behaviour) is smoother on those phones.
                try:
                    if not config.get("vsync", False):
                        raise RuntimeError("vsync off")
                    self.window = pygame.display.set_mode((VW, win_vh), pygame.FULLSCREEN | pygame.SCALED, vsync=1)
                    self.vsync = True
                except Exception:
                    self.window = pygame.display.set_mode((VW, win_vh), pygame.FULLSCREEN | pygame.SCALED)
                self.scaled = True
            except Exception:
                self.window = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        else:
            self.win_w, self.win_h = 540, int(540 * self.vh / VW)
            self.window = pygame.display.set_mode((self.win_w, self.win_h), pygame.RESIZABLE)
        self.win_w, self.win_h = self.window.get_size()
        self.frame_direct = False
        if self.scaled and self.window.get_size() == (VW, win_vh):
            # SCALED: the window surface already is the virtual frame (the GPU upscales it) - draw straight
            # into it and skip a full-screen clear + copy every frame. The safe-area strips above / below the
            # frame stay black (cut-out camera, gesture bar).
            self.window.fill((0, 0, 0))
            self.frame = self.window.subsurface((0, self.safe_top, VW, self.vh))
            self.frame_direct = True
        else:
            self.safe_top = self.safe_bottom = 0
            self.frame = pygame.Surface((VW, self.vh))
        self._present_buffer = None
        self.is_fullscreen = False

    def to_virtual(self, pos):
        if self.scaled:
            return (pos[0], pos[1] - self.safe_top)
        scale = min(self.win_w / float(VW), self.win_h / float(self.vh))
        ox = (self.win_w - VW * scale) * 0.5
        oy = (self.win_h - self.vh * scale) * 0.5
        return ((pos[0] - ox) / scale, (pos[1] - oy) / scale)

    def toggle_fullscreen(self):
        if self.android or self.headless:
            return
        self.is_fullscreen = not self.is_fullscreen
        if self.is_fullscreen:
            self.window = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        else:
            self.window = pygame.display.set_mode((540, int(540 * self.vh / VW)), pygame.RESIZABLE)
        self.win_w, self.win_h = self.window.get_size()

    def _make_backdrops(self):
        """Space backdrop for the menu screens and edge-vignette strips for the end-of-level tension."""
        st, sb = self.safe_top, self.safe_bottom
        # the backdrop is painted for the whole screen, camera cut-out / gesture-bar strips included: the frame shows
        # the middle part, the strips above and below it get the rest (full-bleed, no black bands on phones)
        full = space_art.make_menu_backdrop(VW, self.vh + st + sb).convert()
        veil = pygame.Surface(full.get_size(), pygame.SRCALPHA)
        veil.fill((4, 6, 12, 150))
        full_dark = full.copy()
        full_dark.blit(veil, (0, 0))
        self.menu_bg = full.subsurface((0, st, VW, self.vh)).copy()
        self.menu_bg_dark = full_dark.subsurface((0, st, VW, self.vh)).copy()
        self._edge_art = {}
        for name, src in (("bright", full), ("dark", full_dark)):
            top = src.subsurface((0, 0, VW, st)).copy() if st else None
            bottom = src.subsurface((0, st + self.vh, VW, sb)).copy() if sb else None
            self._edge_art[name] = (top, bottom)
        self._edge_key = None
        # Keep the full menu scenery on every device.  Performance work belongs
        # in the update/draw path; reducing the stars and rocks makes the Android
        # version look like a different game.
        self.menu_life = space_art.SpaceLife(VW, self.vh, 1, 21, quality=1.0)
        self.intro_band = _Gradient((4, 6, 14), 210, VW, lambda y: int(200 * (1 - abs(y - 105) / 105.0) ** 0.6), False)
        n = 90
        edge = lambda d: int(255 * (1 - d / float(n)) ** 2)
        self.vig = {"l": (_Gradient((255, 40, 60), n, self.view_h, edge, True), (0, 0)),
                    "r": (_Gradient((255, 40, 60), n, self.view_h, lambda x: edge(n - 1 - x), True), (VW - n, 0)),
                    "t": (_Gradient((255, 40, 60), n, VW, edge, False), (0, 0)),
                    "b": (_Gradient((255, 40, 60), n, VW, lambda y: edge(n - 1 - y), False), (0, self.view_h - n))}

    # ------------------------------------------------------------------ ui construction
    def _build_ui(self):
        self.menu_ui = ui.MainMenu(
            self.save_mgr, on_continue=self.continue_campaign, on_levels=self.open_level_select,
            on_leaderboard=self.open_leaderboard, on_skins=self.open_skins, on_shop=self.open_featured, on_achievements=self.open_achievements,
            on_profile=lambda: self.open_profile("menu"), on_settings=lambda: self.open_settings("menu"),
            on_quit=None if self.android else self.quit_game, rank_provider=lambda: self.online.rank_info,
            on_daily=self.open_daily, on_endless=self.open_endless)
        self.level_select_ui = ui.LevelSelectScreen(self.save_mgr, self.on_select_level, self.open_menu)
        self.leaderboard_ui = ui.LeaderboardScreen(self.save_mgr, self.open_menu,
                                                   on_edit_profile=lambda: self.open_profile("leaderboard"), online=self.online)
        self.skin_ui = ui.SkinScreen(self.save_mgr, self.open_menu, audio_manager=self.audio, on_shop=self.open_shop)
        self.shop = shop_mod.Shop(self.save_mgr)
        self.online.on_purchase = self.shop.purchase_result
        self.ach_ui = ui.AchievementsScreen(self.save_mgr, self.open_menu, audio_manager=self.audio)
        self.daily_ui = ui.DailyMissionsScreen(self.save_mgr, self.open_menu, audio_manager=self.audio)
        self.shop_ui = ui.ShopScreen(self.save_mgr, self.shop, self.open_featured, audio_manager=self.audio)
        self.featured_ui = ui.FeaturedScreen(self.save_mgr, self.shop, self.open_menu, self.open_shop, audio_manager=self.audio)
        lvl_cb = self.open_level_select
        self.pause_modal = ui.PauseModal(self.resume_game, self.restart_level, lambda: self.open_settings("paused"),
                                         self.open_menu, lvl_cb)
        self.howto_ui = ui.HowToModal(self._close_howto, save_mgr=self.save_mgr)
        self.settings_modal = ui.SettingsModal(self.save_mgr, self.audio, self.toggle_fullscreen, self.close_settings,
                                               self.on_language_change, on_reset=self.on_progress_reset, desktop=not self.android)

    def on_language_change(self):
        self.menu_ui.refresh_texts()
        self.pause_modal.refresh_texts()
        self.leaderboard_ui.refresh_texts()
        self.skin_ui.refresh_texts()
        self.shop_ui.refresh_texts()
        self.featured_ui.refresh_texts()
        self.ach_ui.refresh_texts()
        self.daily_ui.refresh_texts()
        self.howto_ui.refresh_texts()
        self.level_select_ui.refresh_texts()
        self.settings_modal.refresh_texts()
        if self.failure_modal:
            self.failure_modal.refresh_texts()

    # ------------------------------------------------------------------ navigation
    def _click(self):
        self.audio.play_sfx("sfx_click")

    def _warm_up(self):
        """Render the first screen once off-screen while Android still shows the loading splash (assets/presplash.png),
        so its text / button / glow caches exist before the first visible frame - no stutter right after start."""
        f = pygame.Surface((VW, self.vh)).convert()
        # the first frame of every menu screen used to build its sprites / texts on the spot (10-25 ms on a PC,
        # a visible hitch on phones the first time a screen opened) - build them all now, behind the splash
        for st in (self.state, "menu", "featured", "shop", "skins", "leaderboard", "levels", "achievements", "daily", "settings"):
            try:
                self._draw_scene(f, st, False)
            except Exception as e:                   # warming up must never stop the game from starting
                print("warm-up skipped", st, e)

    def open_menu(self):
        self._leave_endless()
        self.state = "menu"
        self.menu_ui.build()
        self._click()

    # ---- daily login calendar (login_rewards.py): pops up on the menu once a day, the menu also has a button
    def open_login_reward(self):
        self.login_modal = ui.LoginRewardModal(self.save_mgr, on_claim=self._claim_login, on_close=self.close_login_reward)
        self.state = "login"

    def _claim_login(self):
        got = login_rewards.claim(self.save_mgr)
        if got:
            self.audio.play_sfx("sfx_coin")
            haptics.buzz(30)
            self.login_modal.claimed = got
            notify.plan(self.save_mgr)               # tomorrow's reminder, now that today's reward is taken

    def close_login_reward(self):
        if self.login_modal is not None and self.login_modal.claimed:
            notify.ask_permission(self.save_mgr)     # Android 13+: once, right after the first reward
        self.login_modal = None
        self.state = "menu"
        self.menu_ui.build()

    def _maybe_login_popup(self):
        if self.state != "menu":
            self._menu_since = self.ui_time
            return
        if self.ui_time - getattr(self, "_menu_since", 0.0) < 1.0:     # let the menu show for a moment first
            return
        if (self.state == "menu" and self.save_mgr.is_profile_set and login_rewards.claimable(self.save_mgr)
                and not self.toasts and self.ui_time > getattr(self, "_login_popup_after", 0.0)):
            self._login_popup_after = self.ui_time + 3600.0      # at most once an hour if they close it unclaimed
            self.open_login_reward()

    def on_progress_reset(self):
        """Settings -> reset progress (armed 2nd tap): wipe the in-memory run state and land back on the menu."""
        self.level = None
        self.sim = None
        self.ghost = None
        self.level_id = 1
        self.attempts = 1
        self.failure_modal = None
        self.victory_modal = None
        self.toasts = []
        self.state = "menu"
        self.menu_ui.build()
        self._click()

    def open_level_select(self):
        self.state = "levels"
        self.level_select_ui.refresh_texts()
        self.level_select_ui.focus_level(min(self.save_mgr.unlocked_level, self.save_mgr.campaign_level))
        self._click()

    def open_leaderboard(self, scope=None):
        self.state = "leaderboard"
        if scope and scope != self.leaderboard_ui.scope:
            self.leaderboard_ui.set_scope(scope)
        else:
            self.leaderboard_ui.on_open()
        self._click()

    # ------------------------------------------------------------------ endless climb
    def open_endless(self):
        if not self.save_mgr.endless_unlocked:
            self.toasts.append([t("endless_locked_toast"), "", 2.6])
            self._click()
            return False
        self._show_loading(t("endless_loading"))
        self.endless_week = E.week_of(time.time() + self.online._clock_offset)
        # every climb is a new map (the server replays this seed), never opening like one of the last few climbs
        self.endless_nonce, first = E.fresh_nonce(self.endless_week, self.save_mgr.endless.get("recent", []))
        self.save_mgr.endless["recent"] = (list(self.save_mgr.endless.get("recent", [])) + [first])[-E.RECENT_KEEP:]
        run = E.EndlessRun(E.seed_of(self.endless_week, self.endless_nonce), record_events=True)
        lvl = EndlessLevel(run)
        lvl.finish(run.w0)                         # the first stage now; the ones above are drawn a little per frame
        self.endless_run = run
        lvl.record_m = int(self.save_mgr.endless.get("best_m", 0))     # the gold REKOR line in the world
        self.endless_fx = {"m100": 0, "tier": 0, "record": lvl.record_m <= 0, "streak": 0, "last_star": -9.0}
        self.endless_banner = None
        self.level = lvl
        self.sim = run.sim
        self.attempts = 1
        self._reset_attempt()
        self.state = "playing"
        self.audio.play_sfx("sfx_warp")
        _settle_gc()
        return True

    def _show_loading(self, text):
        """One frame with a small card while something heavy is prepared (so the tap visibly did something)."""
        if self.headless:
            return
        f = self.frame
        f.blit(self.menu_bg_dark, (0, 0))
        card = pygame.Rect(VW // 2 - 260, self.vh // 2 - 70, 520, 140)
        ui.panel(f, card, (12, 20, 36), ui.ACCENT_CYAN, 24)
        ui.draw_text(f, text, 34, ui.TEXT_WHITE, card.center, bg=(12, 20, 36), max_w=480)
        self._present()

    def _endless_banner(self, title, sub="", color=(255, 215, 60), secs=1.7):
        """A big line across the middle of the climb (milestone, new record, new zone)."""
        self.endless_banner = [title, sub, color, secs, secs]

    def _endless_progress(self):
        """Milestones while climbing: every 100 m, every diamond height, the player's record, each new zone."""
        run, fx = self.endless_run, self.endless_fx
        m = run.metres
        if not fx["record"] and m > self.level.record_m > 0:
            fx["record"] = True
            self._endless_banner(t("endless_banner_record"), t("endless_banner_record_sub"), (255, 215, 60), 2.2)
            self.audio.play_sfx("sfx_win")
            self.particles.add_shake(10.0)
            haptics.buzz(40)
        elif m // 100 > fx["m100"]:
            fx["m100"] = m // 100
            h = fx["m100"] * 100
            if h % E.DIAMOND_EVERY_M == 0:
                self._endless_banner(f"{ui.fmt_int(h)} m", t("endless_banner_gem"), (0, 230, 255))
                self.audio.play_sfx("sfx_coin")
            else:
                self._endless_banner(f"{ui.fmt_int(h)} m", "", (255, 255, 255), 1.2)
        tier = E.tier_of(run.stage)
        if tier > fx["tier"]:
            fx["tier"] = tier
            self._endless_banner(t("endless_banner_zone", n=tier + 1), t(f"endless_zone_{min(tier, 7)}"),
                                 ui.SECTOR_COL.get(sector_for_stage(run.stage), (255, 170, 60)), 2.0)
            self.audio.play_sfx("sfx_warp")

    def _endless_died(self):
        """The climb ended: offer a paid revive (like the campaign's) while there are some left, else finish it."""
        run = self.endless_run
        used = sum(1 for a in self.assists if a[1] != "S")
        if used >= E.MAX_REVIVES:
            self._endless_over()
            return
        self.state = "failed"
        self.failure_modal = ui.EndlessReviveModal(run.points, run.metres, run.stars, self.save_mgr, REVIVE_COST,
                                                   E.MAX_REVIVES - used, on_revive=self.revive_run,
                                                   on_finish=self._endless_over)

    def _endless_over(self):
        run = self.endless_run
        metres = run.metres
        new_best = self.save_mgr.record_endless(self.endless_week, run.points, metres, run.stars)
        ach_mod.bump(self.save_mgr, "endless_runs")
        self.save_mgr.bump_weekly("endless_m", metres)
        self.save_mgr.bump_weekly("endless_stars", run.stars)
        events.add_points(self.save_mgr, run.stars)          # the running event counts the climb's stars
        if self.taps or metres > 0:
            self.online.submit_endless(self.endless_week, self.endless_nonce, self.taps, run.n, self.assists)
        else:
            self.online.endless_result = {"ok": True, "added": 0, "next_gem": E.DIAMOND_EVERY_M}
        self.state = "failed"
        self.failure_modal = ui.EndlessResultModal(
            metres, run.stage, self.save_mgr.endless["best_all"], self.save_mgr.endless["best_all"],
            new_best, sector_for_stage(run.stage), self.online, on_retry=self.retry_after_fail, on_menu=self.open_menu,
            on_board=lambda: self.open_leaderboard("endless"), points=run.points, stars=run.stars,
            wallet=self.save_mgr.star_coins, on_skins=self._open_star_skins)

    def _open_star_skins(self):
        """From the climb's result straight to the Yıldız Avcısı page (what the stars buy)."""
        self._leave_endless()
        self.open_skins()
        self.skin_ui.cat = skin_catalog.STAR_THEME
        self.skin_ui.selected_skin = skin_catalog.THEMES[skin_catalog.STAR_THEME][2][0]

    def _leave_endless(self):
        if self.endless_run is not None:
            self.endless_run = None
            self.level = None
            self.sim = None

    def open_skins(self):
        self.state = "skins"
        self.save_mgr._check_skin_unlocks()
        self.skin_ui.open_at(self.save_mgr.equipped_skin)
        self._click()

    def open_achievements(self):
        self.state = "achievements"
        self.ach_ui.page = 0
        self._click()

    def open_daily(self):
        if login_rewards.claimable(self.save_mgr):      # today's login reward first (the daily badge counts it)
            self.open_login_reward()
            return
        self._open_daily_missions()

    def _open_daily_missions(self):
        self.state = "daily"
        self._click()

    def open_featured(self):
        self.state = "featured"
        self.featured_ui.refresh()
        self._click()

    def open_shop(self):
        self.state = "shop"
        self.shop_ui.select(self.skin_ui.selected_skin)
        self._click()

    def open_settings(self, from_state):
        self.prev_state = from_state
        self.state = "settings"
        self._click()

    def close_settings(self):
        self.save_mgr.save()
        self.particles.quality = 1.0 if self.settings.get("particles", True) else 0.0
        self.state = self.prev_state
        self._click()

    def open_profile(self, from_state="menu"):
        self.prev_profile_state = from_state
        self.state = "profile"
        self.profile_modal = ui.ProfileModal(self.save_mgr, on_save=self.close_profile, on_recovery=self.open_recovery)
        self._click()

    # ------------------------------------------------------------------ account recovery
    def open_recovery(self, mode):
        """mode "link" / "restore": account recovery through a Google account (Android's own account chooser)."""
        if self.google_auth is None:
            import google_auth
            self.google_auth = google_auth.GoogleAuth()
        self.recovery_modal = ui.GoogleModal(self.google_auth, self.online, mode, on_close=self.close_recovery,
                                             on_restored=self._on_account_restored, on_linked=self._on_google_linked)
        self.state = "recovery"
        self._click()

    def _on_google_linked(self, email):
        self.save_mgr.data["google_email"] = email
        self.save_mgr.save()
        if self.profile_modal:
            self.profile_modal.btn_code.text = ui.t("google_linked_btn", email=email)
            self.profile_modal.btn_code.font_size = 22

    def close_recovery(self):
        self.recovery_modal = None
        self.state = "profile" if self.profile_modal else "menu"
        self._click()

    def _on_account_restored(self, payload):
        """The server found the account behind a recovery code: this device becomes that pilot."""
        self.save_mgr.import_cloud(payload)
        if self.profile_modal:
            self.profile_modal.close()
        self.profile_modal = None
        self.recovery_modal = None
        self.settings = self.save_mgr.settings
        self.audio.set_music_volume(self.settings.get("music_volume", 0.6))
        self.audio.set_sfx_volume(self.settings.get("sfx_volume", 0.8))
        haptics.set_enabled(self.settings.get("haptics", True))
        self.level_id = self.save_mgr.campaign_level
        self._build_ui()
        self.online.boards = {}
        self.online.rank_info = None
        self.online.register()
        self.online.fetch("around", limit=11)
        self.save_mgr.cloud_dirty = False           # it is the server's copy
        self.toasts.append([t("recovery_done"), self.save_mgr.player_name, 3.5])
        self.state = "menu"
        self.audio.play_sfx("sfx_win")

    def _sync_cloud(self, now=False):
        """Keep the account's cloud copy (used by account recovery) fresh; never mid-swing."""
        sm = self.save_mgr
        if not sm.cloud_dirty or not sm.is_profile_set or self.state in ("playing", "dying"):
            return
        if not now and self.ui_time < self._cloud_next:
            return
        self._cloud_next = self.ui_time + 45.0
        sm.cloud_dirty = False
        self.online.cloud_save(sm.export_cloud())

    def close_profile(self):
        self.state = self.prev_profile_state
        self.profile_modal = None
        self.menu_ui.build()
        self.online.register()
        self.online.wallet_sync()
        self.online.flush_pending()
        self._click()

    def resume_game(self):
        self.state = "playing"
        self.accum = 0.0
        self.prev_pos = [(o.x, o.y) for o in self.sim.orbs]
        self.resume_timer = 1.2
        self._click()

    def quit_game(self):
        self.running = False

    def continue_campaign(self):
        lvl = min(self.save_mgr.unlocked_level, self.save_mgr.campaign_level)
        self.attempts = 1
        self.load_and_play_level(lvl)

    def on_select_level(self, level_id):
        if not 1 <= level_id <= self.save_mgr.unlocked_level:
            return False
        self.attempts = 1
        self.load_and_play_level(level_id)
        self.audio.play_sfx("sfx_warp")

    # ------------------------------------------------------------------ level lifecycle
    def load_and_play_level(self, level_id):
        self._leave_endless()
        # the try count of a level survives leaving it (menu, other levels, closing the game) until it is cleared
        self.attempts = self.save_mgr.level_attempts(level_id)
        lvl = Level(level_id)
        if not lvl.load():
            print(f"Failed to load level {level_id}")
            return False
        self.level_id = level_id
        self.level = lvl
        self.tut_shown = 0
        if hasattr(self.online, "fetch_ghost") and self.settings.get("ghost_race", False):
            self.online.fetch_ghost(level_id)
        self.restart_level(count_attempt=False)
        if level_id == 1 and not self.save_mgr.data.get("howto_seen"):
            self.howto_ui.reset()
            self.state = "howto"
        return True

    def _close_howto(self):
        self.save_mgr.data["howto_seen"] = True
        self.save_mgr.save()
        self.state = "playing"
        self.accum = 0.0
        self._click()

    def restart_level(self, count_attempt=False):
        if self.endless_run is not None:
            self.open_endless()
            return
        if not self.level:
            return
        # a shield armed before the very first swap was never actually used - carry it into the fresh attempt
        # instead of discarding it, so restarting (R / menu) right after arming one doesn't waste it.
        carried_shields, carried_bought = 0, 0
        if self.sim and self.sim.swaps == 0 and self.sim.shields > 0:
            carried_shields = self.sim.shields
            carried_bought = self.run_bought
        self.sim = Sim(self.level.data, record_events=True)
        self._reset_attempt()
        # only bought shields carry over: they are replayed by the server as paid help, a collected one would not be
        for k in range(min(carried_shields, carried_bought)):
            self.sim.add_shield()
            self.assists.append([0, "S"])              # a bought shield armed before the first swap
        self.run_bought = carried_bought
        self._install_ghost()
        self._snap_camera()
        self.state = "playing"
        _settle_gc()                    # collect now (between attempts) instead of mid-swing

    def _reset_attempt(self):
        """Per-attempt state of a fresh self.sim (campaign attempt or endless climb)."""
        self.level.reset_fx()
        self.resume_timer = 0.0
        self.taps = []
        self.assisted = False
        self.assists = []
        self.run_bought = 0
        self.accum = 0.0
        self.death_timer = 0.0
        self.failure_modal = None
        self.victory_modal = None
        self.particles.clear()
        self.prev_pos = [(o.x, o.y) for o in self.sim.orbs]
        self.heart_timer = 0.0
        self.tick_timer = 0.0
        self.tension = 0.0
        self.play_clock = 0.0
        self.hint = None
        self.hint_cool = 0.0
        self.rewind_fx_t = 0.0
        self.ghost = None
        self._snap_camera()

    def retry_after_fail(self):
        if isinstance(self.failure_modal, ui.EndlessReviveModal):
            self._endless_over()                  # a climb waiting on its revive offer is finished (and sent) first
        self.attempts += 1
        if self.endless_run is None:
            self.save_mgr.set_level_attempts(self.level_id, self.attempts)
        self.restart_level()

    def revive_run(self):
        """Failure screen: pay REVIVE_COST diamonds to resume in place instead of retrying from the start.
        The run still counts for the leaderboard: the server replays the revive and checks it was paid."""
        s = self.sim
        if not s or not s.dead or self.save_mgr.diamonds < REVIVE_COST or self._revive_wait:
            return False
        self._revive_wait = True
        modal = self.failure_modal
        if modal:
            modal.waiting = True

        def paid(ok, reason):
            self._revive_wait = False
            if modal:
                modal.waiting = False
            if ok and self.sim is s and self.state == "failed" and self.failure_modal is modal:
                self._revive_now(s)
            elif not ok:
                self.toasts.append([t("need_online" if reason == "offline" else "not_enough_diamonds"), "", 2.6])

        self.save_mgr.spend("revive", REVIVE_COST, paid)
        return True

    def _revive_now(self, s):
        self.assisted = True
        self.assists.append([s.n, "R2"])
        ach_mod.bump(self.save_mgr, "revive")
        s.revive(guarded=True)                 # same rule the server's replay applies (sim.py Sim.revive, "R2"):
        #                                        slow spin-up, shielded until the next tap
        self.particles.clear()
        self.rewind_cam_start = self.cam_y     # the camera glides back to the rewound pair ("rewinding" overlay)
        self.rewind_fx_t = 0.45
        self.state = "playing"
        self.death_timer = 0.0
        self.failure_modal = None
        self.accum = 0.0
        self.audio.play_sfx("sfx_shield")
        self.prev_pos = [(o.x, o.y) for o in s.orbs]
        # no 3-2-1 any more: the pair starts turning slowly and stays shielded until the player's next tap
        self.resume_timer = 0.0
        self._click()
        return True

    def use_hud_shield(self):
        """HUD button next to pause: put a shield on the pair now (stock first, otherwise 10 diamonds)."""
        s = self.sim
        if not s or s.dead or s.won or self.state != "playing":
            return
        if s.shields >= 3 or self.run_bought >= self.save_mgr.SHIELD_STOCK_MAX:
            return
        if self.run_bought >= self.save_mgr.shield_stock:            # nothing left in stock for this run: buy one
            if getattr(self, "_shield_wait", False):
                return

            def paid(ok):
                self._shield_wait = False
                if not ok:
                    self.toasts.append([t(self.shop.current_message() or "not_enough_diamonds"), "", 2.4])
                    self._click()
                elif self.sim is s and self.state == "playing" and not s.dead:
                    self._put_shield(s)                  # bought while this run is still going: use it now

            self._shield_wait = True
            self.shop.buy_shield(on_done=paid)
            return
        self._put_shield(s)

    def _put_shield(self, s):
        s.add_shield()
        self.assists.append([s.n, "S"])
        self.run_bought += 1
        self.audio.play_sfx("sfx_shield")
        p = s.pivot
        self.particles.emit_swap_pulse(p.x, p.y, (0, 220, 255))
        self.particles.emit_floating_text(p.x, p.y - 40, t("shield_on_popup"), (120, 235, 255))

    def _snap_camera(self):
        self.cam_y = self._camera_target()

    def _camera_target(self):
        run = self.endless_run
        if run is not None:
            p, r = self.sim.pivot, self.sim.rotating
            top = (p.y + r.y) / 2.0 - self.view_h * 0.62
            return min(top, run.world.stage(run.w0).bottom - self.view_h)    # never below the window floor
        h = self.level.height
        vh = self.view_h
        if h <= vh:
            return -(vh - h) / 2.0
        p = self.sim.pivot
        r = self.sim.rotating
        cy = (p.y + r.y) / 2.0
        # keep the pair at ~60% of the view height so the upcoming route is visible
        top = cy - vh * (0.62 if self.level.data.end[1] < self.level.data.start[1] else 0.38)
        return max(0.0, min(h - vh, top))

    # ------------------------------------------------------------------ input
    def swap_pivot(self):
        s = self.sim
        if (self.state != "playing" or s is None or s.dead or s.won
                or self.rewind_fx_t > 0.0 or self.resume_timer > 0.0):
            return
        # One swap per MIN_TAP_GAP ticks: a touch that bounces (two events a few ms apart) must not swap straight
        # back, and faster input than that is refused by the ranking server - the whole run would be lost.
        if self.taps and s.n - self.taps[-1] < MIN_TAP_GAP:
            return
        s.swap()
        self.taps.append(s.n)
        self.tut_shown += 1

    # ------------------------------------------------------------------ simulation events
    def _handle_sim_events(self):
        s = self.sim
        skin = get_skin(self.save_mgr.equipped_skin)
        for ev in s.events:
            kind = ev[0]
            if kind in ("smash", "shield_pop", "shrink", "grow", "boost", "chase", "graze"):
                ach_mod.bump(self.save_mgr, kind)
            elif kind == "die":
                ach_mod.bump(self.save_mgr, "deaths")
            if kind == "swap":
                self.audio.play_sfx("sfx_swap")
                self.particles.emit_swap_pulse(ev[1], ev[2], skin["glow1"])
            elif kind == "combo":
                self.audio.play_sfx("sfx_combo")
                self.particles.emit_floating_text(ev[1], ev[2] - 30, t("combo_popup", val=ev[3]), (255, 215, 30))
            elif kind == "reverse":
                haptics.buzz(22)
                self.audio.play_sfx("sfx_bounce")
                self.particles.add_shake(9.0)
                self.particles.emit_bounce(ev[1], ev[2], (90, 255, 200))
                self.particles.emit_floating_text(ev[1], ev[2] - 34, t("bounce_popup"), (110, 255, 200))
                if len(ev) > 3 and self.level:
                    self.level.flash_bumper(ev[3], self.sim.t)
            elif kind == "grow":
                self.audio.play_sfx("sfx_warp")
                self.particles.emit_floating_text(ev[1], ev[2] - 30, t("grow_popup"), (40, 255, 130))
            elif kind == "shrink":
                self.audio.play_sfx("sfx_warp")
                self.particles.emit_floating_text(ev[1], ev[2] - 30, t("shrink_popup"), (0, 220, 255))
            elif kind == "boost":
                self.audio.play_sfx("sfx_warp")
                self.particles.emit_floating_text(ev[1], ev[2] - 30, t("boost_popup"), (255, 190, 30))
            elif kind == "shield_get":
                self.audio.play_sfx("sfx_shield")
                self.particles.emit_floating_text(ev[1], ev[2] - 30, t("shield_get_popup"), (0, 220, 255))
            elif kind == "shield_pop":
                if self.run_bought > 0:
                    self.assisted = True                     # a bought shield was spent (replayed + checked by the server)
                    self.run_bought -= 1
                    self.save_mgr.use_shield()
                    self.particles.emit_floating_text(ev[1], ev[2] - 70, t("shield_used"), (120, 230, 255))
                haptics.buzz(30)
                self.audio.play_sfx("sfx_shield")
                self.particles.add_shake(12.0)
                self.particles.emit_swap_pulse(ev[1], ev[2], (0, 220, 255))
                self.particles.emit_floating_text(ev[1], ev[2] - 30, t("shield_protect_popup"), (0, 240, 255))
            elif kind == "smash":
                haptics.buzz(35)
                self.audio.play_sfx("sfx_smash")
                self.particles.add_shake(14.0)
                self.particles.emit_explosion(ev[1], ev[2], (200, 140, 80))
                self.particles.emit_floating_text(ev[1], ev[2] - 30, t("smash_popup"), (255, 190, 90))
            elif kind == "chase":
                haptics.buzz(40)
                self.audio.play_sfx("sfx_chase")
                self.particles.add_shake(10.0)
                self.particles.emit_floating_text(s.pivot.x, s.pivot.y - 60, t("chase_popup"), (255, 90, 110))
            elif kind == "fx_end":
                self.audio.play_sfx("sfx_fxend")
            elif kind == "star":
                self.audio.play_sfx("sfx_star")
                self.particles.emit_star_collect(ev[1], ev[2])
                if self.endless_run is not None:          # the climb: +100 each, quick pickups make a streak
                    fx = self.endless_fx
                    fx["streak"] = fx["streak"] + 1 if s.t - fx["last_star"] < 2.5 else 1
                    fx["last_star"] = s.t
                    self.particles.emit_floating_text(ev[1], ev[2] - 24, f"+{E.POINTS_PER_STAR}", (255, 220, 40))
                    if fx["streak"] >= 5:
                        self.save_mgr.data.setdefault("counters", {})["star_streak5"] = 1
                    if fx["streak"] >= 2:
                        self.particles.emit_floating_text(ev[1], ev[2] - 64, t("endless_streak", n=fx["streak"]),
                                                          (255, 150, 60))
                        haptics.buzz(15)
                else:
                    self.particles.emit_floating_text(ev[1], ev[2] - 24, f"+{ev[3]}", (255, 220, 40))
            elif kind == "graze":
                self.audio.play_sfx("sfx_near_miss")
                self.particles.emit_floating_text(ev[1], ev[2] - 24, t("graze_popup"), (0, 230, 255))
            elif kind == "die":
                haptics.buzz(45)
                self.audio.play_sfx("sfx_die")
                self.particles.emit_explosion(ev[1], ev[2], skin["color1"], trail_kind(skin))
                self.state = "dying"
                self.death_timer = 0.55
            elif kind == "win":
                self._on_win()
        s.events.clear()

    def _on_win(self):
        if self._autoplay is not None:
            self._autoplay_next()
            return
        s = self.sim
        haptics.buzz(25)
        self.audio.play_sfx("sfx_win")
        res = compute_result(s)
        if s.max_combo >= 4:
            self.save_mgr.data.setdefault("counters", {})["combo4"] = 1
        # the run's paid help is kept with its taps (a best the server missed can be re-sent); the ghost skips such runs
        improved = self.save_mgr.record_level_clear(self.level_id, res, self.taps, self.assists)
        self.save_mgr.set_level_attempts(self.level_id, 1)       # cleared: the next visit counts from 1 again
        self.save_mgr.bump_daily("levels_played", 1)
        self.save_mgr.bump_daily("stars_earned", res["stars"])
        self.save_mgr.bump_weekly("levels_played", 1)
        self.save_mgr.bump_weekly("stars_earned", res["stars"])
        # Send every clear, with its paid help (revives / bought shields): the server replays it, checks the help was
        # paid for and decides whether it improves the stored best.
        if self.online.enabled:
            self.online.submit(self.level_id, self.taps, self.level.data.digest, self.assists)
        elif self.online.enabled:
            self.online.last_submit = None
        nxt = self.level_id + 1
        lid = self.level_id

        def go_next():
            if nxt <= MAX_LEVELS:
                self.attempts = 1
                self.load_and_play_level(nxt)
            else:
                self.open_leaderboard()

        self.state = "victory"
        self.victory_modal = ui.VictoryModal(
            level_id=lid, result=res, total_score=self.save_mgr.total_score,
            pilot_name=self.save_mgr.player_name, pilot_country=self.save_mgr.player_country,
            on_next=go_next, on_replay=lambda: (setattr(self, "attempts", 1), self.restart_level()),
            on_menu=self.open_menu, on_levels=self.open_level_select, new_best=improved, attempts=self.attempts,
            online=self.online, is_last=(nxt > MAX_LEVELS), assisted=False)   # paid help is ranked now

    # ------------------------------------------------------------------ frame update
    def update_gameplay(self, dt):
        if self.rewind_fx_t > 0.0:                      # a revive rewound the pair: glide there, then count down
            self.rewind_fx_t -= dt
            target_cam = self._camera_target()
            k = max(0.0, min(1.0, 1.0 - (self.rewind_fx_t / 0.45)))
            self.cam_y = self.rewind_cam_start + (target_cam - self.rewind_cam_start) * k
            self.accum = 0.0
            return
        if self.resume_timer > 0.0:
            self.resume_timer = max(0.0, self.resume_timer - dt)
            self.accum = 0.0
            return

        s = self.sim
        run = self.endless_run
        b = getattr(self, "endless_banner", None)
        if run is not None and b:                      # the milestone banner's clock
            b[3] -= dt
            if b[3] <= 0.0:
                self.endless_banner = None
        if self._autoplay is not None:
            self._autoplay_step(s)
        self.accum = min(self.accum + dt, SIM_DT * 6)
        steps = 0
        while self.accum >= SIM_DT and self.state == "playing":
            self.prev_pos = [(o.x, o.y) for o in s.orbs]
            if run is not None:
                w0 = run.w0
                run.step()                             # the climb: speed per stage, window moves up by itself
                if run.w0 != w0:
                    self.level.rev_hits = {}           # bumper indices shifted with the window
                self._endless_progress()
            else:
                s.step()
            self.accum -= SIM_DT
            steps += 1
            if self.settings.get("particles", True) and not s.dead:
                skin = get_skin(self.save_mgr.equipped_skin)
                r = s.rotating
                if s.n % 2 == 0:
                    self.particles.emit_trail(r.x, r.y, skin["color2"], radius=int(r.r * 0.55), kind=trail_kind(skin))
                if s.n % 3 == 0 and run is None:
                    self.particles.emit_portal_particles(*self.level.data.end)
            self._step_ghost()
            self._handle_sim_events()
        if run is not None:
            self.level.prepare(run.w0 + E.WINDOW - 1)
            self.level.pump(0.0015)
        if self.state == "playing":
            self._update_tension(dt)
            self._update_hints(dt)
        self.particles.update(dt * 60.0)

    # ---- performance test hook (config.json "perf_autoplay": [level ids]); never on in a release build
    _autoplay = None

    def _start_autoplay(self):
        if config.get("release_mode", False):
            return
        if config.get("perf_autoplay") == "shop":               # the shop list scrolled up and down (fling)
            self.open_shop()
            self._autoplay = None
            self._perf_shop = True
            print("[perf] autoplay shop")
            return
        if config.get("perf_autoplay") == "endless":            # the endless climb with a steady tap rhythm
            for lv in range(1, 11):
                self.save_mgr.stats.setdefault(str(lv), {"stars": 1, "best_score": 1})
            self.open_endless()
            taps = config.get("perf_endless_taps")             # a bot's climb for this nonce: a long, real run
            if taps and config.get("perf_endless_nonce"):
                self.endless_nonce = str(config.get("perf_endless_nonce"))
                self.endless_run = E.EndlessRun(E.seed_of(self.endless_week, self.endless_nonce), record_events=True)
                lvl = EndlessLevel(self.endless_run)
                lvl.finish(self.endless_run.w0)
                lvl.record_m = self.level.record_m
                self.level, self.sim = lvl, self.endless_run.sim
                self._reset_attempt()
            self._autoplay = [sorted(taps) if taps else list(range(60, 60 * 60 * 20, 52)), 0, True]
            self._autoplay_levels = []
            print("[perf] autoplay endless")
            return
        levels = [int(x) for x in config.get("perf_autoplay") or []]
        if not levels:
            return
        self._autoplay_levels = levels
        self._autoplay_next()

    def _autoplay_next(self):
        if not self._autoplay_levels:
            self._autoplay = None
            return
        lid = self._autoplay_levels.pop(0)
        self.save_mgr.data["howto_seen"] = True
        self.load_and_play_level(lid)
        self._autoplay = [sorted(self.level.data.raw.get("ref_taps", [])), 0, False]
        print(f"[perf] autoplay level {lid}")

    def _autoplay_step(self, s):
        taps, i, revived = self._autoplay
        while i < len(taps) and taps[i] <= s.n:
            s.swap()
            self.taps.append(s.n)
            i += 1
        if not revived and s.n > 300:                  # one paid revive per level (the event players felt)
            revived = True
            self.save_mgr.data["diamonds"] = max(self.save_mgr.diamonds, 100)
            s.dead = True
            self._revive_now(s)
        self._autoplay = [taps, i, revived]

    def _install_ghost(self):
        """The ghost raced in this attempt: the world's best clean run of the level (named), else my own best."""
        self.ghost, self.ghost_name = None, None
        if not self.settings.get("ghost_race", False) or not self.level or self.endless_run is not None:
            return
        world = (getattr(self.online, "ghosts", None) or {}).get(self.level_id) or {}
        taps = None
        if world.get("taps") and world.get("id") != self.save_mgr.player_id:
            taps, self.ghost_name = world["taps"], world.get("name") or "#1"
        else:
            own = self.save_mgr.get_best_taps(self.level_id)
            if own and not self.save_mgr.get_best_assists(self.level_id):
                taps = own
        if not taps:
            return
        self.ghost = Sim(self.level.data)
        self.ghost_taps = sorted(taps)
        self.ghost_i = 0
        if self.sim is not None:                     # it arrived mid-attempt: catch up with the pair
            for _ in range(min(self.sim.n, 20000)):
                self._step_ghost()

    def _step_ghost(self):
        g = self.ghost
        if g is None or g.dead or g.won:
            return
        while self.ghost_i < len(self.ghost_taps) and self.ghost_taps[self.ghost_i] <= g.n:
            g.swap()
            self.ghost_i += 1
        g.step()

    _HINT_KEYS = (("shrink", "hint_shrink"), ("grow", "hint_grow"), ("shield", "hint_shield"), ("boost", "hint_boost"))

    def _update_hints(self, dt):
        """Show a one-time tip the first time the pair approaches each kind of power-up gate."""
        s = self.sim
        if self.hint:
            key, left = self.hint
            left -= dt
            self.hint = (key, left) if left > 0 else None
            return
        self.hint_cool -= dt
        if self.hint_cool > 0 or s.swaps == 0:
            return
        d = s.lvl
        px, py = s.pivot.x, s.pivot.y
        cands = (("shrink", d.shrink), ("grow", d.growth), ("shield", d.shields), ("boost", d.boost))
        for kind, zs in cands:
            key = "hint_" + kind
            if self.save_mgr.hint_seen(key):
                continue
            for z in zs:
                if abs(z[1] - py) < 560 and abs(z[0] - px) < 560:
                    self.save_mgr.mark_hint(key)
                    self.hint = (key, 4.2)
                    self.hint_cool = 1.0
                    return

    def _update_tension(self, dt):
        """Subliminal, gradual end-of-level pressure: the pulse quickens, cyber-ticks accelerate,
        and screen edges glow smoothly and imperceptibly as the hidden speed-up builds ('hissettirmeden yavaş yavaş').
        When a chaser wall is active, tension surges to create thrilling chase pressure."""
        s = self.sim
        self.play_clock += dt
        prog = max(s.max_progress, s.progress)
        # Smooth continuous exponential curve matching the secret game acceleration
        base_tension = max(0.0, min(1.0, (prog ** 2.2)))

        # Wall active pursuit: tension surges while the wall is in hot pursuit!
        if s and s.chaser_active:
            self.tension = max(base_tension, 0.76)
        else:
            self.tension = base_tension

        if not s.dead and not s.won and self.tension > 0.10:
            # 1. Accelerating heartbeat (smoothly speeds up from 60 BPM to ~250 BPM, volume builds gradually)
            self.heart_timer -= dt
            if self.heart_timer <= 0:
                h_vol = min(0.72, max(0.05, (self.tension - 0.10) * 0.75))
                self.audio.play_sfx("sfx_heartbeat", volume=h_vol)
                self.heart_timer = max(0.18, 1.10 - 0.88 * self.tension)

            # 2. Subliminal accelerating cyber-tick rhythm (blends seamlessly into music, accelerating the perceived tempo)
            if self.tension > 0.22:
                self.tick_timer -= dt
                if self.tick_timer <= 0:
                    t_vol = min(0.35, max(0.04, (self.tension - 0.22) * 0.40))
                    self.audio.play_sfx("sfx_tick", volume=t_vol)
                    self.tick_timer = max(0.11, 0.28 - 0.15 * self.tension)

    _SECTOR_TRACK = {1: "bgm_synthwave", 2: "bgm_s2", 3: "bgm_s3", 4: "bgm_s4", 5: "bgm_s5"}

    def _sync_music(self):
        """Menu lullaby in menus, uninterrupted sector synthwave track in game (seamless continuous loop)."""
        st = self.state
        in_level = st in ("playing", "dying", "failed", "victory", "paused") or (st == "settings" and self.prev_state == "paused")
        sector = sector_for_stage(self.endless_run.stage) if self.endless_run is not None else (self.level.sector if self.level else 1)
        want = self._SECTOR_TRACK.get(sector, "bgm_synthwave") if (in_level and self.level) else "bgm_menu"
        if want != self._music_track:
            self._music_track = want
            self.audio.play_music(want, loop=True, fade_ms=600)

    def _check_achievements(self):
        # ~25 achievement values (star totals over every level ...) do not need a check every frame
        if self.ui_time < getattr(self, "_ach_next", 0.0):
            return
        self._ach_next = self.ui_time + 0.25
        sm = self.save_mgr
        if not self._ach_synced:                                   # skins of achievements earned in older versions
            self._ach_synced = True
            for aid in ach_mod.unlocked_ids(sm):
                if aid in skin_catalog.ACH_REWARD:
                    sm.grant_skin(skin_catalog.ACH_REWARD[aid])
        for a in ach_mod.check(sm):
            sm.earn("ach", a[0], 5)
            sub = ach_mod.desc(a)
            sid = skin_catalog.ACH_REWARD.get(a[0])
            if sid:
                sm.grant_skin(sid)
                sub = f"{sub}  •  + {SKINS[sid]['name']}"
            self.toasts.append([ach_mod.title(a) + f"  •  +5 {t('diamonds').upper()}", sub, 4.0])
            self.audio.play_sfx("sfx_coin")

    def _draw_toasts(self, f):
        if not self.toasts or self.state == "intro":
            return
        title, sub, left = self.toasts[0]
        if sub and self.state in ("playing", "dying", "howto"):
            return
        k = min(1.0, left / 0.35, (4.0 - left) / 0.35)
        w = 700
        # the card is rendered once per toast (colour-keyed corners) and then only copied while it slides / waits
        key = (title, sub, ui.get_language())
        cached = getattr(self, "_toast_img", None)
        if cached is None or cached[0] != key:
            img = pygame.Surface((w, 116)).convert()
            img.fill((255, 0, 255))
            r0 = img.get_rect()
            pygame.draw.rect(img, (10, 22, 46), r0, border_radius=28)
            pygame.draw.rect(img, (0, 214, 255), r0, 3, border_radius=28)
            ui.draw_vector_star(img, 62, r0.centery, 26)
            ui.draw_text(img, t("ach_toast"), 22, (120, 230, 255), (120, 26), anchor="midleft", bold=False, bg=(10, 22, 46))
            ui.draw_text(img, title, 36, (255, 255, 255), (120, 62), anchor="midleft", max_w=w - 160, bg=(10, 22, 46))
            ui.draw_text(img, sub, 21, (200, 195, 235), (120, 94), anchor="midleft", bold=False, max_w=w - 160, bg=(10, 22, 46))
            img.set_colorkey((255, 0, 255), pygame.RLEACCEL)
            cached = self._toast_img = (key, img)
        f.blit(cached[1], (VW // 2 - w // 2, int(-130 + 170 * max(0.0, k))))

    def update(self, dt, v_mouse):
        self.ui_time += dt
        if self.state == "menu" and not getattr(self, "_autoplay_started", False) and config.get("perf_autoplay"):
            self._autoplay_started = True
            self._start_autoplay()
        self.shop.poll()                              # store events (also purchases finished while in another screen)
        self._sync_music()
        self._check_achievements()
        self._sync_cloud()
        if self.online.gift_notice and self.state not in ("intro", "playing", "dying"):
            self.toasts.append([t("gift_title", n=self.online.gift_notice), t("gift_sub"), 4.5])
            self.online.gift_notice = 0
            self.audio.play_sfx("sfx_coin")
        if self.ui_time >= self._wallet_next and self.state not in ("playing", "dying"):
            self._wallet_next = self.ui_time + 180.0      # picks up gifts and retries earnings that were offline
            self.online.wallet_sync()
        if self.toasts and self.state != "intro" and not (self.toasts[0][1] and self.state in ("playing", "dying", "howto")):
            self.toasts[0][2] -= dt
            if self.toasts[0][2] <= 0:
                self.toasts.pop(0)
        self._maybe_login_popup()
        st = self.state
        if getattr(self, "_perf_shop", False) and st == "shop":      # test hook: keep flinging the shop list
            sc = self.shop_ui._scroll
            if abs(sc.vel) < 1.0:
                sc.vel = 38.0 if sc.y < 600 else -38.0
        if st == "playing":
            self.update_gameplay(dt)
            self._update_camera(dt)
        elif st == "dying":
            self.particles.update(dt * 60.0)
            self.death_timer -= dt
            if self.death_timer <= 0 and self.endless_run is not None:
                self._endless_died()
            elif self.death_timer <= 0:
                self.state = "failed"
                s = self.sim
                self.failure_modal = ui.FailureModal(
                    self.level_id, int(s.max_progress * 100), s.stars_collected, s.combo_mult, self.attempts,
                    on_retry=self.retry_after_fail, on_menu=self.open_menu,
                    on_levels=self.open_level_select,
                    save_mgr=self.save_mgr, shop=self.shop, on_revive=self.revive_run, revive_cost=REVIVE_COST,
                    on_endless=self.open_endless if self.save_mgr.endless_unlocked else None)
        else:
            self.particles.update(dt * 60.0)
            if st == "menu":
                self.menu_ui.update(v_mouse, dt * 60.0)
            elif st == "levels":
                self.level_select_ui.update(v_mouse, dt * 60.0)
            elif st == "leaderboard":
                self.leaderboard_ui.update(v_mouse, dt * 60.0)
            elif st == "skins":
                self.skin_ui.update(v_mouse, dt * 60.0)
            elif st == "shop":
                self.shop_ui.update(v_mouse, dt * 60.0)
            elif st == "featured":
                self.featured_ui.update(v_mouse, dt * 60.0)
            elif st == "howto":
                self.howto_ui.update(v_mouse, dt * 60.0)
            elif st == "intro":
                self._update_intro(dt, v_mouse)
            elif st == "achievements":
                self.ach_ui.update(v_mouse, dt * 60.0)
            elif st == "daily":
                self.daily_ui.update(v_mouse, dt * 60.0)
            elif st == "profile" and self.profile_modal:
                self.profile_modal.update(v_mouse, dt * 60.0)
            elif st == "recovery" and self.recovery_modal:
                self.recovery_modal.update(v_mouse, dt * 60.0)
            elif st == "login" and self.login_modal:
                self.login_modal.update(v_mouse, dt * 60.0)
            elif st == "paused":
                self.pause_modal.update(v_mouse, dt * 60.0)
            elif st == "settings":
                self.settings_modal.update(v_mouse, dt * 60.0)
            elif st == "failed" and self.failure_modal:
                self.failure_modal.update(v_mouse, dt * 60.0)
            elif st == "victory" and self.victory_modal:
                self.victory_modal.update(v_mouse, dt * 60.0)
        if st in ("dying", "failed", "victory"):
            self._update_camera(dt)
        self.online.poll()
        if getattr(self.online, "ghost_new", False):
            self.online.ghost_new = False
            if (self.level and self.state in ("playing", "paused", "howto") and self.endless_run is None
                    and self.sim is not None and self.sim.n < 400 and not self.ghost_name):
                self._install_ghost()                # the world #1 replaces my own best early in the attempt

    def _update_camera(self, dt):
        if not self.sim:
            return
        target = self._camera_target()
        self.cam_y += (target - self.cam_y) * (1.0 - math.exp(-7.0 * dt))

    # ------------------------------------------------------------------ events
    def handle_event(self, event):
        st = self.state
        if event.type == pygame.QUIT:
            self.running = False
            return
        if event.type == pygame.VIDEORESIZE and not self.scaled:
            self.win_w, self.win_h = event.w, event.h
            return
        if event.type in (pygame.WINDOWFOCUSLOST, getattr(pygame, "APP_WILLENTERBACKGROUND", -1)):
            if st == "playing":
                self.state = "paused"
            self._sync_cloud(now=True)                  # the app may be closed from the background
            return
        if st == "intro":                               # any tap / key plays the rest of the intro fast
            if event.type in (pygame.MOUSEBUTTONDOWN, pygame.KEYDOWN):
                self.intro_speed = 4.0
            return
        if event.type == pygame.KEYDOWN:
            if getattr(event, "repeat", False):
                return
            k = event.key
            if k == pygame.K_F11:
                self.toggle_fullscreen()
            elif k == pygame.K_m and st not in ("profile", "recovery"):
                self.audio.toggle_mute()
            elif k in (pygame.K_ESCAPE, pygame.K_AC_BACK if hasattr(pygame, "K_AC_BACK") else -1):
                if st == "playing":
                    self.state = "paused"
                    self._click()
                elif st == "paused":
                    self.resume_game()
                elif st == "shop":
                    self.open_featured()
                elif st == "featured":
                    self.open_menu()
                elif st in ("achievements", "daily"):
                    self.open_menu()
                elif st == "failed" and isinstance(self.failure_modal, ui.EndlessReviveModal):
                    self._endless_over()          # back on the revive offer = finish the climb (it is still sent)
                elif st in ("leaderboard", "skins", "levels", "failed", "victory"):
                    self.open_menu()
                elif st == "settings":
                    self.close_settings()
                elif st == "profile" and self.save_mgr.is_profile_set:
                    self.profile_modal.close()
                    self.close_profile()
                elif st == "recovery":
                    self.close_recovery()
                elif st == "login":
                    self.close_login_reward()
                elif st == "menu" and self.android:
                    self.running = False          # Android back button on the main menu leaves the app
                return
            elif k == pygame.K_p and st in ("playing", "paused"):
                # P is only a desktop pause shortcut. As a global back key it
                # closed the profile modal while names such as HOPWATOR were typed.
                if st == "playing":
                    self.state = "paused"
                    self._click()
                else:
                    self.resume_game()
                return
            elif k == pygame.K_r and st in ("playing", "dying", "paused", "failed"):
                if st == "failed" or st == "dying":
                    self.retry_after_fail()
                else:
                    self.restart_level()
                return
            elif k in (pygame.K_SPACE, pygame.K_w, pygame.K_UP, pygame.K_RETURN):
                if st == "playing":
                    self.swap_pivot()
                elif st == "failed":
                    self.retry_after_fail()
                elif st == "howto":
                    self.howto_ui._advance()
                return

        if hasattr(event, "pos") and (not self.scaled or self.safe_top):
            vx, vy = self.to_virtual(event.pos)
            d = dict(event.__dict__)
            d["pos"] = (int(vx), int(vy))
            event = pygame.event.Event(event.type, d)

        if st == "playing":
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                hud = self.endless_hud if self.endless_run is not None else self.hud
                if hud.hit_pause(event.pos):
                    self.state = "paused"
                    self._click()
                elif hud.hit_shield(event.pos):
                    self.use_hud_shield()
                elif 0 <= event.pos[0] < VW and HUD_H < event.pos[1] < HUD_H + self.view_h:
                    self.swap_pivot()
            return

        action = None
        if st == "menu":
            action = self.menu_ui.handle_event(event)
        elif st == "levels":
            action = self.level_select_ui.handle_event(event)
        elif st == "leaderboard":
            action = self.leaderboard_ui.handle_event(event)
        elif st == "skins":
            action = self.skin_ui.handle_event(event)
        elif st == "shop":
            action = self.shop_ui.handle_event(event)
        elif st == "featured":
            action = self.featured_ui.handle_event(event)
        elif st == "howto":
            action = self.howto_ui.handle_event(event)
        elif st == "achievements":
            action = self.ach_ui.handle_event(event)
        elif st == "daily":
            action = self.daily_ui.handle_event(event)
        elif st == "profile" and self.profile_modal:
            self.profile_modal.handle_event(event)
        elif st == "recovery" and self.recovery_modal:
            self.recovery_modal.handle_event(event)
        elif st == "login" and self.login_modal:
            action = self.login_modal.handle_event(event)
        elif st == "paused":
            action = self.pause_modal.handle_event(event)
        elif st == "settings":
            action = self.settings_modal.handle_event(event)
        elif st == "failed" and self.failure_modal:
            action = self.failure_modal.handle_event(event)
        elif st == "victory" and self.victory_modal:
            action = self.victory_modal.handle_event(event)
        if callable(action):
            action()

    # ------------------------------------------------------------------ rendering
    def _modal_for(self, st, in_play):
        """The modal drawn over a frozen scene in this state, or None."""
        if in_play:
            return {"paused": self.pause_modal, "howto": self.howto_ui, "victory": self.victory_modal,
                    "failed": self.failure_modal}.get(st)
        if st == "profile":
            return self.profile_modal
        if st == "recovery":
            return self.recovery_modal
        if st == "login":
            return self.login_modal
        if st == "settings":
            return self.settings_modal
        return None

    def draw(self):
        f = self.frame
        st = self.state
        in_play = st in ("playing", "dying", "paused", "victory", "failed", "howto") and self.level and self.sim
        # An open modal sits on a dimmed scene that stops changing once the death/victory effects have played:
        # capture that dimmed frame once and afterwards only copy it and draw the modal.
        if st != getattr(self, "_draw_state", None):
            self._draw_state, self._state_t0 = st, self.ui_time
            self._state_serial = getattr(self, "_state_serial", 0) + 1
        modal = self._modal_for(st, in_play)
        freeze_key = None
        # the scene behind keeps moving for a moment (victory warp 1.6 s, the last death particles) before it freezes
        settle = 1.8 if st == "victory" else (0.5 if st == "failed" else 0.0)
        if modal is not None and self.ui_time - self._state_t0 >= settle:
            freeze_key = (self._state_serial, id(modal), ui.get_language(), self.prev_state, self.prev_profile_state)
            frozen = getattr(self, "_frozen_bg", None)
            if frozen is not None and frozen[0] == freeze_key:
                # The modal itself only changes when a button is pressed or its content changes (ui.modal_sig):
                # meanwhile the finished frame (dimmed scene + modal) is shown as it is - one copy per frame.
                sig = ui.modal_sig(modal)
                cached = getattr(self, "_modal_frame", None)
                if sig is not None and cached is not None and cached[0] == (freeze_key, sig):
                    f.blit(cached[1], (0, 0))
                else:
                    f.blit(frozen[1], (0, 0))
                    ui.set_dim_mode("replay")
                    try:
                        modal.draw(f)
                    finally:
                        ui.set_dim_mode(None)
                    if sig is not None:
                        surf = cached[1] if cached is not None and cached[1].get_size() == f.get_size() else f.copy()
                        if surf is not f:
                            surf.blit(f, (0, 0))
                        self._modal_frame = ((freeze_key, sig), surf)
                self._draw_toasts(f)
                self._present()
                return
            ui.set_dim_mode("capture")
        try:
            self._draw_scene(f, st, in_play)
        finally:
            snap = ui.take_dim_snapshot()
            ui.set_dim_mode(None)
        if freeze_key is not None and snap is not None:
            self._frozen_bg = (freeze_key, snap)
        self._draw_toasts(f)
        self._present()

    def _draw_scene(self, f, st, in_play):
        if st == "intro":
            self._draw_intro(f)
            return
        screen = self._list_screens().get(st) if not in_play else None
        if screen is not None:
            self._draw_list_screen(f, st, screen)
            return
        if in_play and self.level.height >= self.view_h:
            # the arena background covers everything but the footer strip: skip the full-screen clear + starfield
            f.fill(BG_DARK, (0, HUD_H + self.view_h, VW, self.vh - HUD_H - self.view_h))
        elif st == "menu" and self.menu_ui.enter >= 1.0:
            self.menu_ui.draw_fast(f, get_skin(self.save_mgr.equipped_skin), self.menu_bg, self.menu_life, self.ui_time)
            return
        elif st == "menu":
            f.blit(self.menu_bg, (0, 0))
            self.menu_life.draw(f, self.ui_time)
        elif st in ("levels", "leaderboard", "skins", "shop", "achievements", "daily") or (st == "settings" and self.prev_state != "paused") or st in ("profile", "recovery", "login"):
            f.blit(self.menu_bg_dark, (0, 0))
            self.menu_life.draw(f, self.ui_time)
        else:
            f.fill(BG_DARK)
            self.particles.draw_starfield(f)
        skin = get_skin(self.save_mgr.equipped_skin)
        if in_play:
            self._draw_gameplay(f, skin)
            if st == "paused":
                self.pause_modal.draw(f)
            elif st == "howto":
                self.howto_ui.draw(f)
            elif st == "victory" and self.victory_modal:
                self._draw_warp(f, self.victory_modal.anim / 60.0)
                self.victory_modal.draw(f)
            elif st == "failed" and self.failure_modal:
                self.failure_modal.draw(f)
        elif st == "menu":
            self.menu_ui.draw(f, skin, backdrop=self.menu_bg)
        elif st == "levels":
            self.level_select_ui.draw(f)
        elif st == "leaderboard":
            self.leaderboard_ui.draw(f)
        elif st == "skins":
            self.skin_ui.draw(f)
        elif st == "shop":
            self.shop_ui.draw(f)
        elif st == "achievements":
            self.ach_ui.draw(f)
        elif st == "daily":
            self.daily_ui.draw(f)
        elif st == "profile":
            if self.prev_profile_state == "leaderboard":
                self.leaderboard_ui.draw(f)
            else:
                self.menu_ui.draw(f, skin, backdrop=self.menu_bg_dark)
            if self.profile_modal:
                self.profile_modal.draw(f)
        elif st == "login":
            self.menu_ui.draw(f, skin, backdrop=self.menu_bg_dark)
            if self.login_modal:
                self.login_modal.draw(f)
        elif st == "recovery":
            if self.prev_profile_state == "leaderboard":
                self.leaderboard_ui.draw(f)
            else:
                self.menu_ui.draw(f, skin, backdrop=self.menu_bg_dark)
            if self.recovery_modal:
                self.recovery_modal.draw(f)
        if st == "settings":
            if self.prev_state == "paused" and self.level and self.sim:
                self._draw_gameplay(f, skin)
            else:
                self.menu_ui.draw(f, skin, backdrop=self.menu_bg_dark)
            self.settings_modal.draw(f)

    def _list_screens(self):
        return {"levels": self.level_select_ui, "leaderboard": self.leaderboard_ui, "skins": self.skin_ui,
                "shop": self.shop_ui, "achievements": self.ach_ui, "daily": self.daily_ui, "featured": self.featured_ui}

    def _draw_list_screen(self, f, st, screen):
        """List screens are mostly still: while nothing on them changes (scroll, press, selection, save, network)
        the finished frame is copied; only the animated preview (shop / skins) is drawn on top every frame."""
        sm, on = self.save_mgr, self.online
        board = on.boards.get(self.leaderboard_ui.scope) if st == "leaderboard" else None
        extra = (sm.rev, sm.diamonds, sm.equipped_skin, len(sm.data.get("unlocked_skins", [])), st,
                 on.status, id(board), on.is_loading(self.leaderboard_ui.scope) if st == "leaderboard" else False,
                 self.shop.current_message() if st in ("shop", "featured") else None,
                 screen.sig_extra() if hasattr(screen, "sig_extra") else None)
        sig = ui.screen_sig(screen, extra)
        cache = getattr(self, "_screen_frame", None)
        if cache is None or cache[0] != sig or cache[1].get_size() != f.get_size():
            f.blit(self.menu_bg_dark, (0, 0))
            self.menu_life.draw(f, self.ui_time)
            screen._static = True
            try:
                screen.draw(f)
            finally:
                screen._static = False
            surf = cache[1] if cache is not None and cache[1].get_size() == f.get_size() else pygame.Surface(f.get_size()).convert()
            surf.blit(f, (0, 0))
            self._screen_frame = (sig, surf)
        else:
            f.blit(cache[1], (0, 0))
        if hasattr(screen, "draw_dynamic"):
            screen.draw_dynamic(f)

    # ------------------------------------------------------------------ start-up intro
    def _update_intro(self, dt, v_mouse):
        self.menu_ui.update(v_mouse, dt * 60.0)
        self.intro_t += dt * self.intro_speed
        self.menu_ui.set_enter((self.intro_t - 1.1) / 0.85)
        if self.intro_t >= INTRO_LEN:
            self.menu_ui.set_enter(1.0)
            self.state = self._after_intro
            self._intro_buf = None

    def _draw_intro(self, f):
        """At most one full-screen blend per frame: the space backdrop fades in over the splash colour, then the whole
        menu (its cached plate) fades in over the backdrop; the logo glides and the orbs spin up on top."""
        t = self.intro_t
        mu = self.menu_ui
        skin = get_skin(self.save_mgr.equipped_skin)
        move = _smooth((t - 0.30) / 0.80)          # logo glides from the splash spot to its menu spot
        bgk = _smooth((t - 0.25) / 0.90)           # flat splash colour -> space backdrop
        orbit = _smooth((t - 0.55) / 0.70)         # the orb pair spins up around the logo
        uik = _smooth((t - 1.10) / 0.85)           # everything else fades in
        if uik >= 1.0:
            f.blit(mu.plate(skin, self.menu_bg), (0, 0))
        elif uik > 0.0:
            f.blit(self.menu_bg, (0, 0))
            plate = mu.plate(skin, self.menu_bg)
            plate.set_alpha(int(255 * uik))
            f.blit(plate, (0, 0))
            plate.set_alpha(None)
        elif bgk >= 1.0:
            f.blit(self.menu_bg, (0, 0))
        else:
            f.fill(BG_DARK)
            if bgk > 0.0:
                if getattr(self, "_intro_bg", None) is None:
                    self._intro_bg = self.menu_bg.copy()     # own copy: menu_bg also feeds the button tile cache
                self._intro_bg.set_alpha(int(255 * bgk))
                f.blit(self._intro_bg, (0, 0))
        # loading dots of the splash image fade out (same place / colours as in assets/presplash.png)
        sy = (self.vh + self.safe_bottom - self.safe_top) // 2 - 80    # splash logo spot, in frame coordinates
        dots = 1.0 - _smooth(t / 0.30)
        if dots > 0.0:
            for i, c in enumerate(((0, 230, 255), (0, 150, 190), (0, 80, 110))):
                col = tuple(int(BG_DARK[j] + (c[j] - BG_DARK[j]) * dots) for j in range(3))
                pygame.draw.circle(f, col, (VW // 2 + (i - 1) * 40, sy + 187), 9)
        ex, ey = mu.title_center()
        # once the plate shows, it carries the logo (by then at its menu spot): only the orbs are drawn on top
        mu.draw_title(f, skin, (ex, int(sy + (ey - sy) * move)), orbit_k=orbit, sparkles=orbit > 0.6, subtitle=False,
                      logo=uik <= 0.0)
        if t >= INTRO_LEN - 0.05:
            self._intro_bg = None

    def _draw_warp(self, f, k):
        """Hyperspace burst behind the victory card: radial streaks that fly outwards for ~1.5 s."""
        if k > 1.6 or not self.level:
            return
        cx, cy = VW // 2, int(self.vh * 0.42)
        acc = ui.SECTOR_COL.get(self.level.sector, ui.ACCENT_CYAN)
        fade = max(0.0, 1.0 - k / 1.6)
        for i in range(64):
            a = i * 6.283 / 64 + (i % 7) * 0.05
            d0 = 40 + 1500 * (k * (0.6 + 0.4 * ((i * 37) % 10) / 10.0)) ** 1.5
            d1 = d0 + 60 + 260 * k
            col = tuple(int(c * fade) for c in acc)
            pygame.draw.line(f, col, (cx + math.cos(a) * d0, cy + math.sin(a) * d0), (cx + math.cos(a) * d1, cy + math.sin(a) * d1), 2)

    def _draw_gameplay(self, f, skin):
        s = self.sim
        lvl = self.level
        view = f.subsurface((0, HUD_H, VW, self.view_h))
        alpha = 1.0
        if self.state == "playing" and self.resume_timer <= 0.0:
            alpha = max(0.0, min(1.0, self.accum / SIM_DT))
        t_render = max(0.0, s.t - (1.0 - alpha) * SIM_DT)
        oy = self.cam_y
        boost = s.smooth / max(0.01, lvl.data.speed)
        lvl.draw(view, t_render, s, oy, boost)

        g = self.ghost
        if g is not None and self.state in ("playing", "paused") and not g.won:
            a, b = g.orbs
            ga = (int(a.x), int(a.y - oy))
            gb = (int(b.x), int(b.y - oy))
            gc = tuple(int(c * 0.55) for c in skin["color2"])
            pygame.draw.line(view, tuple(int(c * 0.35) for c in skin["tether_color"][:3]), ga, gb, 2)
            for pt, r_, col in ((ga, a.r, tuple(int(c * 0.5) for c in skin["color1"])), (gb, b.r, gc)):
                pygame.draw.circle(view, col, pt, int(r_), 2)
            if self.ghost_name:
                piv = ga if g.piv == 0 else gb
                ui.draw_text(view, "#1 " + self.ghost_name, 18, (190, 200, 230), (piv[0], piv[1] - 34), bold=False)
        if self.state not in ("dying", "failed"):
            p0, p1 = s.orbs
            q0, q1 = self.prev_pos
            pos = [(q0[0] + (p0.x - q0[0]) * alpha, q0[1] + (p0.y - q0[1]) * alpha - oy),
                   (q1[0] + (p1.x - q1[0]) * alpha, q1[1] + (p1.y - q1[1]) * alpha - oy)]
            tt = s.t
            draw_tether(view, pos[0], pos[1], skin, tt)
            is_p0 = s.piv == 0
            # A clean orbit marker distinguishes the fixed anchor from the
            # moving orb even when a skin uses similar colors for both.
            anchor = pos[s.piv]
            radius = int(s.pivot.r + 12)
            ring = pygame.Rect(0, 0, radius * 2, radius * 2)
            ring.center = (int(anchor[0]), int(anchor[1]))
            phase = tt * 1.6 * s.rot_sign
            for offset in (0, math.pi):
                pygame.draw.arc(view, (190, 235, 255), ring,
                                phase + offset, phase + offset + 1.1, 2)
            draw_orb(view, pos[0], p0.r, skin["color1"], skin["glow1"], is_p0, skin, tt)
            draw_orb(view, pos[1], p1.r, skin["color2"], skin["glow2"], not is_p0, skin, tt)
            if s.protected or s.guard:                 # s.guard: revived, shielded until the next tap
                life = max(0.25, min(1.0, s.grace / 0.65)) if s.grace > 0 else 0.85
                self.particles.draw_spawn_shield(view, pos[0], pos[1], tt, life)
            if s.invuln > 0 or s.barrier_t > 0:
                self.particles.draw_spawn_shield(view, pos[0], pos[1], tt, min(1.0, max(s.invuln, s.barrier_t) / 0.5))
        self.particles.draw(view, oy)

        # rewind visual overlay (holographic cyan scanlines + vector rewind arrows)
        if self.rewind_fx_t > 0.0:
            # plain thin lines straight onto the view (a full-view alpha layer cost more than the whole frame on phones)
            for sy in range(int(self.rewind_fx_t * 120) % 24, self.view_h, 24):
                pygame.draw.line(view, (0, 70, 90), (0, sy), (VW, sy), 1)
            pygame.draw.rect(view, (0, 150, 190), (0, 0, VW, self.view_h), 4)

            rw, rh = 520, 76
            r_rect = pygame.Rect(VW // 2 - rw // 2, 70, rw, rh)
            pygame.draw.rect(view, (8, 20, 42), r_rect, border_radius=20)
            pygame.draw.rect(view, (0, 240, 255), r_rect, 3, border_radius=20)
            tx = r_rect.centerx - 160
            ty = r_rect.centery
            for off in (0, 18):
                pygame.draw.polygon(view, (0, 240, 255), [(tx + off + 6, ty - 12), (tx + off - 6, ty), (tx + off + 6, ty + 12)])
            ui.draw_text(view, t("rewinding"), 32, (0, 240, 255), (r_rect.centerx + 16, r_rect.centery), bold=True, bg=(8, 20, 42))

        # tension: red edge glow that swells with the pulse near the end (the speed-up itself is never shown)
        if self.tension > 0.02 and self.state == "playing":
            pulse = 0.55 + 0.45 * math.sin(self.play_clock * (4.0 + 6.0 * self.tension))
            al = int(150 * self.tension * pulse)
            if al > 4:
                for grad, pos in self.vig.values():
                    grad.draw(view, pos, al / 255.0)

        run = self.endless_run
        if run is not None and self.state == "playing" and s.swaps == 0 and s.t < 3.2:
            k = min(1.0, s.t / 0.35, (3.2 - s.t) / 0.7)
            fade = lambda c: tuple(int(v * max(0.0, k)) for v in c)
            y0 = int(self.view_h * 0.24)
            self.intro_band.draw(view, (0, y0 - 52), int(170 * max(0.0, k)) / 255.0)
            ui.draw_text(view, t("endless_title"), 66, fade((255, 255, 255)), (VW // 2, y0 + 62), max_w=820, bg="key")
            ui.draw_text(view, t("endless_card_sub"), 28, fade((200, 210, 235)), (VW // 2, y0 + 124), max_w=820, bold=False, bg="key")
        # level intro card (first attempt): sector, title, boss tag
        if run is None and self.state == "playing" and self.attempts == 1 and s.swaps == 0 and s.t < 3.2:
            k = min(1.0, s.t / 0.35, (3.2 - s.t) / 0.7)
            col = ui.SECTOR_COL.get(lvl.sector, ui.ACCENT_CYAN)
            fade = lambda c: tuple(int(v * max(0.0, k)) for v in c)
            y0 = int(self.view_h * 0.24)
            self.intro_band.draw(view, (0, y0 - 52), int(170 * max(0.0, k)) / 255.0)
            ui.draw_text(view, f"{t('sector')} {lvl.sector}  •  {lvl.sector_title}", 30, fade(col), (VW // 2, y0), bg="key")
            ui.draw_text(view, lvl.level_title, 66, fade((255, 255, 255)), (VW // 2, y0 + 62), max_w=820, bg="key")
            if self.level_id % 20 == 0:
                ui.draw_text(view, t("boss_tag"), 34, fade((255, 90, 110)), (VW // 2, y0 + 128), bg="key")

        # arrow towards the portal when it is off-screen (tall levels)
        gx, gy = lvl.data.end
        gy -= oy
        if run is None and (gy < 30 or gy > self.view_h - 30):
            up = gy < 30
            ax = max(70, min(VW - 70, gx))
            ay = 46 if up else self.view_h - 46
            k = -1 if up else 1
            pulse = 0.6 + 0.4 * math.sin(s.t * 5)
            col = (int(80 * pulse + 60), int(200 * pulse + 40), 255)
            for off in (0, 16):
                yy = ay + k * off * -1
                pygame.draw.lines(view, col, False, [(ax - 22, yy + k * 8), (ax, yy - k * 8), (ax + 22, yy + k * 8)], 5)

        # active shrink / growth effect (timed) + contextual tip
        if s.fx_t > 0.0 and self.state == "playing":
            shrink = s.orbs[0].tr < 12
            col = (90, 200, 255) if shrink else (40, 255, 130)
            bw = 300
            bx, by = VW // 2 - bw // 2, 16
            pygame.draw.rect(view, (10, 18, 34), (bx - 3, by - 3, bw + 6, 26), border_radius=13)
            frac = max(0.0, min(1.0, s.fx_t / 10.0))
            pygame.draw.rect(view, col, (bx, by, int(bw * frac), 20), border_radius=10)
            # whole seconds: the label is rasterised 10 times per effect instead of 100, and copied, not blended
            ui.draw_text(view, t("fx_shrink" if shrink else "fx_grow") + f"  {math.ceil(s.fx_t)}s", 20, (235, 245, 255),
                         (VW // 2, by + 10), bg="key")
        if self.hint and self.state == "playing":
            key, left = self.hint
            k = min(1.0, left / 0.4, (4.2 - left) / 0.3)
            band = getattr(self, "_hint_band", None)
            if band is None:
                band = self._hint_band = pygame.Surface((VW, 92)).convert()
                band.fill((6, 12, 26))
            by = int(self.view_h * 0.70)
            if k >= 0.99:                                   # most of the 4 s: a plain opaque band + opaque text
                view.blit(band, (0, by))
                ui.draw_text(view, t(key), 30, (255, 235, 150), (VW // 2, by + 46), max_w=840, bg=(6, 12, 26))
            else:                                           # the short fade in / out
                band.set_alpha(int(220 * max(0.0, k)))
                view.blit(band, (0, by))
                band.set_alpha(None)
                ui.draw_text(view, t(key), 30, tuple(int(c * max(0.0, k)) for c in (255, 235, 150)), (VW // 2, by + 46),
                             max_w=840, bg="key")

        # first-time tap hint
        if run is None and self.state == "playing" and s.swaps == 0 and self.level_id <= 3 and self.attempts <= 2:
            pulse = 0.65 + 0.35 * math.sin(s.t * 6)
            col = tuple(int(c * pulse) for c in (255, 255, 255))
            ui.draw_text(view, t("tap_hint"), 52, col, (VW // 2, self.view_h - 190), bg="key")
            ui.draw_text(view, t("tap_hint2"), 28, ui.TEXT_MUTED, (VW // 2, self.view_h - 140), bold=False, bg="key")

        # HUD
        if run is not None:
            wk = self.endless_week
            best = int(self.save_mgr.endless.get("best_all", 0)) if self.save_mgr.endless.get("v") == 2 else 0
            self.endless_hud.shield_stock = self.save_mgr.shield_stock
            self.endless_hud.shield_active = s.shields
            self.endless_hud.draw_endless(f, run.metres, max(run.points, best), s.shields, sector_for_stage(run.stage),
                                          points=run.points, stars=run.stars)
            self._draw_endless_banner(view)
            self.hud.draw_footer(f, HUD_H + self.view_h + FOOT_H // 2, run.metres, s.t, s.swaps, s.combo_mult, s.near_count)
        else:
            self._draw_campaign_hud(f, s, lvl)
        if self.state == "playing" and self.resume_timer > 0.0:
            col = ui.SECTOR_COL.get(lvl.sector, ui.ACCENT_CYAN)
            card = pygame.Rect(VW // 2 - 170, self.view_h // 2 - 76, 340, 152)
            ui.panel(view, card, (12, 20, 36), col, 24)
            ui.draw_text(view, t("resume_ready"), 25, ui.TEXT_MUTED,
                         (card.centerx, card.y + 36), bg=(12, 20, 36))
            ui.draw_text(view, str(max(1, math.ceil(self.resume_timer / 0.4))),
                         64, ui.TEXT_WHITE, (card.centerx, card.y + 92), bg=(12, 20, 36))

    def _draw_endless_banner(self, view):
        b = getattr(self, "endless_banner", None)
        if not b:
            return
        title, sub, col, left, total = b
        age = total - left
        y = int(self.view_h * 0.30 - min(1.0, age / 0.18) * 20)          # slides up a little as it appears
        band = pygame.Rect(0, y - 58, VW, 116 if sub else 84)
        view.fill((8, 12, 22), band)
        pygame.draw.line(view, col, band.topleft, band.topright, 3)
        pygame.draw.line(view, col, band.bottomleft, band.bottomright, 3)
        ui.draw_text(view, title, 60, col, (VW // 2, y - 14 if sub else y - 16), bg=(8, 12, 22), max_w=VW - 60)
        if sub:
            ui.draw_text(view, sub, 26, (220, 228, 245), (VW // 2, y + 36), bold=False, bg=(8, 12, 22), max_w=VW - 60)

    def _draw_campaign_hud(self, f, s, lvl):
        self.hud.shield_stock = self.save_mgr.shield_stock
        self.hud.diamonds = self.save_mgr.diamonds
        self.hud.shield_active = s.shields
        score = s.star_pts + s.near_pts              # tapping itself earns nothing: fewer swaps score more at the end
        self.hud.draw(f, self.level_id, MAX_LEVELS, s.stars_collected, score, s.combo_mult, s.shields, s.swaps, s.t,
                      max(s.max_progress, s.progress), sector_title=f"{lvl.sector_title}", sector=lvl.sector,
                      attempts=self.attempts, title=lvl.level_title)
        self.hud.draw_footer(f, HUD_H + self.view_h + FOOT_H // 2, score, s.t, s.swaps, s.combo_mult, s.near_count)

    _EDGE_SOLID_STATES = ("playing", "dying", "paused", "victory", "failed", "howto", "intro")

    def _paint_edges(self):
        """Phones: fill the strips beside the camera cut-out and the gesture bar so the picture reaches the screen
        edges. Menus continue their space backdrop there; play screens continue the colour of the frame's own top /
        bottom row (the HUD bar, the footer). Only repainted when what belongs there changes."""
        if not self.frame_direct or not (self.safe_top or self.safe_bottom):
            return
        st = self.state
        if st in self._EDGE_SOLID_STATES or (st == "settings" and self.prev_state == "paused"):
            f = self.frame
            top = tuple(pygame.transform.average_color(f, (0, 0, VW, 2))[:3])
            bottom = tuple(pygame.transform.average_color(f, (0, self.vh - 2, VW, 2))[:3])
            key = ("solid", top, bottom)
        else:
            key = ("art", "bright" if st == "menu" else "dark")
        if key == self._edge_key:
            return
        self._edge_key = key
        w, top_y, bot_y = self.window, 0, self.safe_top + self.vh
        if key[0] == "solid":
            if self.safe_top:
                w.fill(key[1], (0, top_y, VW, self.safe_top))
            if self.safe_bottom:
                w.fill(key[2], (0, bot_y, VW, self.safe_bottom))
        else:
            top, bottom = self._edge_art[key[1]]
            if top is not None:
                w.blit(top, (0, top_y))
            if bottom is not None:
                w.blit(bottom, (0, bot_y))

    def _present(self):
        f = self.frame
        self._paint_edges()
        if config.get("fps_overlay", False) or self.settings.get("show_fps", False):   # live frame rate, top-left
            ui.draw_text(f, f"{self.clock.get_fps():.0f} FPS", 26, (120, 255, 160), (8, 6), anchor="topleft", bg=(0, 0, 0))
        ox = oy = 0
        if self.settings.get("screen_shake", True):
            ox, oy = self.particles.get_shake_offset()
        if self.frame_direct:
            if ox or oy:
                # shake in place; the uncovered edge strips go black like the letterbox did before
                f.scroll(ox, oy)
                if ox:
                    f.fill((0, 0, 0), (0 if ox > 0 else VW + ox, 0, abs(ox), self.vh))
                if oy:
                    f.fill((0, 0, 0), (0, 0 if oy > 0 else self.vh + oy, VW, abs(oy)))
        elif self.scaled:
            self.window.fill((0, 0, 0))
            self.window.blit(f, (ox, oy))
        else:
            self.window.fill((0, 0, 0))
            scale = min(self.win_w / float(VW), self.win_h / float(self.vh))
            sw, sh = max(1, int(VW * scale)), max(1, int(self.vh * scale))
            img = f
            if (sw, sh) != f.get_size():
                if self._present_buffer is None or self._present_buffer.get_size() != (sw, sh):
                    self._present_buffer = pygame.Surface((sw, sh)).convert(f)
                # Android fallback must not filter millions of pixels on the CPU.
                transform = pygame.transform.scale if self.android else pygame.transform.smoothscale
                img = transform(f, (sw, sh), self._present_buffer)
            self.window.blit(img, ((self.win_w - sw) // 2 + int(ox * scale), (self.win_h - sh) // 2 + int(oy * scale)))
        pygame.display.flip()

    # ------------------------------------------------------------------ main loop
    def run(self):
        probe = _PerfProbe(self) if config.get("perf_log", False) else None
        # With vsync the flip itself paces the loop; an extra 60 fps cap on top of it fights the refresh and makes
        # frames alternate between one and two refreshes. If vsync turns out not to block (>240 fps), cap again.
        cap = 0 if self.vsync else 60
        fast = 0
        while self.running:
            ms = self.clock.tick(cap)
            if not cap:
                fast = fast + 1 if ms < 4 else 0
                if fast > 30:
                    cap = 60
            dt = min(0.05, ms / 1000.0)
            if self.android and self.settings.get("particles", True):
                # React gradually to sustained frame pressure. This only changes
                # newly emitted particles, so visuals never pop mid-effect.
                target = 0.45 if ms >= 24 else (0.70 if ms >= 19 else 1.0)
                self._render_quality += (target - self._render_quality) * 0.04
                self.particles.quality = self._render_quality
            if probe:
                probe.begin()
            v_mouse = self.to_virtual(pygame.mouse.get_pos())
            for event in pygame.event.get():
                self.handle_event(event)
            self.update(dt, v_mouse)
            if probe:
                probe.mid()
            self.draw()
            if probe:
                probe.end()
        self.save_mgr.save()
        pygame.quit()
        sys.exit(0)


def _smooth(k):
    """Ease-in-out on 0..1 (clamped)."""
    k = max(0.0, min(1.0, k))
    return k * k * (3.0 - 2.0 * k)


def _settle_gc():
    """Collect garbage at a calm moment and move every surviving object out of the collector's reach (gc.freeze),
    so the periodic full collections during play only scan what the current attempt allocated - no multi-ms
    pauses from walking the whole heap (level data, caches, fonts) mid-game."""
    gc.collect()
    if hasattr(gc, "freeze"):
        gc.freeze()


gc.set_threshold(2000, 20, 20)


class _Gradient:
    """A one-dimensional alpha ramp (edge glow, fading band) drawn as thin opaque strips, each with its own
    surface alpha. Same look as a per-pixel-alpha surface faded with set_alpha, but that combination takes
    pygame's slowest blend path - these strips take the fast one."""

    def __init__(self, color, length, thickness, alpha_at, columns, step=3):
        self.columns = columns                    # True: the ramp runs along x (strips are columns)
        self.strips = [(o, alpha_at(min(length - 1, o + step // 2))) for o in range(0, length, step)]
        self.surf = pygame.Surface((step, thickness) if columns else (thickness, step)).convert()
        self.surf.fill(color)

    def draw(self, dst, pos, mult):
        """mult (0..1) scales the ramp like surface.set_alpha(mult * 255) scaled the old per-pixel-alpha sprite."""
        x, y = pos
        for o, a in self.strips:
            al = int(a * mult)
            if al >= 2:
                self.surf.set_alpha(al)
                dst.blit(self.surf, (x + o, y) if self.columns else (x, y + o))


class _PerfProbe:
    """Diagnostics, off unless config.json has "perf_log": true. Every 2 s prints fps and the time split
    (update / draw / flip) to stdout (logcat on Android). With "perf_profile": true it also profiles 180 frames
    of each screen once and prints the most expensive functions."""

    def __init__(self, game):
        import time
        self.game, self.clock = game, time.perf_counter
        self.sums = [0.0, 0.0, 0.0]
        self.frames = 0
        self.t0 = self.clock()
        self.profile = bool(config.get("perf_profile", False))
        self.prof_at = int(config.get("perf_profile_at", 60))          # frames into a screen before profiling
        self.prof_len = int(config.get("perf_profile_frames", 180))
        self.done, self.prof, self.prof_state, self.prof_n, self.state_frames = set(), None, None, 0, 0
        self.last_state = None
        game._flip_time = 0.0
        flip = pygame.display.flip

        def timed_flip():
            a = self.clock()
            flip()
            game._flip_time += self.clock() - a
        pygame.display.flip = timed_flip

    def begin(self):
        self.a = self.clock()
        st = self.game.state
        self.state_frames = self.state_frames + 1 if st == self.last_state else 0
        self.last_state = st
        if self.profile and self.prof is None and st not in self.done and self.state_frames == self.prof_at:
            import cProfile
            self.prof, self.prof_state, self.prof_n = cProfile.Profile(), st, 0
            self.prof.enable()

    def mid(self):
        self.b = self.clock()

    def end(self):
        c = self.clock()
        g = self.game
        self.sums[0] += self.b - self.a
        self.sums[1] += c - self.b - g._flip_time
        self.sums[2] += g._flip_time
        g._flip_time = 0.0
        self.frames += 1
        if self.prof is not None:
            self.prof_n += 1
            if self.prof_n >= self.prof_len or g.state != self.prof_state:
                import io
                import pstats
                self.prof.disable()
                out = io.StringIO()
                st_ = pstats.Stats(self.prof, stream=out).sort_stats("tottime")
                st_.print_stats(25)
                if config.get("perf_callers", False):
                    st_.print_callers("blit")
                print(f"[perf] profile of '{self.prof_state}' ({self.prof_n} frames):")
                for line in out.getvalue().splitlines():
                    if line.strip():
                        print("[perf] " + line)
                self.done.add(self.prof_state)
                self.prof = None
        if c - self.t0 >= 2.0:
            n = max(1, self.frames)
            print(f"[perf] {g.state} fps={self.frames / (c - self.t0):.1f} update={self.sums[0] / n * 1000:.1f}ms "
                  f"draw={self.sums[1] / n * 1000:.1f}ms flip={self.sums[2] / n * 1000:.1f}ms")
            self.sums, self.frames, self.t0 = [0.0, 0.0, 0.0], 0, c


if __name__ == "__main__":
    HoloGame().run()
