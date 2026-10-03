import json
from pathlib import Path

from endless_stitched_prototype import DEFAULT_STAGES, GAP, build_stitched, choose_levels, map_id
from sim import LevelData

ROOT = Path(__file__).resolve().parents[1]


def main():
    a, b = build_stitched(seed="test-seed"), build_stitched(seed="test-seed")
    assert a == b
    assert choose_levels("test-seed") != choose_levels("other-seed")
    assert build_stitched(seed="alternate")["_map_id"] == map_id("alternate")
    assert len(a["_source_levels"]) == DEFAULT_STAGES
    assert len(a["_return_gates"]) == DEFAULT_STAGES - 1
    assert a["height"] > sum(1400 for _ in range(DEFAULT_STAGES))
    chosen = a["_source_levels"]
    assert all(x != y for x, y in zip(chosen, chosen[1:])), "consecutive maps should not repeat"
    mechanics = a["_stage_mechanics"]
    assert not mechanics[0]["reverse_walls"] and not mechanics[0]["moving_walls"]
    assert not any(m["circles"] for m in mechanics[:2])
    assert not any(m["growth_zones"] or m["breakables"] or m["barriers"] or m["shields"] for m in mechanics[:3])
    assert not any(m["shrink_zones"] or m["boost_pads"] or m["chasers"] for m in mechanics[:4])
    assert not any(m["lasers"] or m["spinners"] for m in mechanics[:5])
    assert any(m["lasers"] or m["spinners"] for m in mechanics[5:]), "endgame must mix hard hazards"
    assert len(a["waypoints"]) > 20
    assert len(a["moving_walls"]) > 0
    assert len(a["reverse_walls"]) > 0
    assert len(a["circles"]) > 0
    assert not any(abs(a["end"][0] - p[0]) < 1 and abs(a["end"][1] - p[1]) < 1 for p in a["waypoints"][:-1])
    data = LevelData(a)
    assert data.path_total > data.height
    print(f"OK: stitched={chosen}, height={int(data.height)}, route={int(data.path_total)}, gap={GAP}")


if __name__ == "__main__":
    main()
