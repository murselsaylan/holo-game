"""First-run tutorial ("Level 0", 1.1.0).

A short, wide, slow corridor that teaches the one control before level 1. The pair cannot be lost here: a crash
rewinds it a second (the guarded revive of sim.py) and a tip explains what happened. The tutorial is never sent
to the server and never ranked; finishing it claims the one-time "tutorial" diamond reward (the server sets the
amount, see supabase/functions/scores/wallet.ts TUTORIAL_REWARD).

The level lives here (not in levels/) so the level tools, exports and goldens that walk levels/level*.json never
see it, and both app packages carry it as code.

Steps the player is walked through (each one waits for the player, nothing is timed out):
    tap   - "tap the screen": the spinning orb stops, the other one starts to swing
    climb - "keep tapping to climb towards the portal" (until a third of the way)
    star  - "fly through the stars" (until a star is taken or two thirds of the way)
    goal  - "reach the portal"
"""

TUTORIAL_ID = 0
REWARD = 20            # shown on the finish toast; the server decides the real amount

LEVEL = {
    "id": TUTORIAL_ID, "title": "TRAINING ORBIT", "height": 1300,
    "start": [450, 1080], "end": [450, 250], "speed": 0.8, "ramp": 0.0,
    # a 420 px wide corridor (level 1: 334 px) with a floor and a ceiling
    "walls": [[0, 0, 900, 90], [0, 90, 240, 1140], [660, 90, 240, 1140], [0, 1230, 900, 70]],
    "waypoints": [[450, 1080], [450, 250]],
    "reverse_walls": [], "moving_walls": [], "lasers": [], "spinners": [], "circles": [], "growth_zones": [],
    "shrink_zones": [], "boost_pads": [], "shields": [], "breakables": [], "chasers": [], "barriers": [],
    "stars": [[380, 880], [375, 680], [380, 480]],
    "sector": 1, "par_time": 14.0, "par_swaps": 10,
    "ref_taps": [150, 228, 303, 378, 453, 528, 603],      # a 3-star solution (levelgen/solver.py), for the tests
}

STEPS = ("tap", "climb", "star", "goal")
CLIMB_DONE = 0.33      # progress (0..1 along the route) that ends the "climb" step
STAR_DONE = 0.66       # ... and the "star" step when no star was taken by then
IDLE_TAP_S = 1.3       # seconds without a tap before the hand reminds the player to tap
DEATH_TIP_S = 2.6      # seconds the "do not touch the walls" tip stays after a crash


class Tutorial:
    """The tutorial's own state; the game asks it which tip to show and tells it what happened."""

    def __init__(self):
        self.step = 0              # index into STEPS
        self.deaths = 0
        self.death_tip = 0.0       # seconds left of the crash tip
        self.done = False
        self.reached = set()       # funnel milestones already reported ("tut_tap", "tut_half", "tut_star")
        self.idle = 0.0            # seconds since the last tap (the "TAP" hand shows when the player waits)
        self._swaps = 0

    @property
    def name(self):
        return STEPS[min(self.step, len(STEPS) - 1)]

    def tip_key(self):
        """locales key of the tip to show now (its second, smaller line is the same key + "_sub")."""
        if self.death_tip > 0.0:
            return "tut_crash"
        return "tut_" + self.name

    def need_tap(self):
        """Show the pulsing TAP hand: before the first tap at once, later when the player has waited a moment."""
        return self.death_tip <= 0.0 and (self.step == 0 or self.idle >= IDLE_TAP_S)

    def update(self, dt, sim):
        """Advance the steps from the pair's state. Returns the funnel milestones reached in this frame."""
        if self.death_tip > 0.0:
            self.death_tip = max(0.0, self.death_tip - dt)
        if sim.swaps != self._swaps:
            self._swaps, self.idle = sim.swaps, 0.0
        else:
            self.idle += dt
        out = []
        prog = max(sim.max_progress, sim.progress)
        if self.step == 0 and sim.swaps >= 1:
            self.step = 1
            out.append("tut_tap")
        if self.step == 1 and prog >= CLIMB_DONE:
            self.step = 2
            out.append("tut_half")
        if self.step == 2 and (sim.stars_collected >= 1 or prog >= STAR_DONE):
            self.step = 3
            if sim.stars_collected >= 1:
                out.append("tut_star")
        fresh = [m for m in out if m not in self.reached]
        self.reached.update(fresh)
        return fresh

    def crashed(self, sim):
        """The pair hit something: rewind it a second (no failure screen in the tutorial). The revive is the guarded
        one (assist "R3" of sim.py): the pair spins up slowly and bounces off walls until the next tap, so a player
        who waits is never crashed again."""
        self.deaths += 1
        self.death_tip = DEATH_TIP_S
        sim.revive(guarded=True, walls=True)


def should_offer(save_mgr):
    """New players only: never finished nor skipped, and level 1 never cleared (players from before 1.1.0 skip it)."""
    d = save_mgr.data
    return not d.get("tutorial_done") and save_mgr.get_level_stars(1) == 0 and save_mgr.highest_cleared == 0
