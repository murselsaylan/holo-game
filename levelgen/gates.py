"""Power-up gates: obstacles that CANNOT be passed without the matching pickup.

  shrink  -> narrow throat (needs the compact pair)            + shrink field before it
  grow    -> cracked wall (only a grown orb smashes it)         + growth field before it
  shield  -> thin energy barrier (only a shield lets you cross) + shield pickup before it
  boost   -> escape run: a wall chases the pair, boost pads keep you ahead of it

Every gate is built on a straight corridor leg: `site = (x, y, dx, dy, span)` with (dx, dy) the travel direction.
"""
import math



def zone_radius(span):
    return max(60.0, min(115.0, span / 2.0 - 6.0))


EXTENT = {"gshrink": (300.0, 170.0), "ggrow": (190.0, 50.0), "gshield": (190.0, 50.0), "gboost": (490.0, 280.0)}


def _along(site, dist):
    x, y, dx, dy, span = site
    return x + dx * dist, y + dy * dist


def _across_rect(site, along_len, span, extra=6.0):
    """Rectangle spanning the whole corridor width, `along_len` long along the travel direction, centred on the site."""
    x, y, dx, dy, _ = site
    if abs(dx) > abs(dy):
        return (x - along_len / 2.0, y - span / 2.0 - extra, along_len, span + 2 * extra)
    return (x - span / 2.0 - extra, y - along_len / 2.0, span + 2 * extra, along_len)


def gate_shrink(L, ctx, site, throat_w=104.0, length=300.0):
    """Two wall blocks leave a narrow throat of width `throat_w` and length `length`; a shrink field sits before it."""
    x, y, dx, dy, span = site
    half = (span - throat_w) / 2.0
    if half < 10:
        return False
    if abs(dx) > abs(dy):
        L.pillar(x - length / 2, y - span / 2 - 6, length, half + 6)
        L.pillar(x - length / 2, y + throat_w / 2, length, half + 6)
    else:
        L.pillar(x - span / 2 - 6, y - length / 2, half + 6, length)
        L.pillar(x + throat_w / 2, y - length / 2, half + 6, length)
    zr = min(zone_radius(span), 100.0)
    zx, zy = _along(site, -(length / 2.0 + zr + 30.0))
    L.add("shrink_zones", [zx, zy, zr])
    return True


def gate_grow(L, ctx, site, thickness=46.0):
    """Cracked wall across the corridor + growth field before it."""
    x, y, dx, dy, span = site
    rx, ry, rw, rh = _across_rect(site, thickness, span, extra=0.0)
    L.add("breakables", [rx, ry, rw, rh])
    zr = min(zone_radius(span), 100.0)
    zx, zy = _along(site, -(thickness / 2.0 + zr + 40.0))
    L.add("growth_zones", [zx, zy, zr])
    return True


def gate_shield(L, ctx, site, thickness=34.0):
    """Thin energy barrier (a deadly wall) + a shield pickup on the centre line before it."""
    x, y, dx, dy, span = site
    rx, ry, rw, rh = _across_rect(site, thickness, span, extra=6.0)
    L.pillar(rx, ry, rw, rh)
    L.add("barriers", [rx, ry, rw, rh])
    sx, sy = _along(site, -(thickness / 2.0 + 150.0))
    L.add("shields", [sx, sy])
    return True


def gate_boost(L, ctx, site, chaser_speed, run_len=460.0, pads=3, lead=260.0):
    """Escape run along the leg: `pads` boost fields along `run_len`. A wall waits `lead` px behind the first pad and starts
    chasing the moment the pair enters the run; only boosting keeps you ahead of it."""
    x, y, dx, dy, span = site
    zr = min(zone_radius(span), 90.0)
    for k in range(pads):
        px, py = _along(site, -run_len / 2.0 + run_len * k / max(1, pads - 1))
        L.add("boost_pads", [px, py, zr])
    thick = 60.0
    bx, by = _along(site, -run_len / 2.0 - lead)
    tx, ty = _along(site, -run_len / 2.0 - 90.0)
    if abs(dx) > abs(dy):
        rect = (bx - thick / 2.0, y - span / 2.0 - 6, thick, span + 12)
        trig = (tx - 20.0, y - span / 2.0, 40.0, span)
        vel = (chaser_speed * dx, 0.0)
    else:
        rect = (x - span / 2.0 - 6, by - thick / 2.0, span + 12, thick)
        trig = (x - span / 2.0, ty - 20.0, span, 40.0)
        vel = (0.0, chaser_speed * dy)
    L.add("chasers", [rect[0], rect[1], rect[2], rect[3], vel[0], vel[1], trig[0], trig[1], trig[2], trig[3],
                      run_len + lead + 200.0])
    return True
