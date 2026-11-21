/* ========================================================
   Electrodesk - Curved 3D product carousel
   Vanilla JS, wrapped in an IIFE so nothing leaks to the page.
   Replaces the old flat scroll-snap carousel script.
   ======================================================== */
(function () {
    'use strict';

    var root = document.querySelector('.curve-carousel');
    if (!root) return;

    var viewport = root.querySelector('.cc-viewport');
    var rail = root.querySelector('.cc-rail');
    var cards = Array.prototype.slice.call(rail.querySelectorAll('.cc-card'));
    var n = cards.length;
    if (!n) return;

    var prevBtn = root.querySelector('.cc-prev');
    var nextBtn = root.querySelector('.cc-next');
    var toggleBtn = root.querySelector('.cc-toggle');
    var live = root.querySelector('.cc-live');

    var AUTOPLAY_MS = 4000;
    var SWIPE_PX = 40;
    var reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)');

    var active = 0;
    var cfg = null;
    var lastWidth = 0;

    /* ---------- Layout presets (index = distance from the centre card) ----------
       tx is a multiple of the card width, so presets follow the CSS card size. */
    var PRESETS = {
        desktop: { range: 3, tx: [0, 0.72, 1.14, 1.50], rot: [0, 35, 45, 55], scale: [1, 0.88, 0.77, 0.68], tz: [0, -60, -130, -210], op: [1, 0.85, 0.60, 0.35] },
        tablet:  { range: 2, tx: [0, 0.72, 1.12],       rot: [0, 32, 42],     scale: [1, 0.88, 0.77],       tz: [0, -60, -130],       op: [1, 0.80, 0.50] },
        mobile:  { range: 1, tx: [0, 0.62],             rot: [0, 25],         scale: [1, 0.86],             tz: [0, -50],             op: [1, 0.70] }
    };

    function getConfig() {
        var w = viewport.clientWidth;
        var preset = w >= 1000 ? PRESETS.desktop : (w >= 640 ? PRESETS.tablet : PRESETS.mobile);
        return { p: preset, cardW: cards[0].offsetWidth || 300 };
    }

    /* Signed distance from the active card, wrapped so the carousel loops. */
    function offsetOf(i) {
        var d = i - active;
        if (n > 1) {
            var half = n / 2;
            if (d > half) d -= n;
            else if (d < -half) d += n;
        }
        return d;
    }

    /* Position every card. `step` = how far the active index just moved (for wrap detection). */
    function render(step) {
        var p = cfg.p;
        cards.forEach(function (el, i) {
            var d = offsetOf(i);
            var a = Math.abs(d);
            var sign = d < 0 ? -1 : 1;
            var visible = a <= p.range;
            var k = Math.min(a, p.range);

            // A card that wraps from one end to the other would sweep across the centre; teleport it instead.
            var jump = false;
            if (typeof step === 'number' && typeof el._d === 'number' && d !== el._d - step) jump = true;
            if (jump) el.style.transition = 'none';

            el.style.transform =
                'translate3d(' + (sign * p.tx[k] * cfg.cardW) + 'px, 0, ' + p.tz[k] + 'px) ' +
                'rotateY(' + (-sign * p.rot[k]) + 'deg) ' +
                'scale(' + p.scale[k] + ')';
            el.style.opacity = visible ? p.op[k] : 0;

            if (jump) {
                void el.offsetWidth; // flush so the "none" transition applies to this change only
                el.style.transition = '';
            }

            el._d = d;
            el.classList.toggle('is-active', d === 0);
            el.classList.toggle('is-hidden', !visible);
            el.setAttribute('aria-hidden', visible ? 'false' : 'true');
            el.tabIndex = visible ? 0 : -1;
            if (d === 0) el.setAttribute('aria-current', 'true');
            else el.removeAttribute('aria-current');
        });
    }

    function goTo(index) {
        index = ((index % n) + n) % n;
        if (index === active) return;
        var step = index - active;
        if (step > n / 2) step -= n;
        else if (step < -n / 2) step += n;
        active = index;
        render(step);
    }

    /* A move made by the person: also restarts the autoplay clock and announces the card. */
    function userGo(index) {
        goTo(index);
        schedule();
        if (live) {
            var name = cards[active].querySelector('.cc-name');
            live.textContent = (name ? name.textContent : 'Product') + ', ' + (active + 1) + ' of ' + n;
        }
    }

    /* ---------- Autoplay ---------- */
    var timer = null;
    var userPaused = false;
    var hovering = false;
    var touching = false;
    var focusInside = false;
    var offscreen = false;

    function shouldPlay() {
        return n > 1 && !userPaused && !hovering && !touching && !focusInside &&
            !offscreen && !document.hidden && !reduceMotion.matches;
    }

    function stop() {
        if (timer) { clearInterval(timer); timer = null; }
    }

    function schedule() {
        stop();
        if (shouldPlay()) timer = setInterval(function () { goTo(active + 1); }, AUTOPLAY_MS);
    }

    function syncToggle() {
        if (!toggleBtn) return;
        var icon = toggleBtn.querySelector('i');
        toggleBtn.setAttribute('aria-pressed', userPaused ? 'true' : 'false');
        toggleBtn.setAttribute('aria-label', userPaused ? 'Resume automatic rotation' : 'Pause automatic rotation');
        toggleBtn.title = userPaused ? 'Play' : 'Pause';
        if (icon) icon.className = 'bi ' + (userPaused ? 'bi-play-fill' : 'bi-pause-fill');
        toggleBtn.hidden = reduceMotion.matches; // nothing to pause when motion is reduced
    }

    /* ---------- Events ---------- */
    if (prevBtn) prevBtn.addEventListener('click', function () { userGo(active - 1); });
    if (nextBtn) nextBtn.addEventListener('click', function () { userGo(active + 1); });
    if (toggleBtn) toggleBtn.addEventListener('click', function () {
        userPaused = !userPaused;
        syncToggle();
        schedule();
    });

    // Click: side card -> move to centre; centre card -> follow its link.
    rail.addEventListener('click', function (e) {
        var card = e.target.closest ? e.target.closest('.cc-card') : null;
        if (!card || card.classList.contains('is-active')) return;
        e.preventDefault();
        userGo(cards.indexOf(card));
    });

    // Keyboard: left / right arrows while focus is anywhere inside the carousel.
    root.addEventListener('keydown', function (e) {
        if (e.key === 'ArrowLeft') { e.preventDefault(); userGo(active - 1); }
        else if (e.key === 'ArrowRight') { e.preventDefault(); userGo(active + 1); }
    });

    // Pause on hover / touch / keyboard focus.
    root.addEventListener('mouseenter', function () { hovering = true; schedule(); });
    root.addEventListener('mouseleave', function () { hovering = false; schedule(); });
    root.addEventListener('focusin', function (e) {
        var kb = true;
        try { kb = e.target.matches(':focus-visible'); } catch (err) { /* old browsers: assume keyboard */ }
        focusInside = kb;
        schedule();
    });
    root.addEventListener('focusout', function () { focusInside = false; schedule(); });

    // Swipe / drag (pointer events cover mouse, touch and pen).
    var downX = 0, downY = 0, pressing = false, dragging = false, suppressClick = false;

    viewport.addEventListener('pointerdown', function (e) {
        if (e.pointerType === 'mouse' && e.button !== 0) return;
        pressing = true;
        dragging = false;
        suppressClick = false;
        downX = e.clientX;
        downY = e.clientY;
        if (e.pointerType !== 'mouse') { touching = true; schedule(); }
    });

    viewport.addEventListener('pointermove', function (e) {
        if (!pressing || dragging) return;
        var dx = e.clientX - downX, dy = e.clientY - downY;
        if (Math.abs(dx) > 8 && Math.abs(dx) > Math.abs(dy)) {
            dragging = true;
            viewport.classList.add('is-dragging');
            // Capture only once a drag is certain, so plain clicks still reach the cards.
            try { viewport.setPointerCapture(e.pointerId); } catch (err) { /* ignore */ }
        }
    });

    function endPress(e, cancelled) {
        if (!pressing) return;
        pressing = false;
        touching = false;
        viewport.classList.remove('is-dragging');
        if (dragging && !cancelled) {
            var dx = e.clientX - downX;
            if (Math.abs(dx) >= SWIPE_PX) userGo(dx < 0 ? active + 1 : active - 1);
            suppressClick = true; // swallow the click that follows a drag
        }
        dragging = false;
        schedule();
    }

    viewport.addEventListener('pointerup', function (e) { endPress(e, false); });
    viewport.addEventListener('pointercancel', function (e) { endPress(e, true); });

    viewport.addEventListener('click', function (e) {
        if (suppressClick) {
            suppressClick = false;
            e.preventDefault();
            e.stopPropagation();
        }
    }, true);

    // Stop spinning when the tab is hidden or the carousel is scrolled out of view.
    document.addEventListener('visibilitychange', schedule);
    if ('IntersectionObserver' in window) {
        new IntersectionObserver(function (entries) {
            offscreen = !entries[0].isIntersecting;
            schedule();
        }, { threshold: 0.2 }).observe(root);
    }

    if (reduceMotion.addEventListener) reduceMotion.addEventListener('change', function () { syncToggle(); schedule(); });

    /* ---------- Resize: recompute the preset and reposition without animating ---------- */
    function onResize() {
        var w = viewport.clientWidth;
        if (w === lastWidth) return;
        lastWidth = w;
        cfg = getConfig();
        root.classList.add('is-resizing');
        render();
        requestAnimationFrame(function () {
            requestAnimationFrame(function () { root.classList.remove('is-resizing'); });
        });
    }

    if ('ResizeObserver' in window) new ResizeObserver(onResize).observe(viewport);
    else window.addEventListener('resize', onResize);

    /* ---------- Init ---------- */
    cfg = getConfig();
    lastWidth = viewport.clientWidth;
    render();
    root.classList.add('is-ready');
    syncToggle();
    schedule();
})();
