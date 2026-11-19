-- Electrodesk Sample Seed Data (MySQL 8.0+)
USE electrodesk_db;

-- Users (Ram, Geetha, Sai, Suresh)
INSERT IGNORE INTO USER (user_id, username, password_hash, full_name, role, avatar, email, phone, status)
VALUES
(1, 'admin', 'scrypt:32768:8:1$K5b8lRk$e2b5e28a47...', 'Ram', 'System Administrator', 'RA', 'ram.admin@electrodesk.in', '+91 98480 11001', 'Active'),
(2, 'geetha', 'scrypt:32768:8:1$K5b8lRk$e2b5e28a47...', 'Geetha', 'Shop Manager', 'GE', 'geetha.mgr@electrodesk.in', '+91 98480 22002', 'Active'),
(3, 'sai', 'scrypt:32768:8:1$K5b8lRk$e2b5e28a47...', 'Sai', 'Sales Staff', 'SA', 'sai.sales@electrodesk.in', '+91 98480 33003', 'Active'),
(4, 'suresh', 'scrypt:32768:8:1$K5b8lRk$e2b5e28a47...', 'Suresh', 'Shop Owner', 'S', 'suresh.owner@electrodesk.in', '+91 98480 44004', 'Active');

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
