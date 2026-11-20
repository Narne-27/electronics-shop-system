"""
Electrodesk - Database Initialization & Comprehensive Seed Script
Sets up the relational tables and seeds 4 users, 7 categories, 31 Indian products,
14 days of sequential invoices, stock movements, warranties, claims, and operations data.
All dates derive from the central APP_TODAY anchor.
"""
import os
import sys
import datetime
import sqlite3
import config
from werkzeug.security import generate_password_hash

try:
    import pymysql
    PYMYSQL_AVAILABLE = True
except ImportError:
    PYMYSQL_AVAILABLE = False


SQLITE_SCHEMA = """
-- 1. USER: Staff & Admin Accounts
CREATE TABLE IF NOT EXISTS USER (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    full_name TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'Sales Staff',
    avatar TEXT NOT NULL DEFAULT 'U',
    email TEXT,
    phone TEXT,
    status TEXT NOT NULL DEFAULT 'Active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. CATEGORY: Product Departments
CREATE TABLE IF NOT EXISTS CATEGORY (
    category_id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_code TEXT NOT NULL UNIQUE,
    category_name TEXT NOT NULL UNIQUE,
    icon TEXT DEFAULT 'bi-grid-fill',
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. PRODUCT: Electronics Inventory
CREATE TABLE IF NOT EXISTS PRODUCT (
    product_id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_code TEXT NOT NULL UNIQUE,
    product_name TEXT NOT NULL,
    category_id INTEGER NOT NULL,
    brand TEXT NOT NULL,
    model TEXT,
    hsn_code TEXT DEFAULT '8517',
    tagline TEXT,
    image_url TEXT DEFAULT '/static/images/logo.svg',
    is_new INTEGER DEFAULT 0,
    cost_price REAL NOT NULL DEFAULT 0.0,
    selling_price REAL NOT NULL DEFAULT 0.0,
    tax_rate REAL NOT NULL DEFAULT 18.0,
    stock_quantity INTEGER NOT NULL DEFAULT 0,
    reorder_level INTEGER NOT NULL DEFAULT 5,
    warranty_months INTEGER NOT NULL DEFAULT 12,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (category_id) REFERENCES CATEGORY(category_id) ON DELETE RESTRICT
);

-- 4. CUSTOMER: Customer Directory
CREATE TABLE IF NOT EXISTS CUSTOMER (
    customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_name TEXT NOT NULL,
    phone TEXT NOT NULL UNIQUE,
    email TEXT,
    city TEXT DEFAULT 'Hyderabad',
    address TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 5. SALE: Sales Invoices & Checkout Transactions
CREATE TABLE IF NOT EXISTS SALE (
    sale_id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_number TEXT NOT NULL UNIQUE,
    customer_id INTEGER,
    user_id INTEGER NOT NULL,
    sale_date TIMESTAMP NOT NULL,
    subtotal REAL NOT NULL DEFAULT 0.0,
    cgst_amount REAL NOT NULL DEFAULT 0.0,
    sgst_amount REAL NOT NULL DEFAULT 0.0,
    tax_amount REAL NOT NULL DEFAULT 0.0,
    discount_amount REAL NOT NULL DEFAULT 0.0,
    discount_type TEXT DEFAULT 'none',
    discount_rate REAL DEFAULT 0.0,
    owner_approved INTEGER DEFAULT 0,
    exchange_device TEXT,
    exchange_value REAL DEFAULT 0.0,
    grand_total REAL NOT NULL DEFAULT 0.0,
    payment_method TEXT NOT NULL DEFAULT 'Cash',
    payment_status TEXT NOT NULL DEFAULT 'Paid',
    amount_paid REAL NOT NULL DEFAULT 0.0,
    balance_due REAL NOT NULL DEFAULT 0.0,
    emi_months INTEGER DEFAULT 0,
    emi_interest_rate REAL DEFAULT 0.0,
    emi_monthly_amount REAL DEFAULT 0.0,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (customer_id) REFERENCES CUSTOMER(customer_id) ON DELETE SET NULL,
    FOREIGN KEY (user_id) REFERENCES USER(user_id)
);

-- 6. SALE_ITEM: Line-Item Details & Warranties
CREATE TABLE IF NOT EXISTS SALE_ITEM (
    item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 1,
    unit_price REAL NOT NULL DEFAULT 0.0,
    total_price REAL NOT NULL DEFAULT 0.0,
    serial_number TEXT,
    warranty_months INTEGER DEFAULT 12,
    warranty_expiry_date TEXT,
    FOREIGN KEY (sale_id) REFERENCES SALE(sale_id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES PRODUCT(product_id)
);

-- 7. STOCK_MOVEMENT: Inventory In/Out Audit Trail
CREATE TABLE IF NOT EXISTS STOCK_MOVEMENT (
    movement_id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    movement_type TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    reason TEXT NOT NULL,
    reference_id TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id) REFERENCES PRODUCT(product_id)
);

-- 8. WARRANTY_CLAIM: Service Center Claims on Warranties
CREATE TABLE IF NOT EXISTS WARRANTY_CLAIM (
    claim_id INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_number TEXT NOT NULL UNIQUE,
    item_id INTEGER,
    serial_number TEXT NOT NULL,
    customer_id INTEGER,
    product_id INTEGER,
    claim_date TEXT NOT NULL,
    issue_description TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'Open',
    resolution_notes TEXT,
    resolved_at TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (customer_id) REFERENCES CUSTOMER(customer_id)
);

-- 9. CREDIT_NOTE: Return & Refund Records
CREATE TABLE IF NOT EXISTS CREDIT_NOTE (
    credit_note_id INTEGER PRIMARY KEY AUTOINCREMENT,
    credit_note_number TEXT NOT NULL UNIQUE,
    sale_id INTEGER NOT NULL,
    customer_id INTEGER,
    refund_amount REAL NOT NULL,
    reason TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sale_id) REFERENCES SALE(sale_id)
);

-- 10. CUSTOMER_PAYMENT: Ledger Receipts for Partial/Credit Sales
CREATE TABLE IF NOT EXISTS CUSTOMER_PAYMENT (
    payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL,
    sale_id INTEGER,
    payment_date TIMESTAMP NOT NULL,
    amount REAL NOT NULL,
    payment_method TEXT NOT NULL DEFAULT 'Cash',
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (customer_id) REFERENCES CUSTOMER(customer_id)
);

-- 11. SUPPLIER: Vendor Directory
CREATE TABLE IF NOT EXISTS SUPPLIER (
    supplier_id INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier_name TEXT NOT NULL,
    contact_person TEXT,
    phone TEXT,
    email TEXT,
    gstin TEXT,
    city TEXT,
    address TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 12. PURCHASE_ORDER: Vendor POs & Restocking
CREATE TABLE IF NOT EXISTS PURCHASE_ORDER (
    po_id INTEGER PRIMARY KEY AUTOINCREMENT,
    po_number TEXT NOT NULL UNIQUE,
    supplier_id INTEGER NOT NULL,
    order_date TEXT NOT NULL,
    expected_date TEXT,
    status TEXT NOT NULL DEFAULT 'Draft',
    total_amount REAL NOT NULL DEFAULT 0.0,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (supplier_id) REFERENCES SUPPLIER(supplier_id)
);

-- 13. PURCHASE_ORDER_ITEM: Items in Purchase Order
CREATE TABLE IF NOT EXISTS PURCHASE_ORDER_ITEM (
    po_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    po_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity_ordered INTEGER NOT NULL,
    quantity_received INTEGER NOT NULL DEFAULT 0,
    unit_cost REAL NOT NULL,
    total_cost REAL NOT NULL,
    FOREIGN KEY (po_id) REFERENCES PURCHASE_ORDER(po_id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES PRODUCT(product_id)
);

-- 14. QUOTATION: Customer Estimates
CREATE TABLE IF NOT EXISTS QUOTATION (
    quote_id INTEGER PRIMARY KEY AUTOINCREMENT,
    quote_number TEXT NOT NULL UNIQUE,
    customer_id INTEGER,
    quote_date TEXT NOT NULL,
    expiry_date TEXT NOT NULL,
    subtotal REAL NOT NULL,
    tax_amount REAL NOT NULL,
    discount_amount REAL DEFAULT 0.0,
    grand_total REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'Draft',
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (customer_id) REFERENCES CUSTOMER(customer_id)
);

-- 15. QUOTATION_ITEM: Items in Quotation
CREATE TABLE IF NOT EXISTS QUOTATION_ITEM (
    quote_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    quote_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price REAL NOT NULL,
    total_price REAL NOT NULL,
    FOREIGN KEY (quote_id) REFERENCES QUOTATION(quote_id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES PRODUCT(product_id)
);

-- 16. REPAIR_TICKET: Device Servicing & Warranty Repairs
CREATE TABLE IF NOT EXISTS REPAIR_TICKET (
    ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_number TEXT NOT NULL UNIQUE,
    claim_id INTEGER,
    customer_id INTEGER,
    product_name TEXT NOT NULL,
    serial_number TEXT,
    issue_description TEXT NOT NULL,
    technician TEXT,
    estimated_cost REAL DEFAULT 0.0,
    actual_cost REAL DEFAULT 0.0,
    status TEXT NOT NULL DEFAULT 'Received',
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (customer_id) REFERENCES CUSTOMER(customer_id)
);

-- 17. EXPENSE: Operational Shop Expenses
CREATE TABLE IF NOT EXISTS EXPENSE (
    expense_id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,
    amount REAL NOT NULL,
    expense_date TEXT NOT NULL,
    payment_method TEXT NOT NULL DEFAULT 'Bank Transfer',
    notes TEXT,
    created_by TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 18. DAILY_CLOSING: Daily Cash & Drawer Reconciliation
CREATE TABLE IF NOT EXISTS DAILY_CLOSING (
    closing_id INTEGER PRIMARY KEY AUTOINCREMENT,
    closing_date TEXT NOT NULL UNIQUE,
    expected_cash REAL NOT NULL DEFAULT 0.0,
    actual_cash REAL NOT NULL DEFAULT 0.0,
    expected_upi REAL NOT NULL DEFAULT 0.0,
    expected_card REAL NOT NULL DEFAULT 0.0,
    expected_total REAL NOT NULL DEFAULT 0.0,
    cash_difference REAL NOT NULL DEFAULT 0.0,
    notes TEXT,
    closed_by TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 19. AUDIT_LOG: Administrative Event Logging
CREATE TABLE IF NOT EXISTS AUDIT_LOG (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    username TEXT,
    action TEXT NOT NULL,
    module TEXT NOT NULL,
    details TEXT,
    ip_address TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 20. STORE_SETTING: Key-Value Dynamic Settings
CREATE TABLE IF NOT EXISTS STORE_SETTING (
    setting_key TEXT PRIMARY KEY,
    setting_value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def seed_database(cursor, is_mysql=False):
    """Seed comprehensive relational demo data anchored to config.APP_TODAY."""
    p = '%s' if is_mysql else '?'
    today = getattr(config, 'APP_TODAY', datetime.date(2026, 11, 19))
    if isinstance(today, str):
        today = datetime.datetime.strptime(today, '%Y-%m-%d').date()

    # 1. USERS
    cursor.execute("SELECT COUNT(*) FROM USER")
    if cursor.fetchone()[0] == 0:
        users = [
            ('admin', generate_password_hash('admin123'), 'Ram', 'System Administrator', 'RA', 'ram.admin@electrodesk.in', '+91 98480 11001', 'Active'),
            ('geetha', generate_password_hash('geetha123'), 'Geetha', 'Shop Manager', 'GE', 'geetha.mgr@electrodesk.in', '+91 98480 22002', 'Active'),
            ('sai', generate_password_hash('sai123'), 'Sai', 'Sales Staff', 'SA', 'sai.sales@electrodesk.in', '+91 98480 33003', 'Active'),
            ('suresh', generate_password_hash('suresh123'), 'Suresh', 'Shop Owner', 'S', 'suresh.owner@electrodesk.in', '+91 98480 44004', 'Active')
        ]
        cursor.executemany(f"""
            INSERT INTO USER (username, password_hash, full_name, role, avatar, email, phone, status)
            VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p}, {p})
        """, users)

    # 2. CATEGORIES (7 Categories)
    cursor.execute("SELECT COUNT(*) FROM CATEGORY")
    if cursor.fetchone()[0] == 0:
        categories = [
            ('CAT-01', 'Smartphones & Tablets', 'bi-phone-fill', '5G flagships, foldables, budget smartphones, iPads and Android tablets'),
            ('CAT-02', 'Laptops & Computers', 'bi-laptop-fill', 'Ultrabooks, workstation PCs, gaming laptops, and high-performance desktops'),
            ('CAT-03', 'Audio & Sound', 'bi-headphones', 'Noise-cancelling wireless headphones, soundbars, TWS earbuds and Bluetooth speakers'),
            ('CAT-04', 'Smart TVs & Displays', 'bi-tv-fill', '4K/8K OLED, QLED, gaming monitors, home theatre screens and projectors'),
            ('CAT-05', 'Smart Home & IoT', 'bi-house-gear-fill', 'Mesh Wi-Fi routers, robot vacuum cleaners, security cameras and smart plugs'),
            ('CAT-06', 'Gaming & Consoles', 'bi-controller', 'PlayStation, Xbox, Nintendo consoles, mechanical keyboards and gaming headsets'),
            ('CAT-07', 'Wearables & Fitness', 'bi-smartwatch', 'Smartwatches, cellular fitness trackers, and health monitoring bands')
        ]
        cursor.executemany(f"""
            INSERT INTO CATEGORY (category_code, category_name, icon, description)
            VALUES ({p}, {p}, {p}, {p})
        """, categories)

    # 3. PRODUCTS (31 Indian-market electronics items: SKU, HSN, Cost, Selling, GST 18%, Stock, Reorder, Warranty, Tagline, isNew)
    cursor.execute("SELECT COUNT(*) FROM PRODUCT")
    if cursor.fetchone()[0] == 0:
        products = [
            # Smartphones & Tablets (CAT-01)
            ('ELEC-SMP-001', 'Samsung Galaxy S24 Ultra 512GB', 1, 'Samsung', 'SM-S928B', '8517', 'AI Zoom & Titanium Frame', 108000.0, 129999.0, 18.0, 12, 3, 12, 1, 'Flagship Snapdragon 8 Gen 3 with S-Pen and 200MP Quad Camera'),
            ('ELEC-SMP-002', 'Apple iPhone 15 Pro Max 256GB', 1, 'Apple', 'MU783HN/A', '8517', 'Titanium. A17 Pro Chip.', 118000.0, 144900.0, 18.0, 8, 3, 12, 1, 'Grade 5 titanium design, Action button, USB-C 3, and 5x telephoto camera'),
            ('ELEC-SMP-003', 'Xiaomi Redmi Note 13 Pro+ 5G', 1, 'Xiaomi', '23090RA98I', '8517', '200MP Camera with OIS', 23000.0, 29999.0, 18.0, 18, 5, 12, 1, 'Curved AMOLED, 120W HyperCharge, IP68 water resistance'),
            ('ELEC-SMP-004', 'OnePlus 12 5G 256GB', 1, 'OnePlus', 'CPH2581', '8517', 'Smooth Beyond Belief', 52000.0, 64999.0, 18.0, 10, 4, 12, 1, 'Snapdragon 8 Gen 3, Hasselblad 4th Gen Camera, 5400mAh battery'),
            ('ELEC-SMP-005', 'Apple iPad Air 11" M2 128GB', 1, 'Apple', 'MUWC3HN/A', '8471', 'Fresh Air. Powerful M2.', 47000.0, 59900.0, 18.0, 9, 3, 12, 1, 'Liquid Retina display, Apple Intelligence ready, Landscape front camera'),

            # Laptops & Computers (CAT-02)
            ('ELEC-LAP-001', 'HP Pavilion 15 Core i7 16GB', 2, 'HP', '15-eg3079TX', '8471', 'Productivity & FHD Display', 62000.0, 77990.0, 18.0, 11, 4, 12, 0, '13th Gen Intel Core i7-1355U, 16GB DDR4, 1TB SSD, Iris Xe Graphics'),
            ('ELEC-LAP-002', 'Dell Inspiron 15 16GB SSD', 2, 'Dell', 'IN3530-7718', '8471', 'Reliable Daily Performance', 44000.0, 54990.0, 18.0, 14, 5, 12, 0, 'Intel Core i5-1335U, 16GB RAM, 512GB NVMe SSD, 120Hz display'),
            ('ELEC-LAP-003', 'Apple MacBook Air 13" M2', 2, 'Apple', 'MLXW3HN/A', '8471', 'Strikingly Thin Design', 79000.0, 99900.0, 18.0, 10, 3, 12, 0, 'Apple M2 8-core CPU, 13.6-inch Liquid Retina display, MagSafe 3'),
            ('ELEC-LAP-004', 'Asus ROG Zephyrus G16', 2, 'Asus', 'GU605MY-QR052W', '8471', 'AI Gaming Powerhouse', 155000.0, 189990.0, 18.0, 4, 2, 24, 1, 'Intel Core Ultra 9, RTX 4080 12GB, 2.5K OLED 240Hz, 32GB RAM'),
            ('ELEC-LAP-005', 'Lenovo IdeaPad Slim 3 15"', 2, 'Lenovo', '83ER0088IN', '8471', 'Smart Everyday Computing', 32000.0, 39990.0, 18.0, 15, 5, 12, 0, 'Core i3-1305U, 8GB LPDDR5, 512GB SSD, Rapid Charge'),
            ('ELEC-ACC-001', 'Logitech MX Keys Wireless Keyboard', 2, 'Logitech', '920-009295', '8471', 'Master Series Precision', 7500.0, 9995.0, 18.0, 22, 6, 12, 0, 'Spherically dished keys, smart backlighting, multi-device Flow'),
            ('ELEC-ACC-002', 'SanDisk Extreme 1TB Portable SSD', 2, 'SanDisk', 'SDSSDE61-1T00-G25', '8471', 'Tough & Fast 1050MB/s', 6800.0, 8999.0, 18.0, 25, 6, 36, 0, 'IP55 water and dust resistance, 2-meter drop protection'),

            # Audio & Sound (CAT-03)
            ('ELEC-AUD-001', 'boAt Airdopes 141 ANC Earbuds', 3, 'boAt', 'Airdopes 141 ANC', '8518', 'Crystal Bionic Sound', 1100.0, 1699.0, 18.0, 40, 10, 12, 1, '32dB Active Noise Cancellation, 42 hours playback, ENx quad mics'),
            ('ELEC-AUD-002', 'JBL Flip 6 Waterproof Speaker', 3, 'JBL', 'JBLFLIP6BLKIN', '8518', 'Bold JBL Original Pro Sound', 7200.0, 9999.0, 18.0, 18, 5, 12, 0, '2-way speaker system, IP67 waterproof & dustproof, PartyBoost'),
            ('ELEC-AUD-003', 'Sony WH-1000XM5 Headphones', 3, 'Sony', 'WH1000XM5/B', '8518', 'Industry-Leading ANC', 21000.0, 29990.0, 18.0, 12, 4, 12, 0, 'Two processors and 8 microphones for superior noise cancelling'),
            ('ELEC-AUD-004', 'boAt Stone 1200 Bluetooth Speaker', 3, 'boAt', 'Stone 1200 BK', '8518', '14W Immersive Stereo', 2400.0, 3499.0, 18.0, 24, 6, 12, 0, 'RGB LEDs, 360-degree cylindrical design, IPX7 water resistance'),
            ('ELEC-AUD-005', 'Marshall Stanmore III Speaker', 3, 'Marshall', '1006010', '8518', 'Legendary Stage Audio', 28000.0, 36999.0, 18.0, 5, 2, 12, 0, 'Room-filling spatial sound, Bluetooth 5.2, analog brass knobs'),

            # Smart TVs & Displays (CAT-04)
            ('ELEC-DIS-001', 'Mi TV 43" 4K Google TV', 4, 'Xiaomi', 'L43M8-A2IN', '8528', 'Bezel-less 4K Dolby Vision', 19000.0, 24999.0, 18.0, 14, 4, 12, 1, '4K Ultra HD HDR10+, Google TV with PatchWall, 30W Dolby Audio'),
            ('ELEC-DIS-002', 'LG 55" OLED 4K Smart Cinema TV', 4, 'LG', 'OLED55B4PSA', '8528', 'Self-Lit Pixels & Infinite Contrast', 95000.0, 119990.0, 18.0, 6, 2, 24, 1, 'alpha 8 AI Processor 4K, 120Hz refresh, Dolby Vision & Atmos'),
            ('ELEC-DIS-003', 'Samsung 65" Neo QLED 4K TV', 4, 'Samsung', 'QA65QN85DAULXL', '8528', 'Quantum Matrix Technology', 125000.0, 159990.0, 18.0, 4, 2, 24, 0, 'NQ4 AI Gen2 Processor, Dolby Atmos with OTS+, NeoSlim Design'),
            ('ELEC-DIS-004', 'Sony Bravia 55" 4K Google TV', 4, 'Sony', 'KD-55X74L', '8528', 'X1 4K Processor Clarity', 48000.0, 59990.0, 18.0, 8, 3, 24, 0, 'Live Colour technology, Motionflow XR 100, Google TV'),

            # Smart Home & IoT (CAT-05)
            ('ELEC-IOT-001', 'Amazon Echo Dot 5th Gen Clock', 5, 'Amazon', 'B09B8W5FW7', '8518', 'Vibrant Sound with Alexa', 3800.0, 5499.0, 18.0, 25, 6, 12, 0, 'High-definition LED display showing time, alarms, weather'),
            ('ELEC-IOT-002', 'Dyson V12 Detect Slim Vacuum', 5, 'Dyson', '368340-01', '8509', 'Illuminates Hidden Dust', 42000.0, 52900.0, 18.0, 7, 2, 24, 1, 'Laser reveals microscopic dust, piezo sensor measures dust particles'),
            ('ELEC-IOT-003', 'TP-Link Archer AX73 WiFi 6', 5, 'TP-Link', 'Archer AX73', '8517', 'Gigabit Dual-Band AX5400', 6500.0, 8499.0, 18.0, 16, 5, 36, 0, '6 high-gain antennas, HomeShield security, OneMesh supported'),
            ('ELEC-IOT-004', 'Wipro 16A Smart WiFi Plug', 5, 'Wipro', 'DS22000', '8536', 'App & Voice Control', 650.0, 999.0, 18.0, 40, 10, 12, 0, 'Suitable for geysers, ACs and high-wattage appliances with energy monitoring'),
            ('ELEC-ACC-003', 'Anker 65W GaN Fast Charger', 5, 'Anker', 'A2663111', '8504', 'Nano II 3-Port GaN Tech', 2400.0, 3499.0, 18.0, 30, 8, 18, 0, 'Simultaneous high-speed charging for phone, tablet and MacBook'),

            # Gaming & Consoles (CAT-06)
            ('ELEC-GAM-001', 'Sony PlayStation 5 Slim 1TB', 6, 'Sony', 'CFI-2008A01X', '9504', 'Ultra-High Speed SSD', 41000.0, 49990.0, 18.0, 7, 2, 12, 1, 'Slim design with 1TB storage, DualSense haptic feedback, 4K 120Hz'),
            ('ELEC-GAM-002', 'Microsoft Xbox Series X 1TB', 6, 'Microsoft', 'RRT-00021', '9504', 'Fastest & Most Powerful', 43000.0, 54990.0, 18.0, 5, 2, 12, 0, '12 Teraflops GPU, Xbox Velocity Architecture, True 4K gaming'),
            ('ELEC-GAM-003', 'Nintendo Switch OLED Model', 6, 'Nintendo', 'HEG-S-KABAA', '9504', 'Vibrant 7-inch OLED Screen', 26000.0, 32999.0, 18.0, 8, 3, 12, 0, 'Enhanced audio, 64GB internal storage, wide adjustable stand'),

            # Wearables & Fitness (CAT-07)
            ('ELEC-WRB-001', 'Apple Watch Series 9 GPS 45mm', 7, 'Apple', 'MR9A3HN/A', '8517', 'S9 SiP with Double Tap Gesture', 34000.0, 44900.0, 18.0, 9, 3, 12, 1, 'Always-On Retina 2000 nits, Blood Oxygen, ECG, Crash Detection'),
            ('ELEC-WRB-002', 'Noise ColorFit Pro 5 Smartwatch', 7, 'Noise', 'WPB-012', '8517', '1.85" AMOLED Display', 2100.0, 2999.0, 18.0, 28, 8, 12, 0, 'BT Calling, SOS technology, rapid health suite monitoring')
        ]
        cursor.executemany(f"""
            INSERT INTO PRODUCT (product_code, product_name, category_id, brand, model, hsn_code, tagline, cost_price, selling_price, tax_rate, stock_quantity, reorder_level, warranty_months, is_new, description)
            VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p})
        """, products)

        # Map matching studio product images
        slug_map = {
            'ELEC-SMP-001': '/static/images/products/samsung-galaxy-s24-ultra-512gb.webp',
            'ELEC-SMP-002': '/static/images/products/apple-iphone-15-pro-max-256gb.webp',
            'ELEC-SMP-003': '/static/images/products/xiaomi-redmi-note-13-pro-5g.webp',
            'ELEC-SMP-004': '/static/images/products/oneplus-12-5g-256gb.webp',
            'ELEC-SMP-005': '/static/images/products/apple-ipad-air-11-m2-128gb.webp',
            'ELEC-LAP-001': '/static/images/products/hp-pavilion-15-core-i7-16gb.webp',
            'ELEC-LAP-002': '/static/images/products/dell-inspiron-15-16gb-ssd.webp',
            'ELEC-LAP-003': '/static/images/products/apple-macbook-air-13-m2.webp',
            'ELEC-LAP-004': '/static/images/products/asus-rog-zephyrus-g16.webp',
            'ELEC-LAP-005': '/static/images/products/lenovo-ideapad-slim-3-15.webp',
            'ELEC-ACC-001': '/static/images/products/logitech-mx-keys-wireless-keyboard.webp',
            'ELEC-ACC-002': '/static/images/products/sandisk-extreme-1tb-portable-ssd.webp',
            'ELEC-AUD-001': '/static/images/products/boat-airdopes-141-anc-earbuds.webp',
            'ELEC-AUD-002': '/static/images/products/jbl-flip-6-waterproof-speaker.webp',
            'ELEC-AUD-003': '/static/images/products/sony-wh-1000xm5-headphones.webp',
            'ELEC-AUD-004': '/static/images/products/boat-stone-1200-bluetooth-speaker.webp',
            'ELEC-AUD-005': '/static/images/products/marshall-stanmore-iii-speaker.webp',
            'ELEC-DIS-001': '/static/images/products/mi-tv-43-4k-google-tv.webp',
            'ELEC-DIS-002': '/static/images/products/lg-55-oled-4k-smart-cinema-tv.webp',
            'ELEC-DIS-003': '/static/images/products/samsung-65-neo-qled-4k-tv.webp',
            'ELEC-DIS-004': '/static/images/products/sony-bravia-55-4k-google-tv.webp',
            'ELEC-IOT-001': '/static/images/products/amazon-echo-dot-5th-gen-clock.webp',
            'ELEC-IOT-002': '/static/images/products/dyson-v12-detect-slim-vacuum.webp',
            'ELEC-IOT-003': '/static/images/products/tp-link-archer-ax73-wifi-6.webp',
            'ELEC-IOT-004': '/static/images/products/wipro-16a-smart-wifi-plug.webp',
            'ELEC-ACC-003': '/static/images/products/anker-65w-gan-fast-charger.webp',
            'ELEC-GAM-001': '/static/images/products/sony-playstation-5-slim-1tb.webp',
            'ELEC-GAM-002': '/static/images/products/microsoft-xbox-series-x-1tb.webp',
            'ELEC-GAM-003': '/static/images/products/nintendo-switch-oled-model.webp',
            'ELEC-WRB-001': '/static/images/products/apple-watch-series-9-gps-45mm.webp',
            'ELEC-WRB-002': '/static/images/products/noise-colorfit-pro-5-smartwatch.webp',
        }
        for code, img_url in slug_map.items():
            cursor.execute(f"UPDATE PRODUCT SET image_url = {p} WHERE product_code = {p}", (img_url, code))

    # 4. CUSTOMERS (10 Indian customers across major cities)
    cursor.execute("SELECT COUNT(*) FROM CUSTOMER")
    if cursor.fetchone()[0] == 0:
        customers = [
            ('Aarav Sharma', '+91 98200 11223', 'aarav.sharma@gmail.com', 'Mumbai', 'Flat 402, Sea Green Apts, Worli, Mumbai, Maharashtra'),
            ('Priya Patel', '+91 98980 22334', 'priya.patel@yahoo.co.in', 'Ahmedabad', 'B-12, Shivalik Residency, Satellite, Ahmedabad, Gujarat'),
            ('Rajesh Iyer', '+91 98400 33445', 'rajesh.iyer@outlook.com', 'Chennai', '15/3, TTK Road, Alwarpet, Chennai, Tamil Nadu'),
            ('Ananya Reddy', '+91 98480 44556', 'ananya.reddy@gmail.com', 'Hyderabad', 'Plot 108, Jubilee Hills, Road No. 36, Hyderabad, Telangana'),
            ('Vikram Malhotra', '+91 98110 55667', 'vikram.m@malhotragroup.in', 'Delhi', 'D-48, Greater Kailash Part 1, New Delhi, Delhi'),
            ('Kavita Sundaram', '+91 98800 66778', 'kavita.sundaram@gmail.com', 'Bengaluru', '24, 100 Feet Road, Indiranagar, Bengaluru, Karnataka'),
            ('Rohan Verma', '+91 98220 77889', 'rohan.verma@techmail.com', 'Pune', 'Tower 3, Magarpatta City, Hadapsar, Pune, Maharashtra'),
            ('Sneha Kulkarni', '+91 98710 88990', 'sneha.k@gmail.com', 'Nagpur', 'Ramdaspeth Central Avenue, Nagpur, Maharashtra'),
            ('Suresh Nair', '+91 98470 99001', 'suresh.nair@cochinlogistics.com', 'Kochi', 'Marine Drive Waterfront, Kochi, Kerala'),
            ('Pooja Gupta', '+91 98300 00112', 'pooja.gupta@kolkatatextiles.in', 'Kolkata', 'Salt Lake Sector V, Kolkata, West Bengal')
        ]
        cursor.executemany(f"""
            INSERT INTO CUSTOMER (customer_name, phone, email, city, address)
            VALUES ({p}, {p}, {p}, {p}, {p})
        """, customers)

    # 5. SUPPLIERS
    cursor.execute("SELECT COUNT(*) FROM SUPPLIER")
    if cursor.fetchone()[0] == 0:
        suppliers = [
            ('Samsung India Electronics Pvt Ltd', 'Manish Agarwal', '+91 (0124) 488-1000', 'b2b.order@samsung.com', '07AAACS8577K1Z0', 'Gurugram', 'Two Horizon Center, DLF Phase 5, Gurugram, Haryana'),
            ('Apple Distribution International', 'Sunil Mehta', '+91 (080) 4045-5000', 'india_orders@apple.com', '29AABCA2773N1ZP', 'Bengaluru', 'UB City, Vittal Mallya Road, Bengaluru, Karnataka'),
            ('Ingram Micro India Pvt Ltd', 'Deepak Joshi', '+91 (022) 6858-6000', 'sales@ingrammicro.co.in', '27AAACI1607L1ZR', 'Mumbai', 'Godrej Millennium, Vikhroli West, Mumbai, Maharashtra'),
            ('Redington India Limited', 'Ramesh Chandran', '+91 (044) 4224-3353', 'contact@redingtongroup.com', '33AAACR2946K1Z9', 'Chennai', 'Guindy Industrial Estate, Chennai, Tamil Nadu')
        ]
        cursor.executemany(f"""
            INSERT INTO SUPPLIER (supplier_name, contact_person, phone, email, gstin, city, address)
            VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p})
        """, suppliers)

    # 6. HISTORICAL SALES (14 Days of Invoices: INV-2026-0001 to INV-2026-0016)
    cursor.execute("SELECT COUNT(*) FROM SALE")
    if cursor.fetchone()[0] == 0:
        sales_plan = [
            # day_offset (days before today), cust_id, user_id, inv_num, p_id, qty, serial, pay_method, status
            (13, 1, 3, 'INV-2026-0001', 1, 1, 'SN-SAMS24U-9901A', 'UPI', 'Paid'),
            (12, 2, 2, 'INV-2026-0002', 3, 1, 'SN-REDMI13P-4402B', 'Cash', 'Paid'),
            (11, 3, 3, 'INV-2026-0003', 13, 1, 'SN-SONYXM5-492104', 'Card', 'Paid'),
            (10, 4, 1, 'INV-2026-0004', 8, 1, 'SN-APPL-M2AIR-7704D', 'UPI', 'Paid'),
            (9, 5, 3, 'INV-2026-0005', 2, 1, 'SN-APPL-15PM-8805E', 'Card', 'Paid'),
            (8, 6, 2, 'INV-2026-0006', 16, 1, 'SN-MITV43-1206F', 'UPI', 'Paid'),
            (7, 7, 3, 'INV-2026-0007', 24, 1, 'SN-PS5SLIM-6307G', 'Cash', 'Paid'),
            (6, 8, 3, 'INV-2026-0008', 6, 1, 'SN-HPPAV15-9108H', 'UPI', 'Paid'),
            (5, 9, 2, 'INV-2026-0009', 11, 2, 'SN-BOAT141-8209J', 'UPI', 'Paid'),
            (4, 10, 3, 'INV-2026-0010', 14, 1, 'SN-BOAT1200-5510K', 'Cash', 'Paid'),
            (3, 1, 3, 'INV-2026-0011', 27, 1, 'SN-APPL-W9-3311L', 'Card', 'Paid'),
            (2, 2, 2, 'INV-2026-0012', 4, 1, 'SN-OP12-7812M', 'UPI', 'Paid'),
            (1, 3, 3, 'INV-2026-0013', 17, 1, 'SN-LGOLED55-9013N', 'Card', 'Paid'),
            (0, 4, 3, 'INV-2026-0014', 1, 1, 'SN-SAMS24U-9914P', 'UPI', 'Paid'),
            (0, 5, 2, 'INV-2026-0015', 5, 1, 'SN-IPADAIR-4415Q', 'UPI', 'Paid'),
            (0, 6, 3, 'INV-2026-0016', 7, 1, 'SN-DELL15-6616R', 'Partial', 'Partial')  # Credit / Partial payment
        ]

        for s in sales_plan:
            offset_days, cust_id, u_id, inv_no, p_id, qty, sn, pay_mode, p_status = s
            sale_dt = today - datetime.timedelta(days=offset_days)
            sale_dt_str = f"{sale_dt.strftime('%Y-%m-%d')} 14:30:00"

            # Fetch product price
            cursor.execute("SELECT selling_price, warranty_months FROM PRODUCT WHERE product_id = " + str(p_id))
            row = cursor.fetchone()
            u_price = row[0]
            w_months = row[1]
            subtot = u_price * qty
            tax_val = round(subtot * 0.18, 2)
            cgst = round(tax_val / 2, 2)
            sgst = round(tax_val - cgst, 2)
            gr_total = subtot + tax_val

            amt_paid = gr_total if p_status == 'Paid' else round(gr_total * 0.5, 2)
            bal_due = 0.0 if p_status == 'Paid' else (gr_total - amt_paid)

            cursor.execute(f"""
                INSERT INTO SALE (invoice_number, customer_id, user_id, sale_date, subtotal, cgst_amount, sgst_amount, tax_amount, discount_amount, grand_total, payment_method, payment_status, amount_paid, balance_due, notes)
                VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p})
            """, (inv_no, cust_id, u_id, sale_dt_str, subtot, cgst, sgst, tax_val, 0.0, gr_total, pay_mode, p_status, amt_paid, bal_due, 'Standard retail purchase'))

            sale_id = cursor.lastrowid

            # Calculate warranty expiry
            exp_date = sale_dt + datetime.timedelta(days=w_months * 30)
            exp_str = exp_date.strftime('%Y-%m-%d')

            cursor.execute(f"""
                INSERT INTO SALE_ITEM (sale_id, product_id, quantity, unit_price, total_price, serial_number, warranty_months, warranty_expiry_date)
                VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p}, {p})
            """, (sale_id, p_id, qty, u_price, subtot, sn, w_months, exp_str))

            # Log stock movement
            cursor.execute(f"""
                INSERT INTO STOCK_MOVEMENT (product_id, movement_type, quantity, reason, reference_id, notes, created_at)
                VALUES ({p}, 'OUT', {p}, 'Customer Sale', {p}, 'Sold on invoice', {p})
            """, (p_id, qty, inv_no, sale_dt_str))

            # Deduct stock
            cursor.execute(f"UPDATE PRODUCT SET stock_quantity = stock_quantity - {qty} WHERE product_id = {p_id}")

    # 7. SEED SPECIFIC COHORTS OF WARRANTIES (12+ Active, 6 Expiring Soon, 6+ Expired, 3 Claims)
    # The requirement explicitly specifies:
    # "6+ expiring at APP_TODAY +2, +6, +11, +15, +20, +26 days; 6+ expired (Aug-Oct 2026); 3 open claims."
    cursor.execute("SELECT COUNT(*) FROM SALE_ITEM WHERE serial_number LIKE 'SN-EXP-%' OR serial_number LIKE 'SN-EXPD-%'")
    if cursor.fetchone()[0] == 0:
        # Create a dedicated historical sale for these warranty cohorts
        dummy_sale_date = (today - datetime.timedelta(days=360)).strftime('%Y-%m-%d 10:00:00')
        cursor.execute(f"""
            INSERT INTO SALE (invoice_number, customer_id, user_id, sale_date, subtotal, cgst_amount, sgst_amount, tax_amount, discount_amount, grand_total, payment_method, payment_status, amount_paid, balance_due, notes)
            VALUES ('INV-2025-ARCH01', 1, 1, {p}, 450000.0, 40500.0, 40500.0, 81000.0, 0.0, 531000.0, 'UPI', 'Paid', 531000.0, 0.0, 'Historical warranty seed cohort')
        """, (dummy_sale_date,))
        arch_sale_id = cursor.lastrowid

        # 6 Expiring Soon items with EXACT target dates: +2, +6, +11, +15, +20, +26 days
        expiring_offsets = [2, 6, 11, 15, 20, 26]
        exp_products = [1, 2, 6, 7, 13, 17]
        for i, off in enumerate(expiring_offsets):
            exp_target = today + datetime.timedelta(days=off)
            sn_code = f"SN-EXP-SOON-0{off}D"
            pid = exp_products[i]
            cursor.execute(f"""
                INSERT INTO SALE_ITEM (sale_id, product_id, quantity, unit_price, total_price, serial_number, warranty_months, warranty_expiry_date)
                VALUES ({arch_sale_id}, {pid}, 1, 50000.0, 50000.0, {p}, 12, {p})
            """, (sn_code, exp_target.strftime('%Y-%m-%d')))

        # 6 Expired items (Aug - Oct 2026)
        expired_targets = [
            datetime.date(2026, 8, 15), datetime.date(2026, 8, 28),
            datetime.date(2026, 9, 10), datetime.date(2026, 9, 25),
            datetime.date(2026, 10, 5), datetime.date(2026, 10, 20)
        ]
        for j, exp_d in enumerate(expired_targets):
            sn_code = f"SN-EXPD-2026-{j+1:02d}"
            cursor.execute(f"""
                INSERT INTO SALE_ITEM (sale_id, product_id, quantity, unit_price, total_price, serial_number, warranty_months, warranty_expiry_date)
                VALUES ({arch_sale_id}, 3, 1, 29999.0, 29999.0, {p}, 12, {p})
            """, (sn_code, exp_d.strftime('%Y-%m-%d')))

        # 3 Open Warranty Claims
        claims = [
            ('CLM-2026-001', 'SN-SAMS24U-9901A', 1, 1, (today - datetime.timedelta(days=4)).strftime('%Y-%m-%d'), 'Display vertical flickering line near power button', 'Open'),
            ('CLM-2026-002', 'SN-SONYXM5-492104', 3, 13, (today - datetime.timedelta(days=2)).strftime('%Y-%m-%d'), 'Left earcup ANC whistling noise when Bluetooth connects', 'Open'),
            ('CLM-2026-003', 'SN-APPL-M2AIR-7704D', 4, 8, (today - datetime.timedelta(days=1)).strftime('%Y-%m-%d'), 'Trackpad click haptics intermittently unresponsive', 'Open')
        ]
        cursor.executemany(f"""
            INSERT INTO WARRANTY_CLAIM (claim_number, serial_number, customer_id, product_id, claim_date, issue_description, status)
            VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p})
        """, claims)

    # 8. INITIAL STOCK IN MOVEMENTS (For remaining inventory)
    cursor.execute("SELECT COUNT(*) FROM STOCK_MOVEMENT WHERE reason = 'Initial Seed'")
    if cursor.fetchone()[0] == 0:
        cursor.execute("SELECT product_id, stock_quantity FROM PRODUCT")
        p_rows = cursor.fetchall()
        for pr in p_rows:
            cursor.execute(f"""
                INSERT INTO STOCK_MOVEMENT (product_id, movement_type, quantity, reason, reference_id, notes, created_at)
                VALUES ({p}, 'IN', {p}, 'Initial Seed', 'PO-INIT-2026', 'Opening stock allotment', {p})
            """, (pr[0], pr[1], f"{today.strftime('%Y-%m-%d')} 09:00:00"))

    # 9. PURCHASE ORDERS & QUOTATIONS (Operations)
    cursor.execute("SELECT COUNT(*) FROM PURCHASE_ORDER")
    if cursor.fetchone()[0] == 0:
        po_date = (today - datetime.timedelta(days=3)).strftime('%Y-%m-%d')
        cursor.execute(f"""
            INSERT INTO PURCHASE_ORDER (po_number, supplier_id, order_date, expected_date, status, total_amount, notes)
            VALUES ('PO-2026-001', 1, {p}, {p}, 'Sent', 540000.0, 'Restock Samsung Galaxy S24 Ultra batch')
        """, (po_date, today.strftime('%Y-%m-%d')))
        po_id = cursor.lastrowid
        cursor.execute(f"""
            INSERT INTO PURCHASE_ORDER_ITEM (po_id, product_id, quantity_ordered, quantity_received, unit_cost, total_cost)
            VALUES ({po_id}, 1, 5, 0, 108000.0, 540000.0)
        """)

    cursor.execute("SELECT COUNT(*) FROM QUOTATION")
    if cursor.fetchone()[0] == 0:
        q_date = (today - datetime.timedelta(days=2)).strftime('%Y-%m-%d')
        q_exp = (today + datetime.timedelta(days=12)).strftime('%Y-%m-%d')
        cursor.execute(f"""
            INSERT INTO QUOTATION (quote_number, customer_id, quote_date, expiry_date, subtotal, tax_amount, discount_amount, grand_total, status, notes)
            VALUES ('QT-2026-001', 4, {p}, {p}, 229990.0, 41398.2, 0.0, 271388.2, 'Draft', 'Executive smart display setup quotation')
        """, (q_date, q_exp))
        qid = cursor.lastrowid
        cursor.execute(f"""
            INSERT INTO QUOTATION_ITEM (quote_id, product_id, quantity, unit_price, total_price)
            VALUES ({qid}, 18, 1, 159990.0, 159990.0), ({qid}, 4, 1, 70000.0, 70000.0)
        """)

    # 10. REPAIR TICKETS
    cursor.execute("SELECT COUNT(*) FROM REPAIR_TICKET")
    if cursor.fetchone()[0] == 0:
        t_date = (today - datetime.timedelta(days=2)).strftime('%Y-%m-%d %H:%M:%S')
        tickets = [
            ('TCK-2026-001', 1, 1, 'Samsung Galaxy S24 Ultra', 'SN-SAMS24U-9901A', 'Display replacement under warranty', 'Ganesh (Lead Tech)', 18000.0, 0.0, 'Diagnosing', 'Awaiting OEM display panel', t_date),
            ('TCK-2026-002', 2, 3, 'Sony WH-1000XM5', 'SN-SONYXM5-492104', 'Left driver speaker calibration', 'Ganesh (Lead Tech)', 3500.0, 0.0, 'Repairing', 'Component re-soldering', t_date),
            ('TCK-2026-003', 3, 4, 'MacBook Air 13" M2', 'SN-APPL-M2AIR-7704D', 'Trackpad flex cable realignment', 'Pravin (Apple Specialist)', 4200.0, 0.0, 'Received', 'In transit to lab', t_date)
        ]
        cursor.executemany(f"""
            INSERT INTO REPAIR_TICKET (ticket_number, claim_id, customer_id, product_name, serial_number, issue_description, technician, estimated_cost, actual_cost, status, notes, created_at)
            VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p})
        """, tickets)

    # 11. EXPENSES
    cursor.execute("SELECT COUNT(*) FROM EXPENSE")
    if cursor.fetchone()[0] == 0:
        e_month = today.strftime('%Y-%m')
        expenses = [
            ('Rent', 65000.0, f"{e_month}-01", 'Bank Transfer', 'Retail store premise monthly lease', 'Geetha'),
            ('Salary', 120000.0, f"{e_month}-05", 'Bank Transfer', 'Staff monthly payroll disbursement', 'Geetha'),
            ('Electricity', 18500.0, f"{e_month}-10", 'UPI', 'Showroom air conditioning & display power bill', 'Geetha'),
            ('Internet', 3500.0, f"{e_month}-08", 'UPI', 'High-speed business fiber broadband', 'Ram'),
            ('Maintenance', 6000.0, f"{e_month}-12", 'Cash', 'Store lighting and AC duct maintenance', 'Sai')
        ]
        cursor.executemany(f"""
            INSERT INTO EXPENSE (category, amount, expense_date, payment_method, notes, created_by)
            VALUES ({p}, {p}, {p}, {p}, {p}, {p})
        """, expenses)

    # 12. STORE SETTINGS
    cursor.execute("SELECT COUNT(*) FROM STORE_SETTING")
    if cursor.fetchone()[0] == 0:
        settings = [
            ('app_today', today.strftime('%Y-%m-%d')),
            ('store_name', config.STORE_NAME),
            ('store_tagline', config.STORE_TAGLINE),
            ('store_address', config.STORE_ADDRESS),
            ('store_phone', config.STORE_PHONE),
            ('store_email', config.STORE_EMAIL),
            ('store_tax_id', config.STORE_TAX_ID),
            ('default_tax_rate', '18.0'),
            ('cgst_rate', '9.0'),
            ('sgst_rate', '9.0'),
            ('low_stock_threshold', '5'),
            ('invoice_prefix', 'INV-'),
            ('invoice_next_number', '1017'),
            ('emi_rate_3m', '0.0'),
            ('emi_rate_6m', '12.0'),
            ('emi_rate_9m', '14.0'),
            ('theme', 'light'),
            ('offers_banner', 'Festival Special: Up to 15% Off with Code FESTIVE10 + No Cost EMI on HDFC & ICICI Cards!')
        ]
        cursor.executemany(f"""
            INSERT INTO STORE_SETTING (setting_key, setting_value)
            VALUES ({p}, {p})
        """, settings)


def init_sqlite_db():
    """Initializes and seeds the SQLite database with foreign keys enabled."""
    conn = sqlite3.connect(config.SQLITE_DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    cursor = conn.cursor()
    cursor.executescript(SQLITE_SCHEMA)
    seed_database(cursor, is_mysql=False)
    conn.commit()
    conn.close()
    print(f"SQLite database initialized and seeded at: {config.SQLITE_DB_PATH}")


def init_mysql_db():
    """Initializes and seeds MySQL database if available."""
    if not PYMYSQL_AVAILABLE:
        print("pymysql not installed. Skipping MySQL initialization.")
        return False
    try:
        conn = pymysql.connect(
            host=config.MYSQL_HOST,
            port=config.MYSQL_PORT,
            user=config.MYSQL_USER,
            password=config.MYSQL_PASSWORD,
            charset='utf8mb4'
        )
        cursor = conn.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {config.MYSQL_DB} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
        cursor.execute(f"USE {config.MYSQL_DB};")

        schema_path = os.path.join(config.BASE_DIR, 'schema_mysql.sql')
        if os.path.exists(schema_path):
            with open(schema_path, 'r', encoding='utf-8') as f:
                sql_commands = f.read().split(';')
                for cmd in sql_commands:
                    cmd_clean = cmd.strip()
                    if cmd_clean and not cmd_clean.startswith('--'):
                        cursor.execute(cmd_clean)

        seed_database(cursor, is_mysql=True)
        conn.commit()
        conn.close()
        print(f"MySQL database '{config.MYSQL_DB}' successfully initialized and seeded.")
        return True
    except Exception as e:
        print(f"MySQL initialization failed ({e}). Falling back to SQLite.")
        return False


def ensure_db_initialized():
    """Idempotent initialization check."""
    init_sqlite_db()


if __name__ == '__main__':
    use_mysql = '--mysql' in sys.argv or config.DB_TYPE == 'mysql'
    if use_mysql:
        success = init_mysql_db()
        if not success:
            init_sqlite_db()
    else:
        init_sqlite_db()
