// Every part of Dado on its own: a wall of tiles, and a bench where one part
// at a time can be turned, cut open and read. Meshes are the CAD's, written by
// build_assets.py, in one cell's frame (x across, y front to back, z up, mm).
import * as THREE from "three";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { mergeGeometries, toCreasedNormals } from "three/addons/utils/BufferGeometryUtils.js";

const PAL = { graphite: 0x24272a, bone: 0xe1ded4, clay: 0xcd8b7a, ochre: 0xba9960, moss: 0x88ab75, teal: 0x57afaf, slate: 0x75a3d2, lilac: 0xaf90c6 };
const DENSITY = 1.01, PRINT = [0.275, 0.52];  // g/cm3 of PA12 nylon; US$ a gram to print, low and high, as in the projections
const REPO = "https://github.com/copyleftdev/dado/blob/main/hardware";
const FAMILIES = [
  ["cell", "The cell and what finishes it", "One sleeve, one carrier, and the base and caps that close a wall's open edges."],
  ["bay", "Bays and what slides into them", "The cell's section stretched over several places, for what is not a Pi."],
  ["spacer", "Spacers", "Half a place of room, for air and for cables."],
];
// Each part: its mesh, family, name, what it is, its body in mm, printed volume in cm3, a face colour if it has a
// coloured face, and notes: a point on it (CAD, mm), a heading and a sentence.
const PARTS = [
  { id: "cell", in: "cell", name: "Cell", body: "67 × 42 × 100", cm3: 73.06,
    blurb: "The sleeve. One cross-section, extruded front to back, with the same joint on all four sides.",
    notes: [[[-33.5, 60, 45.1], "Rail", "A T along the top. The cell above stands on it and cannot lift off."],
      [[-41.3, 60, -3.6], "Lips", "A pair underneath, reaching under the rail of the cell below."],
      [[-70.1, 60, 21], "Side rail", "The same joint on one side, with 1.6 mm of play up and down."],
      [[-33.5, 14, 45.1], "Notch", "A sprung tooth in a neighbour's lip drops in here when it is home."]] },
  { id: "carrier", in: "cell", name: "Carrier", body: "60.5 × 35.5 × 97", cm3: 15.86, face: PAL.clay,
    blurb: "Holds the Pi, its fan and its face. It slides into a cell and latches behind it.",
    notes: [[[-33.5, -5.5, 38.5], "Pull", "A rail along the whole top edge. Pull the face and everything comes."],
      [[-12, 0, 30], "Air in", "Five tall slots, with a 25 mm fan in a cradle behind the middle three."],
      [[-33.5, 45, 8.2], "Posts", "Four, on the Raspberry Pi 5's own hole pattern."],
      [[-22, 62, 9.5], "The board", "A Raspberry Pi 5, ports to the back, card slot to the front.", "pi"],
      [[-33.5, 8.2, 37.5], "Fan", "25 mm, in the cradle behind the face. A plain block stands in for it here.", "fan"],
      [[-33.5, 97, 22], "Back wall", "Ports and air leave through it, so every cable runs behind."],
      [[-33.5, 103, 2.4], "Latch", "Two fingers drop behind the sleeve's rear edge."]] },
  { id: "base", in: "cell", name: "Base", body: "67 × 22 × 100", cm3: 64.31,
    blurb: "A plinth under each column. Bases join side by side, so a row of them acts as one.",
    notes: [[[-33.5, 60, 25.1], "Rail", "The rail a cell has, so a cell stands on it as it would on another cell."],
      [[-33.5, 0, 11], "Front", "Closed, so it reads as a plain block under the column."]] },
  { id: "trimtop", in: "cell", name: "Top cap", body: "67 × 2 × 100", cm3: 17.38,
    blurb: "A 2 mm plate that covers the rail on top of a column.",
    notes: [[[-41.3, 60, -3.6], "Lips", "The cell's own, so it slides on and latches like a cell."]] },
  { id: "trimrail", in: "cell", name: "Side cap, over a rail", body: "2 × 42 × 100", cm3: 10.74,
    blurb: "Covers the side rail on the wall's open edge.",
    notes: [[[3.6, 60, 21], "Side lips", "They take a cell's side rail."]] },
  { id: "trimlip", in: "cell", name: "Side cap, into lips", body: "2 × 42 × 100", cm3: 11.08,
    blurb: "Fills the side lips on the wall's other open edge.",
    notes: [[[-5.1, 60, 21], "Side rail", "It goes into a cell's side lips."]] },

  { id: "bay", in: "bay", name: "Bay", body: "208.2 × 42 × 100", cm3: 247.33,
    blurb: "The place of three cells, for a desktop switch or a hub.",
    notes: [[[-104.1, 60, 45.1], "Rails", "One at every pitch, where three cells would have had theirs."],
      [[-104.1, 0, 38.5], "Roof", "7 mm: it spans the bay and carries one row above it."]] },
  { id: "shelf", in: "bay", name: "Shelf", body: "201.7 × 31.5 × 97", cm3: 50.4, face: PAL.slate,
    blurb: "Slides into a bay behind a closed face, like a carrier. The device is strapped to it.",
    notes: [[[-104.1, 45, 4.8], "Strap slots", "Twelve, at three widths. Nothing is fitted to one model."],
      [[-104.1, -5.5, 34], "Pull", "As on a carrier."], [[-70.1, 103, 3.5], "Latch", "The carrier's two fingers."]] },
  { id: "baytall", in: "bay", name: "Tall bay", body: "208.2 × 87.6 × 100", cm3: 340.37,
    blurb: "Three wide and two rows high: taller gear, or one rack unit up to 200 mm wide.",
    notes: [[[-211.3, 60, 66.6], "Side rails", "One at every rise, so cells join beside both rows."],
      [[-104.1, 0, 82.6], "Roof", "10 mm: it carries three rows above it."]] },
  { id: "shelftall", in: "bay", name: "Tall shelf", body: "201.7 × 74.1 × 97", cm3: 72.75, face: PAL.teal,
    blurb: "The shelf for the tall bay.", notes: [[[-104.1, 45, 4.8], "Strap slots", "The same twelve."]] },
  { id: "bayrack", in: "bay", name: "Rack bay", body: "278.8 × 87.6 × 100", cm3: 491.05,
    blurb: "Four wide and two rows high: ten-inch rack gear, one unit tall, with its ears on.",
    notes: [[[-139.4, 0, 81.6], "Roof", "12 mm across four places: it carries two rows above it."]] },
  { id: "shelfrack", in: "bay", name: "Rack shelf", body: "272.3 × 72.1 × 97", cm3: 97.48, face: PAL.ochre,
    blurb: "The shelf for the rack bay.", notes: [[[-139.4, 45, 4.8], "Strap slots", "Set wider, for gear 222 to 254 mm across."]] },
  { id: "bayduo", in: "bay", name: "Jetson bay", body: "137.6 × 87.6 × 100", cm3: 191.62,
    blurb: "Two wide and two rows high, for an NVIDIA Jetson Orin Nano developer kit.",
    notes: [[[-68.8, 0, 84.6], "Roof", "6 mm over two places: it carries three rows above it."]] },
  { id: "orin", in: "bay", name: "Orin tray", body: "131.1 × 78.1 × 97", cm3: 44.29, face: PAL.moss,
    blurb: "The Jetson Orin Nano's board is screwed to it, cooler up, sockets to the back.",
    notes: [[[-22.8, 79, 10.8], "Posts", "Four, 92 by 58 mm apart: the board's own holes, from NVIDIA's drill file."],
      [[-68.8, 0, 52], "Air", "Five rows of slots. The board can draw about 25 W."]] },
  { id: "bayagx", in: "bay", name: "AGX bay", body: "137.6 × 133.2 × 100", cm3: 224.0,
    blurb: "Two wide and three rows high, for an NVIDIA Jetson AGX Orin developer kit.",
    notes: [[[-68.8, 0, 130.2], "Three rows", "The kit's fan is in its top face. This leaves it 50 mm of air."]] },
  { id: "agx", in: "bay", name: "AGX tray", body: "131.1 × 123.7 × 121", cm3: 60.38, face: PAL.lilac,
    blurb: "The AGX Orin kit stands on it, held by its own weight. Nothing straps over the fan.",
    notes: [[[-12.3, 55, 9.8], "Fence", "Low, on both sides. The kit stands between them."],
      [[-20.8, 120, 8.8], "Rear stops", "Two, either side of the latch fingers."],
      [[-68.8, 112, 4.8], "Longer plate", "The kit is deeper than a bay, so the plate runs 21 mm past it."]] },

  { id: "spacerrow", in: "spacer", name: "Row spacer", body: "67 × 19.2 × 100", cm3: 52.49,
    blurb: "Half a row of room between two rows. Two of them make one row.",
    notes: [[[-33.5, 0, 9.6], "Air", "Five slots in a closed front. The back is open."],
      [[0, 80, 9.6], "Tray", "No side walls over the rear 40 mm: in a line, cables run across."]] },
  { id: "spacercol", in: "spacer", name: "Column spacer", body: "31.7 × 42 × 100", cm3: 43.29,
    blurb: "Half a place of room between two columns. Two of them make one place.",
    notes: [[[-15.85, 80, 42], "Shaft", "No roof or floor over the rear 40 mm: stacked, a shaft for 23 cables."],
      [[-34.8, 40, 21], "Side rail", "It joins to the cells either side as a cell does."]] },
  { id: "spacercross", in: "spacer", name: "Cross", body: "31.7 × 19.2 × 60", cm3: 19.03,
    blurb: "Fills the corner where a line of row spacers meets a column of spacers.",
    notes: [[[-15.85, 60, 9.6], "Short", "60 mm deep. Behind it the tray and the shaft meet with nothing between."]] },
  { id: "basehalf", in: "spacer", name: "Half base", body: "31.7 × 22 × 100", cm3: 41.43,
    blurb: "The base, half a place wide, under a column of spacers.", notes: [[[-15.85, 60, 25.1], "Rail", "As on a base."]] },
  { id: "trimtophalf", in: "spacer", name: "Half top cap", body: "31.7 × 2 × 100", cm3: 10.32,
    blurb: "The top cap, half a place wide. It closes the top of a shaft.", notes: [[[-15.85, 60, 2], "Plate", "2 mm, as on a top cap."]] },
];
const $ = (id) => document.getElementById(id);
const v = (x, y, z) => new THREE.Vector3(x, z, -y);  // CAD to the scene's axes
const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;

// ---------------------------------------------------------------- renderer
const canvas = $("stage");
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, preserveDrawingBuffer: true, stencil: true });  // the stencil fills cut faces
renderer.toneMapping = THREE.NeutralToneMapping;
renderer.shadowMap.enabled = true;
renderer.localClippingEnabled = true;
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(28, 1, 5, 6000);
{
  const pmrem = new THREE.PMREMGenerator(renderer), room = new RoomEnvironment();
  scene.environment = pmrem.fromScene(room, 0.04).texture;
  scene.environmentIntensity = 0.42;
  room.dispose(); pmrem.dispose();
}
const key = new THREE.DirectionalLight(0xfff6ea, 2.3), rim = new THREE.DirectionalLight(0xdfe8ff, 0.7);
key.castShadow = true; key.shadow.mapSize.set(2048, 2048); key.shadow.bias = -0.0004; key.shadow.normalBias = 0.5; key.shadow.radius = 5;
const ground = new THREE.Mesh(new THREE.PlaneGeometry(4000, 4000), new THREE.ShadowMaterial({ opacity: 0.2 }));
ground.rotation.x = -Math.PI / 2; ground.receiveShadow = true;
scene.add(key, key.target, rim, rim.target, new THREE.HemisphereLight(0xffffff, 0x8a8a84, 0.35), ground);

// ------------------------------------------------------------------ assets
async function load(name) {
  const buf = await (await fetch(`assets/${name}.bin`)).arrayBuffer();
  const [nv, nt, ns, tinted] = new Uint32Array(buf, 0, 4);
  const turn = (src) => { const out = new Float32Array(src.length);
    for (let i = 0; i < src.length; i += 3) { out[i] = src[i]; out[i + 1] = src[i + 2]; out[i + 2] = -src[i + 1]; } return out; };
  let at = 16, g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.BufferAttribute(turn(new Float32Array(buf, at, nv * 3)), 3)); at += nv * 12;
  if (tinted) {  // a colour for each vertex, as sRGB bytes
    const raw = new Uint8Array(buf, at, nv * 4), rgb = new Float32Array(nv * 3), c = new THREE.Color();
    for (let i = 0; i < nv; i++) { c.setRGB(raw[4 * i] / 255, raw[4 * i + 1] / 255, raw[4 * i + 2] / 255, THREE.SRGBColorSpace); c.toArray(rgb, 3 * i); }
    g.setAttribute("color", new THREE.BufferAttribute(rgb, 3)); at += nv * 4;
  }
  g.setIndex(new THREE.BufferAttribute(new Uint32Array(buf, at, nt * 3), 1)); at += nt * 12;
  if (tinted) g.computeVertexNormals(); else g = toCreasedNormals(g, Math.PI / 5);
  const lines = new THREE.BufferGeometry();
  lines.setAttribute("position", new THREE.BufferAttribute(turn(new Float32Array(buf, at, ns * 3)), 3));
  g.computeBoundingBox();
  return { g, lines, box: g.boundingBox.clone() };
}
const cut = new THREE.Plane(new THREE.Vector3(0, 0, -1), 0);
// Filling a cut face. A closed solid cut by a plane shows its inside through the hole. Counting, for each pixel, the
// back faces seen less the front faces seen leaves a count wherever the eye looks into the solid; a sheet lying in
// the plane, drawn only where that count is not nothing, is the cut face. One pair of counters and one sheet a solid.
function fill(geometry, colour, order) {
  const count = (side, op) => {
    const m = new THREE.MeshBasicMaterial({ side, colorWrite: false, depthWrite: false, depthTest: false, clippingPlanes: [cut],
      stencilWrite: true, stencilFunc: THREE.AlwaysStencilFunc, stencilFail: op, stencilZFail: op, stencilZPass: op });
    const mesh = new THREE.Mesh(geometry, m); mesh.renderOrder = order; return mesh;
  };
  const group = new THREE.Group();
  const sheet = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), new THREE.MeshStandardMaterial({ color: colour, roughness: 0.95, side: THREE.DoubleSide,
    stencilWrite: true, stencilRef: 0, stencilFunc: THREE.NotEqualStencilFunc, stencilFail: THREE.ReplaceStencilOp, stencilZFail: THREE.ReplaceStencilOp, stencilZPass: THREE.ReplaceStencilOp }));
  sheet.renderOrder = order + 0.1; sheet.onAfterRender = (r) => r.clearStencil();
  group.add(count(THREE.BackSide, THREE.IncrementWrapStencilOp), count(THREE.FrontSide, THREE.DecrementWrapStencilOp), sheet);
  group.visible = false; scene.add(group);
  return { group, sheet };
}
// The sheet lies in the plane, across the part, facing what was cut away.
function lay({ sheet }, p) {
  sheet.position.copy(p.centre).addScaledVector(cut.normal, -cut.distanceToPoint(p.centre));
  sheet.lookAt(sheet.position.clone().sub(cut.normal)); sheet.scale.setScalar(p.radius * 4);
}
const tone = (hex) => { const c = new THREE.Color(hex), l = c.getHSL({}).l; return c.lerp(new THREE.Color(l < 0.3 ? 0xffffff : 0x000000), l < 0.3 ? 0.34 : 0.22); };
for (const p of PARTS) {
  const geo = await load(p.id);
  const skin = new THREE.MeshStandardMaterial({ color: p.face ?? PAL.graphite, roughness: 0.93, side: THREE.DoubleSide, clipShadows: true });
  const line = new THREE.LineBasicMaterial({ color: p.face ? 0x000000 : 0x565b60, transparent: true, opacity: p.face ? 0.2 : 0.6 });
  p.mesh = new THREE.Mesh(geo.g, skin); p.mesh.castShadow = p.mesh.receiveShadow = true;
  p.edges = new THREE.LineSegments(geo.lines, line); p.mesh.add(p.edges);
  p.box = geo.box; p.centre = geo.box.getCenter(new THREE.Vector3()); p.size = geo.box.getSize(new THREE.Vector3()); p.radius = p.size.length() / 2;
  p.mesh.visible = false; p.mesh.renderOrder = 6; scene.add(p.mesh);
  p.fill = fill(geo.g, tone(p.face ?? PAL.graphite), 1);
}
// What a carrier holds. The fan is a stand-in made here: a 25 mm frame 6 thick with a rotor and a hub, where the
// cradle holds it. The Pi is Raspberry Pi's own model: a lighter copy comes for the carrier's tile once the tiles are
// up, and the full one the first time the carrier is opened.
const shown = { pi: true, fan: true };
const fan = (() => {
  const turned = (g) => g.rotateX(Math.PI / 2);
  const solid = mergeGeometries([new THREE.BoxGeometry(25, 25, 5.2), turned(new THREE.CylinderGeometry(11.2, 11.2, 5.6, 40)), turned(new THREE.CylinderGeometry(4.6, 4.6, 6, 24))], true);
  solid.translate(-33.5, 25, -5.6);
  const dark = { roughness: 0.6, side: THREE.DoubleSide, clipShadows: true };
  const mesh = new THREE.Mesh(solid, [new THREE.MeshStandardMaterial({ color: 0x17181a, ...dark }), new THREE.MeshStandardMaterial({ color: 0x2b2d31, ...dark, roughness: 0.5 }),
    new THREE.MeshStandardMaterial({ color: 0x17181a, ...dark })]);
  mesh.castShadow = true; mesh.renderOrder = 6; mesh.visible = false; scene.add(mesh);
  return { mesh, fill: fill(solid, 0x55595e, 3) };
})();
const board = (geo, order) => {
  const mesh = new THREE.Mesh(geo.g, new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.5, metalness: 0.25, side: THREE.DoubleSide, clipShadows: true }));
  mesh.castShadow = mesh.receiveShadow = true; mesh.renderOrder = order; mesh.visible = false; scene.add(mesh); return mesh;
};
const pi = { mesh: null, fill: null, loading: null, far: null };
function bringPi() {
  pi.loading ??= load("pi").then((geo) => {
    pi.mesh = board(geo, 6); pi.fill = fill(geo.g, 0x7d8286, 2);
    if (look.part) slice();
  });
}

// Where the camera stands to see a part: a direction, at the distance that frames it.
const VIEWS = { Corner: [35, 20], Front: [0, 0], Back: [180, 0], Side: [90, 0], Top: [0, 89] };
function seat(p, [az, el], fill = 1.22) {
  // Far enough to hold the whole part in the narrower of the window's two directions.
  const half = THREE.MathUtils.degToRad(camera.fov / 2), narrow = Math.min(half, Math.atan(Math.tan(half) * camera.aspect));
  const a = THREE.MathUtils.degToRad(az), e = THREE.MathUtils.degToRad(el), d = (p.radius / Math.sin(narrow)) * fill;
  return new THREE.Vector3(Math.sin(a) * Math.cos(e), Math.sin(e), Math.cos(a) * Math.cos(e)).multiplyScalar(d).add(p.centre);
}
function light(p) {
  key.target.position.copy(p.centre); key.position.copy(p.centre).add(new THREE.Vector3(-0.55, 1.05, 0.8).multiplyScalar(p.radius * 2.4));
  rim.target.position.copy(p.centre); rim.position.copy(p.centre).add(new THREE.Vector3(0.7, 0.45, -0.9).multiplyScalar(p.radius * 2.4));
  const r = p.radius * 1.5;
  Object.assign(key.shadow.camera, { left: -r, right: r, top: r, bottom: -r, near: p.radius * 0.4, far: p.radius * 6 });
  key.shadow.camera.updateProjectionMatrix();
  ground.position.set(p.centre.x, p.box.min.y - 0.05, p.centre.z);
}
function only(p) {
  for (const q of PARTS) { q.mesh.visible = q === p; q.fill.group.visible = false; }
  fan.mesh.visible = fan.fill.group.visible = false;
  for (const m of [pi.mesh, pi.far]) if (m) m.visible = false;
  if (pi.fill) pi.fill.group.visible = false;
}

// A picture of a part for its tile, made with the same renderer, with whatever else is to be in it.
function snap(p, company = []) {
  renderer.setPixelRatio(1); renderer.setSize(480, 360, false);
  camera.aspect = 4 / 3; camera.clearViewOffset(); camera.updateProjectionMatrix();
  only(p); light(p);
  for (const m of [p.mesh.material, p.edges.material]) m.clippingPlanes = [];
  p.edges.visible = true;
  for (const mesh of company) { mesh.visible = true; for (const m of [mesh.material].flat()) m.clippingPlanes = []; }
  camera.position.copy(seat(p, VIEWS.Corner, 0.82)); camera.lookAt(p.centre);
  renderer.render(scene, camera);
  for (const mesh of company) mesh.visible = false;
  return canvas.toDataURL("image/png");
}
for (const p of PARTS) p.picture = snap(p, p.id === "carrier" ? [fan.mesh] : []);

// ---------------------------------------------------------------- the tiles
const money = (g) => `$${Math.round(g * PRINT[0])} to $${Math.round(g * PRINT[1])}`;
$("families").innerHTML = FAMILIES.map(([key, title, about]) => `<section class="family"><small>${PARTS.filter((p) => p.in === key).length} parts</small>
  <h2>${title}</h2><p>${about}</p><div class="tiles">${PARTS.filter((p) => p.in === key).map((p) =>
    `<a class="tile" href="#${p.id}" id="tile-${p.id}"><img src="${p.picture}" alt="" width="480" height="360"><div><b>${p.name}</b><span>${p.blurb}</span><em>${p.body} mm</em></div></a>`).join("")}</div></section>`).join("");
$("count").textContent = `${PARTS.length} parts make the whole system. Pick one to turn it over, cut it open and read what each feature is for.`;

// ---------------------------------------------------------------- the bench
const controls = new OrbitControls(camera, canvas);
controls.enableDamping = true; controls.dampingFactor = 0.08; controls.autoRotateSpeed = 0.9; controls.enablePan = false;
const timer = new THREE.Timer(); timer.connect(document);
const look = { part: null, goal: null, cut: "Whole", notes: true };
controls.addEventListener("start", () => { look.goal = null; setSpin(false); });
function setSpin(on) { controls.autoRotate = on && !reduced; $("spin").setAttribute("aria-pressed", String(controls.autoRotate)); }
const press = (id, items, current, pick) => {
  $(id).innerHTML = items.map((k) => `<button type="button" data-k="${k}" aria-pressed="${k === current}">${k}</button>`).join("");
  $(id).onclick = (e) => { const b = e.target.closest("button"); if (b) pick(b.dataset.k); };
};
function slice() {
  const p = look.part, t = $("depth").value / 100, whole = look.cut === "Whole";
  const carrier = p.id === "carrier", withPi = carrier && shown.pi && pi.mesh, withFan = carrier && shown.fan;
  $("depth").hidden = whole;
  press("cuts", ["Whole", "From the front", "From the side", "From the top"], look.cut, (k) => { look.cut = k; slice(); });
  if (pi.mesh) pi.mesh.visible = Boolean(withPi);
  fan.mesh.visible = withFan;
  // Keep what lies behind, beside or under the plane; the slider says how much is cut away.
  if (!whole) {
    const [normal, far] = { "From the front": [[0, 0, -1], p.box.max.z - t * p.size.z], "From the side": [[-1, 0, 0], p.box.max.x - t * p.size.x],
      "From the top": [[0, -1, 0], p.box.max.y - t * p.size.y] }[look.cut];
    cut.normal.set(...normal); cut.constant = far;
  }
  const planes = whole ? [] : [cut];
  for (const m of [p.mesh.material, p.edges.material, ...fan.mesh.material, ...(pi.mesh ? [pi.mesh.material] : [])]) m.clippingPlanes = planes;
  p.fill.group.visible = !whole; if (!whole) lay(p.fill, p);
  if (pi.fill) { pi.fill.group.visible = !whole && Boolean(withPi); if (!whole) lay(pi.fill, p); }
  fan.fill.group.visible = !whole && withFan; if (!whole) lay(fan.fill, p);
}
$("depth").oninput = slice;
$("notes").onclick = () => { look.notes = !look.notes; $("notes").setAttribute("aria-pressed", String(look.notes)); };
$("edges").onclick = () => { const p = look.part; p.edges.visible = !p.edges.visible; $("edges").setAttribute("aria-pressed", String(p.edges.visible)); };
$("spin").onclick = () => setSpin(!controls.autoRotate);
for (const what of ["pi", "fan"]) $(what).onclick = () => { shown[what] = !shown[what]; $(what).setAttribute("aria-pressed", String(shown[what])); slice(); label(look.part); };

function open(p) {
  look.part = p; look.cut = "Whole"; look.goal = null;
  only(p); light(p); p.edges.visible = true; $("edges").setAttribute("aria-pressed", "true");
  $("pi").hidden = $("fan").hidden = p.id !== "carrier"; if (p.id === "carrier") bringPi();
  resize();
  controls.target.copy(p.centre); controls.minDistance = p.radius * 1.2; controls.maxDistance = p.radius * 14;
  camera.position.copy(seat(p, VIEWS.Corner)); setSpin(true);
  press("views", Object.keys(VIEWS), "", (k) => { look.goal = seat(p, VIEWS[k]); setSpin(false); });
  slice();
  const grams = p.cm3 * DENSITY, overall = [p.size.x, p.size.y, p.size.z].map((n) => n.toFixed(1)).join(" × ");
  $("family").textContent = FAMILIES.find(([k]) => k === p.in)[1];
  $("name").textContent = p.name; $("blurb").textContent = p.blurb;
  $("facts").innerHTML = [["Body", `${p.body} mm`], ["With its joints", `${overall} mm`], ["Printed in nylon", `${grams.toFixed(0)} g`], ["To print, projected", money(grams)]]
    .map(([a, b]) => `<tr><td>${a}</td><td>${b}</td></tr>`).join("");
  $("files").innerHTML = `<a href="${REPO}/step/${p.id}.step">STEP file</a> · <a href="${REPO}/parameters/${p.id}.json">Every dimension, with its reason</a>`
    + (p.id === "carrier" ? `<br>The board shown is Raspberry Pi Ltd's own model of the Pi 5, coloured by us. The fan is a plain stand-in.` : "");
  const i = PARTS.indexOf(p), before = PARTS[(i + PARTS.length - 1) % PARTS.length], after = PARTS[(i + 1) % PARTS.length];
  $("prev").href = `#${before.id}`; $("prev").textContent = `← ${before.name}`;
  $("next").href = `#${after.id}`; $("next").textContent = `${after.name} →`;
  label(p);
  document.title = `${p.name} · Dado Parts`;
  renderer.setAnimationLoop(frame);
}

// A part's notes, less any that belong to the board or the fan when that is not shown.
const notesOf = (p) => p.notes.filter(([, , , needs]) => !needs || shown[needs]);
function label(p) {
  $("labels").innerHTML = notesOf(p).map(([, head, text]) => `<div class="label"><b>${head}</b><span>${text}</span></div>`).join("");
  $("leaders").innerHTML = notesOf(p).map(() => `<line/><circle r="2.6"/>`).join("");
}
// Notes hang either side of the part, each tied to its point by a leader. They follow as the part turns.
const at = new THREE.Vector3(), ray = new THREE.Raycaster(), toward = new THREE.Vector3();
// Whether a point on the part is behind some other bit of it, as seen from the camera.
function hidden(p, point) {
  toward.copy(point).sub(camera.position); const far = toward.length();
  ray.set(camera.position, toward.normalize()); ray.far = far - 1.5;
  return ray.intersectObject(p.mesh, false).some((hit) => !p.mesh.material.clippingPlanes.length || cut.distanceToPoint(hit.point) >= 0);
}
function annotate() {
  const p = look.part, labels = [...$("labels").children], lines = $("leaders").querySelectorAll("line"), dots = $("leaders").querySelectorAll("circle");
  const wide = innerWidth > 760, gut = wide ? 24 : 12, w = wide ? 190 : 112;
  const onScreen = (point) => { at.copy(point).project(camera); return [(at.x + 1) / 2 * innerWidth, (1 - at.y) / 2 * innerHeight]; };
  // The part's outline on the screen: notes stand clear of it, to its left and right.
  const { min, max } = p.box; let left = Infinity, right = -Infinity;
  for (const x of [min.x, max.x]) for (const y of [min.y, max.y]) for (const z of [min.z, max.z]) {
    const [sx] = onScreen(at.set(x, y, z)); left = Math.min(left, sx); right = Math.max(right, sx);
  }
  const about = $("name").getBoundingClientRect(), bench = document.querySelector(".bench").getBoundingClientRect();
  const lo = wide ? 96 : about.bottom + 58, hi = { [-1]: wide ? about.top - 150 : bench.top - 40, 1: wide ? innerHeight - 150 : bench.top - 40 };
  const edge = { [-1]: Math.max(gut, left - w - 36), 1: Math.min((wide ? bench.left - 16 : innerWidth - gut) - w, right + 36) };
  const spots = notesOf(p).map(([point], i) => { const world = v(...point), [x, y] = onScreen(world); return { i, x, y, behind: hidden(p, world) }; });
  for (const side of [-1, 1]) {
    const mine = spots.filter((s) => (s.x < (left + right) / 2 ? -1 : 1) === side).sort((a, b) => a.y - b.y);
    const room = wide ? 96 : 40, start = Math.max(lo, Math.min(hi[side] - (mine.length - 1) * room, (mine[0]?.y ?? 0) - 46));
    let floor = start;
    mine.forEach((s) => {
      const x = edge[side], y = Math.max(floor, Math.min(hi[side], s.y - 46)), el = labels[s.i];
      floor = y + room;
      el.className = `label${side < 0 ? " left" : ""}${s.behind ? " behind" : ""}`; el.style.transform = `translate(${x}px, ${y}px)`;
      lines[s.i].setAttribute("class", s.behind ? "behind" : ""); dots[s.i].setAttribute("class", s.behind ? "behind" : "");
      const rule = y + el.firstChild.offsetHeight, near = side < 0 ? x + w : x;
      for (const [k, val] of Object.entries({ x1: s.x, y1: s.y, x2: near, y2: rule })) lines[s.i].setAttribute(k, val);
      dots[s.i].setAttribute("cx", s.x); dots[s.i].setAttribute("cy", s.y);
    });
  }
  $("labels").style.visibility = $("leaders").style.visibility = look.notes ? "visible" : "hidden";
}
function frame() {
  timer.update();
  if (look.goal) {
    camera.position.lerp(look.goal, 0.12);
    if (camera.position.distanceTo(look.goal) < look.part.radius * 0.004) look.goal = null;
  }
  controls.update(timer.getDelta());
  renderer.render(scene, camera);
  annotate();
}
function resize() {
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2)); renderer.setSize(innerWidth, innerHeight, false);
  camera.aspect = innerWidth / innerHeight;
  // On a narrow screen the bench covers the bottom, so the picture is lifted to sit in what is left above it.
  const bench = document.querySelector(".bench").getBoundingClientRect(), about = document.querySelector(".about").getBoundingClientRect();
  const wide = innerWidth > 760, lift = wide ? 0 : (innerHeight - bench.top) / 2 - 20;
  // On a wide one the text is on the left and the bench on the right, so it is centred in the space between them.
  const over = wide ? (about.right - (innerWidth - bench.left)) / 2 : 0;
  camera.setViewOffset(innerWidth, innerHeight, -over, Math.max(0, lift), innerWidth, innerHeight);
  camera.updateProjectionMatrix();
}
addEventListener("resize", () => { if (look.part) resize(); });
// The tiles' pictures were made at their own size and shape; the bench has the window's.

// ------------------------------------------------------------ which is showing
// The page's address says which: nothing after the # is the wall of tiles, a part's name is that part on the bench.
function route(first) {
  const p = PARTS.find((q) => q.id === location.hash.slice(1));
  if (!p) {
    renderer.setAnimationLoop(null); const left = look.part; look.part = null;
    document.body.dataset.view = "gallery"; document.title = "Dado Parts"; retile();
    if (left) { const tile = $(`tile-${left.id}`); tile.scrollIntoView({ block: "center" }); tile.focus({ preventScroll: true }); }
    return;
  }
  const tile = $(`tile-${p.id}`).querySelector("img"), from = tile.getBoundingClientRect();
  const fly = document.body.dataset.view === "gallery" && !first && !reduced && from.width > 0;
  if (fly) {
    // The tile's picture grows to fill the window, and the live part arrives behind it.
    const ghost = tile.cloneNode();
    ghost.className = "flight"; Object.assign(ghost.style, { left: `${from.left}px`, top: `${from.top}px`, width: `${from.width}px`, height: `${from.height}px` });
    document.body.append(ghost); ghost.getBoundingClientRect();
    Object.assign(ghost.style, { left: "0", top: "0", width: "100vw", height: "100vh", opacity: "0" });
    setTimeout(() => ghost.remove(), 900);
  }
  document.body.dataset.view = "detail"; scrollTo(0, 0);
  open(p);
}
addEventListener("hashchange", () => route(false));
// The carrier's tile is redrawn with the Pi on it once a lighter copy of the model has come. The one renderer is busy
// while a part is on the bench, so the picture is taken the next time the tiles are showing.
function retile() {
  if (!pi.far || pi.tiled || look.part) return;
  const carrier = PARTS.find((p) => p.id === "carrier");
  carrier.picture = snap(carrier, [fan.mesh, pi.far]); $("tile-carrier").querySelector("img").src = carrier.picture; pi.tiled = true;
}
load("pi-far").then((geo) => { pi.far = board(geo, 6); retile(); });
addEventListener("keydown", (e) => {
  if (!look.part || e.target.matches?.("input")) return;
  if (e.key === "Escape") { if (home) location.href = home; else location.hash = ""; }
  if (e.key === "ArrowRight") $("next").click();
  if (e.key === "ArrowLeft") $("prev").click();
});
// Come from the film's own tiles, "All parts" and Escape go back to them, not to this page's.
const home = new URLSearchParams(location.search).get("from") === "film" ? "index.html#parts" : "";
if (home) $("toAll").href = home;
route(true);
window.dado = { PARTS, look, camera };
