"""
Electrodesk - Database Initialization & Seed Script
Sets up the 6 normalized tables and seeds renamed users, INR products, and GST records.
"""
import os
import sys
import sqlite3
import config
from werkzeug.security import generate_password_hash

try:
    import pymysql
    PYMYSQL_AVAILABLE = True
except ImportError:
    PYMYSQL_AVAILABLE = False


SQLITE_SCHEMA = """
-- 1. USER Table (Renamed: Ram, Geetha, Sai, Suresh)
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

-- 2. CATEGORY Table (with category_code and icon)
CREATE TABLE IF NOT EXISTS CATEGORY (
    category_id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_code TEXT NOT NULL UNIQUE,
    category_name TEXT NOT NULL UNIQUE,
    description TEXT,
    icon TEXT DEFAULT 'bi-box-seam',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. PRODUCT Table (Indian Rupee pricing)
CREATE TABLE IF NOT EXISTS PRODUCT (
    product_id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_code TEXT NOT NULL UNIQUE,
    product_name TEXT NOT NULL,
    category_id INTEGER NOT NULL,
    brand TEXT NOT NULL,
    model TEXT,
    cost_price REAL NOT NULL DEFAULT 0.0,
    selling_price REAL NOT NULL DEFAULT 0.0,
    stock_quantity INTEGER NOT NULL DEFAULT 0,
    reorder_level INTEGER NOT NULL DEFAULT 5,
    warranty_months INTEGER NOT NULL DEFAULT 12,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (category_id) REFERENCES CATEGORY(category_id) ON DELETE RESTRICT
);

-- 4. CUSTOMER Table
CREATE TABLE IF NOT EXISTS CUSTOMER (
    customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_name TEXT NOT NULL,
    phone TEXT NOT NULL,
    email TEXT,
    address TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 5. SALE Table (with CGST 9% + SGST 9%)
CREATE TABLE IF NOT EXISTS SALE (
    sale_id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_number TEXT NOT NULL UNIQUE,
    customer_id INTEGER,
    user_id INTEGER NOT NULL,
    sale_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    subtotal REAL NOT NULL DEFAULT 0.0,
    cgst_amount REAL NOT NULL DEFAULT 0.0,
    sgst_amount REAL NOT NULL DEFAULT 0.0,
    tax_amount REAL NOT NULL DEFAULT 0.0,
    discount_amount REAL NOT NULL DEFAULT 0.0,
    grand_total REAL NOT NULL DEFAULT 0.0,
    payment_method TEXT NOT NULL DEFAULT 'Cash',
    payment_status TEXT NOT NULL DEFAULT 'Paid',
    notes TEXT,
    FOREIGN KEY (customer_id) REFERENCES CUSTOMER(customer_id) ON DELETE SET NULL,
    FOREIGN KEY (user_id) REFERENCES USER(user_id)
);

-- 6. SALE_ITEM Table
CREATE TABLE IF NOT EXISTS SALE_ITEM (
    item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 1,
    unit_price REAL NOT NULL DEFAULT 0.0,
    total_price REAL NOT NULL DEFAULT 0.0,
    serial_number TEXT,
    warranty_expiry_date TEXT,
    FOREIGN KEY (sale_id) REFERENCES SALE(sale_id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES PRODUCT(product_id)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_prod_category ON PRODUCT(category_id);
CREATE INDEX IF NOT EXISTS idx_prod_stock ON PRODUCT(stock_quantity);
CREATE INDEX IF NOT EXISTS idx_sale_customer ON SALE(customer_id);
CREATE INDEX IF NOT EXISTS idx_sale_user ON SALE(user_id);
CREATE INDEX IF NOT EXISTS idx_sale_date ON SALE(sale_date);
CREATE INDEX IF NOT EXISTS idx_item_sale ON SALE_ITEM(sale_id);
CREATE INDEX IF NOT EXISTS idx_item_product ON SALE_ITEM(product_id);
CREATE INDEX IF NOT EXISTS idx_item_warranty ON SALE_ITEM(warranty_expiry_date);
"""


def seed_sqlite(cursor, force=False):
    """Seed sample data into SQLite."""
    if not force:
        cursor.execute("SELECT COUNT(*) FROM USER")
        if cursor.fetchone()[0] > 0:
            return

    # Passwords
    ram_hash = generate_password_hash('admin123')
    geetha_hash = generate_password_hash('geetha123')
    sai_hash = generate_password_hash('sai123')
    suresh_hash = generate_password_hash('suresh123')

    # 1. Renamed Users (Ram, Geetha, Sai, Suresh)
    users = [
        ('admin', ram_hash, 'Ram', 'System Administrator', 'RA', 'ram@electrodesk.in', '+91 98480 11001', 'Active'),
        ('geetha', geetha_hash, 'Geetha', 'Shop Manager', 'GE', 'geetha@electrodesk.in', '+91 98480 11002', 'Active'),
        ('sai', sai_hash, 'Sai', 'Sales Staff', 'SA', 'sai@electrodesk.in', '+91 98480 11003', 'Active'),
        ('suresh', suresh_hash, 'Suresh', 'Shop Owner', 'S', 'suresh@electrodesk.in', '+91 98480 11004', 'Active')
    ]
    cursor.executemany("""
        INSERT INTO USER (username, password_hash, full_name, role, avatar, email, phone, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, users)

    # 2. Categories with Code and Icon
    categories = [
        ('CAT-01', 'Smartphones & Tablets', 'Flagship & budget mobile phones, tablets, e-readers', 'bi-phone-fill'),
        ('CAT-02', 'Laptops & Computers', 'Ultrabooks, gaming PCs, workstations, desktop peripherals', 'bi-laptop-fill'),
        ('CAT-03', 'Audio & Sound', 'Noise-cancelling headphones, wireless earbuds, bluetooth soundbars', 'bi-headphones'),
        ('CAT-04', 'Smart TVs & Displays', '4K OLED/QLED smart TVs, ultra-wide gaming monitors', 'bi-tv-fill'),
        ('CAT-05', 'Wearables & Fitness', 'Smartwatches, fitness bands, health sensors', 'bi-smartwatch'),
        ('CAT-06', 'Gaming & Consoles', 'Next-gen consoles, wireless controllers, VR headsets', 'bi-controller')
    ]
    cursor.executemany("""
        INSERT INTO CATEGORY (category_code, category_name, description, icon)
        VALUES (?, ?, ?, ?)
    """, categories)

    # 3. Products with INR Pricing
    products = [
        ('ELEC-SMP-001', 'Galaxy S25 Ultra 512GB', 1, 'Samsung', 'SM-S938B', 98000.00, 129999.00, 18, 5, 24, 'Snapdragon 8 Elite, 200MP Quad Camera, Dynamic AMOLED 2X, S-Pen included'),
        ('ELEC-SMP-002', 'iPhone 16 Pro Max 256GB', 1, 'Apple', 'A3296', 105000.00, 139900.00, 3, 5, 12, 'A18 Pro chip, Grade 5 Titanium finish, 48MP Fusion camera system (LOW STOCK)'),
        ('ELEC-SMP-003', 'Pixel 9 Pro 128GB', 1, 'Google', 'GZC4K', 65000.00, 89999.00, 12, 4, 24, 'Google Tensor G4, Super Actua display, Pro triple camera with Gemini AI'),
        ('ELEC-LPT-001', 'MacBook Pro 16" M4 Max', 2, 'Apple', 'MUW63LL/A', 260000.00, 319900.00, 7, 3, 12, '16-core CPU, 40-core GPU, 36GB Unified Memory, 1TB SSD Liquid Retina XDR'),
        ('ELEC-LPT-002', 'Dell XPS 15 OLED Core Ultra 9', 2, 'Dell', '9530-U9', 175000.00, 224999.00, 2, 4, 24, 'Intel Core Ultra 9, 32GB DDR5, RTX 4070 8GB, 3.5K OLED Touch (CRITICAL LOW)'),
        ('ELEC-LPT-003', 'ASUS ROG Zephyrus G16', 2, 'ASUS', 'GU605MY', 190000.00, 249999.00, 9, 3, 24, 'AMD Ryzen 9, NVIDIA RTX 4080 12GB, 240Hz ROG Nebula OLED display'),
        ('ELEC-AUD-001', 'WH-1000XM5 Wireless Headphones', 3, 'Sony', 'WH1000XM5/B', 22000.00, 29990.00, 25, 6, 12, 'Industry Leading Noise Cancellation, 30-hour battery, Auto NC Optimizer'),
        ('ELEC-AUD-002', 'AirPods Pro 2 USB-C', 3, 'Apple', 'MTJV3AM/A', 18000.00, 24900.00, 4, 8, 12, 'Active Noise Cancellation, Adaptive Audio, MagSafe Charging Case (LOW STOCK)'),
        ('ELEC-AUD-003', 'Bose QuietComfort Ultra Earbuds', 3, 'Bose', '882826-0010', 21000.00, 27900.00, 14, 5, 12, 'Spatial Audio, CustomTune technology, 24-hour total listening time'),
        ('ELEC-DTV-001', 'LG 65" G4 Series OLED evo 4K', 4, 'LG', 'OLED65G4SUB', 170000.00, 229990.00, 6, 2, 36, 'Alpha 11 AI Processor 4K, Brightness Booster Max, One Wall Design, 144Hz'),
        ('ELEC-DTV-002', 'Samsung 55" The Frame QLED 4K', 4, 'Samsung', 'QN55LS03D', 85000.00, 119990.00, 8, 3, 24, 'Matte Display, Art Mode, Slim-fit Wall Mount included, Pantone Validated'),
        ('ELEC-WRB-001', 'Apple Watch Ultra 2 Black Titanium', 5, 'Apple', 'MX403LL/A', 65000.00, 89900.00, 11, 4, 12, '49mm titanium case, Precision dual-frequency GPS, up to 72 hours battery'),
        ('ELEC-WRB-002', 'Galaxy Watch Ultra LTE', 5, 'Samsung', 'SM-L705U', 42000.00, 59999.00, 1, 3, 12, 'Cushion design, Dual-frequency GPS, Energy Score, 10ATM (CRITICAL LOW)'),
        ('ELEC-GAM-001', 'PlayStation 5 Pro 2TB', 6, 'Sony', 'CFI-7019B', 55000.00, 69990.00, 15, 5, 12, 'PlayStation Spectral Super Resolution (PSSR), Advanced Ray Tracing, 2TB SSD'),
        ('ELEC-GAM-002', 'Xbox Series X 1TB Digital', 6, 'Microsoft', 'RRT-00049', 40000.00, 49990.00, 0, 4, 12, '12 teraflops GPU processing power, 4K gaming, Quick Resume (OUT OF STOCK)')
    ]
    cursor.executemany("""
        INSERT INTO PRODUCT (product_code, product_name, category_id, brand, model, cost_price, selling_price, stock_quantity, reorder_level, warranty_months, description)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, products)

    # 4. Customers in India
    customers = [
        ('Rajesh Sharma', '+91 98201 12345', 'rajesh.sharma@dunder.in', '1725 Nariman Point, Mumbai, MH'),
        ('Priya Nair', '+91 98450 23456', 'priya.nair@techcorp.in', '404 100 Feet Road, Indiranagar, Bengaluru, KA'),
        ('Vikram Reddy', '+91 99890 34567', 'vikram.reddy@horizon.in', '88 Road No. 36, Jubilee Hills, Hyderabad, TS'),
        ('Ananya Patel', '+91 97123 45678', 'ananya.p@aurora.in', '742 SG Highway, Bodakdev, Ahmedabad, GJ'),
        ('Karthik Iyer', '+91 94440 56789', 'karthik.iyer@chennai.in', '12 2nd Avenue, Anna Nagar, Chennai, TN')
    ]
    cursor.executemany("""
        INSERT INTO CUSTOMER (customer_name, phone, email, address)
        VALUES (?, ?, ?, ?)
    """, customers)

    # 5. Sales with GST 18% (CGST 9% + SGST 9%)
    sales = [
        ('INV-20261101-001', 1, 3, '2026-11-01 14:30:00', 159989.00, 14399.00, 14399.00, 28798.00, 5000.00, 183787.00, 'Card', 'Paid', 'Delivered with free tempered glass'),
        ('INV-20261108-002', 2, 3, '2026-11-08 17:15:00', 319900.00, 28791.00, 28791.00, 57582.00, 10000.00, 367482.00, 'UPI', 'Paid', 'Corporate purchase with GST invoice'),
        ('INV-20261112-003', 3, 2, '2026-11-12 12:45:00', 99980.00, 8998.00, 8998.00, 17996.00, 0.00, 117976.00, 'UPI', 'Paid', 'Paid via QR Code terminal'),
        ('INV-20261116-004', 4, 1, '2026-11-16 16:00:00', 229990.00, 20699.00, 20699.00, 41398.00, 8000.00, 263388.00, 'Bank Transfer', 'Paid', 'Express white-glove installation included')
    ]
    cursor.executemany("""
        INSERT INTO SALE (invoice_number, customer_id, user_id, sale_date, subtotal, cgst_amount, sgst_amount, tax_amount, discount_amount, grand_total, payment_method, payment_status, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, sales)

    # 6. Sale Items (with Serial Numbers & calculated warranty expiry dates)
    sale_items = [
        (1, 1, 1, 129999.00, 129999.00, 'SN-SAMS25U-884920', '2028-11-01'),
        (1, 7, 1, 29990.00, 29990.00, 'SN-SONYXM5-492104', '2027-11-01'),
        (2, 4, 1, 319900.00, 319900.00, 'SN-APLM4MX-902144', '2027-11-08'),
        (3, 7, 1, 29990.00, 29990.00, 'SN-SONYXM5-773192', '2027-11-12'),
        (3, 14, 1, 69990.00, 69990.00, 'SN-SONYPS5-330198', '2027-11-12'),
        (4, 10, 1, 229990.00, 229990.00, 'SN-LGOLED65-449102', '2029-11-16')
    ]
    cursor.executemany("""
        INSERT INTO SALE_ITEM (sale_id, product_id, quantity, unit_price, total_price, serial_number, warranty_expiry_date)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, sale_items)


def init_sqlite(force=False):
    """Initializes SQLite database and tables."""
    conn = sqlite3.connect(config.SQLITE_DB_PATH)
    cursor = conn.cursor()
    cursor.executescript(SQLITE_SCHEMA)
    seed_sqlite(cursor, force=force)
    conn.commit()
    conn.close()
    print(f"SQLite database initialized and seeded at: {config.SQLITE_DB_PATH}")


def init_mysql():
    """Initializes MySQL database from schema and seed files."""
    if not PYMYSQL_AVAILABLE:
        print("Error: pymysql is not installed.")
        return False

    try:
        conn = pymysql.connect(
            host=config.MYSQL_HOST,
            port=config.MYSQL_PORT,
            user=config.MYSQL_USER,
            password=config.MYSQL_PASSWORD,
            autocommit=True
        )
        cursor = conn.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{config.MYSQL_DB}`;")
        cursor.execute(f"USE `{config.MYSQL_DB}`;")

        schema_path = os.path.join(config.BASE_DIR, 'schema_mysql.sql')
        if os.path.exists(schema_path):
            with open(schema_path, 'r', encoding='utf-8') as f:
                schema_sql = f.read()
            for statement in schema_sql.split(';'):
                statement = statement.strip()
                if statement:
                    cursor.execute(statement)

        seed_path = os.path.join(config.BASE_DIR, 'seed_data_mysql.sql')
        if os.path.exists(seed_path):
            with open(seed_path, 'r', encoding='utf-8') as f:
                seed_sql = f.read()
            for statement in seed_sql.split(';'):
                statement = statement.strip()
                if statement:
                    cursor.execute(statement)

        conn.close()
        print(f"MySQL database '{config.MYSQL_DB}' successfully initialized and seeded on {config.MYSQL_HOST}:{config.MYSQL_PORT}")
        return True
    except Exception as e:
        print(f"Could not connect to MySQL: {e}")
        return False


def ensure_db_initialized():
    """Ensures database is ready on startup."""
    import db
    if db.ACTIVE_DB_TYPE == 'mysql':
        try:
            db.query("SELECT 1 FROM USER LIMIT 1")
            return
        except Exception:
            init_mysql()
    else:
        init_sqlite()


if __name__ == '__main__':
    force_seed = '--force' in sys.argv
    if len(sys.argv) > 1 and sys.argv[1] == '--mysql':
        init_mysql()
    else:
        init_sqlite(force=force_seed)
