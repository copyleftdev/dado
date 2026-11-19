"""Part against part, asked of Ringwright: each question is one interference
check of `ringwright assemble`, and many are sent in one call, so every part
is built once.

A question is a Case: a fixed part, a moved part, and optionally a box to
look in and boxes to leave out (a sprung latch is meant to press on what it
rides). The answer is how many sampled points of either part are inside the
other, counted and left out, and how deep the deepest counted one is."""
import json, subprocess
from dataclasses import dataclass, field

RW = __import__("os").environ.get("RINGWRIGHT", "ringwright")
FAR = 1e6  # a box's side that is meant to have no end
# These scripts stand seated parts a hair apart themselves (0.02 mm), so that touching is not
# counted; anything inside at all is then a collision, as it was when they counted points by hand.
TOUCHING = 1e-6
CASES_PER_CALL = 60  # an assembly carries at most 64 checks


def box(x=(-FAR, FAR), y=(-FAR, FAR), z=(-FAR, FAR)):
    return {"min": [x[0], y[0], z[0]], "max": [x[1], y[1], z[1]]}


@dataclass(frozen=True)
class Placed:
    """A document, turned about the frame's axes in order and then moved."""
    doc: str
    move: tuple = (0.0, 0.0, 0.0)
    turns: tuple = ()  # of (axis, degrees)


@dataclass
class Case:
    fixed: Placed
    moved: Placed
    within: dict = None
    ignoring: list = field(default_factory=list)


@dataclass
class Found:
    points: int  # counted
    ignored: int  # inside, but in a box left out
    depth: float


def _ask(cases):
    names, parts, checks = {}, [], []
    for case in cases:
        pair = []
        for placed in (case.fixed, case.moved):
            if placed not in names:
                names[placed] = f"p{len(names)}"
                parts.append({"name": names[placed], "document": placed.doc, "move": [float(v) for v in placed.move],
                              "turns": [{"about": a, "degrees": d} for a, d in placed.turns]})
            pair.append(names[placed])
        check = {"kind": "interference", "between": pair, "unit": "mm", "ignoring": case.ignoring, "touching_within": TOUCHING}
        if case.within:
            check["within"] = case.within
        checks.append(check)
    spec = {"schema_version": 1, "name": "fit", "unit": "mm", "parts": parts, "checks": checks}
    out = json.loads(subprocess.run([RW, "assemble", "-"], input=json.dumps(spec), capture_output=True, text=True).stdout)
    if not out["ok"]:
        raise SystemExit("ringwright assemble: " + json.dumps(out["failure"])[:2000])
    found = []
    for check in out["result"]["checks"]:
        pairs = check["evidence"]["overlapping"]
        found.append(Found(sum(p["points_inside"] for p in pairs), sum(p["points_ignored"] for p in pairs), check["evidence"]["measured"]))
    return found


def overlaps(cases):
    """What each case finds, in order."""
    cases, found = list(cases), []
    for at in range(0, len(cases), CASES_PER_CALL):
        found += _ask(cases[at:at + CASES_PER_CALL])
    return found


_known = {}


def _key(a, at_a, b, at_b):
    spot = lambda at: tuple(round(float(v), 9) for v in at)
    return (a, spot(at_a), b, spot(at_b))


def ahead(pairs):
    """Asks about many pairs of parts in one call, so that `clash` finds the answers ready.
    Each pair is (part, where, other part, where)."""
    new = [p for p in dict.fromkeys(_key(*p) for p in pairs) if p not in _known]
    for key, found in zip(new, overlaps(Case(Placed(a, at_a), Placed(b, at_b)) for a, at_a, b, at_b in new)):
        _known[key] = found.points


def clash(a, at_a, b, at_b):
    """Sampled points of each part inside the other."""
    key = _key(a, at_a, b, at_b)
    if key not in _known:
        ahead([(a, at_a, b, at_b)])
    return _known[key]
