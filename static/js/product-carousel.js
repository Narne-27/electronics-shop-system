/**
 * Electrodesk - Apple-Store-Style Product Carousel Controller
 * Scoped, accessible, vanilla JS with smooth snapping & button state management
 */

(function () {
    'use strict';

    function initCarousels() {
        const carousels = document.querySelectorAll('.pc-carousel-section');
        carousels.forEach(carousel => {
            const track = carousel.querySelector('.pc-track');
            const prevBtn = carousel.querySelector('.pc-prev-btn');
            const nextBtn = carousel.querySelector('.pc-next-btn');

            if (!track) return;

            function getScrollStep() {
                const firstCard = track.querySelector('.pc-card');
                if (firstCard) {
                    const style = window.getComputedStyle(track);
                    const gap = parseFloat(style.gap) || 20;
                    return firstCard.offsetWidth + gap;
                }
                return track.clientWidth * 0.8;
            }

            function updateButtons() {
                if (!prevBtn || !nextBtn) return;
                const scrollLeft = Math.round(track.scrollLeft);
                const maxScroll = track.scrollWidth - track.clientWidth;

                // At or near start
                const isAtStart = scrollLeft <= 4;
                prevBtn.disabled = isAtStart;
                prevBtn.setAttribute('aria-disabled', isAtStart ? 'true' : 'false');

                // At or near end
                const isAtEnd = scrollLeft >= maxScroll - 4;
                nextBtn.disabled = isAtEnd;
                nextBtn.setAttribute('aria-disabled', isAtEnd ? 'true' : 'false');
            }

            // Click handlers
            if (prevBtn) {
                prevBtn.addEventListener('click', () => {
                    const step = getScrollStep();
                    track.scrollBy({ left: -step, behavior: 'smooth' });
                });
            }

            if (nextBtn) {
                nextBtn.addEventListener('click', () => {
                    const step = getScrollStep();
                    track.scrollBy({ left: step, behavior: 'smooth' });
                });
            }

            // Keyboard navigation when track has focus
            track.addEventListener('keydown', (e) => {
                if (e.key === 'ArrowLeft') {
                    e.preventDefault();
                    track.scrollBy({ left: -getScrollStep(), behavior: 'smooth' });
                } else if (e.key === 'ArrowRight') {
                    e.preventDefault();
                    track.scrollBy({ left: getScrollStep(), behavior: 'smooth' });
                }
            });

            // Scroll listener with throttle
            let ticking = false;
            track.addEventListener('scroll', () => {
                if (!ticking) {
                    window.requestAnimationFrame(() => {
                        updateButtons();
                        ticking = false;
                    });
                    ticking = true;
                }
            }, { passive: true });

            // Window resize updates
            window.addEventListener('resize', updateButtons, { passive: true });

            // Initial check
            updateButtons();
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initCarousels);
    } else {
        initCarousels();
    }
})();
