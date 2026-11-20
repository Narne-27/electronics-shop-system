/**
 * Electrodesk - Mirror Hall 3D Section Carousel
 * Inertia Physics, Damped Spring Snapping & Multimodal Input Controller
 */

import * as THREE from 'three';
import { CONFIG } from './config.js';

export function createInputController(domElement, camera, cardObjects, options = {}) {
  const { onNavigate, onHoverChange } = options;

  let currentAngle = 0;
  let targetAngle = 0;
  let angularVelocity = 0;
  let isDragging = false;
  let hasPointer = false;

  let startX = 0;
  let lastX = 0;
  let totalDragDistance = 0;
  let lastPointerTime = 0;

  const N = cardObjects.length;
  const angleStep = (Math.PI * 2) / N;

  const raycaster = new THREE.Raycaster();
  const mouse = new THREE.Vector2(-999, -999);
  let hoveredCard = null;

  // Flatten front meshes for raycasting
  const clickableMeshes = cardObjects.map((c) => c.frontMesh);

  function getCardFromMesh(mesh) {
    return cardObjects.find((c) => c.frontMesh === mesh || c.backMesh === mesh);
  }

  // Pointer Events (Mouse, Touch, Pen)
  function onPointerDown(e) {
    if (e.button !== undefined && e.button !== 0) return; // Only primary button
    isDragging = true;
    hasPointer = true;
    startX = e.clientX;
    lastX = e.clientX;
    totalDragDistance = 0;
    angularVelocity = 0;
    lastPointerTime = performance.now();
    domElement.style.cursor = 'grabbing';
    domElement.setPointerCapture(e.pointerId);
  }

  function onPointerMove(e) {
    const rect = domElement.getBoundingClientRect();
    mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
    mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;

    if (!isDragging) {
      // Hover Raycast
      raycaster.setFromCamera(mouse, camera);
      const hits = raycaster.intersectObjects(clickableMeshes, false);
      if (hits.length > 0) {
        const found = getCardFromMesh(hits[0].object);
        if (found !== hoveredCard) {
          hoveredCard = found;
          if (onHoverChange) onHoverChange(hoveredCard);
        }
        domElement.style.cursor = 'pointer';
      } else {
        if (hoveredCard) {
          hoveredCard = null;
          if (onHoverChange) onHoverChange(null);
        }
        domElement.style.cursor = 'grab';
      }
      return;
    }

    const now = performance.now();
    const dt = Math.max(0.001, (now - lastPointerTime) / 1000);
    lastPointerTime = now;

    const dx = e.clientX - lastX;
    lastX = e.clientX;
    totalDragDistance += Math.abs(dx);

    const deltaAngle = dx * CONFIG.dragSensitivity;
    currentAngle += deltaAngle;
    angularVelocity = deltaAngle / dt;

    // Clamp maximum drag fling velocity
    angularVelocity = THREE.MathUtils.clamp(
      angularVelocity,
      -CONFIG.velocityClamp,
      CONFIG.velocityClamp
    );
  }

  function onPointerUp(e) {
    if (!isDragging) return;
    isDragging = false;
    domElement.style.cursor = hoveredCard ? 'pointer' : 'grab';
    try {
      domElement.releasePointerCapture(e.pointerId);
    } catch (_) {}

    // Check click-without-drag (< 6px movement)
    if (totalDragDistance < CONFIG.clickDragThreshold) {
      raycaster.setFromCamera(mouse, camera);
      const hits = raycaster.intersectObjects(clickableMeshes, false);
      if (hits.length > 0) {
        const clicked = getCardFromMesh(hits[0].object);
        if (clicked) {
          handleCardClick(clicked);
        }
      }
    }
  }

  function handleCardClick(cardItem) {
    const targetIdx = cardItem.index;
    const currentNearestIdx = Math.round(-currentAngle / angleStep);

    // Compute shortest angular delta to center this card
    const currentNormIdx = ((currentNearestIdx % N) + N) % N;
    let diff = targetIdx - currentNormIdx;
    if (diff > N / 2) diff -= N;
    if (diff < -N / 2) diff += N;

    if (diff === 0) {
      // Clicked on focused card -> Navigate!
      if (onNavigate) onNavigate(cardItem.section);
    } else {
      // Clicked on neighbor card -> Rotate to center it
      targetAngle = -(currentNearestIdx + diff) * angleStep;
      angularVelocity = (targetAngle - currentAngle) * 3.5;
    }
  }

  // Wheel / Trackpad horizontal scroll
  function onWheel(e) {
    const delta = Math.abs(e.deltaX) > Math.abs(e.deltaY) ? e.deltaX : e.deltaY;
    if (Math.abs(delta) > 2) {
      e.preventDefault();
      angularVelocity -= Math.sign(delta) * CONFIG.wheelSensitivity * 15;
    }
  }

  // Keyboard navigation
  function onKeyDown(e) {
    if (e.target && ['input', 'textarea', 'select'].includes(e.target.tagName.toLowerCase())) {
      return;
    }

    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
      e.preventDefault();
      stepTarget(-1);
    } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
      e.preventDefault();
      stepTarget(1);
    } else if (e.key === 'Home') {
      e.preventDefault();
      jumpToIndex(0);
    } else if (e.key === 'End') {
      e.preventDefault();
      jumpToIndex(N - 1);
    } else if (e.key >= '1' && e.key <= '9') {
      const idx = parseInt(e.key, 10) - 1;
      if (idx < N) {
        e.preventDefault();
        jumpToIndex(idx);
      }
    } else if (e.key === 'Enter' || e.key === ' ') {
      // Navigate to current active card
      const currentNearestIdx = ((Math.round(-currentAngle / angleStep) % N) + N) % N;
      const activeCard = cardObjects[currentNearestIdx];
      if (activeCard && onNavigate) {
        e.preventDefault();
        onNavigate(activeCard.section);
      }
    }
  }

  function stepTarget(direction) {
    const currentNearestIdx = Math.round(-currentAngle / angleStep);
    targetAngle = -(currentNearestIdx + direction) * angleStep;
    angularVelocity += direction * 0.9;
  }

  function jumpToIndex(targetIdx) {
    const currentNearestIdx = Math.round(-currentAngle / angleStep);
    const currentNorm = ((currentNearestIdx % N) + N) % N;
    let diff = targetIdx - currentNorm;
    if (diff > N / 2) diff -= N;
    if (diff < -N / 2) diff += N;
    targetAngle = -(currentNearestIdx + diff) * angleStep;
    angularVelocity = (targetAngle - currentAngle) * 4.0;
  }

  // Attach Event Listeners
  domElement.addEventListener('pointerdown', onPointerDown, { passive: false });
  window.addEventListener('pointermove', onPointerMove, { passive: true });
  window.addEventListener('pointerup', onPointerUp, { passive: true });
  window.addEventListener('pointercancel', onPointerUp, { passive: true });
  domElement.addEventListener('wheel', onWheel, { passive: false });
  window.addEventListener('keydown', onKeyDown);

  return {
    getAngle() {
      return currentAngle;
    },
    getAngularVelocity() {
      return angularVelocity;
    },
    isDragging() {
      return isDragging;
    },
    goTo(index) {
      jumpToIndex(index);
    },
    update(dt) {
      if (!isDragging) {
        // Inertia damping
        angularVelocity *= Math.pow(CONFIG.inertiaDamping, dt * 60);

        // Check if velocity is low enough to snap to nearest card
        if (Math.abs(angularVelocity) < CONFIG.snapThreshold) {
          const nearestStep = Math.round(-currentAngle / angleStep);
          targetAngle = -nearestStep * angleStep;

          // Critically damped spring snapping physics
          const displacement = targetAngle - currentAngle;
          const springForce = displacement * CONFIG.springK;
          const dampingForce = -angularVelocity * CONFIG.springDamping;
          angularVelocity += (springForce + dampingForce) * dt;

          if (Math.abs(displacement) < 0.0005 && Math.abs(angularVelocity) < 0.001) {
            currentAngle = targetAngle;
            angularVelocity = 0;
          }
        }

        currentAngle += angularVelocity * dt;
      }

      return {
        angle: currentAngle,
        velocity: angularVelocity
      };
    },
    dispose() {
      domElement.removeEventListener('pointerdown', onPointerDown);
      window.removeEventListener('pointermove', onPointerMove);
      window.removeEventListener('pointerup', onPointerUp);
      window.removeEventListener('pointercancel', onPointerUp);
      domElement.removeEventListener('wheel', onWheel);
      window.removeEventListener('keydown', onKeyDown);
    }
  };
}
