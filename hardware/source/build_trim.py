#!/usr/bin/env python3
"""Builds the perimeter trim: three thin caps that finish the outside of a
cluster by covering the joints nothing is joined to.

Each is a 2 mm plate carrying one half of the cell's own joint, drawn with
the cell's own code, so it slides on and latches the way a cell does:
  trimtop   over a top rail: a plate with the cell's lips and skids under it
  trimtophalf  the same, half a pitch wide, for the top of a column of spacers
  trimrail  over a side rail: a plate with the cell's side lips
  trimlip   into side lips: a plate with the cell's side rail
"""
import json, sys
import build_cell as c
from build_checks import measures, spans

T = 2.0  # plate thickness
W, H = c.W, c.H


def configure(overrides):
    """The cell's parameters with some changed, and everything derived from them."""
    for k, x in overrides.items():
        c.P[k] = (x, c.P[k][1])
    c.V.clear()
    c.V.update({k: float(x) for k, (x, _) in c.P.items()})
    for k, e in c.D.items():
        c.V[k] = c.num(e, c.V)


def top():
    skid = lambda lo: [(lo, 0), (lo, "-gap"), (f"{lo} + skid.width", "-gap"), (f"{lo} + skid.width", 0)]
    pts = [(0, 0)] + skid("skid.inset") + c.lips("u.mid", 0, -1, lambda a, d: (a, d))
    return pts + skid(f"{W} - skid.inset - skid.width") + [(W, 0), (W, H), (0, H)]


def over_rail():
    lips = c.lips("v.mid", 0, -1, lambda a, d: (d, a), "side.open", "side.chan")
    return [(0, 0), (W, 0), (W, H), (0, H)] + list(reversed(lips))


def into_lips():
    return [(0, 0), (W, 0)] + c.rail("v.mid", W, 1, lambda a, d: (d, a), "side.head") + [(W, H), (0, H)]


# document: (what to change, outline, which reliefs, joint, fingers, notches)
TRIMS = {
    "trimtop": ({"body.height": T}, top, dict(top=False, under=True, rail=False, lips=False), c.UNDER, True, False),
    "trimtophalf": ({"body.height": T, "body.width": 31.7}, top, dict(top=False, under=True, rail=False, lips=False), c.UNDER, True, False),
    "trimrail": ({"body.width": T}, over_rail, dict(top=False, under=False, rail=False, lips=True), c.SIDE, True, False),
    "trimlip": ({"body.width": T}, into_lips, dict(top=False, under=False, rail=True, lips=False), c.SIDE, False, True),
}


def build(doc):
    change, outline, relief, joint, fingers, notches = TRIMS[doc]
    original = dict(c.P)
    configure(change)
    try:
        made = c.rw("create", doc)
        if not made["ok"]:
            sys.exit(json.dumps(made))
        ops = [{"op": "add_parameter", "id": k, "parameter": {
            "value": x, "unit": "mm", "greater_than": 0, "description": d}} for k, (x, d) in c.P.items()]
        ops += [{"op": "add_parameter", "id": k, "parameter": {"expr": e, "unit": "mm"}}
                for k, e in c.D.items()]
        out = outline()
        feats = [c.polygon("shell.sketch", out, "outline", c.FRONT),
                 {"id": "shell.extrude", "version": 1, "type": "extrude",
                  "profile": c.ref("shell.sketch", "outline"), "depth": "body.depth"}]
        more, last = c.reliefs("shell.extrude", **relief)
        feats += more
        more, last = c.latch(joint, last, fingers=fingers, notches=notches)
        feats += more
        ops += [{"op": "add_feature", "feature": f} for f in feats]
        ops.append({"op": "set_name", "name": "trim.body", "reference": c.ref(last, "body")})
        ops.append({"op": "add_output", "output": {"id": "trim.step", "kind": "step", "source": "trim.body"}})
        want = c.area(out) * c.V["body.depth"] - c.relief_area(**relief) * c.V["front.relief"]
        want += c.latch_volume(joint, fingers, notches)
        tx = {"schema_version": 1, "document": doc, "base_revision": made["result"]["revision"],
              "operations": ops,
              "checks": [{"kind": "valid_solid", "body": "trim.body"},
                         {"kind": "volume", "body": "trim.body", "unit": "mm",
                          "at_least": want * 0.9995, "at_most": want * 1.0005}] + measures("trim.body", (lambda w, h: (w, c.V["body.depth"], h))(*spans(out, c.num, c.V)), 1.0)}
        open(f"tx-{doc}.json", "w").write(json.dumps(tx, indent=1))
        dry = c.rw("dry-run", "--brief", "-", stdin=json.dumps(tx))
        if not dry["ok"]:
            sys.exit(f"{doc}: {json.dumps(dry['failure'], indent=1)[:3000]}")
        r = dry["result"]
        print(f"{doc}: checks {[(k['kind'], k['passed']) for k in r['checks']]}, by hand {want:.2f}, "
              f"kernel {r['measurements']['body'].get('kernel_volume')}")
        if not r["checks_passed"]:
            sys.exit(json.dumps(r["checks"], indent=1)[:3000])
        done = c.rw("commit", "--document", doc, "--candidate", r["candidate_digest"],
                    "--base", tx["base_revision"], "--key", f"{doc}-1")
        print("  committed", done["result"]["revision"] if done["ok"] else done)
    finally:
        c.P.clear()
        c.P.update(original)
        configure({})


if __name__ == "__main__":
    for doc in (sys.argv[1:] or TRIMS):
        build(doc)
