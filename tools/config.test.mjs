// Walks every wall the configurator's moves can reach, from every kind of
// start, and checks each one can be built. Run: node tools/config.test.mjs
import assert from "node:assert/strict";
import { Wall } from "../docs/config.js";

const bays = Object.keys(Wall.BAYS), key = (s) => `${s.bay}/${s.cols}x${s.rows}${s.rowGaps ? "/rows spaced" : ""}${s.colGaps ? "/columns spaced" : ""}`;
const moves = (s) => [
  ...bays.map((b) => Wall.setBay(s, b)), Wall.setBay(s, "nonsense"), Wall.setBay(s, "toString"),
  Wall.stepCols(s, 1), Wall.stepCols(s, -1), Wall.stepRows(s, 1), Wall.stepRows(s, -1),
  ...Object.keys(Wall.PRESETS).map((p) => Wall.setPreset(s, p)), Wall.setPreset(s, "nonsense"),
  Wall.toggleSpace(s, "rows"), Wall.toggleSpace(s, "cols"),
];

// 1. Anything at all repairs to a wall that can be built.
const junk = [undefined, null, "", "3", "x", -4, 0, 2.6, 99, NaN, Infinity, {}, "constructor"];
const starts = [Wall.repair()];
for (const bay of [...bays, ...junk]) for (const cols of [1, 2, 3, 4, 5, 6, ...junk]) for (const rows of [1, 4, ...junk]) {
  const s = Wall.repair({ bay, cols, rows, sleeve: "graphite", rowGaps: junk[(starts.length * 7) % junk.length] ?? true, colGaps: starts.length % 3 ? "1" : "yes" });
  assert.ok(Wall.valid(s), `repair gave ${key(s)} from ${String(bay)}, ${String(cols)}, ${String(rows)}`);
  assert.equal(s.sleeve, "graphite", "repair keeps what it does not own");
  starts.push(s);
}

// 2. Every move from a wall that can be built gives another, and nothing else changes.
const seen = new Map(), queue = [...starts];
while (queue.length) {
  const s = queue.pop();
  if (seen.has(key(s))) continue;
  seen.set(key(s), s);
  for (const next of moves(s)) {
    assert.ok(Wall.valid(next), `${key(s)} moved to ${key(next)}, which cannot be built`);
    assert.equal(next.sleeve, s.sleeve);
    queue.push(next);
  }
}

// 3. Every wall that can be built is reachable from the first one: nothing legal is locked out.
const all = [];
for (const bay of bays) for (const cols of Wall.widths(bay)) for (let rows = Wall.ROWS[0]; rows <= Wall.ROWS[1]; rows++)
  for (const rowGaps of [false, true]) for (const colGaps of [false, true]) {
    const s = { bay, cols, rows, rowGaps, colGaps };
    if (Wall.valid(s)) all.push(s);
  }
const fromStart = new Map(), todo = [Wall.repair()];
while (todo.length) { const s = todo.pop(); if (!fromStart.has(key(s))) { fromStart.set(key(s), s); todo.push(...moves(s)); } }
assert.deepEqual([...fromStart.keys()].sort(), all.map(key).sort());
assert.equal(seen.size, all.length);

for (const s of all) {
  const m = Wall.summary(s), kind = Wall.BAYS[s.bay];
  // 4. A bay crowns a whole number of bays; the parts are whole numbers; the words are there.
  assert.ok(Number.isInteger(m.crown) && (kind ? m.crown >= 1 : m.crown === 0), key(s));
  assert.equal(m.crown * (kind ? kind.wide : 0), kind ? s.cols : 0, key(s));
  for (const [name, count] of m.parts) assert.ok(name && Number.isInteger(count) && count > 0, `${key(s)} ${name} ${count}`);
  assert.ok(Wall.note(s).length > 20 && !/undefined|NaN/.test(Wall.note(s) + Wall.facts(s)), key(s));
  // 4b. Spacers: a kind is on only where it has a line to go in; a line of column spacers never runs under a bay;
  // every spacer's count is its lines times what they cross.
  const lines = Wall.spaced(s), count = Object.fromEntries(m.parts);
  assert.equal(s.rowGaps, lines.rows.length > 0, key(s));
  assert.equal(s.colGaps, lines.cols.length > 0, key(s));
  assert.equal(lines.rows.length, s.rowGaps ? s.rows - 1 : 0);
  for (const c of lines.cols) assert.equal((c + 1) % (kind ? kind.wide : 1), 0, `${key(s)}: a line after column ${c} is under a bay`);
  assert.equal(count["Row spacers"] ?? 0, lines.rows.length * s.cols);
  assert.equal(count["Column spacers"] ?? 0, lines.cols.length * m.high);
  assert.equal(count["Crosses"] ?? 0, lines.rows.length * lines.cols.length);
  assert.equal(count["Half bases"] ?? 0, lines.cols.length);
  for (const what of ["rows", "cols"]) {
    const next = Wall.toggleSpace(s, what);
    assert.equal(Wall.canSpace(s, what), key(next) !== key(s), key(s));
    if (next !== s) assert.equal(key(Wall.toggleSpace(next, what)), key(s));
  }
  assert.ok(Wall.spaceNote(s).length > 20 && !/undefined|NaN/.test(Wall.spaceNote(s)), key(s));
  // 5. A stepper is live exactly when it would change the wall, and stepping back undoes stepping.
  for (const what of ["cols", "rows"]) for (const by of [1, -1]) {
    const step = what === "cols" ? Wall.stepCols : Wall.stepRows, next = step(s, by);
    assert.equal(Wall.canStep(s, what, by), key(next) !== key(s), key(s));
    const back = step(next, -by);  // stepping back undoes a step, except that spacers a smaller wall had to drop stay dropped
    if (next !== s) assert.deepEqual([back.bay, back.cols, back.rows], [s.bay, s.cols, s.rows]);
  }
  // 6. Choosing the bay a wall already has, or its own size as a preset, changes nothing.
  assert.equal(key(Wall.setBay(s, s.bay)), key(s));
  if (Wall.preset(s)) assert.equal(key(Wall.setPreset(s, Wall.preset(s))), key(s));
}
// 7. A preset always lands on its own size.
for (const s of all) for (const [name, [cols, rows]] of Object.entries(Wall.PRESETS)) {
  const next = Wall.setPreset(s, name);
  assert.deepEqual([next.cols, next.rows], [cols, rows]);
}
console.log(`ok: ${all.length} walls can be built, all reachable; ${starts.length} starts repaired; no move leaves them`);
