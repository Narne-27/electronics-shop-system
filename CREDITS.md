# Credits & Asset Attributions

All 3D geometry, textures, shaders, and visual assets for the Electrodesk `/login` motherboard scene are either procedurally generated in-house or built on MIT-licensed open-source libraries.

## Libraries

- **Three.js (r143)** — 3D WebGL rendering engine, `PMREMGenerator`, `ACESFilmicToneMapping`, `PCFSoftShadowMap`, and `InstancedMesh`
  - Source: `static/vendor/three/three.module.js`
  - License: MIT License (Copyright © 2010-2022 three.js authors)
- **RoomEnvironment** — Procedural studio environment lighting room for `PMREMGenerator`
  - Source: `static/vendor/three/addons/environments/RoomEnvironment.js`
  - License: MIT License (adapted from Three.js addons)
- **Bootstrap 5 & Bootstrap Icons** — UI layout and fallback icons
  - License: MIT License

## Procedural & In-House Assets

- **Motherboard Geometry & Components (`static/js/circuit-board.js`)** — Procedural PCB slab, brushed aluminium heatsink with copper heat pipes, dark stainless-steel Phillips screws, QFP/SOIC IC packages with gull-wing pins, Rear I/O ports, DDR5 DIMM & PCIe x16 slots, ATX/EPS power connectors, gold pin headers, VRM chokes, cylindrical capacitors, 430 InstancedMesh SMD resistors/capacitors, and status LEDs. (100% procedural Three.js geometry)
- **Procedural Textures (`static/js/circuit-board.js`)** — 2048×2048 PCB solder-mask color, roughness, and metalness maps; brushed metal roughness map; heatsink fin AO gradient; IC laser-etched markings; and radial contact shadow texture. (100% procedural HTML5 Canvas)
- **Static WebGL Fallback Image (`static/images/motherboard-fallback.png`)** — Static render captured directly from the Electrodesk 3D motherboard scene for browsers where WebGL is unavailable.
