#!/usr/bin/env python3
"""Builds the shelf: what goes into a bay. A plate that slides on the bay's
floor under its ledges, a closed face like a carrier's (a pull, a row of air
slots, a label flat), the carrier's two latch fingers, and no back wall.

Switches and hubs have no standard size, so nothing on the shelf is fitted
to one: the plate has rows of slots for two straps, at three widths, and the
device sits with its ports at the open back, where the cables are.

x runs from the front, y across, z up."""
import json, sys, subprocess

RW = __import__("os").environ.get("RINGWRIGHT", "ringwright")
# Which bay it is for: inside width and height of that bay, slots in its
# face, and how far either side of centre its three pairs of strap slots are.
KINDS = {"shelf": (202.2, 32.0, 17, (54, 75, 84)), "shelftall": (202.2, 74.6, 17, (54, 75, 84)),
         "shelfrack": (272.8, 72.6, 23, (84, 100, 115)), "shelfduo": (131.6, 78.6, 11, (30, 45, 58))}
DOC = sys.argv[1] if len(sys.argv) > 1 else "shelf"


def rw(*args, stdin=None):
    out = subprocess.run([RW, *args], input=stdin, capture_output=True, text=True)
    return json.loads(out.stdout)


def ref(feature, role, expect=1):
    return {"feature": feature, "role": role, "expect": expect}


P = {
    "bay.width": (KINDS[DOC][0], "Inside the bay, across"),
    "bay.height": (KINDS[DOC][1], "Inside the bay, floor to roof"),
    "bay.depth": (100, "Bay, front to back"),
    "back.clear": (3, "The plate ends this far short of the bay's back"),
    "plate.thickness": (1.8, "Leaves 0.5 under the bay's ledges"),
    "side.slack": (0.5, "Shelf narrower than the bay, in all"),
    "roof.slack": (0.5, "Face lower than the bay's roof"),
    "front.thickness": (2.6, "The face; it stops on the ends of the bay's ledges"),
    "air.height": (7, "A row of slots across the face"),
    "slot.width": (8, "Each slot"),
    "slot.pitch": (10.5, "Slot to slot, as on a carrier: seventeen of them"),
    "top.bar": (3, "The face's top edge, which the pull grows out of"),
    "label.width": (44, "A flat for a label"),
    "label.low": (10, "Its lower edge"),
    "label.high": (20, "Its upper edge"),
    "label.depth": (0.4, "Sunk, so a label's edges are protected"),
    "pull.reach": (6, "The pull: a rail along the face's top edge"),
    "pull.inset": (2, "The rail's ends in from the face's sides"),
    "pull.lip": (1.5, "A lip under its edge"),
    "nose.taper": (2, "Cut from each back corner"),
    "finger.root": (86, "Where the fingers leave the plate, from the front"),
    "finger.width": (8, "Each finger"),
    "finger.apart": (30, "Each finger's near edge from the centre line"),
    "finger.slot": (1, "Cut either side of a finger to free it"),
    "tooth.depth": (1.2, "Tooth below the finger"),
    "tooth.ramp": (0.93, "Its front ramp"),
    "tooth.lead": (2.75, "Its back ramp"),
    "tooth.behind": (0.6, "Front ramp's start behind the bay's rear edge"),
    "strap.length": (22, "Strap slots, front to back: for a 20 mm strap"),
    "strap.width": (4, "Strap slots, across"),
    "strap.front": (18, "First row of strap slots from the front"),
    "strap.back": (58, "Second row"),
    "strap.a": (KINDS[DOC][3][0], "Strap slots this far either side of centre"),
    "strap.b": (KINDS[DOC][3][1], "And this far"),
    "strap.c": (KINDS[DOC][3][2], "And this far"),
}
D = {
    "plate.width": "bay.width - side.slack",
    "plate.length": "bay.depth - back.clear",
    "front.height": "bay.height - roof.slack",
    "mid": "(bay.width - side.slack) / 2",
    "tooth.x": "bay.depth + tooth.behind",
    "finger.tip": "bay.depth + tooth.behind + tooth.ramp + tooth.lead + 0.1",
    "air.top": "bay.height - roof.slack - top.bar",
    "air.low": "bay.height - roof.slack - top.bar - air.height",
}
SLOTS = KINDS[DOC][2]


def num(expr, v):
    e = str(expr)
    for n in sorted(v, key=len, reverse=True):
        e = e.replace(n, repr(v[n]))
    return eval(e)


V = {k: float(x) for k, (x, _) in P.items()}
for k, e in D.items():
    V[k] = num(e, V)


def sketch(fid, pts, role, plane=None):
    names = [f"{role}{i}" for i in range(len(pts))]
    cons = [{"c": "fix", "p": "o", "at": [0, 0]}]
    for n, (x, y) in zip(names, pts):
        cons += [{"c": "distance_x", "a": "o", "b": n, "value": x}, {"c": "distance_y", "a": "o", "b": n, "value": y}]
    f = {"id": fid, "version": 1, "type": "sketch", "constraints": cons, "profiles": {role: names},
         "points": {"o": [0, 0], **{n: [num(x, V), num(y, V)] for n, (x, y) in zip(names, pts)}}}
    if plane:
        f["plane"] = plane
    return f


box = lambda x0, y0, x1, y1: [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
TOP = {"origin": [0, 0, "plate.thickness"], "x": [1, 0, 0], "y": [0, 1, 0]}
L, WD = "plate.length", "plate.width"
FINGERS = [("mid - finger.apart - finger.width", "mid - finger.apart"), ("mid + finger.apart", "mid + finger.apart + finger.width")]


def outline():
    t = "nose.taper"
    pts = [(0, 0), (f"{L} - {t}", 0), (L, t)]
    for lo, hi in FINGERS:
        pts += [(L, lo), ("finger.tip", lo), ("finger.tip", hi), (L, hi)]
    return pts + [(L, f"{WD} - {t}"), (f"{L} - {t}", WD), (0, WD)]


def cuts():
    out = [("label", ["-1", "mid - label.width / 2", "label.low"], ["label.depth", "mid + label.width / 2", "label.high"])]
    for k in range(SLOTS):
        lo = f"mid - {(SLOTS - 1) / 2} * slot.pitch - slot.width / 2 + {k} * slot.pitch"
        out.append((f"air{k}", ["-1", lo, "air.low"], ["front.thickness + 1", f"{lo} + slot.width", "air.top"]))
    for k, (lo, hi) in enumerate(FINGERS):
        for side, a, b in (("a", f"{lo} - finger.slot", lo), ("b", hi, f"{hi} + finger.slot")):
            out.append((f"slot{k}{side}", ["finger.root", a, "-1"], [f"{L} + 1", b, "plate.thickness + 1"]))
    for row in ("front", "back"):
        for name in "abc":
            for s, sign in (("l", "-"), ("r", "+")):
                y = f"mid {sign} strap.{name}"
                out.append((f"strap.{row}.{name}{s}", [f"strap.{row}", f"{y} - strap.width / 2", "-1"],
                            [f"strap.{row} + strap.length", f"{y} + strap.width / 2", "plate.thickness + 1"]))
    return out


def features():
    f = [sketch("plate.sketch", outline(), "outline"),
         {"id": "plate", "version": 1, "type": "extrude", "profile": ref("plate.sketch", "outline"), "depth": "plate.thickness"},
         sketch("front.sketch", box(0, 0, "front.thickness", WD), "face", TOP),
         {"id": "front", "version": 1, "type": "boss", "target": ref("plate", "body"),
          "profile": ref("front.sketch", "face"), "height": "front.height - plate.thickness"}]
    last = "front"
    for name, lo, hi in cuts():
        f.append({"id": name, "version": 1, "type": "box_cut", "target": ref(last, "body"), "min": lo, "max": hi})
        last = name
    face = {"origin": [0, 0, 0], "x": [0, 0, 1], "y": [0, 1, 0]}  # normal -X, out of the front
    f.append(sketch("pull.sketch", box("air.top", "pull.inset", "front.height", f"{WD} - pull.inset"), "tab", face))
    f.append({"id": "pull", "version": 1, "type": "boss", "target": ref(last, "body"),
              "profile": ref("pull.sketch", "tab"), "height": "pull.reach"})
    under = {"origin": [0, 0, "air.top"], "x": [1, 0, 0], "y": [0, -1, 0]}  # normal -Z
    f.append(sketch("pull.lip.sketch", box("-pull.reach", f"-({WD} - pull.inset)", "-pull.reach + 1.5", "-pull.inset"), "lip", under))
    f.append({"id": "pull.lip", "version": 1, "type": "boss", "target": ref("pull", "body"),
              "profile": ref("pull.lip.sketch", "lip"), "height": "pull.lip"})
    last = "pull.lip"
    wedge = [("tooth.x", 0.3), ("tooth.x + tooth.ramp + tooth.lead", 0.3), ("tooth.x + tooth.ramp + tooth.lead", 0),
             ("tooth.x + tooth.ramp", "-tooth.depth"), ("tooth.x", 0)]
    for k, (lo, hi) in enumerate(FINGERS):
        side = {"origin": [0, hi, 0], "x": [1, 0, 0], "y": [0, 0, 1]}  # normal -Y
        f.append(sketch(f"tooth{k}.sketch", wedge, "wedge", side))
        f.append({"id": f"tooth{k}", "version": 1, "type": "boss", "target": ref(last, "body"),
                  "profile": ref(f"tooth{k}.sketch", "wedge"), "height": "finger.width"})
        last = f"tooth{k}"
    return f, last


def expected_volume():
    v, t = V, V["plate.thickness"]
    xy = [(num(x, V), num(y, V)) for x, y in outline()]
    area = abs(sum(a * d - c * b for (a, b), (c, d) in zip(xy, xy[1:] + xy[:1]))) / 2
    area -= 4 * v["finger.slot"] * (v["plate.length"] - v["finger.root"]) + 12 * v["strap.length"] * v["strap.width"]
    vol = area * t
    front = v["plate.width"] * (v["front.height"] - t) - SLOTS * v["slot.width"] * v["air.height"]
    vol += front * v["front.thickness"] - v["label.width"] * (v["label.high"] - v["label.low"]) * v["label.depth"]
    vol += (v["plate.width"] - 2 * v["pull.inset"]) * (v["top.bar"] * v["pull.reach"] + 1.5 * v["pull.lip"])
    return vol + 2 * v["finger.width"] * (v["tooth.ramp"] + v["tooth.lead"]) * v["tooth.depth"] / 2


def main():
    made = rw("create", DOC)
    if not made["ok"]:
        sys.exit(json.dumps(made))
    ops = [{"op": "add_parameter", "id": k, "parameter": {"value": x, "unit": "mm", "greater_than": 0, "description": d}}
           for k, (x, d) in P.items()]
    ops += [{"op": "add_parameter", "id": k, "parameter": {"expr": e, "unit": "mm"}} for k, e in D.items()]
    feats, last = features()
    ops += [{"op": "add_feature", "feature": f} for f in feats]
    ops.append({"op": "set_name", "name": "shelf.body", "reference": ref(last, "body")})
    ops.append({"op": "add_output", "output": {"id": "shelf.step", "kind": "step", "source": "shelf.body"}})
    want = expected_volume()
    tx = {"schema_version": 1, "document": DOC, "base_revision": made["result"]["revision"], "operations": ops,
          "checks": [{"kind": "valid_solid", "body": "shelf.body"},
                     {"kind": "volume", "body": "shelf.body", "unit": "mm", "at_least": want * 0.9995, "at_most": want * 1.0005}]}
    open(f"tx-{DOC}.json", "w").write(json.dumps(tx, indent=1))
    dry = rw("dry-run", "--brief", "-", stdin=json.dumps(tx))
    if not dry["ok"]:
        sys.exit(json.dumps(dry["failure"], indent=1)[:4000])
    r = dry["result"]
    loose = [(s["feature"], s["degrees_of_freedom"]) for s in r["sketches"] if s["degrees_of_freedom"]]
    print("checks", [(k["kind"], k["passed"]) for k in r["checks"]], "by hand", round(want, 2),
          "kernel", r["measurements"]["body"].get("kernel_volume"), "loose", loose)
    if not r["checks_passed"]:
        sys.exit(json.dumps(r["checks"], indent=1)[:3000])
    done = rw("commit", "--document", DOC, "--candidate", r["candidate_digest"], "--base", tx["base_revision"], "--key", f"{DOC}-1")
    print("committed", done["result"]["revision"] if done["ok"] else done)


if __name__ == "__main__":
    main()
