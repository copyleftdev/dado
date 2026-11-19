#!/usr/bin/env python3
"""QC of the spacers, the half-width base and the half-width top cap: that
they are sound, that two halves make one place, that they join to cells and
to each other, and that air and cables have the ways through them the
design says they have."""
import json, math, subprocess, sys
import numpy as np
from fitlib import ahead, clash
from qclib import inside, integrity, kernel_volume, report, results, scene, thickness

RW = __import__("os").environ.get("RINGWRIGHT", "ringwright")
E = 0.02


def params(doc):
    out = subprocess.run([RW, "inspect", doc], capture_output=True, text=True).stdout
    return {p["id"]: p["value"] for p in json.loads(out)["result"]["parameters"]}


def samples(pos, tri):
    t = pos[tri]
    return np.vstack([pos, t.mean(1), *[(t[:, i] + t[:, j]) / 2 for i, j in ((0, 1), (1, 2), (2, 0))]])


DOCS = ("cell", "base", "spacerrow", "spacercol", "spacercross", "basehalf", "trimtophalf", "bayduo")
P = {d: params(d) for d in DOCS}
M = {d: scene(f".ringwright/{d}/view/scene.rwv") for d in DOCS}
S = {d: samples(*M[d]) for d in DOCS}
cell = P["cell"]
GAP, PX, PZ = cell["gap"], cell["body.width"] + cell["gap"], cell["body.height"] + cell["gap"]
wide = lambda d: P[d]["body.width"]
high = lambda d: P[d].get("body.height", P[d].get("base.height"))
at = lambda x=0.0, y=0.0, z=0.0: np.array([x, y, z], float)


def within(points, placed):
    """How many points are inside any of the placed parts."""
    return sum(int(inside(points - where, *M[d]).sum()) for d, where in placed)


def joint(name, a, b, where, pull):
    hits = clash(a, at(), b, where)
    report("PASS" if hits == 0 else "FAIL", name, f"seated: points of one part inside the other: {hits}")
    held = clash(a, at(), b, where + pull)
    report("PASS" if held > 0 else "FAIL", f"{name}, pulled apart 1.2 mm", f"the lips meet the rail's head: {held} points")


print("== 1. Sound ==")
for d in DOCS[2:7]:
    integrity(d, *M[d], kernel_volume(d))
    thickness(d, *M[d], 0.8)

print("== 2. Two halves make one place ==")
for d, key, whole, word in (("spacercol", "body.width", PX, "pitch across"), ("spacercross", "body.width", PX, "pitch across"),
                            ("basehalf", "body.width", PX, "pitch across"), ("trimtophalf", "body.width", PX, "pitch across"),
                            ("spacerrow", "body.height", PZ, "rise"), ("spacercross", "body.height", PZ, "rise")):
    two = 2 * (P[d][key] + GAP)
    report("PASS" if abs(two - whole) < 1e-9 else "FAIL", f"{d}, {key.split('.')[1]}",
           f"{P[d][key]:.1f} mm; two and their gaps are {two:.1f}, the {word} is {whole:.1f}")
for d in ("spacerrow", "spacercol", "spacercross"):
    skip = ("body.width", "body.height", "body.depth", "u.mid", "v.mid")
    differ = [k for k in cell if k in P[d] and k not in skip and abs(cell[k] - P[d][k]) > 1e-9]
    report("PASS" if not differ else "FAIL", f"{d}: every joint dimension is the cell's", f"differing: {differ or 'none'}")
report("PASS" if P["spacerrow"]["body.width"] == cell["body.width"] and P["spacercol"]["body.height"] == cell["body.height"] else "FAIL",
       "the other way each is a whole place", f"row spacer {wide('spacerrow'):.0f} wide, column spacer {high('spacercol'):.0f} high, as a cell")

print("== 3. Joined: seated without touching, held when pulled ==")
up, out = at(z=1.2), at(x=-1.2)
on = lambda lower: at(z=high(lower) + GAP + E)
beside = lambda first: at(x=-(wide(first) + GAP) - E)
JOINTS = [
    ("a row spacer on a cell", "cell", "spacerrow", on("cell"), up),
    ("a cell on a row spacer", "spacerrow", "cell", on("spacerrow"), up),
    ("a row spacer on a row spacer", "spacerrow", "spacerrow", on("spacerrow"), up),
    ("a column spacer on a column spacer", "spacercol", "spacercol", on("spacercol"), up),
    ("a cross on a column spacer", "spacercol", "spacercross", on("spacercol"), up),
    ("a column spacer on a cross", "spacercross", "spacercol", on("spacercross"), up),
    ("a cross on a cross", "spacercross", "spacercross", on("spacercross"), up),
    ("a column spacer on its base", "basehalf", "spacercol", on("basehalf"), up),
    ("a half top cap on a column spacer", "spacercol", "trimtophalf", on("spacercol"), up),
    ("a column spacer at a cell's rail side", "cell", "spacercol", beside("cell"), out),
    ("a cell at a column spacer's rail side", "spacercol", "cell", beside("spacercol"), out),
    ("a column spacer beside a column spacer", "spacercol", "spacercol", beside("spacercol"), out),
    ("a half base at a base's rail side", "base", "basehalf", beside("base"), out),
    ("a base at a half base's rail side", "basehalf", "base", beside("basehalf"), out),
]
LOOSE = (("row spacers side by side", "spacerrow", "spacerrow"), ("a cross beside a row spacer", "spacerrow", "spacercross"),
         ("a row spacer beside a cross", "spacercross", "spacerrow"))
# Every joint seated and pulled, asked of Ringwright in one go.
ahead([(a, at(), b, where + d) for _, a, b, where, pull in JOINTS for d in (at(), pull)]
      + [(a, at(), b, at(x=-(wide(a) + GAP))) for _, a, b in LOOSE])
for each in JOINTS:
    joint(*each)
for name, a, b in LOOSE:
    hits = clash(a, at(), b, at(x=-(wide(a) + GAP)))
    report("PASS" if hits == 0 else "FAIL", name, f"no joint between them, {GAP} mm apart: points of one inside the other: {hits}")

print("== 4. Back in step ==")
z = high("cell") + GAP + 2 * (high("spacerrow") + GAP)
report("PASS" if abs(z - 2 * PZ) < 1e-9 else "FAIL", "a cell, two row spacers, a cell",
       f"the upper cell stands {z:.1f} mm up: exactly two rows ({2 * PZ:.1f}), so it lines up with a neighbour that has no spacers")
x = wide("cell") + GAP + 2 * (wide("spacercol") + GAP)
report("PASS" if abs(x - 2 * PX) < 1e-9 else "FAIL", "a cell, two column spacers, a cell",
       f"the far cell is {x:.1f} mm over: exactly two places ({2 * PX:.1f}), so a bay above still fits")

# A bay two places wide on two column spacers and a cell.
under = [("spacercol", at()), ("spacercol", at(x=-(wide("spacercol") + GAP))), ("cell", at(x=-PX))]
ahead([(d, where, "bayduo", at(z=PZ + E + lift)) for d, where in under for lift in (0, 1.2)])
seat = [clash(d, where, "bayduo", at(z=PZ + E)) for d, where in under]
held = [clash(d, where, "bayduo", at(z=PZ + E + 1.2)) for d, where in under]
report("PASS" if sum(seat) == 0 and held[2] > 0 else "FAIL", "a two-wide bay on two column spacers and a cell",
       f"it seats without touching ({sum(seat)} points); pulled up 1.2 mm it is held by the cell's rail ({held[2]} points)")
report("NOTE", "a bay over column spacers is not held by them", f"its lips fall between the two spacers' rails ({held[0] + held[1]} points meet when pulled): "
       "it is held only where it stands on cells")

print("== 5. Ways through ==")
col, row, cross = P["spacercol"], P["spacerrow"], P["spacercross"]
w = cell["wall"]
grid = lambda xs, ys, zs: np.array([[a, b, c] for a in xs for b in ys for c in zs], float)
# The shaft: a column spacer, a cross, a column spacer, stacked.
stack, z0 = [], 0.0
for d in ("spacercol", "spacercross", "spacercol"):
    stack.append((d, at(z=z0))); z0 += high(d) + GAP
shaft_y = (col["body.depth"] - col["shaft.depth"] + 1, col["body.depth"] - 0.5)
pts = grid(np.linspace(-wide("spacercol") + w + 0.5, -w - 0.5, 7), np.linspace(*shaft_y, 9), np.linspace(-GAP - 2, z0 + 2, 40))
hits = within(pts, stack)
report("PASS" if hits == 0 else "FAIL", "the shaft: a column spacer, a cross and a column spacer stacked",
       f"{len(pts)} points from under the stack to over it, in the rear {col['shaft.depth']:.0f} mm: inside a part: {hits}")
area = (wide("spacercol") - 2 * w) * col["shaft.depth"]
for name, dia in (("standard cables, 6.0 mm", 6.0), ("slim 28 AWG cables, 3.8 mm", 3.8)):
    n = int(0.65 * area / (math.pi * dia ** 2 / 4))
    report("NOTE", f"the shaft takes {n} {name}", f"{area:.0f} mm2, filled no more than 65 %")
# The tray: a row spacer, a cross, a row spacer, in a line.
line = [("spacerrow", at()), ("spacercross", at(x=-PX)), ("spacerrow", at(x=-PX - wide("spacercross") - GAP))]
far = PX + wide("spacercross") + GAP + wide("spacerrow")
pts = grid(np.linspace(-far + 0.5, -0.5, 60), np.linspace(row["body.depth"] - row["tray.depth"] + 1, row["body.depth"] - 0.5, 7),
           np.linspace(w + 0.5, high("spacerrow") - w - 0.5, 4))
hits = within(pts, line)
report("PASS" if hits == 0 else "FAIL", "the tray: a row spacer, a cross and a row spacer in a line",
       f"{len(pts)} points from one end to the other, in the rear {row['tray.depth']:.0f} mm between floor and roof: inside a part: {hits}")
tray = (high("spacerrow") - 2 * w) * row["tray.depth"]
report("NOTE", f"the tray takes {int(0.65 * tray / (math.pi * 9))} standard cables", f"{tray:.0f} mm2, filled no more than 65 %; they are laid in from behind")
report("PASS" if cross["body.depth"] == row["body.depth"] - row["tray.depth"] == col["body.depth"] - col["shaft.depth"] else "FAIL",
       "the cross ends where the tray and the shaft begin", f"{cross['body.depth']:.0f} mm deep; behind it the tray and the shaft meet with nothing between")
# Air: straight through each slot, front to back.
for d, across, rows in (("spacerrow", 5, 1), ("spacercol", 2, 3), ("spacercross", 2, 1)):
    p = P[d]
    xs = [-(p["u.mid"] - (across - 1) / 2 * p["slot.pitch"] + k * p["slot.pitch"]) for k in range(across)]
    zs = [p["v.mid"] - (rows - 1) / 2 * p["slot.step"] + r * p["slot.step"] for r in range(rows)]
    pts = grid(xs, np.linspace(-1, p["body.depth"] + 1, 25), zs)
    hits = within(pts, [(d, at())])
    report("PASS" if hits == 0 else "FAIL", f"air through {d}",
           f"{across * rows} slots, {across * rows * p['slot.width'] * p['slot.height'] / 100:.1f} cm2; a straight line through each, front to back: blocked points: {hits}")

print("== 6. Load ==")
# Behind its side walls a row spacer's roof is a shelf held along its front edge,
# carrying the back two fifths of whatever column stands on it.
E_MOD, L, t = 1700.0, row["tray.depth"], w
inertia = wide("spacerrow") * t ** 3 / 12
for rows in (3, 9):
    load = rows * 0.20 * 9.81 * L / row["body.depth"]
    sag = load * L ** 3 / (8 * E_MOD * inertia)
    report("PASS" if sag <= 0.25 else "FAIL", f"{rows} loaded cells on a row spacer",
           f"the roof behind the side walls carries about {load:.1f} N and sags about {sag:.2f} mm (0.25 allowed, as for a bay's roof)")

print("== 7. Not checked, and what to know ==")
report("NOTE", "no side joint on the half-height parts", "row spacers and crosses are held from above and below only; the columns stay joined by their cells")
report("NOTE", "a spacer runs the whole line", "a row spacer under every column of its row, with a cross wherever it meets a column of spacers; "
       "a column spacer in every row of its column. A bay cannot stand across a single column spacer")
report("NOTE", "the wall's edges", "there is no side cap half a row high: at a row of spacers the side caps skip 22.8 mm")
report("NOTE", "cables", "a lead leaves a port at the back of a cell, turns behind the wall and is laid into a tray or a shaft from behind; "
       "the bend that takes, and whether air moves usefully through the slots, are not modelled")
print({v: results.count(v) for v in ("PASS", "FAIL", "NOTE")})
sys.exit(1 if "FAIL" in results else 0)
