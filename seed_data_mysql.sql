-- ==========================================================
-- Electrodesk - Electronics Shop Management System
-- Sample Data Script (Renamed Users, INR Currency, GST 18%)
-- ==========================================================

USE electrodesk_db;

-- 1. Insert Renamed Users (Ram, Geetha, Sai, Suresh)
-- Passwords:
-- admin (Ram): admin123
-- geetha (Geetha): geetha123
-- sai (Sai): sai123
-- suresh (Suresh): suresh123
INSERT INTO `USER` (`user_id`, `username`, `password_hash`, `full_name`, `role`, `avatar`, `email`, `phone`, `status`, `created_at`) VALUES
(1, 'admin', 'scrypt:32768:8:1$IA0oYTMQNkVj50vR$2796960e7d115085ac75a626e75f7d00e602d1a312b532e4598484aa122244fa0982c1c189281b7a974c2ca6c0aa5cf3eb02d52d859f9d2cebd7a16d9b1ec7aa', 'Ram', 'System Administrator', 'RA', 'ram@electrodesk.in', '+91 98480 11001', 'Active', '2026-01-10 09:00:00'),
(2, 'geetha', 'scrypt:32768:8:1$1P5LzTWVuR725ipD$87daee26f70f1c7da4d9c5984c8e66065165562d3359634db5cfe507c3c38a9ecbd0475e861d2ce685e1ec8ac9baf8d1bdcea9c365eb83f8b9be7085089aab76', 'Geetha', 'Shop Manager', 'GE', 'geetha@electrodesk.in', '+91 98480 11002', 'Active', '2026-01-15 10:30:00'),
(3, 'sai', 'scrypt:32768:8:1$U6XrGNVGgb90K6Xs$8664ca5fac1e3c017fc4b88786318f9a3e03c43093bb1858256e95b6f035d003ed2a0a5d3e8ae1d8b18373b7248b0ad6646b52ec583045dc9d1cbfe99685f78c', 'Sai', 'Sales Staff', 'SA', 'sai@electrodesk.in', '+91 98480 11003', 'Active', '2026-02-01 11:00:00'),
(4, 'suresh', 'scrypt:32768:8:1$d4Yy5IyugOPxSe7a$bc50f6d19c4a6320b5cf3db590a486ec1103b3febf68028fb4fc7cdc519fc746e02d3e67ff554f7f87a2bf986651d9159b1fd4ad59d63f3538eae1c7b14dd6f9', 'Suresh', 'Shop Owner', 'S', 'suresh@electrodesk.in', '+91 98480 11004', 'Active', '2026-01-01 08:00:00');

-- 2. Insert Categories with Codes and Icons
INSERT INTO `CATEGORY` (`category_id`, `category_code`, `category_name`, `description`, `icon`, `created_at`) VALUES
(1, 'CAT-01', 'Smartphones & Tablets', 'Flagship & budget mobile phones, tablets, e-readers', 'bi-phone-fill', '2026-01-10 09:10:00'),
(2, 'CAT-02', 'Laptops & Computers', 'Ultrabooks, gaming PCs, workstations, desktop peripherals', 'bi-laptop-fill', '2026-01-10 09:12:00'),
(3, 'CAT-03', 'Audio & Sound', 'Noise-cancelling headphones, wireless earbuds, bluetooth soundbars', 'bi-headphones', '2026-01-10 09:14:00'),
(4, 'CAT-04', 'Smart TVs & Displays', '4K OLED/QLED smart TVs, ultra-wide gaming monitors', 'bi-tv-fill', '2026-01-10 09:15:00'),
(5, 'CAT-05', 'Wearables & Fitness', 'Smartwatches, fitness bands, health sensors', 'bi-smartwatch', '2026-01-10 09:16:00'),
(6, 'CAT-06', 'Gaming & Consoles', 'Next-gen consoles, wireless controllers, VR headsets', 'bi-controller', '2026-01-10 09:17:00');

-- 3. Insert Products in INR (Prices formatted in Indian Rupees)
INSERT INTO `PRODUCT` (`product_id`, `product_code`, `product_name`, `category_id`, `brand`, `model`, `cost_price`, `selling_price`, `stock_quantity`, `reorder_level`, `warranty_months`, `description`, `created_at`) VALUES
(1, 'ELEC-SMP-001', 'Galaxy S25 Ultra 512GB', 1, 'Samsung', 'SM-S938B', 98000.00, 129999.00, 18, 5, 24, 'Snapdragon 8 Elite, 200MP Quad Camera, Dynamic AMOLED 2X, S-Pen included', '2026-01-10 10:00:00'),
(2, 'ELEC-SMP-002', 'iPhone 16 Pro Max 256GB', 1, 'Apple', 'A3296', 105000.00, 139900.00, 3, 5, 12, 'A18 Pro chip, Grade 5 Titanium finish, 48MP Fusion camera system (LOW STOCK ALERT)', '2026-01-10 10:05:00'),
(3, 'ELEC-SMP-003', 'Pixel 9 Pro 128GB', 1, 'Google', 'GZC4K', 65000.00, 89999.00, 12, 4, 24, 'Google Tensor G4, Super Actua display, Pro triple camera with Gemini AI', '2026-01-10 10:10:00'),
(4, 'ELEC-LPT-001', 'MacBook Pro 16" M4 Max', 2, 'Apple', 'MUW63LL/A', 260000.00, 319900.00, 7, 3, 12, '16-core CPU, 40-core GPU, 36GB Unified Memory, 1TB SSD Liquid Retina XDR', '2026-01-10 10:20:00'),
(5, 'ELEC-LPT-002', 'Dell XPS 15 OLED Core Ultra 9', 2, 'Dell', '9530-U9', 175000.00, 224999.00, 2, 4, 24, 'Intel Core Ultra 9, 32GB DDR5, RTX 4070 8GB, 3.5K OLED Touch (CRITICAL LOW STOCK)', '2026-01-10 10:25:00'),
(6, 'ELEC-LPT-003', 'ASUS ROG Zephyrus G16', 2, 'ASUS', 'GU605MY', 190000.00, 249999.00, 9, 3, 24, 'AMD Ryzen 9, NVIDIA RTX 4080 12GB, 240Hz ROG Nebula OLED display', '2026-01-10 10:30:00'),
(7, 'ELEC-AUD-001', 'WH-1000XM5 Wireless Headphones', 3, 'Sony', 'WH1000XM5/B', 22000.00, 29990.00, 25, 6, 12, 'Industry Leading Noise Cancellation, 30-hour battery, Auto NC Optimizer', '2026-01-10 10:35:00'),
(8, 'ELEC-AUD-002', 'AirPods Pro 2 USB-C', 3, 'Apple', 'MTJV3AM/A', 18000.00, 24900.00, 4, 8, 12, 'Active Noise Cancellation, Adaptive Audio, MagSafe Charging Case (LOW STOCK)', '2026-01-10 10:40:00'),
(9, 'ELEC-AUD-003', 'Bose QuietComfort Ultra Earbuds', 3, 'Bose', '882826-0010', 21000.00, 27900.00, 14, 5, 12, 'Spatial Audio, CustomTune technology, 24-hour total listening time', '2026-01-10 10:45:00'),
(10, 'ELEC-DTV-001', 'LG 65" G4 Series OLED evo 4K', 4, 'LG', 'OLED65G4SUB', 170000.00, 229990.00, 6, 2, 36, 'Alpha 11 AI Processor 4K, Brightness Booster Max, One Wall Design, 144Hz', '2026-01-10 10:50:00'),
(11, 'ELEC-DTV-002', 'Samsung 55" The Frame QLED 4K', 4, 'Samsung', 'QN55LS03D', 85000.00, 119990.00, 8, 3, 24, 'Matte Display, Art Mode, Slim-fit Wall Mount included, Pantone Validated', '2026-01-10 10:55:00'),
(12, 'ELEC-WRB-001', 'Apple Watch Ultra 2 Black Titanium', 5, 'Apple', 'MX403LL/A', 65000.00, 89900.00, 11, 4, 12, '49mm titanium case, Precision dual-frequency GPS, up to 72 hours in Low Power Mode', '2026-01-10 11:00:00'),
(13, 'ELEC-WRB-002', 'Galaxy Watch Ultra LTE', 5, 'Samsung', 'SM-L705U', 42000.00, 59999.00, 1, 3, 12, 'Cushion design, Dual-frequency GPS, Energy Score, 10ATM Water resistance (CRITICAL LOW)', '2026-01-10 11:05:00'),
(14, 'ELEC-GAM-001', 'PlayStation 5 Pro 2TB', 6, 'Sony', 'CFI-7019B', 55000.00, 69990.00, 15, 5, 12, 'PlayStation Spectral Super Resolution (PSSR), Advanced Ray Tracing, 2TB SSD', '2026-01-10 11:10:00'),
(15, 'ELEC-GAM-002', 'Xbox Series X 1TB Digital', 6, 'Microsoft', 'RRT-00049', 40000.00, 49990.00, 0, 4, 12, '12 teraflops GPU processing power, 4K gaming, Quick Resume (OUT OF STOCK)', '2026-01-10 11:15:00');

-- 4. Insert Customers in India
INSERT INTO `CUSTOMER` (`customer_id`, `customer_name`, `phone`, `email`, `address`, `created_at`) VALUES
(1, 'Rajesh Sharma', '+91 98201 12345', 'rajesh.sharma@dunder.in', '1725 Nariman Point, Mumbai, MH', '2026-01-12 14:00:00'),
(2, 'Priya Nair', '+91 98450 23456', 'priya.nair@techcorp.in', '404 100 Feet Road, Indiranagar, Bengaluru, KA', '2026-01-18 16:30:00'),
(3, 'Vikram Reddy', '+91 99890 34567', 'vikram.reddy@horizon.in', '88 Road No. 36, Jubilee Hills, Hyderabad, TS', '2026-01-25 11:15:00'),
(4, 'Ananya Patel', '+91 97123 45678', 'ananya.p@aurora.in', '742 SG Highway, Bodakdev, Ahmedabad, GJ', '2026-02-05 13:45:00'),
(5, 'Karthik Iyer', '+91 94440 56789', 'karthik.iyer@chennai.in', '12 2nd Avenue, Anna Nagar, Chennai, TN', '2026-02-14 17:20:00');

-- 5. Insert Past Sales with GST 18% (CGST 9% + SGST 9%)
INSERT INTO `SALE` (`sale_id`, `invoice_number`, `customer_id`, `user_id`, `sale_date`, `subtotal`, `cgst_amount`, `sgst_amount`, `tax_amount`, `discount_amount`, `grand_total`, `payment_method`, `payment_status`, `notes`) VALUES
(1, 'INV-20261101-001', 1, 3, '2026-11-01 14:30:00', 159989.00, 14399.00, 14399.00, 28798.00, 5000.00, 183787.00, 'Card', 'Paid', 'Delivered with free tempered glass'),
(2, 'INV-20261108-002', 2, 3, '2026-11-08 17:15:00', 319900.00, 28791.00, 28791.00, 57582.00, 10000.00, 367482.00, 'UPI', 'Paid', 'Corporate purchase with GST invoice'),
(3, 'INV-20261112-003', 3, 2, '2026-11-12 12:45:00', 99980.00, 8998.00, 8998.00, 17996.00, 0.00, 117976.00, 'UPI', 'Paid', 'Paid via QR Code terminal'),
(4, 'INV-20261116-004', 4, 1, '2026-11-16 16:00:00', 229990.00, 20699.00, 20699.00, 41398.00, 8000.00, 263388.00, 'Bank Transfer', 'Paid', 'Express white-glove installation included');

-- 6. Insert Sale Items (with Serial Numbers & calculated warranty expiry dates)
INSERT INTO `SALE_ITEM` (`item_id`, `sale_id`, `product_id`, `quantity`, `unit_price`, `total_price`, `serial_number`, `warranty_expiry_date`) VALUES
(1, 1, 1, 1, 129999.00, 129999.00, 'SN-SAMS25U-884920', '2028-11-01'),
(2, 1, 7, 1, 29990.00, 29990.00, 'SN-SONYXM5-492104', '2027-11-01'),
(3, 2, 4, 1, 319900.00, 319900.00, 'SN-APLM4MX-902144', '2027-11-08'),
(4, 3, 7, 1, 29990.00, 29990.00, 'SN-SONYXM5-773192', '2027-11-12'),
(5, 3, 14, 1, 69990.00, 69990.00, 'SN-SONYPS5-330198', '2027-11-12'),
(6, 4, 10, 1, 229990.00, 229990.00, 'SN-LGOLED65-449102', '2029-11-16');
