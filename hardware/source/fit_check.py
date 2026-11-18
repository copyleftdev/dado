#!/usr/bin/env python3
"""Proves the joint from the meshes the kernel made: copies of the cell are
placed where neighbours go, and slid along the port axis, and every collision
is accounted for."""
import struct, sys
import numpy as np

W, H, GAP, DEPTH, WALL, FLOAT, SIDE_FLOAT = 67.0, 42.0, 3.6, 100.0, 3.0, 0.8, 1.6
PX, PZ = W + GAP, H + GAP  # lattice pitch across and up


def scene(path):
    b = open(path, "rb").read()
    assert b[:8] == b"RWVIEW02"
    at = 8
    (n,) = struct.unpack_from("<I", b, at); at += 4 + n
    (n,) = struct.unpack_from("<I", b, at); at += 4
    pos = np.frombuffer(b, "<f4", n * 3, at).reshape(-1, 3).astype(float); at += n * 12
    (n,) = struct.unpack_from("<I", b, at); at += 4
    return pos, np.frombuffer(b, "<u4", n * 3, at).reshape(-1, 3)


def samples(pos, tri):
    """Corners, edge midpoints and centres of every triangle."""
    t = pos[tri]
    mids = [(t[:, i] + t[:, j]) / 2 for i, j in ((0, 1), (1, 2), (2, 0))]
    return np.vstack([pos, t.mean(1), *mids])


def inside(points, pos, tri):
    d = np.array([0.5377, 0.3183, 0.7809]); d /= np.linalg.norm(d)
    a = pos[tri[:, 0]]; e1 = pos[tri[:, 1]] - a; e2 = pos[tri[:, 2]] - a
    p = np.cross(d, e2); det = (e1 * p).sum(1)
    out = np.zeros(len(points), bool)
    for k, o in enumerate(points):
        s = o - a
        u = (s * p).sum(1) / det
        q = np.cross(s, e1)
        v = (q @ d) / det
        t = (e2 * q).sum(1) / det
        out[k] = ((u >= 0) & (v >= 0) & (u + v <= 1) & (t > 1e-9)).sum() % 2 == 1
    return out


cell, cell_tri = scene(".ringwright/cell/view/scene.rwv")
S = samples(cell, cell_tri)


def clash(offset, points=False):
    """Collisions between the cell at the origin and a copy moved by
    `offset`, as (those in the latch, those anywhere else). The copy carries
    the fingers of the joint between them, so the latch is the stretch of
    the copy from 10.9 to 29.5 mm behind its own front: fingers are springs,
    and a tooth pressing on the stem is what they are for."""
    off = np.array(offset, float)
    hits = np.vstack([(S + off)[inside(S + off, cell, cell_tri)], S[inside(S - off, cell, cell_tri)]])
    along = hits[:, 1] - off[1]
    latch = (along > 10.9) & (along < 29.5)
    if points:
        return hits[~latch]
    return int(latch.sum()), int((~latch).sum())


failed = 0
E = 0.02  # seated cells touch; stand them a hair apart so touching is not counted
# 1. Seated neighbours. Centred, nothing may touch but the lips; pushed to the
# extremes of the joint's play, only the springs may be pressed.
centred = [("above", (0, 0, PZ + E)), ("beside", (-PX - E, 0, 0)), ("diagonal", (-PX - E, 0, PZ + E)),
           ("diagonal", (PX + E, 0, PZ + E))]
for dy in (-0.1, 0.1):  # the latch now leaves 0.15 of play front to back
    centred += [("above", (0, dy, PZ + E)), ("beside", (-PX - E, dy, 0))]
worst = max(sum(clash(o)) for _, o in centred)
print(f"seated and centred: {len(centred)} poses above, beside and diagonal; worst has {worst} collisions")
failed += worst
pushed = []
for dx in (-FLOAT + 0.05, FLOAT - 0.05):
    for dz in (E, 0.45):
        pushed.append((dx, 0, PZ + dz))
for dz in (-SIDE_FLOAT + 0.05, SIDE_FLOAT - 0.05):
    for dx in (E, 0.45):
        pushed.append((-PX - dx, 0, dz))
got = [clash(o) for o in pushed]
print(f"seated and pushed to the limits of play: {len(pushed)} poses; springs pressed in "
      f"{sum(1 for a, _ in got if a)} of them, collisions elsewhere {max(b for _, b in got)}")
failed += max(b for _, b in got)

# 2. Sliding in from the front: the teeth ride along the stem, and nothing else touches.
for name, base in (("above", (0, 0, PZ + E)), ("beside", (-PX - E, 0, 0))):
    got = [clash(np.array(base) + (0, back, 0)) for back in np.arange(-95, 0, 2.5)]
    print(f"sliding {name}: teeth on the stem in {sum(1 for a, _ in got if a)} of {len(got)} steps; "
          f"collisions elsewhere {max(b for _, b in got)}")
    failed += max(b for _, b in got)

# 4. A joined cell cannot be pulled straight off its neighbour.
up, aside = clash((0, 0, PZ + 1.0))[1] > 0, clash((-PX - 1.0, 0, 0))[1] > 0
print("pulled 1 mm up off the cell below, it is held:", up)
print("pulled 1 mm sideways off the cell beside, it is held:", aside)
failed += (not up) + (not aside)
# 5. At the end of its play a joint must still hold on both lips, not hang by one.
for name, off, axis, play, centre in (("above", (0, 0, PZ + 1.0), 0, FLOAT, -W / 2),
                                       ("beside", (-PX - 1.0, 0, 0), 2, SIDE_FLOAT, H / 2)):
    both = True
    for sign in (-1, 1):
        o = np.array(off, float)
        o[axis] += sign * (play - 0.05)
        hits = clash(o, points=True)
        across = hits[:, axis] - centre
        both &= bool((across < -1).any() and (across > 1).any())
    print(f"pulled 1 mm apart at either end of the play, {name}: held on both lips: {both}")
    failed += not both
# 6. The latch must hold front to back: moved along the joint, the teeth meet their notches' ends.
for name, off in (("above", (0, 0, PZ + E)), ("beside", (-PX - E, 0, 0))):
    held = all(clash(np.array(off) + (0, dy, 0))[0] > 0 for dy in (-2.5, 2.5))
    free = max([d for d in (0.1, 0.2, 0.3, 0.5, 1.0, 1.5) if all(sum(clash(np.array(off) + (0, s * d, 0))) == 0 for s in (-1, 1))], default=0.0)
    print(f"moved 2.5 mm along the joint, {name}: the teeth catch: {held}; it moves freely up to {free} mm either way")
    failed += (not held) + (free > 0.3)
sys.exit(1 if failed else 0)
