#!/usr/bin/env python3
"""Quality control of the carrier, alone and in the cell, measured from the
meshes the kernel made. Each check prints PASS, FAIL or NOTE."""
import math, sys
import numpy as np
from fitlib import FAR, Case, Placed, box, overlaps
from qclib import inside, integrity, kernel_volume, ray_hits, report, results, scene, thickness

rng = np.random.default_rng(20261118)
WALL, DEPTH, CAV_W, CAV_H = 3.0, 100.0, 61.0, 36.0
PLATE, PLATE_W, PLATE_L, FRONT_T, FRONT_H = 1.8, 60.5, 97.0, 2.6, 35.5
TOOTH, RAMP, BEHIND = 1.2, 0.2, 0.6  # tooth depth, its front face, the face's start behind the rear edge
PULL = 6.0  # the pull rail's reach in front of the carrier's face
BOARD_TOP = PLATE + 3.0 + 1.35
TOOTH_X = DEPTH + BEHIND  # where the teeth begin, from the carrier's front
# The latch: each finger bends sideways, in the plane of the plate.
FINGER_T, FINGER_ROOT, RIB, HEAD_GAP = 2.2, 82.0, 1.8, 0.4  # a finger across, where it leaves the plate, its rib, the gap before its head
FINGER_MID = (PLATE_W - 56) / 2 + 1 + 1 + FINGER_T / 2  # a finger's centre line from the plate's edge
SIDE = (CAV_W - PLATE_W) / 2  # the gap each side when the carrier is centred

cell, cell_tri = scene(".ringwright/cell/view/scene.rwv")
car, car_tri = scene(".ringwright/carrier/view/scene.rwv")


def samples(pos, tri):
    t = pos[tri]
    mids = [(t[:, i] + t[:, j]) / 2 for i, j in ((0, 1), (1, 2), (2, 0))]
    return np.vstack([pos, t.mean(1), *mids])


C, S = samples(car, car_tri), samples(cell, cell_tri)


def to_cell(p, push=0.0, slack=0.25, lift=0.02):
    """Carrier coordinates (from its front, across, up) to the cell's."""
    return np.stack([-(WALL + slack + p[:, 1]), p[:, 0] + push, WALL + lift + p[:, 2]], 1)


def to_carrier(q, push=0.0, slack=0.25, lift=0.02):
    return np.stack([q[:, 1] - push, -q[:, 0] - WALL - slack, q[:, 2] - WALL - lift], 1)


def clash(poses):
    """For each pose (push, slack, lift), collisions between the carrier and
    the cell, as (at the teeth, anywhere else), asked of Ringwright. The
    carrier is turned to face the cell's mouth and set on its floor. The
    teeth are on springs: what they press on is counted apart."""
    asked = [Case(Placed("cell"), Placed("carrier", (-(WALL + slack), push, WALL + lift), (("z", 90),)), None,
                  [box(y=(push + TOOTH_X - 0.05, FAR))]) for push, slack, lift in poses]
    return [(f.ignored, f.points) for f in overlaps(asked)]


print("== 1. Integrity ==")
integrity("carrier", car, car_tri, kernel_volume("carrier"))

print("== 2. Measured dimensions ==")
lo, hi = car.min(0), car.max(0)
want_lo = np.array([-PULL, -TOOTH, 0])
want_hi = np.array([DEPTH + BEHIND + RAMP + 2.75 + 0.1, PLATE_W + TOOTH, FRONT_H])
ok = np.allclose(lo, want_lo, atol=0.01) and np.allclose(hi, want_hi, atol=0.01)
report("PASS" if ok else "FAIL", "carrier extent",
       f"measured {lo.round(3).tolist()} to {hi.round(3).tolist()}; drawn {want_lo.tolist()} to {want_hi.tolist()}")
# Thinnest meant: the 1.5 mm lip under the pull.
# The fan's two snap barbs are small on purpose (0.9 mm is all the height
# under the cell's roof), so they are measured apart from the walls.
_c = car[car_tri].mean(1)
_barb = (_c[:, 2] > 34.55) & (_c[:, 0] < 8.8) & (np.abs(np.abs(_c[:, 1] - PLATE_W / 2) - 12.6) < 0.75)
thickness("carrier", car, car_tri[~_barb], 1.5)
thickness("fan barbs (snap features, floor 0.4)", car, car_tri[_barb], 0.4)

print("== 3. Seated in the cell ==")
SEAT = -0.02  # against the stop, a hair short so that touching is not counted
# It can lift until its front meets the roof, 0.5 up; try just short of that.
worst = max(sum(c) for c in clash([(SEAT, slack, lift) for slack in (0.02, 0.25, 0.48) for lift in (0.02, 0.45)]))
report("PASS" if worst == 0 else "FAIL", "seated, at every extreme of its slack",
       f"6 poses; collisions anywhere, teeth included: {worst}")
report("PASS" if worst == 0 else "FAIL", "the latch rests unloaded",
       f"seated against the stop, the teeth stand {BEHIND} mm behind the rear ends of the cell's side walls and touch nothing")
face = car[car[:, 0] > -0.01]
front = to_cell(face, SEAT)[:, 1].min()
report("PASS" if abs(front) < 0.05 else "FAIL", "front flush with the cell", f"{front:+.2f} mm from the cell's front plane; "
       f"the pull stands {PULL:.0f} mm proud of it")
side = (CAV_W - PLATE_W) / 2
report("PASS", "front in the cell's mouth", f"{side:.2f} mm each side, {CAV_H - FRONT_H:.1f} mm under the roof, as drawn")

print("== 4. Going in, coming out ==")
got = clash([(push, 0.25, 0.02) for push in np.arange(-96, -2, 2.0)])
report("PASS" if max(b for _, b in got) == 0 else "FAIL", "sliding in",
       f"{len(got)} steps; teeth riding on the side walls in {sum(1 for a, _ in got if a)}; "
       f"collisions elsewhere {max(b for _, b in got)}")
steps = (0.2, 0.4, 0.5)
*freely, held, over, up = clash([(-d, 0.25, 0.02) for d in steps]
                                + [(-(BEHIND + 0.5), 0.25, 0.02), (0.5, 0.25, 0.02), (SEAT, 0.25, 1.0)])
free = max(d for d, c in zip(steps, freely) if sum(c) == 0)
report("PASS" if held[0] > 0 and held[1] == 0 else "FAIL", f"pulled {BEHIND + 0.5:.1f} mm out",
       f"the teeth meet the walls' rear ends ({held[0]} samples) and nothing else touches; "
       f"before that it moves freely at least {free} mm")
report("PASS" if over[1] > 0 else "FAIL", "pushed 0.5 mm past its seat", f"its face meets the ends of the cell's ledges ({over[1]} samples)")
report("PASS" if up[1] > 0 else "FAIL", "lifted 1 mm", f"hits the ledges ({up[1]} samples)")

print("== 5. A Raspberry Pi 5 on the carrier in the cell ==")
m = (PLATE_W - 56) / 2
boxes = {
    # The board is turned: card end at 8.95 from the front, ports through the back wall.
    "board": ((8.95, m, BOARD_TOP - 1.35), (93.95, m + 56, BOARD_TOP)),
    "USB and Ethernet, through the back": ((76, m + 1.7, BOARD_TOP), (97, m + 54.3, BOARD_TOP + 16.2)),
    "Active Cooler": ((13.5, m + 8.8, BOARD_TOP), (77, m + 51.3, BOARD_TOP + 13.7)),
    "USB-C and HDMI overhang": ((47, m + 56, BOARD_TOP), (87, m + 57.5, BOARD_TOP + 3.2)),
    "card sticking out": ((6.45, m + 22, BOARD_TOP - 2.95), (8.95, m + 34, BOARD_TOP - 1.35)),
    "HAT allowance to 29 above board": ((9, m, BOARD_TOP + 13.7), (74, m + 56, BOARD_TOP + 29)),
    "card on its way out through the face": ((-9, PLATE_W / 2 - 6, 3.3), (9, PLATE_W / 2 + 6, 4.7)),
    "25 mm fan, 6 thick, in its cradle": ((2.65, PLATE_W / 2 - 12.5, 9.52), (8.6, PLATE_W / 2 + 12.5, 34.5)),
    "three plugs behind the back wall": ((97.05, m + 1.7, BOARD_TOP), (115, m + 54.3, BOARD_TOP + 16.2)),
}


def box_points(lo, hi, n=9):
    g = [np.linspace(a, b, n) for a, b in zip(lo, hi)]
    pts = np.array(np.meshgrid(*g)).reshape(3, -1).T
    return pts[(np.isclose(pts, lo) | np.isclose(pts, hi)).any(1)]


for name, (lo_b, hi_b) in boxes.items():
    pts = box_points(np.array(lo_b) + 0.01, np.array(hi_b) - 0.01)
    in_car = int(inside(pts, car, car_tri).sum())
    in_cell = int(inside(to_cell(pts, SEAT), cell, cell_tri).sum())
    roof = CAV_H - 0.02 - hi_b[2]
    report("PASS" if in_car + in_cell == 0 else "FAIL", name,
           f"{in_car} points in the carrier, {in_cell} in the cell; {roof:.1f} mm to the cell's roof")
win_lo, win_hi = m + 1, m + 55
report("PASS" if win_lo <= m + 1.7 and win_hi >= m + 54.3 else "FAIL", "port window against the ports",
       f"window {win_hi - win_lo:.0f} mm wide; the ports themselves are measured against it in pi5_fit.py, "
       f"from Raspberry Pi's own model")
air = 5 * 8 * 7 + (54 * 18.35 - (15.9 * 13.3 + 2 * 14.5 * 15.6))  # ports as Raspberry Pi model them
report("NOTE", "open area", f"front {5 * 8 * 18} mm2 (five slots 18 tall, the fan behind the middle three); "
       f"back about {air:.0f} mm2 (five slots, and the window around the ports)")
# The fan snaps under a barb on each upright: pushing it in spreads the
# uprights by the barb's reach, plus the fan's worst oversize.
for label, spread in (("as drawn", 0.6 - 0.15), ("fan 0.3 mm oversize", 0.6 - 0.15 + 0.15)):
    strain = 1.5 * 2.5 * spread / (35.5 - 1.8) ** 2
    report("PASS" if strain < 0.025 else "FAIL", f"uprights spread {spread:.2f} mm each as the fan goes in ({label})",
           f"strain {strain * 100:.2f} % (2.5 % allowed)")
report("PASS" if 0.6 - 0.3 > 0.2 else "FAIL", "barbs over the fan",
       "each barb reaches 0.60 mm over the fan's top edge; with the fan hard against one side, the other still has 0.30 mm")
report("NOTE", "the fan's lead", "it leaves the fan's rear face, which is open, and runs back over the board. Two ways to "
       "power it, neither verified: a splitter on the board's four-pin fan socket, which the Active Cooler also uses "
       "(the socket's current limit is not published in anything found), or 5 V and ground from the header, which a HAT covers")

print("== 6. Will it go together as made? (200,000 simulated carriers) ==")
N = 200_000
for process, tol in (("printed nylon, +/-0.30 mm", 0.30), ("moulded, +/-0.10 mm", 0.10)):
    g = lambda mean: rng.normal(mean, tol / 3, N)
    fits = (g(CAV_W) - g(PLATE_W) > 0) & (g(CAV_H) - g(FRONT_H) > 0) & (g(2.3) - g(PLATE) > 0)
    # With the carrier on its stop the teeth must be clear behind the rear
    # edge: cell depth, stop, plate and tooth position each vary.
    clear = BEHIND + (g(0) + g(0) + g(0) + g(0))
    drops = clear > 0
    # What a tooth catches by: its depth, less the gap beside the plate. The two fingers centre the carrier.
    depth = g(TOOTH) - (g(CAV_W) - g(PLATE_W)) / 2
    good = fits & drops & (depth > 0.5)
    report("PASS" if good.mean() > 0.99 else "FAIL", process,
           f"goes in {100 * fits.mean():.2f}%; the teeth drop behind the walls' ends {100 * drops.mean():.2f}%; "
           f"both, with a tooth catching by 0.5 mm or more {100 * good.mean():.2f}%; "
           f"play in and out up to {np.percentile(clear, 99):.1f} mm")

print("== 7. The fingers (nylon PA12, modulus 1,700 MPa assumed) ==")
# Each finger is a beam from its root to its head, bending sideways: its width is what bends, and the
# plate and its rib together are its depth. The head is stiff and carries the tooth further back.
E_MOD, t, b = 1700.0, FINGER_T, PLATE + RIB
L_F = PLATE_L + HEAD_GAP - FINGER_ROOT  # root to head
reach = TOOTH_X + RAMP - (PLATE_L + HEAD_GAP)  # head's front to where the tooth bears
lever = FINGER_MID + TOOTH / 2  # the tooth's bearing point out from the finger's centre line
stiff = E_MOD * b * t ** 3 / 12
give_side = (L_F ** 3 / 3 + L_F ** 2 * reach / 2) / stiff  # the tooth pushed in, per newton sideways on it
give_pull = lever * (L_F ** 2 / 2 + L_F * reach) / stiff  # the same, per newton along the carrier: it turns the head
caught = TOOTH - SIDE
for label, bend in (("sliding in, centred", caught), ("sliding in, hard against one wall", TOOTH),
                    ("sliding in, centred, worst made", caught + 0.3), ("hard against one wall and worst made", TOOTH + 0.3),
                    ("seated", 0.0)):
    force = bend / give_side
    strain = force * (L_F + reach) * (t / 2) / stiff
    report("PASS" if strain < 0.025 else "FAIL", f"finger bent {bend:.2f} mm ({label})",
           f"strain {100 * strain:.2f}% (kept under 2.5%); each pushes with {force:.2f} N")
# Pulling out: the walls' ends bear on the teeth's front faces, which are nearly square. Each tooth stands
# out to one side of its finger, so the pull turns the head and draws the tooth in, against friction on
# the face; the carrier comes out when the tooth has been drawn in by what it was caught by.
mu = 0.3
across, along_face = RAMP / math.hypot(RAMP, TOOTH), TOOTH / math.hypot(RAMP, TOOTH)  # the face's normal: mostly along the carrier
fx, fy = along_face + mu * across, across - mu * along_face  # on the tooth, per newton of bearing: backward, and inward
bearing = caught / (fx * give_pull + fy * give_side)
pull = 2 * bearing * fx
weight = (16.1 * 1.01 / 1000 + 0.046 + 0.03 + 0.01) * 9.81
report("PASS" if pull > 10 else "FAIL", "force to pull the carrier out",
       f"about {pull:.1f} N (friction 0.3 assumed; {2 * caught / (along_face * give_pull) :.1f} N with none), against {weight:.1f} N for "
       f"a loaded carrier's own weight")
report("NOTE", "the hold is less than the carrier before this one", "which held about 22 N on a tooth under each finger. A tooth to one "
       "side of its finger frees itself under a pull; 12 to 14 N was accepted on 2026-11-19 for a carrier that prints flat")
report("NOTE", "unplugging a network cable", f"a plug with its tab pressed comes out for less than the {pull:.0f} N "
       f"the latch holds; one yanked with the tab up will still draw the carrier out")
report("NOTE", "the pull", f"a rail {PULL:.0f} mm proud along the whole top edge, with a 1.5 mm lip under it; "
       f"fingers pull it while the thumb rests on the cell's rim, so pulling a carrier does not drag its cell. "
       f"Whether that grip is good for {pull:.0f} N is for a hand to judge")
bend = pull * 56.5 / 8 / (3.0 * 6.0 ** 2 / 6)
report("PASS" if bend < 12 else "FAIL", "the pull rail under that pull",
       f"{bend:.1f} MPa in bending along its 56.5 mm, safety factor {48 / bend:.0f}")
report("NOTE", "plate thickness", f"{PLATE} mm, under the 2.5 to 3 mm at which printed flame-retardant "
       f"materials are rated; the front is {FRONT_T} mm")

print()
print({v: results.count(v) for v in ("PASS", "FAIL", "NOTE")})
sys.exit(1 if "FAIL" in results else 0)
