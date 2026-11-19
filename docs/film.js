// Dado: the film. One timeline, driven by scroll, moves the real parts.
// Lengths are millimetres. CAD axes are x across, y front to back, z up;
// three.js sees them as (x, z, -y), so the ports face the camera.
import * as THREE from "three";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
import { Line2 } from "three/addons/lines/Line2.js";
import { LineGeometry } from "three/addons/lines/LineGeometry.js";
import { LineMaterial } from "three/addons/lines/LineMaterial.js";
import { toCreasedNormals } from "three/addons/utils/BufferGeometryUtils.js";

const PAL = {
  graphite: 0x24272a, putty: 0x88867e, bone: 0xe1ded4,
  clay: 0xcd8b7a, ochre: 0xba9960, moss: 0x88ab75, teal: 0x57afaf, slate: 0x75a3d2, lilac: 0xaf90c6,
  night: 0x14161a, day: 0xc9cac4, inkDay: 0x1f2224, inkNight: 0xe7e7e2,
};
const HUES = ["clay", "ochre", "moss", "teal", "slate", "lilac"];
// The rear shot was added after the rest was timed: for REAR seconds from 79
// the film's own clock T holds still while the camera goes round the back.
// The bay's shot follows it the same way, for BAY seconds more.
const REAR = 8, BAY = 33, HOLD = REAR + BAY, TOTAL = 88 + HOLD, CONFIG_AT = 85.5, PX_PER_S = 115;
const B0 = 79 + REAR, B1 = B0 + BAY, B2 = B0 + 11, B3 = B2 + 9.4, B4 = B3 + 6.2;  // B2: the first bay leaves, its taller and wider kin follow; B3: the Jetson bay; B4: the AGX bay
const still = new URLSearchParams(location.search).get("t");
const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;

const clamp01 = (x) => Math.min(1, Math.max(0, x));
const io = (x) => x * x * (3 - 2 * x);
const eo = (x) => 1 - (1 - x) ** 3;
const mix = (a, b, k) => a + (b - a) * k;
const v = (x, y, z) => new THREE.Vector3(x, z, -y);
const $ = (id) => document.getElementById(id);

// ---------------------------------------------------------------- renderer
const canvas = $("stage");
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, powerPreference: "high-performance" });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.toneMapping = THREE.NeutralToneMapping;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFShadowMap;
const scene = new THREE.Scene();
scene.background = new THREE.Color(PAL.night);
const camera = new THREE.PerspectiveCamera(28, 1, 10, 8000);
{
  const pmrem = new THREE.PMREMGenerator(renderer), room = new RoomEnvironment();
  scene.environment = pmrem.fromScene(room, 0.04).texture;
  scene.environmentIntensity = 0.42;
  room.dispose(); pmrem.dispose();
}
const key = new THREE.DirectionalLight(0xfff6ea, 2.3);
key.castShadow = true;
key.shadow.mapSize.set(2048, 2048);
Object.assign(key.shadow.camera, { left: -360, right: 360, top: 360, bottom: -360, near: 100, far: 2200 });
key.shadow.bias = -0.0004; key.shadow.normalBias = 0.5; key.shadow.radius = 5;
const rim = new THREE.DirectionalLight(0xdfe8ff, 0.7);
scene.add(key, key.target, rim, rim.target, new THREE.HemisphereLight(0xffffff, 0x8a8a84, 0.35));
const ground = new THREE.Mesh(new THREE.PlaneGeometry(6000, 6000), new THREE.ShadowMaterial({ opacity: 0.2 }));
ground.rotation.x = -Math.PI / 2; ground.position.y = -3.6; ground.receiveShadow = true;
scene.add(ground);

// ------------------------------------------------------------------ assets
async function part(name, creased) {
  const buf = await (await fetch(`assets/${name}.bin`)).arrayBuffer();
  const [nv, nt, ns, tinted] = new Uint32Array(buf, 0, 4);
  let at = 16;
  const turn = (src) => {
    const out = new Float32Array(src.length);
    for (let i = 0; i < src.length; i += 3) { out[i] = src[i]; out[i + 1] = src[i + 2]; out[i + 2] = -src[i + 1]; }
    return out;
  };
  let g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.BufferAttribute(turn(new Float32Array(buf, at, nv * 3)), 3)); at += nv * 12;
  if (tinted) {
    const raw = new Uint8Array(buf, at, nv * 4), rgb = new Float32Array(nv * 3), c = new THREE.Color();
    for (let i = 0; i < nv; i++) {
      c.setRGB(raw[4 * i] / 255, raw[4 * i + 1] / 255, raw[4 * i + 2] / 255, THREE.SRGBColorSpace);
      rgb[3 * i] = c.r; rgb[3 * i + 1] = c.g; rgb[3 * i + 2] = c.b;
    }
    g.setAttribute("color", new THREE.BufferAttribute(rgb, 3)); at += nv * 4;
  }
  g.setIndex(new THREE.BufferAttribute(new Uint32Array(buf, at, nt * 3), 1)); at += nt * 12;
  if (creased) g = toCreasedNormals(g, Math.PI / 5); else g.computeVertexNormals();
  let lines = null;
  if (ns) {
    lines = new THREE.BufferGeometry();
    lines.setAttribute("position", new THREE.BufferAttribute(turn(new Float32Array(buf, at, ns * 3)), 3));
  }
  return { g, lines };
}
const names = ["cell", "carrier", "base", "trimtop", "trimrail", "trimlip", "bay", "shelf", "baytall", "shelftall", "bayrack", "shelfrack", "bayduo", "orin", "bayagx", "agx", "pi-far", "pi"];
const [man, ...loaded] = await Promise.all([
  fetch("assets/manifest.json").then((r) => r.json()),
  ...names.map((n) => part(n, !n.startsWith("pi"))),
]);
const G = Object.fromEntries(names.map((n, i) => [n, loaded[i]]));
const [PX, PZ] = man.pitch, LIFT = man.base_rise - 2.6, CAP = man.trim + man.gap;

// --------------------------------------------------------------- materials
const matte = (hex) => new THREE.MeshStandardMaterial({ color: hex, roughness: 0.93, metalness: 0 });
const M = {
  sleeve: matte(PAL.graphite), ghost: matte(PAL.graphite),
  pi: new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.5, metalness: 0.25 }),
  sleeveLine: new THREE.LineBasicMaterial({ color: 0x4a4f54, transparent: true, opacity: 0.55 }),
  ghostLine: new THREE.LineBasicMaterial({ color: 0x4a4f54, transparent: true, opacity: 0.55 }),
  faceLine: new THREE.LineBasicMaterial({ color: 0x000000, transparent: true, opacity: 0.16 }),
};
M.ghost.transparent = true;
function solid(geo, material, lineMaterial) {
  const m = new THREE.Mesh(geo.g, material);
  m.castShadow = m.receiveShadow = true;
  if (geo.lines && lineMaterial) m.add(new THREE.LineSegments(geo.lines, lineMaterial));
  return m;
}

// A 25 mm fan, 6 thick, where the cradle holds it: a frame, a rotor and a hub.
const fan = new THREE.Group();
{
  const dark = new THREE.MeshStandardMaterial({ color: 0x17181a, roughness: 0.6 }), blade = new THREE.MeshStandardMaterial({ color: 0x2b2d31, roughness: 0.5 });
  const frame = new THREE.Mesh(new THREE.BoxGeometry(25, 25, 5.2), dark);
  const rotor = new THREE.Mesh(new THREE.CylinderGeometry(11.2, 11.2, 5.6, 40), blade);
  const hub = new THREE.Mesh(new THREE.CylinderGeometry(4.6, 4.6, 6, 24), dark);
  rotor.rotation.x = hub.rotation.x = Math.PI / 2;
  fan.add(frame, rotor, hub); fan.position.set(-33.5, 25, -5.6);
}
// One network cable for the rear shot: a plug in the Ethernet port and its lead.
const cable = new THREE.Group();
{
  const lead = new THREE.CatmullRomCurve3([v(-15.75, 111, 15.5), v(-15.75, 150, 15), v(-10, 195, 7), v(8, 240, -0.6), v(60, 290, -0.6), v(150, 320, -0.6)]);
  const tube = new THREE.Mesh(new THREE.TubeGeometry(lead, 80, 2.7, 12), matte(PAL.bone));
  const plug = new THREE.Mesh(new THREE.BoxGeometry(12, 9, 17), matte(PAL.putty));
  plug.position.copy(v(-15.75, 105, 15.5)); tube.castShadow = plug.castShadow = true;
  cable.add(tube, plug); cable.visible = false; scene.add(cable);
}

// ------------------------------------------------------------------- parts
// Nine slots in the order the film fills them, then the rest of a 6 by 4 wall.
const SLOTS = [[0, 0], [0, 1], [1, 0], [1, 1], [2, 0], [2, 1], [0, 2], [1, 2], [2, 2]];
for (let r = 0; r < 4; r++) for (let c = 0; c < 6; c++) if (!SLOTS.some(([a, b]) => a === c && b === r)) SLOTS.push([c, r]);
const units = SLOTS.map(([c, r], i) => {
  const group = new THREE.Group(), inner = new THREE.Group();
  const sleeve = solid(G.cell, i ? M.sleeve : M.ghost, i ? M.sleeveLine : M.ghostLine);
  const face = matte(PAL.bone);
  const carrier = solid(G.carrier, face, M.faceLine);
  const pi = new THREE.Mesh(G[i ? "pi-far" : "pi"].g, M.pi);
  pi.receiveShadow = true;
  inner.add(carrier, pi, fan.clone()); group.add(sleeve, inner); scene.add(group);
  return { c, r, group, inner, sleeve, pi, face, arr: 0, tint: new THREE.Color(PAL.bone) };
});
const pool = (n, geo) => Array.from({ length: n }, () => {
  const m = solid(geo, M.sleeve, M.sleeveLine); scene.add(m); return { m, arr: 0 };
});
const bases = pool(6, G.base), tops = pool(6, G.trimtop), rails = pool(7, G.trimrail), lips = pool(7, G.trimlip);  // four rows and a three-row bay make seven
// Two bays, each with its shelf and a switch strapped to it, ports to the back.
const bays = [0, 1].map(() => {
  const group = new THREE.Group(), inner = new THREE.Group(), face = matte(PAL.slate);
  const box = new THREE.Mesh(new THREE.BoxGeometry(158, 25, 101), new THREE.MeshStandardMaterial({ color: 0x1d1f22, roughness: 0.7 }));
  box.position.set(-104.1, 17.3, -54.5); box.castShadow = true;
  const ports = new THREE.Mesh(new THREE.BoxGeometry(124, 11, 1), new THREE.MeshStandardMaterial({ color: 0x9ba1a4, roughness: 0.5, metalness: 0.3 }));
  ports.position.set(-104.1, 17.3, -105.3);
  inner.add(solid(G.shelf, face, M.faceLine), box, ports); group.add(solid(G.bay, M.sleeve, M.sleeveLine), inner);
  group.visible = false; scene.add(group);
  return { group, inner, face, arr: 0 };
});
// The taller and wider bays, each with its shelf shut.
const kin = (bay, shelf, n, hex, load) => Array.from({ length: n }, () => {
  const group = new THREE.Group(), face = matte(hex);
  group.add(solid(G[bay], M.sleeve, M.sleeveLine), solid(G[shelf], face, M.faceLine), ...(load ? load() : []));
  group.visible = false; scene.add(group);
  return { group, face, arr: 0 };
});
// A stand-in for the Jetson's board on its posts: board, cooler and sockets
// as plain blocks, at NVIDIA's outline and heights. Not a model of it.
const jetsonBoard = () => [[100, 1.57, 79, -68.8, 11.6, -56.5, 0x2f6a45, 0.6, 0], [58, 18, 39, -68.8, 30.4, -37.5, 0x1d1f22, 0.7, 0],
  [84, 14, 15, -68.8, 19.4, -89.5, 0x9ba1a4, 0.5, 0.3]].map(([w, h, d, x, y, z, color, roughness, metalness]) => {
  const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), new THREE.MeshStandardMaterial({ color, roughness, metalness }));
  m.position.set(x, y, z); m.castShadow = true; return m;
});
// And for the AGX Orin kit on its tray: a plain box of NVIDIA's outside sizes.
const agxKit = () => {
  const m = new THREE.Mesh(new THREE.BoxGeometry(110, 71.65, 110), new THREE.MeshStandardMaterial({ color: 0x1d1f22, roughness: 0.6, metalness: 0.2 }));
  m.position.set(-68.8, 40.6, -63.5); m.castShadow = true; return [m];
};
// Each kind of bay: its pool, how many cells wide and how many rows high.
const CROWNS = {
  bay: { pool: bays, wide: 3, high: 1 },
  tall: { pool: kin("baytall", "shelftall", 2, PAL.teal), wide: 3, high: 2 },
  rack: { pool: kin("bayrack", "shelfrack", 1, PAL.ochre), wide: 4, high: 2 },
  jetson: { pool: kin("bayduo", "orin", 3, PAL.moss, jetsonBoard), wide: 2, high: 2 },
  agx: { pool: kin("bayagx", "agx", 3, PAL.lilac, agxKit), wide: 2, high: 3 },
};
const bayCount = () => { const k = CROWNS[cfg.bay]; return k && cfg.cols % k.wide === 0 ? Math.min(cfg.cols / k.wide, k.pool.length) : 0; };
const bayRows = () => (bayCount() ? CROWNS[cfg.bay].high : 0);

// The section, drawn before anything is solid: the kernel's own edges.
const loops = man.section.map((pts) => {
  const g = new LineGeometry();
  g.setPositions(pts.flatMap(([x, z]) => [x, z, -100]));
  const m = new LineMaterial({ color: PAL.bone, linewidth: 2.2, transparent: true });
  const line = new Line2(g, m); scene.add(line);
  return { line, n: pts.length - 1 };
});

// ---------------------------------------------------------------- the looks
const cfg = { cols: +(new URLSearchParams(location.search).get("cols") || 3), rows: 3, sleeve: "graphite", look: "run", hue: "teal", bay: new URLSearchParams(location.search).get("bay") || "none" };
const FILM = { cols: 3, rows: 3, sleeve: "graphite", hue: "teal" };
function look(name, c, r, s) {
  switch (name) {
    case "first": return c === 0 && r === 0 ? PAL.clay : PAL.bone;
    case "monolith": return s.sleeve === "bone" ? PAL.graphite : PAL.bone;
    case "voice": return PAL[s.hue];
    case "run": return PAL[HUES[(c + r) % 6]];
    case "roles": return [PAL.ochre, PAL.teal, PAL.lilac][c % 3];
    case "signal": return c === Math.floor((s.cols - 1) / 2) && r === Math.floor((s.rows - 1) / 2) ? PAL.clay : PAL.slate;
    case "study": return r === 0 ? PAL.clay : PAL.moss;
    case "config": return look(cfg.look, c, r, cfg);
    default: return PAL.bone;
  }
}
const LOOKS = [[0, "blank"], [16.6, "first"], [34, "monolith"], [36, "voice"], [38, "run"], [40, "roles"], [42, "signal"], [52.5, "study"], [79, "config"]];
const ca = new THREE.Color(), cb = new THREE.Color();
function filmTint(T, c, r, out) {
  let i = LOOKS.length - 1;
  while (i > 0 && LOOKS[i][0] > T) i--;
  const [at, now] = LOOKS[i], before = i ? LOOKS[i - 1][1] : now;
  const k = at === 52.5 ? 1 : io(clamp01((T - at - 0.13 * (c + r)) / 1.2));
  ca.setHex(look(before, c, r, FILM)); cb.setHex(look(now, c, r, FILM));
  return out.copy(ca).lerp(cb, k);
}

// ------------------------------------------------------------------ camera
// [time, target x y z, azimuth, elevation, distance]; azimuth 0 is straight on.
const KEYS = [
  [0, -33.5, 100, 20.75, 0, 0, 430], [4.6, -33.5, 100, 20.75, 0, 0, 430], [9.5, -33.5, 50, 21, 38, 22, 520],
  [12, -33.5, -30, 24, 44, 26, 640], [16.3, -33.5, 30, 21, 30, 18, 500], [18.2, -33.5, 5, 21, 10, 6, 360],
  [20, -33.5, 4, 43.5, 16, 12, 200], [23.2, -33.5, 12, 43.5, -22, 14, 230], [25.5, -50, 50, 45, 32, 20, 760],
  [30, -104, 50, 60, 30, 18, 930], [33.6, -104, 50, 76, 22, 13, 780], [35, -104, 30, 76, 9, 6, 640],
  [41.2, -104, 30, 76, -9, 6, 640], [43.4, -104, 0, 76, 36, 17, 640], [47, -104, 0, 76, 28, 15, 660],
  [51.5, -104, 50, 76, 18, 12, 1700], [52.8, -104, 50, 76, 18, 12, 1700], [53, -33.5, 0, 21, -6, 2, 330],
  [61.5, -33.5, 0, 21, 7, 3, 310], [63.6, -33.5, 36, 40, 40, 34, 430], [69.6, -33.5, 36, 40, 30, 31, 420],
  [72, -33.5, -4, 21, 62, 24, 440], [77.4, -33.5, -4, 21, 52, 22, 430], [80.5, -60, 40, 40, 30, 18, 700],
];
const cam = { x: 0, y: 0, z: 0, az: 0, el: 0, d: 500 };
function filmCam(T) {
  let i = 0;
  while (i < KEYS.length - 2 && KEYS[i + 1][0] <= T) i++;
  const a = KEYS[i], b = KEYS[i + 1], k = io(clamp01((T - a[0]) / (b[0] - a[0])));
  return { x: mix(a[1], b[1], k), y: mix(a[2], b[2], k), z: mix(a[3], b[3], k), az: mix(a[4], b[4], k), el: mix(a[5], b[5], k), d: mix(a[6], b[6], k) };
}
let orbit = 26;
function wallCam() {
  const w = cfg.cols * PX - man.gap + 2 * CAP, h = LIFT + (cfg.rows + bayRows()) * PZ + 2, aspect = innerWidth / innerHeight;
  const wide = innerWidth > 760, across = wide ? 0.4 : 0.56, up = wide ? 0.55 : 0.34;
  const d = Math.max(h / up, (w + 70) / (across * aspect)) / 0.4987;
  return { x: -(cfg.cols * PX - man.gap) / 2, y: 50, z: (h - 3.6) / 2, az: orbit, el: 14, d };
}
function aim(c, fit) {
  const az = THREE.MathUtils.degToRad(c.az), el = THREE.MathUtils.degToRad(c.el), d = c.d * fit;
  const t = v(c.x, c.y, c.z);
  camera.position.copy(v(c.x + d * Math.sin(az) * Math.cos(el), c.y - d * Math.cos(az) * Math.cos(el), c.z + d * Math.sin(el)));
  camera.lookAt(t);
  key.target.position.copy(t); key.position.copy(t).add(new THREE.Vector3(-330, 620, 480));
  rim.target.position.copy(t); rim.position.copy(t).add(new THREE.Vector3(420, 260, -520));
}

// ---------------------------------------------------------------- the words
const CAPS = [
  [1.6, 5, "Act one · 1 of 8", "A line.", "The section every cell is made from, drawn as it is in the CAD."],
  [5.4, 10, "Act one · 2 of 8", "Pulled.", "A hundred millimetres deep. Rails, lips and skids run the whole length."],
  [10.4, 18.2, "Act one · 3 of 8", "One board.", "A Raspberry Pi 5 on its carrier, ports to the back. The carrier slides in and stops flush."],
  [18.6, 24.2, "Act one · 4 of 8", "It slides.", "A second cell’s lips pass over the first cell’s rail, and it holds."],
  [24.6, 33.6, "Act one · 5 of 8", "And again.", "One, two, four, nine. A base under each column, caps on the open edges."],
  [34, 41.6, "Act one · 6 of 8", "Any colour. Same weight.", "A closed face in six hues at one lightness. Every cable leaves from behind."],
  [42, 48, "Act one · 7 of 8", "Pull one.", "A carrier comes out, board and all. The other eight stay where they are."],
  [54.4, 61.9, "Act two · Look closer", "The face.", ""],
  [62.4, 70, "Act two · Look closer", "The joint.", ""],
  [70.6, 78.2, "Act two · Look closer", "The carrier.", ""],
  [79.3, 86.7, "Act two · Look closer", "The back.", "Ports, air and power all leave from behind. Power over Ethernet makes it one cable a cell."],
  [B0 + 0.3, B2 - 0.4, "Act two · Look closer", "The bay.", "A switch or a hub takes the place of three cells, on the same joints. The cables stay behind."],
  [B2 + 0.1, B3 - 0.4, "Act two · Look closer", "Taller. Wider.", "The same idea at two more sizes, for gear that is not a desktop switch."],
  [B3 + 0.1, B4 - 0.4, "Act two · Look closer", "Not only Pis.", "A bay two cells wide and two rows high takes a Jetson Orin Nano developer kit, on its own tray."],
  [B4 + 0.1, B1 - 0.3, "Act two · Look closer", "Room to breathe.", "A Jetson AGX Orin developer kit has its fan in its top face, so its bay stands three rows high."],
  [79.6 + HOLD, 85.2 + HOLD, "Act three", "Make it yours.", "Pick a size and its colours. The list is what would be in the box."],
].map(([a, b, kicker, head, body]) => {
  const el = document.createElement("div");
  el.className = "cap";
  el.innerHTML = `<small>${kicker}</small><h2>${head}</h2>${body ? `<p>${body}</p>` : ""}`;
  $("captions").append(el);
  return { a, b, el };
});
// Each note: when its shot runs, where it points (CAD, in the first cell's
// frame), which part it rides, where its label sits from that point (px).
const NOTES = [
  [54.6, 61.6, [-12, -5.5, 38.5], "", [230, -130], "Pull", "A rail along the whole top edge."],
  [54.6, 61.6, [-12, 0, 30], "", [230, -45], "Air in", "Five tall slots, with a 25 mm fan behind the middle three."],
  [54.6, 61.6, [-22, 0, 13], "", [250, 45], "Label", "A flat 44 mm wide, sunk to protect a label’s edges."],
  [54.6, 61.6, [-30, 0, 6.9], "", [240, 135], "Card", "The one opening low in the face: the card comes out here."],
  [54.6, 61.6, [-65.5, 0, 21], "", [-200, 40], "Rim", "3 mm of sleeve frames every face."],
  [54.6, 61.6, [-50, 0, 43.8], "", [-200, -80], "Reveal", "3.6 mm between neighbours. The joint lives in it."],
  [63.6, 69.4, [-33.5, 30, 45.1], "", [-230, -95], "Rail", "A T on the top and one side of every cell."],
  [63.6, 69.4, [-39.5, 22, 43.4], "", [-260, 5], "Play", "0.8 mm sideways, so a wall still goes together when parts vary."],
  [63.6, 69.4, [-33.5, 12, 45.1], "", [-200, 120], "Hold", "A notch here takes a sprung tooth when the cell is home."],
  [63.6, 69.4, [-40, 10, 42.4], "B", [-250, -190], "Lips", "A pair on the bottom and the other side. A cell stands on them."],
  [72.2, 77.5, [-33.5, 5.6, 25], "out", [-250, 70], "Fan", "A 25 mm fan drops into a cradle behind the face and draws air in over the board."],
  [72.2, 77.5, [-33.5, -4, 38.5], "out", [-150, -110], "Pull and face", "One piece with the plate. Pull the face and everything comes."],
  [72.2, 77.5, [-33.5, 45, 8.2], "out", [-60, 170], "The board", "A Raspberry Pi 5 on four posts, set on its own hole pattern."],
  [72.2, 77.5, [-33.5, 52, 24], "out", [60, -250], "Cooler", "Room above the board for the Active Cooler and a PoE HAT."],
  [72.2, 77.5, [-33.5, 98, 17], "out", [300, -60], "Ports", "Ethernet and USB leave through the back wall, so every cable runs behind."],
  [72.2, 77.5, [-33.5, 103, 2.4], "out", [210, 60], "Latch", "Two fingers drop behind the sleeve’s rear edge, then rest straight."],
  [81, 86.4, [-15.75, 122, 15.5], "", [-230, -50], "One cable", "Power and network together, in at the back."],
  [81, 86.4, [-43, 97, 17], "", [230, 40], "Ports", "Flush with the back wall, clear of the latch fingers below."],
  [81, 86.4, [-33.5, 97, 32], "", [200, -120], "Air out", "Five slots above the ports. Front to back, straight through."],
  [B0 + 4.2, B2 - 2.6, [-196, 0, 84], "", [-190, -80], "The bay", "As wide as three cells, with their rails and lips in the same places."],
  [B0 + 4.2, B2 - 2.6, [-104, 45, 75.6], "shelf", [280, -200], "A switch", "Strapped to the shelf through slots at three widths. Nothing is fitted to one model."],
  [B0 + 4.2, B2 - 2.6, [-24, 0, 62], "shelf", [250, 120], "The shelf", "Slides and latches like a carrier, behind the same closed face."],
  [B2 + 0.9, B2 + 3.3, [-196, 0, 120], "", [-190, -70], "Tall bay", "Two rows high: taller gear, or one rack unit up to 200 mm wide."],
  [B2 + 5.6, B2 + 8.0, [-270, 0, 120], "", [-170, -70], "Rack bay", "Four cells wide: ten-inch rack gear, one unit tall, with its ears on."],
  [B3 + 2.0, B4 - 1.6, [-126, 0, 120], "", [-190, -70], "Jetson bay", "The board on four posts at NVIDIA’s own hole spacing, with 35 mm of air above its cooler."],
  [B4 + 2.0, B1 - 2.0, [-126, 0, 165], "", [-190, -70], "AGX bay", "The kit stands between low fences with 50 mm of air above its fan. Nothing straps over it."],
].map(([a, b, at, rides, off, head, body], i, all) => {
  const el = document.createElement("div");
  el.className = "label" + (off[0] < 0 ? " left" : "");
  el.innerHTML = `<b>${head}</b><span>${body}</span>`;
  $("labels").append(el);
  const ns = "http://www.w3.org/2000/svg";
  const line = document.createElementNS(ns, "line"), dot = document.createElementNS(ns, "circle");
  dot.setAttribute("r", 3); $("leaders").append(line, dot);
  const nth = all.slice(0, i).filter((n) => n[0] === a).length;
  return { a: a + 0.5 + nth * 0.6, b, at, rides, off, el, line, dot };
});

// -------------------------------------------------------------- the timeline
let clock = still === null ? 0 : +still, T = 0, wasConfig = false;
const bg = new THREE.Color(), ink = new THREE.Color(), tmp = new THREE.Color();
const eased = { cols: 3, rows: 3, bay: 0 };
const seg = (a, b) => clamp01((T - a) / (b - a));
const segc = (a, b) => clamp01((clock - a) / (b - a));
const place = (obj, x, y, z) => obj.position.set(x, z, -y);

function frame(dt) {
  const config = T >= CONFIG_AT, study = T >= 52.5 && T < 79, act3 = T >= 79;
  const rate = 1 - Math.exp(-dt * 5), jump = config && !wasConfig ? 1 : rate;
  wasConfig = config;

  // ground and ink
  const day = io(seg(6, 9));
  bg.setHex(PAL.night).lerp(tmp.setHex(PAL.day), day);
  scene.background.copy(bg);
  ink.setHex(PAL.inkNight).lerp(tmp.setHex(PAL.inkDay), day);
  const root = document.documentElement.style;
  root.setProperty("--bg", `#${bg.getHexString(THREE.SRGBColorSpace)}`);
  root.setProperty("--ink", `#${ink.getHexString(THREE.SRGBColorSpace)}`);
  root.setProperty("--soft", day > 0.5 ? "rgba(31,34,36,0.66)" : "rgba(231,231,226,0.62)");

  // the section line
  loops[0].line.geometry.instanceCount = Math.round(loops[0].n * io(seg(0.9, 4)));
  loops[1].line.geometry.instanceCount = Math.round(loops[1].n * io(seg(3.2, 4.6)));
  for (const l of loops) { l.line.material.opacity = 1 - seg(7.2, 9); l.line.visible = T < 9; }

  // sleeves: one colour for all of them
  tmp.setHex(PAL[act3 ? cfg.sleeve : "graphite"]);
  M.sleeve.color.lerp(tmp, jump === 1 ? 0.2 : rate); M.ghost.color.copy(M.sleeve.color);
  const pale = M.sleeve.color.getHSL({}).l > 0.5;
  M.sleeveLine.color.setHex(pale ? 0x8d8b84 : 0x4a4f54); M.ghostLine.color.copy(M.sleeveLine.color);
  const ghost = io(seg(70.6, 72)) - io(seg(77.6, 79));
  M.ghost.opacity = 1 - 0.9 * ghost; M.ghost.depthWrite = ghost < 0.05;
  M.ghostLine.opacity = 0.55 + 0.4 * ghost;

  // the wall's size, and how far it has risen onto its bases
  const cols = config ? cfg.cols : 3, rows = config ? cfg.rows : 3;
  eased.cols = mix(eased.cols, cols, config ? rate : 1); eased.rows = mix(eased.rows, rows, config ? rate : 1);
  const lift = study ? 0 : config ? 1 : act3 ? io(seg(82.2, 83.8)) : io(seg(29.5, 31.3));
  const backB = 46 * (io(seg(62.2, 63.6)) - io(seg(69.2, 70.2)));

  units.forEach((u, i) => {
    let arr = 0, out = 0;
    if (config) arr = u.arr + ((u.c < cols && u.r < rows ? 1 : 0) - u.arr) * rate;
    else if (i > 8) arr = 0;
    else if (study) arr = i === 0 ? 1 : i === 1 ? 1 - seg(70, 71.4) : 0;
    else if (i === 0) arr = 1;
    else if (act3) arr = seg(79.4 + (i - 1) * 0.3, 81.2 + (i - 1) * 0.3);
    else arr = i === 1 ? seg(19.6, 23) : seg(24.6 + (i - 2) * 0.55, 26.6 + (i - 2) * 0.55);
    if (config && Math.abs(arr - Math.round(arr)) < 0.002) arr = Math.round(arr);
    // The bay's shot borrows two cells to stand beside the first.
    if (!config && (i === 2 || i === 4)) arr = Math.max(arr, segc(B0 + 0.1 + i * 0.15, B0 + 1.7 + i * 0.15) * (1 - segc(B1 - 1.3, B1 - 0.1)));
    // And a fourth, for the rack bay.
    if (!config && u.c === 3 && u.r === 0) arr = segc(B2 + 3.4, B2 + 4.8) * (1 - segc(B3 - 1.1, B3 + 0.1));
    u.arr = arr;
    u.group.visible = arr > 0.001 && (i > 0 || T >= 5);
    place(u.group, -u.c * PX, -(1 - eo(arr)) * 360 + (i === 1 && study ? backB : 0), u.r * PZ + lift * LIFT);
    if (i === 0) {
      const grow = T < 10 ? Math.max(0.001, io(seg(5, 8.6))) : 1;
      u.sleeve.scale.z = grow; u.sleeve.position.z = -100 * (1 - grow);
      u.inner.visible = T >= 10; u.pi.visible = T >= 11.4;
      u.pi.position.y = T < 14 ? 110 * (1 - eo(seg(11.4, 13.6))) : 0;
      out = T < 13.8 ? 150 + 420 * (1 - eo(seg(10, 12))) : T < 20 ? 150 * (1 - io(seg(13.8, 16.4)))
        : 62 * (io(seg(70.6, 72)) - io(seg(77.6, 79)));
    }
    if (i === 3 && !config) out = 62 * (io(seg(43.5, 45)) - io(seg(45.9, 47.2)));
    u.inner.position.z = out;
    if (config) u.tint.lerp(tmp.setHex(look("config", u.c, u.r)), jump === 1 ? 1 : rate * 1.4);
    else filmTint(T, u.c, u.r, u.tint);
    u.face.color.copy(u.tint);
  });

  const crowned = config ? bayCount() : 0, extra = config ? bayRows() : 0;
  eased.bay = mix(eased.bay, extra, config ? rate : 1);
  const shelfOut = config ? 0 : mix(420, 92, eo(segc(B0 + 3.2, B0 + 4.8))) * (1 - io(segc(B2 - 2.7, B2 - 1.9)));
  bays.forEach((b, k) => {
    b.arr = config ? b.arr + ((cfg.bay === "bay" && k < crowned ? 1 : 0) - b.arr) * rate
      : k ? 0 : segc(B0 + 1.8, B0 + 3.4) * (1 - segc(B2 - 1.7, B2 - 0.5));
    b.group.visible = b.arr > 0.002;
    place(b.group, -k * 3 * PX, -(1 - eo(b.arr)) * 360, config ? LIFT + eased.rows * PZ : PZ);
    b.inner.position.z = shelfOut; b.inner.visible = config || clock > B0 + 3.2;
    b.face.color.lerp(tmp.setHex(config ? look("config", 1 + 3 * k, cfg.rows) : PAL.slate), config ? rate * 1.4 : 1);
  });
  const SHOTS = { tall: [B2 - 0.4, B2 + 1.2, B2 + 3.1, B2 + 4.1, PAL.teal], rack: [B2 + 4.4, B2 + 6, B3 - 1.3, B3 - 0.1, PAL.ochre],
    jetson: [B3, B3 + 1.6, B4 - 1.3, B4 - 0.1, PAL.moss], agx: [B4, B4 + 1.6, B1 - 1.9, B1 - 0.7, PAL.lilac] };
  for (const kind of ["tall", "rack", "jetson", "agx"]) {
    const { pool: made, wide } = CROWNS[kind], [a0, a1, z0, z1, hex] = SHOTS[kind];
    const film = segc(a0, a1) * (1 - segc(z0, z1));
    made.forEach((b, k) => {
      b.arr = config ? b.arr + ((cfg.bay === kind && k < crowned ? 1 : 0) - b.arr) * rate : k ? 0 : film;
      b.group.visible = b.arr > 0.002;
      place(b.group, -k * wide * PX, -(1 - eo(b.arr)) * 360, config ? LIFT + eased.rows * PZ : PZ);
      if (config) b.face.color.lerp(tmp.setHex(look("config", 1 + wide * k, cfg.rows)), rate * 1.4);
      else b.face.color.setHex(hex);
    });
  }
  const show = (p, on, a, b) => { p.arr = config ? p.arr + ((on ? 1 : 0) - p.arr) * rate : on ? seg(a, b) : 0; p.m.visible = p.arr > 0.002; return eo(p.arr); };
  const rise = act3 ? 82.4 : 30, cap = act3 ? 83.4 : 31.6, wallUp = !study && T >= 24;
  bases.forEach((p, c) => place(p.m, -c * PX, (1 - show(p, wallUp && c < cols, rise + c * 0.25, rise + 1.7 + c * 0.25)) * 320, -2.6));
  tops.forEach((p, c) => place(p.m, -c * PX, -(1 - show(p, wallUp && c < cols, cap + c * 0.2, cap + 1.3 + c * 0.2)) * 140, LIFT + (eased.rows + eased.bay) * PZ));
  rails.forEach((p, r) => place(p.m, -eased.cols * PX, -(1 - show(p, wallUp && r < rows + extra, cap + 0.4 + r * 0.2, cap + 1.7 + r * 0.2)) * 140, LIFT + r * PZ));
  lips.forEach((p, r) => place(p.m, CAP, -(1 - show(p, wallUp && r < rows + extra, cap + 0.4 + r * 0.2, cap + 1.7 + r * 0.2)) * 140, LIFT + r * PZ));

  // camera
  const want = config ? wallCam() : filmCam(T);
  if (!config && T > 80.5) { const w = wallCam(), k = io(seg(80.5, 85.3)); for (const n in want) want[n] = mix(want[n], w[n], k); }
  const rear = io(segc(78.6, 80.8)) * (1 - io(segc(79 + REAR - 1.4, 79 + REAR + 0.8)));
  if (rear > 0) {
    const back = { x: -33.5, y: 100, z: 20, az: 150 + 10 * segc(80, 79 + REAR), el: 13, d: 420 };
    for (const n in want) want[n] = mix(want[n], back[n], rear);
  }
  const overBay = config ? 0 : io(segc(B0 - 0.6, B0 + 1.4)) * (1 - io(segc(B1 - 1.2, B1 + 0.6)));
  if (overBay > 0) {
    const grown = io(segc(B2 - 0.6, B2 + 1)), wider = io(segc(B2 + 3.2, B2 + 4.8)) * (1 - io(segc(B3 - 0.8, B3 + 0.8))), taller = io(segc(B4 - 0.8, B4 + 0.8));
    const b = { x: mix(-104, -138, wider), y: 10, z: mix(44, 64, grown) + 22 * taller, az: 32 - 8 * segc(B0, B1), el: 17, d: mix(720, 860, grown) + 90 * wider + 90 * taller };
    for (const n in want) want[n] = mix(want[n], b[n], overBay);
  }
  cable.visible = rear > 0.02;
  cable.position.z = -((1 - eo(segc(80.2, 81.6))) * 150 + io(segc(79 + REAR - 1.6, 79 + REAR - 0.4)) * 150);
  for (const n in cam) cam[n] = mix(cam[n], want[n], config && jump !== 1 ? rate : 1);
  aim(cam, config ? 1 : Math.max(1, (study || rear > 0.5 || overBay > 0.5 ? 1.75 : 1.25) / (innerWidth / innerHeight)));
  const aside = config ? 1 : io(seg(80.5, 85.3));
  if (aside > 0) {
    const wide = innerWidth > 760;
    camera.setViewOffset(innerWidth, innerHeight, wide ? aside * 0.15 * innerWidth : 0, wide ? 0 : aside * 0.22 * innerHeight, innerWidth, innerHeight);
  } else if (camera.view) camera.clearViewOffset();

  // words
  const fade = (a, b, e = 0.5) => Math.min(segc(a, a + e), 1 - segc(b - e, b));
  const set = (el, o) => { el.style.opacity = o; el.style.visibility = o > 0.004 ? "visible" : "hidden"; };
  set($("hero"), 1 - seg(0.25, 1.4));
  for (const c of CAPS) set(c.el, fade(c.a, c.b));
  set($("card"), Math.min(seg(49.4, 51), 1 - seg(53.4, 54.4)));
  const small = innerWidth < 760 ? 0.5 : Math.min(1, innerWidth / 1300 + 0.15), p = new THREE.Vector3();
  const outA = units[0].inner.position.z;
  for (const n of NOTES) {
    const k = Math.min(segc(n.a, n.a + 0.7), 1 - segc(n.b - 0.5, n.b));
    set(n.el, clamp01(k * 2 - 1));
    n.line.style.visibility = n.dot.style.visibility = k > 0.004 ? "visible" : "hidden";
    if (k <= 0.004) continue;
    p.copy(v(n.at[0], n.at[1] - (n.rides === "out" ? outA : n.rides === "shelf" ? shelfOut : 0) + (n.rides === "B" ? backB : 0), n.at[2] + (n.rides === "B" ? PZ : 0))).project(camera);
    const x = (p.x + 1) / 2 * innerWidth, y = (1 - p.y) / 2 * innerHeight, w = n.el.offsetWidth;
    const left = n.off[0] < 0;
    let lx = x + n.off[0] * small, ly = y + n.off[1] * small;
    lx = left ? Math.max(lx, w + 12) : Math.min(lx, innerWidth - w - 12);
    if (innerWidth < 760) lx = left ? w + 12 : innerWidth - w - 12;
    ly = Math.min(Math.max(ly, 70), innerHeight - 90);
    const e = io(clamp01(k * 2));
    n.dot.setAttribute("cx", x); n.dot.setAttribute("cy", y);
    n.line.setAttribute("x1", x); n.line.setAttribute("y1", y);
    n.line.setAttribute("x2", mix(x, lx, e)); n.line.setAttribute("y2", mix(y, ly + 26, e));
    n.el.style.left = `${left ? lx - w : lx}px`; n.el.style.top = `${ly}px`;
  }
  const panel = $("panel");
  if (panel.hidden === config) { panel.hidden = !config; }
  $("play").hidden = config;
  renderer.render(scene, camera);
}

// ------------------------------------------------------------- configurator
const PRESETS = { One: [1, 1], Trio: [3, 1], Nine: [3, 3], Twelve: [4, 3] };
const LOOK_NAMES = { monolith: "Monolith", voice: "One voice", run: "Run", roles: "Roles", signal: "Signal" };
const css = (hex) => `#${hex.toString(16).padStart(6, "0")}`;
function choices(id, items, current, pick, dot) {
  const el = $(id);
  el.innerHTML = items.map(([k, label]) => dot
    ? `<button type="button" class="dot" data-k="${k}" aria-label="${k}" aria-pressed="${k === current}" style="background:${css(PAL[k])}"></button>`
    : `<button type="button" data-k="${k}" aria-pressed="${k === current}">${label}</button>`).join("");
  el.onclick = (e) => { const b = e.target.closest("button"); if (b) { pick(b.dataset.k); panel(); } };
}
function panel() {
  const { cols, rows } = cfg, n = cols * rows;
  $("colsN").textContent = cols; $("rowsN").textContent = rows;
  choices("presets", Object.keys(PRESETS).map((k) => [k, k]), Object.keys(PRESETS).find((k) => PRESETS[k][0] === cols && PRESETS[k][1] === rows), (k) => { [cfg.cols, cfg.rows] = PRESETS[k]; });
  choices("sleeves", [["graphite"], ["putty"], ["bone"]], cfg.sleeve, (k) => { cfg.sleeve = k; }, true);
  choices("looks", Object.entries(LOOK_NAMES), cfg.look, (k) => { cfg.look = k; });
  $("hues").hidden = cfg.look !== "voice";
  choices("hues", HUES.map((h) => [h]), cfg.hue, (k) => { cfg.hue = k; }, true);
  const crown = bayCount(), kind = CROWNS[cfg.bay], high = rows + bayRows();
  choices("bays", [["none", "None"], ["bay", "Bay"], ["tall", "Tall bay"], ["rack", "Rack bay"], ["jetson", "Jetson bay"], ["agx", "AGX bay"]], cfg.bay, (k) => { cfg.bay = k; });
  $("bayNote").textContent = !kind ? "A bay across the top holds a switch or a hub, with its ports to the back."
    : !crown ? { rack: "A rack bay is four cells wide: it needs four columns.", jetson: "A Jetson bay is two cells wide: it needs two, four or six columns.",
      agx: "An AGX bay is two cells wide: it needs two, four or six columns." }[cfg.bay] || "A bay is three cells wide: it needs three or six columns."
    : cfg.bay === "jetson" ? `Two rows high. ${crown === 1 ? "It takes" : "Each takes"} one Jetson Orin Nano developer kit, on a tray with posts at the board’s own holes.`
    : cfg.bay === "agx" ? `Three rows high. ${crown === 1 ? "It takes" : "Each takes"} one Jetson AGX Orin developer kit, standing between low fences with its top fan clear.`
    : cfg.bay === "tall" ? "Two rows high: taller gear, or one rack unit up to 200 mm wide."
    : cfg.bay === "rack" ? "Takes ten-inch rack gear, one unit tall, with its ears on."
    : n > 7 * crown ? `An eight-port switch serves seven Pis and an uplink. These ${n} need ${Math.ceil(n / 7)} switches; there is room for ${crown}.`
    : `Room for ${crown === 1 ? "one eight-port switch" : "two eight-port switches"}: enough ports for these ${n} Pis and an uplink.`;
  const bayName = { bay: "Bays", tall: "Tall bays", rack: "Rack bays", jetson: "Jetson bays", agx: "AGX bays" }[cfg.bay], bayGrams = { bay: 247.33 + 50.4, tall: 340.37 + 72.75, rack: 491.05 + 97.48, jetson: 191.62 + 44.29, agx: 224.0 + 60.38 }[cfg.bay] || 0;
  $("box").innerHTML = [["Cells", n], ["Carriers", n], ["Bases", cols], ["Top caps", cols], ["Side caps", 2 * high], ...(crown ? [[bayName, crown], [{ jetson: "Orin trays", agx: "AGX trays" }[cfg.bay] || "Shelves", crown]] : [])]
    .map(([a, b]) => `<tr><td>${a}</td><td>${b}</td></tr>`).join("");
  const grams = 1.01 * (n * (73.06 + 15.86) + cols * (64.31 + 17.38) + high * (10.74 + 11.08) + crown * bayGrams);
  $("facts").textContent = `${Math.round(cols * PX - man.gap + 2 * CAP)} mm wide, ${Math.round(high * PZ + 28.6)} tall, ${crown && cfg.bay === "agx" ? 127 : 110} deep. `
    + `About ${(grams / 1000).toFixed(grams < 1000 ? 2 : 1)} kg of printed parts. With a Pi in every cell: about ${(n * 6.2).toFixed(0)} W at typical work, `
    + `${(n * 14.3).toFixed(0)} W flat out.` + (crown && cfg.bay === "jetson" ? ` Each Jetson adds up to 25 W.` : crown && cfg.bay === "agx" ? ` Each AGX Orin adds up to 60 W.` : "");
}
const bump = (k, by, lo, hi) => () => { cfg[k] = Math.min(hi, Math.max(lo, cfg[k] + by)); panel(); };
$("colsDown").onclick = bump("cols", -1, 1, 6); $("colsUp").onclick = bump("cols", 1, 1, 6);
$("rowsDown").onclick = bump("rows", -1, 1, 4); $("rowsUp").onclick = bump("rows", 1, 1, 4);
panel();
let grab = null;
canvas.addEventListener("pointerdown", (e) => { if (T >= CONFIG_AT) grab = { x: e.clientX, az: orbit }; });
addEventListener("pointermove", (e) => { if (grab) orbit = Math.max(-70, Math.min(70, grab.az - (e.clientX - grab.x) * 0.25)); });
addEventListener("pointerup", () => { grab = null; });

// ------------------------------------------------------------------ driving
function size() {
  renderer.setSize(innerWidth, innerHeight, false);
  camera.aspect = innerWidth / innerHeight; camera.updateProjectionMatrix();
  for (const l of loops) l.line.material.resolution.set(innerWidth, innerHeight);
  $("track").style.height = still === null ? `${TOTAL * PX_PER_S + innerHeight}px` : "0";
}
addEventListener("resize", size); size();
const span = () => document.documentElement.scrollHeight - innerHeight;
// The score: a looping instrumental, made with ElevenLabs Music. A browser
// plays sound only after a click, so it starts from a button, and fades.
const score = new Audio("assets/score.mp3");
score.loop = true; score.preload = "auto"; score.volume = 0;
let sound = false, level = 0, byPlay = false;  // byPlay: the film turned the sound on, so pausing it turns it off
function setSound(on) {
  sound = on;
  $("sound").textContent = on ? "Turn sound off" : "Turn sound on";  // the button says what a click will do
  $("sound").setAttribute("aria-pressed", on);
  if (on) score.play().catch(() => setSound(false));
}
$("sound").onclick = () => { byPlay = false; setSound(!sound); };
window.dado = { score, get sound() { return sound; } };  // for checking the sound from outside
let playing = false;
// Pausing with the button also stops music the film started; scrolling by hand or reaching the end does not.
const stop = (quiet) => { playing = false; $("play").textContent = "Play the film"; if (quiet === true && byPlay) { byPlay = false; setSound(false); } };
$("play").onclick = () => {
  if (playing) return stop(true);
  playing = true; $("play").textContent = "Pause";
  if (!sound) { byPlay = true; setSound(true); }
};
for (const ev of ["wheel", "touchstart", "keydown"]) addEventListener(ev, (e) => { if (!e.target.closest?.(".tools")) stop(); }, { passive: true });
$("hint").textContent = "Scroll to unfold it, or play the film";

const timer = new THREE.Timer();
timer.connect(document);
renderer.setAnimationLoop(() => {
  timer.update();
  const dt = Math.min(timer.getDelta(), 0.1);
  if (playing) {
    scrollTo(0, scrollY + dt * PX_PER_S * 1.6);
    if (scrollY >= span() - 1) stop();
  }
  level += ((sound ? 0.7 : 0) - level) * (1 - Math.exp(-dt * 2.5));
  score.volume = Math.min(1, Math.max(0, level));
  if (!sound && level < 0.01 && !score.paused) score.pause();
  const goal = (scrollY / Math.max(1, span())) * TOTAL;
  clock = still !== null ? +still : reduced ? goal : clock + (goal - clock) * (1 - Math.exp(-dt * 7));
  T = clock <= 79 ? clock : clock < 79 + HOLD ? 79 : clock - HOLD;
  frame(dt);
  document.documentElement.dataset.ready = "1";
});
