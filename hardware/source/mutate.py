#!/usr/bin/env python3
"""Plants one defect at a time in a copy of the designs and asks whether the
checks notice. A defect the checks pass is a hole in the checks.

Each defect changes one number in one build script. The copy is rebuilt,
every part of it, and every check suite run on it; the defect counts as
caught if a build fails, or a suite reports a failure the unchanged designs
do not.

  python3 mutate.py            every defect
  python3 mutate.py --check    only that each defect still finds its number
  python3 mutate.py NAME ...   the named defects"""
import glob, json, os, re, shutil, subprocess, sys, tempfile
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
RW = __import__("os").environ.get("RINGWRIGHT", "ringwright")
# Every part: the script that builds it, and what the script is told.
BUILDS = {"cell": ("build_cell.py",), "carrier": ("build_carrier.py",), "base": ("build_base.py",), "basehalf": ("build_base.py", "basehalf"),
          **{d: ("build_trim.py", d) for d in ("trimtop", "trimrail", "trimlip", "trimtophalf")},
          **{d: ("build_bay.py", d) for d in ("bay", "baytall", "bayrack", "bayduo", "bayagx")},
          **{d: ("build_shelf.py", d) for d in ("shelf", "shelftall", "shelfrack")},
          "orin": ("build_orin.py",), "agx": ("build_agx.py",),
          **{d: ("build_spacer.py", d) for d in ("spacerrow", "spacercol", "spacercross")}}
SUITES = ["fit_check.py", "qc.py", "qc_carrier.py", "qc_base.py", "qc_trim.py", "qc_bay.py", "qc_spacer.py", "pi5_fit.py", "print_check.py", "qa.py"]


def number(param, value):
    """One parameter's number, where a script sets it as "name": (number, reason)."""
    return r'("' + re.escape(param) + r'": \()-?[0-9.]+', r"\g<1>" + repr(value)


def text(old, new):
    return re.escape(old), new.replace("\\", "\\\\")


# name: (script, (pattern, replacement), what it breaks)
DEFECTS = {
    "none": (None, None, "the designs as they are"),
    # The joint, which every sleeve, base and cap draws from the cell.
    "cell: no lift in the joint": ("build_cell.py", number("flange.height", 1.9), "flange as thick as the stem is tall"),
    "cell: stacking rail too narrow": ("build_cell.py", number("head.width", 7.8), "head barely wider than the opening: lets go off centre"),
    "cell: side rail too narrow": ("build_cell.py", number("side.head", 10), "lets go at the end of the side joint's play"),
    "cell: latch moved": ("build_cell.py", number("catch.from_front", 14), "teeth 4 mm from the base's notches"),
    "cell: teeth too short": ("build_cell.py", number("tooth.reach", 0.7), "teeth do not reach the stem: no latch"),
    "cell: side teeth too short": ("build_cell.py", number("side.tooth.reach", 1.0), "side teeth do not reach the stem: no latch"),
    "cell: ledges too low": ("build_cell.py", number("ledge.height", 1.7), "carrier's plate cannot pass under"),
    "cell: ledges cut back too far": ("build_cell.py", number("ledge.cut", 5.6), "carrier's face stands 3 mm inside the front"),
    "cell: walls too thin": ("build_cell.py", number("wall", 2), "inside 2 mm bigger each way than the carrier expects"),
    # The carrier.
    "carrier: plate too thick": ("build_carrier.py", number("plate.thickness", 2.4), "binds under the ledges"),
    "carrier: too wide": ("build_carrier.py", number("side.slack", -0.4), "wider than the cell's inside"),
    "carrier: fan too high": ("build_carrier.py", number("fan.low", 14), "fan and its cradle would strike the cell's roof"),
    "carrier: teeth too far forward": ("build_carrier.py", number("tooth.behind", -2.0), "teeth press on the side walls, short of their rear ends"),
    "carrier: posts too short": ("build_carrier.py", number("post.height", 1.5), "board 1.5 mm low: ports miss their window"),
    # The bases.
    "base: seat notches too shallow for the teeth": ("build_base.py", number("cell.reach", 0.2), "notches too narrow for a cell's teeth"),
    "base: cell seat moved": ("build_base.py", number("catch.from_front", 16), "notches 4 mm from where a cell's teeth rest"),
    "base: no play between bases": ("build_base.py", number("base.float", 0.2), "bases as made would not line up"),
    "base: rail head too wide": ("build_base.py", number("head.width", 14), "a cell's lips do not fit over it"),
    "half base: too wide": ("build_base.py", text('"basehalf": 31.7', '"basehalf": 33.7'), "2 mm wider than the column of spacers on it"),
    # The bays.
    "bay: places too far apart": ("build_bay.py", text('PITCH = c.P["body.width"][0] + c.P["gap"][0]', 'PITCH = c.P["body.width"][0] + c.P["gap"][0] + 0.6'),
                                  "its rails and lips are 0.6 mm further apart than the cells'"),
    "bay: rack roof too thin": ("build_bay.py", text('"bayrack": (4, 2, 12.0)', '"bayrack": (4, 2, 4.0)'), "a 279 mm span 4 mm thick under two rows"),
    "bay: Jetson roof changed": ("build_bay.py", text('"bayduo": (2, 2, 6.0)', '"bayduo": (2, 2, 9.0)'), "3 mm less room inside than its tray was made for"),
    # What slides into them.
    "shelf: too wide": ("build_shelf.py", number("side.slack", -0.6), "wider than the bay's inside"),
    "shelf: plate too thick": ("build_shelf.py", number("plate.thickness", 2.5), "binds under the bay's ledges"),
    "shelf: teeth too far forward": ("build_shelf.py", number("tooth.behind", -2.0), "teeth press on the side walls, short of their rear ends"),
    "shelf: made for a lower bay": ("build_shelf.py", text('"shelftall": (202.2, 74.6,', '"shelftall": (202.2, 70.6,'), "its face leaves 4 mm open under the roof"),
    "Jetson tray: holes too close": ("build_orin.py", number("hole.across", 86), "6 mm off NVIDIA's hole pattern"),
    "Jetson tray: posts too short": ("build_orin.py", number("post.height", 3), "the board's underside parts reach 4.3 mm"),
    "Jetson tray: board too far back": ("build_orin.py", number("board.back", 106), "the board's sockets stand out of the back of the bay"),
    "AGX tray: no room for the kit": ("build_agx.py", number("kit.slack", -0.5), "fences 1 mm closer together than the kit is wide"),
    "AGX tray: made for a lower bay": ("build_agx.py", number("bay.height", 120), "its face leaves 4 mm open under the roof"),
    "AGX tray: fences too thick": ("build_agx.py", number("fence.thick", 3.6), "each fence stands over the slot that frees a latch finger"),
    # The spacers.
    "column spacer: more than half": ("build_spacer.py", text('"spacercol": (0.5, 1,', '"spacercol": (0.55, 1,'), "two of them and their gaps are wider than a place"),
    "row spacer: more than half": ("build_spacer.py", text('"spacerrow": (1, 0.5,', '"spacerrow": (1, 0.6,'), "two of them and their gaps are higher than a row"),
    "cross: as deep as a cell": ("build_spacer.py", text('c.P["body.depth"] = (60,', 'c.P["body.depth"] = (100,'), "it closes the shaft and the tray where they meet"),
    "column spacer: shaft too short": ("build_spacer.py", text('c.P["shaft.depth"] = (40,', 'c.P["shaft.depth"] = (25,'), "the shaft does not line up with the cross behind it"),
    # The caps.
    "caps: plate too thin": ("build_trim.py", text("T = 2.0", "T = 0.6"), "a 0.6 mm plate: below what prints"),
}


def planted(name, root):
    """The named defect's script from root, with the defect in it."""
    script, (pattern, new), _ = DEFECTS[name]
    out, n = re.subn(pattern, new, open(os.path.join(root, script)).read())
    assert n == 1, f"{name}: its number was found {n} times in {script}"
    return script, out


def fails(text):
    return {line.split(":")[0][6:] for line in text.splitlines() if line.startswith("FAIL")}


def one(name):
    env = dict(os.environ, OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", QA_QUICK="1", RINGWRIGHT_VIEWER="/nowhere/ringwright-view",
               RINGWRIGHT_TIMEOUT_MS="300000")  # many copies build at once: none may fail for want of time
    with tempfile.TemporaryDirectory() as tmp:
        for f in glob.glob(os.path.join(HERE, "*.py")) + [os.path.join(HERE, "pi5.rwv")]:
            shutil.copy(f, tmp)
        if DEFECTS[name][0]:
            script, changed = planted(name, tmp)
            open(os.path.join(tmp, script), "w").write(changed)
        out = {"name": name, "build": None, "suites": {}}

        def build(item):
            doc, cmd = item
            run = subprocess.run([sys.executable, *cmd], cwd=tmp, capture_output=True, text=True, env=env)
            if run.returncode:
                return f"{doc} would not build: " + ((run.stdout + run.stderr).strip().splitlines() or ["no output"])[-1][:160]
            # The scene file is written before the viewer is looked for.
            subprocess.run([RW, "view", "--document", doc], cwd=tmp, capture_output=True, env=env)

        with ThreadPoolExecutor(max_workers=4) as pool:
            broken = [b for b in pool.map(build, BUILDS.items()) if b]
        if broken:
            out["build"] = broken[0] + (f" (+{len(broken) - 1})" if len(broken) > 1 else "")
            return out
        with ThreadPoolExecutor(max_workers=5) as pool:
            runs = list(pool.map(lambda s: subprocess.run([sys.executable, s], cwd=tmp, capture_output=True, text=True, env=env), SUITES))
        for suite, run in zip(SUITES, runs):
            found = fails(run.stdout)
            if suite == "fit_check.py" and run.returncode:
                found.add("the joint proof")
            if run.returncode and not found:
                found.add("suite stopped: " + ((run.stderr.strip().splitlines() or ["no message"])[-1][:100]))
            out["suites"][suite] = sorted(found)
        return out


def main():
    args = sys.argv[1:]
    if args[:1] == ["--check"]:
        for name in DEFECTS:
            if DEFECTS[name][0]:
                planted(name, HERE)
        print(f"each of the {len(DEFECTS) - 1} defects finds its number exactly once")
        return
    names = args or list(DEFECTS)
    if "none" not in names:
        names = ["none"] + names
    # Every copy asks one serving Ringwright, which builds each different part once and
    # runs no more workers than the machine has cores. One already named is used as it is.
    server = None
    if not os.environ.get("RINGWRIGHT_SERVER"):
        socket = os.path.join(tempfile.mkdtemp(), "ringwright.sock")
        server = subprocess.Popen([RW, "serve", "--socket", socket], stdout=subprocess.PIPE, text=True)
        server.stdout.readline()  # it says one line when it is listening
        os.environ["RINGWRIGHT_SERVER"] = socket
    try:
        with ThreadPoolExecutor(max_workers=12) as pool:
            got = {r["name"]: r for r in pool.map(one, names)}
    finally:
        if server:
            said = subprocess.run([RW, "serve", "--stats"], capture_output=True, text=True).stdout
            subprocess.run([RW, "serve", "--stop"], capture_output=True)
            server.wait(timeout=180)
            did = json.loads(said)["result"]
            print(f"one Ringwright served {did['jobs_done']} jobs: {did['built']} builds, {did['cache_hits'] + did['joined']} answered from builds already made")
    base = got["none"]
    assert base["build"] is None, base
    dirty = {s: f for s, f in base["suites"].items() if f}
    print(f"unchanged designs: {'every suite passes' if not dirty else 'failing already: ' + json.dumps(dirty)}")
    caught = 0
    for name in names:
        if name == "none":
            continue
        r, why = got[name], []
        if r["build"]:
            why.append(r["build"])
        for suite, found in r["suites"].items():
            new = [f for f in found if f not in base["suites"][suite]]
            if new:
                why.append(f"{suite}: " + "; ".join(new[:2]) + (f" (+{len(new) - 2})" if len(new) > 2 else ""))
        caught += bool(why)
        print(f"{'CAUGHT' if why else 'MISSED':7} {name}  [{DEFECTS[name][2]}]")
        for w in why[:3]:
            print(f"          {w[:170]}")
    total = len(names) - 1
    print(f"\n{caught} of {total} planted defects caught")
    json.dump(got, open(os.path.join(HERE, "mutation-results.json"), "w"), indent=1)
    sys.exit(0 if caught == total and not dirty else 1)


main()
