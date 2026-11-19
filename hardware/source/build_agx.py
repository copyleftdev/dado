#!/usr/bin/env python3
"""Builds the AGX tray: what an NVIDIA Jetson AGX Orin developer kit stands
on in the two-by-three bay (bayagx).

The kit is a closed box with its fan in its top face, so nothing may cover
it: no straps. It stands between two low fences and two pairs of stops, held
by its own weight (872.5 g). It is 110 mm deep and a bay is 100, so the
plate carries on past the bay's back and the kit's sockets stand behind it.
The latch fingers and their heads are cut out of that longer plate's two
edges, where the bay's side walls end.

The kit's sizes are NVIDIA's (Carrier Board Specification SP-10900-001
v1.1, figures 5-3 and 5-4): 110 x 110 x 71.65 mm.

x runs from the front, y across, z up."""
import sys

sys.argv[1:] = ["shelfduo"]
import build_shelf as s

s.DOC = "agx"
ROWS = 9  # rows of air slots in the face
for k in [k for k in s.P if k.startswith("strap.")] + ["back.clear"]:
    del s.P[k]
s.P.update({
    "bay.height": (124.2, "Inside the bay, floor to roof"),
    "air.step": (11.5, "Row of air slots to row: the lowest clears the label flat by 1.7"),
    "kit.width": (110, "The kit, across (NVIDIA's figure 5-3)"),
    "kit.depth": (110, "The kit, front to back (NVIDIA's figure 5-3)"),
    "kit.front": (8.5, "The kit's front from the tray's front: air from the face's slots passes between them"),
    "kit.slack": (0.5, "Between the kit and each fence or stop"),
    "fence.thick": (2, "Fences and stops"),
    "fence.height": (5, "Fences and the front stop: low, below the kit's vents"),
    "fence.front": (14, "Where the side fences start, from the front"),
    "fence.back": (96, "Where they end: short of the bay's back"),
    "stop.height": (4, "The two rear stops"),
    "stop.width": (15, "Each rear stop, across"),
    "tail.gap": (0.6, "Cut behind each finger's head, to free it from the plate that carries on"),
})
s.D.update({
    "plate.length": "kit.front + kit.depth + kit.slack + fence.thick",
    "side.lo": "mid - kit.width / 2 - kit.slack",
    "side.hi": "mid + kit.width / 2 + kit.slack",
    "front.stop": "kit.front - kit.slack",
    "back.stop": "kit.front + kit.depth + kit.slack",
})
s.V.clear()
s.V.update({k: float(x) for k, (x, _) in s.P.items()})
for k, e in s.D.items():
    s.V[k] = s.num(e, s.V)
shelf_cuts, shelf_features = s.cuts, s.features
L, WD = s.L, s.WD


def outline():
    """The plate: a plain outline. The fingers and their heads are cut out of it."""
    t = "nose.taper"
    return [(0, 0), (f"{L} - {t}", 0), (L, t), (L, f"{WD} - {t}"), (f"{L} - {t}", WD), (0, WD)]


def cuts():
    out = []
    for name, lo, hi in shelf_cuts():
        if name.startswith("strap."):
            continue
        if name.startswith("slot") and name.endswith("b"):  # the inner slot runs to the cut behind the head
            hi = ["finger.tip + tail.gap", hi[1], hi[2]]
        out.append((name, lo, hi))
    for k in range(2):
        # A gap before each head and a cut behind it, both open to the plate's edge.
        a, b = s.across(k, "-1", "finger.low")
        out.append((f"gap{k}", [s.B, a, "-1"], [f"{s.B} + head.gap", b, "plate.thickness + 1"]))
        a, b = s.across(k, "-1", "finger.high + finger.room")
        out.append((f"tail{k}", ["finger.tip", a, "-1"], ["finger.tip + tail.gap", b, "plate.thickness + 1"]))
    top = [c for c in out if c[0].startswith("air")]
    for r in range(1, ROWS):
        for name, lo, hi in top:
            out.append((f"{name}.row{r}", [lo[0], lo[1], f"{lo[2]} - {r} * air.step"],
                        [hi[0], hi[1], f"{hi[2]} - {r} * air.step"]))
    return out


def latch_cut_area():
    """Plate taken to free the two fingers: the slot outside each, the gap before its head, the slot
    inside it as far as its tip, and the cut behind its head."""
    v = s.V
    one = v["finger.slot"] * (v["latch.back"] - v["finger.root"]) + v["head.gap"] * v["finger.low"]
    one += v["finger.room"] * (v["finger.tip"] - v["finger.root"]) + v["tail.gap"] * (v["finger.high"] + v["finger.room"])
    return 2 * one


# Each: its name, its box on the plate (x0, y0, x1, y1) and its height.
RIBS = [
    ("fence.lo", ("fence.front", "side.lo - fence.thick", "fence.back", "side.lo"), "fence.height"),
    ("fence.hi", ("fence.front", "side.hi", "fence.back", "side.hi + fence.thick"), "fence.height"),
    ("stop.front", ("front.stop - fence.thick", "side.lo", "front.stop", "side.hi"), "fence.height"),
    ("stop.back.lo", ("back.stop", "side.lo", "back.stop + fence.thick", "side.lo + stop.width"), "stop.height"),
    ("stop.back.hi", ("back.stop", "side.hi - stop.width", "back.stop + fence.thick", "side.hi"), "stop.height"),
]


def features():
    f, last = shelf_features()
    for name, (x0, y0, x1, y1), height in RIBS:
        f.append(s.sketch(f"{name}.sketch", s.box(x0, y0, x1, y1), "rib", s.TOP))
        f.append({"id": name, "version": 1, "type": "boss", "target": s.ref(last, "body"),
                  "profile": s.ref(f"{name}.sketch", "rib"), "height": height})
        last = name
    return f, last


def expected_volume():
    v, t = s.V, s.V["plate.thickness"]
    n = lambda e: s.num(e, v)
    xy = [(n(x), n(y)) for x, y in outline()]
    area = abs(sum(a * d - c * b for (a, b), (c, d) in zip(xy, xy[1:] + xy[:1]))) / 2
    vol = (area - latch_cut_area()) * t
    front = v["plate.width"] * (v["front.height"] - t) - ROWS * s.SLOTS * v["slot.width"] * v["air.height"]
    vol += front * v["front.thickness"] - v["label.width"] * (v["label.high"] - v["label.low"]) * v["label.depth"]
    vol += s.pull_volume()
    vol += s.latch_volume()
    return vol + sum((n(x1) - n(x0)) * (n(y1) - n(y0)) * n(h) for _, (x0, y0, x1, y1), h in RIBS)


s.outline, s.cuts, s.features, s.expected_volume = outline, cuts, features, expected_volume
if __name__ == "__main__":
    s.main()
