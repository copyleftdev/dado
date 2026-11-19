#!/usr/bin/env python3
"""Builds the bay: a sleeve as wide as several cells, for what is not a
Raspberry Pi: a network switch, a hub, a drive.

It is the cell's own section, stretched. Its body is N pitches wide and M
rises tall, less one gap each way, so it fills exactly the place of N by M
cells; it carries one of the cell's top rails and one pair of the cell's
lips at every pitch, and the cell's side rail and side lips at every rise,
in the places those cells would have had them. So it
slides onto a row of cells, a row of cells or caps slides onto it, and
columns join to its sides, all with the joints already made. Everything is
drawn with the cell's own code."""
import json, math, sys
import build_cell as c

# Places across, places up, roof thickness. The roof spans the whole bay and
# carries whatever stands on it, so it is thicker than a cell's wall:
#   bay      3 x 1, roof 7:  switches and hubs up to about 29 mm tall
#   baytall  3 x 2, roof 10: taller gear
#   bayrack  4 x 2, roof 12: ten-inch rack gear, one unit (44.45 mm) tall
#   bayduo   2 x 2, roof 6:  a larger single-board computer with its cooler,
#                            such as a Jetson Orin Nano developer kit
KINDS = {"bay": (3, 1, 7.0), "baytall": (3, 2, 10.0), "bayrack": (4, 2, 12.0), "bayduo": (2, 2, 6.0)}
DOC = sys.argv[1] if len(sys.argv) > 1 else "bay"
N, M, ROOF = KINDS[DOC]
W, H = c.W, c.H
PITCH = c.P["body.width"][0] + c.P["gap"][0]
RISE = c.P["body.height"][0] + c.P["gap"][0]
CENTRES = [f"cell.mid + {k} * pitch" for k in range(N)]
ROWS = [f"row.mid + {j} * rise" for j in range(M)]


def configure():
    c.P["cell.mid"] = (c.P["body.width"][0] / 2, "Centre of the first cell's place, from the bay's side")
    c.P["pitch"] = (PITCH, "Cell to cell across: where each rail and pair of lips goes")
    c.P["row.mid"] = (c.P["body.height"][0] / 2, "Centre of the first row's place, from the bay's underside")
    c.P["rise"] = (RISE, "Row to row: where each side rail and pair of side lips goes")
    c.P["roof"] = (ROOF, "The roof: it spans the bay and carries what stands on it")
    c.P["body.width"] = (N * PITCH - c.P["gap"][0], f"{N} pitches less one gap: the place of {N} cells")
    c.P["body.height"] = (M * RISE - c.P["gap"][0], f"{M} rises less one gap: {M} row(s) of cells")
    c.V.clear()
    c.V.update({k: float(x) for k, (x, _) in c.P.items()})
    for k, e in c.D.items():
        c.V[k] = c.num(e, c.V)


def outline():
    skid = lambda lo: [(lo, 0), (lo, "-gap"), (f"{lo} + skid.width", "-gap"), (f"{lo} + skid.width", 0)]
    flat = lambda a, d: (a, d)
    pts = [(0, 0)] + skid("skid.inset")
    for ck in CENTRES:
        pts += c.lips(ck, 0, -1, flat)
    pts += skid(f"{W} - skid.inset - skid.width") + [(W, 0)]
    for vc in ROWS:
        pts += c.rail(vc, W, 1, lambda a, d: (d, a), "side.head")
    pts += [(W, H)]
    for ck in reversed(CENTRES):
        pts += list(reversed(c.rail(ck, H, 1, flat)))
    pts += [(0, H)]
    for vc in reversed(ROWS):
        pts += list(reversed(c.lips(vc, 0, -1, lambda a, d: (d, a), "side.open", "side.chan")))
    return pts


def cavity():
    """The cell's opening, under a thicker roof."""
    return [(x, f"{H} - roof") if y == f"{H} - wall" else (x, y) for x, y in c.cavity()]


def features():
    out = outline()
    f = [c.polygon("shell.sketch", out, "outline", c.FRONT),
         {"id": "shell.extrude", "version": 1, "type": "extrude",
          "profile": c.ref("shell.sketch", "outline"), "depth": "body.depth"},
         c.polygon("cavity.sketch", cavity(), "opening", c.BACK),
         {"id": "cavity", "version": 1, "type": "pocket", "target": c.ref("shell.extrude", "body"),
          "profile": c.ref("cavity.sketch", "opening"), "depth": "body.depth + 1"}]
    last = "cavity"
    for k, ck in enumerate(CENTRES):
        f.append(c.rect(f"relief.top{k}.sketch", f"{ck} - head.width / 2 - 0.5", "-front.relief",
                        f"{ck} + head.width / 2 + 0.5", 1, "cut", c.UNDER["rail"]))
        f.append({"id": f"relief.top{k}", "version": 1, "type": "pocket", "target": c.ref(last, "body"),
                  "profile": c.ref(f"relief.top{k}.sketch", "cut"), "depth": "rail.top"})
        last = f"relief.top{k}"
    more, last = c.reliefs(last, top=False, rail=False, lips=False)
    f += more
    for j, vc in enumerate(ROWS):
        for name, plane, box, depth in (
                (f"relief.rail{j}", c.SIDE["rail"], (f"{vc} - side.head / 2 - 0.5", -1, f"{vc} + side.head / 2 + 0.5", "front.relief"), "rail.top"),
                (f"relief.lips{j}", c.SIDE["lip"], (-1, f"{vc} - side.chan - web.width - 0.5", "front.relief", f"{vc} + side.chan + web.width + 0.5"), "gap")):
            f.append(c.rect(f"{name}.sketch", *box, "cut", plane))
            f.append({"id": name, "version": 1, "type": "pocket", "target": c.ref(last, "body"),
                      "profile": c.ref(f"{name}.sketch", "cut"), "depth": depth})
            last = name
    face = {"origin": [0, 0, 0], "x": [1, 0, 0], "y": [0, 0, 1]}
    z0, z1 = "wall + ledge.height - 0.3", "wall + ledge.height + ledge.size + 0.3"
    for k, (a, b) in enumerate((("-(wall + ledge.size + 0.3)", "-wall"),
                                (f"-({W} - wall)", f"-({W} - wall - ledge.size - 0.3)"))):
        f.append(c.rect(f"ledge{k}.cut.sketch", a, z0, b, z1, "cut", face))
        f.append({"id": f"ledge{k}.cut", "version": 1, "type": "pocket", "target": c.ref(last, "body"),
                  "profile": c.ref(f"ledge{k}.cut.sketch", "cut"), "depth": "ledge.cut"})
        last = f"ledge{k}.cut"
    for k, ck in enumerate(CENTRES):
        more, last = c.latch(dict(c.UNDER, name=f"under{k}", centre=ck), last)
        f += more
    for j, vc in enumerate(ROWS):
        more, last = c.latch(dict(c.SIDE, name=f"side{j}", centre=vc), last)
        f += more
    return f, last, out


def expected_volume(rounded):
    v = c.V
    vol = (c.area(outline()) - c.area(cavity())) * v["body.depth"]
    lips = 2 * (v["web.width"] * v["gap"] + (v["chan.half"] - v["open.half"]) * v["flange.height"])
    rail = v["stem.width"] * v["stem.height"] + v["head.width"] * v["head.height"]
    cut = N * (lips + rail) + 2 * v["skid.width"] * v["gap"] + M * c.relief_area(top=False, under=False)
    vol -= cut * v["front.relief"]
    vol -= 2 * v["ledge.size"] ** 2 * v["ledge.cut"]
    vol += N * c.latch_volume(c.UNDER) + M * c.latch_volume(c.SIDE)
    if rounded:
        vol -= (4 - math.pi) * v["corner.radius"] ** 2 * v["body.depth"]
    return vol


def run(ops, last, key, rounded):
    head = c.rw("inspect", DOC)["result"]["revision"]
    ops = ops + [{"op": "set_name", "name": "bay.body", "reference": c.ref(last, "body")}]
    want = expected_volume(rounded)
    tx = {"schema_version": 1, "document": DOC, "base_revision": head, "operations": ops,
          "checks": [{"kind": "valid_solid", "body": "bay.body"},
                     {"kind": "volume", "body": "bay.body", "unit": "mm",
                      "at_least": want * 0.9995, "at_most": want * 1.0005}]}
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
         {"op": "add_output", "output": {"id": "bay.step", "kind": "step", "source": "bay.body"}}],
        "soften", "soften", True)


if __name__ == "__main__":
    main()
