"""What the quality-control scripts share: reading the viewer's scene files,
casting rays at meshes, and the checks any part gets."""
import json, math, struct, subprocess, sys
import numpy as np

results = []


def kernel_volume(doc):
    """What the kernel says the committed body's volume is."""
    rw = __import__("os").environ.get("RINGWRIGHT", "ringwright")
    head = json.loads(subprocess.run([rw, "inspect", doc], capture_output=True, text=True).stdout)
    tx = {"schema_version": 1, "document": doc, "base_revision": head["result"]["revision"],
          "operations": [], "checks": []}
    out = subprocess.run([rw, "dry-run", "--brief", "-"], input=json.dumps(tx),
                         capture_output=True, text=True).stdout
    return json.loads(out)["result"]["measurements"]["body"]["kernel_volume"]


def report(verdict, name, detail):
    results.append(verdict)
    print(f"{verdict:4}  {name}: {detail}")


def scene(path):
    b = open(path, "rb").read()
    at = 8
    (n,) = struct.unpack_from("<I", b, at); at += 4 + n
    (n,) = struct.unpack_from("<I", b, at); at += 4
    pos = np.frombuffer(b, "<f4", n * 3, at).reshape(-1, 3).astype(float); at += n * 12
    (n,) = struct.unpack_from("<I", b, at); at += 4
    return pos, np.frombuffer(b, "<u4", n * 3, at).reshape(-1, 3).astype(int)


def ray_hits(origins, dirs, pos, tri):
    """Distance from each origin along its direction to the nearest triangle."""
    a = pos[tri[:, 0]]; e1 = pos[tri[:, 1]] - a; e2 = pos[tri[:, 2]] - a
    out = np.full(len(origins), np.inf)
    for k, (o, d) in enumerate(zip(origins, dirs)):
        p = np.cross(d, e2); det = (e1 * p).sum(1)
        ok = np.abs(det) > 1e-12
        s = o - a
        u = np.where(ok, (s * p).sum(1) / np.where(ok, det, 1), -1)
        q = np.cross(s, e1)
        v = np.where(ok, (q @ d) / np.where(ok, det, 1), -1)
        t = np.where(ok, (e2 * q).sum(1) / np.where(ok, det, 1), -1)
        hit = (u >= -1e-9) & (v >= -1e-9) & (u + v <= 1 + 1e-9) & (t > 1e-6)
        if hit.any():
            out[k] = t[hit].min()
    return out


def inside(points, pos, tri):
    d = np.array([0.5377, 0.3183, 0.7809]); d /= np.linalg.norm(d)
    a = pos[tri[:, 0]]; e1 = pos[tri[:, 1]] - a; e2 = pos[tri[:, 2]] - a
    p = np.cross(d, e2); det = (e1 * p).sum(1)
    out = np.zeros(len(points), bool)
    for k, o in enumerate(points):
        s = o - a
        u = (s * p).sum(1) / det
        q = np.cross(s, e1)
        v = (q @ d) / det
        t = (e2 * q).sum(1) / det
        out[k] = ((u >= 0) & (v >= 0) & (u + v <= 1) & (t > 1e-9)).sum() % 2 == 1
    return out


def integrity(name, pos, tri, kernel_volume):
    """Closed, consistently wound, and the volume the kernel reported."""
    _, weld = np.unique(np.round(pos, 4), axis=0, return_inverse=True)
    t = weld[tri]
    edges = np.vstack([t[:, [0, 1]], t[:, [1, 2]], t[:, [2, 0]]])
    key = lambda e: e[:, 0].astype(np.int64) * 10_000_000 + e[:, 1]
    forward, backward = key(edges), key(edges[:, ::-1])
    paired = np.isin(forward, backward).all() and len(np.unique(forward)) == len(forward)
    report("PASS" if paired else "FAIL", f"{name} mesh is closed and consistently wound",
           f"{len(tri)} triangles, every edge used once each way: {bool(paired)}")
    p = pos[tri]
    vol = (p[:, 0] * np.cross(p[:, 1], p[:, 2])).sum() / 6
    off = abs(vol - kernel_volume) / kernel_volume
    report("PASS" if off < 2e-3 else "FAIL", f"{name} mesh volume against the kernel's",
           f"mesh {vol:.1f} mm3, kernel {kernel_volume:.1f} mm3, {off * 100:.3f}% apart")
    return vol


def thickness(name, pos, tri, floor):
    """Material thickness behind every face: from each triangle's centre,
    straight in, to the far surface."""
    p = pos[tri]
    n = np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0])
    area = np.linalg.norm(n, axis=1)
    keep = area > 1e-9
    c, n = p.mean(1)[keep], n[keep] / area[keep][:, None]
    t = ray_hits(c - n * 1e-4, -n, pos, tri)
    t = t[np.isfinite(t)]
    thin = np.sort(np.unique(np.round(t, 2)))[:6]
    report("PASS" if t.min() >= floor - 0.02 else "FAIL", f"{name} thinnest section",
           f"{t.min():.2f} mm (floor for this check {floor} mm); thinnest values found {thin.tolist()}")
    return t


