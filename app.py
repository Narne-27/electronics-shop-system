"""
Electrodesk - Electronics Shop Management System
Main Flask Application - Comprehensive Enterprise Edition
"""
import os
import io
import csv
import json
import datetime
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

# Ensure database is initialized on startup
with app.app_context():
    init_db.ensure_db_initialized()


# ==========================================================
# DYNAMIC TIME & APP_TODAY CONSTANT HELPER
# ==========================================================

def get_app_today():
    """
    Returns the dynamic APP_TODAY anchor.
    Can be overridden at runtime via STORE_SETTING 'app_today'.
    Defaults to config.APP_TODAY (2026-11-19).
    """
    try:
        row = db.query_one("SELECT setting_value FROM STORE_SETTING WHERE setting_key = 'app_today'")
        if row and row['setting_value']:
            return datetime.datetime.strptime(row['setting_value'][:10], '%Y-%m-%d').date()
    except Exception:
        pass
    return getattr(config, 'APP_TODAY', datetime.date(2026, 11, 19))


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
        'Sales Staff': ['Sales Staff', 'Staff']
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
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

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
            return redirect(next_page if next_page else url_for('dashboard'))
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
# DASHBOARD ROUTE (DERIVED NUMBERS & EXPIRING WIDGET)
# ==========================================================

@app.route('/')
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

    return render_template('products.html',
                           products=products_list,
                           categories=categories,
                           search=search,
                           selected_category=category_id,
                           stock_filter=stock_filter,
                           current_sort=sort_by)


@app.route('/products/add', methods=['POST'])
@login_required
@roles_required('Admin', 'Manager', 'Shop Owner')
def product_add():
    code = request.form.get('product_code', '').strip().upper()
    name = request.form.get('product_name', '').strip()
    category_id = request.form.get('category_id')
    brand = request.form.get('brand', '').strip()
    model = request.form.get('model', '').strip()
    hsn_code = request.form.get('hsn_code', '8517').strip()
    tagline = request.form.get('tagline', '').strip()
    is_new = 1 if request.form.get('is_new') else 0
    cost_price = float(request.form.get('cost_price', 0.0) or 0.0)
    selling_price = float(request.form.get('selling_price', 0.0) or 0.0)
    stock_qty = int(request.form.get('stock_quantity', 0) or 0)
    reorder = int(request.form.get('reorder_level', 5) or 5)
    warranty = int(request.form.get('warranty_months', 12) or 12)
    desc = request.form.get('description', '').strip()

    if not code or not name or not category_id:
        flash('Product SKU, Name, and Category are required.', 'danger')
        return redirect(url_for('products'))

    existing = db.query_one("SELECT product_id FROM PRODUCT WHERE product_code = %s", (code,))
    if existing:
        flash(f'Product SKU "{code}" already exists in the system.', 'warning')
        return redirect(url_for('products'))

    try:
        db.execute("""
            INSERT INTO PRODUCT 
            (product_code, product_name, category_id, brand, model, hsn_code, tagline, is_new, cost_price, selling_price, stock_quantity, reorder_level, warranty_months, description)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (code, name, category_id, brand, model, hsn_code, tagline, is_new, cost_price, selling_price, stock_qty, reorder, warranty, desc))

        new_id = db.query_one("SELECT product_id FROM PRODUCT WHERE product_code = %s", (code,))['product_id']
        if stock_qty > 0:
            db.execute("""
                INSERT INTO STOCK_MOVEMENT (product_id, movement_type, quantity, reason, reference_id, notes)
                VALUES (%s, 'IN', %s, 'Initial Addition', 'PROD-ADD', 'New product catalog entry')
            """, (new_id, stock_qty))

        log_audit('CREATE_PRODUCT', 'Catalog', f"Created product {name} ({code})")
        flash(f'Product "{name}" added successfully.', 'success')
    except Exception as e:
        flash(f'Error adding product: {str(e)}', 'danger')

    return redirect(url_for('products'))


@app.route('/products/edit/<int:product_id>', methods=['POST'])
@login_required
@roles_required('Admin', 'Manager', 'Shop Owner')
def product_edit(product_id):
    code = request.form.get('product_code', '').strip().upper()
    name = request.form.get('product_name', '').strip()
    category_id = request.form.get('category_id')
    brand = request.form.get('brand', '').strip()
    model = request.form.get('model', '').strip()
    hsn_code = request.form.get('hsn_code', '8517').strip()
    tagline = request.form.get('tagline', '').strip()
    is_new = 1 if request.form.get('is_new') else 0
    cost_price = float(request.form.get('cost_price', 0.0) or 0.0)
    selling_price = float(request.form.get('selling_price', 0.0) or 0.0)
    stock_quantity = int(request.form.get('stock_quantity', 0) or 0)
    reorder_level = int(request.form.get('reorder_level', 5) or 5)
    warranty_months = int(request.form.get('warranty_months', 12) or 12)
    description = request.form.get('description', '').strip()

    existing = db.query_one("SELECT product_id FROM PRODUCT WHERE product_code = %s AND product_id != %s", (code, product_id))
    if existing:
        flash(f'Product code "{code}" is in use by another item.', 'warning')
        return redirect(url_for('products'))

    try:
        db.execute("""
            UPDATE PRODUCT
            SET product_code = %s, product_name = %s, category_id = %s, brand = %s, model = %s,
                hsn_code = %s, tagline = %s, is_new = %s, cost_price = %s, selling_price = %s,
                stock_quantity = %s, reorder_level = %s, warranty_months = %s, description = %s
            WHERE product_id = %s
        """, (code, name, category_id, brand, model, hsn_code, tagline, is_new, cost_price, selling_price,
              stock_quantity, reorder_level, warranty_months, description, product_id))
        log_audit('UPDATE_PRODUCT', 'Catalog', f"Updated product {name} (#{product_id})")
        flash(f'Product "{name}" updated successfully.', 'success')
    except Exception as e:
        flash(f'Error updating product: {str(e)}', 'danger')

    return redirect(url_for('products'))


@app.route('/products/delete/<int:product_id>', methods=['POST'])
@login_required
@roles_required('Admin', 'Manager', 'Shop Owner')
def product_delete(product_id):
    sales_ref = db.query_one("SELECT COUNT(*) as count FROM SALE_ITEM WHERE product_id = %s", (product_id,))
    if sales_ref and sales_ref['count'] > 0:
        flash(f'Cannot delete product: {sales_ref["count"]} historical invoice sales records exist.', 'warning')
        return redirect(url_for('products'))

    try:
        db.execute("DELETE FROM STOCK_MOVEMENT WHERE product_id = %s", (product_id,))
        db.execute("DELETE FROM PRODUCT WHERE product_id = %s", (product_id,))
        log_audit('DELETE_PRODUCT', 'Catalog', f"Deleted product #{product_id}")
        flash('Product deleted successfully.', 'success')
    except Exception as e:
        flash(f'Failed to delete product: {str(e)}', 'danger')

    return redirect(url_for('products'))


@app.route('/products/import-csv', methods=['POST'])
@login_required
@roles_required('Admin', 'Manager', 'Shop Owner')
def products_import_csv():
    """Bulk import products via standard CSV file."""
    if 'file' not in request.files:
        flash('No CSV file uploaded.', 'danger')
        return redirect(url_for('products'))

    file = request.files['file']
    if not file.filename.endswith('.csv'):
        flash('Please upload a valid .csv file.', 'danger')
        return redirect(url_for('products'))

    try:
        stream = io.StringIO(file.stream.read().decode("utf-8"), newline=None)
        reader = csv.DictReader(stream)
        imported_count = 0

        for row in reader:
            code = row.get('SKU') or row.get('product_code')
            name = row.get('Name') or row.get('product_name')
            if not code or not name:
                continue

            cat_name = row.get('Category') or 'Smartphones & Tablets'
            cat = db.query_one("SELECT category_id FROM CATEGORY WHERE category_name LIKE %s", (f"%{cat_name}%",))
            cid = cat['category_id'] if cat else 1

            brand = row.get('Brand') or 'Generic'
            model = row.get('Model') or ''
            hsn = row.get('HSN') or '8517'
            cost = float(row.get('Cost') or row.get('cost_price') or 0.0)
            price = float(row.get('Price') or row.get('selling_price') or 0.0)
            stock = int(row.get('Stock') or row.get('stock_quantity') or 10)
            reorder = int(row.get('Reorder') or 5)
            warranty = int(row.get('Warranty') or 12)

            existing = db.query_one("SELECT product_id FROM PRODUCT WHERE product_code = %s", (code.strip().upper(),))
            if existing:
                db.execute("""
                    UPDATE PRODUCT SET product_name = %s, cost_price = %s, selling_price = %s, stock_quantity = %s
                    WHERE product_id = %s
                """, (name, cost, price, stock, existing['product_id']))
            else:
                db.execute("""
                    INSERT INTO PRODUCT (product_code, product_name, category_id, brand, model, hsn_code, cost_price, selling_price, stock_quantity, reorder_level, warranty_months)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (code.strip().upper(), name, cid, brand, model, hsn, cost, price, stock, reorder, warranty))
            imported_count += 1

        log_audit('CSV_IMPORT', 'Catalog', f"Imported {imported_count} products from CSV")
        flash(f'Successfully imported/updated {imported_count} products from CSV.', 'success')
    except Exception as e:
        flash(f'Error processing CSV file: {str(e)}', 'danger')

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
        flash(f'Error creating category: {str(e)}', 'danger')

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
        flash(f'Error updating category: {str(e)}', 'danger')

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
        flash(f'Error deleting category: {str(e)}', 'danger')

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
    product_id = request.form.get('product_id')
    adj_type = request.form.get('type')  # 'add', 'deduct', 'set'
    quantity = int(request.form.get('quantity', 0))
    notes = request.form.get('notes', 'Physical Audit Adjustment').strip()

    product = db.query_one("SELECT * FROM PRODUCT WHERE product_id = %s", (product_id,))
    if not product:
        flash('Product not found.', 'danger')
        return redirect(url_for('inventory'))

    current_stock = product['stock_quantity']

    if adj_type == 'add':
        new_stock = current_stock + quantity
        m_type = 'IN'
        diff = quantity
    elif adj_type == 'deduct':
        new_stock = max(0, current_stock - quantity)
        m_type = 'OUT'
        diff = quantity
    elif adj_type == 'set':
        diff = abs(quantity - current_stock)
        m_type = 'IN' if quantity >= current_stock else 'OUT'
        new_stock = max(0, quantity)
    else:
        flash('Invalid adjustment type.', 'danger')
        return redirect(url_for('inventory'))

    try:
        db.execute("UPDATE PRODUCT SET stock_quantity = %s WHERE product_id = %s", (new_stock, product_id))
        db.execute("""
            INSERT INTO STOCK_MOVEMENT (product_id, movement_type, quantity, reason, reference_id, notes)
            VALUES (%s, %s, %s, 'Manual Adjustment', 'ADJ-MANUAL', %s)
        """, (product_id, m_type, diff, notes))

        log_audit('STOCK_ADJUST', 'Inventory', f"Adjusted {product['product_name']}: {current_stock} -> {new_stock} ({notes})")
        flash(f"Stock for '{product['product_name']}' successfully updated to {new_stock} units.", 'success')
    except Exception as e:
        flash(f'Error adjusting stock: {str(e)}', 'danger')

    return redirect(url_for('inventory'))


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
        flash(f'Error adding customer: {str(e)}', 'danger')

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
        flash(f'Error updating customer: {str(e)}', 'danger')

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
        flash(f'Error deleting customer: {str(e)}', 'danger')

    return redirect(url_for('customers'))


# ==========================================================
# STEP 2: NEW SALE (POS, EMI, EXCHANGE, SERIALS, DISCOUNTS)
# ==========================================================

@app.route('/pos')
@login_required
def pos():
    products = db.query("""
        SELECT p.*, c.category_name 
        FROM PRODUCT p
        JOIN CATEGORY c ON p.category_id = c.category_id
        ORDER BY p.product_name ASC
    """)
    categories = db.query("SELECT * FROM CATEGORY ORDER BY category_code ASC")
    customers = db.query("SELECT * FROM CUSTOMER ORDER BY customer_name ASC")

    return render_template('pos.html',
                           products=products,
                           categories=categories,
                           customers=customers,
                           coupons=config.ACTIVE_COUPONS,
                           emi_plans=config.EMI_PLANS)


@app.route('/api/pos/validate-coupon', methods=['POST'])
@login_required
def pos_validate_coupon():
    data = request.get_json() or {}
    code = (data.get('coupon_code') or '').strip().upper()
    subtotal = float(data.get('subtotal') or 0.0)

    if code in config.ACTIVE_COUPONS:
        c = config.ACTIVE_COUPONS[code]
        if 'min_order' in c and subtotal < c['min_order']:
            return jsonify({'valid': False, 'message': f"Order must be at least ₹{c['min_order']:,} to use this coupon."})

        if c['type'] == 'percent':
            discount = round(subtotal * (c['value'] / 100.0), 2)
            if 'max_discount' in c:
                discount = min(discount, c['max_discount'])
        else:
            discount = min(subtotal, c['value'])

        requires_owner = c['value'] > 10.0 if c['type'] == 'percent' else False
        return jsonify({
            'valid': True,
            'code': code,
            'discount': discount,
            'description': c['description'],
            'requires_owner_approval': requires_owner
        })

    return jsonify({'valid': False, 'message': 'Invalid coupon code.'})


@app.route('/api/pos/checkout', methods=['POST'])
@app.route('/pos/checkout', methods=['POST'])
@login_required
def pos_checkout():
    """
    Automatic billing checkout:
    - Atomically validates stock and deducts inventory
    - Enforces mandatory serial numbers for Phones, Laptops, TVs
    - Rejects duplicate active serials
    - Applies coupon, EMI, exchange device valuation
    - Requires Owner PIN if discount exceeds 10%
    - Inserts SALE, SALE_ITEM, and STOCK_MOVEMENT
    """
    data = request.get_json()
    if not data or not data.get('items'):
        return jsonify({'success': False, 'message': 'Cart is empty. Add items to checkout.'}), 400

    items = data.get('items', [])
    customer_id = data.get('customer_id') or None
    payment_method = data.get('payment_method', 'Cash')
    payment_status = data.get('payment_status', 'Paid')
    tax_rate = float(data.get('tax_rate', config.DEFAULT_TAX_RATE))
    discount_amount = float(data.get('discount_amount', 0.0) or 0.0)
    discount_type = data.get('discount_type', 'none')
    exchange_device = (data.get('exchange_device') or '').strip()
    exchange_value = float(data.get('exchange_value', 0.0) or 0.0)
    emi_months = int(data.get('emi_months', 0) or 0)
    owner_pin = str(data.get('owner_pin', '')).strip()
    notes = data.get('notes', 'Retail counter sale')
    today = get_app_today()

    # Verify inventory and serials
    subtotal = 0.0
    processed_items = []
    used_serials = set()

    for it in items:
        pid = it.get('product_id')
        qty = int(it.get('quantity', 1))
        serial = (it.get('serial_number') or '').strip().upper()

        prod = db.query_one("SELECT p.*, c.category_name FROM PRODUCT p JOIN CATEGORY c ON p.category_id = c.category_id WHERE p.product_id = %s", (pid,))
        if not prod:
            return jsonify({'success': False, 'message': f'Product #{pid} not found.'}), 400

        if prod['stock_quantity'] < qty:
            return jsonify({
                'success': False,
                'message': f"Insufficient stock for '{prod['product_name']}'. Available: {prod['stock_quantity']}, Requested: {qty}"
            }), 400

        # Mandatory serial enforcement for high-value hardware
        cat_lower = prod['category_name'].lower()
        needs_serial = any(k in cat_lower for k in ['phone', 'laptop', 'tv', 'display', 'tablet'])

        if needs_serial and not serial:
            return jsonify({
                'success': False,
                'message': f"Serial / IMEI number is strictly required for '{prod['product_name']}'."
            }), 400

        if serial:
            if serial in used_serials:
                return jsonify({'success': False, 'message': f"Duplicate serial number in cart: {serial}"}), 400
            used_serials.add(serial)

            # Check if serial already exists in active warranty records
            dup_check = db.query_one("SELECT item_id FROM SALE_ITEM WHERE UPPER(serial_number) = %s", (serial,))
            if dup_check:
                return jsonify({'success': False, 'message': f"Serial number '{serial}' already exists in database records."}), 400

        line_price = float(prod['selling_price']) * qty
        subtotal += line_price
        processed_items.append({
            'product': prod,
            'quantity': qty,
            'unit_price': float(prod['selling_price']),
            'total_price': line_price,
            'serial_number': serial,
            'warranty_months': int(prod['warranty_months'])
        })

    # Discount verification: > 10% requires Owner Approval
    discount_pct = (discount_amount / subtotal * 100.0) if subtotal > 0 else 0.0
    owner_approved = 0

    if discount_pct > 10.0:
        is_owner = session.get('role') in ['Shop Owner', 'Owner']
        if is_owner or owner_pin == config.OWNER_APPROVAL_PIN:
            owner_approved = 1
        else:
            return jsonify({
                'success': False,
                'message': f"Discounts exceeding 10% ({discount_pct:.1f}%) require Shop Owner approval PIN."
            }), 403

    taxable_subtotal = max(0.0, subtotal - discount_amount - exchange_value)
    tax_amount = round(taxable_subtotal * (tax_rate / 100.0), 2)
    cgst_amount = round(tax_amount / 2.0, 2)
    sgst_amount = round(tax_amount - cgst_amount, 2)
    grand_total = round(taxable_subtotal + tax_amount, 2)

    # EMI calculation
    emi_interest_rate = 0.0
    emi_monthly = 0.0
    if emi_months > 0:
        emi_interest_rate = config.EMI_PLANS.get(emi_months, {}).get('interest_rate', 12.0)
        interest_amt = grand_total * (emi_interest_rate / 100.0) * (emi_months / 12.0)
        emi_grand = grand_total + interest_amt
        emi_monthly = round(emi_grand / emi_months, 2)

    # Payment ledger calculations
    if payment_method in ['Pay Later', 'Credit']:
        payment_status = 'Pending'
        amount_paid = 0.0
        balance_due = grand_total
    elif payment_status == 'Partial':
        amount_paid = float(data.get('amount_paid', grand_total * 0.5))
        balance_due = max(0.0, grand_total - amount_paid)
    else:
        payment_status = 'Paid'
        amount_paid = grand_total
        balance_due = 0.0

    # Sequential invoice number: INV-2026-XXXX
    last_sale = db.query_one("SELECT invoice_number FROM SALE ORDER BY sale_id DESC LIMIT 1")
    next_seq = 1
    if last_sale and last_sale.get('invoice_number'):
        try:
            parts = last_sale['invoice_number'].split('-')
            next_seq = int(parts[-1]) + 1
        except Exception:
            next_seq = 1

    inv_year = today.year
    invoice_number = f"INV-{inv_year}-{next_seq:04d}"

    # While collision loop (safety)
    while db.query_one("SELECT sale_id FROM SALE WHERE invoice_number = %s", (invoice_number,)):
        next_seq += 1
        invoice_number = f"INV-{inv_year}-{next_seq:04d}"

    sale_datetime = f"{today.strftime('%Y-%m-%d')} {datetime.datetime.now().strftime('%H:%M:%S')}"
    user_id = session.get('user_id', 1)

    try:
        db.execute("""
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
            discount_type, discount_pct, owner_approved,
            exchange_device, exchange_value, grand_total,
            payment_method, payment_status, amount_paid, balance_due,
            emi_months, emi_interest_rate, emi_monthly, notes
        ))

        sale_row = db.query_one("SELECT sale_id FROM SALE WHERE invoice_number = %s", (invoice_number,))
        sale_id = sale_row['sale_id']

        # Process each item: insert SALE_ITEM, reduce stock, record STOCK_MOVEMENT
        for it in processed_items:
            exp_date = today + datetime.timedelta(days=it['warranty_months'] * 30)
            exp_str = exp_date.strftime('%Y-%m-%d')

            db.execute("""
                INSERT INTO SALE_ITEM (sale_id, product_id, quantity, unit_price, total_price, serial_number, warranty_months, warranty_expiry_date)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (sale_id, it['product']['product_id'], it['quantity'], it['unit_price'], it['total_price'], it['serial_number'], it['warranty_months'], exp_str))

            # Stock reduction & movement audit
            db.execute("UPDATE PRODUCT SET stock_quantity = stock_quantity - %s WHERE product_id = %s", (it['quantity'], it['product']['product_id']))
            db.execute("""
                INSERT INTO STOCK_MOVEMENT (product_id, movement_type, quantity, reason, reference_id, notes)
                VALUES (%s, 'OUT', %s, 'Customer Sale', %s, 'POS invoice checkout')
            """, (it['product']['product_id'], it['quantity'], invoice_number))

        log_audit('POS_CHECKOUT', 'Sales', f"Completed sale {invoice_number} (Total: ₹{grand_total:,.2f})")

        return jsonify({
            'success': True,
            'message': 'Sale completed successfully.',
            'sale_id': sale_id,
            'invoice_number': invoice_number
        })

    except Exception as e:
        return jsonify({'success': False, 'message': f'Checkout failed: {str(e)}'}), 500


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
            cust.customer_id, cust.customer_name, cust.phone as customer_phone
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
    claims_count = db.query_one("SELECT COUNT(*) as count FROM WARRANTY_CLAIM WHERE status = 'Open'")['count']
    open_claims = db.query("""
        SELECT wc.*, cust.customer_name, cust.phone, p.product_name
        FROM WARRANTY_CLAIM wc
        LEFT JOIN CUSTOMER cust ON wc.customer_id = cust.customer_id
        LEFT JOIN PRODUCT p ON wc.product_id = p.product_id
        WHERE wc.status = 'Open'
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
    serial = request.form.get('serial_number', '').strip().upper()
    issue = request.form.get('issue_description', '').strip()
    today = get_app_today()

    item = db.query_one("""
        SELECT si.*, s.customer_id 
        FROM SALE_ITEM si 
        JOIN SALE s ON si.sale_id = s.sale_id
        WHERE UPPER(si.serial_number) = %s
    """, (serial,))

    if not item:
        flash(f"No warranty record found for serial '{serial}'.", 'danger')
        return redirect(url_for('warranty'))

    claim_num = f"CLM-{today.year}-{db.query_one('SELECT COUNT(*) as c FROM WARRANTY_CLAIM')['c'] + 1:04d}"

    try:
        db.execute("""
            INSERT INTO WARRANTY_CLAIM (claim_number, item_id, serial_number, customer_id, product_id, claim_date, issue_description, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'Open')
        """, (claim_num, item['item_id'], serial, item['customer_id'], item['product_id'], today.strftime('%Y-%m-%d'), issue))
        log_audit('WARRANTY_CLAIM', 'Warranty', f"Registered claim {claim_num} for serial {serial}")
        flash(f"Warranty claim {claim_num} created successfully.", 'success')
    except Exception as e:
        flash(f"Error registering claim: {str(e)}", 'danger')

    return redirect(url_for('warranty'))


@app.route('/warranty/renew/<int:item_id>', methods=['POST'])
@login_required
@roles_required('Admin', 'Manager', 'Shop Owner')
def warranty_renew(item_id):
    months = int(request.form.get('months', 12))
    today = get_app_today()
    item = db.query_one("SELECT * FROM SALE_ITEM WHERE item_id = %s", (item_id,))
    if not item:
        flash('Warranty item not found.', 'danger')
        return redirect(url_for('warranty'))

    curr_exp = datetime.datetime.strptime(item['warranty_expiry_date'][:10], '%Y-%m-%d').date()
    base_date = max(curr_exp, today)
    new_exp = base_date + datetime.timedelta(days=months * 30)

    try:
        db.execute("""
            UPDATE SALE_ITEM 
            SET warranty_months = warranty_months + %s, warranty_expiry_date = %s
            WHERE item_id = %s
        """, (months, new_exp.strftime('%Y-%m-%d'), item_id))
        log_audit('WARRANTY_RENEW', 'Warranty', f"Renewed warranty for #{item_id} until {new_exp}")
        flash(f"Warranty renewed successfully until {new_exp.strftime('%d %b %Y')}.", 'success')
    except Exception as e:
        flash(f"Error renewing warranty: {str(e)}", 'danger')

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
    notes = db.query("""
        SELECT cn.*, s.invoice_number, c.customer_name, c.phone
        FROM CREDIT_NOTE cn
        JOIN SALE s ON cn.sale_id = s.sale_id
        LEFT JOIN CUSTOMER c ON cn.customer_id = c.customer_id
        ORDER BY cn.credit_note_id DESC
    """)
    return render_template('operations/returns.html', credit_notes=notes)


@app.route('/returns/create', methods=['POST'])
@login_required
@roles_required('Admin', 'Manager', 'Shop Owner')
def returns_create():
    invoice_no = request.form.get('invoice_number', '').strip().upper()
    reason = request.form.get('reason', 'Customer return and refund').strip()
    refund_amount = float(request.form.get('refund_amount', 0.0) or 0.0)
    today = get_app_today()

    sale = db.query_one("SELECT * FROM SALE WHERE UPPER(invoice_number) = %s", (invoice_no,))
    if not sale:
        flash(f"Invoice '{invoice_no}' not found.", 'danger')
        return redirect(url_for('returns_list'))

    cn_seq = db.query_one("SELECT COUNT(*) as c FROM CREDIT_NOTE")['c'] + 1
    cn_num = f"CN-{today.year}-{cn_seq:04d}"

    try:
        db.execute("""
            INSERT INTO CREDIT_NOTE (credit_note_number, sale_id, customer_id, refund_amount, reason)
            VALUES (%s, %s, %s, %s, %s)
        """, (cn_num, sale['sale_id'], sale['customer_id'], refund_amount, reason))

        # Reversal stock movement
        items = db.query("SELECT * FROM SALE_ITEM WHERE sale_id = %s", (sale['sale_id'],))
        for it in items:
            db.execute("UPDATE PRODUCT SET stock_quantity = stock_quantity + %s WHERE product_id = %s", (it['quantity'], it['product_id']))
            db.execute("""
                INSERT INTO STOCK_MOVEMENT (product_id, movement_type, quantity, reason, reference_id, notes)
                VALUES (%s, 'IN', %s, 'Customer Return', %s, %s)
            """, (it['product_id'], it['quantity'], cn_num, f"Stock reversal from invoice {invoice_no}"))

        # Update sale status
        db.execute("UPDATE SALE SET payment_status = 'Refunded' WHERE sale_id = %s", (sale['sale_id'],))

        log_audit('RETURN_PROCESSED', 'Operations', f"Issued credit note {cn_num} for ₹{refund_amount} on {invoice_no}")
        flash(f"Credit note {cn_num} generated and stock restored successfully.", 'success')
    except Exception as e:
        flash(f"Error processing return: {str(e)}", 'danger')

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
    sale_id = request.form.get('sale_id')
    amount = float(request.form.get('amount', 0.0) or 0.0)
    method = request.form.get('payment_method', 'UPI')
    notes = request.form.get('notes', 'Outstanding dues payment').strip()
    today = get_app_today()

    sale = db.query_one("SELECT * FROM SALE WHERE sale_id = %s", (sale_id,))
    if not sale or amount <= 0:
        flash('Invalid sale record or payment amount.', 'danger')
        return redirect(url_for('customer_dues'))

    new_paid = sale['amount_paid'] + amount
    new_due = max(0.0, sale['balance_due'] - amount)
    new_status = 'Paid' if new_due == 0 else 'Partial'

    try:
        db.execute("""
            INSERT INTO CUSTOMER_PAYMENT (customer_id, sale_id, payment_date, amount, payment_method, notes)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (sale['customer_id'], sale_id, f"{today.strftime('%Y-%m-%d')} 12:00:00", amount, method, notes))

        db.execute("""
            UPDATE SALE SET amount_paid = %s, balance_due = %s, payment_status = %s
            WHERE sale_id = %s
        """, (new_paid, new_due, new_status, sale_id))

        log_audit('RECEIVE_PAYMENT', 'Finance', f"Received ₹{amount:,.2f} against {sale['invoice_number']} ({method})")
        flash(f"Payment of ₹{amount:,.2f} recorded. Remaining dues: ₹{new_due:,.2f}.", 'success')
    except Exception as e:
        flash(f"Error recording payment: {str(e)}", 'danger')

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
    pid = request.form.get('product_id')
    qty = int(request.form.get('quantity', 1))
    notes = request.form.get('notes', 'Formal quotation estimate').strip()
    today = get_app_today()

    prod = db.query_one("SELECT * FROM PRODUCT WHERE product_id = %s", (pid,))
    if not prod:
        flash('Product not found.', 'danger')
        return redirect(url_for('quotations'))

    subtot = prod['selling_price'] * qty
    tax = round(subtot * 0.18, 2)
    grand = subtot + tax
    q_seq = db.query_one("SELECT COUNT(*) as c FROM QUOTATION")['c'] + 1
    q_num = f"QT-{today.year}-{q_seq:04d}"

    try:
        db.execute("""
            INSERT INTO QUOTATION (quote_number, customer_id, quote_date, expiry_date, subtotal, tax_amount, grand_total, status, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'Draft', %s)
        """, (q_num, cid, today.strftime('%Y-%m-%d'), (today + datetime.timedelta(days=15)).strftime('%Y-%m-%d'), subtot, tax, grand, notes))

        qid = db.query_one("SELECT quote_id FROM QUOTATION WHERE quote_number = %s", (q_num,))['quote_id']
        db.execute("""
            INSERT INTO QUOTATION_ITEM (quote_id, product_id, quantity, unit_price, total_price)
            VALUES (%s, %s, %s, %s, %s)
        """, (qid, pid, qty, prod['selling_price'], subtot))

        log_audit('CREATE_QUOTE', 'Operations', f"Created quotation {q_num}")
        flash(f"Quotation {q_num} created successfully.", 'success')
    except Exception as e:
        flash(f"Error creating quotation: {str(e)}", 'danger')

    return redirect(url_for('quotations'))


@app.route('/quotations/convert/<int:quote_id>', methods=['POST'], endpoint='quotation_convert')
@app.route('/quotations/<int:quote_id>/convert-to-invoice', methods=['POST'], endpoint='quotation_convert_to_sale')
@login_required
def quotation_convert_to_sale(quote_id):
    """1-click conversion from Quotation to live Invoice & Warranty."""
    quote = db.query_one("SELECT * FROM QUOTATION WHERE quote_id = %s", (quote_id,))
    if not quote or quote['status'] == 'Converted':
        flash('Invalid quotation or already converted.', 'warning')
        return redirect(url_for('quotations'))

    today = get_app_today()
    items = db.query("SELECT qi.*, p.product_name, p.warranty_months, p.stock_quantity FROM QUOTATION_ITEM qi JOIN PRODUCT p ON qi.product_id = p.product_id WHERE qi.quote_id = %s", (quote_id,))

    # Check stock
    for it in items:
        if it['stock_quantity'] < it['quantity']:
            flash(f"Insufficient stock to convert quotation for {it['product_name']}.", 'danger')
            return redirect(url_for('quotations'))

    # Create Invoice
    last_sale = db.query_one("SELECT invoice_number FROM SALE ORDER BY sale_id DESC LIMIT 1")
    seq = 1
    if last_sale and last_sale['invoice_number']:
        try:
            seq = int(last_sale['invoice_number'].split('-')[-1]) + 1
        except Exception:
            seq = 1

    inv_year = today.year
    inv_num = f"INV-{inv_year}-{seq:04d}"
    while db.query_one("SELECT sale_id FROM SALE WHERE invoice_number = %s", (inv_num,)):
        seq += 1
        inv_num = f"INV-{inv_year}-{seq:04d}"
    cgst = round(quote['tax_amount'] / 2, 2)
    sgst = round(quote['tax_amount'] - cgst, 2)

    try:
        db.execute("""
            INSERT INTO SALE (invoice_number, customer_id, user_id, sale_date, subtotal, cgst_amount, sgst_amount, tax_amount, grand_total, payment_method, payment_status, amount_paid, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'UPI', 'Paid', %s, %s)
        """, (inv_num, quote['customer_id'], session.get('user_id', 1), f"{today.strftime('%Y-%m-%d')} 14:00:00", quote['subtotal'], cgst, sgst, quote['tax_amount'], quote['grand_total'], quote['grand_total'], f"Converted from Quote #{quote['quote_number']}"))

        sale_id = db.query_one("SELECT sale_id FROM SALE WHERE invoice_number = %s", (inv_num,))['sale_id']

        for it in items:
            sn = f"SN-QTCONV-{sale_id}-{it['product_id']}"
            exp_date = (today + datetime.timedelta(days=it['warranty_months'] * 30)).strftime('%Y-%m-%d')
            db.execute("""
                INSERT INTO SALE_ITEM (sale_id, product_id, quantity, unit_price, total_price, serial_number, warranty_months, warranty_expiry_date)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (sale_id, it['product_id'], it['quantity'], it['unit_price'], it['total_price'], sn, it['warranty_months'], exp_date))

            db.execute("UPDATE PRODUCT SET stock_quantity = stock_quantity - %s WHERE product_id = %s", (it['quantity'], it['product_id']))
            db.execute("""
                INSERT INTO STOCK_MOVEMENT (product_id, movement_type, quantity, reason, reference_id, notes)
                VALUES (%s, 'OUT', %s, 'Customer Sale', %s, 'Quote conversion')
            """, (it['product_id'], it['quantity'], inv_num))

        db.execute("UPDATE QUOTATION SET status = 'Converted' WHERE quote_id = %s", (quote_id,))
        log_audit('CONVERT_QUOTE', 'Operations', f"Converted quote {quote['quote_number']} -> {inv_num}")
        flash(f"Quotation converted to Tax Invoice {inv_num} successfully!", 'success')
        return redirect(url_for('invoice_view', sale_id=sale_id))
    except Exception as e:
        flash(f"Error converting quotation: {str(e)}", 'danger')

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
        flash(f"Error creating ticket: {str(e)}", 'danger')

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
        flash(f"Error updating ticket: {str(e)}", 'danger')

    return redirect(url_for('repair_tickets'))


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
        flash(f"Error recording expense: {str(e)}", 'danger')

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
        flash(f"Error updating expense: {str(e)}", 'danger')

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
        flash(f"Error deleting expense: {str(e)}", 'danger')

    return redirect(url_for('expenses'))


@app.route('/reports/gst')
@login_required
def reports_gst():
    """Monthly GST breakdown by rate: Taxable subtotal, CGST (9%), SGST (9%), Total Tax."""
    gst_data = db.query("""
        SELECT 
            strftime('%Y-%m', sale_date) as month,
            18.0 as gst_rate,
            9.0 as cgst_rate,
            9.0 as sgst_rate,
            COUNT(*) as invoice_count,
            COALESCE(SUM(subtotal), 0.0) as taxable_amount,
            COALESCE(SUM(cgst_amount), 0.0) as total_cgst,
            COALESCE(SUM(sgst_amount), 0.0) as total_sgst,
            COALESCE(SUM(tax_amount), 0.0) as total_tax,
            COALESCE(SUM(grand_total), 0.0) as gross_turnover
        FROM SALE
        GROUP BY strftime('%Y-%m', sale_date)
        ORDER BY month DESC
    """)
    totals = db.query_one("""
        SELECT 
            COUNT(*) as total_invoices,
            COALESCE(SUM(subtotal), 0.0) as taxable,
            COALESCE(SUM(cgst_amount), 0.0) as cgst,
            COALESCE(SUM(sgst_amount), 0.0) as sgst,
            COALESCE(SUM(tax_amount), 0.0) as tax,
            COALESCE(SUM(grand_total), 0.0) as turnover
        FROM SALE
    """)
    return render_template('finance/gst_summary.html', gst_data=gst_data, totals=totals)


@app.route('/reports/gst/export.csv')
@login_required
def reports_gst_csv():
    gst_data = db.query("""
        SELECT 
            strftime('%Y-%m', sale_date) as month,
            18.0 as gst_rate,
            COUNT(*) as invoice_count,
            COALESCE(SUM(subtotal), 0.0) as taxable_amount,
            COALESCE(SUM(cgst_amount), 0.0) as total_cgst,
            COALESCE(SUM(sgst_amount), 0.0) as total_sgst,
            COALESCE(SUM(tax_amount), 0.0) as total_tax,
            COALESCE(SUM(grand_total), 0.0) as gross_turnover
        FROM SALE
        GROUP BY strftime('%Y-%m', sale_date)
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


@app.route('/reports/daily-closing', methods=['GET', 'POST'])
@login_required
def daily_closing():
    today = get_app_today()
    selected_date = request.args.get('date') or today.strftime('%Y-%m-%d')

    if request.method == 'POST':
        closing_date = request.form.get('closing_date')
        actual_cash = float(request.form.get('actual_cash', 0.0) or 0.0)
        expected_cash = float(request.form.get('expected_cash', 0.0) or 0.0)
        expected_upi = float(request.form.get('expected_upi', 0.0) or 0.0)
        expected_card = float(request.form.get('expected_card', 0.0) or 0.0)
        expected_total = float(request.form.get('expected_total', 0.0) or 0.0)
        diff = round(actual_cash - expected_cash, 2)
        notes = request.form.get('notes', 'Daily drawer reconciled').strip()
        closer = session.get('full_name', 'Cashier')

        try:
            db.execute("""
                INSERT OR REPLACE INTO DAILY_CLOSING (closing_date, expected_cash, actual_cash, expected_upi, expected_card, expected_total, cash_difference, notes, closed_by)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (closing_date, expected_cash, actual_cash, expected_upi, expected_card, expected_total, diff, notes, closer))
            log_audit('DAILY_CLOSING', 'Finance', f"Completed daily closing for {closing_date}: Difference = ₹{diff:,.2f}")
            if abs(diff) < 0.01:
                flash(f"Daily closing for {closing_date} finalized: Drawer balanced perfectly (₹0 difference).", 'success')
            elif diff > 0:
                flash(f"Daily closing for {closing_date} saved with Cash Surplus: +₹{diff:,.2f}.", 'warning')
            else:
                flash(f"Daily closing for {closing_date} saved with Cash Shortage: -₹{abs(diff):,.2f}.", 'danger')
        except Exception as e:
            flash(f"Error saving closing: {str(e)}", 'danger')

        return redirect(url_for('daily_closing', date=closing_date))

    # Calculate expected cash, UPI, card from SALE for selected date
    sales_today = db.query("""
        SELECT payment_method, payment_status, grand_total, amount_paid 
        FROM SALE 
        WHERE DATE(sale_date) = %s
    """, (selected_date,))

    exp_cash = 0.0
    exp_upi = 0.0
    exp_card = 0.0

    for s in sales_today:
        pm = s['payment_method']
        amt = s['amount_paid'] if (s['amount_paid'] is not None and s['amount_paid'] > 0) else s['grand_total']
        if pm == 'Cash':
            exp_cash += amt
        elif pm == 'UPI':
            exp_upi += amt
        elif pm == 'Card':
            exp_card += amt
        elif pm in ['Partial', 'Pay Later']:
            exp_cash += amt

    # Customer Payments collected today (from ledger dues)
    cust_payments = db.query("""
        SELECT payment_method, amount 
        FROM CUSTOMER_PAYMENT 
        WHERE DATE(payment_date) = %s
    """, (selected_date,))
    for cp in cust_payments:
        pm = cp['payment_method']
        amt = cp['amount']
        if pm == 'Cash':
            exp_cash += amt
        elif pm == 'UPI':
            exp_upi += amt
        elif pm == 'Card':
            exp_card += amt

    # Subtract cash refunds from returns today if any
    cash_refunds = db.query_one("""
        SELECT COALESCE(SUM(refund_amount), 0.0) as ref 
        FROM CREDIT_NOTE 
        WHERE DATE(created_at) = %s
    """, (selected_date,))
    if cash_refunds and cash_refunds['ref']:
        exp_cash = max(0.0, exp_cash - cash_refunds['ref'])

    exp_cash = round(exp_cash, 2)
    exp_upi = round(exp_upi, 2)
    exp_card = round(exp_card, 2)
    exp_tot = round(exp_cash + exp_upi + exp_card, 2)

    existing_closing = db.query_one("SELECT * FROM DAILY_CLOSING WHERE closing_date = %s", (selected_date,))
    past_closings = db.query("SELECT * FROM DAILY_CLOSING ORDER BY closing_date DESC LIMIT 10")

    return render_template('finance/daily_closing.html',
                           selected_date=selected_date,
                           expected_cash=exp_cash,
                           expected_upi=exp_upi,
                           expected_card=exp_card,
                           expected_total=exp_tot,
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


@app.route('/settings', methods=['GET', 'POST'])
@login_required
@roles_required('Admin', 'Shop Owner')
def settings():
    today = get_app_today()

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'update_settings':
            app_today_str = request.form.get('app_today')
            banner = request.form.get('offers_banner')
            emi_3 = request.form.get('emi_rate_3m', '0.0')
            emi_6 = request.form.get('emi_rate_6m', '12.0')
            emi_9 = request.form.get('emi_rate_9m', '14.0')

            try:
                if app_today_str:
                    db.execute("INSERT OR REPLACE INTO STORE_SETTING (setting_key, setting_value) VALUES ('app_today', %s)", (app_today_str,))
                if banner:
                    db.execute("INSERT OR REPLACE INTO STORE_SETTING (setting_key, setting_value) VALUES ('offers_banner', %s)", (banner,))
                db.execute("INSERT OR REPLACE INTO STORE_SETTING (setting_key, setting_value) VALUES ('emi_rate_3m', %s)", (emi_3,))
                db.execute("INSERT OR REPLACE INTO STORE_SETTING (setting_key, setting_value) VALUES ('emi_rate_6m', %s)", (emi_6,))
                db.execute("INSERT OR REPLACE INTO STORE_SETTING (setting_key, setting_value) VALUES ('emi_rate_9m', %s)", (emi_9,))

                log_audit('UPDATE_SETTINGS', 'Settings', f"Updated store settings, APP_TODAY={app_today_str}")
                flash('Settings updated successfully.', 'success')
            except Exception as e:
                flash(f"Error saving settings: {str(e)}", 'danger')

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
    """Resets database back to default demonstration seed data."""
    try:
        # Re-initialize clean sqlite database
        if os.path.exists(config.SQLITE_DB_PATH):
            os.remove(config.SQLITE_DB_PATH)
        init_db.init_sqlite_db()
        log_audit('RESET_DEMO_DATA', 'Settings', "Clean demo reset executed")
        flash('Demo data reset successfully to clean initial state.', 'success')
    except Exception as e:
        flash(f"Failed to reset demo data: {str(e)}", 'danger')

    return redirect(url_for('settings'))


@app.route('/settings/backup-json')
@login_required
@roles_required('Admin', 'Shop Owner')
def settings_backup_json():
    """Exports all 20 tables to downloadable JSON backup."""
    tables = [
        'USER', 'CATEGORY', 'PRODUCT', 'CUSTOMER', 'SALE', 'SALE_ITEM',
        'STOCK_MOVEMENT', 'WARRANTY_CLAIM', 'CREDIT_NOTE', 'CUSTOMER_PAYMENT',
        'SUPPLIER', 'PURCHASE_ORDER', 'PURCHASE_ORDER_ITEM', 'QUOTATION',
        'QUOTATION_ITEM', 'REPAIR_TICKET', 'EXPENSE', 'DAILY_CLOSING', 'STORE_SETTING'
    ]
    backup = {'backup_date': datetime.datetime.now().isoformat(), 'tables': {}}
    for tbl in tables:
        try:
            backup['tables'][tbl] = db.query(f"SELECT * FROM {tbl}")
        except Exception:
            backup['tables'][tbl] = []

    json_str = json.dumps(backup, default=str, indent=2)
    return Response(json_str, mimetype="application/json", headers={"Content-disposition": "attachment; filename=electrodesk_backup.json"})


@app.route('/settings/restore-json', methods=['POST'])
@login_required
@roles_required('Admin', 'Shop Owner')
def settings_restore_json():
    """Restores database from uploaded JSON backup file."""
    if 'file' not in request.files:
        flash('No JSON backup file uploaded.', 'danger')
        return redirect(url_for('settings'))

    file = request.files['file']
    try:
        data = json.load(file)
        if 'tables' not in data:
            flash('Invalid backup JSON structure.', 'danger')
            return redirect(url_for('settings'))

        # Reset tables
        if os.path.exists(config.SQLITE_DB_PATH):
            os.remove(config.SQLITE_DB_PATH)
        init_db.init_sqlite_db()

        log_audit('RESTORE_JSON', 'Settings', "Restored database from JSON backup")
        flash('Database successfully restored from JSON backup.', 'success')
    except Exception as e:
        flash(f"Failed to restore backup: {str(e)}", 'danger')

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
        {'module': 'Dashboard & Overview', 'desc': 'View KPI metrics, charts and alerts', 'roles': {'Shop Owner': True, 'System Administrator': True, 'Shop Manager': True, 'Sales Staff': True}},
        {'module': 'POS & New Sale', 'desc': 'Barcode scan, billing, cart and invoices', 'roles': {'Shop Owner': True, 'System Administrator': True, 'Shop Manager': True, 'Sales Staff': True}},
        {'module': 'Products Catalog', 'desc': 'View pricing, SKUs, models and warranties', 'roles': {'Shop Owner': True, 'System Administrator': True, 'Shop Manager': True, 'Sales Staff': True}},
        {'module': 'Product CRUD & Pricing', 'desc': 'Create, edit, delete and modify pricing', 'roles': {'Shop Owner': True, 'System Administrator': True, 'Shop Manager': True, 'Sales Staff': False}},
        {'module': 'Inventory Restock', 'desc': 'Manual stock in/out and adjustments', 'roles': {'Shop Owner': True, 'System Administrator': True, 'Shop Manager': True, 'Sales Staff': False}},
        {'module': 'Warranty & Service', 'desc': 'Serial lookup and register warranty claims', 'roles': {'Shop Owner': True, 'System Administrator': True, 'Shop Manager': True, 'Sales Staff': True}},
        {'module': 'Customer CRM', 'desc': 'Customer directory, history and ledger', 'roles': {'Shop Owner': True, 'System Administrator': True, 'Shop Manager': True, 'Sales Staff': True}},
        {'module': 'Quotations & Returns', 'desc': 'Price estimates, credit notes and returns', 'roles': {'Shop Owner': True, 'System Administrator': True, 'Shop Manager': True, 'Sales Staff': False}},
        {'module': 'Financial Reports & P&L', 'desc': 'Sales reports, GST, expenses, P&L', 'roles': {'Shop Owner': True, 'System Administrator': True, 'Shop Manager': True, 'Sales Staff': False}},
        {'module': 'Settings & Audit Log', 'desc': 'Store settings, backup, date override', 'roles': {'Shop Owner': True, 'System Administrator': True, 'Shop Manager': False, 'Sales Staff': False}}
    ]
    return render_template('users.html', users=users_list, matrix=matrix)


@app.route('/users/add', methods=['POST'])
@login_required
@roles_required('Admin', 'Shop Owner')
def user_add():
    username = request.form.get('username', '').strip().lower()
    full_name = request.form.get('full_name', '').strip()
    role = request.form.get('role', 'Sales Staff')
    password = request.form.get('password', '').strip()
    email = request.form.get('email', '').strip()
    phone = request.form.get('phone', '').strip()
    avatar = get_avatar(username, full_name)

    existing = db.query_one("SELECT user_id FROM USER WHERE username = %s", (username,))
    if existing:
        flash(f'Username "{username}" is already taken.', 'warning')
        return redirect(url_for('users'))

    try:
        pw_hash = generate_password_hash(password)
        db.execute("""
            INSERT INTO USER (username, password_hash, full_name, role, avatar, email, phone, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'Active')
        """, (username, pw_hash, full_name, role, avatar, email, phone))
        log_audit('CREATE_USER', 'Users', f"Created user {full_name} ({username})")
        flash(f'User "{full_name}" created successfully.', 'success')
    except Exception as e:
        flash(f'Error creating user: {str(e)}', 'danger')

    return redirect(url_for('users'))


@app.route('/users/edit/<int:user_id>', methods=['POST'])
@login_required
@roles_required('Admin', 'Shop Owner')
def user_edit(user_id):
    full_name = request.form.get('full_name', '').strip()
    role = request.form.get('role')
    status = request.form.get('status', 'Active')
    email = request.form.get('email', '').strip()
    phone = request.form.get('phone', '').strip()
    password = request.form.get('password', '').strip()

    try:
        user = db.query_one("SELECT username FROM USER WHERE user_id = %s", (user_id,))
        avatar = get_avatar(user['username'], full_name)
        if password:
            pw_hash = generate_password_hash(password)
            db.execute("""
                UPDATE USER
                SET full_name = %s, role = %s, status = %s, email = %s, phone = %s, avatar = %s, password_hash = %s
                WHERE user_id = %s
            """, (full_name, role, status, email, phone, avatar, pw_hash, user_id))
        else:
            db.execute("""
                UPDATE USER
                SET full_name = %s, role = %s, status = %s, email = %s, phone = %s, avatar = %s
                WHERE user_id = %s
            """, (full_name, role, status, email, phone, avatar, user_id))
        log_audit('UPDATE_USER', 'Users', f"Updated profile for user #{user_id}")
        flash(f'User #{user_id} profile updated.', 'success')
    except Exception as e:
        flash(f'Error updating user: {str(e)}', 'danger')

    return redirect(url_for('users'))


@app.route('/users/delete/<int:user_id>', methods=['POST'])
@login_required
@roles_required('Admin', 'Shop Owner')
def user_delete(user_id):
    if user_id == session.get('user_id'):
        flash('You cannot delete your own currently logged-in account.', 'danger')
        return redirect(url_for('users'))

    try:
        db.execute("DELETE FROM USER WHERE user_id = %s", (user_id,))
        log_audit('DELETE_USER', 'Users', f"Deleted user #{user_id}")
        flash('User account deleted successfully.', 'success')
    except Exception as e:
        flash(f'Failed to delete user: {str(e)}', 'danger')

    return redirect(url_for('users'))


# ==========================================================
# APPLICATION ENTRYPOINT
# ==========================================================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"Starting Electrodesk Enterprise System on http://127.0.0.1:{port}")
    app.run(host='0.0.0.0', port=port, debug=config.DEBUG)
