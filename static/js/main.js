/**
 * Electrodesk - Main JS
 * Shared Indian Rupee Formatter, Dark Mode, Global Search (Ctrl+K), i18n, and UI Helpers.
 */

// Shared Currency Formatter:
// Intl.NumberFormat('en-IN', {style:'currency', currency:'INR', maximumFractionDigits:0})
const inrFormatter = new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0
});

function formatINR(amount) {
    if (amount === null || amount === undefined || isNaN(amount)) {
        return '₹0';
    }
    return inrFormatter.format(Math.round(amount));
}

// Multilingual Dictionary (EN / Telugu / Tamil / Hindi)
const i18nDictionary = {
    en: {
        overview: "Overview", dashboard: "Dashboard", inventory: "Inventory", products: "Products",
        categories: "Categories", stock: "Stock", warranty: "Warranty", barcodes: "Barcodes",
        sales: "Sales", customers: "Customers", customer_dues: "Customer Dues", quotations: "Quotations",
        new_sale: "New Sale", invoices: "Billing & Invoices", returns: "Returns & Credit",
        operations: "Operations", purchase_orders: "Suppliers & POs", repair_tickets: "Repair Tickets",
        finance: "Finance & Reports", profit_loss: "Profit & Loss", expenses: "Expenses",
        gst_summary: "GST Summary", daily_closing: "Daily Closing", reports: "Analytics Reports",
        administration: "Administration", notifications: "Alerts & Notices", audit_log: "Audit Trail",
        users: "Users & Roles", settings: "Settings"
    },
    te: {
        overview: "అవలోకనం", dashboard: "డాష్‌బోర్డ్", inventory: "స్టాక్ నిర్వహణ", products: "ఉత్పత్తులు",
        categories: "విభాగాలు", stock: "నిల్వలు", warranty: "వారంటీ", barcodes: "బార్‌కోడ్‌లు",
        sales: "అమ్మకాలు", customers: "కస్టమర్లు", customer_dues: "బాకీల వివరాలు", quotations: "కొటేషన్లు",
        new_sale: "కొత్త బిల్లు", invoices: "ఇన్‌వాయిస్‌లు", returns: "రిటర్న్స్",
        operations: "ఆపరేషన్స్", purchase_orders: "కొనుగోలు ఆర్డర్లు", repair_tickets: "రిపేర్ టికెట్లు",
        finance: "ఆర్థిక నివేదికలు", profit_loss: "లాభ నష్టాలు", expenses: "ఖర్చులు",
        gst_summary: "జీఎస్టీ సారాంశం", daily_closing: "రోజువారీ లెక్కలు", reports: "రిపోర్టులు",
        administration: "నిర్వహణ", notifications: "నోటీసులు", audit_log: "ఆడిట్ లాగ్",
        users: "యూజర్లు", settings: "సెట్టింగులు"
    },
    ta: {
        overview: "மேலோட்டம்", dashboard: "முகப்பு பலகை", inventory: "சரக்கு இருப்பு", products: "பொருட்கள்",
        categories: "வகைகள்", stock: "இருப்பு", warranty: "உத்தரவாதம்", barcodes: "பார்கோடுகள்",
        sales: "விற்பனை", customers: "வாடிக்கையாளர்கள்", customer_dues: "நிலுவைத் தொகை", quotations: "விலைப்புள்ளி",
        new_sale: "புதிய விற்பனை", invoices: "விலைப்பட்டியல்கள்", returns: "திருப்புதல்",
        operations: "செயல்பாடுகள்", purchase_orders: "கொள்முதல் ஆணைகள்", repair_tickets: "பழுதுபார்ப்பு",
        finance: "நிதி அறிக்கைகள்", profit_loss: "லாப நஷ்டம்", expenses: "செலவுகள்",
        gst_summary: "ஜிஎஸ்டி சுருக்கம்", daily_closing: "தினசரி கணக்கு", reports: "அறிக்கைகள்",
        administration: "நிர்வாகம்", notifications: "அறிவிப்புகள்", audit_log: "தணிக்கை பதிவு",
        users: "பயனர்கள்", settings: "அமைப்புகள்"
    },
    hi: {
        overview: "अवलोकन", dashboard: "डैशबोर्ड", inventory: "इन्वेंट्री स्टॉक", products: "उत्पाद सूची",
        categories: "श्रेणियां", stock: "स्टॉक स्थिति", warranty: "वारंटी ट्रैकिंग", barcodes: "बारकोड लेबल्स",
        sales: "बिक्री", customers: "ग्राहक", customer_dues: "बकाया राशि", quotations: "कोटेशन",
        new_sale: "नई बिक्री", invoices: "बिल व इनवॉइस", returns: "रिटर्न व क्रेडिट",
        operations: "ऑपरेशंस", purchase_orders: "खरीद ऑर्डर", repair_tickets: "रिपेयर टिकट",
        finance: "वित्त व रिपोर्ट", profit_loss: "लाभ-हानि", expenses: "दुकान खर्च",
        gst_summary: "जीएसटी सारांश", daily_closing: "दैनिक क्लोजिंग", reports: "एनालिटिक्स रिपोर्ट",
        administration: "प्रशासन", notifications: "अलर्ट व सूचनाएं", audit_log: "ऑडिट लॉग",
        users: "उपयोगकर्ता व रोल्स", settings: "सिस्टम सेटिंग्स"
    }
};

function setAppLanguage(lang) {
    if (!i18nDictionary[lang]) lang = 'en';
    localStorage.setItem('electrodesk-lang', lang);

    const labels = i18nDictionary[lang];
    document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.getAttribute('data-i18n');
        if (labels[key]) {
            el.textContent = labels[key];
        }
    });

    const langBadge = document.getElementById('currentLangLabel');
    if (langBadge) {
        langBadge.textContent = lang.toUpperCase();
    }
}

document.addEventListener('DOMContentLoaded', function() {
    // 1. Restore Language
    const savedLang = localStorage.getItem('electrodesk-lang') || 'en';
    setAppLanguage(savedLang);

    // 2. Dark Mode Toggle
    const themeToggleBtn = document.getElementById('darkModeToggle');
    const themeIcon = document.getElementById('themeIcon');
    const currentTheme = localStorage.getItem('electrodesk-theme') || 'light';

    document.documentElement.setAttribute('data-theme', currentTheme);
    if (themeIcon) {
        themeIcon.className = currentTheme === 'dark' ? 'bi bi-sun-fill text-warning' : 'bi bi-moon-stars-fill';
    }

    if (themeToggleBtn) {
        themeToggleBtn.addEventListener('click', function() {
            const nowTheme = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
            document.documentElement.setAttribute('data-theme', nowTheme);
            localStorage.setItem('electrodesk-theme', nowTheme);
            if (themeIcon) {
                themeIcon.className = nowTheme === 'dark' ? 'bi bi-sun-fill text-warning' : 'bi bi-moon-stars-fill';
            }
        });
    }

    // 2b. Reduce Motion & Visual Effects Toggle
    const reduceEffectsBtn = document.getElementById('reduceEffectsToggle');
    const effectsIcon = document.getElementById('effectsIcon');
    const isReducedEffects = localStorage.getItem('electrodesk-reduce-effects') === 'true';

    if (isReducedEffects) {
        document.documentElement.classList.add('reduce-effects');
        if (effectsIcon) {
            effectsIcon.className = 'bi bi-lightning-slash-fill text-warning';
        }
        if (reduceEffectsBtn) {
            reduceEffectsBtn.classList.add('active');
        }
    }

    if (reduceEffectsBtn) {
        reduceEffectsBtn.addEventListener('click', function() {
            const active = document.documentElement.classList.toggle('reduce-effects');
            localStorage.setItem('electrodesk-reduce-effects', active ? 'true' : 'false');
            if (effectsIcon) {
                effectsIcon.className = active ? 'bi bi-lightning-slash-fill text-warning' : 'bi bi-speedometer2';
            }
            if (active) {
                reduceEffectsBtn.classList.add('active');
            } else {
                reduceEffectsBtn.classList.remove('active');
            }
        });
    }

    // 3. Global Search (Ctrl + K)
    document.addEventListener('keydown', function(e) {
        if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
            e.preventDefault();
            const modalEl = document.getElementById('globalSearchModal');
            if (modalEl) {
                const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
                modal.show();
                setTimeout(() => {
                    const inp = document.getElementById('globalSearchInput');
                    if (inp) inp.focus();
                }, 300);
            }
        }
    });

    const searchInput = document.getElementById('globalSearchInput');
    const searchResults = document.getElementById('globalSearchResults');
    let searchDebounce = null;

    if (searchInput && searchResults) {
        searchInput.addEventListener('input', function() {
            clearTimeout(searchDebounce);
            const val = this.value.trim();
            if (val.length < 2) {
                searchResults.innerHTML = '<div class="text-center py-4 text-muted small"><i class="bi bi-lightning-charge text-primary fs-3 d-block mb-2"></i>Type at least 2 characters to search.</div>';
                return;
            }

            searchDebounce = setTimeout(function() {
                fetch(`/api/global-search?q=${encodeURIComponent(val)}`)
                    .then(res => res.json())
                    .then(data => {
                        if (!data.results || data.results.length === 0) {
                            searchResults.innerHTML = `<div class="text-center py-4 text-muted small"><i class="bi bi-search text-secondary fs-4 d-block mb-1"></i>No results found for "${val}".</div>`;
                            return;
                        }
                        let html = '';
                        data.results.forEach(r => {
                            html += `
                                <a href="${r.url}" class="list-group-item list-group-item-action py-2 px-3 d-flex justify-content-between align-items-center">
                                    <div>
                                        <div class="fw-semibold text-dark">${r.title}</div>
                                        <small class="text-muted">${r.subtitle}</small>
                                    </div>
                                    <span class="badge bg-light text-secondary border">${r.type}</span>
                                </a>
                            `;
                        });
                        searchResults.innerHTML = html;
                    })
                    .catch(() => {
                        searchResults.innerHTML = '<div class="text-danger small p-3 text-center">Failed to fetch search results.</div>';
                    });
            }, 250);
        });
    }

    // 4. Auto-dismiss alerts
    const alerts = document.querySelectorAll('.alert-dismissible');
    alerts.forEach(function(alert) {
        setTimeout(function() {
            try {
                const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
                if (bsAlert) bsAlert.close();
            } catch (e) {}
        }, 5000);
    });

    // 5. Chart.js Dark Glass Palette Defaults
    if (typeof Chart !== 'undefined') {
        Chart.defaults.color = 'rgba(232, 246, 255, 0.75)';
        Chart.defaults.borderColor = 'rgba(143, 230, 255, 0.12)';
    }

    // 6. Global Modal Stacking & Restock Freezing Prevention
    function moveModalsToBody() {
        document.querySelectorAll('.modal').forEach(function(m) {
            if (m.parentElement !== document.body) {
                document.body.appendChild(m);
            }
        });
    }

    moveModalsToBody();

    document.addEventListener('show.bs.modal', function(e) {
        if (e.target && e.target.parentElement !== document.body) {
            document.body.appendChild(e.target);
        }
    });

    document.addEventListener('hidden.bs.modal', function() {
        if (!document.querySelector('.modal.show')) {
            document.querySelectorAll('.modal-backdrop').forEach(function(b) {
                b.remove();
            });
            document.body.classList.remove('modal-open');
            document.body.style.removeProperty('overflow');
            document.body.style.removeProperty('padding-right');
        }
    });
});
