#!/usr/bin/env python3
"""Quality control of the perimeter trim: each cap alone and on the joint
of the cell it covers. Measured from the meshes the kernel made."""
import sys
import numpy as np
from fitlib import FAR, Case, Placed, box, overlaps
from qclib import integrity, kernel_volume, report, results, scene, thickness

W, H, GAP, RAIL, T, DEPTH, RELIEF = 67.0, 42.0, 3.6, 3.1, 2.0, 100.0, 9.0
PX, PZ = W + GAP, H + GAP
FLOAT, SIDE_FLOAT, E = 0.8, 1.6, 0.02
SIDE_ZONE, STACK_ZONE = (10.9, 29.5), (10.9, 25.5)

M = {d: scene(f".ringwright/{d}/view/scene.rwv") for d in ("cell", "trimtop", "trimrail", "trimlip")}


def clash(fixed, moved, offsets, zone):
    """For each offset, collisions between a fixed part and another moved by
    it, as (in the latch, elsewhere), asked of Ringwright."""
    asked = [Case(Placed(fixed), Placed(moved, tuple(float(v) for v in o)), None, [box(y=(o[1] + zone[0], o[1] + zone[1]))])
             for o in offsets]
    return [(f.ignored, f.points) for f in overlaps(asked)]


def joint(name, fixed, moved, seat, axis, play, centre, zone):
    seat = np.array(seat, float)
    normal = 2 if axis == 0 else 0
    apart = np.zeros(3); apart[normal] = 1.0 if normal == 2 else -1.0
    worst = max(sum(c) for c in clash(fixed, moved, [seat + apart * E + (0, dy, 0) for dy in (0, 0.1, -0.1)], zone))
    limits = []
    for sign in (-1, 1):
        for gap in (E, 0.45):
            o = seat + apart * gap
            o[axis] += sign * (play - 0.05)
            limits.append(o)
    pushed = [b for _, b in clash(fixed, moved, limits, zone)]
    slide = clash(fixed, moved, [seat + apart * E + (0, back, 0) for back in np.arange(-95, 0, 2.5)], zone)
    held = clash(fixed, moved, [seat + apart * 1.0], zone)[0][1] > 0
    # Held on both lips at either end of the play: overlap on each side of the rail's centre.
    sides = []
    for sign in (-1, 1):
        o = seat + apart * 1.0
        o[axis] += sign * (play - 0.05)
        for side in ((-FAR, centre - 1), (centre + 1, FAR)):
            sides.append(Case(Placed(fixed), Placed(moved, tuple(float(v) for v in o)), box(**{"xyz"[axis]: side}),
                              [box(y=(o[1] + zone[0], o[1] + zone[1]))]))
    both = all(f.points > 0 for f in overlaps(sides))
    catches = all(a > 0 for a, _ in clash(fixed, moved, [seat + apart * E + (0, dy, 0) for dy in (-2.5, 2.5)], zone))
    ok = worst == 0 and max(pushed) == 0 and max(b for _, b in slide) == 0 and held and both and catches
    report("PASS" if ok else "FAIL", name,
           f"centred collisions {worst}; at the limits of play {max(pushed)}; sliding on {max(b for _, b in slide)}; "
           f"held when pulled apart: {held}, on both lips at either end of the play: {both}; teeth catch: {catches}")

print("== 1. Integrity and size ==")
sizes = {"trimtop": [W, DEPTH, T + GAP], "trimrail": [T + GAP, DEPTH, H], "trimlip": [T + RAIL, DEPTH, H]}
total = 0
for doc, want in sizes.items():
    vol = kernel_volume(doc)
    total += vol
    integrity(doc, *M[doc], vol)
    size = M[doc][0].max(0) - M[doc][0].min(0)
    report("PASS" if np.allclose(size, want, atol=0.01) else "FAIL", f"{doc} overall size",
           f"measured {size.round(3).tolist()}, drawn {want}; {vol / 1000:.0f} cm3, about {vol * 1.01 / 1000:.0f} g")
    thickness(doc, *M[doc], 1.0)

print("== 2. Each cap on the joint it covers ==")
joint("the top cap on a cell's top rail", "cell", "trimtop", (0, 0, PZ), 0, FLOAT, -W / 2, STACK_ZONE)
joint("the side cap over a cell's side rail", "cell", "trimrail", (-PX, 0, 0), 2, SIDE_FLOAT, H / 2, SIDE_ZONE)
joint("a cell's side lips over the other side cap's rail", "trimlip", "cell", (-(T + GAP), 0, 0), 2, SIDE_FLOAT, H / 2, SIDE_ZONE)

print("== 3. What they leave to be seen ==")
for doc, axis, lo, hi in (("trimtop", 2, 0.0, T), ("trimrail", 0, -T, 0.0), ("trimlip", 0, -T, 0.0)):
    pos = M[doc][0]
    front = pos[pos[:, 1] < 0.01]
    plate = front[(front[:, axis] >= lo - 0.01) & (front[:, axis] <= hi + 0.01)]
    report("PASS" if len(plate) == len(front) else "FAIL", f"{doc} from the front",
           f"only the {T:.0f} mm plate reaches the front plane; its joint ends {RELIEF:.0f} mm back "
           f"({len(front) - len(plate)} points of joint at the front)")

print()
print({v: results.count(v) for v in ("PASS", "FAIL", "NOTE")})
sys.exit(1 if "FAIL" in results else 0)
