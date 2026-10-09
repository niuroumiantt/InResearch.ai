/* TA-11: one generic air-cooled accelerator server, not a measured OEM model.
 * Coordinates and all counts are illustration choices: front +z, rear -z.
 * The roof opening and animation explain assembly relationships, not servicing.
 * material(color, options) transfers newly created materials to this builder.
 * tag/label/explode keep ownership of their external registries/decorations;
 * explode follows rack3d's (object, dx, dy, dz, t0, t1) signature.
 */
export const STAGES = Object.freeze([
  Object.freeze([0, '① 通用服务器虚拟剖开 · 非维修步骤']),
  Object.freeze([0.05, '② 顶盖沿竖向抬升']),
  Object.freeze([0.25, '③ 载盘沿前置盘位轴移出']),
  Object.freeze([0.42, '④ 风扇模块沿竖向抬升']),
  Object.freeze([0.59, '⑤ 加速卡沿对应插槽竖向抬升']),
  Object.freeze([0.79, '⑥ 电源沿后舱轴移出 · 内外接口分开']),
]);

export function buildServerAssembly({THREE, material, tag, explode, label, spinners = []}) {
  if (!THREE) throw new TypeError('buildServerAssembly requires THREE');
  const root = new THREE.Group();
  root.name = 'generic-server-assembly';
  root.userData.genericIllustration = true;
  root.userData.frontAxis = '+z';
  root.userData.illustrativeSize = [6, 1.4, 10];
  const ownedGeometry = new Set(), ownedMaterial = new Set(), cache = new Map();
  const rotors = [], decorations = [], registrations = [];
  let disposed = false;
  const groups = {};
  for (const key of ['chassis', 'motherboard', 'CPU', 'DIMM', 'GPU', 'fan', 'drives', 'PSU', 'NIC', 'lid']) {
    const group = new THREE.Group(); group.name = key; root.add(group); groups[key] = group;
  }
  const mat = (color, options = {}) => {
    const result = material ? material(color, options) : new THREE.MeshStandardMaterial({
      color, roughness: 0.72, metalness: 0.25, ...options,
    });
    ownedMaterial.add(result); return result;
  };
  const palette = {
    metal: mat(0xb4b6af, {roughness: 0.72, metalness: 0.48}),
    edge: mat(0x737970, {roughness: 0.76, metalness: 0.38}),
    dark: mat(0x292e2a, {roughness: 0.82, metalness: 0.12}),
    chip: mat(0x1e2520, {roughness: 0.88, metalness: 0.04}),
    board: mat(0x345340, {roughness: 0.82, metalness: 0.08}),
    gold: mat(0xa9904e, {roughness: 0.70, metalness: 0.38}),
    latch: mat(0xae8c42, {roughness: 0.80, metalness: 0.12}),
    wire: mat(0x343c34, {roughness: 0.90, metalness: 0.04}),
  };
  function geometry(key, make) {
    if (!cache.has(key)) {
      const value = make(); cache.set(key, value); ownedGeometry.add(value);
    }
    return cache.get(key);
  }
  const box = (w, h, d) => geometry(`b:${w}:${h}:${d}`, () => new THREE.BoxGeometry(w, h, d));
  const cylinder = (r, h, n = 16) => geometry(`c:${r}:${h}:${n}`,
    () => new THREE.CylinderGeometry(r, r, h, n));
  const torus = (r, tube = 0.014) => geometry(`t:${r}:${tube}`,
    () => new THREE.TorusGeometry(r, tube, 6, 40));
  function mesh(parent, geo, surface, x, y, z, part = 'server') {
    const value = new THREE.Mesh(geo, surface); value.position.set(x, y, z);
    value.castShadow = value.receiveShadow = true;
    value.userData.part = part; parent.add(value);
    if (tag) tag(value, part);
    return value;
  }
  const block = (p, w, h, d, surface, x, y, z, part) =>
    mesh(p, box(w, h, d), surface, x, y, z, part);
  function module(parent, name, x, y, z) {
    const value = new THREE.Group(); value.name = name; value.position.set(x, y, z);
    value.userData.assemblyComponent = name; parent.add(value); return value;
  }
  function motion(object, dx, dy, dz, t0, t1) {
    object.userData.installationAxis = [dx ? Math.sign(dx) : 0, dy ? Math.sign(dy) : 0, dz ? Math.sign(dz) : 0];
    object.userData.assemblyHome = object.position.toArray();
    const registration = explode?.(object, dx, dy, dz, t0, t1);
    if (typeof registration === 'function') registrations.push(registration);
    else if (registration?.dispose) registrations.push(() => registration.dispose());
  }
  function screw(parent, x, y, z, axis = 'y', part = 'server') {
    const value = mesh(parent, cylinder(0.047, 0.027), palette.edge, x, y, z, part);
    const a = block(value, 0.052, 0.006, 0.009, palette.dark, 0, 0.017, 0, part);
    block(value, 0.009, 0.006, 0.052, palette.dark, 0, 0.017, 0, part);
    a.userData.atlasSkip = true;
    if (axis === 'x') value.rotation.z = -Math.PI / 2;
    if (axis === 'z') value.rotation.x = Math.PI / 2;
    return value;
  }
  function rod(parent, from, to, radius, surface, part = 'server') {
    const a = new THREE.Vector3(...from), b = new THREE.Vector3(...to);
    const delta = b.clone().sub(a), length = delta.length();
    const value = mesh(parent, cylinder(radius, length), surface,
      (a.x + b.x) / 2, (a.y + b.y) / 2, (a.z + b.z) / 2, part);
    value.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), delta.normalize());
    return value;
  }
  function plate(w, h, thickness, holes = []) {
    return geometry(`p:${w}:${h}:${thickness}:${JSON.stringify(holes)}`, () => {
      const shape = new THREE.Shape();
      shape.moveTo(-w / 2, -h / 2); shape.lineTo(w / 2, -h / 2);
      shape.lineTo(w / 2, h / 2); shape.lineTo(-w / 2, h / 2); shape.closePath();
      for (const hole of holes) {
        const path = new THREE.Path();
        if (hole.length === 3) path.absarc(hole[0], hole[1], hole[2], 0, Math.PI * 2, true);
        else {
          const [x, y, width, height] = hole;
          path.moveTo(x - width / 2, y - height / 2); path.lineTo(x - width / 2, y + height / 2);
          path.lineTo(x + width / 2, y + height / 2); path.lineTo(x + width / 2, y - height / 2); path.closePath();
        }
        shape.holes.push(path);
      }
      const geo = new THREE.ExtrudeGeometry(shape, {depth: thickness, bevelEnabled: false, curveSegments: 16});
      geo.translate(0, 0, -thickness / 2); return geo;
    });
  }
  function grille(parent, w, h, x, y, z, part, columns = 12, rows = 4) {
    for (const side of [-1, 1]) {
      block(parent, 0.035, h, 0.035, palette.edge, x + side * w / 2, y, z, part);
      block(parent, w, 0.035, 0.035, palette.edge, x, y + side * h / 2, z, part);
    }
    for (let i = 1; i < columns; i++) block(parent, 0.013, h, 0.023, palette.edge, x - w / 2 + w * i / columns, y, z, part);
    for (let i = 1; i < rows; i++) block(parent, w, 0.013, 0.023, palette.edge, x, y - h / 2 + h * i / rows, z, part);
  }

  // Folded chassis: actual openings, seam lips and fastening heads, no rack copy.
  block(groups.chassis, 6, 0.08, 10, palette.metal, 0, 0.04, 0);
  const vents = [];
  for (let k = 0; k < 14; k++) for (const y of [-0.30, 0, 0.30]) vents.push([-3.45 + k * 0.16, y, 0.047]);
  for (const side of [-1, 1]) {
    const wall = mesh(groups.chassis, plate(9.96, 1.26, 0.055, vents), palette.metal, side * 2.985, 0.72, 0);
    wall.rotation.y = Math.PI / 2;
    block(groups.chassis, 0.14, 0.045, 9.92, palette.edge, side * 2.92, 1.355, 0);
    block(groups.chassis, 0.16, 0.04, 9.9, palette.metal, side * 2.89, 0.12, 0);
    for (const z of [-4.7, -1.4, 1.4, 4.7]) screw(groups.chassis, side * 3.02, 1.12, z, 'x');
    const ear = mesh(groups.chassis, plate(0.38, 1.35, 0.07,
      [[0, -0.44, 0.078], [0, 0, 0.078], [0, 0.44, 0.078]]), palette.metal, side * 3.2, 0.72, 5.02);
    ear.name = 'rack-ear';
    rod(groups.chassis, [side * 3.38, 0.26, 5.1], [side * 3.38, 0.26, 5.35], 0.073, palette.dark);
    rod(groups.chassis, [side * 3.38, 1.16, 5.1], [side * 3.38, 1.16, 5.35], 0.073, palette.dark);
    rod(groups.chassis, [side * 3.38, 0.26, 5.35], [side * 3.38, 1.16, 5.35], 0.073, palette.dark);
  }
  const rearHoles = [[2.015, 0.01, 0.56, 1.10], [2.635, 0.01, 0.56, 1.10],
    [-2.6, 0.06, 0.30, 0.25], [-2.23, 0.06, 0.30, 0.25]];
  for (let k = 0; k < 15; k++) rearHoles.push([-1.68 + k * 0.22, 0.39, 0.048]);
  mesh(groups.chassis, plate(5.93, 1.25, 0.065, rearHoles), palette.metal, 0, 0.72, -5.0);
  block(groups.chassis, 5.72, 0.09, 0.15, palette.metal, 0, 1.33, 4.94);
  const roof = mesh(groups.lid, plate(5.88, 9.84, 0.035, [[0, 0, 5.36, 8.86]]), palette.metal, 0, 0, 0);
  roof.rotation.x = -Math.PI / 2; groups.lid.position.y = 1.41;
  groups.lid.userData.virtualCutaway = true;
  for (const side of [-1, 1]) block(groups.lid, 0.05, 0.016, 8.7, palette.edge, side * 2.82, 0.025, 0);
  motion(groups.lid, 0, 2.05, 0, 0.05, 0.20);

  // CPU/DIMM motherboard ends before the middle card cages; PSU lanes are separate.
  block(groups.motherboard, 4.52, 0.055, 3.35, palette.board, -0.55, 0.16, -2.92);
  for (const x of [-2.62, 1.52]) for (const z of [-4.42, -1.45]) screw(groups.motherboard, x, 0.20, z);
  for (const x of [-2.4, -1.6, -0.8, 0, 0.8, 1.45]) {
    block(groups.motherboard, 0.22, 0.07, 0.30, palette.chip, x, 0.23, -1.62);
    for (let k = 0; k < 2; k++) mesh(groups.motherboard, cylinder(0.059, 0.13), palette.metal, x + 0.15, 0.255, -1.57 - k * 0.20);
  }
  const cpuXs = [-1.90, 0.12];
  for (const [index, x] of cpuXs.entries()) {
    const cpu = module(groups.CPU, `cpu-${index + 1}`, x, 0, -3.20);
    block(cpu, 1.17, 0.10, 1.29, palette.dark, 0, 0.235, 0, 'cpu');
    block(cpu, 1.06, 0.09, 1.16, palette.metal, 0, 0.33, 0, 'cpu');
    for (let k = 0; k < 23; k++) block(cpu, 0.025, 0.68, 1.13, palette.metal, -0.50 + k * 1.0 / 22, 0.705, 0, 'cpu');
    for (const sx of [-0.53, 0.53]) for (const sz of [-0.59, 0.59]) screw(cpu, sx, 0.39, sz, 'y', 'cpu');
    const dimmXs = index ? [0.88, 1.04, 1.20, 1.36] : [-1.12, -0.96, -0.80, -0.64];
    for (const [slot, dx] of dimmXs.entries()) {
      const dimm = module(groups.DIMM, `dimm-${index * 4 + slot + 1}`, dx, 0, -3.20);
      block(dimm, 0.095, 0.13, 1.50, palette.dark, 0, 0.25, 0, 'dram');
      block(dimm, 0.045, 0.49, 1.38, palette.board, 0, 0.545, 0, 'dram');
      for (let k = 0; k < 18; k++) block(dimm, 0.052, 0.075, 0.04, palette.gold, 0, 0.325, -0.63 + k * 0.074, 'dram');
      for (let k = 0; k < 6; k++) for (const side of [-1, 1]) block(dimm, 0.038, 0.24, 0.16, palette.chip, side * 0.033, 0.56, -0.52 + k * 0.21, 'dram');
      for (const z of [-0.73, 0.73]) block(dimm, 0.11, 0.22, 0.07, palette.metal, 0, 0.29, z, 'dram');
    }
  }

  // Low horizontal card bodies along z. The vertical side PCB's lower contacts
  // face an upward socket, supported by an L-shaped illustrative riser board.
  // Riser + cage remain fixed when the card moves along y; no lateral socket.
  for (const [index, x] of [-1.48, 1.48].entries()) {
    const z = 0.59;
    const riser = module(groups.motherboard, `fixed-riser-${index + 1}`, x, 0, z);
    block(riser, 2.20, 0.05, 3.22, palette.board, 0, 0.18, 0, 'gpu');
    block(riser, 2.18, 0.36, 0.055, palette.board, 0, 0.36, -1.61, 'gpu');
    const slot = block(riser, 0.14, 0.14, 2.76, palette.dark, -0.78, 0.26, 0, 'gpu');
    slot.name = `accelerator-slot-${index + 1}`;
    slot.userData.insertionAxis = '+y';
    // A short generic link shows the riser belongs to the rear system board;
    // neither its conductor count nor routing is a specified PCIe topology.
    block(groups.motherboard, 0.28, 0.13, 0.10, palette.dark, x - 0.65, 0.255, -1.35, 'gpu');
    for (const offset of [-0.055, 0.055]) rod(groups.motherboard,
      [x - 0.65 + offset, 0.27, -1.30], [x - 0.65 + offset, 0.27, z - 1.645], 0.018, palette.wire, 'gpu');
    // Two rails leave the card and its slot visible, rather than a solid cage box.
    for (const side of [-1, 1]) {
      block(riser, 0.07, 0.10, 3.23, palette.metal, side * 1.09, 0.21, 0, 'gpu');
      for (const end of [-1, 1]) block(riser, 0.07, 0.77, 0.14, palette.metal, side * 1.09, 0.61, end * 1.54, 'gpu');
    }
    const gpu = module(groups.GPU, `accelerator-${index + 1}`, x, 0, z);
    gpu.userData.matingSlot = slot.name;
    block(gpu, 0.045, 0.67, 2.76, palette.board, -0.78, 0.62, 0, 'gpu');
    for (let k = 0; k < 28; k++) block(gpu, 0.052, 0.105, 0.055, palette.gold, -0.78, 0.318, -1.30 + k * 2.60 / 27, 'gpu');
    block(gpu, 1.75, 0.085, 2.73, palette.metal, 0.16, 0.395, 0, 'gpu');
    for (let k = 0; k < 35; k++) block(gpu, 0.025, 0.67, 2.69, palette.metal, -0.675 + k * 1.67 / 34, 0.77, 0, 'gpu');
    block(gpu, 1.76, 0.025, 2.75, palette.metal, 0.16, 1.118, 0, 'gpu');
    grille(gpu, 1.86, 0.74, 0.12, 0.77, 1.40, 'gpu', 13, 5);
    for (const end of [-1, 1]) for (const side of [-1, 1]) screw(gpu, side * 0.95, 1.12, end * 1.34, 'y', 'gpu');
    block(gpu, 0.19, 0.17, 0.24, palette.dark, 0.96, 0.64, -1.14, 'gpu');
    motion(gpu, 0, 2.12, 0, 0.59, 0.75);
  }

  // Four fan modules: circular open frames, motor, curved blades and guards.
  const fanHole = plate(1.20, 1.10, 0.075, [[0, 0, 0.46]]);
  const bladeGeometry = geometry('fan-blade', () => {
    const shape = new THREE.Shape(); shape.moveTo(0.10, -0.04);
    shape.quadraticCurveTo(0.28, -0.17, 0.435, -0.045);
    shape.quadraticCurveTo(0.42, 0.09, 0.16, 0.13); shape.lineTo(0.10, 0.045); shape.closePath();
    return new THREE.ExtrudeGeometry(shape, {depth: 0.018, bevelEnabled: false, curveSegments: 8});
  });
  block(groups.chassis, 5.67, 0.11, 0.71, palette.metal, 0, 0.14, 3.02);
  block(groups.motherboard, 5.58, 0.34, 0.045, palette.board, 0, 0.32, 2.63, 'server-fan');
  for (const [index, x] of [-2.10, -0.70, 0.70, 2.10].entries()) {
    const fan = module(groups.fan, `fan-${index + 1}`, x, 0.73, 3.02);
    for (const z of [-0.25, 0.25]) mesh(fan, fanHole, palette.dark, 0, 0, z, 'server-fan');
    for (const sx of [-0.54, 0.54]) for (const sy of [-0.48, 0.48]) rod(fan, [sx, sy, -0.25], [sx, sy, 0.25], 0.028, palette.metal, 'server-fan');
    const rotor = module(fan, 'rotor', 0, 0, -0.035); rotors.push(rotor); spinners.push(rotor);
    for (let k = 0; k < 7; k++) {
      const blade = mesh(rotor, bladeGeometry, palette.dark, 0, 0, 0, 'server-fan'); blade.rotation.z = k * Math.PI * 2 / 7;
    }
    const hub = mesh(rotor, cylinder(0.12, 0.17), palette.edge, 0, 0, 0.02, 'server-fan'); hub.rotation.x = Math.PI / 2;
    for (const r of [0.19, 0.31, 0.435]) mesh(fan, torus(r), palette.edge, 0, 0, 0.303, 'server-fan');
    for (let k = 0; k < 4; k++) {
      const angle = k * Math.PI / 2;
      rod(fan, [0, 0, 0.30], [0.44 * Math.cos(angle), 0.44 * Math.sin(angle), 0.30], 0.013, palette.edge, 'server-fan');
    }
    block(fan, 0.32, 0.065, 0.12, palette.metal, 0, 0.55, 0, 'server-fan');
    block(fan, 0.26, 0.09, 0.11, palette.gold, 0, -0.51, 0, 'server-fan');
    block(groups.motherboard, 0.33, 0.08, 0.16, palette.dark, x, 0.18, 3.02, 'server-fan');
    motion(fan, 0, 1.70, 0, 0.42, 0.55);
  }

  // Eight distinct front bays and rear-facing drive contacts/backplane sockets.
  block(groups.motherboard, 5.57, 1.10, 0.05, palette.board, 0, 0.70, 3.51, 'ssd');
  for (const x of [-2.8, -1.4, 0, 1.4, 2.8]) block(groups.chassis, 0.035, 1.16, 1.43, palette.metal, x, 0.73, 4.25);
  block(groups.chassis, 5.63, 0.025, 1.43, palette.metal, 0, 0.69, 4.25);
  for (let column = 0; column < 4; column++) for (let row = 0; row < 2; row++) {
    const x = -2.10 + column * 1.40, y = 0.42 + row * 0.55;
    const drive = module(groups.drives, `drive-${column * 2 + row + 1}`, x, y, 4.27);
    block(drive, 1.25, 0.04, 1.36, palette.metal, 0, -0.20, 0, 'ssd');
    for (const side of [-1, 1]) block(drive, 0.033, 0.33, 1.36, palette.edge, side * 0.62, -0.015, 0, 'ssd');
    block(drive, 1.10, 0.265, 1.20, palette.metal, 0, -0.015, -0.03, 'ssd');
    block(drive, 0.57, 0.11, 0.12, palette.dark, 0, -0.01, -0.68, 'ssd');
    for (let k = 0; k < 8; k++) block(drive, 0.046, 0.07, 0.015, palette.gold, -0.24 + k * 0.07, -0.01, -0.748, 'ssd');
    block(groups.motherboard, 0.63, 0.14, 0.095, palette.dark, x, y - 0.01, 3.54, 'ssd');
    grille(drive, 1.11, 0.33, -0.055, 0, 0.738, 'ssd', 14, 4);
    block(drive, 0.10, 0.23, 0.055, palette.latch, 0.51, 0, 0.79, 'ssd');
    block(drive, 0.10, 0.33, 0.06, palette.edge, -0.57, 0, 0.78, 'ssd');
    motion(drive, 0, 0, 1.72, 0.25, 0.38);
  }

  // Rear NIC: port openings face -z; sealed backshells face the interior +z.
  const nic = module(groups.NIC, 'rear-network-card', -2.43, 0, -4.73);
  block(nic, 1.01, 0.73, 0.045, palette.board, 0, 0.58, 0, 'nic');
  for (const x of [-0.17, 0.20]) {
    block(nic, 0.30, 0.25, 0.32, palette.metal, x, 0.78, -0.12, 'nic');
    // A recessed rear aperture, with no opening on the interior backshell.
    const aperture = block(nic, 0.235, 0.16, 0.016, palette.dark, x, 0.78, -0.294, 'nic');
    aperture.name = 'rear-network-aperture'; aperture.userData.facingAxis = '-z';
    for (let k = 0; k < 6; k++) block(nic, 0.012, 0.022, 0.015, palette.gold, x - 0.075 + k * 0.03, 0.72, -0.307, 'nic');
  }
  block(nic, 0.22, 0.23, 0.10, palette.chip, 0.28, 0.42, 0.074, 'nic');
  block(nic, 0.91, 0.07, 0.11, palette.dark, 0, 0.21, 0, 'nic');
  for (const x of [-0.41, 0.41]) screw(nic, x, 0.22, 0.11, 'y', 'nic');

  // PSU DC output faces +z, its mating interface stays inside the chassis.
  // The AC recess, handle and latch face -z, outside the rear wall.
  for (const [index, x] of [2.015, 2.635].entries()) {
    const psu = module(groups.PSU, `rear-psu-${index + 1}`, x, 0, -3.75);
    block(psu, 0.51, 1.04, 2.42, palette.metal, 0, 0.72, 0, 'psu');
    for (const side of [-1, 1]) block(psu, 0.018, 0.026, 2.37, palette.edge, side * 0.24, 1.252, 0, 'psu');
    const dc = block(psu, 0.43, 0.56, 0.045, palette.board, 0, 0.48, 1.235, 'psu');
    dc.name = 'internal-dc-interface'; dc.userData.facingAxis = '+z';
    for (let k = 0; k < 7; k++) block(psu, 0.038, 0.15, 0.03, palette.gold, -0.18 + k * 0.06, 0.43, 1.265, 'psu');
    block(groups.motherboard, 0.46, 0.065, 0.37, palette.board, x, 0.22, -2.26, 'psu');
    block(groups.motherboard, 0.45, 0.24, 0.08, palette.dark, x, 0.43, -2.42, 'psu');
    for (const px of [-0.16, 0.16]) rod(groups.motherboard, [x + px, 0.31, -2.25], [x + px, 0.31, -1.62], 0.028, palette.wire, 'psu');
    const ac = block(psu, 0.24, 0.25, 0.015, palette.dark, 0, 0.56, -1.238, 'psu');
    ac.name = 'external-ac-recess'; ac.userData.facingAxis = '-z';
    for (const [px, py] of [[-0.07, 0.52], [0.07, 0.52], [0, 0.61]])
      block(psu, 0.023, 0.055, 0.015, palette.metal, px, py, -1.25, 'psu');
    grille(psu, 0.43, 0.24, 0, 1.02, -1.245, 'psu', 6, 3);
    for (const side of [-1, 1]) rod(psu, [side * 0.17, 0.27, -1.27], [side * 0.17, 0.27, -1.51], 0.031, palette.edge, 'psu');
    rod(psu, [-0.17, 0.27, -1.51], [0.17, 0.27, -1.51], 0.031, palette.edge, 'psu');
    block(psu, 0.075, 0.19, 0.10, palette.latch, 0.245, 0.53, -1.29, 'psu');
    motion(psu, 0, 0, -2.15, 0.79, 0.95);
  }

  // External drawing callbacks own their label textures; hide/detach on disposal.
  if (label) for (const [text, x, y, z, after] of [
    ['虚拟剖开 · 非维修步骤', 0, 3.8, 0, 0],
    ['CPU / DIMM 主板区', -3.9, 1.8, -3.2, 0.08],
    ['PCIe 加速卡与对应插槽', -4.0, 2.4, 0.5, 0.59],
    ['横向风扇行', 3.9, 2.2, 3.02, 0.42],
    ['前置载盘与背板', -3.7, 1.4, 5.2, 0.25],
    ['后舱电源 · 内 DC / 外 AC', 3.9, 2.1, -3.9, 0.79],
  ]) {
    const decoration = label(text, x, y, z, 0.72, null, null, after);
    if (decoration?.isObject3D) {root.add(decoration); decorations.push(decoration);}
  }
  const counts = Object.freeze({server: 1, cpu: groups.CPU.children.length,
    dram: groups.DIMM.children.length, gpu: groups.GPU.children.length,
    ssd: groups.drives.children.length, nic: groups.NIC.children.length,
    psu: groups.PSU.children.length, 'server-fan': groups.fan.children.length});
  root.userData.exampleCounts = counts;
  return {root, groups, counts, stages: STAGES, dispose() {
    if (disposed) return;
    disposed = true;
    for (const release of registrations) release();
    for (const rotor of rotors) {
      const index = spinners.indexOf(rotor); if (index >= 0) spinners.splice(index, 1);
    }
    for (const decoration of decorations) {decoration.visible = false; decoration.removeFromParent();}
    root.removeFromParent();
    for (const geo of ownedGeometry) geo.dispose();
    for (const surface of ownedMaterial) surface.dispose();
    root.clear(); ownedGeometry.clear(); ownedMaterial.clear(); cache.clear();
  }};
}
