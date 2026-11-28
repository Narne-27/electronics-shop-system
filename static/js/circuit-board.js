/**
 * Electrodesk – Studio Motherboard Scene  (Stage 1 – v2)
 * ───────────────────────────────────────────────────────
 * PCB board, heatsink, screws, materials, studio lighting & camera.
 * Three.js r143 · ES-module · import-map ready.
 *
 * Exports:
 *   window.triggerBoardPowerOn(callback)
 *   window.initCircuitBoardScene()
 */

import * as THREE from 'three';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';

/* ═══════════════════════════════════════════════════════════
   0.  CONSTANTS & CONFIG
   ═══════════════════════════════════════════════════════════ */
const DPR_CAP = 2;
const FOV     = 30;
const ANISO   = 16;

const PAL = {
  pcbMask      : 0x0d1a2e,
  pcbEdge      : 0x05070c,
  pcbBottom    : 0x060912,
  copperTrace  : 0x173256,
  goldENIG     : 0xb89030,
  silkscreen   : 0xd8e0ec,
  heatsinkAlu  : 0x383f48,
  copperPipe   : 0xb87038,
  bracketSteel : 0x161b24,
  screwSteel   : 0x161a20,
  washerSteel  : 0x20252d,
};

const PCB_W = 6.0, PCB_D = 4.2, PCB_H = 0.10;

// Shared IC chip specs (UV fractions -> exact world X, Z & pad alignment)
const CHIP_SPECS = [
  { u: 0.13, v: 0.38, pw: 140, ph: 100, label: 'U1  MCU',  mark: 'ED-32F407\n2644A-IND' },
  { u: 0.74, v: 0.24, pw: 150, ph: 105, label: 'U2  VRM',  mark: 'TPS-54820\nPWM-CTRL' },
  { u: 0.72, v: 0.62, pw: 200, ph: 135, label: 'U3  NAND', mark: 'ED-NAND256\nREV 3.2' },
  { u: 0.20, v: 0.66, pw: 130, ph: 95,  label: 'U4  PHY',  mark: 'RTL-8125B\nGBE-PHY' },
  { u: 0.83, v: 0.43, pw: 120, ph: 90,  label: 'U5  BIOS', mark: 'MX25L128\nUEFI-ROM' },
  { u: 0.46, v: 0.72, pw: 160, ph: 110, label: 'U6  PMIC', mark: 'PMIC-802\n3V3/5V' },
];

/* ═══════════════════════════════════════════════════════════
   1.  PROCEDURAL TEXTURES – PHYSICAL PCB + MATCHING PBR MAPS
   ═══════════════════════════════════════════════════════════ */

function createPCBTextures(w = 2048, h = 2048) {
  const cCol = document.createElement('canvas');
  const cRgh = document.createElement('canvas');
  const cMet = document.createElement('canvas');
  cCol.width = cRgh.width = cMet.width = w;
  cCol.height = cRgh.height = cMet.height = h;

  const gC = cCol.getContext('2d');
  const gR = cRgh.getContext('2d');
  const gM = cMet.getContext('2d');

  // --- base solder-mask (deep matte blue-black #0d1a2e, matte roughness ~0.58) ---
  gC.fillStyle = '#0d1a2e';
  gC.fillRect(0, 0, w, h);
  gR.fillStyle = '#949494';
  gR.fillRect(0, 0, w, h);
  gM.fillStyle = '#000000';
  gM.fillRect(0, 0, w, h);

  // subtle fiberglass weave / mask grain
  for (let i = 0; i < 6000; i++) {
    const v = 12 + Math.random() * 10 | 0;
    gC.fillStyle = `rgba(${v},${v + 12},${v + 24},0.14)`;
    const x = Math.random() * w, y = Math.random() * h;
    gC.fillRect(x, y, 1.5, 1.5);
  }

  // Helper: draw synchronized trace (thin 2-4px, slightly lighter than mask)
  function drawTrace(pts, width = 3.0) {
    for (const [ctx, col] of [[gC, '#183358'], [gR, '#767676'], [gM, '#262626']]) {
      ctx.save();
      ctx.strokeStyle = col;
      ctx.lineWidth = width;
      ctx.lineCap = 'round';
      ctx.lineJoin = 'round';
      ctx.beginPath();
      ctx.moveTo(pts[0][0], pts[0][1]);
      for (let i = 1; i < pts.length; i++) ctx.lineTo(pts[i][0], pts[i][1]);
      ctx.stroke();
      ctx.restore();
    }
  }

  // Helper: draw a muted gold via at (x, y)
  const vias = [];
  function addVia(vx, vy, r = 6.5) {
    vias.push([vx, vy, r]);
  }

  // ---- TIDY PARALLEL BUS GROUPS (every trace starts and ends at a via or chip pad) ----
  // Group 1: Left edge vias -> U1 MCU
  for (let i = 0; i < 6; i++) {
    const y0 = h * 0.19 + i * 11;
    const xStart = w * 0.08;
    const xEnd = w * 0.17 - 70;
    const bendX = xStart + 60 + i * 8;
    addVia(xStart, y0, 6);
    drawTrace([[xStart, y0], [bendX, y0], [bendX + 18, y0 + 18], [xEnd, y0 + 18]], 2.8);
  }

  // Group 2: U1 MCU -> U2 VRM (horizontal upper bus across top)
  for (let i = 0; i < 7; i++) {
    const y0 = h * 0.20 + i * 10;
    const xStart = w * 0.17 + 70;
    const xEnd = w * 0.74 - 75;
    const bendX = w * 0.45 + i * 12;
    drawTrace([[xStart, y0], [bendX, y0], [bendX + 20, y0 - 20], [xEnd, y0 - 20]], 2.6);
  }

  // Group 3: U2 VRM -> U5 BIOS (vertical bus)
  for (let i = 0; i < 5; i++) {
    const x0 = w * 0.72 + i * 11;
    const yStart = h * 0.24 + 52;
    const yEnd = h * 0.43 - 45;
    drawTrace([[x0, yStart], [x0, yEnd]], 2.6);
  }

  // Group 4: U5 BIOS -> U3 NAND (vertical bus)
  for (let i = 0; i < 5; i++) {
    const x0 = w * 0.81 + i * 11;
    const yStart = h * 0.43 + 45;
    const yEnd = h * 0.62 - 68;
    const xDest = w * 0.72 + 20 + i * 11;
    drawTrace([[x0, yStart], [x0, yStart + 35], [xDest, yStart + 35 + Math.abs(x0 - xDest) * 0.5], [xDest, yEnd]], 2.6);
  }

  // Group 5: U4 PHY -> U6 PMIC -> U3 NAND (clean lower horizontal bus, clear of ELECTRODESK text)
  for (let i = 0; i < 6; i++) {
    const y0 = h * 0.65 + i * 11;
    const x1 = w * 0.20 + 65;
    const x2 = w * 0.46 - 80;
    drawTrace([[x1, y0], [x2, y0]], 3.0);

    const x3 = w * 0.46 + 80;
    const x4 = w * 0.72 - 100;
    drawTrace([[x3, y0], [x3 + 50, y0], [x3 + 75, y0 - 25], [x4, y0 - 25]], 3.0);
  }

  // Group 6: Vertical feeder buses from heatsink socket area down to U6 PMIC
  for (let i = 0; i < 6; i++) {
    const x0 = w * 0.41 + i * 12;
    const yStart = h * 0.52;
    const yEnd = h * 0.68 - 55;
    addVia(x0, yStart, 6);
    drawTrace([[x0, yStart], [x0, yEnd]], 2.5);
  }

  // Group 7: Left vertical bus U1 MCU -> U4 PHY
  for (let i = 0; i < 5; i++) {
    const x0 = w * 0.16 + i * 11;
    const yStart = h * 0.24 + 50;
    const yEnd = h * 0.66 - 48;
    drawTrace([[x0, yStart], [x0, yEnd]], 2.6);
  }

  // Group 8: Right edge termination vias from U3 NAND & U2 VRM
  for (let i = 0; i < 5; i++) {
    const y0 = h * 0.58 + i * 12;
    const xStart = w * 0.72 + 100;
    const xEnd = w * 0.91;
    addVia(xEnd, y0, 6);
    drawTrace([[xStart, y0], [xEnd, y0]], 2.5);
  }

  // ---- CHIP FOOTPRINT PADS (muted gold pads + readable silkscreen labels) ----
  const chipPositions = CHIP_SPECS.map(c => ({
    cx: w * c.u, cy: h * c.v, pw: c.pw, ph: c.ph, label: c.label
  }));

  for (const cp of chipPositions) {
    const { cx, cy, pw, ph, label } = cp;

    // silkscreen outline (off-white matte)
    gC.strokeStyle = '#d8e0ec';
    gC.lineWidth = 2.5;
    gC.globalAlpha = 0.75;
    gC.strokeRect(cx - pw / 2, cy - ph / 2, pw, ph);
    gR.strokeStyle = '#b8b8b8';
    gR.lineWidth = 2.5;
    gR.strokeRect(cx - pw / 2, cy - ph / 2, pw, ph);

    // pin-1 dot
    gC.beginPath();
    gC.arc(cx - pw / 2 + 12, cy - ph / 2 + 12, 4.5, 0, Math.PI * 2);
    gC.fillStyle = '#d8e0ec';
    gC.globalAlpha = 0.88;
    gC.fill();

    // muted gold ENIG pads along each side
    const padW = 6, padH = 14, padGap = 12;
    const padsPerSide = Math.floor((pw - 16) / padGap);
    const padsVert = Math.floor((ph - 16) / padGap);
    for (const [ctx, col] of [[gC, '#c49b36'], [gR, '#383838'], [gM, '#dcdcdc']]) {
      ctx.fillStyle = col;
      ctx.globalAlpha = 1.0;
      for (let i = 0; i < padsPerSide; i++) {
        const px = cx - pw / 2 + 12 + i * padGap;
        ctx.fillRect(px, cy - ph / 2 - padH / 2, padW, padH);
        ctx.fillRect(px, cy + ph / 2 - padH / 2, padW, padH);
      }
      for (let i = 0; i < padsVert; i++) {
        const py = cy - ph / 2 + 12 + i * padGap;
        ctx.fillRect(cx - pw / 2 - padH / 2, py, padH, padW);
        ctx.fillRect(cx + pw / 2 - padH / 2, py, padH, padW);
      }
    }

    // crisp off-white label
    gC.font = 'bold 22px monospace';
    gC.fillStyle = '#d8e0ec';
    gC.globalAlpha = 0.90;
    gC.textAlign = 'center';
    gC.fillText(label, cx, cy + 7);
    gR.font = 'bold 22px monospace';
    gR.fillStyle = '#b8b8b8';
    gR.textAlign = 'center';
    gR.fillText(label, cx, cy + 7);
  }
  gC.globalAlpha = 1;
  gC.textAlign = 'start';
  gR.textAlign = 'start';

  // ---- DRAW ALL TERMINATION VIAS (muted gold) ----
  for (const [vx, vy, r] of vias) {
    for (const [ctx, col] of [[gC, '#c49b36'], [gR, '#383838'], [gM, '#dcdcdc']]) {
      ctx.beginPath(); ctx.arc(vx, vy, r, 0, Math.PI * 2);
      ctx.fillStyle = col;
      ctx.fill();
    }
    for (const [ctx, col] of [[gC, '#060a14'], [gR, '#949494'], [gM, '#000000']]) {
      ctx.beginPath(); ctx.arc(vx, vy, r * 0.4, 0, Math.PI * 2);
      ctx.fillStyle = col;
      ctx.fill();
    }
  }

  // ---- SILKSCREEN REFERENCE DESIGNATORS (placed in clear space) ----
  const refs = [
    { t: 'R1', x: 0.11, y: 0.12 }, { t: 'R12', x: 0.31, y: 0.12 }, { t: 'R18', x: 0.62, y: 0.12 },
    { t: 'C1', x: 0.10, y: 0.42 }, { t: 'C6',  x: 0.64, y: 0.35 }, { t: 'C15', x: 0.88, y: 0.20 },
    { t: 'D1', x: 0.10, y: 0.54 }, { t: 'Q1',  x: 0.64, y: 0.48 }, { t: 'L1',  x: 0.84, y: 0.76 },
    { t: 'J1', x: 0.14, y: 0.84 }, { t: 'J2',  x: 0.24, y: 0.84 }, { t: 'SW1', x: 0.80, y: 0.84 },
    { t: 'VCC3V3', x: 0.62, y: 0.16 }, { t: 'VCC5V', x: 0.10, y: 0.48 },
    { t: 'SDA', x: 0.56, y: 0.58 }, { t: 'SCL', x: 0.62, y: 0.58 },
  ];
  gC.font = 'bold 20px monospace';
  gC.fillStyle = '#d8e0ec';
  gR.font = 'bold 20px monospace';
  gR.fillStyle = '#b8b8b8';
  for (const r of refs) {
    const lx = w * r.x, ly = h * r.y;
    gC.globalAlpha = 0.85;
    gC.fillText(r.t, lx, ly);
    gR.fillText(r.t, lx, ly);
  }
  gC.globalAlpha = 1;

  // ---- LARGE BRAND SILKSCREEN IN CLEAR SPACE (no traces over it) ----
  gC.font = 'bold 76px monospace';
  gC.fillStyle = '#d8e0ec';
  gC.globalAlpha = 0.94;
  gC.textAlign = 'center';
  gC.fillText('ELECTRODESK', w * 0.50, h * 0.89);
  gC.font = 'bold 24px monospace';
  gC.globalAlpha = 0.82;
  gC.fillText('REV 3.2  •  MADE IN INDIA', w * 0.50, h * 0.94);
  gC.textAlign = 'start';
  gC.globalAlpha = 1;

  gR.font = 'bold 76px monospace';
  gR.fillStyle = '#b8b8b8';
  gR.textAlign = 'center';
  gR.fillText('ELECTRODESK', w * 0.50, h * 0.89);
  gR.font = 'bold 24px monospace';
  gR.fillText('REV 3.2  •  MADE IN INDIA', w * 0.50, h * 0.94);
  gR.textAlign = 'start';

  const mapTex = new THREE.CanvasTexture(cCol);
  mapTex.encoding = THREE.sRGBEncoding;
  mapTex.anisotropy = ANISO;
  mapTex.wrapS = mapTex.wrapT = THREE.RepeatWrapping;

  const roughTex = new THREE.CanvasTexture(cRgh);
  roughTex.anisotropy = ANISO;
  roughTex.wrapS = roughTex.wrapT = THREE.RepeatWrapping;

  const metalTex = new THREE.CanvasTexture(cMet);
  metalTex.anisotropy = ANISO;
  metalTex.wrapS = metalTex.wrapT = THREE.RepeatWrapping;

  return { mapTex, roughTex, metalTex };
}

function createContactShadowTexture(w = 512, h = 512) {
  const c = document.createElement('canvas');
  c.width = w; c.height = h;
  const g = c.getContext('2d');
  const cx = w / 2, cy = h / 2;
  const grad = g.createRadialGradient(cx, cy, w * 0.22, cx, cy, w * 0.49);
  grad.addColorStop(0.0, 'rgba(0, 0, 0, 0.98)');
  grad.addColorStop(0.55, 'rgba(0, 0, 0, 0.80)');
  grad.addColorStop(0.80, 'rgba(0, 0, 0, 0.36)');
  grad.addColorStop(1.0, 'rgba(0, 0, 0, 0.0)');
  g.fillStyle = grad;
  g.fillRect(0, 0, w, h);
  const tex = new THREE.CanvasTexture(c);
  tex.encoding = THREE.sRGBEncoding;
  return tex;
}

function createHeatsinkFinTexture(w = 64, h = 256) {
  // Satin aluminium vertical gradient: dark in the grooves, satin highlight at top edge (never pure white)
  const c = document.createElement('canvas');
  c.width = w; c.height = h;
  const g = c.getContext('2d');
  const grad = g.createLinearGradient(0, 0, 0, h);
  grad.addColorStop(0.0,  '#cfd6df'); // satin aluminium top edge
  grad.addColorStop(0.10, '#9aa3af');
  grad.addColorStop(0.45, '#5a626e');
  grad.addColorStop(1.0,  '#22272f'); // dark groove base
  g.fillStyle = grad;
  g.fillRect(0, 0, w, h);
  const tex = new THREE.CanvasTexture(c);
  tex.encoding = THREE.sRGBEncoding;
  tex.anisotropy = ANISO;
  return tex;
}

function createBrushedMetalTexture(w = 512, h = 512) {
  const c = document.createElement('canvas');
  c.width = w; c.height = h;
  const g = c.getContext('2d');
  g.fillStyle = '#585858';
  g.fillRect(0, 0, w, h);
  for (let y = 0; y < h; y++) {
    const v = 78 + Math.random() * 44 | 0;
    g.strokeStyle = `rgb(${v},${v},${v})`;
    g.lineWidth = 0.5 + Math.random();
    g.beginPath();
    g.moveTo(0, y); g.lineTo(w, y);
    g.stroke();
  }
  const tex = new THREE.CanvasTexture(c);
  tex.anisotropy = ANISO;
  tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
  return tex;
}

/* ═══════════════════════════════════════════════════════════
   2.  MATERIAL LIBRARY
   ═══════════════════════════════════════════════════════════ */
function createMaterials() {
  const { mapTex, roughTex, metalTex } = createPCBTextures();
  const brushedTex    = createBrushedMetalTexture();
  const contactShadowTex = createContactShadowTexture();
  const finGradTex    = createHeatsinkFinTexture();

  return {
    metalMaskTex: metalTex,
    solderMask: new THREE.MeshPhysicalMaterial({
      map: mapTex,
      roughnessMap: roughTex,
      metalnessMap: metalTex,
      roughness: 1.0,
      metalness: 1.0,
      clearcoat: 0.15,
      clearcoatRoughness: 0.35,
      color: 0xffffff,
      envMapIntensity: 0.25,
    }),
    pcbEdge: new THREE.MeshStandardMaterial({
      color: PAL.pcbEdge,
      roughness: 0.88,
      metalness: 0.0,
      envMapIntensity: 0.05,
    }),
    pcbBottom: new THREE.MeshStandardMaterial({
      color: PAL.pcbBottom,
      roughness: 0.70,
      metalness: 0.0,
      envMapIntensity: 0.1,
    }),
    heatsinkBody: new THREE.MeshPhysicalMaterial({
      color: PAL.heatsinkAlu,
      map: finGradTex,
      metalness: 0.88,
      roughness: 0.42,
      roughnessMap: brushedTex,
      clearcoat: 0.0,
      envMapIntensity: 0.72,
    }),
    copperPipe: new THREE.MeshPhysicalMaterial({
      color: PAL.copperPipe,
      metalness: 0.90,
      roughness: 0.28,
      envMapIntensity: 0.9,
    }),
    bracketSteel: new THREE.MeshStandardMaterial({
      color: PAL.bracketSteel,
      metalness: 0.65,
      roughness: 0.55,
      envMapIntensity: 0.35,
    }),
    screwMetal: new THREE.MeshPhysicalMaterial({
      color: PAL.screwSteel,
      metalness: 0.55,
      roughness: 0.58,
      clearcoat: 0.0,
      envMapIntensity: 0.18,
    }),
    washerMetal: new THREE.MeshStandardMaterial({
      color: PAL.washerSteel,
      metalness: 0.52,
      roughness: 0.60,
      envMapIntensity: 0.18,
    }),
    icBody: new THREE.MeshStandardMaterial({
      color: 0x15181e,
      roughness: 0.68,
      metalness: 0.04,
      envMapIntensity: 0.18,
    }),
    pinMetal: new THREE.MeshStandardMaterial({
      color: 0x8a929e,
      metalness: 0.85,
      roughness: 0.34,
      envMapIntensity: 0.48,
    }),
    goldPin: new THREE.MeshStandardMaterial({
      color: 0xc89e38,
      metalness: 0.88,
      roughness: 0.26,
      envMapIntensity: 0.55,
    }),
    ioMetal: new THREE.MeshPhysicalMaterial({
      color: 0x5c6470,
      metalness: 0.85,
      roughness: 0.38,
      roughnessMap: brushedTex,
      envMapIntensity: 0.52,
    }),
    cavityDark: new THREE.MeshStandardMaterial({
      color: 0x05070a,
      roughness: 0.92,
      metalness: 0.0,
      envMapIntensity: 0.05,
    }),
    usbBlue: new THREE.MeshStandardMaterial({
      color: 0x1a54b0,
      roughness: 0.48,
      metalness: 0.0,
      envMapIntensity: 0.25,
    }),
    slotDark: new THREE.MeshStandardMaterial({
      color: 0x161a22,
      roughness: 0.62,
      metalness: 0.08,
      envMapIntensity: 0.18,
    }),
    slotGraphite: new THREE.MeshStandardMaterial({
      color: 0x222730,
      roughness: 0.52,
      metalness: 0.45,
      envMapIntensity: 0.30,
    }),
    latchGrey: new THREE.MeshStandardMaterial({
      color: 0x2a303a,
      roughness: 0.55,
      metalness: 0.15,
      envMapIntensity: 0.22,
    }),
    chokeFerrite: new THREE.MeshStandardMaterial({
      color: 0x20242c,
      roughness: 0.72,
      metalness: 0.14,
      envMapIntensity: 0.22,
    }),
    capBody: new THREE.MeshPhysicalMaterial({
      color: 0x1c2840,
      roughness: 0.38,
      metalness: 0.25,
      envMapIntensity: 0.35,
    }),
    capTopAlu: new THREE.MeshStandardMaterial({
      color: 0x6e7682,
      metalness: 0.82,
      roughness: 0.36,
      envMapIntensity: 0.42,
    }),
    smdResistor: new THREE.MeshStandardMaterial({
      color: 0x181b20,
      roughness: 0.55,
      metalness: 0.12,
      envMapIntensity: 0.25,
    }),
    smdCap: new THREE.MeshStandardMaterial({
      color: 0x8f6b42,
      roughness: 0.42,
      metalness: 0.08,
      envMapIntensity: 0.30,
    }),
    contactShadow: new THREE.MeshBasicMaterial({
      map: contactShadowTex,
      transparent: true,
      depthWrite: false,
      opacity: 0.98,
    }),
    shadowFloor: new THREE.ShadowMaterial({ opacity: 0.45 }),
  };
}

/* ═══════════════════════════════════════════════════════════
   3.  GEOMETRY BUILDERS
   ═══════════════════════════════════════════════════════════ */

function buildPCB(mats) {
  const group = new THREE.Group();
  group.name = 'pcb';
  const W = 6.0, D = 4.2, H = 0.10;

  // --- Edge body slab (dark, visible thickness) ---
  const bodyGeo = new THREE.BoxGeometry(W, H, D);
  const bodyMesh = new THREE.Mesh(bodyGeo, mats.pcbEdge);
  bodyMesh.position.y = H / 2;
  bodyMesh.castShadow = true;
  bodyMesh.receiveShadow = true;
  group.add(bodyMesh);

  // --- Top face (textured solder mask) ---
  const topGeo = new THREE.PlaneGeometry(W - 0.004, D - 0.004);
  const topMesh = new THREE.Mesh(topGeo, mats.solderMask);
  topMesh.rotation.x = -Math.PI / 2;
  topMesh.position.y = H + 0.001;
  topMesh.receiveShadow = true;
  group.add(topMesh);

  // --- Bottom face ---
  const botGeo = new THREE.PlaneGeometry(W - 0.004, D - 0.004);
  const botMesh = new THREE.Mesh(botGeo, mats.pcbBottom);
  botMesh.rotation.x = Math.PI / 2;
  botMesh.position.y = -0.001;
  group.add(botMesh);

  // --- Mounting holes + muted gold rings + 1.5x SCREWS ---
  const holeR = 0.105;
  const holeGeo = new THREE.CylinderGeometry(holeR, holeR, H + 0.06, 20);
  const holeMat = new THREE.MeshStandardMaterial({ color: 0x040810, roughness: 0.85 });
  const ringGeo = new THREE.RingGeometry(holeR, holeR + 0.075, 24);
  ringGeo.rotateX(-Math.PI / 2);
  const ringMat = new THREE.MeshPhysicalMaterial({
    color: PAL.goldENIG, metalness: 0.85, roughness: 0.28, clearcoat: 0.1
  });

  const corners = [
    [-W / 2 + 0.28, -D / 2 + 0.28],
    [ W / 2 - 0.28, -D / 2 + 0.28],
    [-W / 2 + 0.28,  D / 2 - 0.28],
    [ W / 2 - 0.28,  D / 2 - 0.28],
  ];

  for (const [cx, cz] of corners) {
    // hole
    const hole = new THREE.Mesh(holeGeo, holeMat);
    hole.position.set(cx, H / 2, cz);
    group.add(hole);
    // gold ring
    const ring = new THREE.Mesh(ringGeo, ringMat);
    ring.position.set(cx, H + 0.002, cz);
    group.add(ring);
    // SCREW – Phillips head, seated flush
    const screwGroup = buildScrew(mats);
    screwGroup.position.set(cx, H + 0.002, cz);
    group.add(screwGroup);
  }

  return group;
}

/** Builds a 1.5x dark stainless-steel domed Phillips-head screw with thin washer. */
function buildScrew(mats) {
  const g = new THREE.Group();

  // Thin metal washer seated flush on the muted gold ring
  const washerR = 0.138, washerH = 0.006;
  const washerGeo = new THREE.CylinderGeometry(washerR, washerR, washerH, 28);
  const washer = new THREE.Mesh(washerGeo, mats.washerMetal);
  washer.position.y = washerH / 2;
  washer.castShadow = true;
  washer.receiveShadow = true;
  g.add(washer);

  // Raised domed head (pan-head collar + flattened satin dome to avoid white ceiling glare)
  const headR = 0.102, collarH = 0.015;
  const collarGeo = new THREE.CylinderGeometry(headR, headR * 1.03, collarH, 28);
  const collar = new THREE.Mesh(collarGeo, mats.screwMetal);
  collar.position.y = washerH + collarH / 2;
  collar.castShadow = true;
  g.add(collar);

  const domeGeo = new THREE.SphereGeometry(headR, 28, 16, 0, Math.PI * 2, 0, Math.PI * 0.46);
  domeGeo.scale(1, 0.36, 1);
  const dome = new THREE.Mesh(domeGeo, mats.screwMetal);
  dome.position.y = washerH + collarH - 0.002;
  dome.castShadow = true;
  dome.receiveShadow = true;
  g.add(dome);

  // Clear recessed Phillips cross seated cleanly in the dome apex
  const slotW = headR * 1.18, slotH = 0.016, slotD = 0.028;
  const slotGeo = new THREE.BoxGeometry(slotW, slotH, slotD);
  const slotMat = new THREE.MeshStandardMaterial({ color: 0x040608, roughness: 0.96, metalness: 0.0, envMapIntensity: 0.02 });
  const slotY = washerH + collarH + headR * 0.36 - 0.007;
  const slot1 = new THREE.Mesh(slotGeo, slotMat);
  slot1.position.y = slotY;
  g.add(slot1);
  const slot2 = new THREE.Mesh(slotGeo, slotMat);
  slot2.position.y = slotY;
  slot2.rotation.y = Math.PI / 2;
  g.add(slot2);

  // Shaft going down into the hole
  const shaftR = 0.045, shaftH = 0.14;
  const shaftGeo = new THREE.CylinderGeometry(shaftR, shaftR, shaftH, 10);
  const shaft = new THREE.Mesh(shaftGeo, mats.screwMetal);
  shaft.position.y = -shaftH / 2;
  g.add(shaft);

  return g;
}

function buildHeatsink(mats) {
  const group = new THREE.Group();
  group.name = 'heatsink';
  const baseW = 1.6, baseD = 1.6, baseH = 0.10;

  // --- Base plate ---
  const baseGeo = new THREE.BoxGeometry(baseW, baseH, baseD);
  const base = new THREE.Mesh(baseGeo, mats.heatsinkBody);
  base.position.y = baseH / 2;
  base.castShadow = true;
  base.receiveShadow = true;
  group.add(base);

  // --- Fins: 16 individually separated thin plates with dark grooves ---
  const finCount = 16;
  const finW = 0.026;
  const finH = 0.60;
  const finD = baseD - 0.08;
  const totalSpan = baseW - 0.10;
  const spacing = totalSpan / (finCount - 1);
  const finGeo = new THREE.BoxGeometry(finW, finH, finD);

  for (let i = 0; i < finCount; i++) {
    const fin = new THREE.Mesh(finGeo, mats.heatsinkBody);
    fin.position.set(-totalSpan / 2 + i * spacing, baseH + finH / 2, 0);
    fin.castShadow = true;
    fin.receiveShadow = true;
    group.add(fin);
  }

  // --- Copper heat pipes (3 visible between fins) ---
  const pipeR = 0.035;
  const pipeLen = baseW - 0.25;
  const pipeGeo = new THREE.CylinderGeometry(pipeR, pipeR, pipeLen, 10);
  pipeGeo.rotateZ(Math.PI / 2);
  for (const pz of [-0.35, 0, 0.35]) {
    const pipe = new THREE.Mesh(pipeGeo, mats.copperPipe);
    pipe.position.set(0, baseH + 0.10, pz);
    pipe.castShadow = true;
    group.add(pipe);
  }

  // --- Mounting bracket (steel retention frame) ---
  const bW = baseW + 0.35, bD = baseD + 0.35, bH = 0.035, bT = 0.07;
  const barDefs = [
    { w: bW, d: bT, x: 0, z: -bD / 2 + bT / 2 },
    { w: bW, d: bT, x: 0, z:  bD / 2 - bT / 2 },
    { w: bT, d: bD - bT * 2, x: -bW / 2 + bT / 2, z: 0 },
    { w: bT, d: bD - bT * 2, x:  bW / 2 - bT / 2, z: 0 },
  ];
  for (const b of barDefs) {
    const bg = new THREE.BoxGeometry(b.w, bH, b.d);
    const bm = new THREE.Mesh(bg, mats.bracketSteel);
    bm.position.set(b.x, -0.008, b.z);
    bm.castShadow = true;
    group.add(bm);
  }

  return group;
}

/* ─── Stage Two Builders: ICs, Rear I/O, Slots, Power, VRM, SMDs ─── */

function createICTopTexture(text) {
  const c = document.createElement('canvas');
  c.width = 256; c.height = 256;
  const g = c.getContext('2d');
  g.fillStyle = '#15181e';
  g.fillRect(0, 0, 256, 256);
  // subtle epoxy grain
  for (let i = 0; i < 600; i++) {
    const v = 18 + Math.random() * 10 | 0;
    g.fillStyle = `rgb(${v},${v + 2},${v + 5})`;
    g.fillRect(Math.random() * 256, Math.random() * 256, 2, 2);
  }
  // pin-1 dimple
  g.beginPath(); g.arc(28, 28, 10, 0, Math.PI * 2);
  g.fillStyle = '#0d0f13'; g.fill();
  g.strokeStyle = '#2c323d'; g.lineWidth = 2; g.stroke();
  // faint laser-etched marking
  g.fillStyle = '#7b8494';
  g.font = 'bold 26px monospace';
  g.textAlign = 'center';
  const lines = text.split('\n');
  lines.forEach((ln, idx) => g.fillText(ln, 128, 118 + idx * 36));
  const tex = new THREE.CanvasTexture(c);
  tex.encoding = THREE.sRGBEncoding;
  tex.anisotropy = ANISO;
  return tex;
}

function buildICChips(mats) {
  const group = new THREE.Group();
  group.name = 'ic_chips';
  const pinMatrices = [];
  const chipGlowTargets = [];
  const dummy = new THREE.Object3D();

  for (const cp of CHIP_SPECS) {
    const cx = (cp.u - 0.5) * PCB_W;
    const cz = (cp.v - 0.5) * PCB_D;
    const w = (cp.pw / 2048) * PCB_W * 0.88;
    const d = (cp.ph / 2048) * PCB_D * 0.88;
    const h = 0.042;

    const topTex = createICTopTexture(cp.mark);
    const topMat = new THREE.MeshStandardMaterial({
      map: topTex, roughness: 0.65, metalness: 0.04, envMapIntensity: 0.18,
      emissive: new THREE.Color(0x2868a8), emissiveIntensity: 0,
    });
    chipGlowTargets.push({ cx, mat: topMat });
    const pkgGeo = new THREE.BoxGeometry(w, h, d);
    const pkgMats = [mats.icBody, mats.icBody, topMat, mats.icBody, mats.icBody, mats.icBody];
    const pkg = new THREE.Mesh(pkgGeo, pkgMats);
    pkg.position.set(cx, PCB_H + h / 2 + 0.004, cz);
    pkg.castShadow = true;
    pkg.receiveShadow = true;
    group.add(pkg);

    // Gull-wing pins along all 4 sides matching PCB pad spacing
    const padGapW = (12 / 2048) * PCB_W;
    const padGapD = (12 / 2048) * PCB_D;
    const countX = Math.floor((w * 0.92) / padGapW);
    const countZ = Math.floor((d * 0.92) / padGapD);

    for (let i = 0; i < countX; i++) {
      const px = cx - (countX - 1) * padGapW / 2 + i * padGapW;
      for (const s of [-1, 1]) {
        dummy.position.set(px, PCB_H + 0.012, cz + s * (d / 2 + 0.018));
        dummy.rotation.set(s * 0.32, 0, 0);
        dummy.scale.set(0.011, 0.022, 0.036);
        dummy.updateMatrix();
        pinMatrices.push(dummy.matrix.clone());
      }
    }
    for (let i = 0; i < countZ; i++) {
      const pz = cz - (countZ - 1) * padGapD / 2 + i * padGapD;
      for (const s of [-1, 1]) {
        dummy.position.set(cx + s * (w / 2 + 0.018), PCB_H + 0.012, pz);
        dummy.rotation.set(0, 0, -s * 0.32);
        dummy.scale.set(0.036, 0.022, 0.011);
        dummy.updateMatrix();
        pinMatrices.push(dummy.matrix.clone());
      }
    }
  }

  const pinGeo = new THREE.BoxGeometry(1, 1, 1);
  const pinInst = new THREE.InstancedMesh(pinGeo, mats.pinMetal, pinMatrices.length);
  pinInst.castShadow = true;
  pinMatrices.forEach((m, idx) => pinInst.setMatrixAt(idx, m));
  pinInst.instanceMatrix.needsUpdate = true;
  group.add(pinInst);

  return { group, chipGlowTargets };
}

function buildShieldedPort(mats, w, h, d, wallT = 0.018) {
  // Hollow brushed-metal port shell open on the -X face with recessed dark cavity
  const g = new THREE.Group();
  const top = new THREE.Mesh(new THREE.BoxGeometry(w, wallT, d), mats.ioMetal);
  top.position.y = h - wallT / 2;
  const bot = new THREE.Mesh(new THREE.BoxGeometry(w, wallT, d), mats.ioMetal);
  bot.position.y = wallT / 2;
  const sideL = new THREE.Mesh(new THREE.BoxGeometry(w, h, wallT), mats.ioMetal);
  sideL.position.set(0, h / 2, -d / 2 + wallT / 2);
  const sideR = new THREE.Mesh(new THREE.BoxGeometry(w, h, wallT), mats.ioMetal);
  sideR.position.set(0, h / 2, d / 2 - wallT / 2);
  const back = new THREE.Mesh(new THREE.BoxGeometry(wallT, h, d), mats.ioMetal);
  back.position.set(w / 2 - wallT / 2, h / 2, 0);
  const cavity = new THREE.Mesh(new THREE.BoxGeometry(w * 0.86, h - wallT * 2.1, d - wallT * 2.1), mats.cavityDark);
  cavity.position.set(0.015, h / 2, 0);
  for (const m of [top, bot, sideL, sideR, back]) {
    m.castShadow = true;
    m.receiveShadow = true;
  }
  g.add(top, bot, sideL, sideR, back, cavity);
  return g;
}

function buildRearIO(mats) {
  const group = new THREE.Group();
  group.name = 'rear_io';

  // Place along the front-left +Z edge so port openings face +Z toward the camera
  // buildShieldedPort opens on -X; rotating +Math.PI/2 around Y points its opening to +Z!
  const edgeZ = PCB_D / 2;

  // 1. Dual Stacked USB 3.2 Type-A
  const usbW = 0.36, usbH = 0.32, usbD = 0.32;
  const usb = buildShieldedPort(mats, usbW, usbH, usbD);
  const midBar = new THREE.Mesh(new THREE.BoxGeometry(usbW * 0.92, 0.022, usbD - 0.02), mats.ioMetal);
  midBar.position.set(-0.005, usbH / 2, 0);
  usb.add(midBar);
  for (const ty of [usbH * 0.27, usbH * 0.73]) {
    const tongue = new THREE.Mesh(new THREE.BoxGeometry(usbW * 0.72, 0.018, usbD * 0.68), mats.usbBlue);
    tongue.position.set(-0.02, ty, 0);
    usb.add(tongue);
  }
  usb.rotation.y = Math.PI / 2;
  usb.position.set(-2.22, PCB_H, edgeZ - usbW / 2 + 0.01);
  group.add(usb);

  // 2. RJ-45 Gigabit Ethernet
  const rjW = 0.42, rjH = 0.30, rjD = 0.36;
  const rj = buildShieldedPort(mats, rjW, rjH, rjD);
  for (let i = 0; i < 8; i++) {
    const pin = new THREE.Mesh(new THREE.BoxGeometry(0.10, 0.010, 0.010), mats.goldPin);
    pin.position.set(-0.02, rjH * 0.72, -0.10 + i * 0.028);
    pin.rotation.z = -0.35;
    rj.add(pin);
  }
  rj.rotation.y = Math.PI / 2;
  rj.position.set(-1.76, PCB_H, edgeZ - rjW / 2 + 0.01);
  group.add(rj);

  // 3. USB-C Port
  const ucW = 0.28, ucH = 0.12, ucD = 0.24;
  const uc = buildShieldedPort(mats, ucW, ucH, ucD, 0.014);
  const ucTongue = new THREE.Mesh(new THREE.BoxGeometry(ucW * 0.7, 0.012, ucD * 0.56), mats.slotDark);
  ucTongue.position.set(-0.015, ucH / 2, 0);
  uc.add(ucTongue);
  uc.rotation.y = Math.PI / 2;
  uc.position.set(-1.34, PCB_H, edgeZ - ucW / 2 + 0.01);
  group.add(uc);

  // 4. HDMI Display Port
  const hdW = 0.34, hdH = 0.16, hdD = 0.34;
  const hd = buildShieldedPort(mats, hdW, hdH, hdD, 0.016);
  const hdTongue = new THREE.Mesh(new THREE.BoxGeometry(hdW * 0.72, 0.016, hdD * 0.68), mats.slotDark);
  hdTongue.position.set(-0.015, hdH / 2, 0);
  hd.add(hdTongue);
  hd.rotation.y = Math.PI / 2;
  hd.position.set(-0.94, PCB_H, edgeZ - hdW / 2 + 0.01);
  group.add(hd);

  return group;
}

function buildMemoryAndPCIe(mats) {
  const group = new THREE.Group();
  group.name = 'slots';

  // --- Two DDR5 DIMM Slots with retention latches ---
  const dimmLen = 1.66, dimmW = 0.085, dimmH = 0.14;
  for (const sx of [0.76, 0.98]) {
    const slot = new THREE.Group();
    const base = new THREE.Mesh(new THREE.BoxGeometry(dimmW, dimmH, dimmLen), mats.slotDark);
    base.position.y = dimmH / 2;
    base.castShadow = true;
    base.receiveShadow = true;
    slot.add(base);

    // Recessed dark channel + keying notch
    const chan = new THREE.Mesh(new THREE.BoxGeometry(0.026, 0.04, dimmLen - 0.10), mats.cavityDark);
    chan.position.y = dimmH - 0.015;
    slot.add(chan);

    const keyBridge = new THREE.Mesh(new THREE.BoxGeometry(0.030, 0.045, 0.035), mats.slotDark);
    keyBridge.position.set(0, dimmH - 0.015, 0.08);
    slot.add(keyBridge);

    // Visible gold metal contacts along both inner walls of the DDR5 channel
    const contactGeo = new THREE.BoxGeometry(0.008, 0.025, 0.014);
    const dimmContacts = new THREE.InstancedMesh(contactGeo, mats.goldPin, 60);
    const dummy = new THREE.Object3D();
    let idx = 0;
    for (let i = 0; i < 30; i++) {
      const cz = -dimmLen / 2 + 0.12 + i * 0.048;
      if (Math.abs(cz - 0.08) < 0.035) continue;
      for (const cx of [-0.013, 0.013]) {
        if (idx < 60) {
          dummy.position.set(cx, dimmH - 0.008, cz);
          dummy.updateMatrix();
          dimmContacts.setMatrixAt(idx++, dummy.matrix);
        }
      }
    }
    dimmContacts.count = idx;
    dimmContacts.instanceMatrix.needsUpdate = true;
    slot.add(dimmContacts);

    // Retention latches at both ends
    for (const dir of [-1, 1]) {
      const latch = new THREE.Mesh(new THREE.BoxGeometry(dimmW * 1.12, dimmH * 0.95, 0.055), mats.latchGrey);
      latch.position.set(0, dimmH * 0.58, dir * (dimmLen / 2 + 0.022));
      latch.rotation.x = dir * 0.14;
      latch.castShadow = true;
      slot.add(latch);
    }

    slot.position.set(sx, PCB_H, -0.68);
    group.add(slot);
  }

  // --- One Long PCIe x16 Expansion Slot (dark graphite armor + gold contacts) ---
  const pcieLen = 2.55, pcieW = 0.125, pcieH = 0.14;
  const pcie = new THREE.Group();
  const armor = new THREE.Mesh(new THREE.BoxGeometry(pcieLen, pcieH, pcieW), mats.slotGraphite);
  armor.position.y = pcieH / 2;
  armor.castShadow = true;
  armor.receiveShadow = true;
  pcie.add(armor);

  const inner = new THREE.Mesh(new THREE.BoxGeometry(pcieLen - 0.04, pcieH + 0.004, pcieW - 0.03), mats.slotDark);
  inner.position.y = pcieH / 2 + 0.001;
  pcie.add(inner);

  const groove = new THREE.Mesh(new THREE.BoxGeometry(pcieLen - 0.12, 0.04, 0.034), mats.cavityDark);
  groove.position.y = pcieH - 0.012;
  pcie.add(groove);

  const pcieKey = new THREE.Mesh(new THREE.BoxGeometry(0.04, 0.045, 0.038), mats.slotDark);
  pcieKey.position.set(-0.78, pcieH - 0.012, 0);
  pcie.add(pcieKey);

  // Visible gold metal contacts along both inner edges of PCIe groove
  const pcieContactGeo = new THREE.BoxGeometry(0.016, 0.026, 0.009);
  const pcieContacts = new THREE.InstancedMesh(pcieContactGeo, mats.goldPin, 96);
  const pDummy = new THREE.Object3D();
  let pIdx = 0;
  for (let i = 0; i < 48; i++) {
    const cx = -pcieLen / 2 + 0.10 + i * 0.050;
    if (Math.abs(cx + 0.78) < 0.04) continue;
    for (const cz of [-0.017, 0.017]) {
      if (pIdx < 96) {
        pDummy.position.set(cx, pcieH - 0.007, cz);
        pDummy.updateMatrix();
        pcieContacts.setMatrixAt(pIdx++, pDummy.matrix);
      }
    }
  }
  pcieContacts.count = pIdx;
  pcieContacts.instanceMatrix.needsUpdate = true;
  pcie.add(pcieContacts);

  // Rear retention clip (+X end)
  const clip = new THREE.Mesh(new THREE.BoxGeometry(0.11, 0.09, pcieW * 1.25), mats.latchGrey);
  clip.position.set(pcieLen / 2 + 0.045, pcieH * 0.72, 0);
  clip.castShadow = true;
  pcie.add(clip);

  pcie.position.set(-0.75, PCB_H, 1.28);
  group.add(pcie);

  return group;
}

function buildPowerAndHeaders(mats) {
  const group = new THREE.Group();
  group.name = 'power_headers';

  function makePinHeader(cols, rows, pitch = 0.055, hasShroud = false) {
    const hg = new THREE.Group();
    const bw = cols * pitch + 0.03;
    const bd = rows * pitch + 0.03;
    const baseH = 0.028;
    const base = new THREE.Mesh(new THREE.BoxGeometry(bw, baseH, bd), mats.slotDark);
    base.position.y = baseH / 2;
    base.castShadow = true;
    hg.add(base);

    const pinGeo = new THREE.BoxGeometry(0.014, 0.095, 0.014);
    for (let c = 0; c < cols; c++) {
      for (let r = 0; r < rows; r++) {
        const pin = new THREE.Mesh(pinGeo, mats.goldPin);
        pin.position.set((c - (cols - 1) / 2) * pitch, baseH + 0.042, (r - (rows - 1) / 2) * pitch);
        pin.castShadow = true;
        hg.add(pin);
      }
    }
    if (hasShroud) {
      const sh = new THREE.Mesh(new THREE.BoxGeometry(bw, 0.09, 0.016), mats.latchGrey);
      sh.position.set(0, baseH + 0.045, -bd / 2 + 0.008);
      hg.add(sh);
    }
    return hg;
  }

  // 24-pin ATX Main Power (2x12 nylon housing along right edge)
  const atxW = 0.22, atxH = 0.20, atxD = 1.18;
  const atx = new THREE.Group();
  const atxShell = new THREE.Mesh(new THREE.BoxGeometry(atxW, atxH, atxD), mats.slotDark);
  atxShell.position.y = atxH / 2;
  atxShell.castShadow = true;
  atxShell.receiveShadow = true;
  atx.add(atxShell);
  const atxCavity = new THREE.Mesh(new THREE.BoxGeometry(atxW - 0.04, 0.04, atxD - 0.06), mats.cavityDark);
  atxCavity.position.y = atxH - 0.015;
  atx.add(atxCavity);
  const atxClip = new THREE.Mesh(new THREE.BoxGeometry(0.025, 0.12, 0.16), mats.slotDark);
  atxClip.position.set(-atxW / 2 - 0.012, atxH * 0.6, 0);
  atx.add(atxClip);
  for (let i = 0; i < 12; i++) {
    for (const cx of [-0.04, 0.04]) {
      const p = new THREE.Mesh(new THREE.BoxGeometry(0.018, 0.05, 0.018), mats.goldPin);
      p.position.set(cx, atxH - 0.025, -atxD / 2 + 0.08 + i * 0.092);
      atx.add(p);
    }
  }
  atx.position.set(2.66, PCB_H, -0.15);
  group.add(atx);

  // 8-pin EPS CPU Power (2x4 nylon housing top-left)
  const epsW = 0.40, epsH = 0.19, epsD = 0.20;
  const eps = new THREE.Group();
  const epsShell = new THREE.Mesh(new THREE.BoxGeometry(epsW, epsH, epsD), mats.slotDark);
  epsShell.position.y = epsH / 2;
  epsShell.castShadow = true;
  eps.add(epsShell);
  const epsCavity = new THREE.Mesh(new THREE.BoxGeometry(epsW - 0.05, 0.04, epsD - 0.05), mats.cavityDark);
  epsCavity.position.y = epsH - 0.015;
  eps.add(epsCavity);
  for (let i = 0; i < 4; i++) {
    for (const cz of [-0.038, 0.038]) {
      const p = new THREE.Mesh(new THREE.BoxGeometry(0.018, 0.05, 0.018), mats.goldPin);
      p.position.set(-epsW / 2 + 0.065 + i * 0.09, epsH - 0.025, cz);
      eps.add(p);
    }
  }
  eps.position.set(-1.75, PCB_H, -1.78);
  group.add(eps);

  // Gold pin headers
  const gpio = makePinHeader(10, 2, 0.055, false);
  gpio.position.set(1.85, PCB_H, 1.56);
  group.add(gpio);

  const fanHdr = makePinHeader(4, 1, 0.055, true);
  fanHdr.position.set(0.86, PCB_H, -1.78);
  group.add(fanHdr);

  const uartHdr = makePinHeader(4, 1, 0.055, true);
  uartHdr.rotation.y = Math.PI / 2;
  uartHdr.position.set(-2.70, PCB_H, -0.60);
  group.add(uartHdr);

  return group;
}

function buildVRMAndCaps(mats) {
  const group = new THREE.Group();
  group.name = 'vrm_caps';

  // --- 6 Dark Power Chokes (VRM Inductors) near heatsink ---
  const chokeGeo = new THREE.BoxGeometry(0.22, 0.14, 0.22);
  for (let i = 0; i < 6; i++) {
    const cx = -1.25 + i * 0.30;
    const choke = new THREE.Mesh(chokeGeo, mats.chokeFerrite);
    choke.position.set(cx, PCB_H + 0.07, -1.46);
    choke.castShadow = true;
    choke.receiveShadow = true;
    group.add(choke);
  }

  // Helper for cylindrical electrolytic capacitor
  function makeCap(r, h) {
    const cg = new THREE.Group();
    const body = new THREE.Mesh(new THREE.CylinderGeometry(r, r, h, 20), mats.capBody);
    body.position.y = h / 2;
    body.castShadow = true;
    body.receiveShadow = true;
    cg.add(body);
    const top = new THREE.Mesh(new THREE.CylinderGeometry(r * 0.88, r * 0.88, 0.006, 20), mats.capTopAlu);
    top.position.y = h + 0.002;
    cg.add(top);
    // Polarity stripe
    const stripe = new THREE.Mesh(new THREE.BoxGeometry(r * 0.35, h * 0.92, 0.012), mats.latchGrey);
    stripe.position.set(0, h / 2, r * 0.92);
    cg.add(stripe);
    return cg;
  }

  // 6 VRM solid capacitors in row above chokes
  for (let i = 0; i < 6; i++) {
    const cap = makeCap(0.068, 0.20);
    cap.position.set(-1.25 + i * 0.30, PCB_H, -1.78);
    group.add(cap);
  }

  // 4 Bulk capacitors (2 near ATX, 2 near left edge)
  for (const [cx, cz] of [[2.35, -0.55], [2.35, 0.25], [-2.60, 0.05], [-2.60, 0.42]]) {
    const cap = makeCap(0.082, 0.24);
    cap.position.set(cx, PCB_H, cz);
    group.add(cap);
  }

  return group;
}

function buildSMDs(mats) {
  const group = new THREE.Group();
  group.name = 'smds';

  const resMatrices = [];
  const capMatrices = [];
  const dummy = new THREE.Object3D();

  function pushSMD(type, x, z, rotY = 0) {
    dummy.position.set(x, PCB_H + 0.010, z);
    dummy.rotation.set(0, rotY, 0);
    dummy.scale.set(0.042, 0.020, 0.022);
    dummy.updateMatrix();
    if (type === 'R') resMatrices.push(dummy.matrix.clone());
    else capMatrices.push(dummy.matrix.clone());
  }

  // 1. Tidy vertical columns flanking DDR5 memory slots (2 x 40 = 80)
  for (let i = 0; i < 40; i++) {
    const z = -1.46 + i * 0.041;
    pushSMD(i % 2 === 0 ? 'R' : 'C', 0.62, z, 0);
    pushSMD(i % 2 === 0 ? 'C' : 'R', 1.12, z, 0);
  }

  // 2. Tidy horizontal decoupling rows above & below PCIe x16 slot (2 x 52 = 104)
  for (let i = 0; i < 52; i++) {
    const x = -1.96 + i * 0.048;
    pushSMD(i % 3 === 0 ? 'R' : 'C', x, 1.14, Math.PI / 2);
    pushSMD(i % 2 === 0 ? 'C' : 'R', x, 1.42, Math.PI / 2);
  }

  // 3. Tidy rows around VRM chokes & heatsink bottom/right (6 x 12 + 24 = 96)
  for (let c = 0; c < 6; c++) {
    const bx = -1.25 + c * 0.30;
    for (let k = 0; k < 4; k++) {
      pushSMD('R', bx - 0.09 + k * 0.06, -1.29, Math.PI / 2);
      pushSMD('C', bx - 0.09 + k * 0.06, -1.62, Math.PI / 2);
    }
  }
  for (let i = 0; i < 24; i++) {
    pushSMD(i % 2 === 0 ? 'C' : 'R', -1.35 + i * 0.075, 0.56, Math.PI / 2);
    pushSMD(i % 2 === 0 ? 'R' : 'C', -1.58, -1.05 + i * 0.065, 0);
  }

  // 4. Signal termination rows behind Rear I/O ports (3 x 20 = 60)
  for (let i = 0; i < 20; i++) {
    const x = -2.30 + i * 0.078;
    pushSMD('R', x, 1.56, Math.PI / 2);
    pushSMD('C', x, 1.62, Math.PI / 2);
    pushSMD('R', x, 1.68, Math.PI / 2);
  }

  // 5. Decoupling clusters around U2, U3, U4, U5, U6 (5 x 14 = 70)
  for (const cp of CHIP_SPECS.slice(1)) {
    const cx = (cp.u - 0.5) * PCB_W;
    const cz = (cp.v - 0.5) * PCB_D;
    const hw = (cp.pw / 2048) * PCB_W * 0.55;
    const hd = (cp.ph / 2048) * PCB_D * 0.55;
    for (let i = 0; i < 7; i++) {
      pushSMD(i % 2 === 0 ? 'C' : 'R', cx - hw + i * (hw * 2 / 6), cz - hd - 0.06, Math.PI / 2);
      pushSMD(i % 2 === 0 ? 'R' : 'C', cx - hw + i * (hw * 2 / 6), cz + hd + 0.06, Math.PI / 2);
    }
  }

  // 6. Tidy bank along right ATX power edge (20)
  for (let i = 0; i < 20; i++) {
    pushSMD(i % 2 === 0 ? 'C' : 'R', 2.46, -0.70 + i * 0.060, 0);
  }

  const smdGeo = new THREE.BoxGeometry(1, 1, 1);
  const resInst = new THREE.InstancedMesh(smdGeo, mats.smdResistor, resMatrices.length);
  const capInst = new THREE.InstancedMesh(smdGeo, mats.smdCap, capMatrices.length);
  resInst.castShadow = true;
  capInst.castShadow = true;
  resMatrices.forEach((m, i) => resInst.setMatrixAt(i, m));
  capMatrices.forEach((m, i) => capInst.setMatrixAt(i, m));
  resInst.instanceMatrix.needsUpdate = true;
  capInst.instanceMatrix.needsUpdate = true;
  group.add(resInst, capInst);

  return group;
}

/* ─── Stage Three Builders: Subtle Trace Pulses & Status LEDs ─── */

function buildTracePulses() {
  const group = new THREE.Group();
  group.name = 'trace_pulses';
  const pulseGeo = new THREE.BoxGeometry(0.14, 0.005, 0.018);
  const paths = [
    // From U1 MCU -> Processor
    { start: [-2.05, -0.50], end: [-0.85, -0.25] },
    // From U2 VRM -> Processor
    { start: [ 1.44, -1.09], end: [ 0.05, -0.35] },
    // From U3 NAND -> Processor
    { start: [ 1.32,  0.50], end: [ 0.05,  0.05] },
    // From U4 PHY -> Processor
    { start: [-1.80,  0.67], end: [-0.75,  0.15] },
    // From U6 PMIC -> Processor
    { start: [-0.24,  0.92], end: [-0.45,  0.30] },
    // From Left Edge -> Processor
    { start: [-2.52, -1.25], end: [-0.95, -0.55] },
  ];

  const pulses = [];
  for (const p of paths) {
    const mat = new THREE.MeshBasicMaterial({
      color: 0x38bdf8,
      transparent: true,
      opacity: 0.0,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    const mesh = new THREE.Mesh(pulseGeo, mat);
    const dx = p.end[0] - p.start[0];
    const dz = p.end[1] - p.start[1];
    mesh.rotation.y = -Math.atan2(dz, dx);
    mesh.position.set(p.start[0], PCB_H + 0.004, p.start[1]);
    group.add(mesh);
    pulses.push({ mesh, mat, start: p.start, end: p.end, progress: -1, speed: 1.0 });
  }
  return { group, pulses };
}

function createLEDGlowTexture() {
  const c = document.createElement('canvas');
  c.width = 128; c.height = 128;
  const g = c.getContext('2d');
  const grad = g.createRadialGradient(64, 64, 4, 64, 64, 62);
  grad.addColorStop(0.0, 'rgba(255, 255, 255, 0.95)');
  grad.addColorStop(0.35, 'rgba(255, 255, 255, 0.45)');
  grad.addColorStop(0.75, 'rgba(255, 255, 255, 0.10)');
  grad.addColorStop(1.0, 'rgba(255, 255, 255, 0.0)');
  g.fillStyle = grad;
  g.fillRect(0, 0, 128, 128);
  const tex = new THREE.CanvasTexture(c);
  tex.encoding = THREE.sRGBEncoding;
  return tex;
}

function buildStatusLEDs() {
  const group = new THREE.Group();
  group.name = 'status_leds';
  const leds = [];
  // 3x larger SMD LEDs placed in clear view along the front-right edge
  const bodyGeo = new THREE.BoxGeometry(0.14, 0.042, 0.095);
  const padMat = new THREE.MeshStandardMaterial({ color: 0x181e26, roughness: 0.6 });
  const lensGeo = new THREE.BoxGeometry(0.105, 0.028, 0.068);
  const haloGeo = new THREE.PlaneGeometry(0.36, 0.36);
  const haloTex = createLEDGlowTexture();

  for (let i = 0; i < 4; i++) {
    const lx = 1.05 + i * 0.22;
    const lz = 1.88;
    const housing = new THREE.Mesh(bodyGeo, padMat);
    housing.position.set(lx, PCB_H + 0.021, lz);
    housing.castShadow = true;
    group.add(housing);

    const lensMat = new THREE.MeshStandardMaterial({
      color: 0x1a3824,
      emissive: 0x22ff66,
      emissiveIntensity: 0.05,
      roughness: 0.25,
      metalness: 0.05,
    });
    const emitter = new THREE.Mesh(lensGeo, lensMat);
    emitter.position.set(lx, PCB_H + 0.046, lz);
    group.add(emitter);

    const haloMat = new THREE.MeshBasicMaterial({
      map: haloTex,
      color: 0x22ff66,
      transparent: true,
      opacity: 0.0,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    const halo = new THREE.Mesh(haloGeo, haloMat);
    halo.rotation.x = -Math.PI / 2;
    halo.position.set(lx, PCB_H + 0.052, lz);
    group.add(halo);

    leds.push({
      lensMat,
      haloMat,
      intensity: 0,
      hold: 0,
      color: new THREE.Color(0x22ff66),
    });
  }
  return { group, leds };
}

function buildSweepBand(metalMaskTex) {
  const group = new THREE.Group();
  group.name = 'sweep_band';

  // 1. Soft trace-glow overlay (samples metalMaskTex, glows only where band passes)
  const traceGlowMat = new THREE.ShaderMaterial({
    uniforms: {
      uMask: { value: metalMaskTex },
      uSweepX: { value: -10.0 },
      uStrength: { value: 0.0 },
      uColor: { value: new THREE.Color(0x38bdf8) },
    },
    vertexShader: `
      varying vec2 vUv;
      varying float vLocalX;
      void main() {
        vUv = uv;
        vLocalX = position.x;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      }
    `,
    fragmentShader: `
      uniform sampler2D uMask;
      uniform float uSweepX;
      uniform float uStrength;
      uniform vec3 uColor;
      varying vec2 vUv;
      varying float vLocalX;
      void main() {
        float mask = texture2D(uMask, vUv).r;
        float dist = (vLocalX - uSweepX) / 0.48;
        float band = exp(-dist * dist);
        float alpha = mask * band * uStrength * 0.65;
        if (alpha < 0.005) discard;
        gl_FragColor = vec4(uColor, alpha);
      }
    `,
    transparent: true,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  });
  const traceOverlay = new THREE.Mesh(new THREE.PlaneGeometry(PCB_W - 0.004, PCB_D - 0.004), traceGlowMat);
  traceOverlay.rotation.x = -Math.PI / 2;
  traceOverlay.position.y = PCB_H + 0.0025;
  group.add(traceOverlay);

  // 2. Thin visible band of light sweeping across the board
  const c = document.createElement('canvas');
  c.width = 128; c.height = 16;
  const g = c.getContext('2d');
  const grad = g.createLinearGradient(0, 0, 128, 0);
  grad.addColorStop(0.0, 'rgba(56, 189, 248, 0.0)');
  grad.addColorStop(0.5, 'rgba(56, 189, 248, 0.36)');
  grad.addColorStop(1.0, 'rgba(56, 189, 248, 0.0)');
  g.fillStyle = grad;
  g.fillRect(0, 0, 128, 16);
  const bandTex = new THREE.CanvasTexture(c);
  bandTex.encoding = THREE.sRGBEncoding;

  const bandMat = new THREE.MeshBasicMaterial({
    map: bandTex,
    transparent: true,
    opacity: 0.0,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  });
  const bandMesh = new THREE.Mesh(new THREE.PlaneGeometry(0.70, PCB_D - 0.02), bandMat);
  bandMesh.rotation.x = -Math.PI / 2;
  bandMesh.position.y = PCB_H + 0.016;
  group.add(bandMesh);

  return { group, traceGlowMat, bandMesh, bandMat };
}

/* ═══════════════════════════════════════════════════════════
   4.  SCENE ASSEMBLY
   ═══════════════════════════════════════════════════════════ */

let sceneInitialized = false;

function initCircuitBoardScene() {
  if (sceneInitialized) return;
  // Do not load the 3D scene below 900px width
  if (window.innerWidth < 900) {
    const waitDesktop = () => {
      if (window.innerWidth >= 900) {
        window.removeEventListener('resize', waitDesktop);
        initCircuitBoardScene();
      }
    };
    window.addEventListener('resize', waitDesktop);
    return;
  }

  const canvas = document.getElementById('login-board-canvas');
  const container = document.getElementById('login-canvas-container');
  if (!canvas || !container) return;
  sceneInitialized = true;

  // Loading state
  const loaderEl = document.createElement('div');
  loaderEl.className = 'scene-loading-indicator';
  loaderEl.innerHTML = '<div class="scene-loading-spinner"></div><span>INITIALIZING HARDWARE</span>';
  container.appendChild(loaderEl);

  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({
      canvas, antialias: true, alpha: true,
      powerPreference: 'high-performance',
    });
  } catch (e) { console.warn('[Electrodesk] WebGL unavailable:', e); loaderEl.remove(); showFallback(); return; }
  if (!renderer.capabilities) { loaderEl.remove(); showFallback(); return; }

  renderer.setPixelRatio(Math.min(window.devicePixelRatio, DPR_CAP));
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 0.90;
  renderer.outputEncoding = THREE.sRGBEncoding;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;

  const scene = new THREE.Scene();
  // alpha canvas – CSS gradient is the backdrop

  // --- Studio environment map ---
  const pmrem = new THREE.PMREMGenerator(renderer);
  pmrem.compileEquirectangularShader();
  const roomEnv = new RoomEnvironment();
  scene.environment = pmrem.fromScene(roomEnv, 0.04).texture;
  if (roomEnv.dispose) roomEnv.dispose();

  const camera = new THREE.PerspectiveCamera(FOV, container.clientWidth / Math.max(1, container.clientHeight), 0.1, 100);

  const mats = createMaterials();
  const maxAniso = renderer.capabilities.getMaxAnisotropy();
  for (const m of Object.values(mats)) {
    if (m.map) m.map.anisotropy = Math.min(ANISO, maxAniso);
    if (m.roughnessMap) m.roughnessMap.anisotropy = Math.min(ANISO, maxAniso);
    if (m.metalnessMap) m.metalnessMap.anisotropy = Math.min(ANISO, maxAniso);
  }

  // --- Assemble board ---
  const board = new THREE.Group();
  board.name = 'motherboard';
  const pcb = buildPCB(mats);
  board.add(pcb);
  const heatsink = buildHeatsink(mats);
  heatsink.position.set(-0.5, 0.102, -0.25);
  board.add(heatsink);

  // Stage 2 components
  const icChips = buildICChips(mats);
  board.add(icChips.group);
  board.add(buildRearIO(mats));
  board.add(buildMemoryAndPCIe(mats));
  board.add(buildPowerAndHeaders(mats));
  board.add(buildVRMAndCaps(mats));
  board.add(buildSMDs(mats));

  // Stage 3 pulses, status LEDs & click sweep band
  const tracePulses = buildTracePulses();
  board.add(tracePulses.group);
  const statusLEDs = buildStatusLEDs();
  board.add(statusLEDs.group);
  const sweepBand = buildSweepBand(mats.metalMaskTex);
  board.add(sweepBand.group);

  scene.add(board);

  // --- Contact shadow + Shadow floor ---
  const contactGeo = new THREE.PlaneGeometry(9.5, 7.0);
  const contactMesh = new THREE.Mesh(contactGeo, mats.contactShadow);
  contactMesh.rotation.x = -Math.PI / 2;
  contactMesh.position.y = -0.040;
  scene.add(contactMesh);

  const floorGeo = new THREE.PlaneGeometry(24, 24);
  const floor = new THREE.Mesh(floorGeo, mats.shadowFloor);
  floor.rotation.x = -Math.PI / 2;
  floor.position.y = -0.020;
  floor.receiveShadow = true;
  scene.add(floor);

  // --- LIGHTING (studio, balanced for 0.90 exposure) ---
  // Key: warm, top-left
  const key = new THREE.DirectionalLight(0xfff4e8, 1.15);
  key.position.set(-4, 10, 4);
  key.castShadow = true;
  key.shadow.mapSize.set(1024, 1024);
  key.shadow.camera.near = 0.5; key.shadow.camera.far = 25;
  key.shadow.camera.left = -6; key.shadow.camera.right = 6;
  key.shadow.camera.top = 6; key.shadow.camera.bottom = -6;
  key.shadow.bias = -0.0004;
  key.shadow.radius = 5;
  scene.add(key);

  // Rim: subtle cool blue, opposite
  const rim = new THREE.DirectionalLight(0x1a3588, 0.40);
  rim.position.set(5, 4, -5);
  scene.add(rim);

  // Fill: gentle overhead-front (keeps side wall dark)
  const fill = new THREE.DirectionalLight(0xd8e0f0, 0.15);
  fill.position.set(0, 5, 6);
  scene.add(fill);

  // Ambient
  const amb = new THREE.AmbientLight(0x101828, 0.20);
  scene.add(amb);

  // --- Camera (35° elevation, board fills ~80% with zero clipping) ---
  function fitCamera() {
    const box = new THREE.Box3().setFromObject(board);
    const center = box.getCenter(new THREE.Vector3());

    const phi   = THREE.MathUtils.degToRad(35);
    const theta = THREE.MathUtils.degToRad(25);
    const dir = new THREE.Vector3(
      Math.cos(phi) * Math.sin(theta),
      Math.sin(phi),
      Math.cos(phi) * Math.cos(theta)
    ).normalize();

    const worldUp = new THREE.Vector3(0, 1, 0);
    const right = new THREE.Vector3().crossVectors(worldUp, dir).normalize();
    const camUp = new THREE.Vector3().crossVectors(dir, right).normalize();

    const corners = [
      new THREE.Vector3(box.min.x, box.min.y, box.min.z),
      new THREE.Vector3(box.min.x, box.min.y, box.max.z),
      new THREE.Vector3(box.min.x, box.max.y, box.min.z),
      new THREE.Vector3(box.min.x, box.max.y, box.max.z),
      new THREE.Vector3(box.max.x, box.min.y, box.min.z),
      new THREE.Vector3(box.max.x, box.min.y, box.max.z),
      new THREE.Vector3(box.max.x, box.max.y, box.min.z),
      new THREE.Vector3(box.max.x, box.max.y, box.max.z),
    ];

    const vFov = FOV * Math.PI / 180;
    const tanHalfV = Math.tan(vFov / 2);
    const aspect = camera.aspect || (container.clientWidth / Math.max(1, container.clientHeight));
    const tanHalfH = tanHalfV * aspect;

    // Enlarge board by ~15% without clipping
    const fill = 1.03;
    const rel = new THREE.Vector3();
    let dist = 0;
    for (const c of corners) {
      rel.subVectors(c, center);
      const x = Math.abs(rel.dot(right));
      const y = Math.abs(rel.dot(camUp));
      const z = rel.dot(dir);
      dist = Math.max(dist, x / (fill * tanHalfH) + z, y / (fill * tanHalfV) + z);
    }

    camera.position.copy(center).addScaledVector(dir, dist);
    camera.lookAt(center);
    camera.updateProjectionMatrix();
  }
  fitCamera();

  function onResize() {
    const cw = container.clientWidth, ch = container.clientHeight;
    if (!cw || !ch) return;
    camera.aspect = cw / ch;
    camera.updateProjectionMatrix();
    renderer.setSize(cw, ch, false);
    fitCamera();
  }
  window.addEventListener('resize', onResize);
  onResize();

  // --- Mouse parallax & motion state ---
  const mouse = { x: 0, y: 0 };
  const tilt  = { x: 0, y: 0 };
  const curT  = { x: 0, y: 0 };
  const noMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  let ledStep = 0; // cyclic 0..3 only, never tracks password value or length
  let amberPulse = 0;

  function triggerTraceWave(speed = 0.95) {
    if (noMotion) return;
    tracePulses.pulses.forEach((p, idx) => {
      p.progress = -idx * 0.08;
      p.speed = speed;
    });
  }

  function triggerNextStatusLED() {
    if (noMotion) return;
    const led = statusLEDs.leds[ledStep];
    led.color.setHex(0x22ff66);
    led.intensity = 1.0;
    led.hold = 1.5;
    ledStep = (ledStep + 1) % statusLEDs.leds.length;
  }

  function triggerAmberErrorPulse() {
    amberPulse = 1.0;
    statusLEDs.leds.forEach(led => {
      led.color.setHex(0xf59e0b);
      led.intensity = 1.0;
      led.hold = 0.8;
    });
  }

  // Form event hooks (never read, store, or log typed values)
  const usernameEl = document.getElementById('usernameInput');
  if (usernameEl) {
    usernameEl.addEventListener('focus', () => triggerTraceWave(0.90));
  }
  const passwordEl = document.getElementById('passwordInput');
  if (passwordEl) {
    passwordEl.addEventListener('input', () => triggerNextStatusLED());
  }

  // Login error check after redirect/reload
  if (document.querySelector('.alert-danger, .alert-error')) {
    setTimeout(triggerAmberErrorPulse, 260);
  }

  container.addEventListener('mousemove', e => {
    if (noMotion) return;
    const r = container.getBoundingClientRect();
    mouse.x = ((e.clientX - r.left) / r.width  - 0.5) * 2;
    mouse.y = ((e.clientY - r.top)  / r.height - 0.5) * 2;
  });
  container.addEventListener('mouseleave', () => { mouse.x = 0; mouse.y = 0; });

  // Board click: sweep a thin band of light across it once
  let sweepProgress = -1;
  canvas.addEventListener('click', () => {
    if (noMotion) return;
    sweepProgress = 0;
  });

  // --- Render loop ---
  let running = true;
  let firstFrame = true;
  const clock = new THREE.Clock();

  function animate() {
    if (!running) return;
    requestAnimationFrame(animate);
    const dt = Math.min(clock.getDelta(), 0.05);
    const t  = clock.getElapsedTime();

    if (!noMotion) {
      // Idle: slow float + rotation within 1.5° (0.026 rad)
      board.position.y = Math.sin(t * 0.65) * 0.016;
      const idleRotY = Math.sin(t * 0.35) * 0.014;
      tilt.x = -mouse.y * 0.042;
      tilt.y =  mouse.x * 0.055;
      const damp = 1 - Math.exp(-3.5 * dt);
      curT.x += (tilt.x - curT.x) * damp;
      curT.y += (tilt.y - curT.y) * damp;
      board.rotation.x = curT.x;
      board.rotation.y = idleRotY + curT.y * 0.5;
      board.rotation.z = -curT.y * 0.22;

      // Update trace pulses
      for (const p of tracePulses.pulses) {
        if (p.progress >= -1 && p.progress < 1.05) {
          p.progress += dt * p.speed;
          if (p.progress >= 0 && p.progress <= 1.0) {
            p.mesh.position.x = THREE.MathUtils.lerp(p.start[0], p.end[0], p.progress);
            p.mesh.position.z = THREE.MathUtils.lerp(p.start[1], p.end[1], p.progress);
            p.mat.opacity = Math.sin(p.progress * Math.PI) * 0.72;
          } else {
            p.mat.opacity = 0;
          }
        } else {
          p.mat.opacity = 0;
        }
      }

      // Update status LEDs (hold 1.5s, then fade smoothly)
      for (const led of statusLEDs.leds) {
        if (led.hold > 0) {
          led.hold = Math.max(0, led.hold - dt);
        } else if (led.intensity > 0.01) {
          led.intensity = Math.max(0, led.intensity - dt * 1.2);
        } else {
          led.intensity = 0;
        }
        led.lensMat.emissive.copy(led.color);
        led.lensMat.emissiveIntensity = 0.06 + led.intensity * 2.4;
        led.haloMat.color.copy(led.color);
        led.haloMat.opacity = led.intensity * 0.72;
      }

      if (amberPulse > 0) {
        amberPulse = Math.max(0, amberPulse - dt * 0.85);
      }

      // Update click-to-sweep light band + trace & chip soft glow
      if (sweepProgress >= 0 && sweepProgress <= 1.0) {
        sweepProgress += dt * 0.85;
        const sx = THREE.MathUtils.lerp(-PCB_W / 2 - 0.45, PCB_W / 2 + 0.45, Math.min(sweepProgress, 1.0));
        const env = Math.sin(Math.min(sweepProgress, 1.0) * Math.PI);
        sweepBand.bandMesh.position.x = sx;
        sweepBand.bandMat.opacity = env * 0.85;
        sweepBand.traceGlowMat.uniforms.uSweepX.value = sx;
        sweepBand.traceGlowMat.uniforms.uStrength.value = env;
        for (const t of icChips.chipGlowTargets) {
          const d = (sx - t.cx) / 0.52;
          t.mat.emissiveIntensity = Math.exp(-d * d) * env * 0.90;
        }
        if (sweepProgress > 1.0) {
          sweepProgress = -1;
          sweepBand.bandMat.opacity = 0;
          sweepBand.traceGlowMat.uniforms.uStrength.value = 0;
          for (const t of icChips.chipGlowTargets) t.mat.emissiveIntensity = 0;
        }
      }
    }

    renderer.render(scene, camera);
    if (firstFrame) {
      firstFrame = false;
      loaderEl.style.opacity = '0';
      setTimeout(() => loaderEl.remove(), 260);
    }
  }
  animate();

  document.addEventListener('visibilitychange', () => {
    if (document.hidden) { running = false; clock.stop(); }
    else { running = true; clock.start(); animate(); }
  });

  // --- Submit effect: pulses converge on processor without delaying form submission ---
  window.triggerBoardPowerOn = function (cb) {
    triggerTraceWave(2.2);
    statusLEDs.leds.forEach(led => {
      led.color.setHex(0x22ff66);
      led.intensity = 1.0;
      led.hold = 1.5;
    });
    if (cb) cb();
  };

  console.log('[Electrodesk] Studio motherboard scene initialised (Stage 3)');
}

/* ═══════════════════════════════════════════════════════════
   5.  FALLBACK
   ═══════════════════════════════════════════════════════════ */
function showFallback() {
  const c = document.getElementById('login-canvas-container');
  if (!c) return;
  c.innerHTML = `
    <div class="webgl-fallback-container">
      <div class="fallback-glow"></div>
      <img src="/static/images/motherboard-fallback.png" alt="Electrodesk Motherboard" class="webgl-fallback-image" />
      <span class="fallback-caption">ELECTRODESK CIRCUIT BOARD</span>
    </div>`;
}

/* ═══════════════════════════════════════════════════════════
   6.  BOOTSTRAP
   ═══════════════════════════════════════════════════════════ */
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initCircuitBoardScene);
} else {
  initCircuitBoardScene();
}
window.initCircuitBoardScene = initCircuitBoardScene;
window.initLoginScene = initCircuitBoardScene;
