#!/usr/bin/env python3
"""Writes the film's meshes from the CAD: every part in one cell's frame
(x across, y front to back, z up, millimetres), as small binary files, with
a manifest of the dimensions the film needs. Run from pi-cell."""
import json, struct, subprocess, sys
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

RW = __import__("os").environ.get("RINGWRIGHT", "ringwright")
OUT = "brand/film/assets"


def params(doc):
    out = subprocess.run([RW, "inspect", doc], capture_output=True, text=True).stdout
    return {p["id"]: p["value"] for p in json.loads(out)["result"]["parameters"]}


def read(path):
    b = open(path, "rb").read()
    at = 8
    (k,) = struct.unpack_from("<I", b, at); at += 4 + k
    (k,) = struct.unpack_from("<I", b, at); at += 4
    pos = np.frombuffer(b, "<f4", k * 3, at).reshape(-1, 3).astype(float); at += k * 12
    (k,) = struct.unpack_from("<I", b, at); at += 4
    tri = np.frombuffer(b, "<u4", k * 3, at).reshape(-1, 3).astype(np.int64); at += k * 12
    (k,) = struct.unpack_from("<I", b, at); at += 4
    edges = []
    for _ in range(k):
        (m,) = struct.unpack_from("<I", b, at); at += 4
        edges.append(np.frombuffer(b, "<f4", m * 3, at).reshape(-1, 3).astype(float)); at += m * 12
    return pos, tri, edges


def segments(edges):
    out = [np.stack([e[:-1], e[1:]], 1).reshape(-1, 3) for e in edges if len(e) > 1]
    return np.vstack(out) if out else np.zeros((0, 3))


def write(name, pos, tri, seg, colour=None):
    """u32 vertices, triangles, segment points, has-colour; then f32 positions,
    u8 rgba colours if any, u32 indices, f32 segment points."""
    used = np.unique(tri)
    remap = np.full(len(pos), -1); remap[used] = np.arange(len(used))
    pos, tri = pos[used], remap[tri]
    with open(f"{OUT}/{name}.bin", "wb") as f:
        f.write(struct.pack("<4I", len(pos), len(tri), len(seg), 0 if colour is None else 1))
        f.write(pos.astype("<f4").tobytes())
        if colour is not None:
            f.write(colour[used].astype("u1").tobytes())
        f.write(tri.astype("<u4").tobytes())
        f.write(seg.astype("<f4").tobytes())
    return {"vertices": len(pos), "triangles": len(tri), "lo": pos.min(0).round(3).tolist(),
            "hi": pos.max(0).round(3).tolist()}


cell, base, car = params("cell"), params("base"), params("carrier")
w = cell["wall"]
BOTTOM = json.load(open("pi5-seat.json"))["bottom"]
on_carrier = lambda p: np.stack([car["board.front"] + p[:, 0], car["margin"] + p[:, 1],
                                 car["plate.thickness"] + car["post.height"] + p[:, 2] - BOTTOM], 1)
in_cell = lambda p: np.stack([-(w + 0.25 + p[:, 1]), p[:, 0], w + p[:, 2]], 1)

manifest = {"parts": {}, "pitch": [cell["body.width"] + cell["gap"], cell["body.height"] + cell["gap"]],
            "cell": [cell["body.width"], cell["body.depth"] if "body.depth" in cell else 100.0, cell["body.height"]],
            "gap": cell["gap"], "wall": w, "base_rise": base["base.height"] + base["gap"], "trim": 2.0}

for doc in ("cell", "base", "trimtop", "trimrail", "trimlip", "bay", "baytall", "bayrack", "bayduo", "bayagx",
            "spacerrow", "spacercol", "spacercross", "basehalf", "trimtophalf"):
    pos, tri, edges = read(f".ringwright/{doc}/view/scene.rwv")
    manifest["parts"][doc] = write(doc, pos, tri, segments(edges))
    if doc == "cell":
        # The section, as closed loops: the kernel's own edges on the back face.
        back = pos[:, 1].max()
        flat = [e for e in edges if len(e) > 1 and np.all(np.abs(e[:, 1] - back) < 1e-4)]
        loops = []
        while flat:
            loop = flat.pop(0)
            grew = True
            while grew and np.linalg.norm(loop[0] - loop[-1]) > 1e-3:
                grew = False
                for i, e in enumerate(flat):
                    if np.linalg.norm(e[0] - loop[-1]) < 1e-3:
                        loop = np.vstack([loop, e[1:]]); flat.pop(i); grew = True; break
                    if np.linalg.norm(e[-1] - loop[-1]) < 1e-3:
                        loop = np.vstack([loop, e[::-1][1:]]); flat.pop(i); grew = True; break
            loops.append(loop)
        loops.sort(key=lambda l: -len(l))
        manifest["section"] = [np.round(l[:, [0, 2]], 3).tolist() for l in loops]
        print("section loops", [len(l) for l in loops], "closed",
              [bool(np.linalg.norm(l[0] - l[-1]) < 1e-3) for l in loops])

pos, tri, edges = read(".ringwright/carrier/view/scene.rwv")
manifest["parts"]["carrier"] = write("carrier", in_cell(pos), tri, in_cell(segments(edges)))
for doc in ("shelf", "shelftall", "shelfrack", "orin", "agx"):
    pos, tri, edges = read(f".ringwright/{doc}/view/scene.rwv")
    manifest["parts"][doc] = write(doc, in_cell(pos), tri, in_cell(segments(edges)))

# The Pi: Raspberry Pi's model, split into its separate bodies and coloured by
# what each body evidently is. The model carries no colours of its own.
pos, tri, _ = read("pi5.rwv")
key = np.round(pos * 500).astype(np.int64)
_, weld = np.unique(key, axis=0, return_inverse=True)
weld = weld.ravel()
t = weld[tri]
n = weld.max() + 1
graph = coo_matrix((np.ones(len(t) * 2), (np.r_[t[:, 0], t[:, 1]], np.r_[t[:, 1], t[:, 2]])), shape=(n, n))
count, label = connected_components(graph, directed=False)
body = label[weld]                      # per vertex
lo = np.full((count, 3), np.inf); hi = np.full((count, 3), -np.inf)
np.minimum.at(lo, body, pos); np.maximum.at(hi, body, pos)
size = hi - lo
TOP = 1.34
PCB, METAL, DARK, GOLD, WHITE = (38, 112, 70), (176, 180, 184), (30, 31, 34), (196, 160, 84), (222, 220, 212)
tone = np.zeros((count, 3))
kind = []
for i in range(count):
    sx, sy, sz = size[i]
    if sx > 80 and sy > 50:
        c, k = PCB, "board"
    elif hi[i, 2] > 9 and sx * sy > 100:
        c, k = METAL, "port"            # USB and Ethernet shells
    elif max(sx, sy) < 1.2 and sz > 4:
        c, k = GOLD, "pin"
    elif 2.4 < hi[i, 2] - TOP < 9 and sx * sy > 30 and (lo[i, 1] < 1.0 or hi[i, 1] > 55.0 or lo[i, 0] < 1.0):
        c, k = METAL, "edge connector"
    elif 10 < sx < 20 and 10 < sy < 20 and hi[i, 2] - TOP < 3 and lo[i, 2] > 0:
        c, k = METAL, "lid"
    elif lo[i, 2] >= TOP - 0.05 and sz < 0.08:
        c, k = WHITE, "marking"
    else:
        c, k = DARK, "part"
    tone[i] = c; kind.append(k)
print("pi bodies", count, {k: kind.count(k) for k in set(kind)})
rgba = np.concatenate([tone[body], np.full((len(pos), 1), 255)], 1)
placed = in_cell(on_carrier(pos))
diag = np.linalg.norm(size, axis=1)
board = np.array([k == "board" for k in kind])
for name, least in (("pi", float(sys.argv[1]) if len(sys.argv) > 1 else 2.0), ("pi-far", 12.0)):
    keep = (diag >= least) | board
    chosen = tri[keep[body[tri[:, 0]]]]
    manifest["parts"][name] = write(name, placed, chosen, np.zeros((0, 3)), rgba)
    print(name, "bodies kept", int(keep.sum()), manifest["parts"][name]["triangles"], "triangles")

# A third Pi, for a wall: every body at least 5 mm across as the box it fills, in its own colour. Behind a closed
# face, seen through five slots from across a wall, that is all the eye can tell, at a hundredth of the triangles.
FACES = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]  # corner = x + 2y + 4z, wound outward
box_pos, box_tri, box_rgba = [], [], []
for i in np.flatnonzero((diag >= 5.0) | board):
    corners = np.array([[(lo[i], hi[i])[(c >> a) & 1][a] for a in range(3)] for c in range(8)])
    for quad in FACES:  # four corners of its own a face, so each face is shaded flat
        at = len(box_pos)
        box_pos += [corners[c] for c in quad]
        box_tri += [(at, at + 1, at + 2), (at, at + 2, at + 3)]
        box_rgba += [np.r_[tone[i], 255]] * 4
box_pos = np.array(box_pos)
manifest["parts"]["pi-lite"] = write("pi-lite", in_cell(on_carrier(box_pos)), np.array(box_tri), np.zeros((0, 3)), np.array(box_rgba))
print("pi-lite", "bodies kept", int(((diag >= 5.0) | board).sum()), manifest["parts"]["pi-lite"]["triangles"], "triangles")

json.dump(manifest, open(f"{OUT}/manifest.json", "w"))
for k, v in manifest["parts"].items():
    print(f"{k:9s} {v['triangles']:7d} tris  {v['lo']} to {v['hi']}")
print({k: v for k, v in manifest.items() if k not in ("parts", "section")})
