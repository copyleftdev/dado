// The wall a viewer may build in "Make it yours", and the only ways to change
// it. Every move returns a wall that can be built, so the page never has to
// draw or explain one that cannot: a bay always crowns a wall that is a whole
// number of bays wide, and spacers are on only where there is somewhere for
// them to go. config.test.mjs walks every wall these moves can reach.
export const Wall = (() => {
  const COLS = [1, 6], ROWS = [1, 4];
  const PITCH = 70.6, RISE = 45.6, GAP = 3.6, CAPS = 11.2, FOOT = 28.6, DEPTH = 110;  // mm
  const DENSITY = 1.01, PI_W = [6.2, 14.3];  // g/cm3 of PA12; watts a Pi, typical and flat out
  // Printed volume in cm3 of what every wall has: per cell, per column, per row.
  const CM3 = { cell: 73.06 + 15.86, column: 64.31 + 17.38, row: 10.74 + 11.08,
    rowSpacer: 52.49, colSpacer: 43.29, cross: 19.03, halfColumn: 41.43 + 10.32 };
  const SHAFT = 23;  // standard network cables a column of spacers takes
  // Each bay: places across, rows up, roof in mm, rows of air slots in its
  // face, cm3 of bay and tray together, and what stands in it if not a switch.
  const BAYS = {
    none: null,
    bay: { label: "Bay", plural: "Bays", tray: "Shelves", wide: 3, high: 1, roof: 7, airs: 1, cm3: 247.33 + 50.4 },
    tall: { label: "Tall bay", plural: "Tall bays", tray: "Shelves", wide: 3, high: 2, roof: 10, airs: 1, cm3: 340.37 + 72.75 },
    rack: { label: "Rack bay", plural: "Rack bays", tray: "Shelves", wide: 4, high: 2, roof: 12, airs: 1, cm3: 491.05 + 97.48 },
    jetson: { label: "Jetson bay", plural: "Jetson bays", tray: "Orin trays", wide: 2, high: 2, roof: 6, airs: 5, cm3: 191.62 + 44.29,
      guest: "Jetson", watts: 25 },
    agx: { label: "AGX bay", plural: "AGX bays", tray: "AGX trays", wide: 2, high: 3, roof: 6, airs: 9, cm3: 224.0 + 60.38,
      guest: "AGX Orin", watts: 60, depth: 127 },
  };
  const PRESETS = { One: [1, 1], Trio: [3, 1], Nine: [3, 3], Twelve: [4, 3] };
  const known = (bay) => Object.prototype.hasOwnProperty.call(BAYS, bay);
  const whole = (v, [lo, hi]) => { const n = Math.round(Number(v)); return Number.isFinite(n) ? Math.min(hi, Math.max(lo, n)) : lo; };

  // The widths a wall may have under a bay: whole numbers of that bay.
  function widths(bay) {
    const step = BAYS[bay] ? BAYS[bay].wide : 1, out = [];
    for (let c = step; c <= COLS[1]; c += step) if (c >= COLS[0]) out.push(c);
    return out;
  }
  // The allowed width nearest to a wanted one; the wider of two equally near.
  const nearest = (cols, list) => list.reduce((best, c) => (Math.abs(c - cols) <= Math.abs(best - cols) ? c : best));
  const crowns = (s) => (BAYS[s.bay] ? s.cols / BAYS[s.bay].wide : 0);
  // Spacers. A line of row spacers goes between each two rows of cells; a line of column
  // spacers between each two columns, or between each two bays, since a bay cannot stand
  // across one. A wall with nowhere for a line to go cannot have that kind switched on.
  const canSpace = (s, what) => (what === "rows" ? s.rows : crowns(s) || s.cols) >= 2;
  const settle = (s) => ({ ...s, rowGaps: Boolean(s.rowGaps) && canSpace(s, "rows"), colGaps: Boolean(s.colGaps) && canSpace(s, "cols") });
  const toggleSpace = (s, what) => {
    const key = what === "rows" ? "rowGaps" : "colGaps";
    return canSpace(s, what) ? { ...s, [key]: !s[key] } : s;
  };
  // Which rows and which columns have a line of spacers after them.
  function spaced(s) {
    const every = BAYS[s.bay] ? BAYS[s.bay].wide : 1, rows = [], cols = [];
    if (s.rowGaps) for (let r = 0; r < s.rows - 1; r++) rows.push(r);
    if (s.colGaps) for (let c = every - 1; c < s.cols - 1; c += every) cols.push(c);
    return { rows, cols };
  }
  const valid = (s) => known(s.bay) && widths(s.bay).includes(s.cols) && Number.isInteger(s.rows) && s.rows >= ROWS[0] && s.rows <= ROWS[1]
    && typeof s.rowGaps === "boolean" && typeof s.colGaps === "boolean" && (!s.rowGaps || canSpace(s, "rows")) && (!s.colGaps || canSpace(s, "cols"));

  // A wall from anything: a page address, an old saved choice, nonsense.
  function repair(raw = {}) {
    const bay = known(raw.bay) ? raw.bay : "none";
    const on = (v) => v === true || v === "1" || v === "true";
    return settle({ ...raw, bay, rows: whole(raw.rows ?? 3, ROWS), cols: nearest(whole(raw.cols ?? 3, COLS), widths(bay)), rowGaps: on(raw.rowGaps), colGaps: on(raw.colGaps) });
  }
  // Choosing a bay moves the wall to the nearest width that bay fits.
  const setBay = (s, bay) => (known(bay) ? settle({ ...s, bay, cols: nearest(s.cols, widths(bay)) }) : s);
  // Width steps through the widths the bay allows; height through the rows.
  function stepCols(s, by) {
    const list = widths(s.bay), to = list[list.indexOf(s.cols) + Math.sign(by)];
    return to === undefined ? s : settle({ ...s, cols: to });
  }
  function stepRows(s, by) {
    const to = s.rows + Math.sign(by);
    return to < ROWS[0] || to > ROWS[1] ? s : settle({ ...s, rows: to });
  }
  const canStep = (s, what, by) => (what === "cols" ? stepCols(s, by) : stepRows(s, by)) !== s;
  // A preset is a size. It keeps the bay if the bay fits that size, and lets it go if not.
  function setPreset(s, name) {
    if (!Object.prototype.hasOwnProperty.call(PRESETS, name)) return s;
    const [cols, rows] = PRESETS[name];
    return settle({ ...s, cols, rows, bay: widths(s.bay).includes(cols) ? s.bay : "none" });
  }
  const preset = (s) => Object.keys(PRESETS).find((k) => PRESETS[k][0] === s.cols && PRESETS[k][1] === s.rows);

  // What the wall is: its parts, size, mass and power.
  function summary(s) {
    const kind = BAYS[s.bay], crown = crowns(s), n = s.cols * s.rows, high = s.rows + (kind ? kind.high : 0);
    const parts = [["Cells", n], ["Carriers", n], ["Bases", s.cols], ["Top caps", s.cols], ["Side caps", 2 * high]];
    if (kind) parts.push([kind.plural, crown], [kind.tray, crown]);
    const lines = spaced(s), across = lines.rows.length, down = lines.cols.length;
    if (across) parts.push(["Row spacers", across * s.cols]);
    if (down) parts.push(["Column spacers", down * high], ["Half bases", down], ["Half top caps", down]);
    if (across && down) parts.push(["Crosses", across * down]);
    const grams = DENSITY * (n * CM3.cell + s.cols * CM3.column + high * CM3.row + (kind ? crown * kind.cm3 : 0)
      + across * s.cols * CM3.rowSpacer + down * (high * CM3.colSpacer + CM3.halfColumn) + across * down * CM3.cross);
    return { n, crown, high, parts, grams, across, down, wide: s.cols * PITCH - GAP + CAPS + down * PITCH / 2, tall: high * RISE + FOOT + across * RISE / 2,
      deep: (kind && kind.depth) || DEPTH,
      typical: n * PI_W[0], flatOut: n * PI_W[1] };
  }
  const facts = (s) => {
    const m = summary(s), kind = BAYS[s.bay], kg = m.grams / 1000;
    return `${Math.round(m.wide)} mm wide, ${Math.round(m.tall)} tall, ${m.deep} deep. About ${kg.toFixed(kg < 1 ? 2 : 1)} kg of printed parts. `
      + `With a Pi in every cell: about ${m.typical.toFixed(0)} W at typical work, ${m.flatOut.toFixed(0)} W flat out.`
      + (kind && kind.guest ? ` Each ${kind.guest} adds up to ${kind.watts} W.` : "");
  };
  // What the bay holds, and why the width moves the way it does under it.
  function note(s) {
    const kind = BAYS[s.bay], { n, crown } = summary(s), each = crown === 1 ? "It takes" : "Each takes";
    if (!kind) return "A bay across the top holds what is not a Pi: a switch, a hub or a Jetson.";
    const holds = {
      bay: n > 7 * crown ? `An eight-port switch serves seven Pis and an uplink. These ${n} need ${Math.ceil(n / 7)} switches; there is room for ${crown}.`
        : `Room for ${crown === 1 ? "one eight-port switch" : "two eight-port switches"}: enough ports for these ${n} Pis and an uplink.`,
      tall: "Two rows high: taller gear, or one rack unit up to 200 mm wide.",
      rack: "Takes ten-inch rack gear, one unit tall, with its ears on.",
      jetson: `Two rows high. ${each} one Jetson Orin Nano developer kit, on a tray with posts at the board’s own holes.`,
      agx: `Three rows high. ${each} one Jetson AGX Orin developer kit, standing between low fences with its top fan clear.`,
    }[s.bay];
    const fit = widths(s.bay).length === 1 ? `It is ${["", "", "two", "three", "four"][kind.wide]} cells wide, and so is the wall.`
      : `The wall widens ${["", "", "two", "three", "four"][kind.wide]} cells at a time to match it.`;
    return `${holds} ${fit}`;
  }
  // What the spacers are doing, or why a kind cannot be switched on.
  function spaceNote(s) {
    const { across, down } = summary(s), count = (n, one, many) => `${["No", "One", "Two", "Three", "Four", "Five"][n]} ${n === 1 ? one : many}`;
    const said = [];
    if (across) said.push(`${count(across, "line", "lines")} of row spacers: half a row of air between the rows, and a tray behind for cables to run across.`);
    if (down) said.push(`${count(down, "column", "columns")} of spacers: a shaft behind, top to bottom, for ${SHAFT} cables${down === 1 ? "" : " each"}.`);
    if (!across && !down) said.push("A spacer is half a place of room, for air and for cables.");
    if (!canSpace(s, "rows")) said.push("Row spacers go between rows: this wall has one.");
    if (!canSpace(s, "cols")) said.push(BAYS[s.bay] ? "Column spacers go between bays: this wall has one." : "Column spacers go between columns: this wall has one.");
    return said.join(" ");
  }
  return { COLS, ROWS, PITCH, RISE, GAP, BAYS, PRESETS, widths, valid, repair, setBay, stepCols, stepRows, canStep, setPreset, preset, crowns,
    canSpace, toggleSpace, spaced, summary, facts, note, spaceNote };
})();
