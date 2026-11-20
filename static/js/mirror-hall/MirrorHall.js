/**
 * Electrodesk - Mirror Hall 3D Section Carousel
 * Main Orchestrator: Scene Lifecycle, Entrance Animation, Camera Parallax & Responsive Loop
 */

import * as THREE from 'three';
import { CONFIG } from './config.js';
import { createCardRing } from './ring.js';
import { createReflectivePool } from './pool.js';
import { createInputController } from './input.js';
import { createHudController } from './hud.js';

export class MirrorHall {
  constructor() {
    this.container = null;
    this.sections = [];
    this.callbacks = {
      change: [],
      navigate: []
    };

    this.renderer = null;
    this.scene = null;
    this.camera = null;
    this.ring = null;
    this.pool = null;
    this.input = null;
    this.hud = null;

    this.rAFId = null;
    this.isDisposed = false;
    this.isPaused = false;
    this.isNavigating = false;
    this.isReducedMotion = false;

    // Pointer Parallax
    this.mouseTarget = { x: 0, y: 0 };
    this.mouseSmooth = { x: 0, y: 0 };

    // Performance auto-degrade monitor
    this.frameTimes = [];
    this.lastFrameTime = performance.now();
    this.isQualityDegraded = false;
  }

  /**
   * Event Listener API
   */
  on(event, callback) {
    if (this.callbacks[event]) {
      this.callbacks[event].push(callback);
    }
    return this;
  }

  emit(event, data) {
    if (this.callbacks[event]) {
      this.callbacks[event].forEach((cb) => {
        try {
          cb(data);
        } catch (err) {
          console.error(`MirrorHall ${event} handler error:`, err);
        }
      });
    }
  }

  /**
   * Public navigation method
   */
  goTo(index) {
    if (this.input) {
      this.input.goTo(index);
    }
  }

  /**
   * Initializes the 3D WebGL scene or gracefully falls back to CSS grid
   */
  init(container, sections) {
    this.container = container;
    this.sections = sections || [];

    // Reduced motion check
    const motionQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    this.isReducedMotion = motionQuery.matches;

    // Check WebGL availability
    if (!this.isWebGLAvailable()) {
      console.warn('WebGL not available, activating accessible CSS grid fallback.');
      this.renderAccessibleFallback();
      return this;
    }

    try {
      this.setupScene();
      this.setupComponents();
      this.setupEvents();
      this.startEntranceAnimation();
      this.animate();
    } catch (err) {
      console.error('MirrorHall WebGL initialization error:', err);
      this.renderAccessibleFallback();
    }

    return this;
  }

  isWebGLAvailable() {
    try {
      const canvas = document.createElement('canvas');
      return !!(window.WebGLRenderingContext && (canvas.getContext('webgl') || canvas.getContext('experimental-webgl')));
    } catch (_) {
      return false;
    }
  }

  setupScene() {
    const width = this.container.clientWidth || window.innerWidth;
    const height = this.container.clientHeight || window.innerHeight;
    const isMobile = width < CONFIG.mobileBreakpoint;
    const dpr = Math.min(window.devicePixelRatio || 1, isMobile ? CONFIG.maxDprMobile : CONFIG.maxDprDesktop);

    // Renderer
    this.renderer = new THREE.WebGLRenderer({
      antialias: true,
      alpha: true,
      powerPreference: 'high-performance'
    });
    this.renderer.setPixelRatio(dpr);
    this.renderer.setSize(width, height, false);
    this.renderer.outputEncoding = THREE.sRGBEncoding;

    const canvas = this.renderer.domElement;
    canvas.className = 'mh-canvas';
    this.container.appendChild(canvas);

    // Scene & Dark Atmospheric Fog
    this.scene = new THREE.Scene();
    this.scene.fog = new THREE.Fog(CONFIG.fogColor, CONFIG.fogNear, CONFIG.fogFar);

    // Perspective Camera
    const aspect = width / height;
    this.camera = new THREE.PerspectiveCamera(CONFIG.cameraFov, aspect, 0.1, 100);
    this.camera.position.set(0, CONFIG.cameraY, CONFIG.cameraZ);
    this.camera.lookAt(0, CONFIG.lookAtY, 0);

    // Ambient & Directional Lighting
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.85);
    this.scene.add(ambientLight);

    const keyLight = new THREE.DirectionalLight(0x2bf0ff, 1.2);
    keyLight.position.set(5, 10, 8);
    this.scene.add(keyLight);

    const rimLight = new THREE.DirectionalLight(0x7a3cff, 0.9);
    rimLight.position.set(-6, 8, -5);
    this.scene.add(rimLight);
  }

  setupComponents() {
    // 1. Water Surface Pool
    this.pool = createReflectivePool(this.scene);

    // 2. Card Ring & Reflections
    this.ring = createCardRing(this.scene, this.sections);

    // 3. Multi-modal Input Controller
    this.input = createInputController(this.renderer.domElement, this.camera, this.ring.cards, {
      onNavigate: (section) => this.handleNavigate(section),
      onHoverChange: (hoveredCard) => {
        // Can add subtle cursor or edge highlight
      }
    });

    // 4. HUD Overlay & Labels
    this.hud = createHudController(this.container, this.sections, {
      onSelectIndex: (idx) => this.goTo(idx),
      onNavigate: (section) => this.handleNavigate(section)
    });
  }

  setupEvents() {
    this._onResize = () => this.handleResize();
    window.addEventListener('resize', this._onResize, { passive: true });

    this._onPointerMove = (e) => {
      this.mouseTarget.x = (e.clientX / window.innerWidth) * 2 - 1;
      this.mouseTarget.y = -((e.clientY / window.innerHeight) * 2 - 1);
    };
    window.addEventListener('mousemove', this._onPointerMove, { passive: true });

    this._onVisibilityChange = () => {
      this.isPaused = document.hidden;
      if (!this.isPaused) {
        this.lastFrameTime = performance.now();
      }
    };
    document.addEventListener('visibilitychange', this._onVisibilityChange);

    // IntersectionObserver to pause rendering when scrolled out of view
    this.observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          this.isPaused = !entry.isIntersecting;
          if (!this.isPaused) {
            this.lastFrameTime = performance.now();
          }
        });
      },
      { threshold: 0.1 }
    );
    this.observer.observe(this.container);
  }

  handleResize() {
    if (!this.renderer || !this.camera || !this.container) return;
    const w = this.container.clientWidth || window.innerWidth;
    const h = this.container.clientHeight || window.innerHeight;
    const isMobile = w < CONFIG.mobileBreakpoint;
    const dpr = Math.min(window.devicePixelRatio || 1, isMobile ? CONFIG.maxDprMobile : CONFIG.maxDprDesktop);

    this.renderer.setPixelRatio(dpr);
    this.renderer.setSize(w, h, false);
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
  }

  startEntranceAnimation() {
    const hasVisited = sessionStorage.getItem('electrodesk_mh_visited');
    if (hasVisited || this.isReducedMotion) {
      // Immediate layout
      return;
    }
    sessionStorage.setItem('electrodesk_mh_visited', 'true');

    // 1.6s Staggered Rise from below pool
    const startTime = performance.now();
    const duration = 1600;

    const cards = this.ring.cards;
    cards.forEach((c, idx) => {
      const delay = idx * 65;
      const initialY = -CONFIG.cardHeight;
      c.upperCard.position.y = initialY;
      c.reflMesh.position.y = -initialY;

      const animateCard = () => {
        const elapsed = performance.now() - startTime;
        if (elapsed > delay) {
          const t = Math.min(1.0, (elapsed - delay) / 800);
          // Ease out cubic
          const ease = 1 - Math.pow(1 - t, 3);
          c.upperCard.position.y = THREE.MathUtils.lerp(initialY, CONFIG.cardHeight / 2, ease);
          c.reflMesh.position.y = THREE.MathUtils.lerp(-initialY, -CONFIG.cardHeight / 2, ease);
        }
        if (performance.now() - startTime < duration) {
          requestAnimationFrame(animateCard);
        }
      };
      animateCard();
    });
  }

  handleNavigate(section) {
    if (this.isNavigating) return;
    if (section.locked) {
      const liveRegion = document.getElementById('mhAriaLive');
      if (liveRegion) liveRegion.textContent = 'This section is restricted for your user role.';
      return;
    }

    this.isNavigating = true;
    this.emit('navigate', section);

    // Zoom camera toward active card before route change
    const targetZ = this.camera.position.z - 3.2;
    const startZ = this.camera.position.z;
    const startTime = performance.now();
    const animDuration = 450;

    const navAnimation = () => {
      const elapsed = performance.now() - startTime;
      const t = Math.min(1.0, elapsed / animDuration);
      const ease = Math.pow(t, 2.5);
      this.camera.position.z = THREE.MathUtils.lerp(startZ, targetZ, ease);

      if (this.hud && this.hud.root) {
        this.hud.root.style.opacity = String(1.0 - ease);
      }

      if (t < 1.0) {
        requestAnimationFrame(navAnimation);
      } else {
        window.location.href = section.route;
      }
    };
    navAnimation();
  }

  animate() {
    if (this.isDisposed) return;
    this.rAFId = requestAnimationFrame(() => this.animate());

    if (this.isPaused) return;

    const now = performance.now();
    const dt = Math.min(0.05, (now - this.lastFrameTime) / 1000);
    this.lastFrameTime = now;
    const time = now / 1000;

    // Quality monitor
    this.monitorPerformance(dt);

    // 1. Update Input Physics
    const inputState = this.input.update(dt);

    // 2. Camera Parallax Damping
    if (!this.isReducedMotion) {
      this.mouseSmooth.x += (this.mouseTarget.x * CONFIG.parallaxMax - this.mouseSmooth.x) * CONFIG.parallaxDamping;
      this.mouseSmooth.y += (this.mouseTarget.y * CONFIG.parallaxMax - this.mouseSmooth.y) * CONFIG.parallaxDamping;
      this.camera.position.x = this.mouseSmooth.x;
      this.camera.position.y = CONFIG.cameraY + this.mouseSmooth.y * 0.4;
    }

    // 3. Update Card Ring & Retrieve Focused Card
    const ringState = this.ring.update(inputState.angle, time, this.isReducedMotion);

    // 4. Update Water Pool Ripples & Spotlight
    this.pool.update(time, inputState.velocity, ringState.focusedPosition, ringState.activeColor);

    // 5. Update HUD Projected Labels & Active Pager
    const width = this.container.clientWidth || window.innerWidth;
    const height = this.container.clientHeight || window.innerHeight;
    this.hud.updateFloatingLabels(this.ring.cards, this.camera, width, height);
    this.hud.setActiveIndex(ringState.focusedIndex);

    // 6. Render WebGL Scene
    this.renderer.render(this.scene, this.camera);
  }

  monitorPerformance(dt) {
    this.frameTimes.push(dt * 1000);
    if (this.frameTimes.length > 120) {
      this.frameTimes.shift();
      const avgMs = this.frameTimes.reduce((a, b) => a + b, 0) / this.frameTimes.length;
      if (avgMs > CONFIG.fpsDegradeThresholdMs && !this.isQualityDegraded) {
        this.isQualityDegraded = true;
        this.renderer.setPixelRatio(1.0);
        console.warn('MirrorHall: Frame budget exceeded, dynamically degraded DPR to 1.0.');
      }
    }
  }

  renderAccessibleFallback() {
    this.container.innerHTML = `
      <div class="mh-fallback-grid p-4 p-md-5">
        <div class="text-center mb-5">
          <span class="mh-hud-eyebrow">ELECTRODESK &bull; ACCESSIBLE SECTION HUB</span>
          <h1 class="mh-hud-title fs-2 mt-2">Mirror Hall</h1>
          <p class="text-muted">Select a shop department to navigate directly.</p>
        </div>
        <div class="row g-4 justify-content-center">
          ${this.sections
            .map(
              (s, i) => `
            <div class="col-12 col-sm-6 col-lg-3">
              <a href="${s.route}" class="mh-fallback-card text-decoration-none d-block p-4 rounded-4" style="border-top: 3px solid ${s.accent};">
                <div class="d-flex justify-content-between align-items-start mb-3">
                  <span class="badge" style="background: rgba(43,240,255,0.15); color: #8fe6ff;">${s.code}</span>
                  ${s.badge ? `<span class="badge bg-danger rounded-pill">${s.badge}</span>` : ''}
                </div>
                <h3 class="h5 fw-bold text-white mb-2">${s.name}</h3>
                <div class="text-info small fw-semibold mb-3">${s.metric}</div>
                <div class="d-flex align-items-center text-muted small gap-1">
                  <span>Enter department</span>
                  <i class="bi bi-chevron-right"></i>
                </div>
              </a>
            </div>
          `
            )
            .join('')}
        </div>
      </div>
    `;
  }

  dispose() {
    this.isDisposed = true;
    cancelAnimationFrame(this.rAFId);

    window.removeEventListener('resize', this._onResize);
    window.removeEventListener('mousemove', this._onPointerMove);
    document.removeEventListener('visibilitychange', this._onVisibilityChange);

    if (this.observer) this.observer.disconnect();
    if (this.input) this.input.dispose();
    if (this.hud) this.hud.dispose();
    if (this.ring) this.ring.dispose();
    if (this.pool) this.pool.dispose();

    if (this.renderer) {
      this.renderer.dispose();
      if (this.renderer.domElement && this.renderer.domElement.parentNode) {
        this.renderer.domElement.parentNode.removeChild(this.renderer.domElement);
      }
    }
  }
}
