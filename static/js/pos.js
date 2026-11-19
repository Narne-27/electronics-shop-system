/**
 * Electrodesk - Point of Sale (POS) Logic
 * Fast product lookup, reactive cart, live GST (CGST 9% + SGST 9%) calculations,
 * shared Indian Rupee formatting, serial number input for warranty tracking, and checkout.
 */

let cart = []; // Array of { product_id, name, code, price, quantity, stock, warranty_months, serial_number }

// Shared INR Formatter as required
const inrFormatter = new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0
});

function formatINR(val) {
    if (val === null || val === undefined || isNaN(val)) return '₹0';
    return inrFormatter.format(Math.round(val));
}

document.addEventListener('DOMContentLoaded', function() {
    initFilters();
});

// Initialize live search and category pill filtering
function initFilters() {
    const searchInput = document.getElementById('posSearchInput');
    const clearBtn = document.getElementById('clearSearchBtn');
    const catSelect = document.getElementById('posCategoryFilter');
    const catPills = document.querySelectorAll('.cat-pill');

    if (searchInput) {
        searchInput.addEventListener('input', applyFilters);
    }

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
            catSelect.value = cat;
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
    const query = document.getElementById('posSearchInput').value.toLowerCase().trim();
    const cat = document.getElementById('posCategoryFilter').value;
    const items = document.querySelectorAll('.product-pos-item');
    let visibleCount = 0;

    items.forEach(item => {
        const name = item.getAttribute('data-name');
        const code = item.getAttribute('data-code');
        const brand = item.getAttribute('data-brand');
        const itemCat = item.getAttribute('data-category');

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
        if (visibleCount === 0) {
            noMatch.classList.remove('d-none');
        } else {
            noMatch.classList.add('d-none');
        }
    }
}

// Cart Operations
function addToCart(productId) {
    const product = PRODUCTS_MAP[productId];
    if (!product) return;

    if (product.stock_quantity <= 0) {
        alert(`Sorry, "${product.product_name}" is currently out of stock.`);
        return;
    }

    const existingIndex = cart.findIndex(item => item.product_id === productId);

    if (existingIndex > -1) {
        if (cart[existingIndex].quantity + 1 > product.stock_quantity) {
            alert(`Stock limit reached! Only ${product.stock_quantity} units available for ${product.product_name}.`);
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
    const index = cart.findIndex(item => item.product_id === productId);
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
    const index = cart.findIndex(item => item.product_id === productId);
    if (index > -1) {
        cart[index].serial_number = serialVal.trim();
    }
}

function removeFromCart(productId) {
    cart = cart.filter(item => item.product_id !== productId);
    renderCart();
}

function clearCart() {
    if (cart.length === 0) return;
    if (confirm('Are you sure you want to clear all items from the cart?')) {
        cart = [];
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
                <small>Click on any product on the left to add items</small>
            </div>
        `;
        if (checkoutBtn) checkoutBtn.disabled = true;
        recalculateCart();
        return;
    }

    let html = '';
    cart.forEach(item => {
        const itemTotal = item.price * item.quantity;
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
                    <input type="text" class="form-control form-control-sm font-monospace text-muted py-0" 
                           placeholder="Serial # (for warranty)" 
                           value="${item.serial_number}" 
                           onchange="updateItemSerial(${item.product_id}, this.value)"
                           style="font-size: 0.75rem;" title="Device Serial Number for Warranty">
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

    const taxSelect = document.getElementById('cartTaxRate');
    const taxRate = taxSelect ? parseFloat(taxSelect.value || 0) : 18;
    
    // CGST + SGST breakdown for Indian GST
    const cgstAmount = Math.round(subtotal * ((taxRate / 2) / 100));
    const sgstAmount = Math.round(subtotal * ((taxRate / 2) / 100));
    const totalGst = cgstAmount + sgstAmount;

    const discountInput = document.getElementById('cartDiscount');
    const discount = discountInput ? (parseFloat(discountInput.value) || 0) : 0;

    const grandTotal = Math.max(0, Math.round(subtotal + totalGst - discount));

    const subtotalEl = document.getElementById('summarySubtotal');
    if (subtotalEl) subtotalEl.innerText = formatINR(subtotal);

    const cgstEl = document.getElementById('summaryCGST');
    if (cgstEl) cgstEl.innerText = formatINR(cgstAmount);

    const sgstEl = document.getElementById('summarySGST');
    if (sgstEl) sgstEl.innerText = formatINR(sgstAmount);

    const taxEl = document.getElementById('summaryTax');
    if (taxEl) taxEl.innerText = formatINR(totalGst);

    const grandTotalEl = document.getElementById('summaryGrandTotal');
    if (grandTotalEl) grandTotalEl.innerText = formatINR(grandTotal);
}

// Quick Customer Modal
async function handleQuickCustomerSubmit(e) {
    e.preventDefault();
    const btn = document.getElementById('saveQuickCustBtn');
    btn.disabled = true;
    btn.innerHTML = `<span class="spinner-border spinner-border-sm me-1"></span>Saving...`;

    const name = document.getElementById('quickCustName').value.trim();
    const phone = document.getElementById('quickCustPhone').value.trim();
    const email = document.getElementById('quickCustEmail').value.trim();
    const address = document.getElementById('quickCustAddress').value.trim();

    const formData = new FormData();
    formData.append('customer_name', name);
    formData.append('phone', phone);
    formData.append('email', email);
    formData.append('address', address);

    try {
        const response = await fetch('/customers/add', {
            method: 'POST',
            body: formData,
            headers: { 'X-Requested-With': 'XMLHttpRequest' }
        });
        const res = await response.json();

        if (res.success && res.customer) {
            const select = document.getElementById('cartCustomerSelect');
            const newOpt = document.createElement('option');
            newOpt.value = res.customer.customer_id;
            newOpt.text = `${res.customer.customer_name} (${res.customer.phone})`;
            newOpt.selected = true;
            select.appendChild(newOpt);

            const modalEl = document.getElementById('newCustomerModal');
            const modalInstance = bootstrap.Modal.getInstance(modalEl);
            if (modalInstance) modalInstance.hide();
            document.getElementById('quickCustomerForm').reset();
        } else {
            alert('Failed to register customer: ' + (res.message || 'Unknown error'));
        }
    } catch (err) {
        alert('Error connecting to server: ' + err.message);
    } finally {
        btn.disabled = false;
        btn.innerHTML = 'Save & Select';
    }
}

// Process Checkout & Generate Printable Invoice
async function processCheckout() {
    if (cart.length === 0) {
        alert('Cart is empty. Please add products to check out.');
        return;
    }

    const checkoutBtn = document.getElementById('checkoutBtn');
    checkoutBtn.disabled = true;
    checkoutBtn.innerHTML = `<span class="spinner-border spinner-border-sm me-2"></span>Processing & Generating Bill...`;

    const customerId = document.getElementById('cartCustomerSelect').value || null;
    const taxRate = parseFloat(document.getElementById('cartTaxRate').value || 18);
    const discount = parseFloat(document.getElementById('cartDiscount').value || 0);
    const notes = document.getElementById('cartNotes').value || '';
    
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
        payment_status: 'Paid',
        tax_rate: taxRate,
        discount_amount: discount,
        notes: notes
    };

    try {
        const response = await fetch('/api/pos/checkout', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
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
        alert('Network error while processing checkout: ' + err.message);
        checkoutBtn.disabled = false;
        checkoutBtn.innerHTML = `<i class="bi bi-check-circle-fill fs-5"></i> <span>Generate Bill & Invoice</span>`;
    }
}
