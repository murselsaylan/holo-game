"""Uniqueness check for the campaign: are two levels the same shape (mirrored / flipped counts as the same)?

    python levelgen/similar.py            # report the most similar pairs of the planned (unsolved) campaign
    python levelgen/similar.py --fix      # re-roll (levelgen/variants.json) the later level of each too-similar pair

A level is described by its corridor route drawn on a coarse grid (x / arena width, y / level height) plus its power-up gates;
similarity = best overlap over the four mirror images. Routes at least THRESH alike count as duplicates.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from levelgen import gen as GEN, plan as P  # noqa: E402

GX, GY = 16, 36
THRESH = float(os.environ.get("SIM_THRESH", 0.58))
VARIANTS = os.path.join(ROOT, "levelgen", "variants.json")


def raster(route, height, width=900.0):
    cells = set()
    for a, b in zip(route, route[1:]):
        n = int(max(abs(a[0] - b[0]) / width * GX, abs(a[1] - b[1]) / height * GY)) * 2 + 2
        for k in range(n + 1):
            t = k / float(n)
            x = a[0] + (b[0] - a[0]) * t
            y = a[1] + (b[1] - a[1]) * t
            cx = min(GX - 1, max(0, int(x / width * GX)))
            cy = min(GY - 1, max(0, int(y / height * GY)))
            cells.add((cx, cy))
    return cells


def variants(cells):
    return [cells,
            {(GX - 1 - x, y) for x, y in cells},
            {(x, GY - 1 - y) for x, y in cells},
            {(GX - 1 - x, GY - 1 - y) for x, y in cells}]


def iou(a, b):
    u = len(a | b)
    return len(a & b) / float(u) if u else 0.0


def similarity(ca, cb):
    return max(iou(ca, v) for v in variants(cb))


def describe(i):
    d, pl, ctx = GEN.build(i, P.difficulty(i))
    return {"id": i, "family": pl["family"], "cells": raster([tuple(p) for p in d["waypoints"]], d["height"]),
            "kit": tuple(sorted(pl["kit"])), "gates": tuple(sorted(pl["placed"])), "sig": pl.get("sig")}


def main():
    info = [describe(i) for i in range(1, 101)]
    pairs = []
    for x in range(len(info)):
        for y in range(x + 1, len(info)):
            a, b = info[x], info[y]
            s = similarity(a["cells"], b["cells"])
            if a["family"] == "arena" or b["family"] == "arena":
                if a["family"] == b["family"] and a["sig"] == b["sig"]:
                    pairs.append((1.0, a["id"], b["id"], a["family"], b["family"]))
                continue                     # arenas differ by their obstacle rows, not by a route
            if a["family"] == "mines" or b["family"] == "mines":
                continue
            pairs.append((s, a["id"], b["id"], a["family"], b["family"]))
    pairs.sort(reverse=True)
    bad = [p for p in pairs if p[0] >= THRESH and p[1] > 3]
    print(f"top pairs (threshold {THRESH}):")
    for s, a, b, fa, fb in pairs[:12]:
        print(f"  L{a:3d} {fa:8s} ~ L{b:3d} {fb:8s}  {s:.2f}{'  <-- too similar' if s >= THRESH else ''}")
    print("too similar pairs:", len(bad))
    if "--fix" in sys.argv:
        var = {}
        if os.path.exists(VARIANTS):
            var = {int(k): v for k, v in json.load(open(VARIANTS)).items()}
        for _, a, b, _, _ in bad:
            var[b] = var.get(b, 0) + 1
        json.dump({str(k): v for k, v in sorted(var.items())}, open(VARIANTS, "w"))
        print("re-rolled:", sorted({b for _, _, b, _, _ in bad}))
    return len(bad)


if __name__ == "__main__":
    sys.exit(0 if main() == 0 else 1)
