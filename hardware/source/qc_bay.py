#!/usr/bin/env python3
"""QC of the bay and its shelf: that they are sound, that the bay takes the
place of three cells in every joint, that the shelf goes in and latches, and
what will and will not fit on it."""
import json, subprocess, sys
import numpy as np
from qclib import inside, integrity, kernel_volume, report, results, scene, thickness

RW = __import__("os").environ.get("RINGWRIGHT", "ringwright")
rng = np.random.default_rng(7)


def params(doc):
    out = subprocess.run([RW, "inspect", doc], capture_output=True, text=True).stdout
    return {p["id"]: p["value"] for p in json.loads(out)["result"]["parameters"]}


def samples(pos, tri):
    t = pos[tri]
    return np.vstack([pos, t.mean(1), *[(t[:, i] + t[:, j]) / 2 for i, j in ((0, 1), (1, 2), (2, 0))]])



cell_p = params("cell")
PX, PZ, E = cell_p["body.width"] + cell_p["gap"], cell_p["body.height"] + cell_p["gap"], 0.02
M, S = {}, {}
for d in ("cell", "trimtop", "bay", "baytall", "bayrack", "shelf", "shelftall", "shelfrack"):
    M[d] = scene(f".ringwright/{d}/view/scene.rwv")
    S[d] = samples(*M[d])


def scatter(pos, tri, n):
    """Points spread evenly over a surface: the shelf's faces are large and
    plain, so corners and edge midpoints alone miss where it meets the bay."""
    t = pos[tri]
    area = np.linalg.norm(np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0]), axis=1)
    pick = rng.choice(len(t), n, p=area / area.sum())
    u, v = rng.random(n), rng.random(n)
    flip = u + v > 1
    u[flip], v[flip] = 1 - u[flip], 1 - v[flip]
    c, nrm = t[pick], np.cross(t[pick, 1] - t[pick, 0], t[pick, 2] - t[pick, 0])
    p = c[:, 0] + u[:, None] * (c[:, 1] - c[:, 0]) + v[:, None] * (c[:, 2] - c[:, 0])
    return p - nrm / np.linalg.norm(nrm, axis=1)[:, None] * 0.01  # just inside the surface



def clash(a, at_a, b, at_b):
    """Sample points of each part inside the other."""
    pa, pb = S[a] + at_a, S[b] + at_b
    return int(inside(pa - at_b, *M[b]).sum()) + int(inside(pb - at_a, *M[a]).sum())


# bay, its shelf, places across, places up; then what might go in it:
# name, width, depth, height, and whether it is expected to fit.
KINDS = {
    "bay": ("shelf", 3, 1, [
        ("5-port PoE switch (TP-Link TL-SG1005P, maker's figures)", 99.8, 98.0, 25.0, True),
        ("8-port PoE switch (TP-Link TL-SG108PE, one spec sheet)", 158.0, 101.0, 25.0, True),
        ("a switch 29 mm tall (the tallest desktop figure met)", 158.0, 101.0, 29.0, True),
        ("that 8-port switch if a flyer's larger figures are right", 209.0, 126.0, 26.0, False),
        ("one unit of rack gear (44.45 mm tall)", 200.0, 100.0, 44.45, False)]),
    "baytall": ("shelftall", 3, 2, [
        ("one unit of gear, 200 wide", 200.0, 100.0, 44.45, True),
        ("ten-inch rack gear between its ears (222.25 wide)", 222.25, 100.0, 44.45, False)]),
    "bayrack": ("shelfrack", 4, 2, [
        ("ten-inch rack gear between its ears (222.25 wide, one unit)", 222.25, 100.0, 44.45, True),
        ("the same with its ears on (254 wide)", 254.0, 100.0, 44.45, True),
        ("two units of rack gear (88.9 tall)", 222.25, 100.0, 88.9, False)]),
}
for bay, (shelf, n, m, devices) in KINDS.items():
    bay_p, shelf_p = params(bay), params(shelf)
    S[shelf] = np.vstack([S[shelf], scatter(*M[shelf], 60000)])
    print(f"==== {bay}: {n} across, {m} up ====")
    print("== 1. Sound ==")
    for d in (bay, shelf):
        integrity(d, *M[d], kernel_volume(d))
    thickness(bay, *M[bay], 0.8)
    thickness(shelf, *M[shelf], 1.5)

    print("== 2. The lattice ==")
    want = (n * PX - cell_p["gap"], m * PZ - cell_p["gap"])
    got = (bay_p["body.width"], bay_p["body.height"])
    report("PASS" if np.allclose(got, want) else "FAIL", f"fills the place of {n} by {m} cells",
           f"{got[0]:.1f} by {got[1]:.1f} mm; {n} pitches and {m} rises less a gap each way is {want[0]:.1f} by {want[1]:.1f}")
    differ = [k for k in cell_p if k in bay_p and k not in ("body.width", "body.height", "u.mid", "v.mid")
              and abs(cell_p[k] - bay_p[k]) > 1e-9]
    report("PASS" if not differ else "FAIL", "every joint dimension is the cell's", f"differing: {differ or 'none'}")

    print("== 3. Joined to cells: seated without touching, held when pulled ==")
    zero, top = np.zeros(3), np.array([0, 0, m * PZ + E])
    cases = {
        f"on a row of {n} cells": ([("cell", np.array([-k * PX, 0, 0.0]), bay, np.array([0, 0, PZ + E])) for k in range(n)], 2),
        f"{n} cells on it": ([(bay, zero, "cell", np.array([-k * PX, 0, 0]) + top) for k in range(n)], 2),
        f"{n} caps on it": ([(bay, zero, "trimtop", np.array([-k * PX, 0, 0]) + top) for k in range(n)], 2),
        f"{m} cell(s) at its rail side": ([(bay, zero, "cell", np.array([-n * PX - E, 0, j * PZ])) for j in range(m)], 0),
        f"{m} cell(s) at its lips side": ([("cell", np.array([0, 0, j * PZ]), bay, np.array([-PX - E, 0, 0.0])) for j in range(m)], 0),
    }
    for name, (pairs, axis) in cases.items():
        hits = sum(clash(a, pa, b, pb) for a, pa, b, pb in pairs)
        report("PASS" if hits == 0 else "FAIL", name, f"{len(pairs)} joint(s); points of one part inside the other: {hits}")
        pull = np.array([0, 0, 1.2]) if axis == 2 else np.array([-1.2, 0, 0])
        held = [clash(a, pa, b, pb + pull) for a, pa, b, pb in pairs]
        report("PASS" if min(held) > 0 else "FAIL", f"{name}, pulled apart 1.2 mm",
               f"lips meet the rail's head at every joint: {held} points")

    print("== 4. The shelf in the bay ==")
    w = bay_p["wall"]
    place = lambda p, out=0.0, lift=E: np.stack([-(w + 0.25 + p[:, 1]), p[:, 0] - out, w + lift + p[:, 2]], 1)
    teeth = S[shelf][:, 2] < -0.05
    hits = int(inside(place(S[shelf])[~teeth], *M[bay]).sum())
    report("PASS" if hits == 0 else "FAIL", "seated", f"points of the shelf inside the bay's walls, floor, ledges or roof: {hits}")
    behind = S[shelf][teeth][:, 0].min() - bay_p["body.depth"]
    report("PASS" if 0 < behind < 1.5 else "FAIL", "latch teeth", f"they start {behind:.2f} mm behind the bay's rear edge, below its floor")
    over = int(inside(place(S[shelf], out=-0.6)[~teeth], *M[bay]).sum())
    report("PASS" if over > 0 else "FAIL", "pushed 0.6 mm past its seat", f"its face meets the ends of the bay's ledges ({over} points)")
    lifted = int(inside(place(S[shelf], lift=1.0)[~teeth], *M[bay]).sum())
    report("PASS" if lifted > 0 else "FAIL", "lifted 1 mm", f"held down by the ledges ({lifted} points)")
    roof_gap = bay_p["body.height"] - bay_p["roof"] - w - shelf_p["front.height"]
    report("PASS" if 0.3 <= roof_gap <= 0.7 else "FAIL", "the face under the roof", f"{roof_gap:.2f} mm between them")

    print("== 5. What goes on it ==")
    room_w = shelf_p["plate.width"]
    room_h = bay_p["body.height"] - bay_p["roof"] - w - shelf_p["plate.thickness"] - E
    report("NOTE", "room on the shelf", f"{room_w:.1f} mm wide, {room_h:.1f} tall; the back is open, so a device may stand out behind")
    for name, dw, dd, dh, expected in devices:
        fits = dw <= room_w and dh <= room_h
        out = max(dd - (shelf_p["plate.length"] - shelf_p["front.thickness"]), 0)
        strap = [k for k in "abc" if shelf_p[f"strap.{k}"] - shelf_p["strap.width"] / 2 >= dw / 2]
        detail = (f"fits: {room_w - dw:.1f} mm spare across, {room_h - dh:.1f} above; stands {out:.1f} mm behind the plate; "
                  f"strap slots clear of it: {', '.join(strap) or 'none, it covers them all'}") if fits \
            else f"does not fit: {dw} x {dh} against {room_w:.1f} x {room_h:.1f}"
        report(("PASS" if fits else "NOTE") if fits == expected else "FAIL", name, detail)

    print("== 6. Load on the roof ==")
    # The roof as a beam across the bay, carrying the rows above it spread
    # along its length: their skids and lips stand on it at many points.
    E_MOD, span = 1700.0, bay_p["body.width"] - 2 * w
    inertia = bay_p["body.depth"] * bay_p["roof"] ** 3 / 12
    for rows in (1, 2, 3):
        load = rows * n * 0.20 * 9.81  # a cell, carrier, Pi, cooler and fan: about 200 g
        sag = 5 * load * span ** 3 / (384 * E_MOD * inertia)
        report("PASS" if sag <= 0.25 else "NOTE", f"{rows} row(s) of cells on it",
               f"about {load:.1f} N; the {bay_p['roof']:.0f} mm roof sags about {sag:.2f} mm "
               f"(0.25 allowed: half the joint's 0.5 mm clearance, the other half kept for nylon's creep)")
    print()

print({v: results.count(v) for v in ("PASS", "FAIL", "NOTE")})
sys.exit(1 if "FAIL" in results else 0)
