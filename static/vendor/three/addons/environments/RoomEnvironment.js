/**
 * RoomEnvironment – procedural studio box for PBR reflections.
 * Compatible with Three.js r143+.
 * Simplified from three/examples/jsm/environments/RoomEnvironment.js
 */

import {
  BackSide,
  BoxGeometry,
  Color,
  Mesh,
  MeshStandardMaterial,
  PointLight,
  Scene,
} from 'three';

class RoomEnvironment extends Scene {

  constructor() {
    super();

    const geometry = new BoxGeometry();
    geometry.deleteAttribute('uv');

    const roomMaterial = new MeshStandardMaterial({
      side: BackSide,
      color: new Color(0.47, 0.47, 0.47),
    });
    const boxMesh = new Mesh(geometry, roomMaterial);
    boxMesh.scale.setScalar(10);
    this.add(boxMesh);

    // --- studio point lights for soft PBR env illumination ---

    // Main key – warm upper light
    const mainLight = new PointLight(0xfff4e8, 30, 0, 2);
    mainLight.position.set(0.42, 1.6, 0.30);
    this.add(mainLight);

    // Fill 1 – cool rear
    const fill1 = new PointLight(0xd4e4ff, 10, 0, 2);
    fill1.position.set(-1.1, -0.2, -1.45);
    this.add(fill1);

    // Fill 2 – warm front-side
    const fill2 = new PointLight(0xfff0dd, 10, 0, 2);
    fill2.position.set(1.4, -0.6, 1.4);
    this.add(fill2);

    // Floor panel – darker for ground reflection contrast
    const floorGeo = new BoxGeometry();
    floorGeo.deleteAttribute('uv');
    const floorMat = new MeshStandardMaterial({
      side: BackSide,
      color: new Color(0.35, 0.35, 0.35),
    });
    const floorMesh = new Mesh(floorGeo, floorMat);
    floorMesh.position.set(0, -3.12, 0);
    floorMesh.scale.set(14, 0.1, 14);
    this.add(floorMesh);

    // Ceiling panel – bright for soft top reflections
    const ceilGeo = new BoxGeometry();
    ceilGeo.deleteAttribute('uv');
    const ceilMat = new MeshStandardMaterial({
      side: BackSide,
      color: new Color(0.9, 0.9, 0.9),
    });
    const ceilMesh = new Mesh(ceilGeo, ceilMat);
    ceilMesh.position.set(0, 3.12, 0);
    ceilMesh.scale.set(14, 0.1, 14);
    this.add(ceilMesh);
  }

  dispose() {
    this.traverse((child) => {
      if (child.geometry) child.geometry.dispose();
      if (child.material) {
        if (Array.isArray(child.material)) {
          child.material.forEach(m => m.dispose());
        } else {
          child.material.dispose();
        }
      }
    });
  }
}

export { RoomEnvironment };
