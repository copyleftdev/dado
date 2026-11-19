#!/usr/bin/env python3
"""What every part must measure before it is committed, beyond its volume:
its overall size, worked out by hand from its own sketch, and its thinnest
wall. The engine measures both on the body the kernel built and refuses the
commit if either is out."""


def spans(points, num, values):
    """How far a sketch's outline reaches each way: (across, up)."""
    us = [num(u, values) for u, _ in points]
    vs = [num(v, values) for _, v in points]
    return max(us) - min(us), max(vs) - min(vs)


def measures(body, size, floor):
    """`size`: the part along x, y and z, by hand, held to a hundredth.
    `floor`: the thinnest wall allowed."""
    checks = [{"kind": "extent", "body": body, "axis": axis, "at_least": round(s - 0.01, 6),
               "at_most": round(s + 0.01, 6), "unit": "mm"} for axis, s in zip("xyz", size)]
    return checks + [{"kind": "min_thickness", "body": body, "at_least": floor, "unit": "mm"}]
