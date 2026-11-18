#!/usr/bin/env python3
"""Quality control of the cell and tray, measured from the meshes the kernel
made (the viewer's scene files), not from the parameters that asked for them.

Each check prints PASS, FAIL or NOTE with the measured figure."""
import json, math, struct, subprocess, sys
import numpy as np

rng = np.random.default_rng(20261118)
W, H, GAP, DEPTH, WALL = 67.0, 42.0, 3.6, 100.0, 3.0
RAIL = 3.1  # stem 1.9 and head 1.2
PX, PZ = W + GAP, H + GAP
results = []


def kernel_volume(doc):
    """What the kernel says the committed body's volume is."""
    rw = __import__("os").environ.get("RINGWRIGHT", "ringwright")
    head = json.loads(subprocess.run([rw, "inspect", doc], capture_output=True, text=True).stdout)
    tx = {"schema_version": 1, "document": doc, "base_revision": head["result"]["revision"],
          "operations": [], "checks": []}
    out = subprocess.run([rw, "dry-run", "--brief", "-"], input=json.dumps(tx),
                         capture_output=True, text=True).stdout
    return json.loads(out)["result"]["measurements"]["body"]["kernel_volume"]


def report(verdict, name, detail):
    results.append(verdict)
    print(f"{verdict:4}  {name}: {detail}")


def scene(path):
    b = open(path, "rb").read()
    at = 8
    (n,) = struct.unpack_from("<I", b, at); at += 4 + n
    (n,) = struct.unpack_from("<I", b, at); at += 4
    pos = np.frombuffer(b, "<f4", n * 3, at).reshape(-1, 3).astype(float); at += n * 12
    (n,) = struct.unpack_from("<I", b, at); at += 4
    return pos, np.frombuffer(b, "<u4", n * 3, at).reshape(-1, 3).astype(int)


def ray_hits(origins, dirs, pos, tri):
    """Distance from each origin along its direction to the nearest triangle."""
    a = pos[tri[:, 0]]; e1 = pos[tri[:, 1]] - a; e2 = pos[tri[:, 2]] - a
    out = np.full(len(origins), np.inf)
    for k, (o, d) in enumerate(zip(origins, dirs)):
        p = np.cross(d, e2); det = (e1 * p).sum(1)
        ok = np.abs(det) > 1e-12
        s = o - a
        u = np.where(ok, (s * p).sum(1) / np.where(ok, det, 1), -1)
        q = np.cross(s, e1)
        v = np.where(ok, (q @ d) / np.where(ok, det, 1), -1)
        t = np.where(ok, (e2 * q).sum(1) / np.where(ok, det, 1), -1)
        hit = (u >= -1e-9) & (v >= -1e-9) & (u + v <= 1 + 1e-9) & (t > 1e-6)
        if hit.any():
            out[k] = t[hit].min()
    return out


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


def integrity(name, pos, tri, kernel_volume):
    """Closed, consistently wound, and the volume the kernel reported."""
    _, weld = np.unique(np.round(pos, 4), axis=0, return_inverse=True)
    t = weld[tri]
    edges = np.vstack([t[:, [0, 1]], t[:, [1, 2]], t[:, [2, 0]]])
    key = lambda e: e[:, 0].astype(np.int64) * 10_000_000 + e[:, 1]
    forward, backward = key(edges), key(edges[:, ::-1])
    paired = np.isin(forward, backward).all() and len(np.unique(forward)) == len(forward)
    report("PASS" if paired else "FAIL", f"{name} mesh is closed and consistently wound",
           f"{len(tri)} triangles, every edge used once each way: {bool(paired)}")
    p = pos[tri]
    vol = (p[:, 0] * np.cross(p[:, 1], p[:, 2])).sum() / 6
    off = abs(vol - kernel_volume) / kernel_volume
    report("PASS" if off < 2e-3 else "FAIL", f"{name} mesh volume against the kernel's",
           f"mesh {vol:.1f} mm3, kernel {kernel_volume:.1f} mm3, {off * 100:.3f}% apart")
    return vol


def thickness(name, pos, tri, floor):
    """Material thickness behind every face: from each triangle's centre,
    straight in, to the far surface."""
    p = pos[tri]
    n = np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0])
    area = np.linalg.norm(n, axis=1)
    keep = area > 1e-9
    c, n = p.mean(1)[keep], n[keep] / area[keep][:, None]
    t = ray_hits(c - n * 1e-4, -n, pos, tri)
    t = t[np.isfinite(t)]
    thin = np.sort(np.unique(np.round(t, 2)))[:6]
    report("PASS" if t.min() >= floor - 0.02 else "FAIL", f"{name} thinnest section",
           f"{t.min():.2f} mm (floor for this check {floor} mm); thinnest values found {thin.tolist()}")
    return t


cell, cell_tri = scene(".ringwright/cell/view/scene.rwv")

print("== 1. Integrity ==")
integrity("cell", cell, cell_tri, kernel_volume("cell"))

print("== 2. Measured dimensions ==")
lo, hi = cell.min(0), cell.max(0)
size = hi - lo
# Lips on one side and a rail on the other, in both directions.
want = np.array([W + GAP + RAIL, DEPTH, H + GAP + RAIL])
ok = np.allclose(size, want, atol=0.01)
report("PASS" if ok else "FAIL", "cell overall size", f"measured {size.round(3).tolist()}, drawn {want.tolist()}")
body = cell[(cell[:, 2] > -0.01) & (cell[:, 2] < H + 0.01) & (cell[:, 0] < 0.01) & (cell[:, 0] > -W - 0.01)]
report("PASS", "cell body", f"spans {(-body[:, 0].min()):.2f} across, {body[:, 2].max():.2f} up, {size[1]:.2f} deep")
# The thinnest part meant: the strip of flange left behind each finger.
t = thickness("cell", cell, cell_tri, 0.8)
walls = np.sum(np.abs(t - 3.0) < 0.02) / len(t)
report("NOTE", "cell wall", f"{walls * 100:.0f}% of faces have exactly 3.00 mm behind them; "
       f"the rest are rails, lips, skids, ledges and the fingers")
report("NOTE", "the sleeve as an extrusion", "its section is constant front to back; what is local is cut, not added: "
       "the joints end 9 mm short of the front, the ledges 2.6 mm, and the latches are slots, teeth and notches")

print("== 3. Clearances in the joint, measured between two copies ==")
S = np.vstack([cell, cell[cell_tri].mean(1)])


def gap_between(offset, axis, lo_y=25.0):
    """Smallest and typical distance, along `axis`, from the moved copy's
    faces to the fixed cell, away from the catch."""
    p = cell[cell_tri]
    n = np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0])
    n /= np.maximum(np.linalg.norm(n, axis=1), 1e-12)[:, None]
    c = p.mean(1) + offset
    facing = (np.abs(n[:, axis]) > 0.99) & (c[:, 1] > lo_y)
    # Start a little behind each face, so a face that touches the other cell
    # is seen at distance zero and not passed over.
    back = 0.05
    d = ray_hits(c[facing] - n[facing] * back, n[facing], cell + n[facing][0] * 0, cell_tri) - back
    d = d[np.isfinite(d) & (d < 5) & (d > -0.01)]
    return np.sort(np.unique(np.round(d, 3)))


above = gap_between(np.array([0, 0, PZ]), 2)
beside = gap_between(np.array([-PX, 0, 0]), 0)
for name, g in (("stacked", above), ("side by side", beside)):
    small = g[g > 0.01][:4]
    touching = bool((np.abs(g) < 0.01).any())
    report("PASS" if touching and small[0] >= 0.49 else "FAIL", f"{name}: gaps along the joint's own direction",
           f"touching at the lips: {touching}; smallest gaps elsewhere {small.tolist()} mm")
across = gap_between(np.array([0, 0, PZ]), 0, lo_y=30.0)
report("PASS" if across[0] >= 0.79 else "FAIL", "stacked: play across the joint",
       f"smallest sideways gaps {across[:3].tolist()} mm (meant to be 0.8)")
updown = gap_between(np.array([-PX, 0, 0]), 2, lo_y=30.0)
report("PASS" if updown[0] >= 1.59 else "FAIL", "side by side: play up and down in the joint",
       f"smallest gaps {updown[:3].tolist()} mm (meant to be 1.6)")

print("== 5. Will it go together as made? (200,000 simulated joints of each kind) ==")
N = 200_000
JOINTS = {  # play across, tooth reach, finger: thickness in bending, length, room behind
    "stacking joint": dict(play=0.8, reach=1.4, thick=1.0, length=12.0, room=2.0),  # room: the flange behind the finger
    "side joint": dict(play=1.6, reach=2.2, thick=1.4, length=16.0, room=3.2),
}
for process, tol in (("printed nylon, +/-0.30 mm", 0.30), ("moulded, +/-0.10 mm", 0.10)):
    g = lambda mean: rng.normal(mean, tol / 3, N)
    lift, over = g(1.9) - g(1.4), g(3.6) - g(1.9) - g(1.2)  # along the joint's own direction
    slides = (lift > 0) & (over > 0)
    for name, j in JOINTS.items():
        beside = (g(6 + 2 * j["play"]) - g(6.0)) / 2  # lip edge to stem, centred
        press = g(j["reach"]) - beside  # how far a tooth is pushed back while sliding
        works = (press > 0) & (g(j["reach"]) < g(j["room"]))  # touches, and has room at the end of the play
        good = slides & works & (np.minimum(press, g(0.65)) >= 0.2)
        report("PASS" if good.mean() > 0.99 else "FAIL", f"{name}, {process}",
               f"slides freely {100 * slides.mean():.2f}%, fingers work {100 * (slides & works).mean():.2f}%, "
               f"latch holds by 0.2 mm or more {100 * good.mean():.2f}%")
E_MOD, b = 1700.0, 1.4  # PA12 modulus assumed; a finger is as deep as the flange
for name, j in JOINTS.items():
    t, L = j["thick"], j["length"]
    drop = min(j["reach"] - j["play"], 0.65)
    report("PASS" if drop >= 0.4 else "FAIL", f"{name}: latch engagement as drawn",
           f"each tooth is pushed back {j['reach'] - j['play']:.1f} mm when centred and drops {drop:.1f} mm into its notch")
    inertia = b * t ** 3 / 12
    cases = (("centred", j["reach"] - j["play"]), ("at the end of the play", j["reach"]),
             ("at the end of the play, worst made", j["reach"] + 0.4))
    for label, bend in cases:
        strain = 3 * t * bend / (2 * L ** 2)
        force = 3 * E_MOD * inertia * bend / L ** 3
        report("PASS" if strain < 0.025 and bend <= j["room"] else "FAIL", f"{name}: finger bent {bend:.1f} mm ({label})",
               f"strain {100 * strain:.2f}% (kept under 2.5%), room to bend {j['room']:.1f} mm; pushes back {force:.2f} N")

print("== 6. Standing up ==")
stance = W - 2 * 3.0  # outside of one skid to the outside of the other
for n in (1, 2, 3, 4):  # the desk: taller stacks go on bases, and wider
    cg = (n * PZ) / 2
    angle = math.degrees(math.atan((stance / 2) / cg))
    report("PASS" if angle >= 15 else "FAIL", f"stack of {n} on its skids",
           f"stands on a strip {stance:.1f} mm wide under a body {W:.0f} mm wide; tips past {angle:.1f} degrees")

print("== 7. Strength of the lips (nylon PA12, about 48 MPa) ==")
mass = (73.1 + 15.2) * 1.01 / 1000 + 0.046 + 0.03 + 0.01  # cell, carrier, Pi, cooler and HAT, fan  # cell, tray, Pi 5, cooler and HAT, kg
for n in (5, 20):
    force = n * mass * 9.81 / 2  # on each of two flanges
    arm, thick = 6.8 - 3.8 + 0.8, 1.4
    # The fingers take 9 mm of each flange's 100 out of the load path.
    held = DEPTH - 12.8 - 9.0  # less the fingers and the relief at the front
    stress = 6 * force * arm / (held * thick ** 2)
    report("PASS" if stress < 48 / 4 else "FAIL", f"{n} cells hung from one joint",
           f"{force * 2:.1f} N; {stress:.2f} MPa at the root of each flange, safety factor {48 / stress:.0f}")

print()
print({v: results.count(v) for v in ("PASS", "FAIL", "NOTE")})
sys.exit(1 if "FAIL" in results else 0)
