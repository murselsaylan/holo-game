"""Repro + fix check for 'shield bounces off a wall but stays stuck and dies' (sim v8).

Places the rotating orb on a collision course with a wide wall block (~40px along the swing arc, several frames to
cross), pops a shield right as it enters, and checks the pair survives and clears the wall instead of dying when a
fixed-time invulnerability would have run out mid-overlap.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sim import Sim, LevelData, TETHER  # noqa: E402

d = {
    "id": 1, "title": "T", "height": 1400, "start": [450, 600], "end": [450, 200], "speed": 1.3, "ramp": 0.0,
    "walls": [[0, 0, 900, 20], [0, 1380, 900, 20], [0, 0, 20, 1400], [880, 0, 20, 1400], [530, 580, 40, 40]],
    "waypoints": [[450, 600], [450, 200]], "shields": [], "stars": [],
}
lvl = LevelData(d)
s = Sim(lvl, margin=0.0, record_events=True)
s.ang = -0.10                     # already inside the block, about to swing deeper in
s.rot_sign = 1.0
s.shields = 5                     # plenty of shields: isolates "does it ever die WHILE embedded" from "runs out of shields"
s.swaps = 1                       # past spawn protection (swaps == 0 grace)
o0, o1 = s.orbs
o1.x = 450 + math.cos(s.ang) * TETHER
o1.y = 600 + math.sin(s.ang) * TETHER

max_overlap_frames = 0
run = 0
died_while_escaping = False
escapes = 0
for i in range(240):
    was_escaping = s.wall_escaping
    s.step()
    for e in s.events:
        print(s.n, e)
    s.events.clear()
    if s.wall_escaping:
        run += 1
        max_overlap_frames = max(max_overlap_frames, run)
    else:
        if was_escaping:
            escapes += 1
        run = 0
    if s.dead:
        if was_escaping:                       # this is the actual bug: died WHILE still recovering from the bounce
            died_while_escaping = True
        print(f"DIED at frame {s.n} (was mid wall-escape: {was_escaping})")
        break
    if s.won:
        break

print("died_while_escaping (the reported bug):", died_while_escaping, "| completed escapes:", escapes,
      "| max consecutive wall-escape frames:", max_overlap_frames, "| final shields:", s.shields)
sys.exit(1 if died_while_escaping else 0)
