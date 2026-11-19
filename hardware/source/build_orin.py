#!/usr/bin/env python3
"""Builds the Orin tray: what an NVIDIA Jetson Orin Nano developer kit's
board is screwed to before it goes into the two-by-two bay (bayduo).

It is the shelf for that bay, with the strap slots left out, four posts
under the board's mounting holes, and five rows of air slots in the face
where a shelf has one: the board can draw about 25 W.

The board goes on without the plastic stand it ships on, cooler up, its
edge of sockets at the bay's open back. Its sizes are NVIDIA's own:
  outline 100 x 79 mm, 1.57 thick, parts up to 4.30 below it
      (Carrier Board Specification SP-11324-001 v1.3, figure 4-1)
  the whole kit on its stand, 34.77 +/- 1.09 mm tall (figure 4-2)
  four 2.75 mm holes, 92 x 58 apart, 4 mm in from each side and from the
      edge opposite the sockets, 17 mm in from the socket edge
      (drill file of the P3768 A04 reference design)

x runs from the front, y across, z up."""
import math, sys

sys.argv[1:] = ["shelfduo"]
import build_shelf as s

s.DOC = "orin"
ROWS = 5  # rows of air slots in the face
for k in [k for k in s.P if k.startswith("strap.")]:
    del s.P[k]
s.P.update({
    "air.step": (11.5, "Row of air slots to row: the lowest clears the label flat by 2.1"),
    "board.back": (96, "The board's edge of sockets, from the tray's front: they end inside the bay"),
    "hole.back": (17, "Mounting holes from the board's socket edge (NVIDIA's drill file)"),
    "hole.along": (58, "Mounting holes, front to back (NVIDIA's drill file)"),
    "hole.across": (92, "Mounting holes, across (NVIDIA's drill file)"),
    "post.diameter": (7, "Posts the board rests on"),
    "post.height": (6, "Room under the board: its parts reach 4.30 below it"),
    "pilot": (2.1, "Pilot hole for an M2.5 thread-forming screw, the depth of the post"),
})
s.D.update({"post.x": "board.back - hole.back - hole.along", "post.y": "mid - hole.across / 2"})
s.V.clear()
s.V.update({k: float(x) for k, (x, _) in s.P.items()})
for k, e in s.D.items():
    s.V[k] = s.num(e, s.V)
shelf_cuts, shelf_features = s.cuts, s.features
POSTS = {"origin": [0, 0, "plate.thickness + post.height"], "x": [1, 0, 0], "y": [0, 1, 0]}


def cuts():
    out = [c for c in shelf_cuts() if not c[0].startswith("strap.")]
    top = [c for c in out if c[0].startswith("air")]
    for r in range(1, ROWS):
        for name, lo, hi in top:
            out.append((f"{name}.row{r}", [lo[0], lo[1], f"{lo[2]} - {r} * air.step"],
                        [hi[0], hi[1], f"{hi[2]} - {r} * air.step"]))
    return out


def circle(fid, cx, cy, r):
    f = s.sketch(fid, [(f"{cx} + {r}", cy), (f"{cx} - ({r})", cy), (cx, cy)], "c", s.TOP)
    f["profiles"] = {"round": ["c0", "c1"]}
    f["arcs"] = [{"from": "c0", "to": "c1", "center": "c2"}, {"from": "c1", "to": "c0", "center": "c2"}]
    return f


def features():
    f, last = shelf_features()
    for row, x in (("front", "post.x"), ("back", "post.x + hole.along")):
        f.append(circle(f"post.{row}.sketch", x, "post.y", "post.diameter / 2"))
        f.append({"id": f"post.{row}", "version": 1, "type": "boss", "target": s.ref(last, "body"),
                  "profile": s.ref(f"post.{row}.sketch", "round"), "height": "post.height"})
        f.append({"id": f"post.{row}.pair", "version": 1, "type": "pattern",
                  "target": s.ref(f"post.{row}", "body"), "of": s.ref(f"post.{row}", "body"),
                  "layout": {"kind": "linear", "dx": 0, "dy": "hole.across", "count": 2}})
        last = f"post.{row}.pair"
    holes = s.sketch("pilots.sketch", s.box("post.x", "post.y", "post.x + hole.along", "post.y + hole.across"), "pilots", POSTS)
    holes["point_sets"], holes["profiles"] = holes["profiles"], {}
    f.append(holes)
    f.append({"id": "pilots", "version": 1, "type": "hole_pattern", "target": s.ref(last, "body"),
              "centers": s.ref("pilots.sketch", "pilots", 4), "diameter": "pilot", "depth": "post.height"})
    return f, "pilots"


def expected_volume():
    v, t = s.V, s.V["plate.thickness"]
    xy = [(s.num(x, v), s.num(y, v)) for x, y in s.outline()]
    area = abs(sum(a * d - c * b for (a, b), (c, d) in zip(xy, xy[1:] + xy[:1]))) / 2
    vol = (area - s.latch_cut_area()) * t
    front = v["plate.width"] * (v["front.height"] - t) - ROWS * s.SLOTS * v["slot.width"] * v["air.height"]
    vol += front * v["front.thickness"] - v["label.width"] * (v["label.high"] - v["label.low"]) * v["label.depth"]
    vol += (v["plate.width"] - 2 * v["pull.inset"]) * (v["top.bar"] * v["pull.reach"] + 1.5 * v["pull.lip"])
    return vol + s.latch_volume() + 4 * math.pi * ((v["post.diameter"] / 2) ** 2 - (v["pilot"] / 2) ** 2) * v["post.height"]


s.cuts, s.features, s.expected_volume = cuts, features, expected_volume
if __name__ == "__main__":
    s.main()
