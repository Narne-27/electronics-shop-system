-- Electrodesk Sample Seed Data (MySQL 8.0+)
USE electrodesk_db;

-- Users (Ram, Geetha, Sai, Suresh, Vikram)
INSERT IGNORE INTO USER (user_id, username, password_hash, full_name, role, avatar, email, phone, status)
VALUES
(1, 'admin', 'scrypt:32768:8:1$K5b8lRk$e2b5e28a47...', 'Ram', 'System Administrator', 'RA', 'ram.admin@electrodesk.in', '+91 98480 11001', 'Active'),
(2, 'geetha', 'scrypt:32768:8:1$K5b8lRk$e2b5e28a47...', 'Geetha', 'Shop Manager', 'GE', 'geetha.mgr@electrodesk.in', '+91 98480 22002', 'Active'),
(3, 'sai', 'scrypt:32768:8:1$K5b8lRk$e2b5e28a47...', 'Sai', 'Sales Staff', 'SA', 'sai.sales@electrodesk.in', '+91 98480 33003', 'Active'),
(4, 'suresh', 'scrypt:32768:8:1$K5b8lRk$e2b5e28a47...', 'Suresh', 'Shop Owner', 'S', 'suresh.owner@electrodesk.in', '+91 98480 44004', 'Active'),
(5, 'vikram', 'scrypt:32768:8:1$K5b8lRk$e2b5e28a47...', 'Vikram', 'Delivery Staff', 'VI', 'vikram.delivery@electrodesk.in', '+91 98480 55005', 'Active');

-- Categories (7 categories)
INSERT IGNORE INTO CATEGORY (category_id, category_code, category_name, icon, description)
VALUES
(1, 'CAT-01', 'Smartphones & Tablets', 'bi-phone-fill', '5G flagships, foldables, budget smartphones, iPads and Android tablets'),
(2, 'CAT-02', 'Laptops & Computers', 'bi-laptop-fill', 'Ultrabooks, workstation PCs, gaming laptops, and high-performance desktops'),
(3, 'CAT-03', 'Audio & Sound', 'bi-headphones', 'Noise-cancelling wireless headphones, soundbars, TWS earbuds and Bluetooth speakers'),
(4, 'CAT-04', 'Smart TVs & Displays', 'bi-tv-fill', '4K/8K OLED, QLED, gaming monitors, home theatre screens and projectors'),
(5, 'CAT-05', 'Smart Home & IoT', 'bi-house-gear-fill', 'Mesh Wi-Fi routers, robot vacuum cleaners, security cameras and smart plugs'),
(6, 'CAT-06', 'Gaming & Consoles', 'bi-controller', 'PlayStation, Xbox, Nintendo consoles, mechanical keyboards and gaming headsets'),
(7, 'CAT-07', 'Wearables & Fitness', 'bi-smartwatch', 'Smartwatches, cellular fitness trackers, and health monitoring bands');

-- Sample Delivery Orders
INSERT IGNORE INTO DELIVERY_ORDER (delivery_id, delivery_number, sale_id, customer_id, recipient_name, recipient_phone, delivery_address, delivery_charges, expected_date, delivery_status, assigned_to_user_id, delivery_notes, delivered_at)
VALUES
(1, 'DEL-2026-0001', 4, 4, 'Kavita Sundaram', '+91 98800 66778', '24, 100 Feet Road, Indiranagar, Bengaluru, Karnataka', 150.00, '2026-11-21', 'Delivered', 5, 'Doorstep delivery completed with OTP verification', '2026-11-21 16:45:00'),
(2, 'DEL-2026-0002', 3, 3, 'Vikram Malhotra', '+91 98110 55667', 'D-48, Greater Kailash Part 1, New Delhi, Delhi', 200.00, '2026-11-22', 'Out for Delivery', 5, 'Dispatched with logistics van #4', NULL),
(3, 'DEL-2026-0003', 2, 2, 'Ananya Reddy', '+91 98480 44556', 'Plot 108, Jubilee Hills, Road No. 36, Hyderabad, Telangana', 100.00, '2026-11-23', 'Assigned', 5, 'Fragile electronics item - handle with extra care', NULL),
(4, 'DEL-2026-0004', 1, 1, 'Rajesh Iyer', '+91 98400 33445', '15/3, TTK Road, Alwarpet, Chennai, Tamil Nadu', 0.00, '2026-11-24', 'Pending', NULL, 'Free store delivery promotion applied', NULL);

-- Sample Delivery Logs
INSERT IGNORE INTO DELIVERY_LOG (log_id, delivery_id, status_from, status_to, changed_by_user_id, notes, created_at)
VALUES
(1, 1, 'Pending', 'Assigned', 1, 'Assigned to delivery executive Vikram', '2026-11-21 11:30:00'),
(2, 1, 'Assigned', 'Out for Delivery', 5, 'Out for morning delivery run', '2026-11-21 14:00:00'),
(3, 1, 'Out for Delivery', 'Delivered', 5, 'Package handed over to customer. OTP verified.', '2026-11-21 16:45:00'),
(4, 2, 'Pending', 'Assigned', 1, 'Assigned to Vikram for Delhi South route', '2026-11-22 09:00:00'),
(5, 2, 'Assigned', 'Out for Delivery', 5, 'Dispatched with morning van route', '2026-11-22 09:30:00'),
(6, 3, 'Pending', 'Assigned', 1, 'Assigned to Vikram for Jubilee Hills slot', '2026-11-22 14:00:00');
