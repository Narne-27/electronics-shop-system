/**
 * Electrodesk - Mirror Hall 3D Section Carousel
 * HUD Controller: Projected 3D Floating Labels, Dot Pager, Active Name Cross-Fade & Accessible Counter
 */

export const createHudController = (container, sections, options = {}) => {
  const { onSelectIndex, onNavigate } = options;

  let activeIndex = -1;
  const N = sections.length;

  // 1. Root HUD Container
  const hudRoot = document.createElement('div');
  hudRoot.className = 'mh-hud-root';
  hudRoot.innerHTML = `
    <!-- Top Header: Eyebrow + Large Elegant Title + Subtitle -->
    <header class="mh-hud-header" aria-label="Mirror Hall Section Hub">
      <div class="mh-hud-eyebrow">ELECTRODESK &bull; 3D SECTION HUB</div>
      <h1 class="mh-hud-title">Mirror Hall</h1>
      <p class="mh-hud-subtitle">Every department of your shop, suspended over still water.</p>
    </header>

    <!-- Floating 3D Projected Labels Overlay Container -->
    <div class="mh-floating-labels-layer" aria-hidden="true" id="mhFloatingLabelsLayer"></div>

    <!-- Bottom Controls & Pager -->
    <footer class="mh-hud-footer" aria-label="Section Carousel Controls">
      <!-- Active Section Title (Cross-fading) -->
      <div class="mh-active-name-wrap">
        <div class="mh-active-name" id="mhActiveName">DASHBOARD</div>
        <div class="mh-active-subtitle" id="mhActiveMetric">ACTIVE REALTIME</div>
      </div>

      <!-- Center: Dot Pager + Tabular Counter -->
      <div class="mh-pager-bar">
        <div class="mh-counter" id="mhCounter" aria-hidden="true">01 / 0${N}</div>
        <div class="mh-dots-track" role="tablist" aria-label="Section selector">
          ${sections
            .map(
              (s, i) => `
            <button class="mh-dot ${i === 0 ? 'mh-dot--active' : ''}" 
                    role="tab" 
                    aria-selected="${i === 0 ? 'true' : 'false'}" 
                    aria-label="Go to ${s.name} (${i + 1} of ${N})" 
                    data-index="${i}" 
                    tabindex="0">
            </button>
          `
            )
            .join('')}
        </div>
        <div class="mh-nav-hint d-none d-md-flex align-items-center gap-2">
          <kbd class="mh-kbd">&larr;</kbd>
          <kbd class="mh-kbd">&rarr;</kbd>
          <span>to rotate</span>
          <kbd class="mh-kbd">↵ Enter</kbd>
          <span>to open</span>
        </div>
      </div>

      <!-- Action Button for Focused Section -->
      <div class="mh-action-container">
        <button class="mh-action-btn" id="mhActionBtn" aria-label="Enter selected department">
          <span id="mhActionBtnLabel">Enter Section</span>
          <i class="bi bi-arrow-right"></i>
        </button>
      </div>
    </footer>

    <!-- Screen Reader Live Region -->
    <div class="visually-hidden" aria-live="polite" aria-atomic="true" id="mhAriaLive"></div>
  `;

  container.appendChild(hudRoot);

  const labelsLayer = hudRoot.querySelector('#mhFloatingLabelsLayer');
  const activeNameEl = hudRoot.querySelector('#mhActiveName');
  const activeMetricEl = hudRoot.querySelector('#mhActiveMetric');
  const counterEl = hudRoot.querySelector('#mhCounter');
  const dotElements = hudRoot.querySelectorAll('.mh-dot');
  const ariaLiveEl = hudRoot.querySelector('#mhAriaLive');
  const actionBtn = hudRoot.querySelector('#mhActionBtn');
  const actionBtnLabel = hudRoot.querySelector('#mhActionBtnLabel');

  // Create floating label tags for each card
  const floatingTags = sections.map((s, i) => {
    const el = document.createElement('div');
    el.className = 'mh-floating-tag';
    el.textContent = s.code || s.name.toUpperCase();
    el.dataset.index = String(i);
    labelsLayer.appendChild(el);
    return el;
  });

  // Dot Click Handlers
  dotElements.forEach((dot) => {
    dot.addEventListener('click', (e) => {
      e.stopPropagation();
      const idx = parseInt(dot.dataset.index, 10);
      if (onSelectIndex) onSelectIndex(idx);
    });
  });

  // Action Button Click
  if (actionBtn) {
    actionBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      if (activeIndex >= 0 && activeIndex < N && onNavigate) {
        onNavigate(sections[activeIndex]);
      }
    });
  }

  // Vector for 3D NDC projection
  const _projVec = new THREE.Vector3();

  return {
    root: hudRoot,

    /**
     * Updates projected 3D floating labels in screen coordinates
     */
    updateFloatingLabels(cards, camera, containerWidth, containerHeight) {
      const halfW = containerWidth / 2;
      const halfH = containerHeight / 2;

      for (let i = 0; i < cards.length; i++) {
        const item = cards[i];
        const tag = floatingTags[i];

        _projVec.copy(item.anchorWorldPos);
        _projVec.project(camera);

        // Discard points behind camera lens
        if (_projVec.z > 1.0) {
          tag.style.opacity = '0';
          tag.style.transform = 'translate(-9999px, -9999px)';
          continue;
        }

        const screenX = _projVec.x * halfW + halfW;
        const screenY = -_projVec.y * halfH + halfH;

        // Opacity falls off for back-facing cards (where z < 0 in world space)
        const isFacingFront = item.container.position.z > -1.5;
        const isFocused = i === activeIndex;

        tag.style.transform = `translate(${screenX}px, ${screenY}px) translate(-50%, -100%)`;
        tag.style.opacity = isFacingFront ? (isFocused ? '1' : '0.45') : '0';
        tag.classList.toggle('mh-floating-tag--focused', isFocused);
      }
    },

    /**
     * Updates active section data, counter, dots, and screen reader announcements
     */
    setActiveIndex(index) {
      if (index === activeIndex || index < 0 || index >= N) return;
      activeIndex = index;
      const sec = sections[index];

      // 1. Active Name Cross-fade
      activeNameEl.style.opacity = '0';
      activeMetricEl.style.opacity = '0';

      setTimeout(() => {
        activeNameEl.textContent = sec.name.toUpperCase();
        activeMetricEl.textContent = sec.metric || sec.eyebrow || 'READY';
        activeNameEl.style.opacity = '1';
        activeMetricEl.style.opacity = '1';
      }, 120);

      // 2. Tabular Counter (e.g. "04 / 08")
      const currPad = String(index + 1).padStart(2, '0');
      const totPad = String(N).padStart(2, '0');
      counterEl.textContent = `${currPad} / ${totPad}`;

      // 3. Dot Pager Active State
      dotElements.forEach((d, i) => {
        const isActive = i === index;
        d.classList.toggle('mh-dot--active', isActive);
        d.setAttribute('aria-selected', isActive ? 'true' : 'false');
      });

      // 4. Action Button Label
      if (actionBtnLabel) {
        actionBtnLabel.textContent = sec.locked ? 'Locked (Restricted)' : `Open ${sec.name}`;
      }

      // 5. Screen reader live announcement
      if (ariaLiveEl) {
        ariaLiveEl.textContent = `${sec.name}, section ${index + 1} of ${N}. ${sec.metric || ''}`;
      }
    },

    dispose() {
      if (hudRoot && hudRoot.parentNode) {
        hudRoot.parentNode.removeChild(hudRoot);
      }
    }
  };
};
