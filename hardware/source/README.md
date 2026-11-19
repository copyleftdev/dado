# Source of the hardware

These scripts generated every part in `../step`. Each one writes a transaction for Ringwright, a headless parametric CAD engine: parameters with reasons, sketches whose every point is placed by dimension, features, and two checks the kernel must pass before the part is committed (a valid solid, and a volume within 0.05 % of one worked out by hand in the same script).

**Ringwright is not yet public, so these cannot be run today.** They are published as the readable record of the design: every number in `../parameters` and every decision behind it is here. Set `RINGWRIGHT` to the binary's path if you have one.

| Script | Builds or checks |
|---|---|
| `build_cell.py` | The cell, and the joint code every other part reuses |
| `build_carrier.py` | The carrier. `build_carrier_v3.py` is the one before it, whose latch teeth pointed down and could not be printed lying flat; kept for the record |
| `build_base.py`, `build_trim.py` | The base and the three caps |
| `build_bay.py`, `build_shelf.py` | The bays and their shelves |
| `build_orin.py` | The Jetson Orin Nano tray, for the two-by-two bay |
| `build_agx.py` | The Jetson AGX Orin tray, for the two-by-three bay |
| `build_spacer.py`, `qc_spacer.py` | The row spacer, column spacer and cross, and their QC. `build_base.py` and `build_trim.py` also make the half base and half top cap |
| `qc.py`, `qc_carrier.py`, `qc_base.py`, `qc_trim.py`, `qc_bay.py` | QC of each part; output in `../reports` |
| `fit_check.py`, `qa.py` | The joint proof, and checks across all twenty parts: each rebuilt from its script, shared dimensions compared, a mixed wall assembled |
| `mutate.py` | Plants one wrong number at a time in a copy of the designs and reports whether the checks notice; output in `../reports/mutation-report.txt` |
| `pi5_import.py`, `pi5_fit.py` | Imports Raspberry Pi's model and checks the carrier against it. Needs their STEP file, which is not redistributed here: get it from Raspberry Pi's product page |
| `build_checks.py` | The checks every build script adds to its transaction: the part's size along each axis, worked out by hand, and its thinnest wall. The engine refuses the commit if either is out |
| `print_check.py` | How each part would print on a filament printer: the way up it goes, how much of it overhangs that way (held under a ceiling), and which bed sizes take it |
| `qclib.py` | Shared mesh checks |
| `fitlib.py` | Part against part, asked of Ringwright's `assemble`: whether two parts overlap at a given placing, and where. The joint, base, cap, bay, spacer and carrier checks use it |

Some scripts refer to files that live only in the working project (scene files, earlier versions). They are kept as they were used, not tidied into a package.
