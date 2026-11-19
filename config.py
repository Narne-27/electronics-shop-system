"""
Electrodesk - Electronics Shop Management System
Configuration Settings
"""
import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# Flask settings
SECRET_KEY = os.environ.get('SECRET_KEY', 'electrodesk-secure-secret-key-2026-prod')
DEBUG = os.environ.get('FLASK_DEBUG', 'True').lower() in ('true', '1', 'yes')

# Store Branding & Details for Invoices & Receipts
STORE_NAME = os.environ.get('STORE_NAME', 'Electrodesk')
STORE_TAGLINE = 'Smart Electronics & Digital Retail Hub'
STORE_ADDRESS = '#42, Tech Boulevard, Hitec City, Hyderabad, Telangana 500081'
STORE_PHONE = '+91 (040) 4890-2800 / +91 98480 12345'
STORE_EMAIL = 'support@electrodesk.in'
STORE_WEBSITE = 'www.electrodesk.in'
STORE_TAX_ID = 'GSTIN: 36AAACE4812K1Z8 / PAN: AAACE4812K'
DEFAULT_TAX_RATE = 18.0  # GST 18% (CGST 9% + SGST 9%)
CGST_RATE = 9.0
SGST_RATE = 9.0
CURRENCY_SYMBOL = '₹'

# Database Configuration
# Set DB_TYPE to 'mysql' or 'sqlite'. Default is 'sqlite' for zero-setup execution,
# with automated fallback if MySQL server is not running.
DB_TYPE = os.environ.get('DB_TYPE', 'sqlite').lower()

# MySQL Settings
MYSQL_HOST = os.environ.get('MYSQL_HOST', 'localhost')
MYSQL_PORT = int(os.environ.get('MYSQL_PORT', 3306))
MYSQL_USER = os.environ.get('MYSQL_USER', 'root')
MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', 'root')
MYSQL_DB = os.environ.get('MYSQL_DB', 'electrodesk_db')

# SQLite Settings (local zero-dependency fallback)
SQLITE_DB_PATH = os.path.join(BASE_DIR, 'electrodesk.db')
