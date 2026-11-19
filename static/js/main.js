/**
 * Electrodesk - Main JS
 * Shared Indian Rupee Formatter, UI handlers, auto-dismiss alerts, tooltips.
 */

// Shared Currency Formatter as required:
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

document.addEventListener('DOMContentLoaded', function() {
    // Auto-dismiss alerts after 5 seconds
    const alerts = document.querySelectorAll('.alert-dismissible');
    alerts.forEach(function(alert) {
        setTimeout(function() {
            try {
                const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
                if (bsAlert) bsAlert.close();
            } catch (e) {
                // Ignore if already closed
            }
        }, 5000);
    });

    // Initialize tooltips if any
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
});
