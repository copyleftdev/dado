#!/usr/bin/env python3
"""The carrier before its latch was turned on its side (kept for the record; build_carrier.py is current).

Builds the carrier: what a Raspberry Pi 5 is screwed to before it goes into
the cell. A plate that slides on the cell's floor under its two ledges, a
closed face that shuts the cell's mouth and stops on the ends of its ledges,
two spring fingers at the back whose teeth drop behind the cell's rear edge
and then rest straight, and a back wall the board's ports come out through.

The board sits with its ports to the back, so every cable leaves from behind
and the face is a plain door: a pull, a row of air slots, a label flat, and a
low slot for the card. Behind the slots a 25 mm fan, 6 mm thick, drops into
a cradle between the face and the board's card end and draws air in over the
board; a thicker fan would meet a HAT's front edge.

Board dimensions are from Raspberry Pi's mechanical drawing and STEP model;
x runs from the front, y across, z up."""
import json, math, subprocess, sys
from build_checks import measures, spans

RW = __import__("os").environ.get("RINGWRIGHT", "ringwright")
DOC = "carrier"


def rw(*args, stdin=None):
    out = subprocess.run([RW, *args], input=stdin, capture_output=True, text=True)
    return json.loads(out.stdout)


def ref(feature, role, expect=1):
    return {"feature": feature, "role": role, "expect": expect}


P = {
    # The board.
    "board.length": (85, "Raspberry Pi 5, long edge"),
    "board.width": (56, "Raspberry Pi 5, short edge"),
    "board.thickness": (1.35, "From Raspberry Pi's STEP model"),
    "hole.spacing_x": (58, "Mounting holes, along the board"),
    "hole.spacing_y": (49, "Mounting holes, across the board"),
    "hole.inset": (3.5, "Mounting holes from the board's edges, at the card-slot end"),
    "port.overhang": (3.05, "USB and Ethernet beyond the board's port edge, from Raspberry Pi's STEP model"),
    "port.height": (16.2, "Tallest port above the board, from Raspberry Pi's STEP model"),
    # The cell it goes into.
    "cell.depth": (100, "Cell, front to back"),
    "back.clear": (3, "The plate ends this far short of the cell's back"),
    "cell.width": (61, "Inside the cell, across"),
    "cell.height": (36, "Inside the cell, floor to roof"),
    "ledge.under": (2.3, "Underside of the cell's ledges above its floor"),
    "ledge.reach": (1.2, "How far the ledges stand out from the cell's walls"),
    # The carrier.
    "plate.thickness": (1.8, "Leaves 0.5 under the cell's ledges"),
    "side.slack": (0.5, "Carrier narrower than the cell, in all"),
    "roof.slack": (0.5, "Front lower than the cell's roof"),
    "post.diameter": (6, "Posts the board rests on"),
    "post.height": (3, "Room under the board"),
    "screw.hole": (2.7, "Clearance for an M2.5 screw"),
    "front.thickness": (2.6, "The face; it stops on the ends of the cell's ledges and sits flush with the cell"),
    "air.height": (7, "The row of slots across the back wall for air out"),
    "intake.height": (18, "The slots across the face, tall enough to cover the fan behind them"),
    "slot.width": (8, "Each slot"),
    "slot.pitch": (10.5, "Slot to slot: five of them"),
    "top.bar": (3, "The face's top edge, which the pull grows out of"),
    "label.width": (44, "A flat for a label, in the middle of the face"),
    "label.low": (7, "The flat's lower edge above the carrier's underside"),
    "label.high": (13, "The flat's upper edge"),
    "label.depth": (0.4, "Sunk, so a label's edges are protected"),
    "pull.reach": (6, "The pull: a rail along the face's top edge"),
    "pull.inset": (2, "The rail's ends in from the face's sides"),
    "pull.lip": (1.5, "A lip under its edge, for fingertips to catch"),
    "nose.taper": (2, "Cut from each back corner"),
    # The latch.
    "finger.root": (86, "Where the fingers leave the plate, from the front: 14 to the cell's rear edge"),
    "finger.width": (8, "Each finger, across; short and wide, for about 20 N of hold"),
    "finger.apart": (11, "Each finger's near edge from the centre line: clear of the stop"),
    "finger.slot": (1, "Cut either side of a finger to free it"),
    "tooth.depth": (1.2, "Tooth below the finger"),
    "tooth.ramp": (0.93, "Its front ramp, front to back: steep, about 52 degrees, for about 20 N to pull out"),
    "tooth.lead": (2.75, "Its back ramp, which rides in over the floor"),
    # The back wall: the ports come out through it, with a row of slots above them for air out.
    "back.thickness": (2.6, "Back wall; the ports end flush with its rear face"),
    "card.width": (14.5, "Slot low in the face for the card to come out through"),
    "card.low": (2.6, "That slot, bottom"),
    "card.high": (5.2, "That slot, top"),
    # The fan's cradle, behind the face.
    "fan.size": (25, "A 25 mm fan, square"),
    "fan.thick": (6, "Its thickness: 6, because a 10 mm fan would reach over the board and under a HAT"),
    "fan.slack": (0.3, "Cradle wider than the fan, in all"),
    "fan.low": (9.5, "Fan's underside above the carrier's underside: clear of the card and the board's end connector"),
    "cheek.thick": (2.5, "The two uprights the fan drops between"),
    "lip.reach": (1.6, "A lip on each upright that keeps the fan against the face"),
    "lip.low": (10.5, "The lips' underside: above the board's end connector"),
    "lip.height": (5.5, "The lips' height: they stop below a HAT"),
    "barb.reach": (0.6, "A barb at the top of each upright that the fan snaps under"),
    "barb.height": (0.9, "The barb, top to underside: all the room there is under the cell's roof"),
    "barb.nose": (0.4, "Its blunt nose, so it has no feather edge; above the nose a ramp the fan pushes past"),
    "shelf.reach": (2.4, "A shelf on the face that the fan stands on"),
    "shelf.thick": (1.5, "Its thickness"),
    "tooth.behind": (0.6, "Front ramp's start behind the cell's rear edge: the finger rests straight, so it cannot creep"),
}
D = {
    "plate.width": "cell.width - side.slack",
    "plate.length": "cell.depth - back.clear",
    "front.height": "cell.height - roof.slack",
    "margin": "(plate.width - board.width) / 2",
    "board.front": "plate.length - port.overhang - board.length",
    "board.top": "plate.thickness + post.height + board.thickness",
    "post.x": "board.front + hole.inset",
    "post.y": "margin + hole.inset",
    "mid": "plate.width / 2",
    "back.x": "plate.length - back.thickness",
    "tooth.x": "cell.depth + tooth.behind",
    "finger.tip": "cell.depth + tooth.behind + tooth.ramp + tooth.lead + 0.1",
    "air.top": "front.height - top.bar",
    "air.low": "front.height - top.bar - air.height",
    "band.high": "plate.thickness + post.height - 0.2",
    "intake.low": "front.height - top.bar - intake.height",
    "fan.half": "(fan.size + fan.slack) / 2",
    "cheek.back": "front.thickness + fan.thick + 0.15",
    "lip.back": "front.thickness + fan.thick + 0.15 + lip.reach",
    "fan.top": "fan.low + fan.size",
    "barb.low": "fan.low + fan.size + 0.1",
    "cheek.top": "fan.low + fan.size + 0.1 + barb.height",
}


def num(expr, v):
    e = str(expr)
    for n in sorted(v, key=len, reverse=True):
        e = e.replace(n, repr(v[n]))
    return eval(e)


V = {k: float(x) for k, (x, _) in P.items()}
for k, e in D.items():
    V[k] = num(e, V)
ORIGIN = {"c": "fix", "p": "o", "at": [0, 0]}


def at(point, x, y):
    return [{"c": "distance_x", "a": "o", "b": point, "value": x},
            {"c": "distance_y", "a": "o", "b": point, "value": y}]


def sketch(fid, groups, plane=None, point_sets=None, arcs=None):
    """A sketch of closed outlines, every corner placed from the origin.
    `groups` is {role: [(x, y), ...]}."""
    points, cons, profiles = {"o": [0, 0]}, [ORIGIN], {}
    for role, pts in groups.items():
        names = [f"{role}{i}" for i in range(len(pts))]
        for n, (x, y) in zip(names, pts):
            points[n] = [num(x, V), num(y, V)]
            cons += at(n, x, y)
        profiles[role] = names
    f = {"id": fid, "version": 1, "type": "sketch", "points": points, "constraints": cons,
         "profiles": {} if point_sets else profiles}
    if point_sets:
        f["point_sets"] = {role: profiles[role] for role in point_sets}
    if plane:
        f["plane"] = plane
    if arcs:
        f["arcs"] = arcs
    return f


def box(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def circle(fid, cx, cy, r, plane):
    f = sketch(fid, {"c": [(f"{cx} + {r}", cy), (f"{cx} - ({r})", cy)], "m": [(cx, cy)]}, plane)
    f["profiles"] = {"round": ["c0", "c1"]}
    f["arcs"] = [{"from": "c0", "to": "c1", "center": "m0"}, {"from": "c1", "to": "c0", "center": "m0"}]
    return f


TOP = {"origin": [0, 0, "plate.thickness"], "x": [1, 0, 0], "y": [0, 1, 0]}
POSTS = {"origin": [0, 0, "plate.thickness + post.height"], "x": [1, 0, 0], "y": [0, 1, 0]}
L, WD = "plate.length", "plate.width"


def finger_edges():
    """Low and high edge of each finger, across."""
    return [("mid - finger.apart - finger.width", "mid - finger.apart"),
            ("mid + finger.apart", "mid + finger.apart + finger.width")]


def outline():
    """Counter-clockwise from the front low corner; the two fingers reach
    past the back edge."""
    t = "nose.taper"
    pts = [(0, 0), (f"{L} - {t}", 0), (L, t)]
    for lo, hi in finger_edges():
        pts += [(L, lo), ("finger.tip", lo), ("finger.tip", hi), (L, hi)]
    return pts + [(L, f"{WD} - {t}"), (f"{L} - {t}", WD), (0, WD)]


def lightening():
    return box("post.x + 8", "post.y + 8", "post.x + hole.spacing_x - 8",
               "post.y + hole.spacing_y - 8")


def cuts():
    """Each box cut as (name, min, max)."""
    window = ["margin + 1", "margin + board.width - 1"]
    out = [("ports", ["back.x - 1", window[0], "band.high"],
            [f"{L} + 1", window[1], "board.top + port.height + 0.6"]),
           ("label", ["-1", "mid - label.width / 2", "label.low"],
            ["label.depth", "mid + label.width / 2", "label.high"]),
           ("card", ["-1", "mid - card.width / 2", "card.low"],
            ["front.thickness + 1", "mid + card.width / 2", "card.high"])]
    for k in range(5):
        lo = f"mid - 2 * slot.pitch - slot.width / 2 + {k} * slot.pitch"
        out.append((f"air{k}", ["-1", lo, "intake.low"], ["front.thickness + 1", f"{lo} + slot.width", "air.top"]))
        out.append((f"vent{k}", ["back.x - 1", lo, "air.low"], [f"{L} + 1", f"{lo} + slot.width", "air.top"]))
    for k, (lo, hi) in enumerate(finger_edges()):
        # The slots stop at the plate's top: above them is the back wall.
        for side, a, b in (("a", f"{lo} - finger.slot", lo), ("b", hi, f"{hi} + finger.slot")):
            out.append((f"slot{k}{side}", ["finger.root", a, "-1"], [f"{L} + 1", b, "plate.thickness"]))
        # The back wall opens over the finger and its slots, up into the
        # ports' window, so no thin bridge is left between the two.
        out.append((f"arch{k}", ["back.x - 1", f"{lo} - finger.slot - 0.25", "plate.thickness"],
                    [f"{L} + 1", f"{hi} + finger.slot + 0.25", "band.high + 0.1"]))
    # The ledges pass through the back wall as they do the front.
    for name, lo, hi in (("back.ledge.low", "-1", "ledge.reach + 0.2"),
                         ("back.ledge.high", f"{WD} - ledge.reach - 0.2", f"{WD} + 1")):
        out.append((name, ["back.x - 1", lo, "plate.thickness"],
                    [f"{L} + 1", hi, "ledge.under + ledge.reach + 0.2"]))
    return out


def features():
    f = [sketch("plate.sketch", {"outline": outline(), "window": lightening()}),
         {"id": "plate", "version": 1, "type": "extrude",
          "profile": ref("plate.sketch", "outline"), "depth": "plate.thickness"},
         sketch("front.sketch", {"face": box(0, 0, "front.thickness", WD)}, TOP),
         {"id": "front", "version": 1, "type": "boss", "target": ref("plate", "body"),
          "profile": ref("front.sketch", "face"), "height": "front.height - plate.thickness"}]
    last = "front"
    for row, y in (("low", "post.y"), ("high", "post.y + hole.spacing_y")):
        f.append(circle(f"post.{row}.sketch", "post.x", y, "post.diameter / 2", TOP))
        f.append({"id": f"post.{row}", "version": 1, "type": "boss", "target": ref(last, "body"),
                  "profile": ref(f"post.{row}.sketch", "round"), "height": "post.height"})
        f.append({"id": f"post.{row}.pair", "version": 1, "type": "pattern",
                  "target": ref(f"post.{row}", "body"), "of": ref(f"post.{row}", "body"),
                  "layout": {"kind": "linear", "dx": "hole.spacing_x", "dy": 0, "count": 2}})
        last = f"post.{row}.pair"
    holes = box("post.x", "post.y", "post.x + hole.spacing_x", "post.y + hole.spacing_y")
    f.append(sketch("screws.sketch", {"screws": holes}, POSTS, point_sets=["screws"]))
    f.append({"id": "screws", "version": 1, "type": "hole_pattern", "target": ref(last, "body"),
              "centers": ref("screws.sketch", "screws", 4), "diameter": "screw.hole",
              "depth": "plate.thickness + post.height + 1"})
    f.append({"id": "window", "version": 1, "type": "cut", "target": ref("screws", "body"),
              "profile": ref("plate.sketch", "window"), "z_min": -1, "z_max": "plate.thickness + 1"})
    last = "window"
    f.append(sketch("back.sketch", {"face": box("back.x", 0, L, WD)}, TOP))
    f.append({"id": "back", "version": 1, "type": "boss", "target": ref(last, "body"),
              "profile": ref("back.sketch", "face"), "height": "front.height - plate.thickness"})
    last = "back"
    for name, lo, hi in cuts():
        f.append({"id": name, "version": 1, "type": "box_cut", "target": ref(last, "body"),
                  "min": lo, "max": hi})
        last = name
    # The fan's cradle, added after the cuts so the slots do not bite into it:
    # two uprights from the plate, a lip on each, and a shelf on the face.
    for k, (a, b, c) in enumerate((("mid - fan.half - cheek.thick", "mid - fan.half", "mid - fan.half + lip.reach"),
                                   ("mid + fan.half + cheek.thick", "mid + fan.half", "mid + fan.half - lip.reach"))):
        f.append(sketch(f"cheek{k}.sketch", {"wall": box("front.thickness", a, "cheek.back", b)}, TOP))
        f.append({"id": f"cheek{k}", "version": 1, "type": "boss", "target": ref(last, "body"),
                  "profile": ref(f"cheek{k}.sketch", "wall"), "height": "cheek.top - plate.thickness"})
        hook = [("cheek.back - 0.75", a), ("lip.back", a), ("lip.back", c), ("cheek.back", c),
                ("cheek.back", b), ("cheek.back - 0.75", b)]
        level = {"origin": [0, 0, "lip.low"], "x": [1, 0, 0], "y": [0, 1, 0]}
        f.append(sketch(f"lip{k}.sketch", {"hook": hook}, level))
        f.append({"id": f"lip{k}", "version": 1, "type": "boss", "target": ref(f"cheek{k}", "body"),
                  "profile": ref(f"lip{k}.sketch", "hook"), "height": "lip.height"})
        # The barb, drawn from the front and as deep as the upright: flat
        # underneath, ramped on top, rooted 0.3 inside the upright.
        sign = "+" if k == 0 else "-"
        wedge = [(f"{b} {'-' if k == 0 else '+'} 0.3", "barb.low"), (f"{b} {sign} barb.reach", "barb.low"),
                 (f"{b} {sign} barb.reach", "barb.low + barb.nose"),
                 (b, "cheek.top"), (f"{b} {'-' if k == 0 else '+'} 0.3", "cheek.top")]
        if k:
            wedge.reverse()
        across = {"origin": ["front.thickness", 0, 0], "x": [0, 1, 0], "y": [0, 0, 1]}  # normal +X
        f.append(sketch(f"barb{k}.sketch", {"wedge": wedge}, across))
        f.append({"id": f"barb{k}", "version": 1, "type": "boss", "target": ref(f"lip{k}", "body"),
                  "profile": ref(f"barb{k}.sketch", "wedge"), "height": "cheek.back - front.thickness"})
        last = f"barb{k}"
    under_fan = {"origin": [0, 0, "fan.low - shelf.thick"], "x": [1, 0, 0], "y": [0, 1, 0]}
    f.append(sketch("shelf.sketch", {"shelf": box("front.thickness - 0.2", "mid - fan.half - 0.2",
                                                    "front.thickness + shelf.reach", "mid + fan.half + 0.2")}, under_fan))
    f.append({"id": "shelf", "version": 1, "type": "boss", "target": ref(last, "body"),
              "profile": ref("shelf.sketch", "shelf"), "height": "shelf.thick"})
    last = "shelf"
    # The pull: a rail along the face's top edge, with a lip under it.
    face = {"origin": [0, 0, 0], "x": [0, 0, 1], "y": [0, 1, 0]}  # normal -X, out of the front
    f.append(sketch("pull.sketch", {"tab": box("air.top", "pull.inset", "front.height",
                                                f"{WD} - pull.inset")}, face))
    f.append({"id": "pull", "version": 1, "type": "boss", "target": ref(last, "body"),
              "profile": ref("pull.sketch", "tab"), "height": "pull.reach"})
    under = {"origin": [0, 0, "air.top"], "x": [1, 0, 0], "y": [0, -1, 0]}  # normal -Z
    f.append(sketch("pull.lip.sketch", {"lip": box("-pull.reach", f"-({WD} - pull.inset)",
                                                    "-pull.reach + 1.5", "-pull.inset")}, under))
    f.append({"id": "pull.lip", "version": 1, "type": "boss", "target": ref("pull", "body"),
              "profile": ref("pull.lip.sketch", "lip"), "height": "pull.lip"})
    last = "pull.lip"
    # The teeth: a wedge under each finger, drawn from the side and as wide
    # as the finger. It starts a little inside the finger so the two are one.
    wedge = [("tooth.x", 0.3), ("tooth.x + tooth.ramp + tooth.lead", 0.3),
             ("tooth.x + tooth.ramp + tooth.lead", 0), ("tooth.x + tooth.ramp", "-tooth.depth"),
             ("tooth.x", 0)]
    for k, (lo, hi) in enumerate(finger_edges()):
        side = {"origin": [0, hi, 0], "x": [1, 0, 0], "y": [0, 0, 1]}  # normal -Y
        f.append(sketch(f"tooth{k}.sketch", {"wedge": wedge}, side))
        f.append({"id": f"tooth{k}", "version": 1, "type": "boss", "target": ref(last, "body"),
                  "profile": ref(f"tooth{k}.sketch", "wedge"), "height": "finger.width"})
        last = f"tooth{k}"
    return f, last


def poly_area(pts):
    xy = [(num(x, V), num(y, V)) for x, y in pts]
    return abs(sum(a * d - c * b for (a, b), (c, d) in zip(xy, xy[1:] + xy[:1]))) / 2


def expected_volume():
    v, n = V, lambda e: num(e, V)
    t = v["plate.thickness"]
    area = poly_area(outline()) - poly_area(lightening())
    area -= 4 * v["finger.slot"] * (v["plate.length"] - v["finger.root"])
    vol = area * t
    front = v["plate.width"] * (v["front.height"] - t)
    front -= 5 * v["slot.width"] * v["intake.height"] + v["card.width"] * (v["card.high"] - v["card.low"])
    # The cradle: two uprights, the part of each lip that stands beyond its upright, and the shelf.
    deep = v["cheek.back"] - v["front.thickness"]
    vol += 2 * v["cheek.thick"] * deep * (v["cheek.top"] - t)
    vol += 2 * deep * v["barb.reach"] * (v["barb.nose"] + v["barb.height"]) / 2
    vol += 2 * v["lip.reach"] * (v["cheek.thick"] + v["lip.reach"]) * v["lip.height"]
    vol += v["shelf.reach"] * (v["fan.size"] + v["fan.slack"]) * v["shelf.thick"]
    vol -= v["label.width"] * (v["label.high"] - v["label.low"]) * v["label.depth"]
    vol += (v["plate.width"] - 2 * v["pull.inset"]) * (v["top.bar"] * v["pull.reach"] + 1.5 * v["pull.lip"])
    vol += front * v["front.thickness"]
    post, hole = math.pi * (v["post.diameter"] / 2) ** 2, math.pi * (v["screw.hole"] / 2) ** 2
    vol += 4 * post * v["post.height"] - 4 * hole * (t + v["post.height"])
    vol += 2 * v["finger.width"] * (v["tooth.ramp"] + v["tooth.lead"]) * v["tooth.depth"] / 2
    # The back wall, less the openings over the fingers, its ledge notches,
    # the ports' window and the slots above it.
    back = v["plate.width"] * (v["front.height"] - t)
    back -= 2 * (v["finger.width"] + 2 * v["finger.slot"] + 0.5) * (v["band.high"] - t)
    back -= 2 * (v["ledge.reach"] + 0.2) * (v["ledge.under"] + v["ledge.reach"] + 0.2 - t)
    back -= (v["board.width"] - 2) * (v["port.height"] + v["board.thickness"] + 0.8)
    back -= 5 * v["slot.width"] * v["air.height"]
    return vol + back * v["back.thickness"]


def main():
    made = rw("create", DOC)
    if not made["ok"]:
        sys.exit(json.dumps(made))
    ops = [{"op": "add_parameter", "id": k, "parameter": {
        "value": x, "unit": "mm", "greater_than": 0, "description": d}} for k, (x, d) in P.items()]
    ops += [{"op": "add_parameter", "id": k, "parameter": {"expr": e, "unit": "mm"}}
            for k, e in D.items()]
    feats, last = features()
    ops += [{"op": "add_feature", "feature": f} for f in feats]
    ops.append({"op": "set_name", "name": "carrier.body", "reference": ref(last, "body")})
    ops.append({"op": "add_output", "output": {"id": "carrier.step", "kind": "step",
                                               "source": "carrier.body"}})
    want = expected_volume()
    tx = {"schema_version": 1, "document": DOC, "base_revision": made["result"]["revision"],
          "operations": ops,
          "checks": [{"kind": "valid_solid", "body": "carrier.body"},
                     {"kind": "volume", "body": "carrier.body", "unit": "mm",
                      "at_least": want * 0.9995, "at_most": want * 1.0005}] + measures("carrier.body", (lambda l, w: (l + V["pull.reach"], w, V["front.height"] + V["tooth.depth"]))(*spans(outline(), num, V)), 1.5)}
    open("tx-carrier.json", "w").write(json.dumps(tx, indent=1))
    dry = rw("dry-run", "--brief", "-", stdin=json.dumps(tx))
    if not dry["ok"]:
        sys.exit(json.dumps(dry["failure"], indent=1)[:4000])
    r = dry["result"]
    loose = [(s["feature"], s["degrees_of_freedom"]) for s in r["sketches"] if s["degrees_of_freedom"]]
    print("checks", [(c["kind"], c["passed"]) for c in r["checks"]], "by hand", round(want, 2),
          "kernel", r["measurements"]["body"].get("kernel_volume"), "loose", loose,
          "notes", r.get("diagnostics"))
    if not r["checks_passed"]:
        sys.exit(json.dumps(r["checks"], indent=1)[:3000])
    c = rw("commit", "--document", DOC, "--candidate", r["candidate_digest"],
           "--base", tx["base_revision"], "--key", "carrier-1")
    print("committed", c["result"]["revision"] if c["ok"] else c)


main()
