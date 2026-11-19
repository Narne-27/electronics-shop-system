/**
 * Electrodesk - Point of Sale (POS) Advanced Engine
 * Fast search, reactive cart, coupon codes, Owner approval (>10%), EMI plans,
 * old-device trade-in exchange, serial number validation, and atomic checkout.
 */

let cart = [];
let appliedCoupon = null;
let ownerApproved = false;
let ownerApprovalPin = '';


document.addEventListener('DOMContentLoaded', function() {
    initFilters();
    initPOSControls();
});

function initFilters() {
    const searchInput = document.getElementById('posSearchInput');
    const clearBtn = document.getElementById('clearSearchBtn');
    const catSelect = document.getElementById('posCategoryFilter');
    const catPills = document.querySelectorAll('.cat-pill');

    if (searchInput) searchInput.addEventListener('input', applyFilters);

    if (clearBtn) {
        clearBtn.addEventListener('click', function() {
            searchInput.value = '';
            applyFilters();
            searchInput.focus();
        });
    }

    if (catSelect) {
        catSelect.addEventListener('change', function() {
            syncCategoryPill(this.value);
            applyFilters();
        });
    }

    catPills.forEach(pill => {
        pill.addEventListener('click', function() {
            const cat = this.getAttribute('data-cat');
            if (catSelect) catSelect.value = cat;
            syncCategoryPill(cat);
            applyFilters();
        });
    });
}

function syncCategoryPill(catValue) {
    document.querySelectorAll('.cat-pill').forEach(p => {
        if (p.getAttribute('data-cat') === catValue) {
            p.classList.remove('btn-outline-secondary');
            p.classList.add('btn-navy', 'active');
        } else {
            p.classList.remove('btn-navy', 'active');
            p.classList.add('btn-outline-secondary');
        }
    });
}

function applyFilters() {
    const query = (document.getElementById('posSearchInput')?.value || '').toLowerCase().trim();
    const cat = document.getElementById('posCategoryFilter')?.value || 'all';
    const items = document.querySelectorAll('.product-pos-item');
    let visibleCount = 0;

    items.forEach(item => {
        const name = item.getAttribute('data-name') || '';
        const code = item.getAttribute('data-code') || '';
        const brand = item.getAttribute('data-brand') || '';
        const itemCat = item.getAttribute('data-category') || '';

        const matchesQuery = !query || name.includes(query) || code.includes(query) || brand.includes(query);
        const matchesCat = (cat === 'all') || (itemCat === cat);

        if (matchesQuery && matchesCat) {
            item.classList.remove('d-none');
            visibleCount++;
        } else {
            item.classList.add('d-none');
        }
    });

    const noMatch = document.getElementById('noMatchMessage');
    if (noMatch) {
        if (visibleCount === 0) noMatch.classList.remove('d-none');
        else noMatch.classList.add('d-none');
    }
}

function initPOSControls() {
    const couponBtn = document.getElementById('applyCouponBtn');
    if (couponBtn) {
        couponBtn.addEventListener('click', applyCouponCode);
    }

    const exchangeInput = document.getElementById('exchangeValue');
    if (exchangeInput) {
        exchangeInput.addEventListener('input', recalculateCart);
    }

    const emiSelect = document.getElementById('emiPlanSelect');
    if (emiSelect) {
        emiSelect.addEventListener('change', recalculateCart);
    }

    const discountInput = document.getElementById('cartDiscount');
    if (discountInput) {
        discountInput.addEventListener('input', function() {
            appliedCoupon = null;
            recalculateCart();
        });
    }

    // Barcode scanner simulator (Enter key in search)
    const searchInput = document.getElementById('posSearchInput');
    if (searchInput) {
        searchInput.addEventListener('keydown', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                const code = this.value.trim().toUpperCase();
                const matchedEl = document.querySelector(`.product-pos-item[data-code="${code}"]`);
                if (matchedEl) {
                    const pid = matchedEl.getAttribute('data-id');
                    addToCart(parseInt(pid));
                    this.value = '';
                    applyFilters();
                }
            }
        });
    }
}

function addToCart(productId) {
    const product = (typeof PRODUCTS_MAP !== 'undefined') ? (PRODUCTS_MAP[productId] || PRODUCTS_MAP[parseInt(productId)] || PRODUCTS_MAP[String(productId)]) : null;
    if (!product) {
        console.error('Product not found in PRODUCTS_MAP for ID:', productId);
        return;
    }

    if (product.stock_quantity <= 0) {
        alert(`Sorry, "${product.product_name}" is currently out of stock.`);
        return;
    }

    const existingIndex = cart.findIndex(item => item.product_id == product.product_id);

    if (existingIndex > -1) {
        if (cart[existingIndex].quantity + 1 > product.stock_quantity) {
            alert(`Stock limit reached! Only ${product.stock_quantity} units available.`);
            return;
        }
        cart[existingIndex].quantity += 1;
    } else {
        const randomHex = Math.floor(1000 + Math.random() * 9000);
        const defaultSerial = `SN-${product.product_code}-${randomHex}`;

        cart.push({
            product_id: product.product_id,
            name: product.product_name,
            code: product.product_code,
            brand: product.brand,
            category: product.category_name,
            price: parseFloat(product.selling_price),
            quantity: 1,
            stock: product.stock_quantity,
            warranty_months: product.warranty_months,
            serial_number: defaultSerial
        });
    }

    renderCart();
}

function updateQuantity(productId, delta) {
    const index = cart.findIndex(item => item.product_id == productId);
    if (index === -1) return;

    const newQty = cart[index].quantity + delta;
    if (newQty <= 0) {
        removeFromCart(productId);
        return;
    }

    if (newQty > cart[index].stock) {
        alert(`Cannot exceed available stock (${cart[index].stock} units).`);
        return;
    }

    cart[index].quantity = newQty;
    renderCart();
}

function updateItemSerial(productId, serialVal) {
    const index = cart.findIndex(item => item.product_id == productId);
    if (index > -1) {
        cart[index].serial_number = serialVal.trim().toUpperCase();
    }
}

function removeFromCart(productId) {
    cart = cart.filter(item => item.product_id != productId);
    renderCart();
}

function clearCart() {
    if (cart.length === 0) return;
    if (confirm('Clear all items from the cart?')) {
        cart = [];
        appliedCoupon = null;
        ownerApproved = false;
        renderCart();
    }
}

function renderCart() {
    const container = document.getElementById('cartItemList');
    const checkoutBtn = document.getElementById('checkoutBtn');

    if (!container) return;

    if (cart.length === 0) {
        container.innerHTML = `
            <div class="text-center py-5 text-muted" id="emptyCartMessage">
                <i class="bi bi-basket3 fs-1 text-secondary opacity-50 d-block mb-2"></i>
                <p class="mb-0 fw-semibold">Cart is currently empty</p>
                <small>Click on any product on the left or scan a barcode</small>
            </div>
        `;
        if (checkoutBtn) checkoutBtn.disabled = true;
        recalculateCart();
        return;
    }

    let html = '';
    cart.forEach(item => {
        const itemTotal = item.price * item.quantity;
        const catLower = (item.category || '').toLowerCase();
        const serialRequired = catLower.includes('phone') || catLower.includes('laptop') || catLower.includes('tv') || catLower.includes('tablet');

        html += `
            <div class="card p-2 mb-2 border rounded-3 bg-light bg-opacity-50">
                <div class="d-flex justify-content-between align-items-start mb-1">
                    <div class="text-truncate me-2" style="max-width: 190px;">
                        <span class="fw-bold small text-dark d-block text-truncate" title="${item.name}">${item.name}</span>
                        <small class="text-muted font-monospace">${item.code} &bull; ${item.warranty_months}M Wty</small>
                    </div>
                    <button type="button" class="btn btn-sm btn-link text-danger p-0" onclick="removeFromCart(${item.product_id})" title="Remove">
                        <i class="bi bi-x-circle-fill"></i>
                    </button>
                </div>
                
                <div class="mb-2">
                    <div class="input-group input-group-sm">
                        <span class="input-group-text py-0 bg-white" style="font-size: 0.7rem;"><i class="bi bi-upc-scan text-muted"></i></span>
                        <input type="text" class="form-control form-control-sm font-monospace py-0 ${serialRequired && !item.serial_number ? 'border-danger' : ''}" 
                               placeholder="${serialRequired ? 'Serial / IMEI * (Required)' : 'Serial Number (Optional)'}" 
                               value="${item.serial_number}" 
                               onchange="updateItemSerial(${item.product_id}, this.value)"
                               style="font-size: 0.75rem;">
                    </div>
                    ${serialRequired ? '<small class="text-muted" style="font-size: 0.68rem;"><i class="bi bi-shield-check text-primary me-1"></i>Mandatory for warranty tracking</small>' : ''}
                </div>

                <div class="d-flex justify-content-between align-items-center">
                    <div class="input-group input-group-sm" style="width: 100px;">
                        <button class="btn btn-outline-secondary py-0 px-2" type="button" onclick="updateQuantity(${item.product_id}, -1)">-</button>
                        <input type="text" class="form-control text-center py-0 px-1 bg-white" value="${item.quantity}" readonly>
                        <button class="btn btn-outline-secondary py-0 px-2" type="button" onclick="updateQuantity(${item.product_id}, 1)">+</button>
                    </div>
                    <div class="text-end">
                        <small class="text-muted d-block" style="font-size: 0.75rem;">${formatINR(item.price)} each</small>
                        <span class="fw-bold text-dark">${formatINR(itemTotal)}</span>
                    </div>
                </div>
            </div>
        `;
    });

    container.innerHTML = html;
    if (checkoutBtn) checkoutBtn.disabled = false;
    recalculateCart();
}

function recalculateCart() {
    let subtotal = 0;
    cart.forEach(item => {
        subtotal += item.price * item.quantity;
    });

    let discount = 0;
    const discountInput = document.getElementById('cartDiscount');

    if (appliedCoupon) {
        discount = appliedCoupon.discount;
        if (discountInput) discountInput.value = discount;
    } else if (discountInput) {
        discount = parseFloat(discountInput.value) || 0;
    }

    // Exchange Trade-In Value Deduction
    const exchangeVal = parseFloat(document.getElementById('exchangeValue')?.value || 0) || 0;

    // Check discount percentage (exceeding 10% requires Owner Approval)
    const discountPct = subtotal > 0 ? (discount / subtotal * 100) : 0;
    const ownerApprovalBadge = document.getElementById('ownerApprovalBadge');

    if (discountPct > 10.0) {
        if (ownerApprovalBadge) {
            ownerApprovalBadge.classList.remove('d-none');
            if (ownerApproved) {
                ownerApprovalBadge.className = 'badge bg-success-subtle text-success border border-success-subtle d-block mb-2';
                ownerApprovalBadge.innerHTML = `<i class="bi bi-check-circle-fill me-1"></i>Owner Approved (${discountPct.toFixed(1)}% Off)`;
            } else {
                ownerApprovalBadge.className = 'badge bg-warning-subtle text-warning-emphasis border border-warning-subtle d-block mb-2';
                ownerApprovalBadge.innerHTML = `<i class="bi bi-shield-lock-fill me-1"></i>Discount ${discountPct.toFixed(1)}% > 10% requires Owner PIN`;
            }
        }
    } else {
        if (ownerApprovalBadge) ownerApprovalBadge.classList.add('d-none');
    }

    const taxSelect = document.getElementById('cartTaxRate');
    const taxRate = taxSelect ? parseFloat(taxSelect.value || 0) : 18;

    const taxableBase = Math.max(0, subtotal - discount - exchangeVal);
    const cgstAmount = Math.round(taxableBase * ((taxRate / 2) / 100));
    const sgstAmount = Math.round(taxableBase * ((taxRate / 2) / 100));
    const totalGst = cgstAmount + sgstAmount;
    const grandTotal = Math.max(0, Math.round(taxableBase + totalGst));

    // Update Summary UI
    if (document.getElementById('summarySubtotal')) document.getElementById('summarySubtotal').innerText = formatINR(subtotal);
    if (document.getElementById('summaryExchange')) document.getElementById('summaryExchange').innerText = `- ${formatINR(exchangeVal)}`;
    if (document.getElementById('summaryCGST')) document.getElementById('summaryCGST').innerText = formatINR(cgstAmount);
    if (document.getElementById('summarySGST')) document.getElementById('summarySGST').innerText = formatINR(sgstAmount);
    if (document.getElementById('summaryTax')) document.getElementById('summaryTax').innerText = formatINR(totalGst);
    if (document.getElementById('summaryGrandTotal')) document.getElementById('summaryGrandTotal').innerText = formatINR(grandTotal);

    // Live EMI Calculation
    const emiSelect = document.getElementById('emiPlanSelect');
    const emiMonths = emiSelect ? parseInt(emiSelect.value || 0) : 0;
    const emiSummary = document.getElementById('emiBreakdown');

    if (emiMonths > 0 && emiSummary) {
        const rates = {3: 0.0, 6: 12.0, 9: 14.0, 12: 15.0};
        const rate = rates[emiMonths] || 12.0;
        const interest = grandTotal * (rate / 100.0) * (emiMonths / 12.0);
        const totalWithInterest = grandTotal + interest;
        const monthly = Math.round(totalWithInterest / emiMonths);

        emiSummary.classList.remove('d-none');
        emiSummary.innerHTML = `<strong>${emiMonths} Months EMI:</strong> ${formatINR(monthly)} / month (${rate}% p.a.)`;
    } else if (emiSummary) {
        emiSummary.classList.add('d-none');
    }
}

async function applyCouponCode() {
    const input = document.getElementById('couponCodeInput');
    const code = (input ? input.value : '').trim().toUpperCase();
    if (!code) return;

    let subtotal = 0;
    cart.forEach(item => subtotal += item.price * item.quantity);

    if (subtotal === 0) {
        alert('Please add items to cart before applying coupon.');
        return;
    }

    try {
        const res = await fetch('/api/pos/validate-coupon', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({coupon_code: code, subtotal: subtotal})
        });
        const data = await res.json();
        if (data.valid) {
            appliedCoupon = data;
            if (data.requires_owner_approval && !ownerApproved) {
                promptOwnerApproval();
            }
            recalculateCart();
            alert(`Coupon "${code}" applied: ${data.description}`);
        } else {
            alert(data.message || 'Invalid coupon.');
        }
    } catch (e) {
        alert('Failed to validate coupon: ' + e.message);
    }
}

function promptOwnerApproval() {
    const modalEl = document.getElementById('ownerApprovalModal');
    if (modalEl) {
        const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
        modal.show();
    }
}

function verifyOwnerPin() {
    const pin = (document.getElementById('ownerPinInput')?.value || '').trim();
    if (pin === '9999') {
        ownerApproved = true;
        ownerApprovalPin = pin;
        const modalEl = document.getElementById('ownerApprovalModal');
        if (modalEl) {
            const modal = bootstrap.Modal.getInstance(modalEl);
            if (modal) modal.hide();
        }
        recalculateCart();
        alert('Owner authorization granted for special discount.');
    } else {
        alert('Incorrect Owner PIN. Authorization rejected.');
    }
}

async function processCheckout() {
    if (cart.length === 0) {
        alert('Cart is empty.');
        return;
    }

    // Verify mandatory serial numbers
    for (let item of cart) {
        const catLower = (item.category || '').toLowerCase();
        const serialRequired = catLower.includes('phone') || catLower.includes('laptop') || catLower.includes('tv') || catLower.includes('tablet');
        if (serialRequired && !item.serial_number) {
            alert(`Serial number / IMEI is mandatory for ${item.name}. Please enter it in the cart.`);
            return;
        }
    }

    let subtotal = 0;
    cart.forEach(item => subtotal += item.price * item.quantity);
    const discount = parseFloat(document.getElementById('cartDiscount')?.value || 0) || 0;
    const discountPct = subtotal > 0 ? (discount / subtotal * 100) : 0;

    if (discountPct > 10.0 && !ownerApproved) {
        promptOwnerApproval();
        return;
    }

    const checkoutBtn = document.getElementById('checkoutBtn');
    checkoutBtn.disabled = true;
    checkoutBtn.innerHTML = `<span class="spinner-border spinner-border-sm me-2"></span>Processing & Billing...`;

    const customerId = document.getElementById('cartCustomerSelect')?.value || null;
    const taxRate = parseFloat(document.getElementById('cartTaxRate')?.value || 18);
    const notes = document.getElementById('cartNotes')?.value || '';
    const exchangeDevice = document.getElementById('exchangeDeviceName')?.value || '';
    const exchangeValue = parseFloat(document.getElementById('exchangeValue')?.value || 0) || 0;
    const emiMonths = parseInt(document.getElementById('emiPlanSelect')?.value || 0) || 0;

    let paymentMethod = 'Cash';
    const payRadio = document.querySelector('input[name="paymentMethod"]:checked');
    if (payRadio) paymentMethod = payRadio.value;

    const payload = {
        items: cart.map(item => ({
            product_id: item.product_id,
            quantity: item.quantity,
            serial_number: item.serial_number
        })),
        customer_id: customerId,
        payment_method: paymentMethod,
        payment_status: (paymentMethod === 'Pay Later' || paymentMethod === 'Credit') ? 'Pending' : 'Paid',
        tax_rate: taxRate,
        discount_amount: discount,
        discount_type: appliedCoupon ? appliedCoupon.code : 'manual',
        exchange_device: exchangeDevice,
        exchange_value: exchangeValue,
        emi_months: emiMonths,
        owner_pin: ownerApprovalPin,
        notes: notes
    };

    try {
        const response = await fetch('/api/pos/checkout', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });

        const data = await response.json();
        if (data.success) {
            window.location.href = `/invoice/${data.sale_id}`;
        } else {
            alert('Checkout failed: ' + data.message);
            checkoutBtn.disabled = false;
            checkoutBtn.innerHTML = `<i class="bi bi-check-circle-fill fs-5"></i> <span>Generate Bill & Invoice</span>`;
        }
    } catch (err) {
        alert('Error processing checkout: ' + err.message);
        checkoutBtn.disabled = false;
        checkoutBtn.innerHTML = `<i class="bi bi-check-circle-fill fs-5"></i> <span>Generate Bill & Invoice</span>`;
    }
}

// Explicit window bindings for inline HTML event handlers
window.addToCart = addToCart;
window.updateQuantity = updateQuantity;
window.updateItemSerial = updateItemSerial;
window.removeFromCart = removeFromCart;
window.clearCart = clearCart;
window.renderCart = renderCart;
window.recalculateCart = recalculateCart;
window.applyCouponCode = applyCouponCode;
window.promptOwnerApproval = promptOwnerApproval;
window.verifyOwnerPin = verifyOwnerPin;
window.processCheckout = processCheckout;

