/**
 * Electrodesk - Mirror Hall 3D Section Carousel
 * Reflective Water Pool with Dynamic Ripple Distortion & Radial Glow
 */

import * as THREE from 'three';
import { CONFIG } from './config.js';

/**
 * Creates the reflective water plane and dynamic lighting pool
 */
export function createReflectivePool(scene) {
  const poolGroup = new THREE.Group();

  // 1. Water Surface Geometry
  const geo = new THREE.PlaneGeometry(CONFIG.poolWidth, CONFIG.poolHeight, 64, 64);
  geo.rotateX(-Math.PI / 2);

  // 2. Water Surface Shader with Procedural Ripples & Light Pool
  const waterUniforms = {
    uTime: { value: 0 },
    uRippleAmp: { value: CONFIG.rippleAmplitude },
    uFocusedCardPos: { value: new THREE.Vector3(0, 0, 4.8) },
    uLightPoolRadius: { value: CONFIG.lightPoolRadius },
    uBaseColor: { value: new THREE.Color(CONFIG.poolColor) },
    uAccentColor: { value: new THREE.Color(0x2bf0ff) }
  };

  const waterMat = new THREE.ShaderMaterial({
    transparent: true,
    depthWrite: false,
    uniforms: waterUniforms,
    vertexShader: `
      uniform float uTime;
      uniform float uRippleAmp;
      varying vec2 vUv;
      varying vec3 vWorldPos;

      void main() {
        vUv = uv;
        vec3 p = position;

        // Subtle fluid ripple displacement
        float r = length(p.xz);
        float wave = sin(r * 3.5 - uTime * 2.2) * cos(p.x * 2.0 + uTime * 1.5);
        p.y += wave * uRippleAmp * 0.08;

        vec4 worldPosition = modelMatrix * vec4(p, 1.0);
        vWorldPos = worldPosition.xyz;
        gl_Position = projectionMatrix * viewMatrix * worldPosition;
      }
    `,
    fragmentShader: `
      uniform float uTime;
      uniform float uRippleAmp;
      uniform vec3 uFocusedCardPos;
      uniform float uLightPoolRadius;
      uniform vec3 uBaseColor;
      uniform vec3 uAccentColor;

      varying vec2 vUv;
      varying vec3 vWorldPos;

      void main() {
        // Distance to active centered card
        float distToFocused = length(vWorldPos.xz - uFocusedCardPos.xz);
        float lightPool = smoothstep(uLightPoolRadius, 0.2, distToFocused) * 0.55;

        // Fluid ripple highlights
        float ripple1 = sin((vWorldPos.x + vWorldPos.z) * 4.0 - uTime * 2.5);
        float ripple2 = cos((vWorldPos.x * 0.8 - vWorldPos.z * 1.2) * 5.0 + uTime * 3.0);
        float specularStreak = pow(max(0.0, 0.5 + 0.5 * (ripple1 + ripple2)), 4.0) * uRippleAmp * 2.5;

        // Radial falloff from center of pool
        float distFromCenter = length(vWorldPos.xz);
        float poolFade = smoothstep(14.0, 2.0, distFromCenter);

        // Mix pool base with dynamic active card accent glow
        vec3 col = uBaseColor;
        col += uAccentColor * lightPool;
        col += vec3(0.5, 0.9, 1.0) * specularStreak * lightPool;

        float alpha = (0.85 + lightPool * 0.25) * poolFade;
        gl_FragColor = vec4(col, alpha);
      }
    `
  });

  const waterMesh = new THREE.Mesh(geo, waterMat);
  waterMesh.position.y = 0;
  poolGroup.add(waterMesh);

  // 3. Ambient Specular Ring Guide
  const ringGuideGeo = new THREE.RingGeometry(4.7, 4.9, 64);
  ringGuideGeo.rotateX(-Math.PI / 2);
  const ringGuideMat = new THREE.MeshBasicMaterial({
    color: 0x2bf0ff,
    transparent: true,
    opacity: 0.08,
    side: THREE.DoubleSide
  });
  const ringGuideMesh = new THREE.Mesh(ringGuideGeo, ringGuideMat);
  ringGuideMesh.position.y = 0.002;
  poolGroup.add(ringGuideMesh);

  scene.add(poolGroup);

  return {
    group: poolGroup,
    uniforms: waterUniforms,
    update(time, angularVelocity, focusedPos, activeColor) {
      waterUniforms.uTime.value = time * CONFIG.rippleSpeed;

      // Ripple amplitude surges with rotation speed
      const speedSurge = Math.min(0.25, Math.abs(angularVelocity) * CONFIG.rippleVelocityFactor);
      waterUniforms.uRippleAmp.value = THREE.MathUtils.lerp(
        waterUniforms.uRippleAmp.value,
        CONFIG.rippleAmplitude + speedSurge,
        0.12
      );

      if (focusedPos) {
        waterUniforms.uFocusedCardPos.value.copy(focusedPos);
      }
      if (activeColor) {
        waterUniforms.uAccentColor.value.lerp(activeColor, 0.08);
      }
    },
    dispose() {
      geo.dispose();
      waterMat.dispose();
      ringGuideGeo.dispose();
      ringGuideMat.dispose();
      scene.remove(poolGroup);
    }
  };
}
