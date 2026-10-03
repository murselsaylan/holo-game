from endless_mode_prototype_v2 import MAP_ID, World


def main():
    a, b = World(), World()
    assert a.segments == b.segments
    assert a.pickups == b.pickups
    assert {s.kind for s in a.segments} == {"ORBITAL", "WANDER", "U-DÖNÜŞÜ", "ODALAR", "ARENA"}
    u_segments = [s for s in a.segments if s.kind == "U-DÖNÜŞÜ"]
    assert any(s.b[1] < s.a[1] for s in u_segments), "U route must contain a backwards leg"
    old_total = a.total
    a.ensure_ahead(old_total - 1)
    assert a.total > old_total
    print(f"OK: map={MAP_ID}, segments={len(a.segments)}, backwards-U=yes")


if __name__ == "__main__":
    main()
