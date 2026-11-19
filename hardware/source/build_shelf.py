#!/usr/bin/env python3
"""Builds the shelf: what goes into a bay. A plate that slides on the bay's
floor under its ledges, a closed face like a carrier's (a pull, a row of air
slots, a label flat), the carrier's two latch fingers, and no back wall.

The latch lies in the plane of the plate, as the carrier's does, so the
shelf prints lying flat: each finger bends sideways and carries a head that
reaches out past the plate's edge to a tooth, which drops behind the rear
end of the bay's side wall.

Switches and hubs have no standard size, so nothing on the shelf is fitted
to one: the plate has rows of slots for two straps, at three widths, and the
device sits with its ports at the open back, where the cables are.

x runs from the front, y across, z up."""
import json, sys, subprocess
from build_checks import measures, spans

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
    "pull.lip.reach": (1.5, "The lip, front to back"),
    "nose.taper": (2, "Cut from each back corner"),
    "finger.root": (82, "Where the fingers leave the plate, from the front"),
    "finger.width": (2.2, "Each finger, across: this is what bends, in the plane of the plate"),
    "finger.inset": (3.25, "The strip of plate left between a finger's outer slot and the plate's edge, as on a carrier"),
    "finger.slot": (1, "Cut between a finger and that strip"),
    "finger.room": (1.6, "Cut on a finger's inner side: room for it to be pressed in by a tooth's depth and more"),
    "latch.clear": (3, "A finger's head starts this far short of the bay's back, and a gap"),
    "head.gap": (0.4, "Between the plate and a finger's head"),
    "rib.height": (1.8, "A rib along each finger and its head, above the plate, to stiffen it sideways"),
    "rib.root": (3, "How far the rib runs onto the plate ahead of the finger's root"),
    "tooth.depth": (1.2, "Tooth beyond the plate's edge"),
    "tooth.ramp": (0.2, "Its front face, front to back: nearly square, as on a carrier"),
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
    "latch.back": "bay.depth - latch.clear",
    "finger.low": "finger.inset + finger.slot",
    "finger.high": "finger.inset + finger.slot + finger.width",
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
B = "latch.back"  # where the heads begin, less their gap: the plate's back edge on a shelf


def mirrored(y):
    return f"{WD} - ({y})"


def across(k, a, b):
    """Two distances from the plate's edge, on side k, in order."""
    side = (lambda y: y) if k == 0 else mirrored
    return sorted([side(a), side(b)], key=lambda e: num(e, V))


def outline():
    """Counter-clockwise from the front low corner. Behind the back edge each
    finger carries a head that reaches out to the plate's edge."""
    t, back = "nose.taper", f"{L} + head.gap"
    lo, hi = "finger.low", "finger.high"
    far = [(L, t), (L, lo), (back, lo), (back, 0), ("finger.tip", 0), ("finger.tip", hi), (L, hi)]
    pts = [(0, 0), (f"{L} - {t}", 0)] + far + [(x, mirrored(y)) for x, y in reversed(far)]
    return pts + [(f"{L} - {t}", WD), (0, WD)]


def latch_cut_area():
    """Plate taken by the slots beside the two fingers."""
    return 2 * (V["finger.slot"] + V["finger.room"]) * (V["latch.back"] - V["finger.root"])


def latch_volume():
    """The two ribs and the two teeth."""
    rib = (V["finger.tip"] - V["finger.root"] + V["rib.root"]) * V["finger.width"] * V["rib.height"]
    tooth = V["plate.thickness"] * (V["tooth.ramp"] + V["tooth.lead"]) * V["tooth.depth"] / 2
    return 2 * (rib + tooth)


def slot_low(k):
    """The low edge of face slot k, across."""
    return f"mid - {(SLOTS - 1) / 2} * slot.pitch - slot.width / 2 + {k} * slot.pitch"


def gussets():
    """Where the pull is held up from the face, as (low, high) across: at the rail's two ends and on
    every other bar between slots. Between them the rail and its lip are bridges no longer than two
    slots and a bar, and that is where fingers go."""
    out = [("pull.inset", slot_low(0))]
    out += [(f"{slot_low(k)} + slot.width", slot_low(k + 1)) for k in range(1, SLOTS - 1, 2)]
    return out + [(f"{slot_low(SLOTS - 1)} + slot.width", f"{WD} - pull.inset")]


def gusset_section():
    """A gusset seen from the side, as (front to back, up): under the rail and behind its lip, sloping
    back to the face at 45 degrees so it prints without support."""
    low = "air.top - pull.lip"
    return [("-pull.reach", "air.top + 0.3"), (0.3, "air.top + 0.3"),
            (0.3, f"{low} - pull.reach - 0.3"), ("-pull.reach", low)]


def pull_volume():
    """The rail, its lip, and the gussets under them."""
    r, lip = V["pull.reach"], V["pull.lip"]
    rail = (V["plate.width"] - 2 * V["pull.inset"]) * (V["top.bar"] * r + V["pull.lip.reach"] * lip)
    section = r * (lip + lip + r) / 2 - V["pull.lip.reach"] * lip
    return rail + section * sum(num(b, V) - num(a, V) for a, b in gussets())


def cuts():
    out = [("label", ["-1", "mid - label.width / 2", "label.low"], ["label.depth", "mid + label.width / 2", "label.high"])]
    for k in range(SLOTS):
        lo = slot_low(k)
        out.append((f"air{k}", ["-1", lo, "air.low"], ["front.thickness + 1", f"{lo} + slot.width", "air.top"]))
    for k in range(2):
        # The outer slot ends in the gap before the head; the inner one runs out the back.
        a, b = across(k, "finger.low - finger.slot", "finger.low")
        out.append((f"slot{k}a", ["finger.root", a, "-1"], [f"{B} + head.gap / 2", b, "plate.thickness + 1"]))
        a, b = across(k, "finger.high", "finger.high + finger.room")
        out.append((f"slot{k}b", ["finger.root", a, "-1"], [f"{B} + 1", b, "plate.thickness + 1"]))
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
    f.append(sketch("pull.lip.sketch", box("-pull.reach", f"-({WD} - pull.inset)", "-pull.reach + pull.lip.reach", "-pull.inset"), "lip", under))
    f.append({"id": "pull.lip", "version": 1, "type": "boss", "target": ref("pull", "body"),
              "profile": ref("pull.lip.sketch", "lip"), "height": "pull.lip"})
    last = "pull.lip"
    # The gussets that hold the pull up, each drawn from the side and as wide as its bar.
    for k, (lo, hi) in enumerate(gussets()):
        side = {"origin": [0, hi, 0], "x": [1, 0, 0], "y": [0, 0, 1]}  # normal -Y
        f.append(sketch(f"gusset{k}.sketch", gusset_section(), "web", side))
        f.append({"id": f"gusset{k}", "version": 1, "type": "boss", "target": ref(last, "body"),
                  "profile": ref(f"gusset{k}.sketch", "web"), "height": f"({hi}) - ({lo})"})
        last = f"gusset{k}"
    # A rib along each finger, from the plate ahead of its root to the end of its head.
    for k in range(2):
        a, b = across(k, "finger.low", "finger.high")
        f.append(sketch(f"rib{k}.sketch", box("finger.root - rib.root", a, "finger.tip", b), "rib", TOP))
        f.append({"id": f"rib{k}", "version": 1, "type": "boss", "target": ref(last, "body"),
                  "profile": ref(f"rib{k}.sketch", "rib"), "height": "rib.height"})
        last = f"rib{k}"
    # The teeth: a wedge on each head, drawn from above and as thick as the plate, pointing out
    # past the plate's edge. It starts a little inside the head so the two are one.
    wedge = [("tooth.x", 0.3), ("tooth.x", 0), ("tooth.x + tooth.ramp", "-tooth.depth"),
             ("tooth.x + tooth.ramp + tooth.lead", 0), ("tooth.x + tooth.ramp + tooth.lead", 0.3)]
    for k in range(2):
        pts = wedge if k == 0 else [(x, mirrored(y)) for x, y in reversed(wedge)]
        f.append(sketch(f"tooth{k}.sketch", pts, "wedge"))
        f.append({"id": f"tooth{k}", "version": 1, "type": "boss", "target": ref(last, "body"),
                  "profile": ref(f"tooth{k}.sketch", "wedge"), "height": "plate.thickness"})
        last = f"tooth{k}"
    return f, last


def expected_volume():
    v, t = V, V["plate.thickness"]
    xy = [(num(x, V), num(y, V)) for x, y in outline()]
    area = abs(sum(a * d - c * b for (a, b), (c, d) in zip(xy, xy[1:] + xy[:1]))) / 2
    area -= latch_cut_area() + 12 * v["strap.length"] * v["strap.width"]
    vol = area * t
    front = v["plate.width"] * (v["front.height"] - t) - SLOTS * v["slot.width"] * v["air.height"]
    vol += front * v["front.thickness"] - v["label.width"] * (v["label.high"] - v["label.low"]) * v["label.depth"]
    return vol + pull_volume() + latch_volume()


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
                     {"kind": "volume", "body": "shelf.body", "unit": "mm", "at_least": want * 0.9995, "at_most": want * 1.0005}] + measures("shelf.body", (lambda l, w: (l + V["pull.reach"], w + 2 * V["tooth.depth"], V["front.height"]))(*spans(outline(), num, V)), 1.5)}
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
