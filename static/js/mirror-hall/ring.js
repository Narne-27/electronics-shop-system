/**
 * Electrodesk - Mirror Hall 3D Section Carousel
 * Card Ring, Rounded Geometries, Mirrored Reflection Clones & Bobbing
 */

import * as THREE from 'three';
import { CONFIG } from './config.js';
import { createCardTexture } from './cardTexture.js';

/**
 * Creates rounded rectangle shape
 */
function createRoundedRectShape(w, h, r) {
  const shape = new THREE.Shape();
  const hw = w / 2;
  const hh = h / 2;
  shape.moveTo(-hw + r, -hh);
  shape.lineTo(hw - r, -hh);
  shape.absarc(hw - r, -hh + r, r, -Math.PI / 2, 0, false);
  shape.lineTo(hw, hh - r);
  shape.absarc(hw - r, hh - r, r, 0, Math.PI / 2, false);
  shape.lineTo(-hw + r, hh);
  shape.absarc(-hw + r, hh - r, r, Math.PI / 2, Math.PI, false);
  shape.lineTo(-hw, -hh + r);
  shape.absarc(-hw + r, -hh + r, r, Math.PI, Math.PI * 1.5, false);
  return shape;
}

/**
 * Custom shader material for soft vertical gradient reflection fading into dark water
 */
function createReflectionMaterial(texture, baseColor) {
  return new THREE.ShaderMaterial({
    transparent: true,
    depthWrite: false,
    uniforms: {
      tCard: { value: texture },
      uBaseOpacity: { value: CONFIG.reflectionOpacityBase },
      uHeightFade: { value: CONFIG.reflectionHeightFade },
      uColorTint: { value: new THREE.Color(baseColor || 0x2bf0ff) }
    },
    vertexShader: `
      varying vec2 vUv;
      varying float vRelY;
      void main() {
        vUv = uv;
        vRelY = position.y; // 0 at base, increases downwards in inverted space
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      }
    `,
    fragmentShader: `
      uniform sampler2D tCard;
      uniform float uBaseOpacity;
      uniform float uHeightFade;
      uniform vec3 uColorTint;
      varying vec2 vUv;
      varying float vRelY;

      void main() {
        vec4 tex = texture2D(tCard, vUv);
        // Vertical gradient: brightest at the base, fading to 0 by height fade
        float normY = max(0.0, vUv.y);
        float fade = smoothstep(uHeightFade, 0.05, normY);
        float alpha = tex.a * fade * uBaseOpacity;
        vec3 col = mix(tex.rgb, uColorTint, 0.15) * (0.65 + fade * 0.35);
        gl_FragColor = vec4(col, alpha);
      }
    `
  });
}

/**
 * Builds the 3D ring of cards and mirrored reflections
 */
export function createCardRing(scene, sections) {
  const ringGroup = new THREE.Group();
  scene.add(ringGroup);

  const N = sections.length;
  const angleStep = (Math.PI * 2) / N;

  // Derive radius so cards never touch
  const minCircumference = N * (CONFIG.cardWidth * 1.6);
  const ringRadius = Math.max(3.8, (minCircumference / (Math.PI * 2)) * CONFIG.ringRadiusFactor);

  const cardShape = createRoundedRectShape(CONFIG.cardWidth, CONFIG.cardHeight, CONFIG.cardRadius);
  const cardGeo = new THREE.ShapeGeometry(cardShape);

  // Slightly extruded backplate for 3D depth
  const backGeo = new THREE.BoxGeometry(CONFIG.cardWidth, CONFIG.cardHeight, 0.06);

  const cards = [];
  const cardMaterials = [];
  const textures = [];

  for (let i = 0; i < N; i++) {
    const sec = sections[i];
    const angle = i * angleStep;

    const cardContainer = new THREE.Group();
    cardContainer.userData = {
      index: i,
      section: sec,
      baseAngle: angle,
      targetAngle: angle,
      color: new THREE.Color(sec.accent || '#2bf0ff')
    };

    // 1. Procedural Front Texture
    const texture = createCardTexture(sec, i);
    textures.push(texture);

    const cardMat = new THREE.MeshBasicMaterial({
      map: texture,
      transparent: true,
      side: THREE.FrontSide
    });
    cardMaterials.push(cardMat);

    const frontMesh = new THREE.Mesh(cardGeo, cardMat);
    frontMesh.position.z = 0.035;

    // 2. Beveled Dark Glass Backplate
    const backMat = new THREE.MeshStandardMaterial({
      color: 0x070318,
      roughness: 0.35,
      metalness: 0.75,
      emissive: new THREE.Color(sec.accent || 0x2bf0ff),
      emissiveIntensity: CONFIG.cardEmissiveBase
    });
    const backMesh = new THREE.Mesh(backGeo, backMat);
    backMesh.position.z = 0;

    // Card assembly
    const upperCard = new THREE.Group();
    upperCard.add(backMesh);
    upperCard.add(frontMesh);

    // Anchor at card base (y = 0 at pool surface)
    upperCard.position.y = CONFIG.cardHeight / 2;
    cardContainer.add(upperCard);

    // 3. Mirrored Reflection Below Pool Surface (y < 0)
    const reflMat = createReflectionMaterial(texture, sec.accent);
    const reflMesh = new THREE.Mesh(cardGeo, reflMat);
    reflMesh.scale.y = -1;
    reflMesh.position.y = -CONFIG.cardHeight / 2;
    reflMesh.position.z = 0.02;
    cardContainer.add(reflMesh);

    // Position on ring circle
    const x = Math.sin(angle) * ringRadius;
    const z = Math.cos(angle) * ringRadius;
    cardContainer.position.set(x, 0, z);

    // Look at ring center, plus slight inward tilt
    cardContainer.rotation.y = angle;
    cardContainer.rotation.x = -CONFIG.cardTilt;

    ringGroup.add(cardContainer);

    cards.push({
      container: cardContainer,
      upperCard: upperCard,
      frontMesh: frontMesh,
      backMesh: backMesh,
      backMat: backMat,
      reflMesh: reflMesh,
      reflMat: reflMat,
      section: sec,
      index: i,
      baseAngle: angle,
      anchorWorldPos: new THREE.Vector3()
    });
  }

  return {
    group: ringGroup,
    cards: cards,
    ringRadius: ringRadius,
    update(rotationAngle, time, isReducedMotion) {
      ringGroup.rotation.y = rotationAngle;

      let focusedIndex = 0;
      let minAngularDist = Infinity;
      let focusedCardObj = null;

      const normAngle = ((rotationAngle % (Math.PI * 2)) + Math.PI * 2) % (Math.PI * 2);

      for (let i = 0; i < cards.length; i++) {
        const item = cards[i];
        const card = item.container;

        // Current world angle relative to front camera (angle = 0 is front)
        let worldAngle = (item.baseAngle + normAngle) % (Math.PI * 2);
        if (worldAngle > Math.PI) worldAngle -= Math.PI * 2; // Range [-PI, PI]

        const absDist = Math.abs(worldAngle);
        if (absDist < minAngularDist) {
          minAngularDist = absDist;
          focusedIndex = i;
          focusedCardObj = item;
        }

        // Focus falloff curve (1 at center, ~0.65 at edges, ~0.35 at back)
        const focusFactor = Math.max(0, Math.min(1, 1.0 - absDist / (Math.PI * 0.75)));
        const scale = 1.0 + 0.12 * Math.pow(focusFactor, 2.0);

        // Gentle floating bob & breathing
        if (!isReducedMotion) {
          const bob = Math.sin(time * CONFIG.bobFrequency + i * 0.9) * CONFIG.bobAmplitude;
          item.upperCard.position.y = CONFIG.cardHeight / 2 + bob;
          item.reflMesh.position.y = -CONFIG.cardHeight / 2 - bob;

          const breath = 1.0 + Math.sin(time * 2.0 + i) * CONFIG.breathAmplitude;
          item.backMat.emissiveIntensity = THREE.MathUtils.lerp(
            CONFIG.cardEmissiveBase,
            CONFIG.cardEmissiveFocus * breath,
            focusFactor
          );
        } else {
          item.backMat.emissiveIntensity = THREE.MathUtils.lerp(
            CONFIG.cardEmissiveBase,
            CONFIG.cardEmissiveFocus,
            focusFactor
          );
        }

        // Scale and depth perspective
        card.scale.setScalar(scale);

        // Update 3D label projection anchor point (just above card top)
        item.upperCard.getWorldPosition(item.anchorWorldPos);
        item.anchorWorldPos.y += CONFIG.cardHeight / 2 + 0.28;
      }

      return {
        focusedIndex,
        focusedCard: focusedCardObj,
        focusedPosition: focusedCardObj ? focusedCardObj.container.position : null,
        activeColor: focusedCardObj ? focusedCardObj.container.userData.color : null
      };
    },
    dispose() {
      cardGeo.dispose();
      backGeo.dispose();
      textures.forEach((t) => t.dispose());
      cardMaterials.forEach((m) => m.dispose());
      cards.forEach((c) => {
        c.backMat.dispose();
        c.reflMat.dispose();
      });
      scene.remove(ringGroup);
    }
  };
}
