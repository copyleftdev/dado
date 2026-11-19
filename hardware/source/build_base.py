#!/usr/bin/env python3
"""Builds the base (second version, after the product panel): a plinth one
column wide and exactly as deep as a cell, that a cell slides onto and that
joins to copies of itself side by side.

It is the cell's own idea again: one cross-section, extruded front to back.
On top is the same rail a cell has, so a cell's lips, skids and latch meet
exactly what they meet on another cell. On its sides are a rail and lips of
the same kind, so joined bases act as one plinth. Its front is closed and
its joints end short of the front, so from the front it is a plain block
under each column."""
import json, math, subprocess, sys
from build_checks import measures, spans

RW = __import__("os").environ.get("RINGWRIGHT", "ringwright")
# "base" stands under a column of cells; "basehalf" under a column of column spacers.
DOC = sys.argv[1] if len(sys.argv) > 1 else "base"
WIDTH = {"base": 67, "basehalf": 31.7}[DOC]


def rw(*args, stdin=None):
    out = subprocess.run([RW, *args], input=stdin, capture_output=True, text=True)
    return json.loads(out.stdout)


def ref(feature, role, expect=1):
    return {"feature": feature, "role": role, "expect": expect}


P = {
    # What it shares with the cell; these must match the cell.
    "body.width": (WIDTH, "As the part it stands under: a cell, or a column spacer half a pitch wide"),
    "gap": (3.6, "Between joined parts: the height of lips"),
    "stem.width": (6, "Rail stem"),
    "head.width": (12, "Rail head"),
    "stem.height": (1.9, "Rail stem"),
    "head.height": (1.2, "Rail head"),
    "flange.height": (1.4, "Lip flange"),
    "web.width": (2, "Lip web"),
    "cell.reach": (1.4, "How far a cell's teeth reach: sets the notches in the top rail"),
    "catch.from_front": (12, "Where a finger's free end is, from the front of its part"),
    "tooth.length": (4, "Tooth along the joint, ramps included"),
    "tooth.ramp": (1.5, "Each ramp"),
    "notch.depth": (0.65, "Notch into a rail's stem"),
    # The base itself.
    "base.height": (22, "Tall enough for the side joint, clear of the rounded corners"),
    "base.depth": (100, "Front to back: as the cell, so their fronts are one plane"),
    "front.wall": (3, "Closes the front of the hollows"),
    "front.relief": (9, "Rails and lips cut back from the front, as on the cell"),
    "wall": (3, "Deck, floor, sides and the web under the rail"),
    "corner.radius": (2, "The four long outer edges"),
    "pad.inset": (3, "Pads in from the sides"),
    "pad.width": (3, "Pads: two ribs underneath that the base stands on"),
    "pad.height": (1, "Pads"),
    "base.float": (0.8, "Play up and down between bases: as made, their heights differ by a few tenths"),
    "finger.length": (12, "Latch finger between bases"),
    "finger.width": (1, "That finger, across the joint"),
}
D = {"u.mid": "body.width / 2", "v.mid": "base.height / 2",
     "rail.top": "stem.height + head.height",
     "open.half": "stem.width / 2 + base.float", "chan.half": "head.width / 2 + base.float",
     "base.reach": "base.float + 0.6",
     "tooth.from": "catch.from_front + 0.3"}


def num(expr, v):
    e = str(expr)
    for n in sorted(v, key=len, reverse=True):
        e = e.replace(n, repr(v[n]))
    return eval(e)


V = {k: float(x) for k, (x, _) in P.items()}
for k, e in D.items():
    V[k] = num(e, V)
ORIGIN = {"c": "fix", "p": "o", "at": [0, 0]}
W, H = "body.width", "base.height"


def at(point, x, y):
    return [{"c": "distance_x", "a": "o", "b": point, "value": x},
            {"c": "distance_y", "a": "o", "b": point, "value": y}]


def polygon(fid, pts, role, plane):
    names = [f"p{i}" for i in range(len(pts))]
    cons = [ORIGIN]
    for n, (x, y) in zip(names, pts):
        cons += at(n, x, y)
    return {"id": fid, "version": 1, "type": "sketch", "plane": plane,
            "points": {"o": [0, 0], **{n: [num(x, V), num(y, V)] for n, (x, y) in zip(names, pts)}},
            "constraints": cons, "profiles": {role: names}}


def shape(fid, pts, role, plane, swap):
    """A polygon given as (across the joint, along it), on a plane whose
    sketch axes are those two, or the other way round."""
    pts = [(y, a) if swap else (a, y) for a, y in pts]
    xy = [(num(x, V), num(y, V)) for x, y in pts]
    turn = sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(xy, xy[1:] + xy[:1]))
    return polygon(fid, pts if turn > 0 else pts[::-1], role, plane)


FRONT = {"origin": [0, 0, 0], "x": [-1, 0, 0], "y": [0, 0, 1]}
BACK = {"origin": [0, "base.depth", 0], "x": [-1, 0, 0], "y": [0, 0, 1]}


def lips(c, along):
    g, f = "gap", "gap - flange.height"
    seq = [(f"{c} - chan.half - web.width", 0), (f"{c} - chan.half - web.width", g),
           (f"{c} - open.half", g), (f"{c} - open.half", f), (f"{c} - chan.half", f),
           (f"{c} - chan.half", 0), (f"{c} + chan.half", 0), (f"{c} + chan.half", f),
           (f"{c} + open.half", f), (f"{c} + open.half", g),
           (f"{c} + chan.half + web.width", g), (f"{c} + chan.half + web.width", 0)]
    return [along(a, f"-({d})") for a, d in seq]


def rail(c, base, along):
    s, t = "stem.height", "rail.top"
    seq = [(f"{c} - stem.width / 2", 0), (f"{c} - stem.width / 2", s),
           (f"{c} - head.width / 2", s), (f"{c} - head.width / 2", t),
           (f"{c} + head.width / 2", t), (f"{c} + head.width / 2", s),
           (f"{c} + stem.width / 2", s), (f"{c} + stem.width / 2", 0)]
    return [along(a, f"{base} + ({d})") for a, d in seq]


def outline():
    """Counter-clockwise from the low left corner: two pads under, a rail on
    the right, the cell's rail on top, lips on the left."""
    pad = lambda lo: [(lo, 0), (lo, "-pad.height"), (f"{lo} + pad.width", "-pad.height"),
                      (f"{lo} + pad.width", 0)]
    pts = [(0, 0)] + pad("pad.inset") + pad(f"{W} - pad.inset - pad.width") + [(W, 0)]
    pts += rail("v.mid", W, lambda a, d: (d, a))
    pts += [(W, H)]
    pts += list(reversed(rail("u.mid", H, lambda a, d: (a, d))))
    pts += [(0, H)]
    pts += list(reversed(lips("v.mid", lambda a, d: (d, a))))
    return pts


def hollows():
    """Two, either side of a web that stands under the rail."""
    lo, hi = "wall", f"{H} - wall"
    return [[("wall", lo), ("u.mid - wall / 2", lo), ("u.mid - wall / 2", hi), ("wall", hi)],
            [("u.mid + wall / 2", lo), (f"{W} - wall", lo), (f"{W} - wall", hi),
             ("u.mid + wall / 2", hi)]]


def area(pts):
    xy = [(num(x, V), num(y, V)) for x, y in pts]
    return abs(sum(a * d - c * b for (a, b), (c, d) in zip(xy, xy[1:] + xy[:1]))) / 2


def inset(reach):
    """As on the cell: a notch ends where the tooth's ramps cross the stem's
    surface, less a little, so the tooth is held by its ramps."""
    return f"tooth.ramp * (base.float + 0.2) / ({reach} + 0.2) - 0.15"


def box(a0, y0, a1, y1):
    return [(a0, y0), (a1, y0), (a1, y1), (a0, y1)]


def notches(name, plane, back, swap, centre, reach, y0, last):
    """Two notches through a rail's head and into its stem, where the teeth
    of what slides onto it come to rest. `y0` is where those teeth start."""
    f = []
    y = (lambda e: f"-({e})") if back else (lambda e: e)
    for k, s in enumerate((1, -1)):
        side = lambda d: f"{centre} + {s} * (stem.width / 2 + ({d}))"
        n0, n1 = f"{y0} + {inset(reach)}", f"{y0} + tooth.length - ({inset(reach)})"
        cut = [(side("-notch.depth"), y(n0)), (side(f"{reach} + 0.4"), y(n0)),
               (side(f"{reach} + 0.4"), y(n1)), (side("-notch.depth"), y(n1))]
        f.append(shape(f"{name}{k}.sketch", cut, "notch", plane, swap))
        f.append({"id": f"{name}{k}", "version": 1, "type": "pocket", "target": ref(last, "body"),
                  "profile": ref(f"{name}{k}.sketch", "notch"), "depth": "rail.top"})
        last = f"{name}{k}"
    return f, last


def fingers(last):
    """Two spring fingers in the side lips, as a cell has, for the next base."""
    f, c = [], "v.mid"
    lip = {"origin": ["gap", 0, 0], "x": [0, 1, 0], "y": [0, 0, 1]}
    flange = {"origin": ["gap - flange.height", 0, 0], "x": [0, 1, 0], "y": [0, 0, 1]}
    tip, root = "catch.from_front", "catch.from_front + finger.length"
    t0, t1 = "tooth.from", "tooth.from + tooth.length"
    for k, s in enumerate((1, -1)):
        edge = lambda d: f"{c} + {s} * (open.half + ({d}))"
        far = f"{c} + {s} * (chan.half)"
        slot = [(edge(-0.2), f"{tip} - 0.8"), (far, f"{tip} - 0.8"), (far, root),
                (edge("finger.width"), root), (edge("finger.width"), tip), (edge(-0.2), tip)]
        f.append(shape(f"finger{k}.slot.sketch", slot, "slot", lip, True))
        f.append({"id": f"finger{k}.slot", "version": 1, "type": "pocket", "target": ref(last, "body"),
                  "profile": ref(f"finger{k}.slot.sketch", "slot"), "depth": "flange.height + 0.2"})
        tooth = [(edge(0.2), t0), (edge(0.2), t1), (edge("-base.reach"), f"{t1} - tooth.ramp"),
                 (edge("-base.reach"), f"{t0} + tooth.ramp")]
        f.append(shape(f"finger{k}.tooth.sketch", tooth, "tooth", flange, True))
        f.append({"id": f"finger{k}.tooth", "version": 1, "type": "boss",
                  "target": ref(f"finger{k}.slot", "body"),
                  "profile": ref(f"finger{k}.tooth.sketch", "tooth"), "height": "flange.height"})
        last = f"finger{k}.tooth"
    return f, last


def features():
    out = outline()
    f = [polygon("section.sketch", out, "outline", FRONT),
         {"id": "section", "version": 1, "type": "extrude",
          "profile": ref("section.sketch", "outline"), "depth": "base.depth"}]
    last = "section"
    for k, pts in enumerate(hollows()):
        f.append(polygon(f"hollow{k}.sketch", pts, "opening", BACK))
        f.append({"id": f"hollow{k}", "version": 1, "type": "pocket", "target": ref(last, "body"),
                  "profile": ref(f"hollow{k}.sketch", "opening"), "depth": "base.depth - front.wall"})
        last = f"hollow{k}"
    top = {"origin": [0, 0, f"{H} + rail.top"], "x": [-1, 0, 0], "y": [0, -1, 0]}
    side = {"origin": [f"-({W} + rail.top)", 0, 0], "x": [0, 0, 1], "y": [0, 1, 0]}
    lip = {"origin": ["gap", 0, 0], "x": [0, 1, 0], "y": [0, 0, 1]}
    # The joints end short of the front, as on the cell.
    half = "(head.width / 2 + 0.5)"
    reach = "(chan.half + web.width + 0.5)"
    cuts = [("relief.top", top, box(f"u.mid - {half}", "-front.relief", f"u.mid + {half}", 1), "rail.top"),
            ("relief.rail", side, box(f"v.mid - {half}", -1, f"v.mid + {half}", "front.relief"), "rail.top"),
            ("relief.lips", lip, box(-1, f"v.mid - {reach}", "front.relief", f"v.mid + {reach}"), "gap")]
    for name, plane, pts, depth in cuts:
        f.append(polygon(f"{name}.sketch", pts, "cut", plane))
        f.append({"id": name, "version": 1, "type": "pocket", "target": ref(last, "body"),
                  "profile": ref(f"{name}.sketch", "cut"), "depth": depth})
        last = name
    more, last = notches("seat", top, True, False, "u.mid", "cell.reach", "tooth.from", last)
    f += more
    more, last = notches("link", side, False, False, "v.mid", "base.reach", "tooth.from", last)
    f += more
    more, last = fingers(last)
    return f + more, last, out


def corners(out):
    pairs = []
    for corner in [(0, 0), (W, 0), (W, H), (0, H)]:
        i = out.index(corner)
        side = lambda k: {"feature": "section", "role": "side", "index": k % len(out)}
        pairs.append([side(i - 1), side(i)])
    return pairs


def expected_volume(rounded):
    v = V
    vol = area(outline()) * v["base.depth"]
    vol -= sum(area(h) for h in hollows()) * (v["base.depth"] - v["front.wall"])
    rail = v["stem.width"] * v["stem.height"] + v["head.width"] * v["head.height"]
    lips = 2 * (v["web.width"] * v["gap"] + (v["chan.half"] - v["open.half"]) * v["flange.height"])
    vol -= (2 * rail + lips) * v["front.relief"]
    for reach in (v["cell.reach"], v["base.reach"]):
        long = v["tooth.length"] - 2 * (v["tooth.ramp"] * (v["base.float"] + 0.2) / (reach + 0.2) - 0.15)
        vol -= 2 * long * ((v["notch.depth"] + reach + 0.4) * v["head.height"]
                           + v["notch.depth"] * v["stem.height"])
    flange, reach = v["chan.half"] - v["open.half"], v["base.reach"]
    slot = (flange - v["finger.width"]) * v["finger.length"] + flange * 0.8
    wide = v["tooth.length"] - 2 * v["tooth.ramp"] * 0.2 / (reach + 0.2)
    tooth = (wide + v["tooth.length"] - 2 * v["tooth.ramp"]) / 2 * reach
    vol += 2 * (tooth - slot) * v["flange.height"]
    if rounded:
        vol -= (4 - math.pi) * v["corner.radius"] ** 2 * v["base.depth"]
    return vol


def run(ops, last, key, rounded):
    head = rw("inspect", DOC)["result"]["revision"]
    ops = ops + [{"op": "set_name", "name": "base.body", "reference": ref(last, "body")}]
    want = expected_volume(rounded)
    tx = {"schema_version": 1, "document": DOC, "base_revision": head, "operations": ops,
          "checks": [{"kind": "valid_solid", "body": "base.body"},
                     {"kind": "volume", "body": "base.body", "unit": "mm",
                      "at_least": want * 0.9995, "at_most": want * 1.0005}] + measures("base.body", (lambda w, h: (w, V["base.depth"], h))(*spans(outline(), num, V)), 1.0)}
    open(f"tx-{DOC}-{key}.json", "w").write(json.dumps(tx, indent=1))
    dry = rw("dry-run", "--brief", "-", stdin=json.dumps(tx))
    if not dry["ok"]:
        sys.exit(f"{key}: {json.dumps(dry['failure'], indent=1)[:3000]}")
    r = dry["result"]
    loose = [(s["feature"], s["degrees_of_freedom"]) for s in r["sketches"] if s["degrees_of_freedom"]]
    print(f"{key}: checks {[(c['kind'], c['passed']) for c in r['checks']]}, by hand {want:.2f},"
          f" kernel {r['measurements']['body'].get('kernel_volume')}, loose {loose},"
          f" notes {r.get('diagnostics')}")
    if not r["checks_passed"]:
        sys.exit(json.dumps(r["checks"], indent=1)[:3000])
    c = rw("commit", "--document", DOC, "--candidate", r["candidate_digest"], "--base", head,
           "--key", f"{DOC}-{key}")
    print("  committed", c["result"]["revision"] if c["ok"] else c)


def main():
    made = rw("create", DOC)
    if not made["ok"]:
        sys.exit(json.dumps(made))
    ops = [{"op": "add_parameter", "id": k, "parameter": {
        "value": x, "unit": "mm", "greater_than": 0, "description": d}} for k, (x, d) in P.items()]
    ops += [{"op": "add_parameter", "id": k, "parameter": {"expr": e, "unit": "mm"}}
            for k, e in D.items()]
    feats, last, out = features()
    ops += [{"op": "add_feature", "feature": f} for f in feats]
    run(ops, last, "shape", False)
    soften = {"id": "soften", "version": 1, "type": "edge_fillet", "target": ref(last, "body"),
              "edges": corners(out), "radius": "corner.radius"}
    run([{"op": "add_feature", "feature": soften},
         {"op": "add_output", "output": {"id": "base.step", "kind": "step", "source": "base.body"}}],
        "soften", "soften", True)


if __name__ == "__main__":
    main()
