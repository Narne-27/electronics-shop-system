-- ==========================================================
-- Electrodesk - Electronics Shop Management System
-- MySQL Database Schema
-- Six Tables: USER, CATEGORY, PRODUCT, CUSTOMER, SALE, SALE_ITEM
-- ==========================================================

CREATE DATABASE IF NOT EXISTS electrodesk_db;
USE electrodesk_db;

-- 1. USER Table (Roles: System Administrator, Shop Manager, Sales Staff, Shop Owner)
CREATE TABLE IF NOT EXISTS `USER` (
    `user_id` INT AUTO_INCREMENT PRIMARY KEY,
    `username` VARCHAR(50) NOT NULL UNIQUE,
    `password_hash` VARCHAR(255) NOT NULL,
    `full_name` VARCHAR(100) NOT NULL,
    `role` VARCHAR(50) NOT NULL DEFAULT 'Sales Staff',
    `avatar` VARCHAR(10) NOT NULL DEFAULT 'U',
    `email` VARCHAR(100),
    `phone` VARCHAR(20),
    `status` VARCHAR(20) NOT NULL DEFAULT 'Active',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 2. CATEGORY Table
CREATE TABLE IF NOT EXISTS `CATEGORY` (
    `category_id` INT AUTO_INCREMENT PRIMARY KEY,
    `category_code` VARCHAR(20) NOT NULL UNIQUE,
    `category_name` VARCHAR(100) NOT NULL UNIQUE,
    `description` TEXT,
    `icon` VARCHAR(50) DEFAULT 'bi-box-seam',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 3. PRODUCT Table
CREATE TABLE IF NOT EXISTS `PRODUCT` (
    `product_id` INT AUTO_INCREMENT PRIMARY KEY,
    `product_code` VARCHAR(50) NOT NULL UNIQUE,
    `product_name` VARCHAR(150) NOT NULL,
    `category_id` INT NOT NULL,
    `brand` VARCHAR(80) NOT NULL,
    `model` VARCHAR(80),
    `cost_price` DECIMAL(12, 2) NOT NULL DEFAULT 0.00,
    `selling_price` DECIMAL(12, 2) NOT NULL DEFAULT 0.00,
    `stock_quantity` INT NOT NULL DEFAULT 0,
    `reorder_level` INT NOT NULL DEFAULT 5,
    `warranty_months` INT NOT NULL DEFAULT 12,
    `description` TEXT,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT `fk_product_category` FOREIGN KEY (`category_id`) REFERENCES `CATEGORY` (`category_id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 4. CUSTOMER Table
CREATE TABLE IF NOT EXISTS `CUSTOMER` (
    `customer_id` INT AUTO_INCREMENT PRIMARY KEY,
    `customer_name` VARCHAR(100) NOT NULL,
    `phone` VARCHAR(20) NOT NULL,
    `email` VARCHAR(100),
    `address` TEXT,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 5. SALE Table
CREATE TABLE IF NOT EXISTS `SALE` (
    `sale_id` INT AUTO_INCREMENT PRIMARY KEY,
    `invoice_number` VARCHAR(50) NOT NULL UNIQUE,
    `customer_id` INT,
    `user_id` INT NOT NULL,
    `sale_date` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `subtotal` DECIMAL(12, 2) NOT NULL DEFAULT 0.00,
    `cgst_amount` DECIMAL(12, 2) NOT NULL DEFAULT 0.00,
    `sgst_amount` DECIMAL(12, 2) NOT NULL DEFAULT 0.00,
    `tax_amount` DECIMAL(12, 2) NOT NULL DEFAULT 0.00,
    `discount_amount` DECIMAL(12, 2) NOT NULL DEFAULT 0.00,
    `grand_total` DECIMAL(12, 2) NOT NULL DEFAULT 0.00,
    `payment_method` VARCHAR(30) NOT NULL DEFAULT 'Cash',
    `payment_status` VARCHAR(20) NOT NULL DEFAULT 'Paid',
    `notes` TEXT,
    CONSTRAINT `fk_sale_customer` FOREIGN KEY (`customer_id`) REFERENCES `CUSTOMER` (`customer_id`) ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT `fk_sale_user` FOREIGN KEY (`user_id`) REFERENCES `USER` (`user_id`) ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 6. SALE_ITEM Table
CREATE TABLE IF NOT EXISTS `SALE_ITEM` (
    `item_id` INT AUTO_INCREMENT PRIMARY KEY,
    `sale_id` INT NOT NULL,
    `product_id` INT NOT NULL,
    `quantity` INT NOT NULL DEFAULT 1,
    `unit_price` DECIMAL(12, 2) NOT NULL DEFAULT 0.00,
    `total_price` DECIMAL(12, 2) NOT NULL DEFAULT 0.00,
    `serial_number` VARCHAR(100),
    `warranty_expiry_date` DATE,
    CONSTRAINT `fk_item_sale` FOREIGN KEY (`sale_id`) REFERENCES `SALE` (`sale_id`) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT `fk_item_product` FOREIGN KEY (`product_id`) REFERENCES `PRODUCT` (`product_id`) ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Indexes for performance
CREATE INDEX `idx_product_category` ON `PRODUCT`(`category_id`);
CREATE INDEX `idx_product_stock` ON `PRODUCT`(`stock_quantity`);
CREATE INDEX `idx_sale_customer` ON `SALE`(`customer_id`);
CREATE INDEX `idx_sale_user` ON `SALE`(`user_id`);
CREATE INDEX `idx_sale_date` ON `SALE`(`sale_date`);
CREATE INDEX `idx_sale_item_sale` ON `SALE_ITEM`(`sale_id`);
CREATE INDEX `idx_sale_item_product` ON `SALE_ITEM`(`product_id`);
CREATE INDEX `idx_sale_item_warranty` ON `SALE_ITEM`(`warranty_expiry_date`);
