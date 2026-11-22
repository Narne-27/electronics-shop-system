"""
Electrodesk - Electronics Shop Management System
Main Flask Application - Comprehensive Enterprise Edition
"""
import os
import io
import re
import csv
import json
import math
import hmac
import calendar
import datetime
from urllib.parse import urlparse
from functools import wraps
from flask import (
    Flask, render_template, request, redirect, url_for, flash, session, jsonify, Response, send_file
)
from werkzeug.security import generate_password_hash, check_password_hash
import config
import db
import init_db

app = Flask(__name__)
app.secret_key = config.SECRET_KEY
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    MAX_CONTENT_LENGTH=16 * 1024 * 1024,   # 16 MB upload cap (CSV import / JSON restore)
)

# Ensure database is initialized on startup
with app.app_context():
    init_db.ensure_db_initialized()


# ==========================================================
# DYNAMIC TIME & APP_TODAY CONSTANT HELPER
# ==========================================================

def get_app_today():
    """
    Returns the dynamic operational reference date.
    If 'app_today_mode' in STORE_SETTING is 'manual', returns the manual 'app_today' date.
    Otherwise returns the REAL current calendar date, evaluated per call
    (previously a value frozen at server start-up was used, so a server left
    running past midnight kept yesterday's date).
    """
    try:
        mode_row = db.query_one("SELECT setting_value FROM STORE_SETTING WHERE setting_key = 'app_today_mode'")
        mode = mode_row['setting_value'] if mode_row else 'auto'
        if mode == 'manual':
            row = db.query_one("SELECT setting_value FROM STORE_SETTING WHERE setting_key = 'app_today'")
            if row and row['setting_value']:
                return datetime.datetime.strptime(str(row['setting_value'])[:10], '%Y-%m-%d').date()
    except Exception:
        pass
    return datetime.date.today()


# ==========================================================
# INPUT VALIDATION, SAFE REDIRECTS, ERROR HELPERS
# ==========================================================

class InputError(ValueError):
    """Raised for invalid user input; shown to the user as a friendly message."""


def parse_float(value, label, default=0.0, minimum=None, maximum=None):
    if value is None or (isinstance(value, str) and not value.strip()):
        number = float(default)
    else:
        try:
            number = float(value)
        except (TypeError, ValueError):
            raise InputError(f"{label} must be a valid number.")
    if math.isnan(number) or math.isinf(number):
        raise InputError(f"{label} must be a valid number.")
    if minimum is not None and number < minimum:
        raise InputError(f"{label} cannot be less than {minimum:g}.")
    if maximum is not None and number > maximum:
        raise InputError(f"{label} cannot be more than {maximum:g}.")
    return number


def parse_int(value, label, default=0, minimum=None, maximum=None):
    if value is None or (isinstance(value, str) and not value.strip()):
        number = int(default)
    elif isinstance(value, bool):
        raise InputError(f"{label} must be a whole number.")
    elif isinstance(value, int):
        number = value
    else:
        try:
            as_float = float(value)
            if math.isnan(as_float) or math.isinf(as_float) or as_float != int(as_float):
                raise ValueError
            number = int(as_float)          # "5", "5.0" are fine; "1.9" is rejected, not truncated
        except (TypeError, ValueError, OverflowError):
            raise InputError(f"{label} must be a whole number.")
    if minimum is not None and number < minimum:
        raise InputError(f"{label} cannot be less than {minimum}.")
    if maximum is not None and number > maximum:
        raise InputError(f"{label} cannot be more than {maximum}.")
    return number


def parse_date_str(value, label):
    try:
        return datetime.datetime.strptime(str(value or '').strip()[:10], '%Y-%m-%d').date()
    except ValueError:
        raise InputError(f"{label} must be a valid date (YYYY-MM-DD).")


def add_months(start_date, months):
    """Calendar-accurate month addition (12 months = 1 year, not 360 days)."""
    months = int(months)
    year = start_date.year + (start_date.month - 1 + months) // 12
    month = (start_date.month - 1 + months) % 12 + 1
    day = min(start_date.day, calendar.monthrange(year, month)[1])
    return datetime.date(year, month, day)


def is_safe_redirect(target):
    """Only allow same-site redirects (blocks open-redirect via ?next=)."""
    if not target or '\\' in target:
        return False
    parsed = urlparse(target)
    if parsed.scheme or parsed.netloc:
        return parsed.scheme in ('http', 'https') and parsed.netloc == request.host
    return target.startswith('/') and not target.startswith('//')


def _public_error(e):
    """Log the real exception; show users a generic message (no internals leaked)."""
    app.logger.error("Unhandled error: %r", e, exc_info=e)
    return "an internal error occurred (details were written to the server log)"


def _is_fk_error(e):
    text = str(e).lower()
    return 'foreign key' in text or 'constraint' in text or 'integrity' in text


@app.errorhandler(ValueError)
def handle_value_error(e):
    if not isinstance(e, InputError):
        app.logger.warning("Unexpected ValueError handled as bad input: %r", e, exc_info=e)
    message = str(e) if isinstance(e, InputError) else "Invalid input - please check the numbers and dates you entered."
    if request.path.startswith('/api/') or request.is_json or request.path == '/pos/checkout':
        return jsonify({'success': False, 'message': message}), 400
    flash(message, 'danger')
    back = request.referrer
    return redirect(back if is_safe_redirect(back) else url_for('dashboard'))


@app.before_request
def block_cross_site_posts():
    """Lightweight CSRF defence (no template changes needed): reject state-changing
    requests whose Origin/Referer is a different site."""
    if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
        origin = request.headers.get('Origin') or request.headers.get('Referer')
        if origin and urlparse(origin).netloc != request.host:
            return ('Cross-site request blocked.', 403)


# ==========================================================
# SHARED FORMATTERS: INR CURRENCY & DATES
# ==========================================================

def format_inr(value):
    """
    Formats a number as Indian Currency (INR):
    e.g. 3172747 -> ₹31,72,747 (maximumFractionDigits: 0)
    Matches: Intl.NumberFormat('en-IN', {style:'currency', currency:'INR', maximumFractionDigits:0})
    """
    if value is None:
        return '₹0'
    try:
        val = round(float(value))
        is_neg = val < 0
        s = str(abs(val))
        if len(s) <= 3:
            formatted = s
        else:
            last_three = s[-3:]
            remaining = s[:-3]
            groups = []
            while len(remaining) > 2:
                groups.insert(0, remaining[-2:])
                remaining = remaining[:-2]
            if remaining:
                groups.insert(0, remaining)
            formatted = ','.join(groups) + ',' + last_three
        return f"{'-' if is_neg else ''}₹{formatted}"
    except Exception:
        return f"₹{value}"


def format_date_in(value):
    """
    Formats a date string or object like: '19 Nov 2026'
    """
    if not value:
        return ''
    if isinstance(value, str):
        try:
            d = datetime.datetime.fromisoformat(value[:19])
            return d.strftime('%d %b %Y').lstrip('0')
        except Exception:
            try:
                parts = value[:10].split('-')
                dt = datetime.date(int(parts[0]), int(parts[1]), int(parts[2]))
                return dt.strftime('%d %b %Y').lstrip('0')
            except Exception:
                return value
    elif isinstance(value, (datetime.date, datetime.datetime)):
        return value.strftime('%d %b %Y').lstrip('0')
    return str(value)


app.jinja_env.filters['inr'] = format_inr
app.jinja_env.filters['date_in'] = format_date_in


@app.after_request
def add_header(response):
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


# ==========================================================
# AVATARS & USER ACCESS CONTROL
# ==========================================================

AVATAR_MAP = {
    'admin': 'RA', 'ram': 'RA',
    'geetha': 'GE', 'manager': 'GE',
    'sai': 'SA', 'staff': 'SA',
    'suresh': 'S', 'owner': 'S'
}

def get_avatar(username, full_name=''):
    u = (username or '').lower().strip()
    if u in AVATAR_MAP:
        return AVATAR_MAP[u]
    parts = (full_name or '').strip().split()
    if len(parts) >= 2:
        return (parts[0][0] + parts[1][0]).upper()
    elif len(parts) == 1 and len(parts[0]) >= 2:
        return parts[0][:2].upper()
    return 'U'


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login', next=request.url))
        # Re-check the account so deactivated/deleted users and role changes
        # take effect immediately instead of surviving until logout.
        try:
            account = db.query_one("SELECT role, status FROM USER WHERE user_id = %s", (session['user_id'],))
        except Exception:
            account = {'role': session.get('role'), 'status': 'Active'}
        if not account or account.get('status') != 'Active':
            session.clear()
            flash('Your account is no longer active. Please contact an administrator.', 'danger')
            return redirect(url_for('login'))
        session['role'] = account['role']
        return f(*args, **kwargs)
    return decorated_function


def roles_required(*allowed_roles):
    """
    Permission Matrix:
    - Shop Owner / Suresh: All privileges including Settings, Audit log, Owner Discounts.
    - System Administrator / Admin / Ram: All operational, catalog, user, and system privileges.
    - Shop Manager / Geetha: Operations, Catalog, Inventory, Purchase Orders, Reports, Claims. Cannot edit settings or delete users.
    - Sales Staff / Sai: View, New Sale, Add to sale, Invoices, Customer view/add, Warranty lookup.
      Staff CANNOT reach Audit Log, Settings, or Delete actions.
    """
    role_hierarchy = {
        'Shop Owner': ['Shop Owner', 'Owner'],
        'System Administrator': ['System Administrator', 'Admin'],
        'Shop Manager': ['Shop Manager', 'Manager'],
        'Sales Staff': ['Sales Staff', 'Staff'],
        'Delivery Staff': ['Delivery Staff', 'Delivery']
    }

    expanded = set()
    for r in allowed_roles:
        expanded.add(r)
        for canon, aliases in role_hierarchy.items():
            if r == canon or r in aliases:
                expanded.update(aliases)
                expanded.add(canon)

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('Please log in to access this page.', 'warning')
                return redirect(url_for('login'))
            user_role = session.get('role', '')
            if user_role not in expanded:
                flash(f'Access denied. Your role ({user_role}) does not have permission for this action.', 'danger')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def log_audit(action, module, details=''):
    """Logs system actions to AUDIT_LOG table."""
    try:
        uid = session.get('user_id')
        uname = session.get('username', 'System')
        ip = request.remote_addr if request else '127.0.0.1'
        db.execute("""
            INSERT INTO AUDIT_LOG (user_id, username, action, module, details, ip_address)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (uid, uname, action, module, details, ip))
    except Exception:
        pass


# ==========================================================
# DERIVED TOTALS AGGREGATOR
# Ensures Dashboard = Categories = Stock = Reports totals
# ==========================================================

def get_inventory_derived_totals():
    """
    Derived aggregation strictly calculated from PRODUCT table.
    Guarantees that total units, active SKUs, inventory cost value,
    and total retail value match identically everywhere.
    """
    row = db.query_one("""
        SELECT 
            COALESCE(SUM(stock_quantity), 0) as total_units,
            COUNT(*) as total_products,
            COALESCE(SUM(stock_quantity * cost_price), 0.0) as total_cost_value,
            COALESCE(SUM(stock_quantity * selling_price), 0.0) as total_retail_value
        FROM PRODUCT
    """)
    if not row:
        return {'total_units': 0, 'total_products': 0, 'total_skus': 0, 'total_cost_value': 0.0, 'total_retail_value': 0.0, 'projected_profit': 0.0}

    units = int(row['total_units'])
    skus = int(row['total_products'])
    cost = float(row['total_cost_value'])
    retail = float(row['total_retail_value'])
    return {
        'total_units': units,
        'total_products': skus,
        'total_skus': skus,
        'total_cost_value': cost,
        'total_retail_value': retail,
        'projected_profit': round(retail - cost, 2)
    }


# ==========================================================
# GLOBAL CONTEXT PROCESSOR
# ==========================================================

@app.context_processor
def inject_global_context():
    today = get_app_today()
    low_stock_count = 0
    expiring_warranties_count = 0
    open_claims_count = 0
    dues_count = 0

    if 'user_id' in session:
        try:
            ls = db.query_one("SELECT COUNT(*) as cnt FROM PRODUCT WHERE stock_quantity <= reorder_level")
            low_stock_count = ls['cnt'] if ls else 0
        except Exception:
            pass

        try:
            # Warranties expiring soon: within 30 days of APP_TODAY and >= today
            exp_date_limit = (today + datetime.timedelta(days=30)).strftime('%Y-%m-%d')
            today_str = today.strftime('%Y-%m-%d')
            ws = db.query_one("""
                SELECT COUNT(*) as cnt FROM SALE_ITEM 
                WHERE warranty_expiry_date IS NOT NULL 
                  AND warranty_expiry_date >= %s 
                  AND warranty_expiry_date <= %s
            """, (today_str, exp_date_limit))
            expiring_warranties_count = ws['cnt'] if ws else 0
        except Exception:
            pass

        try:
            oc = db.query_one("SELECT COUNT(*) as cnt FROM WARRANTY_CLAIM WHERE status = 'Open'")
            open_claims_count = oc['cnt'] if oc else 0
        except Exception:
            pass

        try:
            dc = db.query_one("SELECT COUNT(*) as cnt FROM SALE WHERE balance_due > 0")
            dues_count = dc['cnt'] if dc else 0
        except Exception:
            pass

    return {
        'store': {
            'name': config.STORE_NAME,
            'tagline': config.STORE_TAGLINE,
            'address': config.STORE_ADDRESS,
            'phone': config.STORE_PHONE,
            'email': config.STORE_EMAIL,
            'website': config.STORE_WEBSITE,
            'tax_id': config.STORE_TAX_ID,
            'currency': config.CURRENCY_SYMBOL,
            'default_tax_rate': config.DEFAULT_TAX_RATE,
            'cgst_rate': config.CGST_RATE,
            'sgst_rate': config.SGST_RATE
        },
        'current_user': {
            'id': session.get('user_id'),
            'username': session.get('username'),
            'full_name': session.get('full_name'),
            'role': session.get('role'),
            'avatar': session.get('avatar') or get_avatar(session.get('username'), session.get('full_name')),
            'email': session.get('email')
        } if 'user_id' in session else None,
        'app_today': today,
        'app_today_formatted': today.strftime('%d %b %Y').lstrip('0'),
        'today_weekday': today.strftime('%A'),
        'low_stock_count': low_stock_count,
        'expiring_warranties_count': expiring_warranties_count,
        'open_claims_count': open_claims_count,
        'dues_count': dues_count,
        'db_info': db.get_db_info()
    }


# ==========================================================
# AUTHENTICATION ROUTES
# ==========================================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.args.get('logout') or request.args.get('force'):
        session.clear()
    elif 'user_id' in session:
        return redirect(url_for('mirror_hall_hub'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip().lower()
        password = request.form.get('password', '').strip()

        alias_map = {'manager': 'geetha', 'staff': 'sai', 'owner': 'suresh', 'ram': 'admin'}
        lookup = alias_map.get(username, username)

        user = db.query_one("SELECT * FROM USER WHERE LOWER(username) = %s AND status = 'Active'", (lookup,))

        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['user_id']
            session['username'] = user['username']
            session['full_name'] = user['full_name']
            session['role'] = user['role']
            session['avatar'] = user.get('avatar') or get_avatar(user['username'], user['full_name'])
            session['email'] = user.get('email', '')

            log_audit('LOGIN', 'Auth', f"User {user['full_name']} logged in successfully")
            flash(f"Welcome back, {user['full_name']}!", 'success')
            next_page = request.args.get('next')
            return redirect(next_page if is_safe_redirect(next_page) else url_for('mirror_hall_hub'))
        else:
            flash('Invalid username or password. Please try again.', 'danger')

    return render_template('login.html')


@app.route('/logout')
def logout():
    log_audit('LOGOUT', 'Auth', f"User {session.get('full_name')} logged out")
    session.clear()
    flash('You have been successfully logged out.', 'info')
    return redirect(url_for('login'))


# ==========================================================
# MIRROR HALL 3D SECTION HUB ROUTES & METRICS
# ==========================================================

ROLES_FINANCE = ['System Administrator', 'Admin', 'Shop Owner', 'Shop Manager', 'Manager']
ROLES_ADMIN = ['System Administrator', 'Admin', 'Shop Owner']

def get_hub_sections_data(user_role):
    today = get_app_today()
    today_str = today.strftime('%Y-%m-%d')
    exp_limit = (today + datetime.timedelta(days=30)).strftime('%Y-%m-%d')

    # Single source of truth for inventory metrics (matches Dashboard, Categories, Stock & Reports)
    inv_totals = get_inventory_derived_totals()
    total_units = inv_totals['total_units']
    total_products = inv_totals['total_products']

    cat_cnt = db.query_one("SELECT COUNT(*) as cnt FROM CATEGORY")
    total_categories = cat_cnt['cnt'] if cat_cnt else 0

    low_stock = db.query_one("SELECT COUNT(*) as cnt FROM PRODUCT WHERE stock_quantity <= reorder_level")
    low_stock_cnt = low_stock['cnt'] if low_stock else 0

    exp_wty = db.query_one("SELECT COUNT(*) as cnt FROM SALE_ITEM WHERE warranty_expiry_date >= %s AND warranty_expiry_date <= %s", (today_str, exp_limit))
    exp_wty_cnt = exp_wty['cnt'] if exp_wty else 0

    cust_cnt = db.query_one("SELECT COUNT(*) as cnt FROM CUSTOMER")
    total_cust = cust_cnt['cnt'] if cust_cnt else 0

    dues_data = db.query_one("SELECT COALESCE(SUM(grand_total), 0.0) as amt, COUNT(*) as cnt FROM SALE WHERE payment_status = 'Pending'")
    pending_dues_amt = dues_data['amt'] if dues_data else 0.0
    pending_dues_cnt = dues_data['cnt'] if dues_data else 0

    quote_cnt = db.query_one("SELECT COUNT(*) as cnt FROM QUOTATION")
    total_quotes = quote_cnt['cnt'] if quote_cnt else 0

    today_rev = db.query_one("SELECT COALESCE(SUM(grand_total), 0.0) as rev, COUNT(*) as cnt FROM SALE WHERE DATE(sale_date) = %s", (today_str,))
    today_sales_val = today_rev['rev'] if today_rev else 0.0
    today_orders_cnt = today_rev['cnt'] if today_rev else 0

    sale_cnt = db.query_one("SELECT COUNT(*) as cnt FROM SALE")
    total_sales_cnt = sale_cnt['cnt'] if sale_cnt else 0

    ret_cnt = db.query_one("SELECT COUNT(*) as cnt FROM CREDIT_NOTE")
    total_returns_cnt = ret_cnt['cnt'] if ret_cnt else 0

    rep_cnt = db.query_one("SELECT COUNT(*) as cnt FROM REPAIR_TICKET WHERE status != 'Delivered'")
    total_repairs_cnt = rep_cnt['cnt'] if rep_cnt else 0

    deliv_active = db.query_one("SELECT COUNT(*) as cnt FROM DELIVERY_ORDER WHERE status IN ('Pending', 'Assigned', 'Out for Delivery')")
    active_deliveries_cnt = deliv_active['cnt'] if deliv_active else 0

    deliv_total = db.query_one("SELECT COUNT(*) as cnt FROM DELIVERY_ORDER")
    total_deliveries_cnt = deliv_total['cnt'] if deliv_total else 0

    exp_data = db.query_one("SELECT COALESCE(SUM(amount), 0.0) as total FROM EXPENSE")
    total_expenses = exp_data['total'] if exp_data else 0.0

    audit_cnt = db.query_one("SELECT COUNT(*) as cnt FROM AUDIT_LOG")
    total_audit_cnt = audit_cnt['cnt'] if audit_cnt else 0

    user_cnt = db.query_one("SELECT COUNT(*) as cnt FROM USER")
    total_users_cnt = user_cnt['cnt'] if user_cnt else 0

    total_notifs = low_stock_cnt + exp_wty_cnt + pending_dues_cnt

    sections = [
        # 1. OVERVIEW
        {
            'id': 'dashboard',
            'name': 'Dashboard',
            'code': 'DASH',
            'category': 'Overview',
            'eyebrow': 'SHOP OVERVIEW',
            'icon': 'bi-grid-1x2-fill',
            'route': '/dashboard',
            'metric': f"₹{today_sales_val:,.0f} Today" if today_sales_val > 0 else "Active Today",
            'badge': None,
            'accent': '#2bf0ff',
            'warm_accent': '#38bdf8',
            'allowed_roles': None
        },

        # 2. INVENTORY
        {
            'id': 'products',
            'name': 'Products',
            'code': 'PROD',
            'category': 'Inventory',
            'eyebrow': 'CATALOG',
            'icon': 'bi-box-seam-fill',
            'route': '/products',
            'metric': f"{total_products} Items Listed",
            'badge': None,
            'accent': '#7a3cff',
            'warm_accent': '#c084fc',
            'allowed_roles': None
        },
        {
            'id': 'categories',
            'name': 'Categories',
            'code': 'DEPT',
            'category': 'Inventory',
            'eyebrow': 'DEPARTMENTS',
            'icon': 'bi-tags-fill',
            'route': '/categories',
            'metric': f"{total_categories} Categories",
            'badge': None,
            'accent': '#f59e0b',
            'warm_accent': '#fbbf24',
            'allowed_roles': None
        },
        {
            'id': 'inventory',
            'name': 'Stock Inventory',
            'code': 'STCK',
            'category': 'Inventory',
            'eyebrow': 'WAREHOUSE',
            'icon': 'bi-boxes',
            'route': '/inventory',
            'metric': f"{total_units} Units On Hand",
            'badge': f"{low_stock_cnt} Low" if low_stock_cnt > 0 else None,
            'accent': '#10b981',
            'warm_accent': '#34d399',
            'allowed_roles': None
        },
        {
            'id': 'warranty',
            'name': 'Warranty',
            'code': 'WRTY',
            'category': 'Inventory',
            'eyebrow': 'PROTECTION',
            'icon': 'bi-shield-check',
            'route': '/warranty',
            'metric': f"{exp_wty_cnt} Expiring Soon" if exp_wty_cnt > 0 else "All Active",
            'badge': f"{exp_wty_cnt} Soon" if exp_wty_cnt > 0 else None,
            'accent': '#f43f5e',
            'warm_accent': '#fb7185',
            'allowed_roles': None
        },

        # 3. SALES
        {
            'id': 'customers',
            'name': 'Customers',
            'code': 'CUST',
            'category': 'Sales',
            'eyebrow': 'ACCOUNTS',
            'icon': 'bi-people-fill',
            'route': '/customers',
            'metric': f"{total_cust} Accounts",
            'badge': None,
            'accent': '#06b6d4',
            'warm_accent': '#22d3ee',
            'allowed_roles': None
        },
        {
            'id': 'customer_dues',
            'name': 'Customer Dues',
            'code': 'DUES',
            'category': 'Sales',
            'eyebrow': 'COLLECTIONS',
            'icon': 'bi-wallet2',
            'route': '/customer-dues',
            'metric': f"₹{pending_dues_amt:,.0f} Pending" if pending_dues_amt > 0 else "All Settled",
            'badge': f"{pending_dues_cnt} Due" if pending_dues_cnt > 0 else None,
            'accent': '#f97316',
            'warm_accent': '#fb923c',
            'allowed_roles': None
        },
        {
            'id': 'quotations',
            'name': 'Quotations',
            'code': 'QUOT',
            'category': 'Sales',
            'eyebrow': 'PROPOSALS',
            'icon': 'bi-file-earmark-text-fill',
            'route': '/quotations',
            'metric': f"{total_quotes} Estimates",
            'badge': None,
            'accent': '#6366f1',
            'warm_accent': '#818cf8',
            'allowed_roles': None
        },
        {
            'id': 'pos',
            'name': 'New Sale',
            'code': 'POS',
            'category': 'Sales',
            'eyebrow': 'CHECKOUT',
            'icon': 'bi-cart-check-fill',
            'route': '/pos',
            'metric': f"{today_orders_cnt} Today" if today_orders_cnt > 0 else "Quick POS Checkout",
            'badge': None,
            'accent': '#eab308',
            'warm_accent': '#fde047',
            'allowed_roles': None
        },
        {
            'id': 'invoices',
            'name': 'Billing & Invoices',
            'code': 'BILL',
            'category': 'Sales',
            'eyebrow': 'TRANSACTIONS',
            'icon': 'bi-receipt',
            'route': '/invoices',
            'metric': f"{total_sales_cnt} Invoices Issued",
            'badge': None,
            'accent': '#38bdf8',
            'warm_accent': '#7dd3fc',
            'allowed_roles': None
        },
        {
            'id': 'returns',
            'name': 'Returns & Credit',
            'code': 'RETN',
            'category': 'Sales',
            'eyebrow': 'REFUNDS',
            'icon': 'bi-arrow-return-left',
            'route': '/returns',
            'metric': f"{total_returns_cnt} Credit Notes",
            'badge': None,
            'accent': '#ec4899',
            'warm_accent': '#f472b6',
            'allowed_roles': None
        },

        # 4. OPERATIONS
        {
            'id': 'deliveries',
            'name': 'Delivery & Logistics',
            'code': 'DLVR',
            'category': 'Operations',
            'eyebrow': 'LOGISTICS',
            'icon': 'bi-truck',
            'route': '/deliveries',
            'metric': f"{active_deliveries_cnt} Active Dispatches" if active_deliveries_cnt > 0 else f"{total_deliveries_cnt} Orders" if total_deliveries_cnt > 0 else "Dispatch & Fleet",
            'badge': f"{active_deliveries_cnt} Active" if active_deliveries_cnt > 0 else None,
            'accent': '#06b6d4',
            'warm_accent': '#38bdf8',
            'allowed_roles': None
        },
        {
            'id': 'repair_tickets',
            'name': 'Repair Tickets',
            'code': 'REP',
            'category': 'Operations',
            'eyebrow': 'SERVICE',
            'icon': 'bi-tools',
            'route': '/repair-tickets',
            'metric': f"{total_repairs_cnt} Active Tickets" if total_repairs_cnt > 0 else "No Open Tickets",
            'badge': f"{total_repairs_cnt}" if total_repairs_cnt > 0 else None,
            'accent': '#14b8a6',
            'warm_accent': '#2dd4bf',
            'allowed_roles': None
        },

        # 5. FINANCE & REPORTS (Restricted by sidebar role rule)
        {
            'id': 'reports_profit_loss',
            'name': 'Profit & Loss',
            'code': 'PNL',
            'category': 'Finance & Reports',
            'eyebrow': 'FINANCIALS',
            'icon': 'bi-pie-chart-fill',
            'route': '/reports/profit-loss',
            'metric': f"₹{today_sales_val:,.0f} Rev Today" if today_sales_val > 0 else "Net P&L Reports",
            'badge': None,
            'accent': '#8b5cf6',
            'warm_accent': '#a78bfa',
            'allowed_roles': ROLES_FINANCE
        },
        {
            'id': 'expenses',
            'name': 'Expenses',
            'code': 'EXP',
            'category': 'Finance & Reports',
            'eyebrow': 'OUTFLOWS',
            'icon': 'bi-cash-coin',
            'route': '/expenses',
            'metric': f"₹{total_expenses:,.0f} Recorded",
            'badge': None,
            'accent': '#f43f5e',
            'warm_accent': '#fb7185',
            'allowed_roles': ROLES_FINANCE
        },
        {
            'id': 'reports_gst',
            'name': 'GST Summary',
            'code': 'GST',
            'category': 'Finance & Reports',
            'eyebrow': 'TAXATION',
            'icon': 'bi-file-earmark-ruled',
            'route': '/reports/gst',
            'metric': "Tax Invoices & Filing",
            'badge': None,
            'accent': '#0ea5e9',
            'warm_accent': '#38bdf8',
            'allowed_roles': ROLES_FINANCE
        },
        {
            'id': 'daily_closing',
            'name': 'Daily Closing',
            'code': 'CLOS',
            'category': 'Finance & Reports',
            'eyebrow': 'RECONCILIATION',
            'icon': 'bi-calendar2-check-fill',
            'route': '/daily-closing',
            'metric': "Day-end Cash Drawer",
            'badge': None,
            'accent': '#10b981',
            'warm_accent': '#34d399',
            'allowed_roles': ROLES_FINANCE
        },
        {
            'id': 'reports',
            'name': 'Analytics Reports',
            'code': 'ANLY',
            'category': 'Finance & Reports',
            'eyebrow': 'INSIGHTS',
            'icon': 'bi-graph-up-arrow',
            'route': '/reports',
            'metric': "Trends & Performance",
            'badge': None,
            'accent': '#a855f7',
            'warm_accent': '#c084fc',
            'allowed_roles': ROLES_FINANCE
        },

        # 6. ADMINISTRATION
        {
            'id': 'notifications',
            'name': 'Alerts & Notices',
            'code': 'ALRT',
            'category': 'Administration',
            'eyebrow': 'NOTIFICATIONS',
            'icon': 'bi-bell-fill',
            'route': '/notifications',
            'metric': f"{total_notifs} System Notices" if total_notifs > 0 else "All Clear",
            'badge': f"{total_notifs}" if total_notifs > 0 else None,
            'accent': '#ef4444',
            'warm_accent': '#f87171',
            'allowed_roles': None
        },
        {
            'id': 'audit_log',
            'name': 'Audit Trail',
            'code': 'AUDT',
            'category': 'Administration',
            'eyebrow': 'SECURITY',
            'icon': 'bi-journal-text',
            'route': '/audit-log',
            'metric': f"{total_audit_cnt} Logged Events",
            'badge': None,
            'accent': '#64748b',
            'warm_accent': '#94a3b8',
            'allowed_roles': ROLES_ADMIN
        },
        {
            'id': 'users',
            'name': 'Users & Roles',
            'code': 'USER',
            'category': 'Administration',
            'eyebrow': 'ACCESS CONTROL',
            'icon': 'bi-shield-lock-fill',
            'route': '/users',
            'metric': f"{total_users_cnt} Active Accounts",
            'badge': None,
            'accent': '#3b82f6',
            'warm_accent': '#60a5fa',
            'allowed_roles': ROLES_ADMIN
        },
        {
            'id': 'settings',
            'name': 'Settings',
            'code': 'SETT',
            'category': 'Administration',
            'eyebrow': 'CONFIGURATION',
            'icon': 'bi-gear-fill',
            'route': '/settings',
            'metric': "Shop Profile & Config",
            'badge': None,
            'accent': '#8b5cf6',
            'warm_accent': '#a78bfa',
            'allowed_roles': ROLES_ADMIN
        }
    ]

    # Strictly reuse sidebar role conditions: filter out restricted cards
    visible_sections = [
        s for s in sections 
        if not s.get('allowed_roles') or user_role in s['allowed_roles']
    ]
    return visible_sections


@app.route('/hub')
@login_required
def mirror_hall_hub():
    role = session.get('role', '')
    sections = get_hub_sections_data(role)
    return render_template('hub.html', sections=sections)


@app.route('/api/hub/metrics')
@login_required
def api_hub_metrics():
    role = session.get('role', '')
    sections = get_hub_sections_data(role)
    return jsonify({'status': 'ok', 'sections': sections})


# ==========================================================
# DASHBOARD ROUTE (DERIVED NUMBERS & EXPIRING WIDGET)
# ==========================================================

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('mirror_hall_hub'))
    return redirect(url_for('login'))


@app.route('/dashboard')
@login_required
def dashboard():
    today = get_app_today()
    today_str = today.strftime('%Y-%m-%d')

    # Derived inventory valuation
    inv_totals = get_inventory_derived_totals()

    # Sales metrics
    today_sales = db.query_one("""
        SELECT COALESCE(SUM(grand_total), 0.0) as revenue, COUNT(*) as count 
        FROM SALE 
        WHERE DATE(sale_date) = %s
    """, (today_str,))
    today_revenue = today_sales['revenue'] if today_sales else 0.0
    today_orders = today_sales['count'] if today_sales else 0

    all_time = db.query_one("SELECT COALESCE(SUM(grand_total), 0.0) as rev, COUNT(*) as count FROM SALE")
    total_revenue = all_time['rev'] if all_time else 0.0
    total_sales_count = all_time['count'] if all_time else 0

    # Low-stock items
    low_stock_items = db.query("""
        SELECT p.*, c.category_name 
        FROM PRODUCT p
        JOIN CATEGORY c ON p.category_id = c.category_id
        WHERE p.stock_quantity <= p.reorder_level
        ORDER BY p.stock_quantity ASC
    """)
    low_stock_count = len(low_stock_items)

    # Warranties Expiring Soon Widget (Within 30 Days of APP_TODAY)
    exp_limit = (today + datetime.timedelta(days=30)).strftime('%Y-%m-%d')
    expiring_soon_warranties = db.query("""
        SELECT 
            si.item_id, si.serial_number, si.warranty_expiry_date,
            p.product_name, p.brand,
            s.sale_id, s.invoice_number, s.sale_date,
            c.customer_name, c.phone as customer_phone
        FROM SALE_ITEM si
        JOIN PRODUCT p ON si.product_id = p.product_id
        JOIN SALE s ON si.sale_id = s.sale_id
        LEFT JOIN CUSTOMER c ON s.customer_id = c.customer_id
        WHERE si.warranty_expiry_date IS NOT NULL
          AND si.warranty_expiry_date >= %s
          AND si.warranty_expiry_date <= %s
        ORDER BY si.warranty_expiry_date ASC
        LIMIT 6
    """, (today_str, exp_limit))

    for w in expiring_soon_warranties:
        exp_d = datetime.datetime.strptime(w['warranty_expiry_date'][:10], '%Y-%m-%d').date()
        w['days_left'] = (exp_d - today).days

    # Recent Sales
    recent_sales = db.query("""
        SELECT s.*, c.customer_name, u.full_name as staff_name,
               (SELECT COUNT(*) FROM SALE_ITEM si WHERE si.sale_id = s.sale_id) as item_count
        FROM SALE s
        LEFT JOIN CUSTOMER c ON s.customer_id = c.customer_id
        LEFT JOIN USER u ON s.user_id = u.user_id
        ORDER BY s.sale_id DESC
        LIMIT 5
    """)

    # Category Revenue Distribution (Chart)
    category_chart = db.query("""
        SELECT c.category_name, 
               COALESCE(SUM(si.total_price), 0.0) as revenue,
               COALESCE(SUM(si.quantity), 0) as units_sold
        FROM CATEGORY c
        LEFT JOIN PRODUCT p ON c.category_id = p.category_id
        LEFT JOIN SALE_ITEM si ON p.product_id = si.product_id
        GROUP BY c.category_id, c.category_name
        ORDER BY revenue DESC
    """)

    # Top 5 Best Selling Products (Chart)
    top_products = db.query("""
        SELECT p.product_name, p.brand, p.model, c.category_name,
               COALESCE(SUM(si.quantity), 0) as total_sold,
               COALESCE(SUM(si.total_price), 0.0) as total_revenue
        FROM SALE_ITEM si
        JOIN PRODUCT p ON si.product_id = p.product_id
        JOIN CATEGORY c ON p.category_id = c.category_id
        GROUP BY p.product_id, p.product_name, p.brand, p.model, c.category_name
        HAVING total_sold > 0
        ORDER BY total_sold DESC
        LIMIT 5
    """)

    return render_template('dashboard.html',
                           today_sales_total=today_revenue,
                           today_sales_count=today_orders,
                           total_revenue=total_revenue,
                           total_sales_count=total_sales_count,
                           total_units=inv_totals['total_units'],
                           total_products=inv_totals['total_products'],
                           low_stock_count=low_stock_count,
                           low_stock_items=low_stock_items,
                           low_stock_products=low_stock_items,
                           expiring_soon_warranties=expiring_soon_warranties,
                           recent_sales=recent_sales,
                           category_chart=category_chart,
                           category_sales=category_chart,
                           top_products=top_products)


# ==========================================================
# STEP 1: DATA CORE - PRODUCTS (CRUD & CSV IMPORT/EXPORT)
# ==========================================================

@app.route('/products')
@login_required
def products():
    search = request.args.get('search', '').strip()
    category_id = request.args.get('category', '').strip()
    stock_filter = request.args.get('stock', '').strip()
    sort_by = request.args.get('sort', 'code').strip()

    query = """
        SELECT p.*, c.category_name 
        FROM PRODUCT p
        JOIN CATEGORY c ON p.category_id = c.category_id
        WHERE 1=1
    """
    params = []

    if search:
        query += " AND (p.product_name LIKE %s OR p.product_code LIKE %s OR p.brand LIKE %s OR p.model LIKE %s)"
        s = f"%{search}%"
        params.extend([s, s, s, s])

    if category_id:
        query += " AND p.category_id = %s"
        params.append(category_id)

    if stock_filter == 'in':
        query += " AND p.stock_quantity > p.reorder_level"
    elif stock_filter == 'low':
        query += " AND p.stock_quantity <= p.reorder_level AND p.stock_quantity > 0"
    elif stock_filter == 'out':
        query += " AND p.stock_quantity = 0"

    sort_dict = {
        'code': 'p.product_code ASC',
        'name': 'p.product_name ASC',
        'price_asc': 'p.selling_price ASC',
        'price_desc': 'p.selling_price DESC',
        'stock': 'p.stock_quantity ASC'
    }
    query += " ORDER BY " + sort_dict.get(sort_by, 'p.product_code ASC')

    products_list = db.query(query, tuple(params) if params else None)
    categories = db.query("SELECT * FROM CATEGORY ORDER BY category_code ASC")
    carousel_products = db.query("""
        SELECT p.*, c.category_name 
        FROM PRODUCT p
        JOIN CATEGORY c ON p.category_id = c.category_id
        WHERE p.is_new = 1 OR p.stock_quantity > 0
        ORDER BY p.is_new DESC, p.product_id ASC
        LIMIT 10
    """)

    return render_template('products.html',
                           products=products_list,
                           carousel_products=carousel_products,
                           categories=categories,
                           search=search,
                           selected_category=category_id,
                           stock_filter=stock_filter,
                           current_sort=sort_by)


@app.route('/products/<int:product_id>')
@login_required
def product_detail(product_id):
    product = db.query_one("""
        SELECT p.*, c.category_name
        FROM PRODUCT p
        JOIN CATEGORY c ON p.category_id = c.category_id
        WHERE p.product_id = %s
    """, (product_id,))
    if not product:
        flash('Product not found.', 'danger')
        return redirect(url_for('products'))
    return render_template('product_detail.html', product=product)


def _product_form_values():
    """Parse + validate the shared add/edit product form. Raises InputError."""
    code = request.form.get('product_code', '').strip().upper()
    name = request.form.get('product_name', '').strip()
    category_id = parse_int(request.form.get('category_id'), 'Category', 0, minimum=0)
    if not code or not name or not category_id:
        raise InputError('Product SKU, Name, and Category are required.')
    if len(code) > 50 or len(name) > 150:
        raise InputError('Product SKU (max 50) or Name (max 150) is too long.')
    return {
        'code': code,
        'name': name,
        'category_id': category_id,
        'brand': request.form.get('brand', '').strip()[:80] or 'Generic',
        'model': request.form.get('model', '').strip()[:100],
        'hsn_code': request.form.get('hsn_code', '8517').strip()[:20] or '8517',
        'tagline': request.form.get('tagline', '').strip()[:255],
        'is_new': 1 if request.form.get('is_new') else 0,
        'cost_price': parse_float(request.form.get('cost_price'), 'Cost price', 0.0, minimum=0.0),
        'selling_price': parse_float(request.form.get('selling_price'), 'Selling price', 0.0, minimum=0.0),
        'stock': parse_int(request.form.get('stock_quantity'), 'Stock quantity', 0, minimum=0),
        'reorder': parse_int(request.form.get('reorder_level'), 'Reorder level', 5, minimum=0),
        'warranty': parse_int(request.form.get('warranty_months'), 'Warranty months', 12, minimum=0, maximum=240),
        'description': request.form.get('description', '').strip(),
    }


@app.route('/products/add', methods=['POST'])
@login_required
@roles_required('Admin', 'Manager', 'Shop Owner')
def product_add():
    v = _product_form_values()

    try:
        with db.transaction() as tx:
            if not tx.query_one("SELECT category_id FROM CATEGORY WHERE category_id = %s", (v['category_id'],)):
                flash('Selected category does not exist.', 'danger')
                return redirect(url_for('products'))
            if tx.query_one("SELECT product_id FROM PRODUCT WHERE product_code = %s", (v['code'],)):
                flash(f'Product SKU "{v["code"]}" already exists in the system.', 'warning')
                return redirect(url_for('products'))

            tx.execute("""
                INSERT INTO PRODUCT 
                (product_code, product_name, category_id, brand, model, hsn_code, tagline, is_new, cost_price, selling_price, stock_quantity, reorder_level, warranty_months, description)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (v['code'], v['name'], v['category_id'], v['brand'], v['model'], v['hsn_code'], v['tagline'],
                  v['is_new'], v['cost_price'], v['selling_price'], v['stock'], v['reorder'], v['warranty'], v['description']))
            new_id = tx.lastrowid
            if v['stock'] > 0:
                tx.execute("""
                    INSERT INTO STOCK_MOVEMENT (product_id, movement_type, quantity, reason, reference_id, notes)
                    VALUES (%s, 'IN', %s, 'Initial Addition', 'PROD-ADD', 'New product catalog entry')
                """, (new_id, v['stock']))

        log_audit('CREATE_PRODUCT', 'Catalog', f"Created product {v['name']} ({v['code']})")
        flash(f'Product "{v["name"]}" added successfully.', 'success')
    except Exception as e:
        flash(f'Error adding product: {_public_error(e)}', 'danger')

    return redirect(url_for('products'))


@app.route('/products/edit/<int:product_id>', methods=['POST'])
@login_required
@roles_required('Admin', 'Manager', 'Shop Owner')
def product_edit(product_id):
    v = _product_form_values()

    try:
        with db.transaction() as tx:
            old = tx.query_one("SELECT * FROM PRODUCT WHERE product_id = %s", (product_id,))
            if not old:
                flash('Product not found.', 'danger')
                return redirect(url_for('products'))
            if tx.query_one("SELECT product_id FROM PRODUCT WHERE product_code = %s AND product_id != %s", (v['code'], product_id)):
                flash(f'Product code "{v["code"]}" is in use by another item.', 'warning')
                return redirect(url_for('products'))
            if not tx.query_one("SELECT category_id FROM CATEGORY WHERE category_id = %s", (v['category_id'],)):
                flash('Selected category does not exist.', 'danger')
                return redirect(url_for('products'))

            tx.execute("""
                UPDATE PRODUCT
                SET product_code = %s, product_name = %s, category_id = %s, brand = %s, model = %s,
                    hsn_code = %s, tagline = %s, is_new = %s, cost_price = %s, selling_price = %s,
                    stock_quantity = %s, reorder_level = %s, warranty_months = %s, description = %s
                WHERE product_id = %s
            """, (v['code'], v['name'], v['category_id'], v['brand'], v['model'], v['hsn_code'], v['tagline'],
                  v['is_new'], v['cost_price'], v['selling_price'], v['stock'], v['reorder'], v['warranty'],
                  v['description'], product_id))

            # A stock change made through the edit form is now recorded in the audit trail.
            if v['stock'] != old['stock_quantity']:
                diff = abs(v['stock'] - old['stock_quantity'])
                tx.execute("""
                    INSERT INTO STOCK_MOVEMENT (product_id, movement_type, quantity, reason, reference_id, notes)
                    VALUES (%s, %s, %s, 'Manual Adjustment', 'PROD-EDIT', %s)
                """, (product_id, 'IN' if v['stock'] > old['stock_quantity'] else 'OUT', diff,
                      f"Stock edited in product form: {old['stock_quantity']} -> {v['stock']}"))

        log_audit('UPDATE_PRODUCT', 'Catalog', f"Updated product {v['name']} (#{product_id})")
        flash(f'Product "{v["name"]}" updated successfully.', 'success')
    except Exception as e:
        flash(f'Error updating product: {_public_error(e)}', 'danger')

    return redirect(url_for('products'))


@app.route('/products/delete/<int:product_id>', methods=['POST'])
@login_required
@roles_required('Admin', 'Manager', 'Shop Owner')
def product_delete(product_id):
    try:
        with db.transaction() as tx:
            for table, label in (('SALE_ITEM', 'historical invoice sales'),
                                 ('PURCHASE_ORDER_ITEM', 'purchase order'),
                                 ('QUOTATION_ITEM', 'quotation'),
                                 ('WARRANTY_CLAIM', 'warranty claim')):
                ref = tx.query_one(f"SELECT COUNT(*) AS cnt FROM {table} WHERE product_id = %s", (product_id,))
                if ref and ref['cnt'] > 0:
                    flash(f'Cannot delete product: {ref["cnt"]} {label} records exist.', 'warning')
                    return redirect(url_for('products'))

            # Both deletes succeed together or not at all (the audit trail is no
            # longer lost when the product delete is rejected).
            tx.execute("DELETE FROM STOCK_MOVEMENT WHERE product_id = %s", (product_id,))
            tx.execute("DELETE FROM PRODUCT WHERE product_id = %s", (product_id,))

        log_audit('DELETE_PRODUCT', 'Catalog', f"Deleted product #{product_id}")
        flash('Product deleted successfully.', 'success')
    except Exception as e:
        flash(f'Failed to delete product: {_public_error(e)}', 'danger')

    return redirect(url_for('products'))


def _csv_norm(row):
    """Normalise CSV headers so exported files can be re-imported
    ('Product Name', 'Selling Price', 'Stock Qty' ... and the short names both work)."""
    return {re.sub(r'[^a-z0-9]', '', (k or '').lower()): (v or '').strip() for k, v in row.items()}


def _csv_pick(norm, *names):
    for n in names:
        if n in norm and norm[n] != '':
            return norm[n]
    return None


@app.route('/products/import-csv', methods=['POST'])
@login_required
@roles_required('Admin', 'Manager', 'Shop Owner')
def products_import_csv():
    """Bulk import/update products via CSV (also accepts files produced by Export CSV)."""
    if 'file' not in request.files:
        flash('No CSV file uploaded.', 'danger')
        return redirect(url_for('products'))

    file = request.files['file']
    if not (file.filename or '').lower().endswith('.csv'):
        flash('Please upload a valid .csv file.', 'danger')
        return redirect(url_for('products'))

    try:
        text = file.stream.read().decode('utf-8-sig')   # handles the BOM Excel adds
    except UnicodeDecodeError:
        flash('CSV must be UTF-8 encoded.', 'danger')
        return redirect(url_for('products'))

    imported, skipped, problems = 0, 0, []
    try:
        with db.transaction() as tx:
            first_cat = tx.query_one("SELECT category_id FROM CATEGORY ORDER BY category_id ASC LIMIT 1")
            reader = csv.DictReader(io.StringIO(text, newline=None))
            for line_no, row in enumerate(reader, start=2):
                n = _csv_norm(row)
                code = (_csv_pick(n, 'sku', 'productcode') or '').upper()
                name = _csv_pick(n, 'name', 'productname')
                if not code or not name:
                    continue
                try:
                    cat_name = _csv_pick(n, 'category')
                    if cat_name:
                        cat = tx.query_one("SELECT category_id FROM CATEGORY WHERE LOWER(category_name) = %s", (cat_name.lower(),)) \
                              or tx.query_one("SELECT category_id FROM CATEGORY WHERE category_name LIKE %s", (f"%{cat_name}%",))
                        if not cat:
                            raise InputError(f"unknown category '{cat_name}'")
                        cid = cat['category_id']
                    else:
                        cid = None
                    brand = _csv_pick(n, 'brand')
                    model = _csv_pick(n, 'model')
                    hsn = _csv_pick(n, 'hsn', 'hsncode')
                    cost = parse_float(_csv_pick(n, 'cost', 'costprice'), 'Cost', 0.0, minimum=0.0)
                    price = parse_float(_csv_pick(n, 'price', 'sellingprice'), 'Price', 0.0, minimum=0.0)
                    stock_raw = _csv_pick(n, 'stock', 'stockqty', 'stockquantity')
                    stock = parse_int(stock_raw, 'Stock', 0, minimum=0) if stock_raw is not None else None
                    reorder = parse_int(_csv_pick(n, 'reorder', 'reorderlevel'), 'Reorder', 5, minimum=0)
                    warranty = parse_int(_csv_pick(n, 'warranty', 'warrantymonths'), 'Warranty', 12, minimum=0, maximum=240)

                    existing = tx.query_one("SELECT * FROM PRODUCT WHERE product_code = %s", (code,))
                    if existing:
                        new_stock = existing['stock_quantity'] if stock is None else stock
                        tx.execute("""
                            UPDATE PRODUCT SET product_name = %s, category_id = %s, brand = %s, model = %s, hsn_code = %s,
                                   cost_price = %s, selling_price = %s, stock_quantity = %s, reorder_level = %s, warranty_months = %s
                            WHERE product_id = %s
                        """, (name, cid or existing['category_id'], brand or existing['brand'], model if model is not None else existing['model'],
                              hsn or existing['hsn_code'], cost, price, new_stock, reorder, warranty, existing['product_id']))
                        if new_stock != existing['stock_quantity']:
                            tx.execute("""
                                INSERT INTO STOCK_MOVEMENT (product_id, movement_type, quantity, reason, reference_id, notes)
                                VALUES (%s, %s, %s, 'Manual Adjustment', 'CSV-IMPORT', 'Stock set by CSV import')
                            """, (existing['product_id'], 'IN' if new_stock > existing['stock_quantity'] else 'OUT',
                                  abs(new_stock - existing['stock_quantity'])))
                    else:
                        new_stock = stock or 0
                        tx.execute("""
                            INSERT INTO PRODUCT (product_code, product_name, category_id, brand, model, hsn_code, cost_price, selling_price, stock_quantity, reorder_level, warranty_months)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (code, name, cid or first_cat['category_id'], brand or 'Generic', model or '', hsn or '8517',
                              cost, price, new_stock, reorder, warranty))
                        if new_stock > 0:
                            tx.execute("""
                                INSERT INTO STOCK_MOVEMENT (product_id, movement_type, quantity, reason, reference_id, notes)
                                VALUES (%s, 'IN', %s, 'Initial Addition', 'CSV-IMPORT', 'Created by CSV import')
                            """, (tx.lastrowid, new_stock))
                    imported += 1
                except InputError as ie:
                    skipped += 1
                    if len(problems) < 3:
                        problems.append(f"line {line_no}: {ie}")

        log_audit('CSV_IMPORT', 'Catalog', f"Imported {imported} products from CSV ({skipped} skipped)")
        msg = f'Successfully imported/updated {imported} products from CSV.'
        if skipped:
            msg += f" {skipped} row(s) skipped ({'; '.join(problems)})."
        flash(msg, 'success' if not skipped else 'warning')
    except Exception as e:
        flash(f'Error processing CSV file: {_public_error(e)}', 'danger')

    return redirect(url_for('products'))


@app.route('/products/export.csv')
@login_required
def products_export_csv():
    """Export current products catalog to CSV."""
    products_list = db.query("""
        SELECT p.product_code, p.product_name, c.category_name, p.brand, p.model,
               p.hsn_code, p.cost_price, p.selling_price, p.stock_quantity, p.reorder_level, p.warranty_months
        FROM PRODUCT p
        JOIN CATEGORY c ON p.category_id = c.category_id
        ORDER BY p.product_code ASC
    """)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['SKU', 'Product Name', 'Category', 'Brand', 'Model', 'HSN', 'Cost Price', 'Selling Price', 'Stock Qty', 'Reorder Level', 'Warranty Months'])
    for p in products_list:
        writer.writerow([p['product_code'], p['product_name'], p['category_name'], p['brand'], p['model'], p['hsn_code'], p['cost_price'], p['selling_price'], p['stock_quantity'], p['reorder_level'], p['warranty_months']])
    return Response(output.getvalue(), mimetype="text/csv", headers={"Content-disposition": "attachment; filename=electrodesk_products.csv"})


# ==========================================================
# STEP 1: CATEGORIES (2-COLUMN GRID CARDS & CRUD)
# ==========================================================

@app.route('/categories')
@login_required
def categories():
    categories_list = db.query("""
        SELECT c.*,
            COALESCE(COUNT(p.product_id), 0) as product_count,
            COALESCE(SUM(p.stock_quantity), 0) as units_count,
            COALESCE(SUM(p.stock_quantity * p.selling_price), 0.0) as stock_value
        FROM CATEGORY c
        LEFT JOIN PRODUCT p ON c.category_id = p.category_id
        GROUP BY c.category_id, c.category_code, c.category_name, c.description, c.icon, c.created_at
        ORDER BY c.category_code ASC
    """)
    inv_totals = get_inventory_derived_totals()

    return render_template('categories.html',
                           categories=categories_list,
                           inv_totals=inv_totals)


@app.route('/categories/add', methods=['POST'])
@login_required
@roles_required('Admin', 'Manager', 'Shop Owner')
def category_add():
    code = request.form.get('category_code', '').strip().upper()
    name = request.form.get('category_name', '').strip()
    icon = request.form.get('icon', 'bi-box-seam').strip()
    description = request.form.get('description', '').strip()

    if not code:
        cat_count = db.query_one("SELECT COUNT(*) as count FROM CATEGORY")['count']
        code = f"CAT-{cat_count + 1:02d}"

    try:
        db.execute("""
            INSERT INTO CATEGORY (category_code, category_name, icon, description)
            VALUES (%s, %s, %s, %s)
        """, (code, name, icon, description))
        log_audit('CREATE_CATEGORY', 'Catalog', f"Created category {name} ({code})")
        flash(f'Category "{name}" created successfully.', 'success')
    except Exception as e:
        flash(f'Error creating category: {_public_error(e)}', 'danger')

    return redirect(url_for('categories'))


@app.route('/categories/edit/<int:category_id>', methods=['POST'])
@login_required
@roles_required('Admin', 'Manager', 'Shop Owner')
def category_edit(category_id):
    code = request.form.get('category_code', '').strip().upper()
    name = request.form.get('category_name', '').strip()
    icon = request.form.get('icon', 'bi-box-seam').strip()
    description = request.form.get('description', '').strip()

    try:
        db.execute("""
            UPDATE CATEGORY 
            SET category_code = %s, category_name = %s, icon = %s, description = %s
            WHERE category_id = %s
        """, (code, name, icon, description, category_id))
        log_audit('UPDATE_CATEGORY', 'Catalog', f"Updated category {name} (#{category_id})")
        flash(f'Category "{name}" updated successfully.', 'success')
    except Exception as e:
        flash(f'Error updating category: {_public_error(e)}', 'danger')

    return redirect(url_for('categories'))


@app.route('/categories/delete/<int:category_id>', methods=['POST'])
@login_required
@roles_required('Admin', 'Manager', 'Shop Owner')
def category_delete(category_id):
    products_count = db.query_one("SELECT COUNT(*) as count FROM PRODUCT WHERE category_id = %s", (category_id,))
    if products_count and products_count['count'] > 0:
        flash(f'Cannot delete category: {products_count["count"]} products are currently assigned to it.', 'warning')
        return redirect(url_for('categories'))

    try:
        db.execute("DELETE FROM CATEGORY WHERE category_id = %s", (category_id,))
        log_audit('DELETE_CATEGORY', 'Catalog', f"Deleted category #{category_id}")
        flash('Category deleted successfully.', 'success')
    except Exception as e:
        flash(f'Error deleting category: {_public_error(e)}', 'danger')

    return redirect(url_for('categories'))


# ==========================================================
# STEP 1: INVENTORY & STOCK MOVEMENTS AUDIT
# ==========================================================

@app.route('/inventory')
@login_required
def inventory():
    filter_type = request.args.get('filter', 'all')
    category_id = request.args.get('category', '')

    query = """
        SELECT p.*, c.category_name 
        FROM PRODUCT p
        JOIN CATEGORY c ON p.category_id = c.category_id
        WHERE 1=1
    """
    params = []

    if category_id:
        query += " AND p.category_id = %s"
        params.append(category_id)

    if filter_type == 'low':
        query += " AND p.stock_quantity <= p.reorder_level AND p.stock_quantity > 0"
    elif filter_type == 'out':
        query += " AND p.stock_quantity = 0"
    elif filter_type == 'in':
        query += " AND p.stock_quantity > p.reorder_level"

    query += " ORDER BY p.stock_quantity ASC"

    inventory_items = db.query(query, tuple(params) if params else None)
    categories = db.query("SELECT * FROM CATEGORY ORDER BY category_name ASC")
    valuation = get_inventory_derived_totals()

    # Recent stock movements log
    recent_movements = db.query("""
        SELECT sm.*, p.product_name, p.product_code 
        FROM STOCK_MOVEMENT sm
        JOIN PRODUCT p ON sm.product_id = p.product_id
        ORDER BY sm.movement_id DESC
        LIMIT 15
    """)

    return render_template('inventory.html',
                           inventory=inventory_items,
                           categories=categories,
                           valuation=valuation,
                           recent_movements=recent_movements,
                           current_filter=filter_type,
                           selected_category=category_id)


@app.route('/inventory/adjust', methods=['POST'])
@login_required
@roles_required('Admin', 'Manager', 'Shop Owner')
def inventory_adjust():
    product_id = parse_int(request.form.get('product_id'), 'Product', 0, minimum=0)
    adj_type = request.form.get('type')  # 'add', 'deduct', 'set'
    quantity = parse_int(request.form.get('quantity'), 'Quantity', -1)

    notes = request.form.get('notes', '').strip()
    if not notes:
        notes = 'Restock Inventory' if adj_type == 'add' else 'Physical Audit Adjustment'

    # "Set" may legitimately be 0 (physical audit finds nothing on the shelf).
    minimum_ok = 0 if adj_type == 'set' else 1
    if quantity < minimum_ok:
        flash('Please enter a valid quantity greater than zero.' if adj_type != 'set'
              else 'Please enter a valid stock count (0 or more).', 'warning')
        return redirect(request.referrer if is_safe_redirect(request.referrer) else url_for('inventory'))

    if adj_type not in ('add', 'deduct', 'set'):
        flash('Invalid adjustment type.', 'danger')
        return redirect(request.referrer if is_safe_redirect(request.referrer) else url_for('inventory'))

    back = request.referrer if is_safe_redirect(request.referrer) else url_for('inventory')
    try:
        with db.transaction() as tx:
            product = tx.query_one("SELECT * FROM PRODUCT WHERE product_id = %s", (product_id,))
            if not product:
                flash('Product not found.', 'danger')
                return redirect(back)

            current_stock = product['stock_quantity']
            if adj_type == 'add':
                new_stock, m_type, diff = current_stock + quantity, 'IN', quantity
            elif adj_type == 'deduct':
                new_stock, m_type, diff = max(0, current_stock - quantity), 'OUT', min(quantity, current_stock)
            else:
                new_stock = quantity
                diff = abs(quantity - current_stock)
                m_type = 'IN' if quantity >= current_stock else 'OUT'

            if diff == 0:
                flash(f"Stock for '{product['product_name']}' is already {current_stock} units - no change needed.", 'info')
                return redirect(back)

            tx.execute("UPDATE PRODUCT SET stock_quantity = %s WHERE product_id = %s", (new_stock, product_id))
            tx.execute("""
                INSERT INTO STOCK_MOVEMENT (product_id, movement_type, quantity, reason, reference_id, notes)
                VALUES (%s, %s, %s, 'Manual Adjustment', 'ADJ-MANUAL', %s)
            """, (product_id, m_type, diff, notes))

        log_audit('STOCK_ADJUST', 'Inventory', f"Adjusted {product['product_name']}: {current_stock} -> {new_stock} ({notes})")
        flash(f"Stock for '{product['product_name']}' successfully updated to {new_stock} units.", 'success')
    except Exception as e:
        flash(f'Error adjusting stock: {_public_error(e)}', 'danger')

    return redirect(back)


# ==========================================================
# STEP 1: CUSTOMERS (CRM & CRUD)
# ==========================================================

@app.route('/customers')
@login_required
def customers():
    search = request.args.get('search', '').strip()
    query = """
        SELECT c.*,
               COALESCE(COUNT(s.sale_id), 0) as total_orders,
               COALESCE(SUM(s.grand_total), 0.0) as total_spent,
               COALESCE(SUM(s.balance_due), 0.0) as total_dues
        FROM CUSTOMER c
        LEFT JOIN SALE s ON c.customer_id = s.customer_id
        WHERE 1=1
    """
    params = []
    if search:
        query += " AND (c.customer_name LIKE %s OR c.phone LIKE %s OR c.city LIKE %s)"
        s = f"%{search}%"
        params.extend([s, s, s])

    query += " GROUP BY c.customer_id ORDER BY c.customer_name ASC"
    customers_list = db.query(query, tuple(params) if params else None)

    return render_template('customers.html', customers=customers_list, search=search)


@app.route('/customers/add', methods=['POST'])
@login_required
def customer_add():
    name = request.form.get('customer_name', '').strip()
    phone = request.form.get('phone', '').strip()
    email = request.form.get('email', '').strip()
    city = request.form.get('city', 'Hyderabad').strip()
    address = request.form.get('address', '').strip()

    if not name or not phone:
        flash('Customer name and phone number are required.', 'danger')
        return redirect(url_for('customers'))

    existing = db.query_one("SELECT customer_id FROM CUSTOMER WHERE phone = %s", (phone,))
    if existing:
        flash(f'Customer with phone {phone} already exists.', 'warning')
        return redirect(url_for('customer_detail', customer_id=existing['customer_id']))

    try:
        db.execute("""
            INSERT INTO CUSTOMER (customer_name, phone, email, city, address)
            VALUES (%s, %s, %s, %s, %s)
        """, (name, phone, email, city, address))
        log_audit('CREATE_CUSTOMER', 'CRM', f"Created customer {name} ({phone})")
        flash(f'Customer "{name}" registered successfully.', 'success')
    except Exception as e:
        flash(f'Error adding customer: {_public_error(e)}', 'danger')

    return redirect(url_for('customers'))


@app.route('/customers/<int:customer_id>')
@login_required
def customer_detail(customer_id):
    customer = db.query_one("SELECT * FROM CUSTOMER WHERE customer_id = %s", (customer_id,))
    if not customer:
        flash('Customer not found.', 'danger')
        return redirect(url_for('customers'))

    today = get_app_today()
    purchases = db.query("""
        SELECT s.*, u.full_name as staff_name,
               (SELECT COUNT(*) FROM SALE_ITEM si WHERE si.sale_id = s.sale_id) as item_count
        FROM SALE s
        LEFT JOIN USER u ON s.user_id = u.user_id
        WHERE s.customer_id = %s
        ORDER BY s.sale_date DESC
    """, (customer_id,))

    warranties = db.query("""
        SELECT si.*, p.product_name, p.product_code, p.brand, s.invoice_number, s.sale_date
        FROM SALE_ITEM si
        JOIN PRODUCT p ON si.product_id = p.product_id
        JOIN SALE s ON si.sale_id = s.sale_id
        WHERE s.customer_id = %s AND si.warranty_expiry_date IS NOT NULL
        ORDER BY si.warranty_expiry_date DESC
    """, (customer_id,))

    payments = db.query("SELECT * FROM CUSTOMER_PAYMENT WHERE customer_id = %s ORDER BY payment_date DESC", (customer_id,))

    return render_template('customer_detail.html',
                           customer=customer,
                           purchases=purchases,
                           warranties=warranties,
                           payments=payments)


@app.route('/customers/edit/<int:customer_id>', methods=['POST'])
@login_required
def customer_edit(customer_id):
    name = request.form.get('customer_name', '').strip()
    phone = request.form.get('phone', '').strip()
    email = request.form.get('email', '').strip()
    city = request.form.get('city', '').strip()
    address = request.form.get('address', '').strip()

    try:
        db.execute("""
            UPDATE CUSTOMER 
            SET customer_name = %s, phone = %s, email = %s, city = %s, address = %s
            WHERE customer_id = %s
        """, (name, phone, email, city, address, customer_id))
        log_audit('UPDATE_CUSTOMER', 'CRM', f"Updated customer {name} (#{customer_id})")
        flash(f'Customer "{name}" updated successfully.', 'success')
    except Exception as e:
        flash(f'Error updating customer: {_public_error(e)}', 'danger')

    return redirect(url_for('customers'))


@app.route('/customers/delete/<int:customer_id>', methods=['POST'])
@login_required
@roles_required('Admin', 'Shop Owner')
def customer_delete(customer_id):
    try:
        db.execute("UPDATE SALE SET customer_id = NULL WHERE customer_id = %s", (customer_id,))
        db.execute("DELETE FROM CUSTOMER WHERE customer_id = %s", (customer_id,))
        log_audit('DELETE_CUSTOMER', 'CRM', f"Deleted customer #{customer_id}")
        flash('Customer record deleted successfully.', 'success')
    except Exception as e:
        flash(f'Error deleting customer: {_public_error(e)}', 'danger')

    return redirect(url_for('customers'))


# ==========================================================
# STEP 2: NEW SALE (POS, EMI, EXCHANGE, SERIALS, DISCOUNTS)
# ==========================================================

def get_emi_plans():
    """EMI plans from config, with interest rates overridden by Settings (STORE_SETTING)."""
    plans = {k: dict(v) for k, v in config.EMI_PLANS.items()}
    try:
        rows = db.query("SELECT setting_key, setting_value FROM STORE_SETTING WHERE setting_key LIKE 'emi_rate_%'")
        for r in rows:
            m = re.fullmatch(r'emi_rate_(\d+)m', r['setting_key'])
            if not m:
                continue
            months = int(m.group(1))
            rate = float(r['setting_value'])
            if months in plans and 0.0 <= rate <= 60.0:
                plans[months]['interest_rate'] = rate
                plans[months]['label'] = re.sub(
                    r'\(\s*[\d.]+%( p\.a\.)?\)',
                    lambda mm: f"({rate:g}%{mm.group(1) or ''})",
                    plans[months]['label'])
    except Exception:
        pass
    return plans


def compute_coupon(code, subtotal):
    """Server-side coupon evaluation. Returns (coupon_dict | None, discount, message)."""
    c = config.ACTIVE_COUPONS.get(code)
    if not c:
        return None, 0.0, 'Invalid coupon code.'
    if 'min_order' in c and subtotal < c['min_order']:
        return None, 0.0, f"Order must be at least ₹{c['min_order']:,.0f} to use this coupon."
    if c['type'] == 'percent':
        discount = round(subtotal * (c['value'] / 100.0), 2)
        if 'max_discount' in c:
            discount = min(discount, float(c['max_discount']))
    else:
        discount = min(subtotal, float(c['value']))
    return c, round(discount, 2), ''


@app.route('/pos')
@login_required
def pos():
    products = db.query("""
        SELECT p.*, c.category_name 
        FROM PRODUCT p
        JOIN CATEGORY c ON p.category_id = c.category_id
        ORDER BY p.product_name ASC
    """)
    # Cost prices are embedded in the page for the POS script; Sales Staff must not see them.
    if session.get('role') in ('Sales Staff', 'Staff'):
        for p in products:
            p.pop('cost_price', None)
    categories = db.query("SELECT * FROM CATEGORY ORDER BY category_code ASC")
    customers = db.query("SELECT * FROM CUSTOMER ORDER BY customer_name ASC")

    return render_template('pos.html',
                           products=products,
                           categories=categories,
                           customers=customers,
                           coupons=config.ACTIVE_COUPONS,
                           emi_plans=get_emi_plans())


@app.route('/api/pos/validate-coupon', methods=['POST'])
@login_required
def pos_validate_coupon():
    data = request.get_json(silent=True) or {}
    code = (data.get('coupon_code') or '').strip().upper()
    subtotal = parse_float(data.get('subtotal'), 'Subtotal', 0.0, minimum=0.0)

    c, discount, message = compute_coupon(code, subtotal)
    if not c:
        return jsonify({'valid': False, 'message': message})

    requires_owner = c['value'] > config.DISCOUNT_APPROVAL_PCT if c['type'] == 'percent' else False
    return jsonify({
        'valid': True,
        'code': code,
        'discount': discount,
        'description': c['description'],
        'requires_owner_approval': requires_owner
    })


class CheckoutError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.message = message
        self.status = status


def _owner_authorised(pin):
    if session.get('role') in ('Shop Owner', 'Owner'):
        return True
    return bool(pin) and hmac.compare_digest(str(pin), str(config.OWNER_APPROVAL_PIN))


@app.route('/api/pos/checkout', methods=['POST'])
@app.route('/pos/checkout', methods=['POST'])
@login_required
def pos_checkout():
    """
    Automatic billing checkout. Everything happens in ONE atomic transaction:
    - Prices, tax, discounts and exchange value are computed on the SERVER
      (client-sent tax_rate / totals are ignored)
    - Quantities must be >= 1; stock is deducted with a guarded UPDATE (no overselling)
    - Mandatory serial numbers for Phones, Laptops, TVs; duplicate serials rejected
    - Discounts > 10% (and very large exchange values) need Owner approval
    - Inserts SALE, SALE_ITEM and STOCK_MOVEMENT - all or nothing
    """
    data = request.get_json(silent=True)
    if not data or not isinstance(data.get('items'), list) or not data['items']:
        return jsonify({'success': False, 'message': 'Cart is empty. Add items to checkout.'}), 400
    if len(data['items']) > 100:
        return jsonify({'success': False, 'message': 'Too many line items in one invoice.'}), 400

    customer_id = data.get('customer_id') or None
    if customer_id is not None:
        customer_id = parse_int(customer_id, 'Customer', minimum=1)
    payment_method = str(data.get('payment_method') or 'Cash').strip()[:30] or 'Cash'
    requested_status = str(data.get('payment_status') or 'Paid').strip()
    manual_discount = parse_float(data.get('discount_amount'), 'Discount', 0.0, minimum=0.0)
    discount_type = str(data.get('discount_type') or 'none').strip()[:20]
    coupon_code = str(data.get('coupon_code') or '').strip().upper()
    exchange_device = str(data.get('exchange_device') or '').strip()[:150]
    exchange_value = parse_float(data.get('exchange_value'), 'Exchange value', 0.0, minimum=0.0)
    emi_months = parse_int(data.get('emi_months'), 'EMI months', 0, minimum=0)
    owner_pin = str(data.get('owner_pin') or '').strip()
    notes = str(data.get('notes') or 'Retail counter sale').strip()[:500]
    upi_ref = str(data.get('upi_ref') or '').strip()[:50]
    card_last4 = str(data.get('card_last4') or '').strip()[:10]
    card_brand = str(data.get('card_brand') or '').strip()[:20]
    card_auth = str(data.get('card_auth') or '').strip()[:30]
    cash_tendered = parse_float(data.get('cash_tendered'), 'Cash tendered', 0.0, minimum=0.0)

    payment_details = []
    if payment_method == 'UPI' and upi_ref:
        payment_details.append(f"UPI Ref: {upi_ref}")
    elif payment_method == 'Card':
        card_desc = f"Card •••• {card_last4}" if card_last4 else "Card Payment"
        if card_brand:
            card_desc += f" ({card_brand})"
        if card_auth:
            card_desc += f" [Auth: {card_auth}]"
        payment_details.append(card_desc)
    elif payment_method == 'Cash' and cash_tendered > 0:
        payment_details.append(f"Cash Tendered: ₹{cash_tendered:,.2f}")

    if payment_details:
        detail_str = " | ".join(payment_details)
        if notes and notes != 'Retail counter sale':
            notes = f"{notes} | {detail_str}"
        else:
            notes = detail_str

    today = get_app_today()

    emi_plans = get_emi_plans()
    if emi_months and emi_months not in emi_plans:
        return jsonify({'success': False, 'message': f'EMI plan of {emi_months} months is not available.'}), 400

    try:
        with db.transaction() as tx:
            if customer_id is not None and not tx.query_one("SELECT customer_id FROM CUSTOMER WHERE customer_id = %s", (customer_id,)):
                raise CheckoutError('Selected customer was not found.')

            subtotal = 0.0
            tax_before_discount = 0.0
            processed_items = []
            used_serials = set()
            reserved = {}

            for it in data['items']:
                if not isinstance(it, dict):
                    raise CheckoutError('Invalid cart item.')
                pid = parse_int(it.get('product_id'), 'Product', minimum=1)
                qty = parse_int(it.get('quantity'), 'Quantity', 1, minimum=1, maximum=1000)
                serial = str(it.get('serial_number') or '').strip().upper()[:100]

                prod = tx.query_one(
                    "SELECT p.*, c.category_name FROM PRODUCT p JOIN CATEGORY c ON p.category_id = c.category_id WHERE p.product_id = %s",
                    (pid,))
                if not prod:
                    raise CheckoutError(f'Product #{pid} not found.')

                reserved[pid] = reserved.get(pid, 0) + qty
                if prod['stock_quantity'] < reserved[pid]:
                    raise CheckoutError(
                        f"Insufficient stock for '{prod['product_name']}'. Available: {prod['stock_quantity']}, Requested: {reserved[pid]}")

                cat_lower = prod['category_name'].lower()
                needs_serial = any(k in cat_lower for k in ['phone', 'laptop', 'tv', 'display', 'tablet'])
                if needs_serial and not serial:
                    raise CheckoutError(f"Serial / IMEI number is strictly required for '{prod['product_name']}'.")

                if serial:
                    if serial in used_serials:
                        raise CheckoutError(f"Duplicate serial number in cart: {serial}")
                    used_serials.add(serial)
                    if tx.query_one("""SELECT si.item_id FROM SALE_ITEM si JOIN SALE s ON s.sale_id = si.sale_id
                                     WHERE UPPER(si.serial_number) = %s AND s.payment_status <> 'Refunded'""", (serial,)):
                        raise CheckoutError(f"Serial number '{serial}' already exists in database records.")

                unit_price = float(prod['selling_price'])
                line_price = round(unit_price * qty, 2)
                subtotal += line_price
                line_rate = float(prod['tax_rate']) if prod.get('tax_rate') is not None else config.DEFAULT_TAX_RATE
                tax_before_discount += line_price * line_rate / 100.0
                processed_items.append({
                    'product': prod, 'quantity': qty, 'unit_price': unit_price,
                    'total_price': line_price, 'serial_number': serial,
                    'warranty_months': int(prod['warranty_months'])
                })

            subtotal = round(subtotal, 2)
            if subtotal <= 0:
                raise CheckoutError('Invoice total must be greater than zero.')

            # ---- Discount (always evaluated server-side) ----
            if coupon_code:
                coupon, discount_amount, message = compute_coupon(coupon_code, subtotal)
                if not coupon:
                    raise CheckoutError(message)
                discount_type = 'coupon'
            else:
                discount_amount = round(min(manual_discount, subtotal), 2)

            discount_pct = (discount_amount / subtotal * 100.0) if subtotal > 0 else 0.0
            owner_approved = 0
            if discount_amount > subtotal * config.DISCOUNT_APPROVAL_PCT / 100.0 + 0.01:
                if _owner_authorised(owner_pin):
                    owner_approved = 1
                else:
                    raise CheckoutError(
                        f"Discounts exceeding {config.DISCOUNT_APPROVAL_PCT:g}% ({discount_pct:.1f}%) require Shop Owner approval PIN.", 403)

            # ---- Exchange / trade-in value ----
            exchange_value = round(min(exchange_value, max(0.0, subtotal - discount_amount)), 2)
            if exchange_value > 0 and exchange_value > subtotal * config.EXCHANGE_APPROVAL_PCT / 100.0 + 0.01:
                if _owner_authorised(owner_pin):
                    owner_approved = 1
                else:
                    raise CheckoutError(
                        f"Exchange value above {config.EXCHANGE_APPROVAL_PCT:g}% of the bill requires Shop Owner approval PIN.", 403)

            # ---- Tax (per-product GST rate on the net taxable value) ----
            taxable_subtotal = round(max(0.0, subtotal - discount_amount - exchange_value), 2)
            tax_amount = round((tax_before_discount / subtotal) * taxable_subtotal, 2)
            cgst_amount = round(tax_amount / 2.0, 2)
            sgst_amount = round(tax_amount - cgst_amount, 2)
            grand_total = round(taxable_subtotal + tax_amount, 2)

            # ---- EMI ----
            emi_interest_rate = 0.0
            emi_monthly = 0.0
            if emi_months > 0:
                emi_interest_rate = float(emi_plans[emi_months]['interest_rate'])
                interest_amt = grand_total * (emi_interest_rate / 100.0) * (emi_months / 12.0)
                emi_monthly = round((grand_total + interest_amt) / emi_months, 2)

            # ---- Payment ledger ----
            if payment_method in ('Pay Later', 'Credit'):
                payment_status, amount_paid = 'Pending', 0.0
            elif requested_status == 'Partial':
                amount_paid = parse_float(data.get('amount_paid'), 'Amount paid', grand_total * 0.5, minimum=0.0)
                amount_paid = round(min(amount_paid, grand_total), 2)
                if amount_paid >= grand_total:
                    payment_status = 'Paid'
                elif amount_paid <= 0:
                    payment_status = 'Pending'
                else:
                    payment_status = 'Partial'
            else:
                payment_status, amount_paid = 'Paid', grand_total
            balance_due = round(max(0.0, grand_total - amount_paid), 2)

            if balance_due > 0 and customer_id is None:
                raise CheckoutError('Select a customer for credit / partial payment sales so the balance can be tracked.')

            # ---- Sequential invoice number (read inside the write-locked transaction) ----
            last_sale = tx.query_one("SELECT invoice_number FROM SALE ORDER BY sale_id DESC LIMIT 1")
            next_seq = 1
            if last_sale and last_sale.get('invoice_number'):
                try:
                    next_seq = int(last_sale['invoice_number'].split('-')[-1]) + 1
                except ValueError:
                    next_seq = 1
            invoice_number = f"INV-{today.year}-{next_seq:04d}"
            while tx.query_one("SELECT sale_id FROM SALE WHERE invoice_number = %s", (invoice_number,)):
                next_seq += 1
                invoice_number = f"INV-{today.year}-{next_seq:04d}"

            sale_datetime = f"{today.strftime('%Y-%m-%d')} {datetime.datetime.now().strftime('%H:%M:%S')}"
            user_id = session.get('user_id')

            tx.execute("""
                INSERT INTO SALE (
                    invoice_number, customer_id, user_id, sale_date,
                    subtotal, cgst_amount, sgst_amount, tax_amount, discount_amount,
                    discount_type, discount_rate, owner_approved,
                    exchange_device, exchange_value, grand_total,
                    payment_method, payment_status, amount_paid, balance_due,
                    emi_months, emi_interest_rate, emi_monthly_amount, notes
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                invoice_number, customer_id, user_id, sale_datetime,
                subtotal, cgst_amount, sgst_amount, tax_amount, discount_amount,
                discount_type, round(discount_pct, 2), owner_approved,
                exchange_device, exchange_value, grand_total,
                payment_method, payment_status, amount_paid, balance_due,
                emi_months, emi_interest_rate, emi_monthly, notes
            ))
            sale_id = tx.lastrowid

            for it in processed_items:
                prod = it['product']
                exp_str = add_months(today, it['warranty_months']).strftime('%Y-%m-%d')
                tx.execute("""
                    INSERT INTO SALE_ITEM (sale_id, product_id, quantity, unit_price, total_price, serial_number, warranty_months, warranty_expiry_date)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (sale_id, prod['product_id'], it['quantity'], it['unit_price'], it['total_price'],
                      it['serial_number'], it['warranty_months'], exp_str))

                # Guarded decrement: fails (and rolls everything back) rather than going negative.
                tx.execute("UPDATE PRODUCT SET stock_quantity = stock_quantity - %s WHERE product_id = %s AND stock_quantity >= %s",
                           (it['quantity'], prod['product_id'], it['quantity']))
                if tx.rowcount != 1:
                    raise CheckoutError(f"Insufficient stock for '{prod['product_name']}'. Please refresh and retry.")
                tx.execute("""
                    INSERT INTO STOCK_MOVEMENT (product_id, movement_type, quantity, reason, reference_id, notes)
                    VALUES (%s, 'OUT', %s, 'Customer Sale', %s, 'POS invoice checkout')
                """, (prod['product_id'], it['quantity'], invoice_number))

    except CheckoutError as ce:
        return jsonify({'success': False, 'message': ce.message}), ce.status
    except InputError as ie:
        return jsonify({'success': False, 'message': str(ie)}), 400
    except Exception as e:
        app.logger.error("Checkout failed: %r", e, exc_info=e)
        return jsonify({'success': False, 'message': 'Checkout failed due to an internal error. No changes were saved.'}), 500

    log_audit('POS_CHECKOUT', 'Sales', f"Completed sale {invoice_number} (Total: ₹{grand_total:,.2f})")
    return jsonify({
        'success': True,
        'message': 'Sale completed successfully.',
        'sale_id': sale_id,
        'invoice_number': invoice_number
    })


# ==========================================================
# INVOICES & BILLING HISTORY (A4 & 80MM THERMAL)
# ==========================================================

@app.route('/invoices')
@login_required
def invoices():
    search = request.args.get('search', '').strip()
    status_filter = request.args.get('status', '').strip()
    date_filter = request.args.get('date', '').strip()

    query = """
        SELECT s.*, c.customer_name, c.phone as customer_phone, u.full_name as staff_name,
               (SELECT COUNT(*) FROM SALE_ITEM si WHERE si.sale_id = s.sale_id) as total_items
        FROM SALE s
        LEFT JOIN CUSTOMER c ON s.customer_id = c.customer_id
        LEFT JOIN USER u ON s.user_id = u.user_id
        WHERE 1=1
    """
    params = []
    if search:
        query += " AND (s.invoice_number LIKE %s OR c.customer_name LIKE %s OR c.phone LIKE %s)"
        s = f"%{search}%"
        params.extend([s, s, s])

    if status_filter:
        query += " AND s.payment_status = %s"
        params.append(status_filter)

    if date_filter:
        query += " AND DATE(s.sale_date) = %s"
        params.append(date_filter)

    query += " ORDER BY s.sale_id DESC"
    invoices_list = db.query(query, tuple(params) if params else None)

    return render_template('invoices_list.html',
                           invoices=invoices_list,
                           search=search,
                           status_filter=status_filter,
                           date_filter=date_filter)


@app.route('/invoice/<int:sale_id>')
@login_required
def invoice_view(sale_id):
    sale = db.query_one("""
        SELECT s.*, c.customer_name, c.phone as customer_phone, c.email as customer_email,
               c.address as customer_address, c.city as customer_city,
               u.full_name as staff_name, u.role as staff_role
        FROM SALE s
        LEFT JOIN CUSTOMER c ON s.customer_id = c.customer_id
        LEFT JOIN USER u ON s.user_id = u.user_id
        WHERE s.sale_id = %s
    """, (sale_id,))

    if not sale:
        flash('Invoice not found.', 'danger')
        return redirect(url_for('invoices'))

    items = db.query("""
        SELECT si.*, p.product_name, p.product_code, p.brand, p.model, p.hsn_code
        FROM SALE_ITEM si
        JOIN PRODUCT p ON si.product_id = p.product_id
        WHERE si.sale_id = %s
        ORDER BY si.item_id ASC
    """, (sale_id,))

    is_thermal = request.args.get('format') == 'thermal'

    return render_template('invoice.html',
                           sale=sale,
                           items=items,
                           is_thermal=is_thermal)


# ==========================================================
# STEP 3: WARRANTY TRACKING CENTER (4 KPIS, TABS, CLAIMS)
# ==========================================================

@app.route('/warranty')
@login_required
def warranty():
    today = get_app_today()
    tab = request.args.get('tab', 'all').lower()
    search = request.args.get('search', '').strip()
    category_id = request.args.get('category', '').strip()
    brand_filter = request.args.get('brand', '').strip()
    sort_by = request.args.get('sort', 'expiry_asc').strip()

    # Query all warranty items
    query = """
        SELECT 
            si.item_id, si.serial_number, si.warranty_months, si.warranty_expiry_date,
            p.product_id, p.product_name, p.product_code, p.brand, p.model,
            c.category_id, c.category_name,
            s.sale_id, s.invoice_number, s.sale_date,
            cust.customer_id, cust.customer_name, cust.phone as customer_phone,
            (SELECT wc.claim_id FROM WARRANTY_CLAIM wc 
             WHERE wc.item_id = si.item_id OR (wc.serial_number = si.serial_number AND si.serial_number IS NOT NULL AND si.serial_number != '') 
             ORDER BY wc.claim_id DESC LIMIT 1) as claim_id,
            (SELECT wc.status FROM WARRANTY_CLAIM wc 
             WHERE wc.item_id = si.item_id OR (wc.serial_number = si.serial_number AND si.serial_number IS NOT NULL AND si.serial_number != '') 
             ORDER BY wc.claim_id DESC LIMIT 1) as claim_status
        FROM SALE_ITEM si
        JOIN PRODUCT p ON si.product_id = p.product_id
        JOIN CATEGORY c ON p.category_id = c.category_id
        JOIN SALE s ON si.sale_id = s.sale_id
        LEFT JOIN CUSTOMER cust ON s.customer_id = cust.customer_id
        WHERE si.warranty_expiry_date IS NOT NULL
    """
    params = []

    if search:
        query += " AND (si.serial_number LIKE %s OR s.invoice_number LIKE %s OR p.product_name LIKE %s OR cust.customer_name LIKE %s OR cust.phone LIKE %s)"
        s = f"%{search}%"
        params.extend([s, s, s, s, s])

    if category_id:
        query += " AND p.category_id = %s"
        params.append(category_id)

    if brand_filter:
        query += " AND p.brand = %s"
        params.append(brand_filter)

    sort_sql = {
        'expiry_asc': 'si.warranty_expiry_date ASC',
        'expiry_desc': 'si.warranty_expiry_date DESC',
        'serial': 'si.serial_number ASC',
        'product': 'p.product_name ASC'
    }
    query += " ORDER BY " + sort_sql.get(sort_by, 'si.warranty_expiry_date ASC')

    raw_items = db.query(query, tuple(params) if params else None)

    # Classify warranty status & calculate exact KPI totals
    active_count = 0
    expiring_count = 0
    expired_count = 0
    processed_items = []

    for item in raw_items:
        exp_d = datetime.datetime.strptime(item['warranty_expiry_date'][:10], '%Y-%m-%d').date()
        days_left = (exp_d - today).days
        item['days_left'] = days_left

        if days_left < 0:
            item['status'] = 'Expired'
            item['badge_class'] = 'bg-secondary'
            item['days_class'] = 'text-danger fw-bold'
            expired_count += 1
        elif days_left <= 30:
            item['status'] = 'Expiring Soon'
            item['badge_class'] = 'bg-warning text-dark'
            item['days_class'] = 'text-warning-emphasis fw-bold'
            expiring_count += 1
        else:
            item['status'] = 'Active'
            item['badge_class'] = 'bg-success'
            item['days_class'] = 'text-success fw-bold'
            active_count += 1

        # Apply Tab Filtering
        if tab == 'active' and item['status'] != 'Active':
            continue
        elif tab == 'expiring' and item['status'] != 'Expiring Soon':
            continue
        elif tab == 'expired' and item['status'] != 'Expired':
            continue

        processed_items.append(item)

    # 4th KPI: Open Claims
    claims_count = db.query_one("SELECT COUNT(*) as count FROM WARRANTY_CLAIM WHERE status IN ('Open', 'In Review')")['count']
    open_claims = db.query("""
        SELECT wc.*, cust.customer_name, cust.phone, p.product_name, p.product_code
        FROM WARRANTY_CLAIM wc
        LEFT JOIN CUSTOMER cust ON wc.customer_id = cust.customer_id
        LEFT JOIN PRODUCT p ON wc.product_id = p.product_id
        ORDER BY wc.claim_id DESC
    """)

    categories = db.query("SELECT * FROM CATEGORY ORDER BY category_name ASC")
    brands = db.query("SELECT DISTINCT brand FROM PRODUCT ORDER BY brand ASC")

    return render_template('warranty.html',
                           warranties=processed_items,
                           active_count=active_count,
                           expiring_count=expiring_count,
                           expired_count=expired_count,
                           claims_count=claims_count,
                           open_claims=open_claims,
                           current_tab=tab,
                           search=search,
                           selected_category=category_id,
                           selected_brand=brand_filter,
                           current_sort=sort_by,
                           categories=categories,
                           brands=brands)


@app.route('/warranty/claim/add', methods=['POST'], endpoint='warranty_claim_register')
@app.route('/warranty/claim/add', methods=['POST'], endpoint='warranty_claim_add')
@login_required
def warranty_claim_add():
    item_id = request.form.get('item_id')
    serial = request.form.get('serial_number', '').strip().upper()
    claim_type = request.form.get('claim_type', 'Manufacturer Service').strip()
    issue = request.form.get('issue_description', '') or request.form.get('claim_reason', '')
    issue = issue.strip()
    today = get_app_today()

    item = None
    if item_id:
        item = db.query_one("""
            SELECT si.*, s.customer_id 
            FROM SALE_ITEM si 
            JOIN SALE s ON si.sale_id = s.sale_id
            WHERE si.item_id = %s
        """, (item_id,))
        if item and not serial:
            serial = (item.get('serial_number') or '').upper()

    if not item and serial:
        item = db.query_one("""
            SELECT si.*, s.customer_id 
            FROM SALE_ITEM si 
            JOIN SALE s ON si.sale_id = s.sale_id
            WHERE UPPER(si.serial_number) = %s
        """, (serial,))

    if not item:
        flash(f"No warranty record found for serial/item '{serial or item_id}'.", 'danger')
        return redirect(url_for('warranty'))

    claim_num = f"CLM-{today.year}-{db.query_one('SELECT COUNT(*) as c FROM WARRANTY_CLAIM')['c'] + 1:04d}"
    full_desc = f"[{claim_type}] {issue}" if claim_type else issue

    try:
        db.execute("""
            INSERT INTO WARRANTY_CLAIM (claim_number, item_id, serial_number, customer_id, product_id, claim_date, issue_description, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'Open')
        """, (claim_num, item['item_id'], serial, item.get('customer_id'), item['product_id'], today.strftime('%Y-%m-%d'), full_desc))
        log_audit('WARRANTY_CLAIM', 'Warranty', f"Registered claim {claim_num} for serial {serial}")
        flash(f"Warranty claim {claim_num} registered successfully.", 'success')
    except Exception as e:
        flash(f"Error registering claim: {_public_error(e)}", 'danger')

    return redirect(url_for('warranty', tab='claims'))


@app.route('/warranty/claim/update/<int:claim_id>', methods=['POST'])
@login_required
@roles_required('Admin', 'Manager', 'Shop Owner', 'Sales Staff')
def warranty_claim_update(claim_id):
    status = request.form.get('status', 'In Review').strip()
    resolution_notes = request.form.get('resolution_notes', '').strip()
    claim = db.query_one("SELECT * FROM WARRANTY_CLAIM WHERE claim_id = %s", (claim_id,))
    if not claim:
        flash('Claim record not found.', 'danger')
        return redirect(url_for('warranty', tab='claims'))

    try:
        resolved_at = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') if status in ('Resolved', 'Closed') else None
        db.execute("""
            UPDATE WARRANTY_CLAIM 
            SET status = %s, resolution_notes = %s, resolved_at = COALESCE(%s, resolved_at) 
            WHERE claim_id = %s
        """, (status, resolution_notes, resolved_at, claim_id))
        log_audit('WARRANTY_CLAIM_UPDATE', 'Warranty', f"Updated claim {claim['claim_number']} to {status}")
        flash(f"Claim {claim['claim_number']} status updated to '{status}'.", 'success')
    except Exception as e:
        flash(f"Error updating claim: {_public_error(e)}", 'danger')

    return redirect(url_for('warranty', tab='claims'))


@app.route('/warranty/renew/<int:item_id>', methods=['POST'])
@login_required
@roles_required('Admin', 'Manager', 'Shop Owner')
def warranty_renew(item_id):
    months = parse_int(request.form.get('months'), 'Renewal months', 12, minimum=1, maximum=120)
    today = get_app_today()
    item = db.query_one("SELECT * FROM SALE_ITEM WHERE item_id = %s", (item_id,))
    if not item:
        flash('Warranty item not found.', 'danger')
        return redirect(url_for('warranty'))

    try:
        curr_exp = parse_date_str(item['warranty_expiry_date'], 'Current warranty expiry')
    except InputError:
        curr_exp = today
    new_exp = add_months(max(curr_exp, today), months)

    try:
        db.execute("""
            UPDATE SALE_ITEM 
            SET warranty_months = warranty_months + %s, warranty_expiry_date = %s
            WHERE item_id = %s
        """, (months, new_exp.strftime('%Y-%m-%d'), item_id))
        log_audit('WARRANTY_RENEW', 'Warranty', f"Renewed warranty for #{item_id} until {new_exp}")
        flash(f"Warranty renewed successfully until {new_exp.strftime('%d %b %Y')}.", 'success')
    except Exception as e:
        flash(f"Error renewing warranty: {_public_error(e)}", 'danger')

    return redirect(url_for('warranty'))


@app.route('/api/warranty/lookup')
@login_required
def warranty_lookup_api():
    query = request.args.get('q', '').strip().upper()
    if not query:
        return jsonify({'found': False})

    today = get_app_today()
    res = db.query_one("""
        SELECT si.*, p.product_name, p.brand, p.model, s.invoice_number, s.sale_date,
               cust.customer_name, cust.phone
        FROM SALE_ITEM si
        JOIN PRODUCT p ON si.product_id = p.product_id
        JOIN SALE s ON si.sale_id = s.sale_id
        LEFT JOIN CUSTOMER cust ON s.customer_id = cust.customer_id
        WHERE UPPER(si.serial_number) = %s OR UPPER(s.invoice_number) = %s
    """, (query, query))

    if res:
        exp_d = datetime.datetime.strptime(res['warranty_expiry_date'][:10], '%Y-%m-%d').date()
        days_left = (exp_d - today).days
        status = 'Expired' if days_left < 0 else ('Expiring Soon' if days_left <= 30 else 'Active')
        return jsonify({
            'found': True,
            'serial_number': res['serial_number'],
            'product_name': res['product_name'],
            'brand': res['brand'],
            'invoice_number': res['invoice_number'],
            'purchase_date': res['sale_date'][:10],
            'expiry_date': res['warranty_expiry_date'],
            'days_left': days_left,
            'status': status,
            'customer_name': res['customer_name'] or 'Walk-in'
        })
    return jsonify({'found': False})


@app.route('/warranty/export.csv')
@app.route('/warranty/export.csv', endpoint='warranty_csv')
@login_required
def warranty_export_csv():
    today = get_app_today()
    items = db.query("""
        SELECT si.item_id, p.product_name, si.serial_number, cust.customer_name,
               s.invoice_number, s.sale_date, si.warranty_months, si.warranty_expiry_date
        FROM SALE_ITEM si
        JOIN PRODUCT p ON si.product_id = p.product_id
        JOIN SALE s ON si.sale_id = s.sale_id
        LEFT JOIN CUSTOMER cust ON s.customer_id = cust.customer_id
        WHERE si.warranty_expiry_date IS NOT NULL
        ORDER BY si.warranty_expiry_date ASC
    """)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Warranty ID', 'Product', 'Serial Number', 'Customer', 'Invoice No', 'Purchase Date', 'Months', 'Expiry Date', 'Status'])
    for it in items:
        exp_d = datetime.datetime.strptime(it['warranty_expiry_date'][:10], '%Y-%m-%d').date()
        days = (exp_d - today).days
        st = 'Expired' if days < 0 else ('Expiring Soon' if days <= 30 else 'Active')
        writer.writerow([it['item_id'], it['product_name'], it['serial_number'], it['customer_name'] or 'Walk-in', it['invoice_number'], it['sale_date'][:10], it['warranty_months'], it['warranty_expiry_date'], st])

    return Response(output.getvalue(), mimetype="text/csv", headers={"Content-disposition": "attachment; filename=electrodesk_warranties.csv"})


# ==========================================================
# STEP 4: OPERATIONS - RETURNS & CREDIT NOTES
# ==========================================================

@app.route('/returns')
@login_required
def returns_list():
    today = get_app_today()
    search = request.args.get('search', '').strip()
    date_filter = request.args.get('date', '').strip()

    query_sql = """
        SELECT cn.*, cn.created_at as issue_date,
               s.invoice_number, s.sale_date, s.grand_total as original_amount, s.amount_paid as original_paid, s.payment_method,
               c.customer_name, c.phone, c.address, c.city,
               u.full_name as processed_by_name, u.role as processed_by_role
        FROM CREDIT_NOTE cn
        JOIN SALE s ON cn.sale_id = s.sale_id
        LEFT JOIN CUSTOMER c ON cn.customer_id = c.customer_id
        LEFT JOIN USER u ON s.user_id = u.user_id
        WHERE 1=1
    """
    params = []
    if search:
        query_sql += """ AND (
            cn.credit_note_number LIKE %s OR 
            s.invoice_number LIKE %s OR 
            c.customer_name LIKE %s OR 
            c.phone LIKE %s OR 
            cn.reason LIKE %s
        )"""
        s_wild = f"%{search}%"
        params.extend([s_wild, s_wild, s_wild, s_wild, s_wild])

    if date_filter:
        query_sql += " AND DATE(cn.created_at) = %s"
        params.append(date_filter)

    query_sql += " ORDER BY cn.credit_note_id DESC"
    notes = db.query(query_sql, tuple(params))

    # Fetch returned items for each credit note
    for cn in notes:
        cn['sale_items'] = db.query("""
            SELECT si.*, p.product_name, p.product_code, p.image_url
            FROM SALE_ITEM si
            JOIN PRODUCT p ON si.product_id = p.product_id
            WHERE si.sale_id = %s
        """, (cn['sale_id'],))
        cn['total_items_qty'] = sum(it.get('quantity', 0) for it in cn['sale_items'])

    # KPI Statistics
    all_notes = db.query("SELECT refund_amount, created_at, sale_id FROM CREDIT_NOTE")
    total_refunded = sum(float(n['refund_amount'] or 0.0) for n in all_notes)

    restocked_cnt_row = db.query_one("""
        SELECT COALESCE(SUM(quantity), 0) as total_units
        FROM STOCK_MOVEMENT
        WHERE movement_type = 'IN' AND reason = 'Customer Return'
    """)
    total_units_restocked = restocked_cnt_row['total_units'] if restocked_cnt_row else 0

    cur_month_str = today.strftime('%Y-%m')
    month_notes = [n for n in all_notes if str(n.get('created_at') or '')[:7] == cur_month_str]
    month_refunded = sum(float(n['refund_amount'] or 0.0) for n in month_notes)

    stats = {
        'total_count': len(all_notes),
        'total_refunded': total_refunded,
        'month_count': len(month_notes),
        'month_refunded': month_refunded,
        'units_restocked': total_units_restocked
    }

    # Available sales eligible for return
    available_sales = db.query("""
        SELECT s.sale_id, s.invoice_number, s.sale_date, s.grand_total, s.amount_paid, s.payment_method, s.customer_id,
               c.customer_name, c.phone, c.city
        FROM SALE s
        LEFT JOIN CUSTOMER c ON s.customer_id = c.customer_id
        LEFT JOIN CREDIT_NOTE cn ON s.sale_id = cn.sale_id
        WHERE cn.credit_note_id IS NULL AND s.payment_status != 'Refunded' AND s.amount_paid > 0
        ORDER BY s.sale_id DESC
        LIMIT 60
    """)
    for s in available_sales:
        s['sale_items'] = db.query("""
            SELECT si.product_id, si.quantity, si.unit_price, si.total_price, p.product_name, p.product_code
            FROM SALE_ITEM si
            JOIN PRODUCT p ON si.product_id = p.product_id
            WHERE si.sale_id = %s
        """, (s['sale_id'],))

    return render_template('operations/returns.html',
                           credit_notes=notes,
                           stats=stats,
                           available_sales=available_sales,
                           current_search=search,
                           current_date=date_filter,
                           today=today)


@app.route('/api/returns/invoice-lookup/<invoice_number>')
@login_required
def returns_invoice_lookup(invoice_number):
    invoice_no = invoice_number.strip().upper()
    sale = db.query_one("""
        SELECT s.sale_id, s.invoice_number, s.sale_date, s.grand_total, s.amount_paid, s.payment_status,
               s.payment_method, c.customer_name, c.phone, c.city
        FROM SALE s
        LEFT JOIN CUSTOMER c ON s.customer_id = c.customer_id
        WHERE UPPER(s.invoice_number) = %s
    """, (invoice_no,))

    if not sale:
        return jsonify({'found': False, 'error': f"Invoice '{invoice_no}' was not found in the sales register."}), 404

    prior = db.query_one("SELECT credit_note_id, credit_note_number, refund_amount, created_at FROM CREDIT_NOTE WHERE sale_id = %s", (sale['sale_id'],))
    if prior or sale['payment_status'] == 'Refunded':
        return jsonify({
            'found': True,
            'eligible': False,
            'error': f"Invoice {sale['invoice_number']} has already been returned/refunded under Credit Note {prior['credit_note_number'] if prior else 'CN'}."
        }), 400

    if (sale.get('amount_paid') or 0.0) <= 0:
        return jsonify({
            'found': True,
            'eligible': False,
            'error': f"Invoice {sale['invoice_number']} has 0 amount paid (unsettled credit sale)."
        }), 400

    items = db.query("""
        SELECT si.product_id, si.quantity, si.unit_price, si.total_price, p.product_name, p.product_code
        FROM SALE_ITEM si
        JOIN PRODUCT p ON si.product_id = p.product_id
        WHERE si.sale_id = %s
    """, (sale['sale_id'],))

    return jsonify({
        'found': True,
        'eligible': True,
        'sale': sale,
        'items': items,
        'max_refund': float(sale['amount_paid'])
    })


def _next_sequence(tx, table, column, id_column, prefix):
    """Next running number from the LAST document (not COUNT+1, which collides after deletions)."""
    last = tx.query_one(f"SELECT {column} AS num FROM {table} ORDER BY {id_column} DESC LIMIT 1")
    seq = 1
    if last and last.get('num'):
        try:
            seq = int(str(last['num']).split('-')[-1]) + 1
        except ValueError:
            seq = 1
    return seq


@app.route('/returns/create', methods=['POST'])
@login_required
@roles_required('Admin', 'Manager', 'Shop Owner')
def returns_create():
    invoice_no = request.form.get('invoice_number', '').strip().upper()
    reason = request.form.get('reason', 'Customer return and refund').strip()[:500] or 'Customer return and refund'
    refund_input = parse_float(request.form.get('refund_amount'), 'Refund amount', 0.0, minimum=0.0)
    today = get_app_today()

    try:
        with db.transaction() as tx:
            sale = tx.query_one("SELECT * FROM SALE WHERE UPPER(invoice_number) = %s", (invoice_no,))
            if not sale:
                flash(f"Invoice '{invoice_no}' not found.", 'danger')
                return redirect(url_for('returns_list'))

            # A sale can only be returned once (previously repeated submissions
            # re-added stock and issued unlimited refunds).
            prior = tx.query_one("SELECT COUNT(*) AS cnt FROM CREDIT_NOTE WHERE sale_id = %s", (sale['sale_id'],))
            if sale['payment_status'] == 'Refunded' or (prior and prior['cnt'] > 0):
                flash(f"Invoice {sale['invoice_number']} has already been returned/refunded.", 'warning')
                return redirect(url_for('returns_list'))

            paid = round(float(sale['amount_paid'] or 0.0), 2)
            refund_amount = refund_input if refund_input > 0 else paid
            if refund_amount > paid + 0.005:
                flash(f"Refund (₹{refund_amount:,.2f}) cannot exceed the amount actually paid on this invoice (₹{paid:,.2f}).", 'danger')
                return redirect(url_for('returns_list'))

            cn_seq = _next_sequence(tx, 'CREDIT_NOTE', 'credit_note_number', 'credit_note_id', 'CN')
            cn_num = f"CN-{today.year}-{cn_seq:04d}"
            while tx.query_one("SELECT 1 AS x FROM CREDIT_NOTE WHERE credit_note_number = %s", (cn_num,)):
                cn_seq += 1
                cn_num = f"CN-{today.year}-{cn_seq:04d}"

            tx.execute("""
                INSERT INTO CREDIT_NOTE (credit_note_number, sale_id, customer_id, refund_amount, reason)
                VALUES (%s, %s, %s, %s, %s)
            """, (cn_num, sale['sale_id'], sale['customer_id'], refund_amount, reason))

            items = tx.query("SELECT * FROM SALE_ITEM WHERE sale_id = %s", (sale['sale_id'],))
            for it in items:
                tx.execute("UPDATE PRODUCT SET stock_quantity = stock_quantity + %s WHERE product_id = %s", (it['quantity'], it['product_id']))
                tx.execute("""
                    INSERT INTO STOCK_MOVEMENT (product_id, movement_type, quantity, reason, reference_id, notes)
                    VALUES (%s, 'IN', %s, 'Customer Return', %s, %s)
                """, (it['product_id'], it['quantity'], cn_num, f"Stock reversal from invoice {sale['invoice_number']}"))

            # Returned goods no longer leave an outstanding customer balance.
            tx.execute("UPDATE SALE SET payment_status = 'Refunded', balance_due = 0 WHERE sale_id = %s", (sale['sale_id'],))

        log_audit('RETURN_PROCESSED', 'Operations', f"Issued credit note {cn_num} for ₹{refund_amount:,.2f} on {sale['invoice_number']}")
        flash(f"Credit note {cn_num} generated and stock restored successfully.", 'success')
    except Exception as e:
        flash(f"Error processing return: {_public_error(e)}", 'danger')

    return redirect(url_for('returns_list'))


# ==========================================================
# STEP 4: OPERATIONS - CUSTOMER DUES & LEDGER PAYMENTS
# ==========================================================

@app.route('/customer-dues')
@login_required
def customer_dues():
    dues = db.query("""
        SELECT s.*, c.customer_name, c.phone, c.city, u.full_name as staff_name
        FROM SALE s
        LEFT JOIN CUSTOMER c ON s.customer_id = c.customer_id
        LEFT JOIN USER u ON s.user_id = u.user_id
        WHERE s.balance_due > 0
        ORDER BY s.balance_due DESC
    """)
    total_due = sum(d['balance_due'] for d in dues)
    return render_template('operations/customer_dues.html', dues=dues, total_due=total_due)


@app.route('/customer-dues/pay', methods=['POST'])
@login_required
def customer_dues_pay():
    sale_id = parse_int(request.form.get('sale_id'), 'Sale', 0, minimum=0)
    amount = round(parse_float(request.form.get('amount'), 'Payment amount', 0.0, minimum=0.0), 2)
    method = request.form.get('payment_method', 'UPI').strip()[:30] or 'UPI'
    notes = request.form.get('notes', 'Outstanding dues payment').strip()[:500]
    today = get_app_today()

    if amount <= 0:
        flash('Invalid sale record or payment amount.', 'danger')
        return redirect(url_for('customer_dues'))

    try:
        with db.transaction() as tx:
            sale = tx.query_one("SELECT * FROM SALE WHERE sale_id = %s", (sale_id,))
            if not sale:
                flash('Invalid sale record or payment amount.', 'danger')
                return redirect(url_for('customer_dues'))

            balance = round(float(sale['balance_due'] or 0.0), 2)
            if sale['payment_status'] == 'Refunded' or balance <= 0:
                flash('This invoice has no outstanding balance.', 'warning')
                return redirect(url_for('customer_dues'))
            if amount > balance + 0.005:
                flash(f'Payment (₹{amount:,.2f}) exceeds the outstanding balance (₹{balance:,.2f}).', 'danger')
                return redirect(url_for('customer_dues'))

            new_paid = round(float(sale['amount_paid'] or 0.0) + amount, 2)
            new_due = round(balance - amount, 2)
            if new_due < 0.005:
                new_due = 0.0
            new_status = 'Paid' if new_due == 0 else 'Partial'

            tx.execute("""
                INSERT INTO CUSTOMER_PAYMENT (customer_id, sale_id, payment_date, amount, payment_method, notes)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (sale['customer_id'], sale_id, f"{today.strftime('%Y-%m-%d')} {datetime.datetime.now().strftime('%H:%M:%S')}", amount, method, notes))
            tx.execute("""
                UPDATE SALE SET amount_paid = %s, balance_due = %s, payment_status = %s
                WHERE sale_id = %s
            """, (new_paid, new_due, new_status, sale_id))

        log_audit('RECEIVE_PAYMENT', 'Finance', f"Received ₹{amount:,.2f} against {sale['invoice_number']} ({method})")
        flash(f"Payment of ₹{amount:,.2f} recorded. Remaining dues: ₹{new_due:,.2f}.", 'success')
    except Exception as e:
        flash(f"Error recording payment: {_public_error(e)}", 'danger')

    return redirect(url_for('customer_dues'))


# ==========================================================
# STEP 4: OPERATIONS - QUOTATIONS & CONVERSION TO INVOICE
# ==========================================================

@app.route('/quotations')
@login_required
def quotations():
    quotes = db.query("""
        SELECT q.*, c.customer_name, c.phone
        FROM QUOTATION q
        LEFT JOIN CUSTOMER c ON q.customer_id = c.customer_id
        ORDER BY q.quote_id DESC
    """)
    customers = db.query("SELECT * FROM CUSTOMER ORDER BY customer_name ASC")
    products = db.query("SELECT * FROM PRODUCT ORDER BY product_name ASC")
    return render_template('operations/quotations.html', quotes=quotes, customers=customers, products=products)


@app.route('/quotations/create', methods=['POST'])
@login_required
def quotation_create():
    cid = request.form.get('customer_id') or None
    pid = parse_int(request.form.get('product_id'), 'Product', 0, minimum=0)
    qty = parse_int(request.form.get('quantity'), 'Quantity', 1, minimum=1, maximum=1000)
    notes = request.form.get('notes', 'Formal quotation estimate').strip()[:500]
    today = get_app_today()

    try:
        with db.transaction() as tx:
            prod = tx.query_one("SELECT * FROM PRODUCT WHERE product_id = %s", (pid,))
            if not prod:
                flash('Product not found.', 'danger')
                return redirect(url_for('quotations'))

            subtot = round(float(prod['selling_price']) * qty, 2)
            tax = round(subtot * (float(prod['tax_rate']) if prod.get('tax_rate') is not None else config.DEFAULT_TAX_RATE) / 100.0, 2)
            grand = round(subtot + tax, 2)

            q_seq = _next_sequence(tx, 'QUOTATION', 'quote_number', 'quote_id', 'QT')
            q_num = f"QT-{today.year}-{q_seq:04d}"
            while tx.query_one("SELECT 1 AS x FROM QUOTATION WHERE quote_number = %s", (q_num,)):
                q_seq += 1
                q_num = f"QT-{today.year}-{q_seq:04d}"

            tx.execute("""
                INSERT INTO QUOTATION (quote_number, customer_id, quote_date, expiry_date, subtotal, tax_amount, grand_total, status, notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'Draft', %s)
            """, (q_num, cid, today.strftime('%Y-%m-%d'), (today + datetime.timedelta(days=15)).strftime('%Y-%m-%d'), subtot, tax, grand, notes))
            qid = tx.lastrowid
            tx.execute("""
                INSERT INTO QUOTATION_ITEM (quote_id, product_id, quantity, unit_price, total_price)
                VALUES (%s, %s, %s, %s, %s)
            """, (qid, pid, qty, prod['selling_price'], subtot))

        log_audit('CREATE_QUOTE', 'Operations', f"Created quotation {q_num}")
        flash(f"Quotation {q_num} created successfully.", 'success')
    except Exception as e:
        flash(f"Error creating quotation: {_public_error(e)}", 'danger')

    return redirect(url_for('quotations'))


@app.route('/quotations/convert/<int:quote_id>', methods=['POST'], endpoint='quotation_convert')
@app.route('/quotations/<int:quote_id>/convert-to-invoice', methods=['POST'], endpoint='quotation_convert_to_sale')
@login_required
def quotation_convert_to_sale(quote_id):
    """1-click conversion from Quotation to live Invoice & Warranty (atomic)."""
    today = get_app_today()
    try:
        with db.transaction() as tx:
            quote = tx.query_one("SELECT * FROM QUOTATION WHERE quote_id = %s", (quote_id,))
            if not quote or quote['status'] == 'Converted':
                flash('Invalid quotation or already converted.', 'warning')
                return redirect(url_for('quotations'))
            if str(quote['expiry_date'])[:10] < today.strftime('%Y-%m-%d'):
                flash(f"Quotation {quote['quote_number']} expired on {format_date_in(str(quote['expiry_date']))}. Please create a fresh quotation.", 'warning')
                return redirect(url_for('quotations'))

            items = tx.query("""
                SELECT qi.*, p.product_name, p.warranty_months
                FROM QUOTATION_ITEM qi JOIN PRODUCT p ON qi.product_id = p.product_id
                WHERE qi.quote_id = %s
            """, (quote_id,))
            if not items:
                flash('Quotation has no items to convert.', 'warning')
                return redirect(url_for('quotations'))

            seq = _next_sequence(tx, 'SALE', 'invoice_number', 'sale_id', 'INV')
            inv_num = f"INV-{today.year}-{seq:04d}"
            while tx.query_one("SELECT sale_id FROM SALE WHERE invoice_number = %s", (inv_num,)):
                seq += 1
                inv_num = f"INV-{today.year}-{seq:04d}"

            tax_amount = float(quote['tax_amount'])
            cgst = round(tax_amount / 2, 2)
            sgst = round(tax_amount - cgst, 2)
            grand = float(quote['grand_total'])

            # Converting a quotation is NOT a payment: the invoice starts as Pending
            # and appears in Customer Dues until money is actually received.
            tx.execute("""
                INSERT INTO SALE (invoice_number, customer_id, user_id, sale_date, subtotal, cgst_amount, sgst_amount, tax_amount,
                                  grand_total, payment_method, payment_status, amount_paid, balance_due, notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'Pay Later', 'Pending', 0, %s, %s)
            """, (inv_num, quote['customer_id'], session.get('user_id'),
                  f"{today.strftime('%Y-%m-%d')} {datetime.datetime.now().strftime('%H:%M:%S')}",
                  quote['subtotal'], cgst, sgst, tax_amount, grand, grand,
                  f"Converted from Quote #{quote['quote_number']}"))
            sale_id = tx.lastrowid

            for it in items:
                # Serial placeholder so the warranty record can be looked up; update it from the Warranty Center.
                sn = f"SN-QTCONV-{sale_id}-{it['product_id']}"
                exp_date = add_months(today, int(it['warranty_months'])).strftime('%Y-%m-%d')
                tx.execute("""
                    INSERT INTO SALE_ITEM (sale_id, product_id, quantity, unit_price, total_price, serial_number, warranty_months, warranty_expiry_date)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (sale_id, it['product_id'], it['quantity'], it['unit_price'], it['total_price'], sn, it['warranty_months'], exp_date))

                tx.execute("UPDATE PRODUCT SET stock_quantity = stock_quantity - %s WHERE product_id = %s AND stock_quantity >= %s",
                           (it['quantity'], it['product_id'], it['quantity']))
                if tx.rowcount != 1:
                    flash(f"Insufficient stock to convert quotation for {it['product_name']}.", 'danger')
                    raise CheckoutError('stock')
                tx.execute("""
                    INSERT INTO STOCK_MOVEMENT (product_id, movement_type, quantity, reason, reference_id, notes)
                    VALUES (%s, 'OUT', %s, 'Customer Sale', %s, 'Quote conversion')
                """, (it['product_id'], it['quantity'], inv_num))

            tx.execute("UPDATE QUOTATION SET status = 'Converted' WHERE quote_id = %s", (quote_id,))

        log_audit('CONVERT_QUOTE', 'Operations', f"Converted quote {quote['quote_number']} -> {inv_num}")
        flash(f"Quotation converted to Tax Invoice {inv_num} successfully! Payment is pending - record it under Customer Dues.", 'success')
        return redirect(url_for('invoice_view', sale_id=sale_id))
    except CheckoutError:
        pass   # message already flashed; transaction rolled back
    except Exception as e:
        flash(f"Error converting quotation: {_public_error(e)}", 'danger')

    return redirect(url_for('quotations'))


# ==========================================================
# STEP 4: OPERATIONS - REPAIR TICKETS & CLAIMS
# ==========================================================

@app.route('/repair-tickets')
@login_required
def repair_tickets():
    tickets = db.query("""
        SELECT rt.*, c.customer_name, c.phone
        FROM REPAIR_TICKET rt
        LEFT JOIN CUSTOMER c ON rt.customer_id = c.customer_id
        ORDER BY rt.ticket_id DESC
    """)
    customers = db.query("SELECT * FROM CUSTOMER ORDER BY customer_name ASC")
    return render_template('operations/repair_tickets.html', tickets=tickets, customers=customers)


@app.route('/repair-tickets/create', methods=['POST'])
@login_required
def repair_ticket_create():
    cid = request.form.get('customer_id') or None
    pname = request.form.get('product_name', '').strip()
    serial = request.form.get('serial_number', '').strip().upper()
    issue = request.form.get('issue_description', '').strip()
    tech = request.form.get('technician', 'Service Team Lead').strip()
    est = float(request.form.get('estimated_cost', 0.0) or 0.0)
    today = get_app_today()

    t_seq = db.query_one("SELECT COUNT(*) as c FROM REPAIR_TICKET")['c'] + 1
    t_num = f"TCK-{today.year}-{t_seq:04d}"

    try:
        db.execute("""
            INSERT INTO REPAIR_TICKET (ticket_number, customer_id, product_name, serial_number, issue_description, technician, estimated_cost, status, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'Received', 'Intake diagnosis')
        """, (t_num, cid, pname, serial, issue, tech, est))
        log_audit('CREATE_REPAIR_TICKET', 'Operations', f"Logged repair ticket {t_num} for {pname}")
        flash(f"Repair ticket {t_num} created successfully.", 'success')
    except Exception as e:
        flash(f"Error creating ticket: {_public_error(e)}", 'danger')

    return redirect(url_for('repair_tickets'))


@app.route('/repair-tickets/update-status/<int:ticket_id>', methods=['POST'])
@login_required
def repair_ticket_update_status(ticket_id):
    status = request.form.get('status')
    tech = request.form.get('technician')
    actual = float(request.form.get('actual_cost', 0.0) or 0.0)
    notes = request.form.get('notes', '').strip()

    try:
        db.execute("""
            UPDATE REPAIR_TICKET 
            SET status = %s, technician = %s, actual_cost = %s, notes = %s, updated_at = CURRENT_TIMESTAMP
            WHERE ticket_id = %s
        """, (status, tech, actual, notes, ticket_id))
        log_audit('UPDATE_REPAIR_TICKET', 'Operations', f"Updated ticket #{ticket_id} status to {status}")
        flash(f"Repair ticket status updated to '{status}'.", 'success')
    except Exception as e:
        flash(f"Error updating ticket: {_public_error(e)}", 'danger')

    return redirect(url_for('repair_tickets'))


# ==========================================================
# STEP 4B: OPERATIONS - DELIVERY & LOGISTICS
# ==========================================================

@app.route('/deliveries')
@login_required
def deliveries():
    today = get_app_today()
    status_filter = request.args.get('status', '').strip()
    assigned_filter = request.args.get('assigned_to', '').strip()
    search = request.args.get('search', '').strip()
    date_filter = request.args.get('date', '').strip()
    my_only = request.args.get('my_only', '').strip()

    user_role = session.get('role', '')
    user_id = session.get('user_id')

    if user_role == 'Delivery Staff' and not assigned_filter and not my_only:
        my_only = '1'

    query_sql = """
        SELECT d.*, c.customer_name, c.phone as customer_phone, c.city as customer_city,
               s.invoice_number, s.grand_total as sale_amount, s.sale_date,
               u.full_name as assigned_staff_name, u.role as assigned_staff_role, u.phone as assigned_staff_phone
        FROM DELIVERY_ORDER d
        LEFT JOIN CUSTOMER c ON d.customer_id = c.customer_id
        JOIN SALE s ON d.sale_id = s.sale_id
        LEFT JOIN USER u ON d.assigned_to = u.user_id
        WHERE 1=1
    """
    params = []

    if status_filter:
        query_sql += " AND d.status = %s"
        params.append(status_filter)

    if my_only == '1':
        query_sql += " AND d.assigned_to = %s"
        params.append(user_id)
    elif assigned_filter:
        if assigned_filter == 'unassigned':
            query_sql += " AND d.assigned_to IS NULL"
        else:
            try:
                query_sql += " AND d.assigned_to = %s"
                params.append(int(assigned_filter))
            except ValueError:
                pass

    if date_filter:
        query_sql += " AND d.expected_date = %s"
        params.append(date_filter)

    if search:
        query_sql += """ AND (
            d.delivery_number LIKE %s OR 
            s.invoice_number LIKE %s OR 
            c.customer_name LIKE %s OR 
            d.recipient_name LIKE %s OR 
            d.recipient_phone LIKE %s OR 
            d.delivery_address LIKE %s
        )"""
        s_wild = f"%{search}%"
        params.extend([s_wild, s_wild, s_wild, s_wild, s_wild, s_wild])

    query_sql += " ORDER BY d.delivery_id DESC"
    deliveries_list = db.query(query_sql, tuple(params))

    all_deliveries = db.query("SELECT status, delivery_charges FROM DELIVERY_ORDER")
    stats = {
        'total': len(all_deliveries),
        'pending': sum(1 for d in all_deliveries if d['status'] == 'Pending'),
        'assigned': sum(1 for d in all_deliveries if d['status'] == 'Assigned'),
        'out_for_delivery': sum(1 for d in all_deliveries if d['status'] == 'Out for Delivery'),
        'delivered': sum(1 for d in all_deliveries if d['status'] == 'Delivered'),
        'failed': sum(1 for d in all_deliveries if d['status'] == 'Failed'),
        'cancelled': sum(1 for d in all_deliveries if d['status'] == 'Cancelled'),
        'total_charges': sum(float(d.get('delivery_charges') or 0.0) for d in all_deliveries),
    }
    completed_or_failed = stats['delivered'] + stats['failed']
    stats['success_rate'] = round((stats['delivered'] / completed_or_failed * 100), 1) if completed_or_failed > 0 else 100.0

    delivery_staff = db.query("""
        SELECT user_id, full_name, username, role, phone, email, status,
               (SELECT COUNT(*) FROM DELIVERY_ORDER WHERE assigned_to = USER.user_id AND status IN ('Assigned', 'Out for Delivery')) as active_deliveries_count,
               (SELECT COUNT(*) FROM DELIVERY_ORDER WHERE assigned_to = USER.user_id AND status = 'Delivered') as completed_deliveries_count
        FROM USER
        WHERE status = 'Active' AND (role = 'Delivery Staff' OR role = 'Sales Staff' OR role LIKE '%Manager%' OR role LIKE '%Admin%' OR role LIKE '%Owner%')
        ORDER BY CASE WHEN role = 'Delivery Staff' THEN 0 ELSE 1 END, full_name ASC
    """)

    available_sales = db.query("""
        SELECT s.sale_id, s.invoice_number, s.sale_date, s.grand_total, s.customer_id,
               c.customer_name, c.phone, c.address, c.city
        FROM SALE s
        LEFT JOIN CUSTOMER c ON s.customer_id = c.customer_id
        ORDER BY s.sale_id DESC
        LIMIT 60
    """)

    customers = db.query("SELECT customer_id, customer_name, phone, address, city FROM CUSTOMER ORDER BY customer_name ASC")

    return render_template('operations/deliveries.html',
                           deliveries=deliveries_list,
                           stats=stats,
                           delivery_staff=delivery_staff,
                           available_sales=available_sales,
                           customers=customers,
                           current_status=status_filter,
                           current_assigned=assigned_filter,
                           current_search=search,
                           current_date=date_filter,
                           my_only=my_only,
                           today=today)


@app.route('/deliveries/create', methods=['POST'])
@login_required
def delivery_create():
    today = get_app_today()
    sale_id = request.form.get('sale_id')
    recipient_name = request.form.get('recipient_name', '').strip()
    recipient_phone = request.form.get('recipient_phone', '').strip()
    delivery_address = request.form.get('delivery_address', '').strip()
    charges = float(request.form.get('delivery_charges', 0.0) or 0.0)
    expected_date = request.form.get('expected_date', '').strip() or (today + datetime.timedelta(days=1)).strftime('%Y-%m-%d')
    assigned_to = request.form.get('assigned_to') or None
    notes = request.form.get('tracking_notes', '').strip()

    if not sale_id:
        flash("Please select a valid POS invoice/sale.", "danger")
        return redirect(url_for('deliveries'))

    sale = db.query_one("SELECT s.*, c.customer_name, c.phone, c.address FROM SALE s LEFT JOIN CUSTOMER c ON s.customer_id = c.customer_id WHERE s.sale_id = %s", (sale_id,))
    if not sale:
        flash("Sale not found.", "danger")
        return redirect(url_for('deliveries'))

    if not recipient_name:
        recipient_name = sale.get('customer_name') or 'Customer'
    if not recipient_phone:
        recipient_phone = sale.get('phone') or 'N/A'
    if not delivery_address:
        delivery_address = sale.get('address') or "Store Delivery / Standard Address"

    count_row = db.query_one("SELECT COUNT(*) as c FROM DELIVERY_ORDER")
    d_seq = (count_row['c'] if count_row else 0) + 1
    del_number = f"DEL-{today.year}-{d_seq:04d}"

    initial_status = 'Assigned' if assigned_to else 'Pending'

    try:
        db.execute("""
            INSERT INTO DELIVERY_ORDER (
                delivery_number, sale_id, customer_id, recipient_name, recipient_phone,
                delivery_address, delivery_charges, expected_date, status, assigned_to, tracking_notes
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (del_number, sale_id, sale.get('customer_id'), recipient_name, recipient_phone,
              delivery_address, charges, expected_date, initial_status, assigned_to, notes))

        new_del = db.query_one("SELECT delivery_id FROM DELIVERY_ORDER WHERE delivery_number = %s", (del_number,))
        del_id = new_del['delivery_id']

        user_id = session.get('user_id')
        db.execute("""
            INSERT INTO DELIVERY_LOG (delivery_id, status, updated_by, remarks)
            VALUES (%s, %s, %s, %s)
        """, (del_id, 'Pending', user_id, f"Delivery order created for invoice {sale['invoice_number']}"))

        if assigned_to:
            staff = db.query_one("SELECT full_name FROM USER WHERE user_id = %s", (assigned_to,))
            staff_name = staff['full_name'] if staff else 'Staff'
            db.execute("""
                INSERT INTO DELIVERY_LOG (delivery_id, status, updated_by, remarks)
                VALUES (%s, %s, %s, %s)
            """, (del_id, 'Assigned', user_id, f"Assigned to delivery executive {staff_name}"))

        log_audit('CREATE_DELIVERY_ORDER', 'Operations', f"Created delivery order {del_number} for invoice {sale['invoice_number']}")
        flash(f"Delivery order {del_number} created successfully.", "success")
    except Exception as e:
        flash(f"Error creating delivery order: {_public_error(e)}", "danger")

    return redirect(url_for('deliveries'))


@app.route('/deliveries/<int:delivery_id>/update-status', methods=['POST'])
@login_required
def delivery_update_status(delivery_id):
    new_status = request.form.get('status', '').strip()
    remarks = request.form.get('remarks', '').strip()
    valid_statuses = ['Pending', 'Assigned', 'Out for Delivery', 'Delivered', 'Failed', 'Cancelled']

    if new_status not in valid_statuses:
        flash("Invalid status specified.", "danger")
        return redirect(url_for('deliveries'))

    delivery = db.query_one("SELECT * FROM DELIVERY_ORDER WHERE delivery_id = %s", (delivery_id,))
    if not delivery:
        flash("Delivery order not found.", "danger")
        return redirect(url_for('deliveries'))

    user_id = session.get('user_id')
    user_role = session.get('role', '')

    if user_role == 'Delivery Staff' and delivery['assigned_to'] != user_id:
        flash("Access denied: You can only update deliveries assigned to you.", "danger")
        return redirect(url_for('deliveries'))

    try:
        if new_status == 'Delivered':
            db.execute("""
                UPDATE DELIVERY_ORDER 
                SET status = %s, delivered_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                WHERE delivery_id = %s
            """, (new_status, delivery_id))
        else:
            db.execute("""
                UPDATE DELIVERY_ORDER 
                SET status = %s, updated_at = CURRENT_TIMESTAMP
                WHERE delivery_id = %s
            """, (new_status, delivery_id))

        db.execute("""
            INSERT INTO DELIVERY_LOG (delivery_id, status, updated_by, remarks)
            VALUES (%s, %s, %s, %s)
        """, (delivery_id, new_status, user_id, remarks or f"Status updated from {delivery['status']} to {new_status}"))

        log_audit('UPDATE_DELIVERY_STATUS', 'Operations', f"Updated {delivery['delivery_number']} status to {new_status}")
        flash(f"Delivery {delivery['delivery_number']} updated to '{new_status}'.", "success")
    except Exception as e:
        flash(f"Error updating status: {_public_error(e)}", "danger")

    return redirect(url_for('deliveries'))


@app.route('/deliveries/<int:delivery_id>/assign', methods=['POST'])
@login_required
def delivery_assign(delivery_id):
    if session.get('role') == 'Delivery Staff':
        flash("Access denied.", "danger")
        return redirect(url_for('deliveries'))

    assigned_to = request.form.get('assigned_to') or None
    remarks = request.form.get('remarks', '').strip()

    delivery = db.query_one("SELECT * FROM DELIVERY_ORDER WHERE delivery_id = %s", (delivery_id,))
    if not delivery:
        flash("Delivery order not found.", "danger")
        return redirect(url_for('deliveries'))

    user_id = session.get('user_id')
    try:
        if assigned_to:
            staff = db.query_one("SELECT full_name FROM USER WHERE user_id = %s", (assigned_to,))
            staff_name = staff['full_name'] if staff else 'Staff'
            new_status = 'Assigned' if delivery['status'] == 'Pending' else delivery['status']
            db.execute("""
                UPDATE DELIVERY_ORDER 
                SET assigned_to = %s, status = %s, updated_at = CURRENT_TIMESTAMP
                WHERE delivery_id = %s
            """, (assigned_to, new_status, delivery_id))
            db.execute("""
                INSERT INTO DELIVERY_LOG (delivery_id, status, updated_by, remarks)
                VALUES (%s, %s, %s, %s)
            """, (delivery_id, new_status, user_id, f"Assigned to {staff_name}. {remarks}".strip()))
            flash(f"Delivery assigned to {staff_name}.", "success")
        else:
            db.execute("""
                UPDATE DELIVERY_ORDER 
                SET assigned_to = NULL, status = 'Pending', updated_at = CURRENT_TIMESTAMP
                WHERE delivery_id = %s
            """, (delivery_id,))
            db.execute("""
                INSERT INTO DELIVERY_LOG (delivery_id, status, updated_by, remarks)
                VALUES (%s, 'Pending', %s, 'Unassigned from personnel.')
            """, (delivery_id, user_id))
            flash("Delivery marked as unassigned / Pending.", "info")

        log_audit('ASSIGN_DELIVERY', 'Operations', f"Assignment update on delivery #{delivery_id}")
    except Exception as e:
        flash(f"Error assigning delivery: {_public_error(e)}", "danger")

    return redirect(url_for('deliveries'))


@app.route('/deliveries/<int:delivery_id>/edit', methods=['POST'])
@login_required
def delivery_edit(delivery_id):
    if session.get('role') == 'Delivery Staff':
        flash("Access denied.", "danger")
        return redirect(url_for('deliveries'))

    recipient_name = request.form.get('recipient_name', '').strip()
    recipient_phone = request.form.get('recipient_phone', '').strip()
    delivery_address = request.form.get('delivery_address', '').strip()
    charges = float(request.form.get('delivery_charges', 0.0) or 0.0)
    expected_date = request.form.get('expected_date', '').strip()
    notes = request.form.get('tracking_notes', '').strip()

    try:
        db.execute("""
            UPDATE DELIVERY_ORDER 
            SET recipient_name = %s, recipient_phone = %s, delivery_address = %s,
                delivery_charges = %s, expected_date = %s, tracking_notes = %s, updated_at = CURRENT_TIMESTAMP
            WHERE delivery_id = %s
        """, (recipient_name, recipient_phone, delivery_address, charges, expected_date, notes, delivery_id))

        user_id = session.get('user_id')
        db.execute("""
            INSERT INTO DELIVERY_LOG (delivery_id, status, updated_by, remarks)
            VALUES (%s, (SELECT status FROM DELIVERY_ORDER WHERE delivery_id = %s), %s, 'Delivery details/address edited')
        """, (delivery_id, delivery_id, user_id))

        log_audit('EDIT_DELIVERY', 'Operations', f"Updated delivery #{delivery_id} address/contact details")
        flash("Delivery details updated successfully.", "success")
    except Exception as e:
        flash(f"Error editing delivery: {_public_error(e)}", "danger")

    return redirect(url_for('deliveries'))


@app.route('/deliveries/<int:delivery_id>/history')
@login_required
def delivery_history_json(delivery_id):
    delivery = db.query_one("""
        SELECT d.*, c.customer_name, c.phone as customer_phone, s.invoice_number, s.grand_total,
               u.full_name as assigned_staff_name
        FROM DELIVERY_ORDER d
        LEFT JOIN CUSTOMER c ON d.customer_id = c.customer_id
        JOIN SALE s ON d.sale_id = s.sale_id
        LEFT JOIN USER u ON d.assigned_to = u.user_id
        WHERE d.delivery_id = %s
    """, (delivery_id,))
    if not delivery:
        return jsonify({'error': 'Delivery not found'}), 404

    logs = db.query("""
        SELECT l.*, u.full_name as user_name, u.role as user_role
        FROM DELIVERY_LOG l
        LEFT JOIN USER u ON l.updated_by = u.user_id
        WHERE l.delivery_id = %s
        ORDER BY l.log_id ASC
    """, (delivery_id,))

    items = db.query("""
        SELECT si.*, p.product_name, p.product_code
        FROM SALE_ITEM si
        JOIN PRODUCT p ON si.product_id = p.product_id
        WHERE si.sale_id = %s
    """, (delivery['sale_id'],))

    return jsonify({
        'delivery': delivery,
        'logs': logs,
        'items': items
    })


@app.route('/deliveries/staff/create', methods=['POST'])
@login_required
def delivery_staff_create():
    if session.get('role') not in ('System Administrator', 'Admin', 'Shop Owner', 'Owner', 'Shop Manager', 'Manager'):
        flash("Only managers and administrators can add delivery personnel.", "danger")
        return redirect(url_for('deliveries'))

    username = request.form.get('username', '').strip().lower()
    full_name = request.form.get('full_name', '').strip()
    phone = request.form.get('phone', '').strip()
    email = request.form.get('email', '').strip()
    password = request.form.get('password', 'delivery123').strip()

    if not username or not full_name:
        flash("Username and Full Name are required.", "danger")
        return redirect(url_for('deliveries'))

    existing = db.query_one("SELECT user_id FROM USER WHERE username = %s", (username,))
    if existing:
        flash(f"Username '{username}' already exists.", "danger")
        return redirect(url_for('deliveries'))

    avatar = get_avatar(username, full_name)
    try:
        db.execute("""
            INSERT INTO USER (username, password_hash, full_name, role, avatar, email, phone, status)
            VALUES (%s, %s, %s, 'Delivery Staff', %s, %s, %s, 'Active')
        """, (username, generate_password_hash(password), full_name, avatar, email, phone))
        log_audit('CREATE_USER', 'Administration', f"Added delivery personnel {full_name} (@{username})")
        flash(f"Delivery staff '{full_name}' (@{username}) added successfully.", "success")
    except Exception as e:
        flash(f"Error adding delivery staff: {_public_error(e)}", "danger")

    return redirect(url_for('deliveries'))



# ==========================================================
# STEP 5: REPORTS & FINANCE (P&L, EXPENSES, GST, CLOSING)
# ==========================================================

@app.route('/reports')
@login_required
def reports():
    tab = request.args.get('tab', 'sales')
    today = get_app_today()
    preset = request.args.get('preset', 'month')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    if preset == 'today':
        start_d = today
        end_d = today
    elif preset == 'week':
        start_d = today - datetime.timedelta(days=7)
        end_d = today
    elif preset == 'year':
        start_d = datetime.date(today.year, 1, 1)
        end_d = today
    elif preset == 'custom' and start_date and end_date:
        try:
            start_d = datetime.datetime.strptime(start_date[:10], '%Y-%m-%d').date()
            end_d = datetime.datetime.strptime(end_date[:10], '%Y-%m-%d').date()
        except Exception:
            start_d = datetime.date(today.year, today.month, 1)
            end_d = today
    else:
        start_d = datetime.date(today.year, today.month, 1)
        end_d = today

    start_date_str = start_d.strftime('%Y-%m-%d')
    end_date_str = end_d.strftime('%Y-%m-%d')

    # Derived inventory numbers
    inv_totals = get_inventory_derived_totals()

    # Sales Aggregates
    summary = db.query_one("""
        SELECT 
            COALESCE(COUNT(*), 0) as total_orders,
            COALESCE(SUM(grand_total), 0.0) as total_revenue,
            COALESCE(SUM(tax_amount), 0.0) as total_tax,
            COALESCE(SUM(discount_amount), 0.0) as total_discount
        FROM SALE
    """)
    units_row = db.query_one("SELECT COALESCE(SUM(quantity), 0) as units FROM SALE_ITEM")
    total_units_val = units_row['units'] if units_row else 0
    if summary:
        summary['total_sales'] = summary['total_orders']
        summary['total_units'] = total_units_val

    # Cost of goods sold (COGS)
    cogs_row = db.query_one("""
        SELECT COALESCE(SUM(si.quantity * p.cost_price), 0.0) as cogs
        FROM SALE_ITEM si
        JOIN PRODUCT p ON si.product_id = p.product_id
    """)
    cogs = cogs_row['cogs'] if cogs_row else 0.0
    tot_rev = summary['total_revenue'] if summary else 0.0
    gross_profit = tot_rev - cogs
    profit_margin = (gross_profit / tot_rev * 100.0) if tot_rev > 0 else 0.0
    aov = (tot_rev / summary['total_orders']) if summary and summary['total_orders'] > 0 else 0.0

    # 14-Day Daily Revenue Series
    daily_labels = []
    daily_values = []
    for i in range(13, -1, -1):
        day = today - datetime.timedelta(days=i)
        day_str = day.strftime('%Y-%m-%d')
        daily_labels.append(day.strftime('%d %b'))

        d_row = db.query_one("SELECT COALESCE(SUM(grand_total), 0.0) as rev FROM SALE WHERE DATE(sale_date) = %s", (day_str,))
        daily_values.append(d_row['rev'] if d_row else 0.0)

    # Category Sales Breakdown
    cat_sales = db.query("""
        SELECT c.category_code, c.category_name,
               COALESCE(COUNT(DISTINCT s.sale_id), 0) as order_count,
               COALESCE(SUM(si.quantity), 0) as units_sold,
               COALESCE(SUM(si.total_price), 0.0) as revenue
        FROM CATEGORY c
        LEFT JOIN PRODUCT p ON c.category_id = p.category_id
        LEFT JOIN SALE_ITEM si ON p.product_id = si.product_id
        LEFT JOIN SALE s ON si.sale_id = s.sale_id
        GROUP BY c.category_id, c.category_code, c.category_name
        ORDER BY revenue DESC
    """)

    # Top 10 Best Sellers
    top_10 = db.query("""
        SELECT p.product_code, p.product_name, p.brand, c.category_name,
               COALESCE(SUM(si.quantity), 0) as total_sold,
               COALESCE(SUM(si.total_price), 0.0) as total_revenue,
               COALESCE(SUM(si.quantity * (si.unit_price - p.cost_price)), 0.0) as total_profit
        FROM SALE_ITEM si
        JOIN PRODUCT p ON si.product_id = p.product_id
        JOIN CATEGORY c ON p.category_id = c.category_id
        GROUP BY p.product_id, p.product_code, p.product_name, p.brand, c.category_name
        HAVING total_sold > 0
        ORDER BY total_sold DESC
        LIMIT 10
    """)

    # Stock by Category (Inventory tab)
    cat_inventory = db.query("""
        SELECT c.category_code, c.category_name,
               COALESCE(COUNT(p.product_id), 0) as total_products,
               COALESCE(SUM(p.stock_quantity), 0) as total_units,
               COALESCE(SUM(p.stock_quantity * p.cost_price), 0.0) as total_cost,
               COALESCE(SUM(p.stock_quantity * p.selling_price), 0.0) as total_retail
        FROM CATEGORY c
        LEFT JOIN PRODUCT p ON c.category_id = p.category_id
        GROUP BY c.category_id, c.category_code, c.category_name
        ORDER BY c.category_code ASC
    """)

    return render_template('reports.html',
                           active_tab=tab,
                           summary=summary,
                           cogs=cogs,
                           gross_profit=gross_profit,
                           profit_margin=profit_margin,
                           aov=aov,
                           avg_order_value=aov,
                           total_revenue=summary['total_revenue'] if summary else 0.0,
                           total_sales=summary['total_sales'] if summary else 0,
                           total_units=summary['total_units'] if summary else 0,
                           daily_labels=daily_labels,
                           daily_values=daily_values,
                           last_14_days_labels=daily_labels,
                           last_14_days_values=daily_values,
                           last_14_days_data=daily_values,
                           cat_sales=cat_sales,
                           cat_breakdown=cat_sales,
                           top_products=top_10,
                           top_selling=top_10,
                           inv_totals=inv_totals,
                           inventory_valuation=inv_totals,
                           cat_inventory=cat_inventory,
                           category_stock_summary=cat_inventory,
                           date_preset=preset,
                           start_date=start_date_str,
                           end_date=end_date_str,
                           start_date_formatted=format_date_in(start_date_str),
                           end_date_formatted=format_date_in(end_date_str),
                           today_formatted=format_date_in(today.strftime('%Y-%m-%d')))


@app.route('/reports/profit-loss')
@login_required
def reports_profit_loss():
    today = get_app_today()

    rev_row = db.query_one("SELECT COALESCE(SUM(grand_total), 0.0) as rev, COALESCE(SUM(tax_amount), 0.0) as tax, COUNT(*) as count FROM SALE")
    revenue = rev_row['rev'] if rev_row else 0.0
    tax_collected = rev_row['tax'] if rev_row else 0.0
    sales_count = rev_row['count'] if rev_row else 0

    ref_row = db.query_one("SELECT COALESCE(SUM(refund_amount), 0.0) as total_refunds, COUNT(*) as count FROM CREDIT_NOTE")
    total_refunds = ref_row['total_refunds'] if ref_row else 0.0
    refund_count = ref_row['count'] if ref_row else 0

    net_revenue = max(0.0, revenue - total_refunds)

    cogs_row = db.query_one("SELECT COALESCE(SUM(si.quantity * p.cost_price), 0.0) as cogs FROM SALE_ITEM si JOIN PRODUCT p ON si.product_id = p.product_id")
    cogs = cogs_row['cogs'] if cogs_row else 0.0
    gross_profit = net_revenue - cogs
    gross_margin = (gross_profit / revenue * 100.0) if revenue > 0 else 0.0

    exp_row = db.query_one("SELECT COALESCE(SUM(amount), 0.0) as exp FROM EXPENSE")
    total_expenses = exp_row['exp'] if exp_row else 0.0

    net_profit = gross_profit - total_expenses
    net_margin = (net_profit / revenue * 100.0) if revenue > 0 else 0.0

    # Best-sellers
    best_sellers = db.query("""
        SELECT p.product_id, p.product_code, p.product_name, p.brand, c.category_name,
               SUM(si.quantity) as sold, SUM(si.quantity) as total_sold,
               SUM(si.total_price) as rev,
               SUM(si.quantity * (si.unit_price - p.cost_price)) as margin
        FROM SALE_ITEM si
        JOIN PRODUCT p ON si.product_id = p.product_id
        JOIN CATEGORY c ON p.category_id = c.category_id
        GROUP BY p.product_id, p.product_code, p.product_name, p.brand, c.category_name
        HAVING total_sold > 0
        ORDER BY total_sold DESC, rev DESC
        LIMIT 5
    """)

    # Slow-moving stock (high stock, 0 or low sales)
    slow_moving = db.query("""
        SELECT p.*, c.category_name,
               COALESCE((SELECT SUM(si.quantity) FROM SALE_ITEM si WHERE si.product_id = p.product_id), 0) as total_sold
        FROM PRODUCT p
        JOIN CATEGORY c ON p.category_id = c.category_id
        WHERE p.stock_quantity > p.reorder_level
        ORDER BY total_sold ASC, p.stock_quantity DESC
        LIMIT 6
    """)

    # Margin per category
    category_margins = db.query("""
        SELECT c.category_id, c.category_code, c.category_name, c.icon,
               COALESCE(COUNT(DISTINCT p.product_id), 0) as total_skus,
               COALESCE(SUM(si.quantity), 0) as units_sold,
               COALESCE(SUM(si.total_price), 0.0) as revenue,
               COALESCE(SUM(si.quantity * p.cost_price), 0.0) as cogs,
               COALESCE(SUM(si.total_price - (si.quantity * p.cost_price)), 0.0) as gross_profit
        FROM CATEGORY c
        LEFT JOIN PRODUCT p ON c.category_id = p.category_id
        LEFT JOIN SALE_ITEM si ON p.product_id = si.product_id
        GROUP BY c.category_id, c.category_code, c.category_name, c.icon
        ORDER BY revenue DESC
    """)
    for cat in category_margins:
        c_rev = cat['revenue']
        c_gp = cat['gross_profit']
        cat['margin_pct'] = (c_gp / c_rev * 100.0) if c_rev > 0 else 0.0

    return render_template('finance/profit_loss.html',
                           revenue=revenue,
                           gross_revenue=revenue,
                           net_revenue=net_revenue,
                           total_refunds=total_refunds,
                           refund_count=refund_count,
                           sales_count=sales_count,
                           cogs=cogs,
                           gross_profit=gross_profit,
                           gross_margin=gross_margin,
                           total_expenses=total_expenses,
                           net_profit=net_profit,
                           net_margin=net_margin,
                           best_sellers=best_sellers,
                           slow_moving=slow_moving,
                           category_margins=category_margins)


@app.route('/expenses')
@login_required
def expenses():
    today = get_app_today()
    expenses_list = db.query("SELECT * FROM EXPENSE ORDER BY expense_date DESC, expense_id DESC")
    total_exp = sum(e['amount'] for e in expenses_list)
    rent_total = sum(e['amount'] for e in expenses_list if e['category'] == 'Rent')
    salary_total = sum(e['amount'] for e in expenses_list if e['category'] == 'Salary')
    electricity_total = sum(e['amount'] for e in expenses_list if e['category'] == 'Electricity')
    other_total = max(0.0, total_exp - rent_total - salary_total - electricity_total)

    return render_template('finance/expenses.html',
                           expenses=expenses_list,
                           total_expense=total_exp,
                           rent_total=rent_total,
                           salary_total=salary_total,
                           electricity_total=electricity_total,
                           other_total=other_total,
                           app_today_str=today.strftime('%Y-%m-%d'))


@app.route('/expenses/add', methods=['POST'])
@login_required
@roles_required('Admin', 'Manager', 'Shop Owner')
def expense_add():
    category = request.form.get('category', 'Other').strip()
    amount = float(request.form.get('amount', 0.0) or 0.0)
    exp_date = request.form.get('expense_date') or get_app_today().strftime('%Y-%m-%d')
    pay_mode = request.form.get('payment_method', 'Bank Transfer').strip()
    notes = request.form.get('notes', '').strip()
    creator = session.get('full_name', 'Manager')

    if amount <= 0:
        flash("Expense amount must be greater than zero.", 'danger')
        return redirect(url_for('expenses'))

    try:
        db.execute("""
            INSERT INTO EXPENSE (category, amount, expense_date, payment_method, notes, created_by)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (category, amount, exp_date, pay_mode, notes, creator))
        log_audit('RECORD_EXPENSE', 'Finance', f"Recorded {category} expense of ₹{amount:,.2f}")
        flash(f"Expense of ₹{amount:,.2f} under '{category}' recorded successfully.", 'success')
    except Exception as e:
        flash(f"Error recording expense: {_public_error(e)}", 'danger')

    return redirect(url_for('expenses'))


@app.route('/expenses/edit/<int:expense_id>', methods=['POST'])
@login_required
@roles_required('Admin', 'Manager', 'Shop Owner')
def expense_edit(expense_id):
    existing = db.query_one("SELECT * FROM EXPENSE WHERE expense_id = %s", (expense_id,))
    if not existing:
        flash("Expense record not found.", 'danger')
        return redirect(url_for('expenses'))

    category = request.form.get('category', existing['category']).strip()
    amount = float(request.form.get('amount', existing['amount']) or 0.0)
    exp_date = request.form.get('expense_date') or existing['expense_date']
    pay_mode = request.form.get('payment_method', existing['payment_method']).strip()
    notes = request.form.get('notes', existing['notes'] or '').strip()

    if amount <= 0:
        flash("Expense amount must be greater than zero.", 'danger')
        return redirect(url_for('expenses'))

    try:
        db.execute("""
            UPDATE EXPENSE
            SET category = %s, amount = %s, expense_date = %s, payment_method = %s, notes = %s
            WHERE expense_id = %s
        """, (category, amount, exp_date, pay_mode, notes, expense_id))
        log_audit('UPDATE_EXPENSE', 'Finance', f"Updated expense #{expense_id} ({category}: ₹{amount:,.2f})")
        flash(f"Expense #{expense_id} updated successfully.", 'success')
    except Exception as e:
        flash(f"Error updating expense: {_public_error(e)}", 'danger')

    return redirect(url_for('expenses'))


@app.route('/expenses/delete/<int:expense_id>', methods=['POST'])
@login_required
@roles_required('Admin', 'Manager', 'Shop Owner')
def expense_delete(expense_id):
    existing = db.query_one("SELECT * FROM EXPENSE WHERE expense_id = %s", (expense_id,))
    if not existing:
        flash("Expense record not found.", 'danger')
        return redirect(url_for('expenses'))

    try:
        db.execute("DELETE FROM EXPENSE WHERE expense_id = %s", (expense_id,))
        log_audit('DELETE_EXPENSE', 'Finance', f"Deleted expense #{expense_id} ({existing['category']}: ₹{existing['amount']:,.2f})")
        flash(f"Expense #{expense_id} deleted successfully.", 'success')
    except Exception as e:
        flash(f"Error deleting expense: {_public_error(e)}", 'danger')

    return redirect(url_for('expenses'))


# Taxable value = subtotal less discount and exchange value (the amount GST is actually charged on).
# Refunded invoices are excluded so GST liability is not overstated after returns.
_GST_TAXABLE = "COALESCE(SUM(subtotal - COALESCE(discount_amount, 0) - COALESCE(exchange_value, 0)), 0.0)"


@app.route('/reports/gst')
@login_required
def reports_gst():
    """Monthly GST breakdown: Taxable value, CGST, SGST, Total Tax (refunded invoices excluded)."""
    month = db.month_expr('sale_date')
    gst_data = db.query(f"""
        SELECT 
            {month} as month,
            18.0 as gst_rate,
            9.0 as cgst_rate,
            9.0 as sgst_rate,
            COUNT(*) as invoice_count,
            {_GST_TAXABLE} as taxable_amount,
            COALESCE(SUM(cgst_amount), 0.0) as total_cgst,
            COALESCE(SUM(sgst_amount), 0.0) as total_sgst,
            COALESCE(SUM(tax_amount), 0.0) as total_tax,
            COALESCE(SUM(grand_total), 0.0) as gross_turnover
        FROM SALE
        WHERE payment_status <> 'Refunded'
        GROUP BY {month}
        ORDER BY month DESC
    """)
    totals = db.query_one(f"""
        SELECT 
            COUNT(*) as total_invoices,
            {_GST_TAXABLE} as taxable,
            COALESCE(SUM(cgst_amount), 0.0) as cgst,
            COALESCE(SUM(sgst_amount), 0.0) as sgst,
            COALESCE(SUM(tax_amount), 0.0) as tax,
            COALESCE(SUM(grand_total), 0.0) as turnover
        FROM SALE
        WHERE payment_status <> 'Refunded'
    """)
    return render_template('finance/gst_summary.html', gst_data=gst_data, totals=totals)


@app.route('/reports/gst/export.csv')
@login_required
def reports_gst_csv():
    month = db.month_expr('sale_date')
    gst_data = db.query(f"""
        SELECT 
            {month} as month,
            18.0 as gst_rate,
            COUNT(*) as invoice_count,
            {_GST_TAXABLE} as taxable_amount,
            COALESCE(SUM(cgst_amount), 0.0) as total_cgst,
            COALESCE(SUM(sgst_amount), 0.0) as total_sgst,
            COALESCE(SUM(tax_amount), 0.0) as total_tax,
            COALESCE(SUM(grand_total), 0.0) as gross_turnover
        FROM SALE
        WHERE payment_status <> 'Refunded'
        GROUP BY {month}
        ORDER BY month DESC
    """)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Month', 'GST Rate (%)', 'Invoices Count', 'Taxable Value (₹)', 'CGST 9% (₹)', 'SGST 9% (₹)', 'Total GST 18% (₹)', 'Gross Turnover (₹)'])
    for g in gst_data:
        writer.writerow([
            g['month'],
            f"{g['gst_rate']:.0f}%",
            g['invoice_count'],
            f"{g['taxable_amount']:.2f}",
            f"{g['total_cgst']:.2f}",
            f"{g['total_sgst']:.2f}",
            f"{g['total_tax']:.2f}",
            f"{g['gross_turnover']:.2f}"
        ])
    return Response(output.getvalue(), mimetype="text/csv", headers={"Content-disposition": "attachment; filename=electrodesk_gst_summary.csv"})


def compute_closing_totals(date_str):
    """Expected cash / UPI / card / bank for a day, computed ONLY from the database."""
    exp = {'cash': 0.0, 'upi': 0.0, 'card': 0.0, 'bank': 0.0}

    def bucket(method):
        m = (method or '').strip().lower()
        if m == 'cash':
            return 'cash'
        if m == 'upi':
            return 'upi'
        if m == 'card':
            return 'card'
        if m in ('net banking', 'bank', 'bank transfer', 'netbanking'):
            return 'bank'
        return None   # Pay Later / Credit / unknown: no money received at the counter

    # Money actually received at the time of sale (amount_paid) - unpaid credit sales add nothing.
    for s in db.query("SELECT payment_method, amount_paid FROM SALE WHERE DATE(sale_date) = %s", (date_str,)):
        b = bucket(s['payment_method'])
        if b:
            exp[b] += float(s['amount_paid'] or 0.0)

    # Dues collected later through the ledger
    for cp in db.query("SELECT payment_method, amount FROM CUSTOMER_PAYMENT WHERE DATE(payment_date) = %s", (date_str,)):
        b = bucket(cp['payment_method'])
        if b:
            exp[b] += float(cp['amount'] or 0.0)

    # Refunds paid out of the drawer
    refunds = db.query_one("SELECT COALESCE(SUM(refund_amount), 0.0) AS ref FROM CREDIT_NOTE WHERE DATE(created_at) = %s", (date_str,))
    exp['cash'] -= float((refunds or {}).get('ref') or 0.0)

    exp = {k: round(v, 2) for k, v in exp.items()}
    exp['total'] = round(exp['cash'] + exp['upi'] + exp['card'] + exp['bank'], 2)
    return exp


@app.route('/reports/daily-closing', methods=['GET', 'POST'])
@login_required
def daily_closing():
    today = get_app_today()
    selected_date = request.args.get('date') or today.strftime('%Y-%m-%d')

    if request.method == 'POST':
        closing_date = parse_date_str(request.form.get('closing_date'), 'Closing date').strftime('%Y-%m-%d')
        actual_cash = parse_float(request.form.get('actual_cash'), 'Actual cash', 0.0, minimum=0.0)
        notes = request.form.get('notes', 'Daily drawer reconciled').strip()[:500]
        closer = session.get('full_name', 'Cashier')

        # Expected figures are recomputed here - values posted by the browser are ignored,
        # so the cash difference cannot be faked by editing the form.
        exp = compute_closing_totals(closing_date)
        diff = round(actual_cash - exp['cash'], 2)

        try:
            with db.transaction() as tx:
                existing = tx.query_one("SELECT closing_id FROM DAILY_CLOSING WHERE closing_date = %s", (closing_date,))
                if existing and session.get('role') in ('Sales Staff', 'Staff'):
                    flash('This day is already closed. Only a Manager, Administrator or Owner can amend a finalised closing.', 'danger')
                    return redirect(url_for('daily_closing', date=closing_date))
                if existing:
                    tx.execute("""
                        UPDATE DAILY_CLOSING SET expected_cash = %s, actual_cash = %s, expected_upi = %s, expected_card = %s,
                               expected_total = %s, cash_difference = %s, notes = %s, closed_by = %s
                        WHERE closing_id = %s
                    """, (exp['cash'], actual_cash, exp['upi'], exp['card'], exp['total'], diff, notes, closer, existing['closing_id']))
                else:
                    tx.execute("""
                        INSERT INTO DAILY_CLOSING (closing_date, expected_cash, actual_cash, expected_upi, expected_card, expected_total, cash_difference, notes, closed_by)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (closing_date, exp['cash'], actual_cash, exp['upi'], exp['card'], exp['total'], diff, notes, closer))

            log_audit('DAILY_CLOSING', 'Finance', f"Completed daily closing for {closing_date}: Difference = ₹{diff:,.2f}")
            if abs(diff) < 0.01:
                flash(f"Daily closing for {closing_date} finalized: Drawer balanced perfectly (₹0 difference).", 'success')
            elif diff > 0:
                flash(f"Daily closing for {closing_date} saved with Cash Surplus: +₹{diff:,.2f}.", 'warning')
            else:
                flash(f"Daily closing for {closing_date} saved with Cash Shortage: -₹{abs(diff):,.2f}.", 'danger')
        except Exception as e:
            flash(f"Error saving closing: {_public_error(e)}", 'danger')

        return redirect(url_for('daily_closing', date=closing_date))

    selected_date = parse_date_str(selected_date, 'Date').strftime('%Y-%m-%d')
    exp = compute_closing_totals(selected_date)

    existing_closing = db.query_one("SELECT * FROM DAILY_CLOSING WHERE closing_date = %s", (selected_date,))
    past_closings = db.query("SELECT * FROM DAILY_CLOSING ORDER BY closing_date DESC LIMIT 10")

    return render_template('finance/daily_closing.html',
                           selected_date=selected_date,
                           expected_cash=exp['cash'],
                           expected_upi=exp['upi'],
                           expected_card=exp['card'],
                           expected_bank=exp['bank'],
                           expected_total=exp['total'],
                           existing_closing=existing_closing,
                           past_closings=past_closings)


# ==========================================================
# STEP 6: SYSTEM, AUDIT LOG, SETTINGS & UTILITIES
# ==========================================================

@app.route('/notifications')
@login_required
def notifications():
    today = get_app_today()
    today_str = today.strftime('%Y-%m-%d')
    exp_limit = (today + datetime.timedelta(days=30)).strftime('%Y-%m-%d')

    low_stock = db.query("SELECT * FROM PRODUCT WHERE stock_quantity <= reorder_level")
    expiring = db.query("""
        SELECT si.*, p.product_name, s.invoice_number, c.customer_name 
        FROM SALE_ITEM si
        JOIN PRODUCT p ON si.product_id = p.product_id
        JOIN SALE s ON si.sale_id = s.sale_id
        LEFT JOIN CUSTOMER c ON s.customer_id = c.customer_id
        WHERE si.warranty_expiry_date >= %s AND si.warranty_expiry_date <= %s
    """, (today_str, exp_limit))
    claims = db.query("SELECT * FROM WARRANTY_CLAIM WHERE status = 'Open'")
    dues = db.query("SELECT s.*, c.customer_name FROM SALE s LEFT JOIN CUSTOMER c ON s.customer_id = c.customer_id WHERE s.balance_due > 0")

    return render_template('system/notifications.html',
                           low_stock=low_stock,
                           expiring=expiring,
                           claims=claims,
                           dues=dues)


@app.route('/audit-log')
@login_required
@roles_required('Admin', 'Shop Owner')
def audit_log():
    logs = db.query("SELECT * FROM AUDIT_LOG ORDER BY log_id DESC LIMIT 100")
    return render_template('system/audit_log.html', logs=logs)


# Parent tables first (restore inserts in this order, deletes in reverse).
BACKUP_TABLES = [
    'USER', 'CATEGORY', 'SUPPLIER', 'CUSTOMER', 'PRODUCT', 'SALE', 'SALE_ITEM',
    'STOCK_MOVEMENT', 'WARRANTY_CLAIM', 'CREDIT_NOTE', 'CUSTOMER_PAYMENT',
    'PURCHASE_ORDER', 'PURCHASE_ORDER_ITEM', 'QUOTATION', 'QUOTATION_ITEM',
    'REPAIR_TICKET', 'EXPENSE', 'DAILY_CLOSING', 'AUDIT_LOG', 'STORE_SETTING'
]


@app.route('/settings', methods=['GET', 'POST'])
@login_required
@roles_required('Admin', 'Shop Owner')
def settings():
    today = get_app_today()

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'update_settings':
            app_today_mode = request.form.get('app_today_mode', 'auto')
            if app_today_mode not in ('auto', 'manual'):
                app_today_mode = 'auto'
            app_today_str = request.form.get('app_today')

            try:
                emi_3 = parse_float(request.form.get('emi_rate_3m'), 'EMI 3-month rate', 0.0, minimum=0.0, maximum=60.0)
                emi_6 = parse_float(request.form.get('emi_rate_6m'), 'EMI 6-month rate', 12.0, minimum=0.0, maximum=60.0)
                emi_9 = parse_float(request.form.get('emi_rate_9m'), 'EMI 9-month rate', 14.0, minimum=0.0, maximum=60.0)

                # Validate everything BEFORE saving anything so a bad value cannot leave settings half-applied.
                manual_date = None
                if app_today_mode == 'manual':
                    if not app_today_str:
                        raise InputError('Please choose a date for manual mode.')
                    manual_date = parse_date_str(app_today_str, 'Manual date').strftime('%Y-%m-%d')

                db.upsert_setting('app_today_mode', app_today_mode)
                if manual_date:
                    db.upsert_setting('app_today', manual_date)
                    audit_detail = f"Manual override set to {manual_date}"
                else:
                    db.upsert_setting('app_today', datetime.date.today().strftime('%Y-%m-%d'))
                    audit_detail = "Live system date mode enabled"

                # An empty banner is a valid way to clear it (previously it could never be cleared).
                if 'offers_banner' in request.form:
                    db.upsert_setting('offers_banner', request.form.get('offers_banner', '').strip()[:500])
                db.upsert_setting('emi_rate_3m', f"{emi_3:g}")
                db.upsert_setting('emi_rate_6m', f"{emi_6:g}")
                db.upsert_setting('emi_rate_9m', f"{emi_9:g}")

                log_audit('UPDATE_SETTINGS', 'Settings', f"Updated store settings ({audit_detail})")
                flash('Settings updated successfully.', 'success')
            except InputError as ie:
                flash(str(ie), 'danger')
            except Exception as e:
                flash(f"Error saving settings: {_public_error(e)}", 'danger')

        return redirect(url_for('settings'))

    settings_dict = {}
    rows = db.query("SELECT * FROM STORE_SETTING")
    for r in rows:
        settings_dict[r['setting_key']] = r['setting_value']

    return render_template('system/settings.html', settings=settings_dict, current_app_today=today)


@app.route('/settings/reset-demo', methods=['POST'])
@login_required
@roles_required('Admin', 'Shop Owner')
def settings_reset_demo():
    """Resets database back to default demonstration seed data (SQLite only)."""
    if db.is_mysql():
        flash('Demo reset is only available on the SQLite database. Re-run init_db.py --mysql on a fresh MySQL schema.', 'warning')
        return redirect(url_for('settings'))
    try:
        if os.path.exists(config.SQLITE_DB_PATH):
            os.remove(config.SQLITE_DB_PATH)
        init_db.init_sqlite_db()
        session.clear()   # the seeded users have new IDs/hashes - sign in again
        flash('Demo data reset successfully to clean initial state. Please sign in again.', 'success')
        return redirect(url_for('login'))
    except Exception as e:
        flash(f"Failed to reset demo data: {_public_error(e)}", 'danger')

    return redirect(url_for('settings'))


@app.route('/settings/backup-json')
@login_required
@roles_required('Admin', 'Shop Owner')
def settings_backup_json():
    """Exports all 20 tables to a downloadable JSON backup (password hashes are included - keep it private)."""
    backup = {'backup_date': datetime.datetime.now().isoformat(), 'version': 2, 'tables': {}}
    for tbl in BACKUP_TABLES:
        backup['tables'][tbl] = db.query(f"SELECT * FROM {tbl}")   # a failing table now surfaces instead of becoming an empty list

    log_audit('BACKUP_JSON', 'Settings', 'Downloaded full JSON backup')
    json_str = json.dumps(backup, default=str, indent=2)
    return Response(json_str, mimetype="application/json", headers={"Content-disposition": "attachment; filename=electrodesk_backup.json"})


@app.route('/settings/restore-json', methods=['POST'])
@login_required
@roles_required('Admin', 'Shop Owner')
def settings_restore_json():
    """
    Restores the database from a JSON backup made by 'Backup'. The restore runs in one
    transaction: if anything is wrong the existing data is left untouched.
    (Previously this wiped the DB, re-seeded demo data and reported success without
    loading a single row from the file.)
    """
    if 'file' not in request.files or not request.files['file'].filename:
        flash('No JSON backup file uploaded.', 'danger')
        return redirect(url_for('settings'))

    try:
        data = json.load(request.files['file'].stream)
    except (ValueError, UnicodeDecodeError):
        flash('The uploaded file is not valid JSON.', 'danger')
        return redirect(url_for('settings'))

    tables = data.get('tables') if isinstance(data, dict) else None
    if not isinstance(tables, dict) or not isinstance(tables.get('USER'), list) or not tables['USER']:
        flash('Invalid backup file: it must contain a "tables" section with at least one USER.', 'danger')
        return redirect(url_for('settings'))
    if not any(isinstance(u, dict) and u.get('status') == 'Active' for u in tables['USER']):
        flash('Invalid backup file: it contains no active user, restoring it would lock everyone out.', 'danger')
        return redirect(url_for('settings'))

    restored_rows = 0
    try:
        with db.transaction() as tx:
            present = [t for t in BACKUP_TABLES if t in tables]
            for tbl in reversed(present):
                tx.execute(f"DELETE FROM {tbl}")      # tables absent from the backup (e.g. AUDIT_LOG in old backups) are left alone
            for tbl in present:
                rows = tables.get(tbl) or []
                if not isinstance(rows, list) or not rows:
                    continue
                valid_cols = tx.columns(tbl)
                for row in rows:
                    if not isinstance(row, dict):
                        raise ValueError(f'Malformed row in table {tbl}')
                    cols = [c for c in row.keys() if c in valid_cols]
                    if not cols:
                        continue
                    placeholders = ', '.join(['%s'] * len(cols))
                    tx.execute(f"INSERT INTO {tbl} ({', '.join(cols)}) VALUES ({placeholders})",
                               tuple(row[c] for c in cols))
                    restored_rows += 1
    except Exception as e:
        flash(f"Restore failed - your existing data was NOT changed. ({_public_error(e)})", 'danger')
        return redirect(url_for('settings'))

    # The signed-in user might not exist in the restored data.
    if not db.query_one("SELECT user_id FROM USER WHERE user_id = %s AND status = 'Active'", (session.get('user_id'),)):
        session.clear()
        flash(f'Database restored ({restored_rows} rows). Please sign in again.', 'success')
        return redirect(url_for('login'))

    log_audit('RESTORE_JSON', 'Settings', f"Restored database from JSON backup ({restored_rows} rows)")
    flash(f'Database successfully restored from JSON backup ({restored_rows} rows).', 'success')
    return redirect(url_for('settings'))


@app.route('/api/global-search')
@login_required
def api_global_search():
    q = request.args.get('q', '').strip()
    if not q or len(q) < 2:
        return jsonify({'results': []})

    s = f"%{q}%"
    results = []

    # Search Products
    prods = db.query("SELECT product_id, product_name, product_code, selling_price FROM PRODUCT WHERE product_name LIKE %s OR product_code LIKE %s LIMIT 4", (s, s))
    for p in prods:
        results.append({
            'type': 'Product',
            'title': p['product_name'],
            'subtitle': f"SKU: {p['product_code']} • ₹{p['selling_price']:,.0f}",
            'url': url_for('products') + f"?search={p['product_code']}"
        })

    # Search Invoices
    invs = db.query("SELECT sale_id, invoice_number, grand_total, sale_date FROM SALE WHERE invoice_number LIKE %s LIMIT 3", (s,))
    for i in invs:
        results.append({
            'type': 'Invoice',
            'title': i['invoice_number'],
            'subtitle': f"Total: ₹{i['grand_total']:,.0f} • Date: {i['sale_date'][:10]}",
            'url': url_for('invoice_view', sale_id=i['sale_id'])
        })

    # Search Customers
    custs = db.query("SELECT customer_id, customer_name, phone FROM CUSTOMER WHERE customer_name LIKE %s OR phone LIKE %s LIMIT 3", (s, s))
    for c in custs:
        results.append({
            'type': 'Customer',
            'title': c['customer_name'],
            'subtitle': f"Phone: {c['phone']}",
            'url': url_for('customer_detail', customer_id=c['customer_id'])
        })

    # Search Warranties
    warrs = db.query("""
        SELECT si.serial_number, p.product_name, s.sale_id
        FROM SALE_ITEM si
        JOIN PRODUCT p ON si.product_id = p.product_id
        JOIN SALE s ON si.sale_id = s.sale_id
        WHERE UPPER(si.serial_number) LIKE %s LIMIT 3
    """, (s.upper(),))
    for w in warrs:
        results.append({
            'type': 'Warranty Serial',
            'title': w['serial_number'],
            'subtitle': f"Device: {w['product_name']}",
            'url': url_for('warranty') + f"?search={w['serial_number']}"
        })

    return jsonify({'results': results})


# ==========================================================
# USER MANAGEMENT (ADMIN ONLY)
# ==========================================================

@app.route('/users')
@login_required
@roles_required('Admin', 'Shop Owner')
def users():
    users_list = db.query("""
        SELECT u.*,
               COALESCE((SELECT COUNT(*) FROM SALE s WHERE s.user_id = u.user_id), 0) as sales_count,
               COALESCE((SELECT SUM(s.grand_total) FROM SALE s WHERE s.user_id = u.user_id), 0.0) as sales_volume
        FROM USER u
        ORDER BY u.user_id ASC
    """)
    matrix = [
        {'module': 'Dashboard & Overview', 'desc': 'View KPI metrics, charts and alerts',
         'admin': True, 'owner': True, 'manager': True, 'staff': True, 'delivery': False,
         'roles': {'System Administrator': True, 'Shop Owner': True, 'Shop Manager': True, 'Sales Staff': True, 'Delivery Staff': False}},
        {'module': 'POS & New Sale', 'desc': 'Barcode scan, billing, real-time QR code & card processing',
         'admin': True, 'owner': True, 'manager': True, 'staff': True, 'delivery': False,
         'roles': {'System Administrator': True, 'Shop Owner': True, 'Shop Manager': True, 'Sales Staff': True, 'Delivery Staff': False}},
        {'module': 'Products Catalog', 'desc': 'View pricing, SKUs, models and warranties',
         'admin': True, 'owner': True, 'manager': True, 'staff': True, 'delivery': True,
         'roles': {'System Administrator': True, 'Shop Owner': True, 'Shop Manager': True, 'Sales Staff': True, 'Delivery Staff': True}},
        {'module': 'Product CRUD & Pricing', 'desc': 'Create, edit, delete and modify pricing',
         'admin': True, 'owner': True, 'manager': True, 'staff': False, 'delivery': False,
         'roles': {'System Administrator': True, 'Shop Owner': True, 'Shop Manager': True, 'Sales Staff': False, 'Delivery Staff': False}},
        {'module': 'Inventory Restock', 'desc': 'Manual stock in/out and adjustments',
         'admin': True, 'owner': True, 'manager': True, 'staff': False, 'delivery': False,
         'roles': {'System Administrator': True, 'Shop Owner': True, 'Shop Manager': True, 'Sales Staff': False, 'Delivery Staff': False}},
        {'module': 'Delivery Dispatch & Tracking', 'desc': 'Track deliveries, assign routes & verify OTPs',
         'admin': True, 'owner': True, 'manager': True, 'staff': True, 'delivery': True,
         'roles': {'System Administrator': True, 'Shop Owner': True, 'Shop Manager': True, 'Sales Staff': True, 'Delivery Staff': True}},
        {'module': 'Warranty & Service', 'desc': 'Serial lookup and register warranty claims',
         'admin': True, 'owner': True, 'manager': True, 'staff': True, 'delivery': False,
         'roles': {'System Administrator': True, 'Shop Owner': True, 'Shop Manager': True, 'Sales Staff': True, 'Delivery Staff': False}},
        {'module': 'Customer CRM', 'desc': 'Customer directory, history and ledger',
         'admin': True, 'owner': True, 'manager': True, 'staff': True, 'delivery': False,
         'roles': {'System Administrator': True, 'Shop Owner': True, 'Shop Manager': True, 'Sales Staff': True, 'Delivery Staff': False}},
        {'module': 'Quotations & Returns', 'desc': 'Price estimates, credit notes and returns',
         'admin': True, 'owner': True, 'manager': True, 'staff': False, 'delivery': False,
         'roles': {'System Administrator': True, 'Shop Owner': True, 'Shop Manager': True, 'Sales Staff': False, 'Delivery Staff': False}},
        {'module': 'Financial Reports & P&L', 'desc': 'Sales reports, GST, expenses, P&L',
         'admin': True, 'owner': True, 'manager': True, 'staff': False, 'delivery': False,
         'roles': {'System Administrator': True, 'Shop Owner': True, 'Shop Manager': True, 'Sales Staff': False, 'Delivery Staff': False}},
        {'module': 'Settings & Audit Log', 'desc': 'Store settings, backup, date override',
         'admin': True, 'owner': True, 'manager': False, 'staff': False, 'delivery': False,
         'roles': {'System Administrator': True, 'Shop Owner': True, 'Shop Manager': False, 'Sales Staff': False, 'Delivery Staff': False}}
    ]
    return render_template('users.html', users=users_list, matrix=matrix)


ROLE_CANONICAL = {
    'System Administrator': 'System Administrator', 'Admin': 'System Administrator',
    'Shop Owner': 'Shop Owner', 'Owner': 'Shop Owner',
    'Shop Manager': 'Shop Manager', 'Manager': 'Shop Manager',
    'Sales Staff': 'Sales Staff', 'Staff': 'Sales Staff',
    'Delivery Staff': 'Delivery Staff', 'Delivery': 'Delivery Staff',
}
PRIVILEGED_ROLES = ('System Administrator', 'Admin', 'Shop Owner', 'Owner')


def _actor_is_owner():
    return session.get('role') in ('Shop Owner', 'Owner')


def _clean_role(raw):
    role = ROLE_CANONICAL.get((raw or '').strip())
    if not role:
        raise InputError('Please choose a valid role.')
    return role


def _other_active_privileged(exclude_user_id):
    placeholders = ', '.join(['%s'] * len(PRIVILEGED_ROLES))
    row = db.query_one(
        f"SELECT COUNT(*) AS cnt FROM USER WHERE status = 'Active' AND user_id != %s AND role IN ({placeholders})",
        (exclude_user_id,) + PRIVILEGED_ROLES)
    return (row or {}).get('cnt', 0)


@app.route('/users/add', methods=['POST'])
@login_required
@roles_required('Admin', 'Shop Owner')
def user_add():
    username = request.form.get('username', '').strip().lower()
    full_name = request.form.get('full_name', '').strip()
    role = _clean_role(request.form.get('role', 'Sales Staff'))
    password = request.form.get('password', '').strip()
    email = request.form.get('email', '').strip()[:100]
    phone = request.form.get('phone', '').strip()[:30]

    if not re.fullmatch(r'[a-z0-9._-]{3,50}', username):
        raise InputError('Username must be 3-50 characters: letters, numbers, dot, dash or underscore.')
    if not full_name:
        raise InputError('Full name is required.')
    if len(password) < 6:
        raise InputError('Password must be at least 6 characters long.')
    if email and not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', email):
        raise InputError('Please enter a valid email address.')
    if role == 'Shop Owner' and not _actor_is_owner():
        flash('Only a Shop Owner can create another Shop Owner account.', 'danger')
        return redirect(url_for('users'))

    avatar = get_avatar(username, full_name)

    if db.query_one("SELECT user_id FROM USER WHERE LOWER(username) = %s", (username,)):
        flash(f'Username "{username}" is already taken.', 'warning')
        return redirect(url_for('users'))

    try:
        db.execute("""
            INSERT INTO USER (username, password_hash, full_name, role, avatar, email, phone, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'Active')
        """, (username, generate_password_hash(password), full_name, role, avatar, email, phone))
        log_audit('CREATE_USER', 'Users', f"Created user {full_name} ({username}) as {role}")
        flash(f'User "{full_name}" created successfully.', 'success')
    except Exception as e:
        flash(f'Error creating user: {_public_error(e)}', 'danger')

    return redirect(url_for('users'))


@app.route('/users/edit/<int:user_id>', methods=['POST'])
@login_required
@roles_required('Admin', 'Shop Owner')
def user_edit(user_id):
    target = db.query_one("SELECT * FROM USER WHERE user_id = %s", (user_id,))
    if not target:
        flash('User not found.', 'danger')
        return redirect(url_for('users'))

    full_name = request.form.get('full_name', '').strip() or target['full_name']
    role = _clean_role(request.form.get('role') or target['role'])
    status = request.form.get('status', target['status'])
    email = request.form.get('email', '').strip()[:100]
    phone = request.form.get('phone', '').strip()[:30]
    password = request.form.get('password', '').strip()

    if status not in ('Active', 'Inactive'):
        raise InputError('Invalid status.')
    if password and len(password) < 6:
        raise InputError('Password must be at least 6 characters long.')
    if email and not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', email):
        raise InputError('Please enter a valid email address.')

    target_is_owner = ROLE_CANONICAL.get(target['role']) == 'Shop Owner'
    if (target_is_owner or role == 'Shop Owner') and not _actor_is_owner():
        flash('Only a Shop Owner can modify or create Shop Owner accounts.', 'danger')
        return redirect(url_for('users'))

    is_self = user_id == session.get('user_id')
    if is_self and (status != 'Active' or role != ROLE_CANONICAL.get(target['role'])):
        flash('You cannot deactivate your own account or change your own role.', 'danger')
        return redirect(url_for('users'))

    removes_privilege = target['role'] in PRIVILEGED_ROLES and target['status'] == 'Active' and \
        (status != 'Active' or role not in ('System Administrator', 'Shop Owner'))
    if removes_privilege and _other_active_privileged(user_id) == 0:
        flash('At least one active Administrator or Owner account must remain.', 'danger')
        return redirect(url_for('users'))

    avatar = get_avatar(target['username'], full_name)
    try:
        if password:
            db.execute("""
                UPDATE USER
                SET full_name = %s, role = %s, status = %s, email = %s, phone = %s, avatar = %s, password_hash = %s
                WHERE user_id = %s
            """, (full_name, role, status, email, phone, avatar, generate_password_hash(password), user_id))
        else:
            db.execute("""
                UPDATE USER
                SET full_name = %s, role = %s, status = %s, email = %s, phone = %s, avatar = %s
                WHERE user_id = %s
            """, (full_name, role, status, email, phone, avatar, user_id))
        log_audit('UPDATE_USER', 'Users', f"Updated profile for user #{user_id}")
        flash(f'User #{user_id} profile updated.', 'success')
    except Exception as e:
        flash(f'Error updating user: {_public_error(e)}', 'danger')

    return redirect(url_for('users'))


@app.route('/users/delete/<int:user_id>', methods=['POST'])
@login_required
@roles_required('Admin', 'Shop Owner')
def user_delete(user_id):
    if user_id == session.get('user_id'):
        flash('You cannot delete your own currently logged-in account.', 'danger')
        return redirect(url_for('users'))

    target = db.query_one("SELECT * FROM USER WHERE user_id = %s", (user_id,))
    if not target:
        flash('User not found.', 'danger')
        return redirect(url_for('users'))
    if ROLE_CANONICAL.get(target['role']) == 'Shop Owner' and not _actor_is_owner():
        flash('Only a Shop Owner can delete a Shop Owner account.', 'danger')
        return redirect(url_for('users'))
    if target['role'] in PRIVILEGED_ROLES and target['status'] == 'Active' and _other_active_privileged(user_id) == 0:
        flash('At least one active Administrator or Owner account must remain.', 'danger')
        return redirect(url_for('users'))

    try:
        db.execute("DELETE FROM USER WHERE user_id = %s", (user_id,))
        log_audit('DELETE_USER', 'Users', f"Deleted user #{user_id}")
        flash('User account deleted successfully.', 'success')
    except Exception as e:
        if _is_fk_error(e):
            flash('This user has sales or other records and cannot be deleted. Set the account to Inactive instead.', 'warning')
        else:
            flash(f'Failed to delete user: {_public_error(e)}', 'danger')

    return redirect(url_for('users'))


# ==========================================================
# APPLICATION ENTRYPOINT
# ==========================================================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"Starting Electrodesk Enterprise System on http://127.0.0.1:{port}")
    app.run(host=config.HOST, port=port, debug=config.DEBUG)
