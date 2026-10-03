import json
from pathlib import Path

from endless_native_prototype import MAP_ID, OPENING, level_for_stage


ROOT = Path(__file__).resolve().parents[1]


def main():
    assert [level_for_stage(i) for i in range(len(OPENING))] == OPENING
    assert [level_for_stage(i) for i in range(250)] == [level_for_stage(i) for i in range(250)]
    assert all(1 <= level_for_stage(i) <= 100 for i in range(1000))
    level9 = json.loads((ROOT / "levels/level9.json").read_text(encoding="utf-8"))
    wp = level9["waypoints"]
    assert any(b[1] > a[1] + 80 for a, b in zip(wp, wp[1:])), "opening must contain a true reverse leg"
    print(f"OK: native map={MAP_ID}, opening={OPENING}, reverse-route=L9")


if __name__ == "__main__":
    main()
