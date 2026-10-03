"""Max safety margin for each gate at chosen parameters (higher = easier for humans)."""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from levelgen import gate_lab as GL, gates as G
from sim import LevelData
from levelgen import solver as S

t0 = time.time()
which = sys.argv[1]
cases = []
if which == "shrink":
    cases = [("shrink", tw) for tw in (112, 120, 128, 136)]
elif which == "boost":
    cases = [("boost", v) for v in (110, 125, 140)]
else:
    cases = [(which, 0)]
for kind, param in cases:
    d = GL.build(kind, 280, param)
    lvl = LevelData(d)
    m = S.max_margin(lvl, hi=48.0, iters=5, beam=64, max_layers=320)
    print(f"{kind} param={param}: max margin {m:.1f}px ({time.time()-t0:.0f}s)", flush=True)
