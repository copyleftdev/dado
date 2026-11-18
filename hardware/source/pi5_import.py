#!/usr/bin/env python3
"""Imports Raspberry Pi's own STEP model of the Pi 5 through Ringwright's
geometry worker, and writes its mesh and edges as a scene file.

The model is MIT licensed (specs/pi5-step/LICENSE.txt). Raspberry Pi provide
it "for guidance only and without guarantee of accuracy"."""
import json, struct, subprocess, sys, time
import numpy as np

RW = __import__("os").environ.get("RINGWRIGHT", "ringwright")
SRC = "specs/pi5-step/rpi-5b_no_graphics.step"

step = open(SRC).read()
request = {"plan": {"ops": [{"op": "import_step", "feature": "pi5", "step": step}]},
           "tolerance": {"linear": 1e-6, "angular": 1e-9}, "chord_tolerance": 0.05,
           "want_step": False, "timestamp": ""}
start = time.time()
run = subprocess.run([RW, "__worker", "occt"], input=json.dumps(request).encode(), capture_output=True)
raw = run.stdout
reply = json.loads(raw[raw.index(b"{"):])
print(f"worker exit {run.returncode} after {time.time() - start:.0f} s; reply keys {list(reply)[:3]}")
body = reply.get("Ok") or reply.get("ok") or reply
if "mesh" not in body:
    sys.exit(json.dumps(reply)[:1500])
pos = np.array(body["mesh"]["positions"], dtype="<f4")
tri = np.array(body["mesh"]["triangles"], dtype="<u4")
edges = [np.array(e["points"], dtype="<f4") for e in body["edges"]]
print(f"solids {body['solids']}, faces {body['faces']}, kernel says valid: {body['kernel_valid']}, "
      f"triangles {len(tri):,}, edges {len(edges):,}")
print("extent", pos.min(0).round(3).tolist(), "to", pos.max(0).round(3).tolist())
print("notes", body.get("diagnostics"))
title = b"Raspberry Pi 5"
with open("pi5.rwv", "wb") as f:
    f.write(b"RWVIEW02" + struct.pack("<I", len(title)) + title)
    f.write(struct.pack("<I", len(pos)) + pos.tobytes() + struct.pack("<I", len(tri)) + tri.tobytes())
    f.write(struct.pack("<I", len(edges)))
    for e in edges:
        f.write(struct.pack("<I", len(e)) + e.tobytes())
    f.write(struct.pack("<I", 0))
