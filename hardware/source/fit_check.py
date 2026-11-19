#!/usr/bin/env python3
"""Proves the joint from the meshes the kernel made: copies of the cell are
placed where neighbours go, and slid along the port axis, and every collision
is accounted for."""
import sys
import numpy as np
from fitlib import FAR, Case, Placed, box, overlaps

W, H, GAP, DEPTH, WALL, FLOAT, SIDE_FLOAT = 67.0, 42.0, 3.6, 100.0, 3.0, 0.8, 1.6
PX, PZ = W + GAP, H + GAP  # lattice pitch across and up
LATCH = (10.9, 29.5)


def latch(o):
    return [box(y=(o[1] + LATCH[0], o[1] + LATCH[1]))]


def clash(offsets):
    """For each offset, collisions between the cell at the origin and a copy
    moved by it, as (those in the latch, those anywhere else), asked of
    Ringwright. The copy carries the fingers of the joint between them, so
    the latch is the stretch of the copy from 10.9 to 29.5 mm behind its own
    front: fingers are springs, and a tooth pressing on the stem is what
    they are for."""
    asked = [Case(Placed("cell"), Placed("cell", tuple(float(v) for v in o)), None, latch(o)) for o in offsets]
    return [(f.ignored, f.points) for f in overlaps(asked)]


failed = 0
E = 0.02  # seated cells touch; stand them a hair apart so touching is not counted
# 1. Seated neighbours. Centred, nothing may touch but the lips; pushed to the
# extremes of the joint's play, only the springs may be pressed.
centred = [("above", (0, 0, PZ + E)), ("beside", (-PX - E, 0, 0)), ("diagonal", (-PX - E, 0, PZ + E)),
           ("diagonal", (PX + E, 0, PZ + E))]
for dy in (-0.1, 0.1):  # the latch now leaves 0.15 of play front to back
    centred += [("above", (0, dy, PZ + E)), ("beside", (-PX - E, dy, 0))]
worst = max(sum(c) for c in clash([o for _, o in centred]))
print(f"seated and centred: {len(centred)} poses above, beside and diagonal; worst has {worst} collisions")
failed += worst
pushed = []
for dx in (-FLOAT + 0.05, FLOAT - 0.05):
    for dz in (E, 0.45):
        pushed.append((dx, 0, PZ + dz))
for dz in (-SIDE_FLOAT + 0.05, SIDE_FLOAT - 0.05):
    for dx in (E, 0.45):
        pushed.append((-PX - dx, 0, dz))
got = clash(pushed)
print(f"seated and pushed to the limits of play: {len(pushed)} poses; springs pressed in "
      f"{sum(1 for a, _ in got if a)} of them, collisions elsewhere {max(b for _, b in got)}")
failed += max(b for _, b in got)

# 2. Sliding in from the front: the teeth ride along the stem, and nothing else touches.
for name, base in (("above", (0, 0, PZ + E)), ("beside", (-PX - E, 0, 0))):
    got = clash([np.array(base) + (0, back, 0) for back in np.arange(-95, 0, 2.5)])
    print(f"sliding {name}: teeth on the stem in {sum(1 for a, _ in got if a)} of {len(got)} steps; "
          f"collisions elsewhere {max(b for _, b in got)}")
    failed += max(b for _, b in got)

# 4. A joined cell cannot be pulled straight off its neighbour.
up, aside = (b > 0 for _, b in clash([(0, 0, PZ + 1.0), (-PX - 1.0, 0, 0)]))
print("pulled 1 mm up off the cell below, it is held:", up)
print("pulled 1 mm sideways off the cell beside, it is held:", aside)
failed += (not up) + (not aside)
# 5. At the end of its play a joint must still hold on both lips, not hang by one.
for name, off, axis, play, centre in (("above", (0, 0, PZ + 1.0), 0, FLOAT, -W / 2),
                                       ("beside", (-PX - 1.0, 0, 0), 2, SIDE_FLOAT, H / 2)):
    sides = []  # overlap on each side of the rail's centre, at each end of the play
    for sign in (-1, 1):
        o = np.array(off, float)
        o[axis] += sign * (play - 0.05)
        for side in ((-FAR, centre - 1), (centre + 1, FAR)):
            sides.append(Case(Placed("cell"), Placed("cell", tuple(float(v) for v in o)), box(**{"xyz"[axis]: side}), latch(o)))
    both = all(f.points > 0 for f in overlaps(sides))
    print(f"pulled 1 mm apart at either end of the play, {name}: held on both lips: {both}")
    failed += not both
# 6. The latch must hold front to back: moved along the joint, the teeth meet their notches' ends.
for name, off in (("above", (0, 0, PZ + E)), ("beside", (-PX - E, 0, 0))):
    held = all(a > 0 for a, _ in clash([np.array(off) + (0, dy, 0) for dy in (-2.5, 2.5)]))
    steps = (0.1, 0.2, 0.3, 0.5, 1.0, 1.5)
    moved = clash([np.array(off) + (0, s * d, 0) for d in steps for s in (-1, 1)])
    free = max([d for k, d in enumerate(steps) if sum(moved[2 * k]) + sum(moved[2 * k + 1]) == 0], default=0.0)
    print(f"moved 2.5 mm along the joint, {name}: the teeth catch: {held}; it moves freely up to {free} mm either way")
    failed += (not held) + (free > 0.3)
sys.exit(1 if failed else 0)
