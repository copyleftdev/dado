#!/usr/bin/env python3
"""Builds the spacers: half a place of room between rows or between columns,
for air and for cables.

  spacerrow    a full place wide, half a row high: goes between two rows
  spacercol    half a place wide, a full row high: goes between two columns
  spacercross  half by half: where a line of one crosses a line of the other

Each is the cell's own section at half size, drawn with the cell's own code,
so two of them and their gaps are exactly one place and the lattice comes
back into step. Like a cell, each has a rail on top and lips underneath. The
column spacer has the cell's side joint as well; the two half-height ones are
too low to carry it (its lips are 22.4 tall) and are held from above and
below only.

Every spacer has a closed front with air slots and an open back, so air
passes straight through. For cables:
  the column spacer has no floor or roof over its rear 40 mm, so a stack of
      them is one open shaft, top to bottom;
  the row spacer has no side walls over its rear 40 mm, so a line of them
      is one open tray, side to side;
  the cross is only 60 mm deep, so where a tray meets a shaft there is
      nothing in the way.

x runs across (negative, as in a cell), y from the front, z up."""
import json, math, sys
import build_cell as c
from build_checks import measures, spans

PITCH = c.P["body.width"][0] + c.P["gap"][0]
RISE = c.P["body.height"][0] + c.P["gap"][0]
# wide (places), high (rows), shaft through floor and roof, tray through the sides, air slots across and up
KINDS = {"spacerrow": (1, 0.5, False, True, 5, 1), "spacercol": (0.5, 1, True, False, 2, 3),
         "spacercross": (0.5, 0.5, False, False, 2, 1)}
DOC = sys.argv[1] if len(sys.argv) > 1 else "spacerrow"
WIDE, HIGH, SHAFT, TRAY, ACROSS, UP = KINDS[DOC]
FULL, SIDES = WIDE == 1, HIGH == 1  # skids need the full width; the side joint needs the full height
W, H = c.W, c.H


def configure():
    for k in ("ledge.size", "ledge.height", "ledge.cut"):
        del c.P[k]
    gap = c.P["gap"][0]
    c.P["body.width"] = (round(WIDE * PITCH - gap, 4), "A whole place" if FULL else "Half a pitch less a gap: two of these and their gaps are one place")
    c.P["body.height"] = (round(HIGH * RISE - gap, 4), "A whole row" if SIDES else "Half a rise less a gap: two of these and their gaps are one row")
    c.P["front.wall"] = (3, "The closed front")
    c.P["slot.width"] = (8, "Air slots in the front, as in a carrier's face")
    c.P["slot.height"] = (7, "Their height")
    c.P["slot.pitch"] = (10.5, "Slot to slot across")
    c.P["slot.step"] = (11.5, "Row of slots to row")
    if DOC == "spacercross":
        c.P["body.depth"] = (60, "It ends where the shaft and the tray begin: behind it is open, up, down and to both sides")
    if SHAFT:
        c.P["shaft.depth"] = (40, "No floor or roof over this much of the back: stacked, an open shaft for cables")
    if TRAY:
        c.P["tray.depth"] = (40, "No side walls over this much of the back: in a line, an open tray for cables")
    c.V.clear()
    c.V.update({k: float(x) for k, (x, _) in c.P.items()})
    for k, e in c.D.items():
        c.V[k] = c.num(e, c.V)


def outline():
    flat, turn = (lambda a, d: (a, d)), (lambda a, d: (d, a))
    skid = lambda lo: [(lo, 0), (lo, "-gap"), (f"{lo} + skid.width", "-gap"), (f"{lo} + skid.width", 0)]
    pts = [(0, 0)] + (skid("skid.inset") if FULL else []) + c.lips("u.mid", 0, -1, flat)
    pts += (skid(f"{W} - skid.inset - skid.width") if FULL else []) + [(W, 0)]
    pts += (c.rail("v.mid", W, 1, turn, "side.head") if SIDES else []) + [(W, H)]
    pts += list(reversed(c.rail("u.mid", H, 1, flat))) + [(0, H)]
    return pts + (list(reversed(c.lips("v.mid", 0, -1, turn, "side.open", "side.chan"))) if SIDES else [])


def cavity():
    return [("wall", "wall"), (f"{W} - wall", "wall"), (f"{W} - wall", f"{H} - wall"), ("wall", f"{H} - wall")]


FACE = {"origin": [0, 0, 0], "x": [1, 0, 0], "y": [0, 0, 1]}  # the front, seen from outside


def cuts():
    """Pockets cut after the shell: name, plane, box on that plane, depth."""
    out = []
    for r in range(UP):
        z = f"v.mid - {(UP - 1) / 2} * slot.step - slot.height / 2 + {r} * slot.step"
        for k in range(ACROSS):
            x = f"u.mid - {(ACROSS - 1) / 2} * slot.pitch - slot.width / 2 + {k} * slot.pitch"
            out.append((f"air{r}{k}", FACE, (f"-({x} + slot.width)", z, f"-({x})", f"{z} + slot.height"), "front.wall"))
    if SHAFT:
        lo, hi = "body.depth - shaft.depth", "body.depth + 1"
        out.append(("shaft.roof", c.UNDER["rail"], ("wall", f"-({hi})", f"{W} - wall", f"-({lo})"), "rail.top + wall"))
        out.append(("shaft.floor", c.UNDER["lip"], ("wall", lo, f"{W} - wall", hi), "gap + wall"))
    if TRAY:
        lo, hi = "body.depth - tray.depth", "body.depth + 1"
        out.append(("tray.rail", c.SIDE["rail"], ("wall", lo, f"{H} - wall", hi), "rail.top + wall"))
        out.append(("tray.lips", c.SIDE["lip"], (lo, "wall", hi, f"{H} - wall"), "gap + wall"))
    return out


RELIEF = dict(top=True, under=True, rail=SIDES, lips=SIDES, skids=FULL)


def features():
    out = outline()
    f = [c.polygon("shell.sketch", out, "outline", c.FRONT),
         {"id": "shell.extrude", "version": 1, "type": "extrude",
          "profile": c.ref("shell.sketch", "outline"), "depth": "body.depth"},
         c.polygon("cavity.sketch", cavity(), "opening", c.BACK),
         {"id": "cavity", "version": 1, "type": "pocket", "target": c.ref("shell.extrude", "body"),
          "profile": c.ref("cavity.sketch", "opening"), "depth": "body.depth - front.wall"}]
    more, last = c.reliefs("cavity", **RELIEF)
    f += more
    for name, plane, box, depth in cuts():
        f.append(c.rect(f"{name}.sketch", *box, "cut", plane))
        f.append({"id": name, "version": 1, "type": "pocket", "target": c.ref(last, "body"),
                  "profile": c.ref(f"{name}.sketch", "cut"), "depth": depth})
        last = name
    for joint in (c.UNDER, c.SIDE) if SIDES else (c.UNDER,):
        more, last = c.latch(joint, last)
        f += more
    return f, last, out


def expected_volume(rounded):
    v = c.V
    inside_w, inside_h = v["body.width"] - 2 * v["wall"], v["body.height"] - 2 * v["wall"]
    vol = c.area(outline()) * v["body.depth"] - c.area(cavity()) * (v["body.depth"] - v["front.wall"])
    vol -= c.relief_area(**RELIEF) * v["front.relief"]
    vol -= ACROSS * UP * v["slot.width"] * v["slot.height"] * v["front.wall"]
    if SHAFT:
        rail = v["stem.width"] * v["stem.height"] + v["head.width"] * v["head.height"]
        lips = 2 * (v["web.width"] * v["gap"] + (v["chan.half"] - v["open.half"]) * v["flange.height"])
        vol -= v["shaft.depth"] * (2 * v["wall"] * inside_w + rail + lips)
    if TRAY:
        vol -= v["tray.depth"] * 2 * v["wall"] * inside_h
    vol += c.latch_volume(c.UNDER) + (c.latch_volume(c.SIDE) if SIDES else 0)
    if rounded:
        vol -= (4 - math.pi) * v["corner.radius"] ** 2 * v["body.depth"]
    return vol


def run(ops, last, key, rounded):
    head = c.rw("inspect", DOC)["result"]["revision"]
    ops = ops + [{"op": "set_name", "name": "spacer.body", "reference": c.ref(last, "body")}]
    want = expected_volume(rounded)
    tx = {"schema_version": 1, "document": DOC, "base_revision": head, "operations": ops,
          "checks": [{"kind": "valid_solid", "body": "spacer.body"},
                     {"kind": "volume", "body": "spacer.body", "unit": "mm",
                      "at_least": want * 0.9995, "at_most": want * 1.0005}] + measures("spacer.body", (lambda w, h: (w, c.V["body.depth"], h))(*spans(outline(), c.num, c.V)), 0.8)}
    open(f"tx-{DOC}-{key}.json", "w").write(json.dumps(tx, indent=1))
    dry = c.rw("dry-run", "--brief", "-", stdin=json.dumps(tx))
    if not dry["ok"]:
        sys.exit(f"{key}: {json.dumps(dry['failure'], indent=1)[:3000]}")
    r = dry["result"]
    print(f"{DOC} {key}: checks {[(k['kind'], k['passed']) for k in r['checks']]}, by hand {want:.2f},"
          f" kernel {r['measurements']['body'].get('kernel_volume')}")
    if not r["checks_passed"]:
        sys.exit(json.dumps(r["checks"], indent=1)[:3000])
    done = c.rw("commit", "--document", DOC, "--candidate", r["candidate_digest"], "--base", head,
                "--key", f"{DOC}-{key}")
    print("  committed", done["result"]["revision"] if done["ok"] else done)


def main():
    configure()
    made = c.rw("create", DOC)
    if not made["ok"]:
        sys.exit(json.dumps(made))
    ops = [{"op": "add_parameter", "id": k, "parameter": {
        "value": x, "unit": "mm", "greater_than": 0, "description": d}} for k, (x, d) in c.P.items()]
    ops += [{"op": "add_parameter", "id": k, "parameter": {"expr": e, "unit": "mm"}} for k, e in c.D.items()]
    feats, last, out = features()
    ops += [{"op": "add_feature", "feature": f} for f in feats]
    run(ops, last, "shape", False)
    soften = {"id": "soften", "version": 1, "type": "edge_fillet", "target": c.ref(last, "body"),
              "edges": c.corners(out), "radius": "corner.radius"}
    run([{"op": "add_feature", "feature": soften},
         {"op": "add_output", "output": {"id": "spacer.step", "kind": "step", "source": "spacer.body"}}],
        "soften", "soften", True)


if __name__ == "__main__":
    main()
