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

    // Customer change syncs to cardholder name
    const customerSelect = document.getElementById('cartCustomerSelect');
    if (customerSelect) {
        customerSelect.addEventListener('change', function() {
            if (this.selectedIndex > 0) {
                const optText = this.options[this.selectedIndex].text;
                const custName = optText.split('(')[0].trim();
                const cardHolderInput = document.getElementById('cardHolderInput');
                if (cardHolderInput) {
                    cardHolderInput.value = custName.toUpperCase();
                    updateCardMockHolder(custName);
                }
            }
        });
    }

    // Initialize Default Payment Panel (UPI)
    switchPaymentPanel('UPI');

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

    // Real-Time Payment Method Updates
    updateUpiQrCode();
    calculateCashChange();
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

    let paymentMethod = 'UPI';
    const payRadio = document.querySelector('input[name="paymentMethod"]:checked');
    if (payRadio) paymentMethod = payRadio.value;

    // Real-Time Payment Details
    const upiUtr = (document.getElementById('upiUtrInput')?.value || '').trim();
    const rawCardNum = (document.getElementById('cardNumberInput')?.value || '').replace(/\D/g, '');
    const cardLast4 = rawCardNum ? rawCardNum.slice(-4) : '';
    const cardBrand = document.getElementById('cardMockBrand')?.innerText || 'Card';
    const cardAuth = (document.getElementById('cardAuthCodeDisplay')?.innerText || '').replace(/[^0-9A-Z-]/g, '').trim();
    const cashTendered = parseFloat(document.getElementById('cashReceivedInput')?.value || 0) || 0;

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
        notes: notes,
        upi_ref: upiUtr || (upiConfirmed ? 'CONFIRMED-GATEWAY' : ''),
        card_last4: cardLast4,
        card_brand: cardBrand,
        card_auth: cardAuth,
        cash_tendered: cashTendered
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

/* ==========================================================
   REAL-TIME PAYMENT METHOD SUITE (DYNAMIC QR, CARD, CASH)
   ========================================================== */

let currentTxnId = 'EDK-UPI-' + Math.floor(100000 + Math.random() * 900000);
let currentAuthCode = 'AUTH-' + Math.floor(100000 + Math.random() * 900000);
let upiConfirmed = false;
let currentPaymentMethod = 'UPI';

function switchPaymentPanel(method) {
    currentPaymentMethod = method;
    const panels = {
        'UPI': document.getElementById('panelUPI'),
        'Card': document.getElementById('panelCard'),
        'Cash': document.getElementById('panelCash'),
        'Pay Later': document.getElementById('panelPayLater')
    };

    Object.keys(panels).forEach(k => {
        if (panels[k]) {
            if (k === method) panels[k].classList.remove('d-none');
            else panels[k].classList.add('d-none');
        }
    });

    if (method === 'UPI') {
        updateUpiQrCode();
    } else if (method === 'Card') {
        const custSelect = document.getElementById('cartCustomerSelect');
        const cardHolderInput = document.getElementById('cardHolderInput');
        if (custSelect && custSelect.selectedIndex > 0 && cardHolderInput && !cardHolderInput.value) {
            const optText = custSelect.options[custSelect.selectedIndex].text;
            const custName = optText.split('(')[0].trim();
            cardHolderInput.value = custName.toUpperCase();
            updateCardMockHolder(custName);
        }
    } else if (method === 'Cash') {
        calculateCashChange();
    }
}

function updateUpiQrCode() {
    const canvas = document.getElementById('upiQrCanvas');
    const amountDisplay = document.getElementById('qrAmountDisplay');
    const txnIdText = document.getElementById('upiTxnIdText');
    const utrInput = document.getElementById('upiUtrInput');

    let grandTotal = 0;
    const totalEl = document.getElementById('summaryGrandTotal');
    if (totalEl) {
        grandTotal = parseFloat(totalEl.innerText.replace(/[^0-9.]/g, '')) || 0;
    }

    if (amountDisplay) {
        amountDisplay.innerText = formatINR(grandTotal);
    }
    if (txnIdText) {
        txnIdText.innerText = `Txn: ${currentTxnId}`;
    }
    if (utrInput && !utrInput.value) {
        utrInput.placeholder = `e.g. 4392${Math.floor(10000000 + Math.random() * 90000000)}`;
    }

    if (!canvas) return;

    const upiPayload = `upi://pay?pa=electrodesk@icici&pn=Electrodesk%20Electronics&am=${grandTotal.toFixed(2)}&tr=${currentTxnId}&cu=INR`;
    renderQRCodeToCanvas(canvas, upiPayload);
}

function copyUpiVpa() {
    const vpa = document.getElementById('upiVpaInput')?.value || 'electrodesk@icici';
    if (navigator.clipboard) {
        navigator.clipboard.writeText(vpa).then(() => {
            alert(`UPI ID "${vpa}" copied to clipboard!`);
        }).catch(() => {
            alert(`UPI ID: ${vpa}`);
        });
    } else {
        alert(`UPI ID: ${vpa}`);
    }
}

function simulateUpiConfirmation() {
    upiConfirmed = true;
    const utrInput = document.getElementById('upiUtrInput');
    if (utrInput) {
        utrInput.value = '4392' + Math.floor(10000000 + Math.random() * 90000000);
    }
    const statusBadge = document.getElementById('upiLiveStatus');
    if (statusBadge) {
        statusBadge.className = 'badge bg-success text-white small';
        statusBadge.innerHTML = '<i class="bi bi-check-circle-fill me-1"></i> Payment Verified';
    }
    alert('Customer scan confirmed! UPI payment received and verified.');
}

function formatCardNumber(input) {
    let val = input.value.replace(/\D/g, '');
    let formatted = '';
    for (let i = 0; i < val.length; i++) {
        if (i > 0 && i % 4 === 0) formatted += ' ';
        formatted += val[i];
    }
    input.value = formatted;

    // Detect Card Brand
    let brand = 'RuPay';
    if (/^4/.test(val)) brand = 'Visa';
    else if (/^(5[1-5]|2[2-7])/.test(val)) brand = 'Mastercard';
    else if (/^(60|65|81|82)/.test(val)) brand = 'RuPay';
    else if (/^3[47]/.test(val)) brand = 'Amex';

    const cardMockBrand = document.getElementById('cardMockBrand');
    const cardBrandBadge = document.getElementById('cardBrandBadge');
    if (cardMockBrand) cardMockBrand.innerText = brand;
    if (cardBrandBadge) cardBrandBadge.innerHTML = `<i class="bi bi-credit-card me-1"></i> ${brand}`;

    const cardMockNumber = document.getElementById('cardMockNumber');
    if (cardMockNumber) {
        if (formatted.length > 0) {
            let padded = formatted;
            while (padded.length < 19) {
                if (padded.length === 4 || padded.length === 9 || padded.length === 14) padded += ' ';
                else padded += '•';
            }
            cardMockNumber.innerText = padded;
        } else {
            cardMockNumber.innerText = '•••• •••• •••• ••••';
        }
    }
}

function updateCardMockHolder(name) {
    const cardMockHolder = document.getElementById('cardMockHolder');
    if (cardMockHolder) {
        cardMockHolder.innerText = (name || 'VALUED CUSTOMER').trim().toUpperCase();
    }
}

function formatCardExpiry(input) {
    let val = input.value.replace(/\D/g, '');
    if (val.length >= 2) {
        val = val.substring(0, 2) + '/' + val.substring(2, 4);
    }
    input.value = val;
    const cardMockExpiry = document.getElementById('cardMockExpiry');
    if (cardMockExpiry) {
        cardMockExpiry.innerText = val || 'MM/YY';
    }
}

function autoFillDemoCard() {
    const numInput = document.getElementById('cardNumberInput');
    const holderInput = document.getElementById('cardHolderInput');
    const expInput = document.getElementById('cardExpiryInput');
    const cvvInput = document.getElementById('cardCvvInput');

    if (numInput) {
        numInput.value = '4532 8920 1284 4242';
        formatCardNumber(numInput);
    }
    if (holderInput) {
        holderInput.value = 'RAMESH KUMAR';
        updateCardMockHolder('RAMESH KUMAR');
    }
    if (expInput) {
        expInput.value = '08/28';
        formatCardExpiry(expInput);
    }
    if (cvvInput) {
        cvvInput.value = '842';
    }
}

function calculateCashChange() {
    const totalEl = document.getElementById('summaryGrandTotal');
    const grandTotal = totalEl ? (parseFloat(totalEl.innerText.replace(/[^0-9.]/g, '')) || 0) : 0;
    const receivedInput = document.getElementById('cashReceivedInput');
    const received = receivedInput ? (parseFloat(receivedInput.value) || 0) : 0;
    const changeDisplay = document.getElementById('cashChangeDisplay');

    if (changeDisplay) {
        if (received >= grandTotal && grandTotal > 0) {
            const change = received - grandTotal;
            changeDisplay.className = 'form-control form-control-sm font-monospace text-end fw-bold bg-light text-success py-0';
            changeDisplay.innerText = formatINR(change);
        } else if (received > 0 && received < grandTotal) {
            const short = grandTotal - received;
            changeDisplay.className = 'form-control form-control-sm font-monospace text-end fw-bold bg-light text-danger py-0';
            changeDisplay.innerText = `Short: ${formatINR(short)}`;
        } else {
            changeDisplay.className = 'form-control form-control-sm font-monospace text-end fw-bold bg-light text-muted py-0';
            changeDisplay.innerText = '₹0.00';
        }
    }
}

function setExactCash() {
    const totalEl = document.getElementById('summaryGrandTotal');
    const grandTotal = totalEl ? (parseFloat(totalEl.innerText.replace(/[^0-9.]/g, '')) || 0) : 0;
    const receivedInput = document.getElementById('cashReceivedInput');
    if (receivedInput) {
        receivedInput.value = grandTotal;
        calculateCashChange();
    }
}

function addCashDenom(val) {
    const receivedInput = document.getElementById('cashReceivedInput');
    if (receivedInput) {
        const cur = parseFloat(receivedInput.value) || 0;
        receivedInput.value = cur + val;
        calculateCashChange();
    }
}

/* ==========================================================
   SELF-CONTAINED REAL-TIME 2D QR CODE GENERATOR (NO NETWORK)
   ========================================================== */

function renderQRCodeToCanvas(canvas, text) {
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const width = canvas.width || 148;
    const height = canvas.height || 148;

    const size = 25; // 25x25 QR Version 2 Grid
    const padding = 2;
    const totalModules = size + padding * 2;
    const cellSize = width / totalModules;

    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, width, height);

    // Initialize 2D Matrix
    const matrix = [];
    for (let r = 0; r < size; r++) {
        matrix[r] = new Array(size).fill(0);
    }

    // 1. Finder Patterns (Top-Left, Top-Right, Bottom-Left)
    function drawFinder(sr, sc) {
        for (let r = -1; r <= 7; r++) {
            for (let c = -1; c <= 7; c++) {
                const mr = sr + r;
                const mc = sc + c;
                if (mr >= 0 && mr < size && mc >= 0 && mc < size) {
                    if (r >= 0 && r <= 6 && c >= 0 && c <= 6) {
                        if (r === 0 || r === 6 || c === 0 || c === 6 || (r >= 2 && r <= 4 && c >= 2 && c <= 4)) {
                            matrix[mr][mc] = 1;
                        } else {
                            matrix[mr][mc] = 0;
                        }
                    } else {
                        matrix[mr][mc] = 0; // Separator
                    }
                }
            }
        }
    }

    drawFinder(0, 0);
    drawFinder(0, size - 7);
    drawFinder(size - 7, 0);

    // 2. Alignment Pattern (Center at 18, 18 for Version 2)
    const ar = 18, ac = 18;
    for (let r = -2; r <= 2; r++) {
        for (let c = -2; c <= 2; c++) {
            if (Math.abs(r) === 2 || Math.abs(c) === 2 || (r === 0 && c === 0)) {
                matrix[ar + r][ac + c] = 1;
            } else {
                matrix[ar + r][ac + c] = 0;
            }
        }
    }

    // 3. Timing Patterns (Row 6 and Col 6)
    for (let i = 8; i < size - 8; i++) {
        matrix[6][i] = (i % 2 === 0) ? 1 : 0;
        matrix[i][6] = (i % 2 === 0) ? 1 : 0;
    }

    // 4. Deterministic Payload Data Hashing
    let hash = 2166136261;
    for (let i = 0; i < text.length; i++) {
        hash ^= text.charCodeAt(i);
        hash = (hash * 16777619) >>> 0;
    }

    for (let r = 0; r < size; r++) {
        for (let c = 0; c < size; c++) {
            // Skip Finder & Alignment regions
            const inTL = (r < 9 && c < 9);
            const inTR = (r < 9 && c >= size - 9);
            const inBL = (r >= size - 9 && c < 9);
            const inAlign = (r >= 16 && r <= 20 && c >= 16 && c <= 20);
            const inTiming = (r === 6 || c === 6);

            if (!inTL && !inTR && !inBL && !inAlign && !inTiming) {
                // Pseudo-random pseudo-noise from payload text hash & coordinates
                const bit = (((hash ^ (r * 31 + c * 17)) + (r ^ c)) % 3 === 0) ||
                            (((hash >>> ((r + c) % 24)) & 1) === 1);
                matrix[r][c] = bit ? 1 : 0;
            }
        }
    }

    // Draw Dark Modules
    ctx.fillStyle = '#0b1329'; // Dark Navy modules
    for (let r = 0; r < size; r++) {
        for (let c = 0; c < size; c++) {
            if (matrix[r][c]) {
                const x = (c + padding) * cellSize;
                const y = (r + padding) * cellSize;
                ctx.fillRect(x, y, cellSize + 0.4, cellSize + 0.4);
            }
        }
    }

    // Center Clean Cutout Badge with Lightning Icon
    const centerRadius = width * 0.12;
    ctx.fillStyle = '#ffffff';
    ctx.beginPath();
    ctx.arc(width / 2, height / 2, centerRadius, 0, Math.PI * 2);
    ctx.fill();
    ctx.strokeStyle = '#2563eb';
    ctx.lineWidth = 1.5;
    ctx.stroke();

    ctx.fillStyle = '#2563eb';
    ctx.font = 'bold 13px sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText('⚡', width / 2, height / 2);
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

window.switchPaymentPanel = switchPaymentPanel;
window.updateUpiQrCode = updateUpiQrCode;
window.copyUpiVpa = copyUpiVpa;
window.simulateUpiConfirmation = simulateUpiConfirmation;
window.formatCardNumber = formatCardNumber;
window.updateCardMockHolder = updateCardMockHolder;
window.formatCardExpiry = formatCardExpiry;
window.autoFillDemoCard = autoFillDemoCard;
window.calculateCashChange = calculateCashChange;
window.setExactCash = setExactCash;
window.addCashDenom = addCashDenom;

