from endless_mode_prototype import WORLD_SEED, make_row, map_signature


def main():
    first = [make_row(i) for i in range(240)]
    second = [make_row(i) for i in range(240)]
    assert first == second, "same seed must always produce the same map"
    assert map_signature(32) == map_signature(240), "map id must not depend on generated distance"
    assert all(row.width >= 300 for row in first)
    assert all(0 <= row.center <= 900 for row in first)
    assert len({repr(row) for row in first}) == len(first)
    print(f"OK: {WORLD_SEED}, signature={map_signature(240)}, rows={len(first)}")


if __name__ == "__main__":
    main()
