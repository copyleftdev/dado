# Dado: the specification

All lengths are millimetres. Each part's full parameter list, with the reason for every value, is in [`hardware/parameters`](hardware/parameters). This page states what must stay true if you change anything.

## The invariants

1. **One free axis.** Front to back, the axis the ports lie on. Every joint slides along it and nothing else moves.
2. **Four joining faces, two service faces.** Top, bottom and both sides join. Front is for people; back is for cables and air.
3. **One section.** A cell is a constant cross-section extruded 100 deep; everything after that is a cut. A bay is the same section, stretched.
4. **The lattice.** A cell's body is 67 wide and 42 tall. Joined cells sit 3.6 apart, so the pitch is 70.6 across and 45.6 up. A part that takes N places across and M up measures N pitches by M rises, less one gap each way.
5. **Each joint holds along its own normal only.** The stacking joint has 0.8 of play across; the side joint has 1.6 up and down. That is what lets a wall go together when parts vary.
6. **Latches bend within their limit.** Every sprung finger stays under 2.5 % strain at the worst end of its travel.
7. **The carrier is the only part that knows about the Pi.** Change the board and only the carrier changes.

## The joint

| Feature | Value | Why |
|---|---|---|
| Rail stem | 6 wide, 1.9 tall | Rail stem: a lip's flange plus 0.5 to lift in |
| Rail head | 12 wide (15.2 on the side), 1.2 tall | Side rail head: still holds 1.4 at either end of that play |
| Lip flange | 1.4 | Lip flange, the part that holds |
| Wall | 3 | Where printed flame-retardant materials reach V-0 |
| Front relief | 9 | Rails, lips and skids cut back from the front, so the gaps between cells read as clean lines |
| Tooth reach | 1.4 (2.2 on the side) | Tooth beyond the lip's edge: 0.6 past the stem when centred |

## The board

Taken from Raspberry Pi's mechanical drawing and STEP model of the Pi 5: board 85 by 56 and 1.35 thick; mounting holes 2.7 across on a 58 by 49 pattern, 3.5 in from the edges at the card end; ports 3.05 beyond the port edge; tallest part 16.19 above the board.

The board sits with its ports through the carrier's back wall and its card end 6.35 behind the face, so the card comes out through a slot low in the face.

## Bays

| Bay | Places | Roof | Room on its shelf | Rows of cells it carries |
|---|---|---|---|---|
| Bay | 3 by 1 | 7 | 201.7 by 30.2 | 1 |
| Tall bay | 3 by 2 | 10 | 201.7 by 72.8 | 3 |
| Rack bay | 4 by 2 | 12 | 272.3 by 70.8 | 2 |
| Jetson bay | 2 by 2 | 6 | 131.1 by 76.8 | 3 |
| AGX bay | 2 by 3 | 6 | 131.1 by 122.4 | 3 |

Roof loads are beam calculations allowing 0.25 of sag, with 200 g assumed for each loaded cell. Desktop switches and hubs have no standard size, so a shelf holds its device with straps through slots at three widths.

### The Jetson bay

A board too big for a cell takes a bay of its own. The NVIDIA Jetson Orin Nano developer kit is 34.77 ± 1.09 tall with its cooler, and a one-row sleeve has 36 inside, so its bay is two rows high as well as two cells wide.

Its tray is a shelf with four posts in place of strap slots, and five rows of air slots in its face. From NVIDIA's carrier board specification (SP-11324-001 v1.3) and the drill file of the P3768 reference design: board 100 by 79 and 1.57 thick, parts up to 4.30 below it; four mounting holes 2.75 across on a 92 by 58 pattern, 4 in from each side and from the edge opposite the sockets, 17 in from the socket edge.

The board goes on without the stand it ships on, on posts 6 tall, with its sockets at the open back and 4 inside the bay's rear. Screws are M2.5 thread-forming, into pilot holes 2.1 across.

### The AGX bay

The NVIDIA Jetson AGX Orin developer kit is a closed box, 110 by 110 and 71.65 tall, weighing 872.5 g, with its fan in its top face (carrier board specification SP-10900-001 v1.1, figures 5-3 and 5-4). A two-row bay would leave 5.1 above that fan; a gap a quarter of the fan's width lets in as much air as the fan's own opening, which for a fan about 84 across is 21. So its bay is three rows high and leaves 50.7.

Nothing may cover the fan, so the kit is not strapped. It stands between two fences 5 tall, a front stop and two rear stops, with 0.5 of slack to each, held by its own weight. Its front is 8.5 behind the tray's, so air from the face's nine rows of slots can pass.

The kit is deeper than a bay. The tray's plate carries on 21 past the bay's back, the kit's sockets stand 18.5 behind it, and the latch fingers are tongues cut into the longer plate.

## Tolerances

Designed for powder-bed nylon at ±0.30 on every dimension. Injection moulding at ±0.10 would let the plays above be reduced; that study has not been done.
