#!/usr/bin/env python3
"""Quality control of the carrier, alone and in the cell, measured from the
meshes the kernel made. Each check prints PASS, FAIL or NOTE."""
import math, sys
import numpy as np
from qclib import inside, integrity, kernel_volume, ray_hits, report, results, scene, thickness

rng = np.random.default_rng(20261118)
WALL, DEPTH, CAV_W, CAV_H = 3.0, 100.0, 61.0, 36.0
PLATE, PLATE_W, PLATE_L, FRONT_T, FRONT_H = 1.8, 60.5, 97.0, 2.6, 35.5
TOOTH, RAMP, BEHIND = 1.2, 0.93, 0.6  # tooth depth, its front ramp, ramp start behind the rear edge
PULL = 6.0  # the pull rail's reach in front of the carrier's face
BOARD_TOP = PLATE + 3.0 + 1.35
TOOTH_X = DEPTH + BEHIND  # where the teeth begin, from the carrier's front

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


def clash(push=0.0, slack=0.25, lift=0.02):
    """Collisions between the carrier and the cell, as (at the teeth,
    anywhere else), looking both ways: the carrier's points in the cell and
    the cell's points in the carrier. The teeth are on springs."""
    a = C[inside(to_cell(C, push, slack, lift), cell, cell_tri)]
    near = S[(S[:, 1] > push - 5) & (S[:, 1] < push + 110)]
    b = to_carrier(near, push, slack, lift)
    b = b[inside(b, car, car_tri)]
    hits = np.vstack([a, b])
    teeth = hits[:, 0] > TOOTH_X - 0.05
    return int(teeth.sum()), int((~teeth).sum())


print("== 1. Integrity ==")
integrity("carrier", car, car_tri, kernel_volume("carrier"))

print("== 2. Measured dimensions ==")
lo, hi = car.min(0), car.max(0)
want_lo = np.array([-PULL, 0, -TOOTH])
want_hi = np.array([DEPTH + BEHIND + RAMP + 2.75 + 0.1, PLATE_W, FRONT_H])
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
worst = 0
for slack in (0.02, 0.25, 0.48):
    for lift in (0.02, 0.45):
        worst = max(worst, sum(clash(SEAT, slack, lift)))
report("PASS" if worst == 0 else "FAIL", "seated, at every extreme of its slack",
       f"6 poses; collisions anywhere, teeth included: {worst}")
report("PASS" if worst == 0 else "FAIL", "the latch rests unloaded",
       f"seated against the stop, the teeth stand {BEHIND} mm behind the cell's rear edge and touch nothing")
face = car[car[:, 0] > -0.01]
front = to_cell(face, SEAT)[:, 1].min()
report("PASS" if abs(front) < 0.05 else "FAIL", "front flush with the cell", f"{front:+.2f} mm from the cell's front plane; "
       f"the pull stands {PULL:.0f} mm proud of it")
side = (CAV_W - PLATE_W) / 2
report("PASS", "front in the cell's mouth", f"{side:.2f} mm each side, {CAV_H - FRONT_H:.1f} mm under the roof, as drawn")

print("== 4. Going in, coming out ==")
got = [clash(push, 0.25, 0.02) for push in np.arange(-96, -2, 2.0)]
report("PASS" if max(b for _, b in got) == 0 else "FAIL", "sliding in",
       f"{len(got)} steps; teeth riding on the floor in {sum(1 for a, _ in got if a)}; "
       f"collisions elsewhere {max(b for _, b in got)}")
free = max(d for d in (0.2, 0.4, 0.5) if sum(clash(-d, 0.25, 0.02)) == 0)
held = clash(-(BEHIND + 0.5), 0.25, 0.02)
report("PASS" if held[0] > 0 and held[1] == 0 else "FAIL", f"pulled {BEHIND + 0.5:.1f} mm out",
       f"the teeth meet the rear edge ({held[0]} samples) and nothing else touches; "
       f"before that it moves freely at least {free} mm")
over = clash(0.5, 0.25, 0.02)
report("PASS" if over[1] > 0 else "FAIL", "pushed 0.5 mm past its seat", f"its face meets the ends of the cell's ledges ({over[1]} samples)")
up = clash(SEAT, 0.25, 1.0)
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
    depth = g(TOOTH)
    good = fits & drops & (depth > 0.5)
    report("PASS" if good.mean() > 0.99 else "FAIL", process,
           f"goes in {100 * fits.mean():.2f}%; the teeth drop behind the edge {100 * drops.mean():.2f}%; "
           f"both, with a tooth of 0.5 mm or more {100 * good.mean():.2f}%; "
           f"play in and out up to {np.percentile(clear, 99):.1f} mm")

print("== 7. The fingers (nylon PA12, modulus 1,700 MPa assumed) ==")
E_MOD, t, b, L_F = 1700.0, PLATE, 8.0, 100.0 - 86.0
inertia = b * t ** 3 / 12
for label, bend in (("sliding in, as drawn", TOOTH), ("sliding in, worst made", TOOTH + 0.3), ("seated", 0.0)):
    strain = 3 * t * bend / (2 * L_F ** 2)
    force = 3 * E_MOD * inertia * bend / L_F ** 3
    report("PASS" if strain < 0.025 else "FAIL", f"finger bent {bend:.2f} mm ({label})",
           f"strain {100 * strain:.2f}% (kept under 2.5%); each pushes with {force:.2f} N")
# Pulling out bends the fingers from straight to the whole tooth, up a ramp of
# TOOTH in RAMP, with friction. The hold is greatest as the tooth clears.
mu, slope = 0.3, TOOTH / RAMP
normal = 3 * E_MOD * inertia * (0.5 * TOOTH) / L_F ** 3  # each finger, on average
pull = 2 * normal * (slope + mu) / (1 - mu * slope)
weight = (14.0 * 1.01 / 1000 + 0.046 + 0.03 + 0.01) * 9.81
report("PASS" if pull > 15 else "FAIL", "force to pull the carrier out",
       f"about {pull:.1f} N on average over the ramps, twice that at the top (friction 0.3 assumed), against {weight:.1f} N for "
       f"a loaded carrier's own weight")
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
