#!/usr/bin/env python3
"""Quality assurance of every part as one system, and of the process that made
them: the cell, carrier, base and caps, the five bays and what slides into
them, and the spacers. Where the QC scripts ask "is this part right?", this
asks "can we trust the parts, their agreement with each other, and the QC?"

Planted defects (does the QC catch them?) are in mutate.py; this file covers
the rest."""
import json, os, re, shutil, subprocess, sys, tempfile
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from qclib import inside, report, results, scene

RW = __import__("os").environ.get("RINGWRIGHT", "ringwright")
HERE = os.path.dirname(os.path.abspath(__file__))
# Every part: the script that builds it, and what the script is told.
DOCS = {"cell": ("build_cell.py",), "carrier": ("build_carrier.py",), "base": ("build_base.py",), "basehalf": ("build_base.py", "basehalf"),
        **{d: ("build_trim.py", d) for d in ("trimtop", "trimrail", "trimlip", "trimtophalf")},
        **{d: ("build_bay.py", d) for d in ("bay", "baytall", "bayrack", "bayduo", "bayagx")},
        **{d: ("build_shelf.py", d) for d in ("shelf", "shelftall", "shelfrack")},
        "orin": ("build_orin.py",), "agx": ("build_agx.py",),
        **{d: ("build_spacer.py", d) for d in ("spacerrow", "spacercol", "spacercross")}}
# Each bay with what slides into it.
PAIRS = {"bay": "shelf", "baytall": "shelftall", "bayrack": "shelfrack", "bayduo": "orin", "bayagx": "agx"}


def rw(*args, cwd=HERE, stdin=None):
    out = subprocess.run([RW, *args], input=stdin, capture_output=True, text=True, cwd=cwd)
    return json.loads(out.stdout)


def state(doc, cwd=HERE):
    """Head revision, the digest of its document, its parameters, and the
    kernel's volume of its body."""
    head = rw("inspect", doc, cwd=cwd)["result"]
    tx = {"schema_version": 1, "document": doc, "base_revision": head["revision"],
          "operations": [], "checks": []}
    dry = rw("dry-run", "--brief", "-", cwd=cwd, stdin=json.dumps(tx))["result"]
    record = json.load(open(os.path.join(cwd, ".ringwright", doc, "revisions", head["revision"] + ".json")))
    params = {p["id"]: p["value"] for p in head["parameters"]}
    return head["revision"], record["document_digest"], params, dry["measurements"]["body"]["kernel_volume"]


QUICK = bool(os.environ.get("QA_QUICK"))  # skip the rebuild and the exports
print("== 1. Can the designs be rebuilt from their scripts, identically? ==")
now = {doc: state(doc) for doc in DOCS}
with tempfile.TemporaryDirectory() as tmp:
  if not QUICK:
    for script in sorted({cmd[0] for cmd in DOCS.values()}):
        shutil.copy(os.path.join(HERE, script), tmp)
    quiet = dict(os.environ, OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1")
    with ThreadPoolExecutor(max_workers=10) as pool:
        runs = list(pool.map(lambda cmd: subprocess.run([sys.executable, *cmd], cwd=tmp, capture_output=True, text=True, env=quiet), DOCS.values()))
    for (doc, cmd), run in zip(DOCS.items(), runs):
        if run.returncode:
            report("FAIL", f"{doc} rebuilds from {cmd[0]}", run.stdout[-300:] + run.stderr[-300:])
            continue
        rev, digest, _, volume = state(doc, cwd=tmp)
        same = digest == now[doc][1]
        report("PASS" if same and rev == now[doc][0] else "FAIL", f"{doc} rebuilds from {cmd[0]}",
               f"a fresh store reaches {rev} with the same document digest as the working store: {same}; "
               f"volume {volume:.3f} against {now[doc][3]:.3f} mm3")

print("== 2. Do the parts agree on the dimensions they share? ==")
cell, carrier, base = (now[d][2] for d in ("cell", "carrier", "base"))
shared = ["body.width", "gap", "stem.width", "head.width", "stem.height", "head.height", "flange.height",
          "web.width", "catch.from_front", "tooth.length", "tooth.ramp", "notch.depth", "front.relief"]
bad = [k for k in shared if abs(cell[k] - base[k]) > 1e-9]
report("PASS" if not bad else "FAIL", "cell and base: the joint", f"{len(shared)} shared dimensions; disagreeing: {bad}")
pairs = [("the reach of a cell's teeth", cell["tooth.reach"], base["cell.reach"]),
         ("play across the stacking joint", cell["float"], base["base.float"]),
         ("finger length", cell["finger.length"], base["finger.length"])]
pairs += [("cell and base depth: one front plane", cell["body.depth"], base["base.depth"]),
          ("cell depth", cell["body.depth"], carrier["cell.depth"]),
          ("the ledges' cut and the carrier's face: flush", cell["ledge.cut"], carrier["front.thickness"]),
          ("inside width", cell["body.width"] - 2 * cell["wall"], carrier["cell.width"]),
          ("inside height", cell["body.height"] - 2 * cell["wall"], carrier["cell.height"]),
          ("underside of the ledges", cell["ledge.height"], carrier["ledge.under"]),
          ("reach of the ledges", cell["ledge.size"], carrier["ledge.reach"])]
for name, a, b in pairs:
    report("PASS" if abs(a - b) < 1e-9 else "FAIL", name, f"{a} and {b}")
for doc in ("trimtop", "trimrail", "trimlip"):
    trim = now[doc][2]
    differs = sorted(k for k in cell if abs(cell[k] - trim[k]) > 1e-9)
    allowed = {"trimtop": ["body.height", "v.mid"], "trimrail": ["body.width", "u.mid"], "trimlip": ["body.width", "u.mid"]}[doc]
    report("PASS" if differs == sorted(allowed) else "FAIL", f"cell and {doc}",
           f"{len(cell)} dimensions; differing only where a cap is a plate: {differs}")

# Everything drawn with the cell's own joint keeps the cell's dimensions, but for its own size.
SIZE = ["body.width", "body.height", "body.depth", "u.mid", "v.mid"]
for doc in ("bay", "baytall", "bayrack", "bayduo", "bayagx", "spacerrow", "spacercol", "spacercross", "trimtophalf"):
    part = now[doc][2]
    differs = sorted(k for k in cell if k in part and abs(cell[k] - part[k]) > 1e-9)
    report("PASS" if set(differs) <= set(SIZE) else "FAIL", f"cell and {doc}: the joint",
           f"{sum(k in part for k in cell)} shared dimensions; differing beyond its own size: {sorted(set(differs) - set(SIZE)) or 'none'}")
half = now["basehalf"][2]
differs = sorted(k for k in base if abs(base[k] - half[k]) > 1e-9)
report("PASS" if differs == ["body.width", "u.mid"] else "FAIL", "base and half base", f"{len(base)} dimensions; differing: {differs}")
# A bay and what slides into it are built by different scripts, each of which is told the bay's inside.
for bay_doc, tray_doc in PAIRS.items():
    bay, tray = now[bay_doc][2], now[tray_doc][2]
    inside_of = {"width": bay["body.width"] - 2 * bay["wall"], "height": bay["body.height"] - bay["wall"] - bay["roof"], "depth": bay["body.depth"]}
    told = {"width": tray["bay.width"], "height": tray["bay.height"], "depth": tray["bay.depth"]}
    off = [k for k in told if abs(told[k] - inside_of[k]) > 1e-9]
    report("PASS" if not off else "FAIL", f"{bay_doc} and {tray_doc}: the bay's inside",
           f"the bay is {inside_of['width']:.1f} by {inside_of['height']:.1f} by {inside_of['depth']:.0f} inside; "
           f"the {tray_doc} was built for {told['width']:.1f} by {told['height']:.1f} by {told['depth']:.0f}; disagreeing: {off or 'none'}")
    for name, a, b in (("underside of the ledges", bay["ledge.height"], tray["plate.thickness"] + 0.5),
                       ("the ledges' cut and the face: flush", bay["ledge.cut"], tray["front.thickness"])):
        report("PASS" if abs(a - b) < 1e-9 else "FAIL", f"{bay_doc} and {tray_doc}: {name}", f"{a} and {b}")

print("== 3. Do the QC scripts measure against the dimensions the parts now have? ==")


def constants(script, names):
    """The numbers a QC script hard-codes, read from the line that sets them."""
    text = open(os.path.join(HERE, script)).read()
    m = re.search(r"^" + re.escape(names) + r" = ([^#\n]+)", text, re.M)
    return [float(x) for x in m.group(1).split(",")] if m else None


rail = cell["stem.height"] + cell["head.height"]
expect = [
    ("fit_check.py", "W, H, GAP, DEPTH, WALL, FLOAT, SIDE_FLOAT",
     [cell["body.width"], cell["body.height"], cell["gap"], cell["body.depth"], cell["wall"],
      cell["float"], cell["side.float"]]),
    ("qc.py", "W, H, GAP, DEPTH, WALL", [cell["body.width"], cell["body.height"], cell["gap"],
                                          cell["body.depth"], cell["wall"]]),
    ("qc_carrier.py", "PLATE, PLATE_W, PLATE_L, FRONT_T, FRONT_H",
     [carrier["plate.thickness"], carrier["plate.width"], carrier["plate.length"],
      carrier["front.thickness"], carrier["front.height"]]),
    ("qc_carrier.py", "TOOTH, RAMP, BEHIND", [carrier["tooth.depth"], carrier["tooth.ramp"],
                                               carrier["tooth.behind"]]),
    ("qc_base.py", "W, GAP, RAIL, HB, DEPTH, SETBACK, PAD",
     [base["body.width"], base["gap"], rail, base["base.height"], base["base.depth"],
      0.0, base["pad.height"]]),
]
for script, names, want in expect:
    got = constants(script, names)
    ok = got is not None and np.allclose(got, want)
    report("PASS" if ok else "FAIL", f"{script}: {names}", f"script has {got}; the parts have {want}")

print("== 4. Assembled: two bases, four cells two by two, a carrier in each, with plugs behind it ==")
meshes = {d: scene(os.path.join(HERE, ".ringwright", d, "view", "scene.rwv")) for d in ("cell", "carrier", "base")}


def samples(pos, tri):
    t = pos[tri]
    mids = [(t[:, i] + t[:, j]) / 2 for i, j in ((0, 1), (1, 2), (2, 0))]
    return np.vstack([pos, t.mean(1), *mids])


E = 0.02
PX, PZ = cell["body.width"] + cell["gap"], cell["body.height"] + cell["gap"]
parts = []  # name, positions, triangles, samples, kind
for i in (0, 1):
    off = np.array([-i * (PX + E), 0, 0])
    pos, tri = meshes["base"]
    parts.append((f"base {i}", pos + off, tri, samples(pos, tri) + off, "base"))
    for k in (0, 1):
        at = np.array([-i * (PX + E), 0.0, base["base.height"] + base["gap"] + E + k * (PZ + E)])
        pos, tri = meshes["cell"]
        parts.append((f"cell {i},{k}", pos + at, tri, samples(pos, tri) + at, "cell"))
        pos, tri = meshes["carrier"]
        wall = cell["wall"]
        place = lambda p: np.stack([-(wall + 0.25 + p[:, 1]), p[:, 0] - E, wall + E + p[:, 2]], 1) + at
        parts.append((f"carrier {i},{k}", place(pos), tri, place(samples(pos, tri)), "carrier"))
        # Three plugs as a block behind the carrier's back wall, where the ports come out.
        g = [np.linspace(a, b, 7) for a, b in ((carrier["plate.length"] + 0.05, carrier["plate.length"] + 18),
                                              (carrier["margin"] + 1.7, carrier["margin"] + 54.3),
                                              (carrier["board.top"], carrier["board.top"] + 16.2))]
        block = np.array(np.meshgrid(*g)).reshape(3, -1).T
        parts.append((f"fan {i},{k}", None, None, place(block), "fan"))
pairs = clashes = 0
expected = []
for a in range(len(parts)):
    for b in range(len(parts)):
        na, pa, ta, sa, ka = parts[a]
        nb, pb, tb, sb, kb = parts[b]
        if a == b or pa is None:
            continue
        lo, hi = pa.min(0) - 0.5, pa.max(0) + 0.5
        near = sb[((sb >= lo) & (sb <= hi)).all(1)]
        if not len(near):
            continue
        pairs += 1
        hit = near[inside(near, pa, ta)]
        if not len(hit):
            continue
        # The one meeting that is meant: a carrier's teeth on its own cell's rear edge.
        own = {ka, kb} == {"cell", "carrier"} and na.split()[1] == nb.split()[1]
        teeth = own and (hit[:, 1] > cell["body.depth"] - 1).all()
        if teeth:
            expected.append(f"{nb} on {na}")
        else:
            clashes += 1
            print(f"      {nb} is inside {na} at {len(hit)} points, e.g. {hit[0].round(2).tolist()}")
report("PASS" if clashes == 0 else "FAIL", "nothing collides that should not",
       f"{len(parts)} bodies, {pairs} neighbouring pairs tested both ways; unexpected collisions in {clashes}")
report("PASS" if not expected else "FAIL", "every carrier's latch rests unloaded",
       f"carriers whose teeth press on their cell at rest: {len(set(expected))} of 4")

print("== 4b. Assembled: a wall with every kind of part in it ==")
# Two columns of cells, a column of spacers, a third column of cells; a line of row spacers between two rows, with a
# cross where it meets the column of spacers; a Jetson bay with its tray across the first two columns; caps on top.
wall_docs = ("cell", "carrier", "base", "basehalf", "spacerrow", "spacercol", "spacercross", "bayduo", "orin", "trimtop", "trimtophalf")
mesh = {d: scene(os.path.join(HERE, ".ringwright", d, "view", "scene.rwv")) for d in wall_docs}
duo, half = now["bayduo"][2], now["spacercol"][2]
HX, HZ = half["body.width"] + cell["gap"] + E, now["spacerrow"][2]["body.height"] + cell["gap"] + E
CX, CZ, Z0 = PX + E, PZ + E, base["base.height"] + base["gap"] + E
columns = [("cell", 0.0), ("cell", -CX), ("half", -2 * CX), ("cell", -2 * CX - HX)]
ZT = Z0 + 2 * CZ + HZ  # the top of the second row of cells
wall = []  # name, kind, positions, triangles, samples


def put(name, doc, at, slid=None):
    pos, tri = mesh[doc]
    w = cell["wall"]
    place = (lambda p: np.stack([-(w + 0.25 + p[:, 1]), p[:, 0] - E, w + E + p[:, 2]], 1) + at) if slid else (lambda p: p + at)
    wall.append((name, doc, place(pos), tri, place(samples(pos, tri))))


for c, (kind, x) in enumerate(columns):
    whole = kind == "cell"
    put(f"base {c}", "base" if whole else "basehalf", np.array([x, 0, 0.0]))
    levels = [Z0, Z0 + CZ + HZ] + ([ZT, ZT + CZ] if c >= 2 else [])  # the first two columns carry the bay instead
    for k, z in enumerate(levels):
        put(f"{'cell' if whole else 'column spacer'} {c},{k}", "cell" if whole else "spacercol", np.array([x, 0, z]))
        if whole:
            put(f"carrier {c},{k}", "carrier", np.array([x, 0, z]), slid=True)
    put(f"{'row spacer' if whole else 'cross'} {c}", "spacerrow" if whole else "spacercross", np.array([x, 0, Z0 + CZ]))
    put(f"cap {c}", "trimtop" if whole else "trimtophalf", np.array([x, 0, ZT + 2 * CZ]))
put("bay", "bayduo", np.array([0, 0, ZT]))
put("tray", "orin", np.array([0, 0, ZT]), slid=True)
tested = clashes = 0
resting = []
for na, da, pa, ta, sa in wall:
    lo, hi = pa.min(0) - 0.5, pa.max(0) + 0.5
    for nb, db, pb, tb, sb in wall:
        if na == nb:
            continue
        near = sb[((sb >= lo) & (sb <= hi)).all(1)]
        if not len(near):
            continue
        tested += 1
        hit = near[inside(near, pa, ta)]
        if not len(hit):
            continue
        # The one meeting that is meant: the teeth of a carrier or a tray behind the rear edge of what it is in.
        own = (da, db) in (("cell", "carrier"), ("bayduo", "orin")) and (na.split()[-1] == nb.split()[-1] or da == "bayduo")
        if own and (hit[:, 1] > cell["body.depth"] - 1).all():
            resting.append(nb)
        else:
            clashes += 1
            print(f"      {nb} is inside {na} at {len(hit)} points, e.g. {hit[0].round(2).tolist()}")
report("PASS" if clashes == 0 else "FAIL", "nothing in the wall collides that should not",
       f"{len(wall)} bodies of {len(wall_docs)} kinds, {tested} neighbouring pairs tested both ways; unexpected collisions in {clashes}")
report("PASS" if not resting else "FAIL", "every latch in the wall rests unloaded", f"carriers or trays whose teeth press at rest: {sorted(set(resting)) or 'none'}")
size = np.vstack([p for _, _, p, _, _ in wall])
across = 3 * PX + HX - cell["gap"]
report("PASS" if abs((size[:, 0].max() - size[:, 0].min()) - (across + 2 * 3 * E + cell["gap"] + (cell["stem.height"] + cell["head.height"]))) < 0.2 else "NOTE",
       "the wall's width", f"{size[:, 0].max() - size[:, 0].min():.1f} mm over its joints; three places and a half is {across:.1f} between the outer walls")

print("== 5. The engine's own check of intent, before the corners are rounded ==")
for doc in (() if QUICK else DOCS):
    out = rw("export", "--document", doc, "--revision", "r2")
    v = out["result"]["validation"] if out["ok"] else {}
    intent = v.get("intent", {})
    ok = out["ok"] and v.get("passed") and intent.get("checked") and intent.get("disagreements") == 0
    report("PASS" if ok else "FAIL", f"{doc} at r2",
           f"file validated: {v.get('passed')}; shape compared with the plan at {intent.get('samples')} points, "
           f"{intent.get('disagreements')} disagree" if out["ok"] else out["failure"]["message"])
report("NOTE", "the sleeves at r3", "for the cell, the bases, the bays and the spacers the rounded corners are the only change "
       "after r2, and the engine cannot compare a part this thin once they are in; their volume was checked by hand instead")

print()
print({v: results.count(v) for v in ("PASS", "FAIL", "NOTE")})
sys.exit(1 if "FAIL" in results else 0)
