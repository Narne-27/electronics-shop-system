-- Electrodesk - Electronics Shop Management System
-- Comprehensive Relational Database Schema (MySQL 8.0+ compatible)

CREATE DATABASE IF NOT EXISTS electrodesk_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE electrodesk_db;

-- 1. USER: Staff & Administrative Accounts
CREATE TABLE IF NOT EXISTS USER (
    user_id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(100) NOT NULL,
    role ENUM('System Administrator', 'Shop Owner', 'Shop Manager', 'Sales Staff', 'Admin', 'Manager') NOT NULL DEFAULT 'Sales Staff',
    avatar VARCHAR(10) NOT NULL DEFAULT 'ED',
    email VARCHAR(100),
    phone VARCHAR(30),
    status ENUM('Active', 'Inactive') NOT NULL DEFAULT 'Active',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- 2. CATEGORY: Electronics Department Taxonomies
CREATE TABLE IF NOT EXISTS CATEGORY (
    category_id INT AUTO_INCREMENT PRIMARY KEY,
    category_code VARCHAR(20) NOT NULL UNIQUE,
    category_name VARCHAR(100) NOT NULL UNIQUE,
    icon VARCHAR(50) DEFAULT 'bi-grid-fill',
    description TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- 3. PRODUCT: Electronics Inventory & Hardware Items
CREATE TABLE IF NOT EXISTS PRODUCT (
    product_id INT AUTO_INCREMENT PRIMARY KEY,
    product_code VARCHAR(50) NOT NULL UNIQUE,
    product_name VARCHAR(150) NOT NULL,
    category_id INT NOT NULL,
    brand VARCHAR(80) NOT NULL,
    model VARCHAR(100),
    hsn_code VARCHAR(20) DEFAULT '8517',
    tagline VARCHAR(255),
    image_url VARCHAR(255) DEFAULT '/static/images/logo.svg',
    is_new TINYINT(1) DEFAULT 0,
    cost_price DECIMAL(12, 2) NOT NULL DEFAULT 0.00,
    selling_price DECIMAL(12, 2) NOT NULL DEFAULT 0.00,
    tax_rate DECIMAL(5, 2) NOT NULL DEFAULT 18.00,
    stock_quantity INT NOT NULL DEFAULT 0,
    reorder_level INT NOT NULL DEFAULT 5,
    warranty_months INT NOT NULL DEFAULT 12,
    description TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (category_id) REFERENCES CATEGORY(category_id) ON UPDATE CASCADE
) ENGINE=InnoDB;

-- 4. CUSTOMER: Customer CRM Directory
CREATE TABLE IF NOT EXISTS CUSTOMER (
    customer_id INT AUTO_INCREMENT PRIMARY KEY,
    customer_name VARCHAR(120) NOT NULL,
    phone VARCHAR(30) NOT NULL UNIQUE,
    email VARCHAR(100),
    city VARCHAR(80) DEFAULT 'Hyderabad',
    address TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- 5. SALE: Invoices & Checkout Transactions
CREATE TABLE IF NOT EXISTS SALE (
    sale_id INT AUTO_INCREMENT PRIMARY KEY,
    invoice_number VARCHAR(50) NOT NULL UNIQUE,
    customer_id INT,
    user_id INT NOT NULL,
    sale_date DATETIME NOT NULL,
    subtotal DECIMAL(12, 2) NOT NULL DEFAULT 0.00,
    cgst_amount DECIMAL(12, 2) NOT NULL DEFAULT 0.00,
    sgst_amount DECIMAL(12, 2) NOT NULL DEFAULT 0.00,
    tax_amount DECIMAL(12, 2) NOT NULL DEFAULT 0.00,
    discount_amount DECIMAL(12, 2) NOT NULL DEFAULT 0.00,
    discount_type VARCHAR(20) DEFAULT 'none',
    discount_rate DECIMAL(5, 2) DEFAULT 0.00,
    owner_approved TINYINT(1) DEFAULT 0,
    exchange_device VARCHAR(150),
    exchange_value DECIMAL(12, 2) DEFAULT 0.00,
    grand_total DECIMAL(12, 2) NOT NULL DEFAULT 0.00,
    payment_method VARCHAR(30) NOT NULL DEFAULT 'Cash',
    payment_status VARCHAR(20) NOT NULL DEFAULT 'Paid',
    amount_paid DECIMAL(12, 2) NOT NULL DEFAULT 0.00,
    balance_due DECIMAL(12, 2) NOT NULL DEFAULT 0.00,
    emi_months INT DEFAULT 0,
    emi_interest_rate DECIMAL(5, 2) DEFAULT 0.00,
    emi_monthly_amount DECIMAL(12, 2) DEFAULT 0.00,
    notes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (customer_id) REFERENCES CUSTOMER(customer_id) ON DELETE SET NULL,
    FOREIGN KEY (user_id) REFERENCES USER(user_id)
) ENGINE=InnoDB;

-- 6. SALE_ITEM: Line-Item Details & Hardware Warranty Records
CREATE TABLE IF NOT EXISTS SALE_ITEM (
    item_id INT AUTO_INCREMENT PRIMARY KEY,
    sale_id INT NOT NULL,
    product_id INT NOT NULL,
    quantity INT NOT NULL DEFAULT 1,
    unit_price DECIMAL(12, 2) NOT NULL DEFAULT 0.00,
    total_price DECIMAL(12, 2) NOT NULL DEFAULT 0.00,
    serial_number VARCHAR(100),
    warranty_months INT DEFAULT 12,
    warranty_expiry_date DATE,
    FOREIGN KEY (sale_id) REFERENCES SALE(sale_id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES PRODUCT(product_id)
) ENGINE=InnoDB;

-- 7. STOCK_MOVEMENT: Inventory In/Out Audit Trail
CREATE TABLE IF NOT EXISTS STOCK_MOVEMENT (
    movement_id INT AUTO_INCREMENT PRIMARY KEY,
    product_id INT NOT NULL,
    movement_type VARCHAR(10) NOT NULL, -- 'IN' or 'OUT'
    quantity INT NOT NULL,
    reason VARCHAR(100) NOT NULL,       -- 'Initial Seed', 'Customer Sale', 'Customer Return', 'Supplier PO', 'Damaged', 'Physical Audit'
    reference_id VARCHAR(50),          -- Invoice # or PO #
    notes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id) REFERENCES PRODUCT(product_id)
) ENGINE=InnoDB;

-- 8. WARRANTY_CLAIM: Service Center Claims on Warranties
CREATE TABLE IF NOT EXISTS WARRANTY_CLAIM (
    claim_id INT AUTO_INCREMENT PRIMARY KEY,
    claim_number VARCHAR(50) NOT NULL UNIQUE,
    item_id INT,
    serial_number VARCHAR(100) NOT NULL,
    customer_id INT,
    product_id INT,
    claim_date DATE NOT NULL,
    issue_description TEXT NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'Open', -- 'Open', 'In Progress', 'Resolved', 'Rejected'
    resolution_notes TEXT,
    resolved_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (customer_id) REFERENCES CUSTOMER(customer_id)
) ENGINE=InnoDB;

-- 9. CREDIT_NOTE: Return & Refund Records
CREATE TABLE IF NOT EXISTS CREDIT_NOTE (
    credit_note_id INT AUTO_INCREMENT PRIMARY KEY,
    credit_note_number VARCHAR(50) NOT NULL UNIQUE,
    sale_id INT NOT NULL,
    customer_id INT,
    refund_amount DECIMAL(12, 2) NOT NULL,
    reason TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sale_id) REFERENCES SALE(sale_id)
) ENGINE=InnoDB;

-- 10. CUSTOMER_PAYMENT: Ledger Payment Receipts for Partial/Credit Sales
CREATE TABLE IF NOT EXISTS CUSTOMER_PAYMENT (
    payment_id INT AUTO_INCREMENT PRIMARY KEY,
    customer_id INT NOT NULL,
    sale_id INT,
    payment_date DATETIME NOT NULL,
    amount DECIMAL(12, 2) NOT NULL,
    payment_method VARCHAR(30) NOT NULL DEFAULT 'Cash',
    notes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (customer_id) REFERENCES CUSTOMER(customer_id)
) ENGINE=InnoDB;

-- 11. SUPPLIER: Vendor Directory
CREATE TABLE IF NOT EXISTS SUPPLIER (
    supplier_id INT AUTO_INCREMENT PRIMARY KEY,
    supplier_name VARCHAR(150) NOT NULL,
    contact_person VARCHAR(100),
    phone VARCHAR(30),
    email VARCHAR(100),
    gstin VARCHAR(30),
    city VARCHAR(80),
    address TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- 12. PURCHASE_ORDER: Vendor POs & Restocking
CREATE TABLE IF NOT EXISTS PURCHASE_ORDER (
    po_id INT AUTO_INCREMENT PRIMARY KEY,
    po_number VARCHAR(50) NOT NULL UNIQUE,
    supplier_id INT NOT NULL,
    order_date DATE NOT NULL,
    expected_date DATE,
    status VARCHAR(30) NOT NULL DEFAULT 'Draft', -- 'Draft', 'Sent', 'Received', 'Cancelled'
    total_amount DECIMAL(12, 2) NOT NULL DEFAULT 0.00,
    notes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (supplier_id) REFERENCES SUPPLIER(supplier_id)
) ENGINE=InnoDB;

-- 13. PURCHASE_ORDER_ITEM: Items in Purchase Order
CREATE TABLE IF NOT EXISTS PURCHASE_ORDER_ITEM (
    po_item_id INT AUTO_INCREMENT PRIMARY KEY,
    po_id INT NOT NULL,
    product_id INT NOT NULL,
    quantity_ordered INT NOT NULL,
    quantity_received INT NOT NULL DEFAULT 0,
    unit_cost DECIMAL(12, 2) NOT NULL,
    total_cost DECIMAL(12, 2) NOT NULL,
    FOREIGN KEY (po_id) REFERENCES PURCHASE_ORDER(po_id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES PRODUCT(product_id)
) ENGINE=InnoDB;

-- 14. QUOTATION: Customer Estimates
CREATE TABLE IF NOT EXISTS QUOTATION (
    quote_id INT AUTO_INCREMENT PRIMARY KEY,
    quote_number VARCHAR(50) NOT NULL UNIQUE,
    customer_id INT,
    quote_date DATE NOT NULL,
    expiry_date DATE NOT NULL,
    subtotal DECIMAL(12, 2) NOT NULL,
    tax_amount DECIMAL(12, 2) NOT NULL,
    discount_amount DECIMAL(12, 2) DEFAULT 0.00,
    grand_total DECIMAL(12, 2) NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'Draft', -- 'Draft', 'Sent', 'Converted', 'Expired'
    notes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (customer_id) REFERENCES CUSTOMER(customer_id)
) ENGINE=InnoDB;

-- 15. QUOTATION_ITEM: Items in Quotation
CREATE TABLE IF NOT EXISTS QUOTATION_ITEM (
    quote_item_id INT AUTO_INCREMENT PRIMARY KEY,
    quote_id INT NOT NULL,
    product_id INT NOT NULL,
    quantity INT NOT NULL,
    unit_price DECIMAL(12, 2) NOT NULL,
    total_price DECIMAL(12, 2) NOT NULL,
    FOREIGN KEY (quote_id) REFERENCES QUOTATION(quote_id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES PRODUCT(product_id)
) ENGINE=InnoDB;

-- 16. REPAIR_TICKET: Device Servicing & Warranty Repairs
CREATE TABLE IF NOT EXISTS REPAIR_TICKET (
    ticket_id INT AUTO_INCREMENT PRIMARY KEY,
    ticket_number VARCHAR(50) NOT NULL UNIQUE,
    claim_id INT,
    customer_id INT,
    product_name VARCHAR(150) NOT NULL,
    serial_number VARCHAR(100),
    issue_description TEXT NOT NULL,
    technician VARCHAR(100),
    estimated_cost DECIMAL(12, 2) DEFAULT 0.00,
    actual_cost DECIMAL(12, 2) DEFAULT 0.00,
    status VARCHAR(30) NOT NULL DEFAULT 'Received', -- 'Received', 'Diagnosing', 'Repairing', 'Ready', 'Delivered'
    notes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (customer_id) REFERENCES CUSTOMER(customer_id)
) ENGINE=InnoDB;

-- 17. EXPENSE: Operational Shop Expenses
CREATE TABLE IF NOT EXISTS EXPENSE (
    expense_id INT AUTO_INCREMENT PRIMARY KEY,
    category VARCHAR(50) NOT NULL, -- 'Rent', 'Salary', 'Electricity', 'Marketing', 'Maintenance', 'Internet', 'Other'
    amount DECIMAL(12, 2) NOT NULL,
    expense_date DATE NOT NULL,
    payment_method VARCHAR(30) NOT NULL DEFAULT 'Bank Transfer',
    notes TEXT,
    created_by VARCHAR(100),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- 18. DAILY_CLOSING: Daily Cash & Drawer Reconciliation
CREATE TABLE IF NOT EXISTS DAILY_CLOSING (
    closing_id INT AUTO_INCREMENT PRIMARY KEY,
    closing_date DATE NOT NULL UNIQUE,
    expected_cash DECIMAL(12, 2) NOT NULL DEFAULT 0.00,
    actual_cash DECIMAL(12, 2) NOT NULL DEFAULT 0.00,
    expected_upi DECIMAL(12, 2) NOT NULL DEFAULT 0.00,
    expected_card DECIMAL(12, 2) NOT NULL DEFAULT 0.00,
    expected_total DECIMAL(12, 2) NOT NULL DEFAULT 0.00,
    cash_difference DECIMAL(12, 2) NOT NULL DEFAULT 0.00,
    notes TEXT,
    closed_by VARCHAR(100),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- 19. AUDIT_LOG: Administrative Event Logging
CREATE TABLE IF NOT EXISTS AUDIT_LOG (
    log_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    username VARCHAR(50),
    action VARCHAR(50) NOT NULL,
    module VARCHAR(50) NOT NULL,
    details TEXT,
    ip_address VARCHAR(50),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- 20. STORE_SETTING: Key-Value Dynamic Settings Overrides
CREATE TABLE IF NOT EXISTS STORE_SETTING (
    setting_key VARCHAR(50) PRIMARY KEY,
    setting_value TEXT NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- 21. DELIVERY_ORDER: Delivery & Logistics Management
CREATE TABLE IF NOT EXISTS DELIVERY_ORDER (
    delivery_id INT AUTO_INCREMENT PRIMARY KEY,
    delivery_number VARCHAR(30) NOT NULL UNIQUE,
    sale_id INT NOT NULL,
    customer_id INT NULL,
    recipient_name VARCHAR(100) NOT NULL,
    recipient_phone VARCHAR(20) NOT NULL,
    delivery_address TEXT NOT NULL,
    delivery_charges DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
    expected_date DATE NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'Pending',
    assigned_to INT NULL,
    tracking_notes TEXT NULL,
    delivered_at DATETIME NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_del_sale (sale_id),
    INDEX idx_del_customer (customer_id),
    INDEX idx_del_status (status),
    INDEX idx_del_assigned (assigned_to),
    CONSTRAINT fk_del_sale FOREIGN KEY (sale_id) REFERENCES SALE(sale_id) ON DELETE CASCADE,
    CONSTRAINT fk_del_customer FOREIGN KEY (customer_id) REFERENCES CUSTOMER(customer_id) ON DELETE SET NULL,
    CONSTRAINT fk_del_assigned FOREIGN KEY (assigned_to) REFERENCES USER(user_id) ON DELETE SET NULL
) ENGINE=InnoDB;

-- 22. DELIVERY_LOG: Delivery History and Audit Timeline
CREATE TABLE IF NOT EXISTS DELIVERY_LOG (
    log_id INT AUTO_INCREMENT PRIMARY KEY,
    delivery_id INT NOT NULL,
    status VARCHAR(30) NOT NULL,
    updated_by INT NULL,
    remarks TEXT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_dellog_delivery (delivery_id),
    CONSTRAINT fk_dellog_delivery FOREIGN KEY (delivery_id) REFERENCES DELIVERY_ORDER(delivery_id) ON DELETE CASCADE,
    CONSTRAINT fk_dellog_user FOREIGN KEY (updated_by) REFERENCES USER(user_id) ON DELETE SET NULL
) ENGINE=InnoDB;

