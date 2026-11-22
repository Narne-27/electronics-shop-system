"""
Electrodesk - Electronics Shop Management System
Configuration Settings
"""
import os
import datetime

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# Flask settings
import secrets


def _load_secret_key():
    """
    SECRET_KEY comes from the environment; otherwise a random key is generated
    once and persisted next to the app (never a hard-coded value in source).
    """
    env_key = os.environ.get('SECRET_KEY')
    if env_key:
        return env_key
    key_path = os.path.join(BASE_DIR, '.secret_key')
    try:
        if os.path.exists(key_path):
            with open(key_path, 'r', encoding='utf-8') as fh:
                stored = fh.read().strip()
                if stored:
                    return stored
        generated = secrets.token_hex(32)
        with open(key_path, 'w', encoding='utf-8') as fh:
            fh.write(generated)
        return generated
    except OSError:
        return secrets.token_hex(32)


SECRET_KEY = _load_secret_key()
# Debug mode exposes an interactive debugger: it is OFF unless explicitly enabled.
DEBUG = os.environ.get('FLASK_DEBUG', 'False').lower() in ('true', '1', 'yes')
# Bind to localhost by default; set HOST=0.0.0.0 to expose on the network.
HOST = os.environ.get('HOST', '127.0.0.1')

# Global Date Constant fallback. NOTE: the application resolves "today" at
# request time (see get_app_today in app.py) so this value is never stale.
APP_TODAY = datetime.date.today()

# Store Branding & Details for Invoices & Receipts
STORE_NAME = os.environ.get('STORE_NAME', 'Electrodesk')
STORE_TAGLINE = 'Smart Electronics & Digital Retail Hub'
STORE_ADDRESS = os.environ.get('STORE_ADDRESS', '#42, Tech Boulevard, Hitec City, Hyderabad, Telangana 500081')
STORE_LOCATION = os.environ.get('STORE_LOCATION', 'Hitec City, Hyderabad')
STORE_PHONE = '+91 (040) 4890-2800 / +91 98480 12345'
STORE_EMAIL = 'support@electrodesk.in'
STORE_WEBSITE = 'www.electrodesk.in'
STORE_TAX_ID = 'GSTIN: 36AAACE4812K1Z8 / PAN: AAACE4812K'
DEFAULT_TAX_RATE = 18.0  # GST 18% (CGST 9% + SGST 9%)
CGST_RATE = 9.0
SGST_RATE = 9.0
CURRENCY_SYMBOL = '₹'

# Quick Demo login toggle (enabled by default; set DEMO_MODE=false to disable)
DEMO_MODE = os.environ.get('DEMO_MODE', 'true').lower() in ('true', '1', 'yes')

# Financing & EMI Defaults (Annual Interest Rates)
EMI_PLANS = {
    3: {'months': 3, 'interest_rate': 0.0, 'label': '3 Months No-Cost EMI (0%)'},
    6: {'months': 6, 'interest_rate': 12.0, 'label': '6 Months Standard EMI (12% p.a.)'},
    9: {'months': 9, 'interest_rate': 14.0, 'label': '9 Months Standard EMI (14% p.a.)'},
    12: {'months': 12, 'interest_rate': 15.0, 'label': '12 Months Extended EMI (15% p.a.)'}
}

# Standard Active Promotional Coupons
ACTIVE_COUPONS = {
    'WELCOME5': {'type': 'percent', 'value': 5.0, 'description': 'Welcome Discount 5% Off', 'max_discount': 2500},
    'FESTIVE10': {'type': 'percent', 'value': 10.0, 'description': 'Festival Electronics Offer 10% Off', 'max_discount': 5000},
    'VIP15': {'type': 'percent', 'value': 15.0, 'description': 'VIP Special 15% Off (Requires Owner Approval)', 'max_discount': 10000},
    'FLAT1000': {'type': 'flat', 'value': 1000.0, 'description': 'Flat ₹1,000 Off on orders above ₹20,000', 'min_order': 20000}
}

# Owner Authorization PIN for discounts > 10%
# Override in production: set the OWNER_APPROVAL_PIN environment variable.
OWNER_APPROVAL_PIN = os.environ.get('OWNER_APPROVAL_PIN', '9999')

# Discounts above this percentage of the subtotal need Owner approval
DISCOUNT_APPROVAL_PCT = 10.0
# Trade-in / exchange value above this percentage of the subtotal needs Owner approval
EXCHANGE_APPROVAL_PCT = 50.0

# Database Configuration
DB_TYPE = os.environ.get('DB_TYPE', 'sqlite').lower()

# MySQL Settings
MYSQL_HOST = os.environ.get('MYSQL_HOST', 'localhost')
MYSQL_PORT = int(os.environ.get('MYSQL_PORT', 3306))
MYSQL_USER = os.environ.get('MYSQL_USER', 'root')
MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', 'root')
MYSQL_DB = os.environ.get('MYSQL_DB', 'electrodesk_db')

# SQLite Settings (local zero-dependency fallback)
SQLITE_DB_PATH = os.path.join(BASE_DIR, 'electrodesk.db')
