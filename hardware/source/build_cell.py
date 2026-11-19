#!/usr/bin/env python3
"""Builds the cell (fourth version, after the product panel): a sleeve for one Raspberry Pi 5 that joins to copies of
itself on four faces by sliding along the port axis.

Everything that joins is one constant cross-section, drawn once on the front
plane and extruded front to back: a T rail on the top and on one side, and a
pair of lips on the bottom and on the other side that the neighbour's rail
slides between. Rails and lips stand `gap` proud, so joined cells sit `gap`
apart and the lattice pitch is the body plus the gap.
"""
import json, math, subprocess, sys
from build_checks import measures, spans

RW = __import__("os").environ.get("RINGWRIGHT", "ringwright")
DOC = "cell"


def rw(*args, stdin=None):
    out = subprocess.run([RW, *args], input=stdin, capture_output=True, text=True)
    return json.loads(out.stdout)


def ref(feature, role, expect=1):
    return {"feature": feature, "role": role, "expect": expect}


P = {
    "body.width": (67, "Sleeve across; the pitch across is this plus the gap"),
    "body.height": (42, "Sleeve up; the pitch up is this plus the gap"),
    "body.depth": (100, "Front to back: 3 port overhang, 85 board, 12 behind"),
    "wall": (3, "Where printed flame-retardant materials reach V-0"),
    "gap": (3.6, "Between joined cells: the height of the lips and skids"),
    "corner.radius": (2, "The four long outer edges"),
    # The joint. A rail is a stem with a wider head; lips are a web with a
    # flange that reaches under the head.
    "stem.width": (6, "Rail stem"),
    "head.width": (12, "Rail head"),
    "stem.height": (1.9, "Rail stem: a lip's flange plus 0.5 to lift in"),
    "head.height": (1.2, "Rail head"),
    "flange.height": (1.4, "Lip flange, the part that holds"),
    "web.width": (2, "Lip web"),
    "float": (0.8, "Play across the stacking joint: it holds up and down only"),
    # The side joint has more play, up and down: columns settle under their
    # own weight, so height errors add up and neighbours drift out of line.
    "side.float": (1.6, "Play up and down in the side joint"),
    "side.head": (15.2, "Side rail head: still holds 1.4 at either end of that play"),
    # The tray's seat.
    "ledge.size": (1.2, "Ribs that hold the tray's edges down"),
    "ledge.height": (2.3, "Underside of the ribs above the floor: tray plus clearance"),
    "ledge.cut": (2.6, "Ledges cut back at the front: the carrier's face stops against their ends"),
    "front.relief": (9, "Rails, lips and skids cut back from the front, so the gaps between cells read as clean lines"),
    "skid.inset": (3, "Skids in from the body's sides: the rounded corner needs the first 2"),
    "skid.width": (3, "Skids: plain ribs the cell stands on, as tall as the lips"),
    # The latch: in each lip a finger is cut free of the flange, along the
    # joint, and springs across it. A ramped tooth on the finger rides along
    # the neighbour's stem and drops into a notch when the cell is home.
    "catch.from_front": (12, "The finger's free end: behind the relief"),
    "finger.length": (12, "Free end to root: long enough to bend the whole 1.4 at the end of the play"),
    "finger.width": (1, "The finger, across the joint: the direction it bends"),
    "tooth.reach": (1.4, "Tooth beyond the lip's edge: 0.6 past the stem when centred"),
    "side.finger.length": (16, "Side joint: a longer finger, for it bends further"),
    "side.finger.width": (1.4, "Side joint: and a stouter one"),
    "side.tooth.reach": (2.2, "Side joint: 0.6 past the stem when centred"),
    "tooth.length": (4, "Tooth along the joint, ramps included"),
    "tooth.ramp": (1.5, "Each ramp"),
    "notch.depth": (0.65, "Into the stem: the tooth's 0.6 and a little"),
}
D = {"u.mid": "body.width / 2", "v.mid": "body.height / 2",
     "open.half": "stem.width / 2 + float", "chan.half": "head.width / 2 + float",
     "side.open": "stem.width / 2 + side.float", "side.chan": "side.head / 2 + side.float",
     "rail.top": "stem.height + head.height",
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


def at(point, x, y):
    return [{"c": "distance_x", "a": "o", "b": point, "value": x},
            {"c": "distance_y", "a": "o", "b": point, "value": y}]


def polygon(fid, pts, role, plane, extra=None):
    """A closed outline through `pts`, every corner placed from the origin."""
    names = [f"p{i}" for i in range(len(pts))]
    cons = [ORIGIN]
    for n, (x, y) in zip(names, pts):
        cons += at(n, x, y)
    return {"id": fid, "version": 1, "type": "sketch", "plane": plane,
            "points": {"o": [0, 0], **{n: [num(x, V), num(y, V)] for n, (x, y) in zip(names, pts)}},
            "constraints": cons, "profiles": {role: names}}


def rect(fid, x0, y0, x1, y1, role, plane):
    return polygon(fid, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)], role, plane)


# The front plane, looking from the front: sketch x runs to the viewer's
# right (world -X), sketch y runs up, and the normal runs back into the body.
FRONT = {"origin": [0, 0, 0], "x": [-1, 0, 0], "y": [0, 0, 1]}
BACK = {"origin": [0, "body.depth", 0], "x": [-1, 0, 0], "y": [0, 0, 1]}
W, H = "body.width", "body.height"


def lips(c, base, out, along, opening="open.half", chan="chan.half"):
    """Two lips either side of centre `c` on the face at `base`, standing
    `out` (+1 or -1) from it. `along` gives a point from (distance along the
    face, distance out of it). Listed in the direction of increasing
    distance along the face."""
    g, f = "gap", "gap - flange.height"
    seq = [(f"{c} - {chan} - web.width", 0), (f"{c} - {chan} - web.width", g),
           (f"{c} - {opening}", g), (f"{c} - {opening}", f), (f"{c} - {chan}", f),
           (f"{c} - {chan}", 0), (f"{c} + {chan}", 0), (f"{c} + {chan}", f),
           (f"{c} + {opening}", f), (f"{c} + {opening}", g),
           (f"{c} + {chan} + web.width", g), (f"{c} + {chan} + web.width", 0)]
    return [along(a, f"{base} + {out} * ({d})") for a, d in seq]


def rail(c, base, out, along, head="head.width"):
    """A T rail centred at `c` on the face at `base`, standing `out` from it."""
    s, t = "stem.height", "rail.top"
    seq = [(f"{c} - stem.width / 2", 0), (f"{c} - stem.width / 2", s),
           (f"{c} - {head} / 2", s), (f"{c} - {head} / 2", t),
           (f"{c} + {head} / 2", t), (f"{c} + {head} / 2", s),
           (f"{c} + stem.width / 2", s), (f"{c} + stem.width / 2", 0)]
    return [along(a, f"{base} + {out} * ({d})") for a, d in seq]


def outline():
    """Counter-clockwise from the low left corner: a skid, lips and a skid
    under, a rail on the right, a rail on top, lips on the left."""
    skid = lambda lo: [(lo, 0), (lo, "-gap"), (f"{lo} + skid.width", "-gap"),
                       (f"{lo} + skid.width", 0)]
    pts = [(0, 0)] + skid("skid.inset")
    pts += lips("u.mid", 0, -1, lambda a, d: (a, d))
    pts += skid(f"{W} - skid.inset - skid.width") + [(W, 0)]
    pts += rail("v.mid", W, 1, lambda a, d: (d, a), "side.head")
    pts += [(W, H)]
    pts += list(reversed(rail("u.mid", H, 1, lambda a, d: (a, d))))
    pts += [(0, H)]
    pts += list(reversed(lips("v.mid", 0, -1, lambda a, d: (d, a), "side.open", "side.chan")))
    return pts


def cavity():
    lo, hi = "wall", f"{W} - wall"
    a, b = "wall + ledge.height", "wall + ledge.height + ledge.size"
    return [(lo, "wall"), (hi, "wall"), (hi, a), (f"{hi} - ledge.size", a),
            (f"{hi} - ledge.size", b), (hi, b), (hi, f"{H} - wall"), (lo, f"{H} - wall"),
            (lo, b), (f"{lo} + ledge.size", b), (f"{lo} + ledge.size", a), (lo, a)]


def shape(fid, pts, role, plane, swap):
    """A polygon given as (across the joint, along it), drawn on a plane
    whose sketch axes are those two, or the other way round."""
    pts = [(y, a) if swap else (a, y) for a, y in pts]
    xy = [(num(x, V), num(y, V)) for x, y in pts]
    turn = sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(xy, xy[1:] + xy[:1]))
    return polygon(fid, pts if turn > 0 else pts[::-1], role, plane)


# A joint, as the planes its parts are drawn on. `swap` says the plane's
# sketch axes are (along, across) and not (across, along); `back` that the
# plane's second axis runs from back to front, so distances along are negated.
UNDER = {"name": "under", "centre": "u.mid", "swap": False,
         "open": "open.half", "chan": "chan.half", "fw": "finger.width",
         "fl": "finger.length", "reach": "tooth.reach", "play": "float",
         # Outside of the lips' flanges, the flanges' inner side, the rail's top.
         "lip": {"origin": [0, 0, "-gap"], "x": [-1, 0, 0], "y": [0, 1, 0]},
         "flange": {"origin": [0, 0, "-(gap - flange.height)"], "x": [-1, 0, 0], "y": [0, 1, 0]},
         "rail": {"origin": [0, 0, f"{H} + rail.top"], "x": [-1, 0, 0], "y": [0, -1, 0]},
         "rail_back": True, "rail_swap": False}
SIDE = {"name": "side", "centre": "v.mid", "swap": True,
        "open": "side.open", "chan": "side.chan", "fw": "side.finger.width",
        "fl": "side.finger.length", "reach": "side.tooth.reach", "play": "side.float",
        "lip": {"origin": ["gap", 0, 0], "x": [0, 1, 0], "y": [0, 0, 1]},
        "flange": {"origin": ["gap - flange.height", 0, 0], "x": [0, 1, 0], "y": [0, 0, 1]},
        "rail": {"origin": [f"-({W} + rail.top)", 0, 0], "x": [0, 0, 1], "y": [0, 1, 0]},
        "rail_back": False, "rail_swap": False}


def notch_inset(joint):
    """How far inside a tooth's ends its notch's ends are. Centred, the
    tooth's ramps cross the stem's surface this far in; a notch that ends
    there (less a little) holds the tooth by its ramps, with no slide."""
    return f"tooth.ramp * ({joint['play']} + 0.2) / ({joint['reach']} + 0.2) - 0.15"


def latch(joint, last, fingers=True, notches=True):
    """Two fingers in the lips of one joint, and two notches in the rail
    that the same joint of a neighbour presents."""
    f, c = [], joint["centre"]
    opening, chan, fw, reach = joint["open"], joint["chan"], joint["fw"], joint["reach"]
    tip, root = "catch.from_front", f"catch.from_front + {joint['fl']}"
    t0, t1 = "tooth.from", "tooth.from + tooth.length"
    for k, s in enumerate((1, -1)):
        edge = lambda d: f"{c} + {s} * ({opening} + ({d}))"
        far = f"{c} + {s} * ({chan})"
        name = f"latch.{joint['name']}{k}"
        if fingers:
            # The slot that frees the finger: all of the flange behind it,
            # and across its end.
            slot = [(edge(-0.2), f"{tip} - 0.8"), (far, f"{tip} - 0.8"), (far, root),
                    (edge(fw), root), (edge(fw), tip), (edge(-0.2), tip)]
            f.append(shape(f"{name}.slot.sketch", slot, "slot", joint["lip"], joint["swap"]))
            f.append({"id": f"{name}.slot", "version": 1, "type": "pocket", "target": ref(last, "body"),
                      "profile": ref(f"{name}.slot.sketch", "slot"), "depth": "flange.height + 0.2"})
            tooth = [(edge(0.2), t0), (edge(0.2), t1), (edge(f"-{reach}"), f"{t1} - tooth.ramp"),
                     (edge(f"-{reach}"), f"{t0} + tooth.ramp")]
            f.append(shape(f"{name}.tooth.sketch", tooth, "tooth", joint["flange"], joint["swap"]))
            f.append({"id": f"{name}.tooth", "version": 1, "type": "boss",
                      "target": ref(f"{name}.slot", "body"),
                      "profile": ref(f"{name}.tooth.sketch", "tooth"), "height": "flange.height"})
            last = f"{name}.tooth"
        if notches:
            # The notch, through the rail's head and into its stem.
            y = (lambda e: f"-({e})") if joint["rail_back"] else (lambda e: e)
            side = lambda d: f"{c} + {s} * (stem.width / 2 + ({d}))"
            inset = notch_inset(joint)
            n0, n1 = f"{t0} + {inset}", f"{t1} - ({inset})"
            notch = [(side("-notch.depth"), y(n0)), (side(f"{reach} + 0.4"), y(n0)),
                     (side(f"{reach} + 0.4"), y(n1)), (side("-notch.depth"), y(n1))]
            f.append(shape(f"{name}.notch.sketch", notch, "notch", joint["rail"], joint["rail_swap"]))
            f.append({"id": f"{name}.notch", "version": 1, "type": "pocket",
                      "target": ref(last, "body"),
                      "profile": ref(f"{name}.notch.sketch", "notch"), "depth": "rail.top"})
            last = f"{name}.notch"
    return f, last


def reliefs(last, top=True, under=True, rail=True, lips=True, skids=True):
    """Cuts that end the joints short of the front. Each takes exactly the
    height of what it removes, so the body's faces are left whole."""
    f = []
    lo = "skid.inset - 0.5" if skids else "u.mid - chan.half - web.width - 0.5"
    hi = f"{W} - skid.inset + 0.5" if skids else "u.mid + chan.half + web.width + 0.5"
    cuts = []
    if top:
        cuts.append(("relief.top", UNDER["rail"], ("u.mid - head.width / 2 - 0.5", "-front.relief",
                                                    "u.mid + head.width / 2 + 0.5", 1), "rail.top"))
    if under:
        cuts.append(("relief.under", UNDER["lip"], (lo, -1, hi, "front.relief"), "gap"))
    if rail:
        cuts.append(("relief.rail", SIDE["rail"], ("v.mid - side.head / 2 - 0.5", -1,
                                                    "v.mid + side.head / 2 + 0.5", "front.relief"), "rail.top"))
    if lips:
        cuts.append(("relief.lips", SIDE["lip"], (-1, "v.mid - side.chan - web.width - 0.5", "front.relief",
                                                   "v.mid + side.chan + web.width + 0.5"), "gap"))
    for name, plane, (x0, y0, x1, y1), depth in cuts:
        f.append(rect(f"{name}.sketch", x0, y0, x1, y1, "cut", plane))
        f.append({"id": name, "version": 1, "type": "pocket", "target": ref(last, "body"),
                  "profile": ref(f"{name}.sketch", "cut"), "depth": depth})
        last = name
    return f, last


def relief_area(top=True, under=True, rail=True, lips=True, skids=True):
    """Cross-section the reliefs remove, for the volume by hand."""
    v, a = V, 0.0
    if top:
        a += v["stem.width"] * v["stem.height"] + v["head.width"] * v["head.height"]
    if under:
        a += 2 * (v["web.width"] * v["gap"] + (v["chan.half"] - v["open.half"]) * v["flange.height"])
        a += 2 * v["skid.width"] * v["gap"] if skids else 0
    if rail:
        a += v["stem.width"] * v["stem.height"] + v["side.head"] * v["head.height"]
    if lips:
        a += 2 * (v["web.width"] * v["gap"] + (v["side.chan"] - v["side.open"]) * v["flange.height"])
    return a


def latch_volume(joint, fingers=True, notches=True):
    """What one joint's latch adds (teeth) less what it removes (slots, notches)."""
    v, vol = V, 0.0
    flange = v[joint["chan"]] - v[joint["open"]]
    fw, fl, reach, play = v[joint["fw"]], v[joint["fl"]], v[joint["reach"]], v[joint["play"]]
    if fingers:
        slot = (flange - fw) * fl + flange * 0.8
        wide = v["tooth.length"] - 2 * v["tooth.ramp"] * 0.2 / (reach + 0.2)
        tooth = (wide + v["tooth.length"] - 2 * v["tooth.ramp"]) / 2 * reach
        vol += 2 * (tooth - slot) * v["flange.height"]
    if notches:
        long = v["tooth.length"] - 2 * (v["tooth.ramp"] * (play + 0.2) / (reach + 0.2) - 0.15)
        vol -= 2 * long * ((v["notch.depth"] + reach + 0.4) * v["head.height"]
                           + v["notch.depth"] * v["stem.height"])
    return vol


def area(pts):
    xy = [(num(x, V), num(y, V)) for x, y in pts]
    return abs(sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(xy, xy[1:] + xy[:1]))) / 2


def features():
    out = outline()
    f = [polygon("shell.sketch", out, "outline", FRONT),
         {"id": "shell.extrude", "version": 1, "type": "extrude",
          "profile": ref("shell.sketch", "outline"), "depth": "body.depth"},
         polygon("cavity.sketch", cavity(), "opening", BACK),
         {"id": "cavity", "version": 1, "type": "pocket", "target": ref("shell.extrude", "body"),
          "profile": ref("cavity.sketch", "opening"), "depth": "body.depth + 1"}]
    last = "cavity"
    more, last = reliefs(last)
    f += more
    # The ledges end short of the front; the carrier's face stops on their ends.
    face = {"origin": [0, 0, 0], "x": [1, 0, 0], "y": [0, 0, 1]}  # normal -Y: sketch x is world X
    z0, z1 = "wall + ledge.height - 0.3", "wall + ledge.height + ledge.size + 0.3"
    for k, (a, b) in enumerate((("-(wall + ledge.size + 0.3)", "-wall"),
                                (f"-({W} - wall)", f"-({W} - wall - ledge.size - 0.3)"))):
        f.append(rect(f"ledge{k}.cut.sketch", a, z0, b, z1, "cut", face))
        f.append({"id": f"ledge{k}.cut", "version": 1, "type": "pocket", "target": ref(last, "body"),
                  "profile": ref(f"ledge{k}.cut.sketch", "cut"), "depth": "ledge.cut"})
        last = f"ledge{k}.cut"
    for joint in (UNDER, SIDE):
        more, last = latch(joint, last)
        f += more
    return f, last, out


def corners(out):
    """The four long outer edges, each as the two sides of the outline that
    meet at a corner of the body."""
    pairs = []
    for corner in [(0, 0), (W, 0), (W, H), (0, H)]:
        i = out.index(corner)
        side = lambda k: {"feature": "shell.extrude", "role": "side", "index": k % len(out)}
        pairs.append([side(i - 1), side(i)])
    return pairs


def expected_volume(rounded):
    v = V
    vol = (area(outline()) - area(cavity())) * v["body.depth"]
    vol -= relief_area() * v["front.relief"]
    vol -= 2 * v["ledge.size"] ** 2 * v["ledge.cut"]
    vol += latch_volume(UNDER) + latch_volume(SIDE)
    if rounded:
        vol -= (4 - math.pi) * v["corner.radius"] ** 2 * v["body.depth"]
    return vol


def run(ops, last, key, rounded):
    head = rw("inspect", DOC)["result"]["revision"]
    ops = ops + [{"op": "set_name", "name": "cell.body", "reference": ref(last, "body")}]
    want = expected_volume(rounded)
    tx = {"schema_version": 1, "document": DOC, "base_revision": head, "operations": ops,
          "checks": [{"kind": "valid_solid", "body": "cell.body"},
                     {"kind": "volume", "body": "cell.body", "unit": "mm",
                      "at_least": want * 0.9995, "at_most": want * 1.0005}] + measures("cell.body", (lambda w, h: (w, V["body.depth"], h))(*spans(outline(), num, V)), 0.8)}
    open(f"tx-{key}.json", "w").write(json.dumps(tx, indent=1))
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
         {"op": "add_output", "output": {"id": "cell.step", "kind": "step", "source": "cell.body"}}],
        "soften", "soften", True)


if __name__ == "__main__":
    main()
