#!/usr/bin/env python3
"""How each part would print: which way up it goes, how much of it overhangs
that way, and which printers' beds take it. Measured by Ringwright on the
committed bodies, with its overhang check.

Each part has one way up, chosen as the one with the least overhang of the
six, and a ceiling on its overhang that way: what it measured when this was
written, and a little. A change that makes a part harder to print fails here.

Overhang is the area facing downward that leans more than 60 degrees from
upright, which is where a slicer starts adding support by default.

  python3 print_check.py            check every part
  python3 print_check.py --survey   measure all six ways up, to choose from"""
import json, os, subprocess, sys

RW = __import__("os").environ.get("RINGWRIGHT", "ringwright")
LEAN = 60
# part: (way up, overhang allowed that way in mm2). "-y" is the y axis pointing down: the part stands on its back end.
WAYS = {
    "cell": ("-y", 45), "bay": ("-y", 80), "baytall": ("-y", 105), "bayrack": ("-y", 120), "bayduo": ("-y", 85), "bayagx": ("-y", 110),
    "trimtop": ("-y", 10), "trimrail": ("-y", 15), "trimlip": ("-y", 12), "trimtophalf": ("-y", 10),
    "base": ("+y", 105), "basehalf": ("+y", 105), "spacerrow": ("+y", 92), "spacercol": ("+y", 153), "spacercross": ("+y", 70),
    "carrier": ("+z", 875), "shelf": ("+z", 1635), "shelftall": ("+z", 1635), "shelfrack": ("+z", 2215), "orin": ("+z", 2020), "agx": ("+z", 2985),
}
# Beds to try: across, front to back, height. From makers' stated figures.
BEDS = {"180 class (Bambu Lab A1 mini, Prusa MINI)": (180, 180, 180), "220 class (Creality Ender-3 V3 SE)": (220, 220, 250),
        "Prusa MK4S": (250, 210, 220), "256 class (Bambu Lab P1S, A1)": (256, 256, 250), "350 class (Voron 2.4 350)": (350, 350, 325)}
results = []


def rw(*args, stdin=None):
    return json.loads(subprocess.run([RW, *args], input=stdin, capture_output=True, text=True).stdout)


def report(verdict, name, detail):
    results.append(verdict)
    print(f"{verdict:4}  {name}: {detail}")


def measure(doc, ways):
    """The part's size, and for each way up its overhang and what rests on the bed."""
    head = rw("inspect", doc)["result"]["revision"]
    ask = lambda checks: rw("dry-run", "--brief", "-", stdin=json.dumps(
        {"schema_version": 1, "document": doc, "base_revision": head, "operations": [], "checks": checks}))
    body = ask([{"kind": "valid_solid", "body": "?"}])["failure"]["details"]["known"][0]
    checks = [{"kind": "extent", "body": body, "axis": a, "at_least": 0, "unit": "mm"} for a in "xyz"]
    checks += [{"kind": "overhang", "body": body, "up": w[1], "flipped": w[0] == "-", "beyond_deg": LEAN, "area_at_most": 0, "unit": "mm"}
               for w in ways]
    got = ask(checks)["result"]["checks"]
    size = [c["evidence"]["measured"] for c in got[:3]]
    return size, {w: (c["evidence"]["measured"], c["evidence"]["on_the_bed"]) for w, c in zip(ways, got[3:])}


def fits(size, way, bed):
    """Whether the part, stood the given way up, goes on the bed either way round."""
    up = "xyz".index(way[1])
    a, b = (s for k, s in enumerate(size) if k != up)
    return size[up] <= bed[2] and ((a <= bed[0] and b <= bed[1]) or (b <= bed[0] and a <= bed[1]))


if "--survey" in sys.argv:
    ALL = [s + a for a in "xyz" for s in "+-"]
    for doc in WAYS:
        size, found = measure(doc, ALL)
        print(f"{doc:12} " + "  ".join(f"{w} {o:7.0f}/{bed:6.0f}" for w, (o, bed) in found.items()) + "   (overhang/on the bed, mm2)")
    sys.exit(0)

print("== 1. Each part, the way up it prints ==")
sizes = {}
for doc, (way, ceiling) in WAYS.items():
    sizes[doc], found = measure(doc, [way])
    over, bed = found[way]
    report("PASS" if over <= ceiling and bed > 0 else "FAIL", f"{doc}, {way} up",
           f"{over:.0f} mm2 overhangs (allowed {ceiling}); {bed:.0f} mm2 rests on the bed")
report("NOTE", "the carrier, shelves and Jetson trays", "lie flat on their plates: their latches are in the plane of the plate. Most of "
       "what still overhangs is the pull, a rail 6 mm proud along the top of the face, which needs support; the rest is the tops of "
       "the slots and windows, which are bridges")

print("== 2. Which beds take each part, that way up ==")
for name, bed in BEDS.items():
    out = [doc for doc, (way, _) in WAYS.items() if not fits(sizes[doc], way, bed)]
    report("NOTE", name, f"takes {len(WAYS) - len(out)} of {len(WAYS)} parts" + (f"; too big: {', '.join(out)}" if out else ""))

print()
print({v: results.count(v) for v in ("PASS", "FAIL", "NOTE")})
sys.exit(1 if "FAIL" in results else 0)
