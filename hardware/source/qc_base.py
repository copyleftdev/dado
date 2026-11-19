#!/usr/bin/env python3
"""Quality control of the base: alone, under a cell, beside another base, and
as what keeps a cluster standing. Measured from the meshes the kernel made."""
import math, sys
import numpy as np
from fitlib import FAR, Case, Placed, box, overlaps
from qclib import integrity, kernel_volume, ray_hits, report, results, scene, thickness

rng = np.random.default_rng(20261118)
W, GAP, RAIL, HB, DEPTH, SETBACK, PAD = 67.0, 3.6, 3.1, 22.0, 100.0, 0.0, 1.0
PX, PZ, CELL_H, CELL_D = W + GAP, 45.6, 42.0, 100.0
FLOAT, E = 0.8, 0.02

base, base_tri = scene(".ringwright/base/view/scene.rwv")
cell, cell_tri = scene(".ringwright/cell/view/scene.rwv")


def clash(fixed, moved, offsets, zone):
    """For each offset, collisions between a fixed part and another moved by
    it, as (in the latch, elsewhere), asked of Ringwright. The moved part
    carries the fingers; the latch is the stretch `zone` behind its own front."""
    asked = [Case(Placed(fixed), Placed(moved, tuple(float(v) for v in o)), None, [box(y=(o[1] + zone[0], o[1] + zone[1]))])
             for o in offsets]
    return [(f.ignored, f.points) for f in overlaps(asked)]


def both_lips(fixed, moved, offset, axis, centre):
    """Pulled apart at either end of the joint's play: is it held on both
    lips, or hanging by one? Asked as overlap on each side of the rail's centre."""
    asked = []
    for sign in (-1, 1):
        o = np.array(offset, float)
        o[axis] += sign * (FLOAT - 0.05)
        latch = [box(y=(o[1] + ZONE[0], o[1] + ZONE[1]))]
        for side in ((-FAR, centre - 1), (centre + 1, FAR)):
            where = box(**{"xyz"[axis]: side})
            asked.append(Case(Placed(fixed), Placed(moved, tuple(float(v) for v in o)), where, latch))
    return all(f.points > 0 for f in overlaps(asked))


def catches(fixed, moved, offset):
    """Moved along the joint, do the teeth meet the ends of their notches?"""
    return all(a > 0 for a, _ in clash(fixed, moved, [np.array(offset) + (0, dy, 0) for dy in (-2.5, 2.5)], ZONE))


BASE, CELL = "base", "cell"
ZONE = (10.9, 25.5)  # a 12 mm finger from 12 behind the front, and its end cut

print("== 1. Integrity ==")
vol = kernel_volume("base")
integrity("base", base, base_tri, vol)

print("== 2. Measured dimensions ==")
size = base.max(0) - base.min(0)
want = np.array([W + GAP + RAIL, DEPTH, HB + RAIL + PAD])
report("PASS" if np.allclose(size, want, atol=0.01) else "FAIL", "base overall size",
       f"measured {size.round(3).tolist()}, drawn {want.tolist()}")
thickness("base", base, base_tri, 1.0)
report("NOTE", "material", f"{vol / 1000:.0f} cm3, about {vol * 1.01 / 1000:.0f} g in nylon")

print("== 3. A cell on the base ==")
ON = np.array([0, SETBACK, HB + GAP])
poses = [ON + (0, 0, E), ON + (0, 0.1, E), ON + (0, -0.1, E)]
worst = max(sum(c) for c in clash(BASE, CELL, poses, ZONE))
report("PASS" if worst == 0 else "FAIL", "seated and centred", f"{len(poses)} poses; collisions {worst}")
pushed = [ON + (dx, 0, dz) for dx in (-FLOAT + 0.05, FLOAT - 0.05) for dz in (E, 0.45)]
got = clash(BASE, CELL, pushed, ZONE)
report("PASS" if max(b for _, b in got) == 0 else "FAIL", "seated and pushed to the limits of play",
       f"{len(pushed)} poses; springs pressed in {sum(1 for a, _ in got if a)}; collisions elsewhere {max(b for _, b in got)}")
got = clash(BASE, CELL, [ON + (0, back, E) for back in np.arange(-95, 0, 2.5)], ZONE)
report("PASS" if max(b for _, b in got) == 0 else "FAIL", "sliding on from the front",
       f"{len(got)} steps; teeth on the rail in {sum(1 for a, _ in got if a)}; collisions elsewhere {max(b for _, b in got)}")
up = clash(BASE, CELL, [ON + (0, 0, 1.0)], ZONE)[0][1]
report("PASS" if up > 0 else "FAIL", "pulled 1 mm up off the base", f"it is held ({up} samples collide)")
ok = both_lips(BASE, CELL, ON + (0, 0, 1.0), 0, -W / 2)
report("PASS" if ok else "FAIL", "pulled up at either end of its play", f"held on both lips: {ok}")
ok = catches(BASE, CELL, ON + (0, 0, E))
report("PASS" if ok else "FAIL", "moved 2.5 mm along the rail", f"the cell's teeth catch in the base's notches: {ok}")
# What the cell stands on: its downward faces that touch the base's deck.
p = cell[cell_tri]
n = np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0])
n /= np.maximum(np.linalg.norm(n, axis=1), 1e-12)[:, None]
c = p.mean(1) + ON
down = n[:, 2] < -0.99
d = ray_hits(c[down] + (0, 0, 0.05), np.tile([0, 0, -1.0], (down.sum(), 1)), base, base_tri) - 0.05
u = -c[down][:, 0]
touch = np.abs(d) < 0.01
skids = touch & ((u < 7) | (u > W - 7))
lips = touch & (np.abs(u - W / 2) < 9)
report("PASS" if skids.any() and lips.any() else "FAIL", "what the cell stands on",
       f"its skids touch the deck ({int(skids.sum())} faces) and so do its lips ({int(lips.sum())} faces)")

print("== 4. A base beside a base ==")
BESIDE = np.array([-PX - E, 0, 0])
worst = max(sum(c) for c in clash(BASE, BASE, [BESIDE + (0, dy, 0) for dy in (0, 0.1, -0.1)], ZONE))
report("PASS" if worst == 0 else "FAIL", "seated and centred", f"3 poses; collisions {worst}")
pushed = [BESIDE + (-dx, 0, dz) for dz in (-FLOAT + 0.05, FLOAT - 0.05) for dx in (0, 0.43)]
got = clash(BASE, BASE, pushed, ZONE)
report("PASS" if max(b for _, b in got) == 0 else "FAIL", "seated and pushed to the limits of play",
       f"{len(pushed)} poses; springs pressed in {sum(1 for a, _ in got if a)}; collisions elsewhere {max(b for _, b in got)}")
got = clash(BASE, BASE, [BESIDE + (0, back, 0) for back in np.arange(-95, 0, 2.5)], ZONE)
report("PASS" if max(b for _, b in got) == 0 else "FAIL", "sliding on from the front",
       f"{len(got)} steps; teeth on the rail in {sum(1 for a, _ in got if a)}; collisions elsewhere {max(b for _, b in got)}")
(_, apart), (_, lifted) = clash(BASE, BASE, [BESIDE + (-1.0, 0, 0), BESIDE + (0, 0, FLOAT + 0.5)], ZONE)
report("PASS" if apart > 0 else "FAIL", "pulled 1 mm apart", f"it is held ({apart} samples collide)")
report("PASS" if lifted > 0 else "FAIL", "one base lifted past the joint's play",
       f"the other holds it down ({lifted} samples collide): joined bases tip as one")

ok = both_lips(BASE, BASE, BESIDE + (-1.0, 0, 0), 2, HB / 2)
report("PASS" if ok else "FAIL", "pulled apart at either end of the play", f"held on both lips: {ok}")
ok = catches(BASE, BASE, BESIDE)
report("PASS" if ok else "FAIL", "moved 2.5 mm along the joint", f"the teeth catch in the notches: {ok}")

print("== 5. Will it go together as made? (200,000 simulated bases) ==")
N = 200_000
for process, tol in (("printed nylon, +/-0.30 mm", 0.30), ("moulded, +/-0.10 mm", 0.10)):
    g = lambda mean: rng.normal(mean, tol / 3, N)
    lift, over = g(1.9) - g(1.4), g(3.6) - g(1.9) - g(1.2)
    slides = (lift > 0) & (over > 0)
    beside = (g(6 + 2 * FLOAT) - g(6.0)) / 2
    press = g(1.4) - beside
    latch = slides & (press > 0) & (np.minimum(press, g(0.65)) >= 0.2)
    # Two bases on one surface: each joint's height above it is pad plus half
    # the body, so the rail and the lips it meets differ by four dimensions.
    level = np.abs(g(0) + g(0) + g(0) + g(0)) < FLOAT
    report("PASS" if (latch & level).mean() > 0.99 else "FAIL", process,
           f"slides and latches {100 * latch.mean():.2f}%; neighbours' joints line up on one surface "
           f"{100 * level.mean():.2f}%; both {100 * (latch & level).mean():.2f}%")
for label, bend in (("centred", 0.6), ("at the end of the play", 1.4), ("at the end of the play, worst made", 1.8)):
    strain = 3 * 1.0 * bend / (2 * 12.0 ** 2)
    report("PASS" if strain < 0.025 else "FAIL", f"finger bent {bend:.1f} mm ({label})",
           f"strain {100 * strain:.2f}% (kept under 2.5%)")

print("== 6. Standing up ==")
M_CELL = (73.1 + 15.2) * 1.01 / 1000 + 0.046 + 0.03 + 0.01  # cell, carrier, Pi, cooler and HAT, fan
M_BASE = vol * 1.01 / 1e6


def tip(rows, cols, bases):
    """Angles past which a block of loaded cells, `cols` wide and `rows`
    high on `bases` joined bases, tips sideways and front to back."""
    z = [HB + GAP + PZ * r + CELL_H / 2 for r in range(rows)]
    mass = cols * rows * M_CELL + bases * M_BASE
    cg = (cols * M_CELL * sum(z) + bases * M_BASE * HB / 2) / mass + PAD
    across = (bases - 1) * PX + (W - 6)  # outer pad to outer pad
    return (math.degrees(math.atan(across / 2 / cg)), math.degrees(math.atan(DEPTH / 2 / cg)))


print("  rule: the plinth is at least one base wide for every four cells of height; empty")
print("  bases go on in pairs, one each side, so the cells stay in the middle of it")
print(f"  {'cells high':>12} {'cells wide':>11} {'bases':>6} {'sideways':>10} {'front-back':>11}")
low = 90.0
for rows in (1, 2, 3, 4):
    for cols in (1, 2, 3):
        extra = max(0, math.ceil(rows / 4) - cols)
        bases = cols + extra + extra % 2  # a pair at a time: the model takes the cells as centred
        a, b = tip(rows, cols, bases)
        low = min(low, a, b)
        note = f"  ({bases - cols} empty)" if bases > cols else ""
        print(f"  {rows:>12} {cols:>11} {bases:>6} {a:>9.1f}° {b:>10.1f}°{note}")
report("PASS" if low >= 15 else "FAIL", "every desk cluster, to 4 high and 3 wide",
       f"the least steady tips past {low:.1f} degrees (bar: 15)")
hi = [f"{r} high {min(tip(r, 3, 3)):.1f}" for r in (5, 6, 8)]
report("NOTE", "beyond the desk, three wide", "tips past (degrees): " + ", ".join(hi) + "; the base no longer "
       "reaches in front of or behind the cells, so tall walls would want a deeper one")

print("== 7. Strength (nylon PA12, about 48 MPa) ==")
lean = 4 * M_CELL * 9.81
stress = 6 * (lean / 2) * (6.8 - 3.8 + FLOAT) / ((DEPTH - 12.8 - 9.0) * 1.4 ** 2)
report("PASS" if stress < 12 else "FAIL", "a 4-high column leaning on the base beside it",
       f"{lean:.0f} N through the side joint; {stress:.2f} MPa at the root of each flange, safety factor {48 / stress:.0f}")
line = 4 * M_CELL * 9.81 / 2 / CELL_D  # N per mm along each skid
m = line * 3.0  # the skid stands up to 3 mm in from the side wall
bend = 6 * m / 3.0 ** 2
report("PASS" if bend < 12 else "FAIL", "the deck under a 4-high column's skids",
       f"{line * 1000:.0f} N/m along each skid, at most 3 mm in from a wall: {bend:.2f} MPa in the 3 mm deck")

print()
print({v: results.count(v) for v in ("PASS", "FAIL", "NOTE")})
sys.exit(1 if "FAIL" in results else 0)
