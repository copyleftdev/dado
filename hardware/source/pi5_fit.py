#!/usr/bin/env python3
"""Seats Raspberry Pi's own model of the Pi 5 on the carrier, in the cell,
and checks the design against it: what the board really measures, whether
it collides with anything, whether the screw holes line up, and how the
ports come out through the carrier's back wall."""
import json, struct, subprocess, sys
import numpy as np
from qclib import inside, ray_hits, report, results, scene

rng = np.random.default_rng(20261118)
RW = __import__("os").environ.get("RINGWRIGHT", "ringwright")


def params(doc):
    out = subprocess.run([RW, "inspect", doc], capture_output=True, text=True).stdout
    return {p["id"]: p["value"] for p in json.loads(out)["result"]["parameters"]}


car, cell = params("carrier"), params("cell")
pi, pi_tri = scene("pi5.rwv")
carrier, carrier_tri = scene(".ringwright/carrier/view/scene.rwv")
sleeve, sleeve_tri = scene(".ringwright/cell/view/scene.rwv")

print("== 1. The board as Raspberry Pi model it ==")
lo, hi = pi.min(0), pi.max(0)
# The board itself: the two levels where most of the model's flat area lies.
z = np.round(pi[:, 2], 2)
levels, counts = np.unique(z, return_counts=True)
flat = levels[np.argsort(counts)[-2:]]
bottom, top = float(flat.min()), float(flat.max())
edge = pi[(pi[:, 2] > bottom - 0.01) & (pi[:, 2] < top + 0.01)]
blo, bhi = np.percentile(edge[:, 0], [0.5, 99.5]), np.percentile(edge[:, 1], [0.5, 99.5])
facts = {
    "board length": (85.0, 85.0), "board width": (56.0, 56.0),
    "board thickness": (top - bottom, car["board.thickness"]),
    "ports beyond the port edge": (hi[0] - 85.0, car["port.overhang"]),
    "tallest part above the board": (hi[2] - top, car["port.height"]),
    "deepest part under the board": (bottom - lo[2], car["post.height"]),
    "connectors beyond the long edge": (-lo[1], car["margin"]),
    "card slot end beyond the board": (-lo[0], car["board.front"] - car["front.thickness"]),
}
print(f"   board lies from z {bottom:.2f} to {top:.2f} in the model; model extent "
      f"{lo.round(2).tolist()} to {hi.round(2).tolist()}")
for name, (measured, allowed) in facts.items():
    if name.startswith("board l") or name.startswith("board w"):
        continue
    exact = name in ("board thickness", "ports beyond the port edge")
    ok = abs(measured - allowed) <= 0.05 if exact else measured <= allowed + 1e-6
    word = "the design assumed" if name in ("board thickness", "ports beyond the port edge",
                                             "tallest part above the board") else "the design allows"
    report("PASS" if ok else "FAIL", name, f"model {measured:.2f} mm; {word} {allowed:.2f}")


def seat(p):
    """Model coordinates to the carrier's: the model's ports are at its far
    end and so are the carrier's, so the board goes on as it is drawn."""
    x = car["board.front"] + p[:, 0]
    y = car["margin"] + p[:, 1]
    zc = car["plate.thickness"] + car["post.height"] + (p[:, 2] - bottom)
    return np.stack([x, y, zc], 1)


def to_cell(p, slack=0.25, lift=0.02):
    w = cell["wall"]
    return np.stack([-(w + slack + p[:, 1]), p[:, 0], w + lift + p[:, 2]], 1)


print("== 2. Seated on the carrier, in the cell ==")
pick = rng.choice(len(pi), 60000, replace=False)
tri_mid = pi[pi_tri[rng.choice(len(pi_tri), 40000, replace=False)]].mean(1)
pts = seat(np.vstack([pi[pick], tri_mid]))
lifted = pts + (0, 0, 0.03)  # resting on the posts is touching, not colliding
hit = lifted[inside(lifted, carrier, carrier_tri)]
report("PASS" if len(hit) == 0 else "FAIL", "the board against the carrier",
       f"{len(pts):,} points of the model; inside the carrier: {len(hit)}"
       + (f", e.g. {hit[0].round(2).tolist()} (from the front, across, up)" if len(hit) else ""))
hit = pts[inside(to_cell(pts), sleeve, sleeve_tri)]
report("PASS" if len(hit) == 0 else "FAIL", "the board against the cell",
       f"inside the cell's walls, ledges or roof: {len(hit)}")
roof = cell["body.height"] - 2 * cell["wall"] - 0.02 - pts[:, 2].max()
side = min(pts[:, 1].min(), car["plate.width"] - pts[:, 1].max()) + 0.25
report("PASS" if roof > 0 and side > 0 else "FAIL", "room around the board",
       f"{roof:.1f} mm above its tallest part to the cell's roof; {side:.2f} mm from its widest part to a side wall")

print("== 3. Screws ==")
px, py = car["post.x"], car["post.y"]
posts = [(px, py), (px + car["hole.spacing_x"], py), (px + car["hole.spacing_x"], py + car["hole.spacing_y"]),
         (px, py + car["hole.spacing_y"])]
board = seat(pi)
clear = []
for cx, cy in posts:
    # How near the board's material comes to the screw's axis, through the board's thickness.
    near = board[(np.abs(board[:, 2] - (car["plate.thickness"] + car["post.height"] + (top - bottom) / 2)) < 1.0)]
    clear.append(float(np.hypot(near[:, 0] - cx, near[:, 1] - cy).min()))
report("PASS" if min(clear) >= 1.2 else "FAIL", "the four posts under the board's four holes",
       f"nearest board material to each screw axis: {[round(c, 2) for c in clear]} mm "
       f"(a 2.7 mm hole leaves 1.35; an M2.5 screw needs 1.25)")

print("== 4. The ports through the back wall ==")
edge = car["board.front"] + 85.0
front = board[board[:, 0] > edge + 0.5]  # what stands beyond the board's port edge
order = np.sort(np.unique(np.round(front[:, 1], 1)))
gaps = np.flatnonzero(np.diff(order) > 1.0)
groups = np.split(order, gaps + 1)
win_lo, win_hi = car["margin"] + 1, car["margin"] + car["board.width"] - 1
win_z0, win_z1 = car["band.high"], car["board.top"] + car["port.height"] + 0.6
worst = 99.0
for g in groups:
    part = front[(front[:, 1] >= g.min() - 0.05) & (front[:, 1] <= g.max() + 0.05)]
    y0, y1, z0, z1 = part[:, 1].min(), part[:, 1].max(), part[:, 2].min(), part[:, 2].max()
    margin = min(y0 - win_lo, win_hi - y1, z0 - win_z0, win_z1 - z1)
    worst = min(worst, margin)
    print(f"   a port {y1 - y0:.1f} wide, {z1 - z0:.1f} tall, standing {part[:, 0].max() - edge:.2f} "
          f"beyond the board: {margin:.2f} mm inside the window at its nearest")
report("PASS" if worst > 0 else "FAIL", "every port passes through the window",
       f"{len(groups)} ports; the tightest clears the window's edge by {worst:.2f} mm "
       f"(window {win_hi - win_lo:.0f} wide, {win_z1 - win_z0:.1f} tall)")
proud = front[:, 0].max() - car["plate.length"]
report("PASS" if abs(proud) < 0.3 else "FAIL", "the ports against the back wall's rear face",
       f"they end {proud:+.2f} mm from it (positive is proud)")
card = car["board.front"] - car["front.thickness"]
report("NOTE", "the card", f"{card:.2f} mm between the board's card end and the face: a card cannot be drawn in that "
       f"space, so it comes out through the slot in the face")

print()
print({v: results.count(v) for v in ("PASS", "FAIL", "NOTE")})
json.dump({"bottom": bottom, "top": top}, open("pi5-seat.json", "w"))
sys.exit(1 if "FAIL" in results else 0)
