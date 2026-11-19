"""
Electrodesk - Electronics Shop Management System
Main Flask Application
Features:
- Role-based Access Control (System Administrator, Shop Manager, Sales Staff, Shop Owner)
- Dashboard with KPIs, Low-Stock Alerts & 14-Day Sales Chart
- Product & Category Management (CRUD, 2-column cards, SKU, Reorder Level, Warranty)
- Customer Management with Purchase History & Warranty Records
- Real-time Inventory Tracking & Quick Restock Adjustments
- Point of Sale (POS) with Fast Search, Cart, GST (CGST 9% + SGST 9%) & Discount Calculation
- Automatic Billing, Sequential Invoice Generation & Stock Deduction
- Professional Printable Invoices in INR
- Serial-number based Warranty Tracking with Expiry Calculations
- Sales & Inventory Reports with 14-day Navy Bar Chart
- User Management & Permission Matrix
"""
import os
import datetime
from functools import wraps
from flask import (
    Flask, render_template, request, redirect, url_for, flash, session, jsonify
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
    Formats a date string or object like: '18 Nov 2026'
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


# Register Jinja Filters
app.jinja_env.filters['inr'] = format_inr
app.jinja_env.filters['date_in'] = format_date_in


# ==========================================================
# AVATAR & ROLE MAPPINGS
# ==========================================================

AVATAR_MAP = {
    'admin': 'RA',
    'ram': 'RA',
    'geetha': 'GE',
    'manager': 'GE',
    'sai': 'SA',
    'staff': 'SA',
    'suresh': 'S',
    'owner': 'S'
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
    elif len(parts) == 1:
        return parts[0][0].upper()
    return 'U'


# ==========================================================
# AUTHENTICATION & ROLE-BASED ACCESS CONTROL HELPERS
# ==========================================================

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
    Flexible role checker that maps role variants (e.g. 'Admin' or 'System Administrator').
    """
    role_aliases = {
        'Admin': ['Admin', 'System Administrator', 'Shop Owner'],
        'System Administrator': ['Admin', 'System Administrator'],
        'Shop Owner': ['Shop Owner', 'Admin', 'System Administrator'],
        'Manager': ['Manager', 'Shop Manager', 'System Administrator', 'Admin', 'Shop Owner'],
        'Shop Manager': ['Manager', 'Shop Manager', 'System Administrator', 'Admin', 'Shop Owner'],
        'Sales Staff': ['Sales Staff', 'Shop Manager', 'Manager', 'System Administrator', 'Admin', 'Shop Owner']
    }

    expanded_allowed = set()
    for r in allowed_roles:
        expanded_allowed.add(r)
        if r in role_aliases:
            expanded_allowed.update(role_aliases[r])

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('Please log in to access this page.', 'warning')
                return redirect(url_for('login'))
            user_role = session.get('role')
            if user_role not in expanded_allowed:
                flash(f'Access denied. Your role ({user_role}) does not have permission for this action.', 'danger')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator


@app.context_processor
def inject_global_context():
    """Injects store information, current user, avatar, and alert counts into all templates."""
    low_stock_count = 0
    if 'user_id' in session:
        try:
            res = db.query_one("SELECT COUNT(*) as cnt FROM PRODUCT WHERE stock_quantity <= reorder_level")
            if res:
                low_stock_count = res.get('cnt', 0)
        except Exception:
            low_stock_count = 0

    now = datetime.datetime.now()
    today_formatted = now.strftime('%d %b %Y').lstrip('0')
    today_weekday = now.strftime('%A')

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
        'low_stock_count': low_stock_count,
        'db_info': db.get_db_info(),
        'now': now,
        'today_formatted': today_formatted,
        'today_weekday': today_weekday
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

        if not username or not password:
            flash('Please enter both username and password.', 'danger')
            return render_template('login.html')

        # Check aliases: manager -> geetha, staff -> sai, owner -> suresh
        alias_map = {
            'manager': 'geetha',
            'staff': 'sai',
            'owner': 'suresh',
            'ram': 'admin'
        }
        lookup_username = alias_map.get(username, username)

        user = db.query_one("SELECT * FROM USER WHERE LOWER(username) = %s AND status = 'Active'", (lookup_username,))

        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['user_id']
            session['username'] = user['username']
            session['full_name'] = user['full_name']
            session['role'] = user['role']
            session['avatar'] = user.get('avatar') or get_avatar(user['username'], user['full_name'])
            session['email'] = user.get('email', '')

            flash(f"Welcome back, {user['full_name']}! Signed in as {user['role']}.", 'success')
            next_url = request.args.get('next')
            return redirect(next_url or url_for('dashboard'))
        else:
            flash('Invalid username or password. Please verify credentials.', 'danger')

    return render_template('login.html')


@app.route('/logout')
def logout():
    name = session.get('full_name', 'User')
    session.clear()
    flash(f'Goodbye {name}, you have been safely logged out.', 'info')
    return redirect(url_for('login'))


# ==========================================================
# DASHBOARD ROUTE
# ==========================================================

@app.route('/')
@app.route('/dashboard')
@login_required
def dashboard():
    today_str = datetime.date.today().strftime('%Y-%m-%d')

    # 1. Metric: Today's Sales
    today_sales_data = db.query_one("""
        SELECT COUNT(*) as count, IFNULL(SUM(grand_total), 0) as total
        FROM SALE
        WHERE DATE(sale_date) = %s
    """, (today_str,))
    today_sales_count = today_sales_data['count'] if today_sales_data else 0
    today_sales_total = float(today_sales_data['total']) if today_sales_data else 0.0

    # 2. Metric: Total Revenue (All time)
    total_revenue_data = db.query_one("SELECT IFNULL(SUM(grand_total), 0) as total, COUNT(*) as count FROM SALE")
    total_revenue = float(total_revenue_data['total']) if total_revenue_data else 0.0
    total_sales_count = total_revenue_data['count'] if total_revenue_data else 0

    # 3. Metric: Inventory Volume
    prod_data = db.query_one("SELECT COUNT(*) as total_prods, IFNULL(SUM(stock_quantity), 0) as total_units FROM PRODUCT")
    total_products = prod_data['total_prods'] if prod_data else 0
    total_units = prod_data['total_units'] if prod_data else 0

    # 4. Metric: Low Stock Products
    low_stock_products = db.query("""
        SELECT p.*, c.category_name
        FROM PRODUCT p
        JOIN CATEGORY c ON p.category_id = c.category_id
        WHERE p.stock_quantity <= p.reorder_level
        ORDER BY p.stock_quantity ASC
    """)
    low_stock_count = len(low_stock_products)

    # 5. Metric: Total Customers
    cust_data = db.query_one("SELECT COUNT(*) as count FROM CUSTOMER")
    total_customers = cust_data['count'] if cust_data else 0

    # 6. Recent Sales (Last 6)
    recent_sales = db.query("""
        SELECT s.*, c.customer_name, c.phone as customer_phone, u.full_name as staff_name, u.avatar as staff_avatar,
               (SELECT COUNT(*) FROM SALE_ITEM si WHERE si.sale_id = s.sale_id) as item_count
        FROM SALE s
        LEFT JOIN CUSTOMER c ON s.customer_id = c.customer_id
        JOIN USER u ON s.user_id = u.user_id
        ORDER BY s.sale_date DESC
        LIMIT 6
    """)

    # 7. Category Revenue Breakdown
    category_sales = db.query("""
        SELECT c.category_name, IFNULL(SUM(si.total_price), 0) as revenue, IFNULL(SUM(si.quantity), 0) as units_sold
        FROM CATEGORY c
        LEFT JOIN PRODUCT p ON c.category_id = p.category_id
        LEFT JOIN SALE_ITEM si ON p.product_id = si.product_id
        GROUP BY c.category_id, c.category_name
        ORDER BY revenue DESC
    """)

    # 8. Top 5 Best-Selling Products
    top_products = db.query("""
        SELECT p.product_name, p.brand, p.model, c.category_name,
               IFNULL(SUM(si.quantity), 0) as total_sold,
               IFNULL(SUM(si.total_price), 0) as total_revenue
        FROM PRODUCT p
        JOIN CATEGORY c ON p.category_id = c.category_id
        JOIN SALE_ITEM si ON p.product_id = si.product_id
        GROUP BY p.product_id, p.product_name, p.brand, p.model, c.category_name
        ORDER BY total_sold DESC
        LIMIT 5
    """)

    return render_template(
        'dashboard.html',
        today_sales_count=today_sales_count,
        today_sales_total=today_sales_total,
        total_revenue=total_revenue,
        total_sales_count=total_sales_count,
        total_products=total_products,
        total_units=total_units,
        low_stock_products=low_stock_products,
        low_stock_count=low_stock_count,
        total_customers=total_customers,
        recent_sales=recent_sales,
        category_sales=category_sales,
        top_products=top_products
    )


# ==========================================================
# CATEGORY MANAGEMENT ROUTES (2-COLUMN CARDS)
# ==========================================================

@app.route('/categories')
@login_required
def categories():
    categories_list = db.query("""
        SELECT c.*,
               COUNT(p.product_id) as product_count,
               IFNULL(SUM(p.stock_quantity), 0) as units_count,
               IFNULL(SUM(p.stock_quantity * p.selling_price), 0) as stock_value
        FROM CATEGORY c
        LEFT JOIN PRODUCT p ON c.category_id = p.category_id
        GROUP BY c.category_id, c.category_code, c.category_name, c.description, c.icon, c.created_at
        ORDER BY c.category_code ASC
    """)
    return render_template('categories.html', categories=categories_list)


@app.route('/categories/add', methods=['POST'])
@login_required
@roles_required('Admin', 'Manager', 'Shop Owner')
def category_add():
    name = request.form.get('category_name', '').strip()
    code = request.form.get('category_code', '').strip().upper()
    description = request.form.get('description', '').strip()
    icon = request.form.get('icon', 'bi-box-seam').strip()

    if not name:
        flash('Category name is required.', 'danger')
        return redirect(url_for('categories'))

    if not code:
        # Auto generate code
        last_cat = db.query_one("SELECT category_id FROM CATEGORY ORDER BY category_id DESC LIMIT 1")
        next_num = (last_cat['category_id'] + 1) if last_cat else 1
        code = f"CAT-{next_num:02d}"

    existing = db.query_one("SELECT category_id FROM CATEGORY WHERE LOWER(category_name) = LOWER(%s) OR category_code = %s", (name, code))
    if existing:
        flash(f'Category "{name}" or code "{code}" already exists.', 'warning')
        return redirect(url_for('categories'))

    try:
        db.execute(
            "INSERT INTO CATEGORY (category_code, category_name, description, icon) VALUES (%s, %s, %s, %s)",
            (code, name, description, icon)
        )
        flash(f'Category "{name}" ({code}) created successfully!', 'success')
    except Exception as e:
        flash(f'Failed to create category: {str(e)}', 'danger')

    return redirect(url_for('categories'))


@app.route('/categories/edit/<int:category_id>', methods=['POST'])
@login_required
@roles_required('Admin', 'Manager', 'Shop Owner')
def category_edit(category_id):
    name = request.form.get('category_name', '').strip()
    code = request.form.get('category_code', '').strip().upper()
    description = request.form.get('description', '').strip()
    icon = request.form.get('icon', 'bi-box-seam').strip()

    if not name or not code:
        flash('Category name and code are required.', 'danger')
        return redirect(url_for('categories'))

    try:
        db.execute(
            "UPDATE CATEGORY SET category_code = %s, category_name = %s, description = %s, icon = %s WHERE category_id = %s",
            (code, name, description, icon, category_id)
        )
        flash(f'Category "{name}" updated successfully!', 'success')
    except Exception as e:
        flash(f'Failed to update category: {str(e)}', 'danger')

    return redirect(url_for('categories'))


@app.route('/categories/delete/<int:category_id>', methods=['POST'])
@login_required
@roles_required('Admin', 'Manager', 'Shop Owner')
def category_delete(category_id):
    prod_count = db.query_one("SELECT COUNT(*) as count FROM PRODUCT WHERE category_id = %s", (category_id,))
    if prod_count and prod_count['count'] > 0:
        flash(f'Cannot delete category: {prod_count["count"]} products are currently assigned to it.', 'danger')
        return redirect(url_for('categories'))

    try:
        db.execute("DELETE FROM CATEGORY WHERE category_id = %s", (category_id,))
        flash('Category deleted successfully.', 'success')
    except Exception as e:
        flash(f'Failed to delete category: {str(e)}', 'danger')

    return redirect(url_for('categories'))


# ==========================================================
# PRODUCT MANAGEMENT ROUTES
# ==========================================================

@app.route('/products')
@login_required
def products():
    search = request.form.get('search') or request.args.get('search', '').strip()
    cat_filter = request.args.get('category', '').strip()
    stock_filter = request.args.get('stock', '').strip()

    sql = """
        SELECT p.*, c.category_name, c.category_code
        FROM PRODUCT p
        JOIN CATEGORY c ON p.category_id = c.category_id
        WHERE 1=1
    """
    params = []

    if search:
        sql += " AND (p.product_name LIKE %s OR p.product_code LIKE %s OR p.brand LIKE %s OR p.model LIKE %s)"
        term = f"%{search}%"
        params.extend([term, term, term, term])

    if cat_filter and cat_filter.isdigit():
        sql += " AND p.category_id = %s"
        params.append(int(cat_filter))

    if stock_filter == 'low':
        sql += " AND p.stock_quantity <= p.reorder_level AND p.stock_quantity > 0"
    elif stock_filter == 'out':
        sql += " AND p.stock_quantity = 0"
    elif stock_filter == 'in':
        sql += " AND p.stock_quantity > p.reorder_level"

    sql += " ORDER BY p.product_name ASC"

    products_list = db.query(sql, tuple(params))
    categories_list = db.query("SELECT * FROM CATEGORY ORDER BY category_code ASC")

    return render_template(
        'products.html',
        products=products_list,
        categories=categories_list,
        search=search,
        selected_category=cat_filter,
        stock_filter=stock_filter
    )


@app.route('/products/add', methods=['POST'])
@login_required
@roles_required('Admin', 'Manager', 'Shop Owner')
def product_add():
    code = request.form.get('product_code', '').strip().upper()
    name = request.form.get('product_name', '').strip()
    category_id = request.form.get('category_id')
    brand = request.form.get('brand', '').strip()
    model = request.form.get('model', '').strip()
    cost_price = float(request.form.get('cost_price', 0.0) or 0.0)
    selling_price = float(request.form.get('selling_price', 0.0) or 0.0)
    stock_quantity = int(request.form.get('stock_quantity', 0) or 0)
    reorder_level = int(request.form.get('reorder_level', 5) or 5)
    warranty_months = int(request.form.get('warranty_months', 12) or 12)
    description = request.form.get('description', '').strip()

    if not code or not name or not category_id or not brand or selling_price <= 0:
        flash('Please fill in all required fields (Product Code, Name, Category, Brand, Valid Price).', 'danger')
        return redirect(url_for('products'))

    existing = db.query_one("SELECT product_id FROM PRODUCT WHERE product_code = %s", (code,))
    if existing:
        flash(f'Product code / SKU "{code}" already exists.', 'warning')
        return redirect(url_for('products'))

    try:
        db.execute("""
            INSERT INTO PRODUCT (product_code, product_name, category_id, brand, model,
                                cost_price, selling_price, stock_quantity, reorder_level,
                                warranty_months, description)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (code, name, category_id, brand, model, cost_price, selling_price,
              stock_quantity, reorder_level, warranty_months, description))
        flash(f'Product "{name}" added successfully with code {code}.', 'success')
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
    cost_price = float(request.form.get('cost_price', 0.0) or 0.0)
    selling_price = float(request.form.get('selling_price', 0.0) or 0.0)
    stock_quantity = int(request.form.get('stock_quantity', 0) or 0)
    reorder_level = int(request.form.get('reorder_level', 5) or 5)
    warranty_months = int(request.form.get('warranty_months', 12) or 12)
    description = request.form.get('description', '').strip()

    existing = db.query_one("SELECT product_id FROM PRODUCT WHERE product_code = %s AND product_id != %s", (code, product_id))
    if existing:
        flash(f'Product code "{code}" is already in use by another item.', 'warning')
        return redirect(url_for('products'))

    try:
        db.execute("""
            UPDATE PRODUCT
            SET product_code = %s, product_name = %s, category_id = %s, brand = %s, model = %s,
                cost_price = %s, selling_price = %s, stock_quantity = %s, reorder_level = %s,
                warranty_months = %s, description = %s
            WHERE product_id = %s
        """, (code, name, category_id, brand, model, cost_price, selling_price,
              stock_quantity, reorder_level, warranty_months, description, product_id))
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
        flash(f'Cannot delete product: {sales_ref["count"]} recorded sales exist for warranty audit history.', 'warning')
        return redirect(url_for('products'))

    try:
        db.execute("DELETE FROM PRODUCT WHERE product_id = %s", (product_id,))
        flash('Product removed from catalog.', 'success')
    except Exception as e:
        flash(f'Error deleting product: {str(e)}', 'danger')

    return redirect(url_for('products'))


# ==========================================================
# INVENTORY TRACKING & RESTOCK ROUTES
# ==========================================================

@app.route('/inventory')
@login_required
def inventory():
    filter_type = request.args.get('filter', 'all')
    category_id = request.args.get('category', '')

    sql = """
        SELECT p.*, c.category_name, c.category_code
        FROM PRODUCT p
        JOIN CATEGORY c ON p.category_id = c.category_id
        WHERE 1=1
    """
    params = []

    if category_id and category_id.isdigit():
        sql += " AND p.category_id = %s"
        params.append(int(category_id))

    if filter_type == 'low':
        sql += " AND p.stock_quantity <= p.reorder_level AND p.stock_quantity > 0"
    elif filter_type == 'out':
        sql += " AND p.stock_quantity = 0"
    elif filter_type == 'in':
        sql += " AND p.stock_quantity > p.reorder_level"

    sql += " ORDER BY p.stock_quantity ASC, p.product_name ASC"
    inventory_items = db.query(sql, tuple(params))
    categories_list = db.query("SELECT * FROM CATEGORY ORDER BY category_code ASC")

    # Inventory Valuation
    valuation = db.query_one("""
        SELECT
            COUNT(*) as total_skus,
            IFNULL(SUM(stock_quantity), 0) as total_units,
            IFNULL(SUM(stock_quantity * cost_price), 0) as total_cost_value,
            IFNULL(SUM(stock_quantity * selling_price), 0) as total_retail_value
        FROM PRODUCT
    """)

    return render_template(
        'inventory.html',
        inventory=inventory_items,
        categories=categories_list,
        current_filter=filter_type,
        selected_category=category_id,
        valuation=valuation
    )


@app.route('/inventory/adjust', methods=['POST'])
@login_required
@roles_required('Admin', 'Manager', 'Shop Owner')
def inventory_adjust():
    product_id = request.form.get('product_id')
    adjustment_type = request.form.get('type')  # 'add', 'deduct', 'set'
    quantity = int(request.form.get('quantity', 0) or 0)
    notes = request.form.get('notes', '').strip()

    if not product_id or quantity < 0:
        flash('Invalid product or quantity specified.', 'danger')
        return redirect(url_for('inventory'))

    prod = db.query_one("SELECT * FROM PRODUCT WHERE product_id = %s", (product_id,))
    if not prod:
        flash('Product not found.', 'danger')
        return redirect(url_for('inventory'))

    current_stock = prod['stock_quantity']
    if adjustment_type == 'add':
        new_stock = current_stock + quantity
    elif adjustment_type == 'deduct':
        new_stock = max(0, current_stock - quantity)
    elif adjustment_type == 'set':
        new_stock = quantity
    else:
        new_stock = current_stock

    try:
        db.execute(
            "UPDATE PRODUCT SET stock_quantity = %s WHERE product_id = %s",
            (new_stock, product_id)
        )
        flash(f'Stock for "{prod["product_name"]}" successfully updated: {current_stock} -> {new_stock} units. ({notes or "Stock Adjustment"})', 'success')
    except Exception as e:
        flash(f'Failed to adjust stock: {str(e)}', 'danger')

    return redirect(url_for('inventory'))


# ==========================================================
# CUSTOMER MANAGEMENT ROUTES
# ==========================================================

@app.route('/customers')
@login_required
def customers():
    search = request.args.get('search', '').strip()
    sql = """
        SELECT c.*,
               COUNT(s.sale_id) as total_orders,
               IFNULL(SUM(s.grand_total), 0) as total_spent,
               MAX(s.sale_date) as last_purchase_date
        FROM CUSTOMER c
        LEFT JOIN SALE s ON c.customer_id = s.customer_id
        WHERE 1=1
    """
    params = []

    if search:
        sql += " AND (c.customer_name LIKE %s OR c.phone LIKE %s OR c.email LIKE %s)"
        term = f"%{search}%"
        params.extend([term, term, term])

    sql += " GROUP BY c.customer_id, c.customer_name, c.phone, c.email, c.address, c.created_at ORDER BY c.customer_name ASC"
    customers_list = db.query(sql, tuple(params))

    return render_template('customers.html', customers=customers_list, search=search)


@app.route('/customers/add', methods=['POST'])
@login_required
def customer_add():
    name = request.form.get('customer_name', '').strip()
    phone = request.form.get('phone', '').strip()
    email = request.form.get('email', '').strip()
    address = request.form.get('address', '').strip()

    if not name or not phone:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'Name and phone are required'}), 400
        flash('Customer name and phone number are required.', 'danger')
        return redirect(url_for('customers'))

    try:
        new_id = db.execute(
            "INSERT INTO CUSTOMER (customer_name, phone, email, address) VALUES (%s, %s, %s, %s)",
            (name, phone, email, address),
            return_id=True
        )
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': True,
                'customer': {
                    'customer_id': new_id,
                    'customer_name': name,
                    'phone': phone,
                    'email': email,
                    'address': address
                }
            })
        flash(f'Customer "{name}" registered successfully.', 'success')
    except Exception as e:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': str(e)}), 500
        flash(f'Error registering customer: {str(e)}', 'danger')

    return redirect(url_for('customers'))


@app.route('/customers/edit/<int:customer_id>', methods=['POST'])
@login_required
def customer_edit(customer_id):
    name = request.form.get('customer_name', '').strip()
    phone = request.form.get('phone', '').strip()
    email = request.form.get('email', '').strip()
    address = request.form.get('address', '').strip()

    if not name or not phone:
        flash('Customer name and phone number are required.', 'danger')
        return redirect(url_for('customers'))

    try:
        db.execute(
            "UPDATE CUSTOMER SET customer_name = %s, phone = %s, email = %s, address = %s WHERE customer_id = %s",
            (name, phone, email, address, customer_id)
        )
        flash(f'Customer "{name}" updated successfully.', 'success')
    except Exception as e:
        flash(f'Error updating customer: {str(e)}', 'danger')

    return redirect(url_for('customers'))


@app.route('/customers/delete/<int:customer_id>', methods=['POST'])
@login_required
@roles_required('Admin', 'Manager', 'Shop Owner')
def customer_delete(customer_id):
    try:
        db.execute("DELETE FROM CUSTOMER WHERE customer_id = %s", (customer_id,))
        flash('Customer removed successfully.', 'success')
    except Exception as e:
        flash(f'Failed to delete customer: {str(e)}', 'danger')

    return redirect(url_for('customers'))


@app.route('/customers/<int:customer_id>')
@login_required
def customer_detail(customer_id):
    cust = db.query_one("SELECT * FROM CUSTOMER WHERE customer_id = %s", (customer_id,))
    if not cust:
        flash('Customer not found.', 'danger')
        return redirect(url_for('customers'))

    purchases = db.query("""
        SELECT s.*, u.full_name as staff_name, u.avatar as staff_avatar,
               (SELECT COUNT(*) FROM SALE_ITEM si WHERE si.sale_id = s.sale_id) as item_count
        FROM SALE s
        JOIN USER u ON s.user_id = u.user_id
        WHERE s.customer_id = %s
        ORDER BY s.sale_date DESC
    """, (customer_id,))

    warranties = db.query("""
        SELECT si.*, p.product_name, p.product_code, p.brand, p.model, s.invoice_number, s.sale_date
        FROM SALE_ITEM si
        JOIN SALE s ON si.sale_id = s.sale_id
        JOIN PRODUCT p ON si.product_id = p.product_id
        WHERE s.customer_id = %s
        ORDER BY si.warranty_expiry_date DESC
    """, (customer_id,))

    return render_template(
        'customer_detail.html',
        customer=cust,
        purchases=purchases,
        warranties=warranties
    )


# ==========================================================
# POINT OF SALE & AUTOMATIC BILLING (GST 18%)
# ==========================================================

@app.route('/pos')
@login_required
def pos():
    products_list = db.query("""
        SELECT p.*, c.category_name, c.category_code
        FROM PRODUCT p
        JOIN CATEGORY c ON p.category_id = c.category_id
        WHERE p.stock_quantity > 0
        ORDER BY p.product_name ASC
    """)
    categories_list = db.query("SELECT * FROM CATEGORY ORDER BY category_code ASC")
    customers_list = db.query("SELECT * FROM CUSTOMER ORDER BY customer_name ASC")

    # Generate prospective invoice preview
    today_code = datetime.datetime.now().strftime('%Y%m%d')
    last_inv_row = db.query_one("SELECT invoice_number FROM SALE WHERE invoice_number LIKE %s ORDER BY sale_id DESC LIMIT 1", (f"INV-{today_code}-%",))
    if last_inv_row:
        try:
            seq_num = int(str(last_inv_row['invoice_number']).split('-')[-1]) + 1
        except Exception:
            seq_num = 1
    else:
        seq_num = 1
    invoice_preview = f"INV-{today_code}-{seq_num:03d}"

    return render_template(
        'pos.html',
        products=products_list,
        categories=categories_list,
        customers=customers_list,
        invoice_preview=invoice_preview
    )


@app.route('/api/pos/checkout', methods=['POST'])
@login_required
def pos_checkout():
    """
    Handles automatic billing checkout:
    1. Validates cart items and verifies stock.
    2. Atomically creates SALE record with CGST (9%) + SGST (9%) = GST 18%.
    3. Creates SALE_ITEM records with calculated warranty expiration dates.
    4. Automatically decrements inventory stock.
    """
    data = request.get_json() or {}
    items = data.get('items', [])
    customer_id = data.get('customer_id') or None
    payment_method = data.get('payment_method', 'Cash')
    payment_status = data.get('payment_status', 'Paid')
    tax_rate = float(data.get('tax_rate', config.DEFAULT_TAX_RATE))
    discount_amount = float(data.get('discount_amount', 0.0) or 0.0)
    notes = data.get('notes', '').strip()

    if not items:
        return jsonify({'success': False, 'message': 'Cart is empty. Please select products to bill.'}), 400

    conn = db.get_connection()
    try:
        cursor = conn.cursor()

        # Generate unique sequential invoice number
        today_code = datetime.datetime.now().strftime('%Y%m%d')
        cursor.execute(db._adapt_sql("SELECT invoice_number FROM SALE WHERE invoice_number LIKE %s ORDER BY sale_id DESC LIMIT 1"), (f"INV-{today_code}-%",))
        last_row = cursor.fetchone()
        if last_row:
            last_inv = last_row['invoice_number'] if isinstance(last_row, dict) else last_row[0]
            try:
                seq_num = int(str(last_inv).split('-')[-1]) + 1
            except Exception:
                seq_num = 1
        else:
            seq_num = 1
        invoice_number = f"INV-{today_code}-{seq_num:03d}"

        subtotal = 0.0
        validated_items = []

        for item in items:
            p_id = item.get('product_id')
            qty = int(item.get('quantity', 1))
            serial = item.get('serial_number', '').strip()

            cursor.execute(db._adapt_sql("SELECT * FROM PRODUCT WHERE product_id = %s"), (p_id,))
            row = cursor.fetchone()
            prod = db._row_to_dict(row)

            if not prod:
                conn.rollback()
                return jsonify({'success': False, 'message': f"Product ID {p_id} not found."}), 400

            if prod['stock_quantity'] < qty:
                conn.rollback()
                return jsonify({
                    'success': False,
                    'message': f"Insufficient stock for {prod['product_name']}. Requested: {qty}, Available: {prod['stock_quantity']}."
                }), 400

            unit_price = float(prod['selling_price'])
            item_total = unit_price * qty
            subtotal += item_total

            # Calculate warranty expiry date: today + warranty_months
            warranty_months = int(prod.get('warranty_months', 12))
            today_date = datetime.date.today()
            year_add = (today_date.month + warranty_months - 1) // 12
            new_month = ((today_date.month + warranty_months - 1) % 12) + 1
            new_day = min(today_date.day, 28)
            try:
                warranty_expiry = datetime.date(today_date.year + year_add, new_month, today_date.day).strftime('%Y-%m-%d')
            except ValueError:
                warranty_expiry = datetime.date(today_date.year + year_add, new_month, new_day).strftime('%Y-%m-%d')

            validated_items.append({
                'product_id': p_id,
                'quantity': qty,
                'unit_price': unit_price,
                'total_price': item_total,
                'serial_number': serial or f"SN-{prod['product_code']}-{datetime.datetime.now().strftime('%f')[:4]}",
                'warranty_expiry_date': warranty_expiry
            })

        # Calculate GST: CGST (9%) + SGST (9%) = 18%
        cgst_rate = tax_rate / 2.0
        sgst_rate = tax_rate / 2.0
        cgst_amount = round(subtotal * (cgst_rate / 100.0), 2)
        sgst_amount = round(subtotal * (sgst_rate / 100.0), 2)
        total_tax = round(cgst_amount + sgst_amount, 2)
        grand_total = max(0.0, round(subtotal + total_tax - discount_amount, 2))

        # Insert into SALE
        cursor.execute(db._adapt_sql("""
            INSERT INTO SALE (invoice_number, customer_id, user_id, sale_date,
                              subtotal, cgst_amount, sgst_amount, tax_amount,
                              discount_amount, grand_total, payment_method, payment_status, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """), (
            invoice_number,
            customer_id,
            session['user_id'],
            datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            subtotal,
            cgst_amount,
            sgst_amount,
            total_tax,
            discount_amount,
            grand_total,
            payment_method,
            payment_status,
            notes
        ))
        sale_id = cursor.lastrowid

        # Insert SALE_ITEMS and decrement stock
        for v_item in validated_items:
            cursor.execute(db._adapt_sql("""
                INSERT INTO SALE_ITEM (sale_id, product_id, quantity, unit_price, total_price, serial_number, warranty_expiry_date)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """), (
                sale_id,
                v_item['product_id'],
                v_item['quantity'],
                v_item['unit_price'],
                v_item['total_price'],
                v_item['serial_number'],
                v_item['warranty_expiry_date']
            ))

            cursor.execute(db._adapt_sql("""
                UPDATE PRODUCT
                SET stock_quantity = stock_quantity - %s
                WHERE product_id = %s
            """), (v_item['quantity'], v_item['product_id']))

        conn.commit()

        return jsonify({
            'success': True,
            'sale_id': sale_id,
            'invoice_number': invoice_number,
            'grand_total': grand_total,
            'message': f"Sale completed! Invoice #{invoice_number} generated."
        })

    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': f"Transaction failed: {str(e)}"}), 500
    finally:
        conn.close()


# ==========================================================
# INVOICES & BILLING ROUTES
# ==========================================================

@app.route('/invoices')
@login_required
def invoices():
    search = request.args.get('search', '').strip()
    status_filter = request.args.get('status', '').strip()
    date_filter = request.args.get('date', '').strip()

    sql = """
        SELECT s.*, c.customer_name, c.phone as customer_phone, u.full_name as staff_name, u.avatar as staff_avatar,
               (SELECT COUNT(*) FROM SALE_ITEM si WHERE si.sale_id = s.sale_id) as total_items
        FROM SALE s
        LEFT JOIN CUSTOMER c ON s.customer_id = c.customer_id
        JOIN USER u ON s.user_id = u.user_id
        WHERE 1=1
    """
    params = []

    if search:
        sql += " AND (s.invoice_number LIKE %s OR c.customer_name LIKE %s OR c.phone LIKE %s)"
        term = f"%{search}%"
        params.extend([term, term, term])

    if status_filter:
        sql += " AND s.payment_status = %s"
        params.append(status_filter)

    if date_filter:
        sql += " AND DATE(s.sale_date) = %s"
        params.append(date_filter)

    sql += " ORDER BY s.sale_date DESC"
    invoices_list = db.query(sql, tuple(params))

    return render_template(
        'invoices_list.html',
        invoices=invoices_list,
        search=search,
        status_filter=status_filter,
        date_filter=date_filter
    )


@app.route('/invoice/<int:sale_id>')
@login_required
def invoice_view(sale_id):
    sale = db.query_one("""
        SELECT s.*, c.customer_name, c.phone as customer_phone, c.email as customer_email,
               c.address as customer_address, u.full_name as staff_name, u.role as staff_role, u.avatar as staff_avatar
        FROM SALE s
        LEFT JOIN CUSTOMER c ON s.customer_id = c.customer_id
        JOIN USER u ON s.user_id = u.user_id
        WHERE s.sale_id = %s
    """, (sale_id,))

    if not sale:
        flash('Invoice not found.', 'danger')
        return redirect(url_for('invoices'))

    items = db.query("""
        SELECT si.*, p.product_name, p.product_code, p.brand, p.model, p.warranty_months
        FROM SALE_ITEM si
        JOIN PRODUCT p ON si.product_id = p.product_id
        WHERE si.sale_id = %s
        ORDER BY si.item_id ASC
    """, (sale_id,))

    # GST calculation breakdown (CGST 9% + SGST 9%)
    subtotal = float(sale.get('subtotal', 0.0))
    cgst_val = float(sale.get('cgst_amount') or round(subtotal * 0.09, 2))
    sgst_val = float(sale.get('sgst_amount') or round(subtotal * 0.09, 2))

    return render_template('invoice.html', sale=sale, items=items, cgst_val=cgst_val, sgst_val=sgst_val)


# ==========================================================
# WARRANTY TRACKING ROUTE
# ==========================================================

@app.route('/warranty')
@login_required
def warranty():
    search = request.args.get('search', '').strip()
    status_filter = request.args.get('status', 'all')

    sql = """
        SELECT si.item_id, si.serial_number, si.warranty_expiry_date, si.quantity, si.unit_price,
               p.product_id, p.product_name, p.product_code, p.brand, p.model, p.warranty_months,
               s.sale_id, s.invoice_number, s.sale_date,
               c.customer_id, c.customer_name, c.phone as customer_phone, c.email as customer_email
        FROM SALE_ITEM si
        JOIN SALE s ON si.sale_id = s.sale_id
        JOIN PRODUCT p ON si.product_id = p.product_id
        LEFT JOIN CUSTOMER c ON s.customer_id = c.customer_id
        WHERE 1=1
    """
    params = []

    if search:
        sql += " AND (si.serial_number LIKE %s OR s.invoice_number LIKE %s OR p.product_name LIKE %s OR c.customer_name LIKE %s OR c.phone LIKE %s)"
        term = f"%{search}%"
        params.extend([term, term, term, term, term])

    sql += " ORDER BY si.warranty_expiry_date ASC"
    raw_warranties = db.query(sql, tuple(params))

    today = datetime.date.today()
    processed_warranties = []

    for w in raw_warranties:
        exp_str = w['warranty_expiry_date']
        if exp_str:
            if isinstance(exp_str, str):
                try:
                    exp_date = datetime.datetime.strptime(exp_str[:10], '%Y-%m-%d').date()
                except ValueError:
                    exp_date = today
            elif isinstance(exp_str, (datetime.date, datetime.datetime)):
                exp_date = exp_str if isinstance(exp_str, datetime.date) else exp_str.date()
            else:
                exp_date = today

            days_left = (exp_date - today).days

            if days_left < 0:
                status = 'Expired'
                badge_class = 'bg-danger'
            elif days_left <= 30:
                status = 'Expiring Soon'
                badge_class = 'bg-warning text-dark'
            else:
                status = 'Active'
                badge_class = 'bg-success'
        else:
            days_left = 0
            status = 'No Warranty'
            badge_class = 'bg-secondary'

        w['days_left'] = days_left
        w['status'] = status
        w['badge_class'] = badge_class

        if status_filter == 'active' and status != 'Active':
            continue
        elif status_filter == 'expiring' and status != 'Expiring Soon':
            continue
        elif status_filter == 'expired' and status != 'Expired':
            continue

        processed_warranties.append(w)

    return render_template(
        'warranty.html',
        warranties=processed_warranties,
        search=search,
        status_filter=status_filter
    )


# ==========================================================
# SALES & INVENTORY REPORTS (TABS & 14-DAY NAVY CHART)
# ==========================================================

@app.route('/reports')
@login_required
@roles_required('Admin', 'Manager', 'Shop Owner')
def reports():
    tab = request.args.get('tab', 'sales')  # 'sales' or 'inventory'
    date_preset = request.args.get('preset', 'month')
    custom_start = request.args.get('start_date', '')
    custom_end = request.args.get('end_date', '')

    today = datetime.date.today()

    if date_preset == 'today':
        start_date = today
        end_date = today
    elif date_preset == 'yesterday':
        start_date = today - datetime.timedelta(days=1)
        end_date = today - datetime.timedelta(days=1)
    elif date_preset == 'week':
        start_date = today - datetime.timedelta(days=7)
        end_date = today
    elif date_preset == 'month':
        start_date = today.replace(day=1)
        end_date = today
    elif date_preset == 'year':
        start_date = today.replace(month=1, day=1)
        end_date = today
    elif date_preset == 'custom' and custom_start and custom_end:
        try:
            start_date = datetime.datetime.strptime(custom_start, '%Y-%m-%d').date()
            end_date = datetime.datetime.strptime(custom_end, '%Y-%m-%d').date()
        except ValueError:
            start_date = today.replace(day=1)
            end_date = today
    else:
        start_date = today.replace(day=1)
        end_date = today

    start_str = start_date.strftime('%Y-%m-%d 00:00:00')
    end_str = end_date.strftime('%Y-%m-%d 23:59:59')

    # 1. Sales Performance Metrics in Date Range
    metrics = db.query_one("""
        SELECT
            COUNT(*) as total_orders,
            IFNULL(SUM(subtotal), 0) as total_subtotal,
            IFNULL(SUM(tax_amount), 0) as total_tax,
            IFNULL(SUM(discount_amount), 0) as total_discounts,
            IFNULL(SUM(grand_total), 0) as total_revenue
        FROM SALE
        WHERE sale_date BETWEEN %s AND %s
    """, (start_str, end_str))

    total_orders = metrics['total_orders'] if metrics else 0
    total_revenue = float(metrics['total_revenue']) if metrics else 0.0
    avg_order_value = (total_revenue / total_orders) if total_orders > 0 else 0.0

    # 2. Cost of Goods Sold & Gross Profit
    cogs_data = db.query_one("""
        SELECT IFNULL(SUM(si.quantity * p.cost_price), 0) as total_cost
        FROM SALE_ITEM si
        JOIN SALE s ON si.sale_id = s.sale_id
        JOIN PRODUCT p ON si.product_id = p.product_id
        WHERE s.sale_date BETWEEN %s AND %s
    """, (start_str, end_str))
    total_cogs = float(cogs_data['total_cost']) if cogs_data else 0.0
    gross_profit = total_revenue - total_cogs
    profit_margin = ((gross_profit / total_revenue) * 100.0) if total_revenue > 0 else 0.0

    # 3. Last 14 Days Daily Revenue Data for Navy Bar Chart
    last_14_days_labels = []
    last_14_days_values = []
    for i in range(13, -1, -1):
        day_dt = today - datetime.timedelta(days=i)
        day_str = day_dt.strftime('%Y-%m-%d')
        day_label = day_dt.strftime('%d %b')
        last_14_days_labels.append(day_label)

        day_rev = db.query_one("""
            SELECT IFNULL(SUM(grand_total), 0) as total
            FROM SALE
            WHERE DATE(sale_date) = %s
        """, (day_str,))
        last_14_days_values.append(float(day_rev['total']) if day_rev else 0.0)

    # 4. Category Breakdown
    cat_breakdown = db.query("""
        SELECT c.category_name, c.category_code,
               COUNT(DISTINCT s.sale_id) as transaction_count,
               IFNULL(SUM(si.quantity), 0) as units_sold,
               IFNULL(SUM(si.total_price), 0) as revenue
        FROM CATEGORY c
        JOIN PRODUCT p ON c.category_id = p.category_id
        JOIN SALE_ITEM si ON p.product_id = si.product_id
        JOIN SALE s ON si.sale_id = s.sale_id
        WHERE s.sale_date BETWEEN %s AND %s
        GROUP BY c.category_id, c.category_name, c.category_code
        ORDER BY revenue DESC
    """, (start_str, end_str))

    # 5. Top Selling Products in Range
    top_selling = db.query("""
        SELECT p.product_code, p.product_name, p.brand, c.category_name,
               SUM(si.quantity) as units_sold,
               SUM(si.total_price) as total_revenue,
               SUM(si.total_price - (si.quantity * p.cost_price)) as estimated_profit
        FROM SALE_ITEM si
        JOIN SALE s ON si.sale_id = s.sale_id
        JOIN PRODUCT p ON si.product_id = p.product_id
        JOIN CATEGORY c ON p.category_id = c.category_id
        WHERE s.sale_date BETWEEN %s AND %s
        GROUP BY p.product_id, p.product_code, p.product_name, p.brand, c.category_name
        ORDER BY units_sold DESC
        LIMIT 10
    """, (start_str, end_str))

    # 6. Payment Methods Breakdown
    payment_breakdown = db.query("""
        SELECT payment_method, COUNT(*) as count, IFNULL(SUM(grand_total), 0) as amount
        FROM SALE
        WHERE sale_date BETWEEN %s AND %s
        GROUP BY payment_method
        ORDER BY amount DESC
    """, (start_str, end_str))

    # 7. Inventory Report Data (for Inventory Tab)
    inventory_valuation = db.query_one("""
        SELECT
            COUNT(*) as total_skus,
            IFNULL(SUM(stock_quantity), 0) as total_units,
            IFNULL(SUM(stock_quantity * cost_price), 0) as total_cost,
            IFNULL(SUM(stock_quantity * selling_price), 0) as total_retail
        FROM PRODUCT
    """)

    category_stock_summary = db.query("""
        SELECT c.category_name, c.category_code,
               COUNT(p.product_id) as sku_count,
               IFNULL(SUM(p.stock_quantity), 0) as total_stock,
               IFNULL(SUM(p.stock_quantity * p.cost_price), 0) as cost_value,
               IFNULL(SUM(p.stock_quantity * p.selling_price), 0) as retail_value
        FROM CATEGORY c
        LEFT JOIN PRODUCT p ON c.category_id = p.category_id
        GROUP BY c.category_id, c.category_name, c.category_code
        ORDER BY retail_value DESC
    """)

    low_stock_audit = db.query("""
        SELECT p.*, c.category_name
        FROM PRODUCT p
        JOIN CATEGORY c ON p.category_id = c.category_id
        WHERE p.stock_quantity <= p.reorder_level
        ORDER BY p.stock_quantity ASC
    """)

    return render_template(
        'reports.html',
        active_tab=tab,
        date_preset=date_preset,
        start_date=start_date.strftime('%Y-%m-%d'),
        end_date=end_date.strftime('%Y-%m-%d'),
        start_date_formatted=format_date_in(start_date),
        end_date_formatted=format_date_in(end_date),
        total_orders=total_orders,
        total_revenue=total_revenue,
        total_cogs=total_cogs,
        gross_profit=gross_profit,
        profit_margin=profit_margin,
        avg_order_value=avg_order_value,
        last_14_days_labels=last_14_days_labels,
        last_14_days_values=last_14_days_values,
        cat_breakdown=cat_breakdown,
        top_selling=top_selling,
        payment_breakdown=payment_breakdown,
        inventory_valuation=inventory_valuation,
        category_stock_summary=category_stock_summary,
        low_stock_audit=low_stock_audit
    )


# ==========================================================
# USERS & ROLES MANAGEMENT (WITH PERMISSION MATRIX)
# ==========================================================

@app.route('/users')
@login_required
@roles_required('Admin', 'Shop Owner')
def users():
    users_list = db.query("SELECT * FROM USER ORDER BY user_id ASC")

    # Permission Matrix Definition (Modules x 4 Roles)
    # Roles: System Administrator, Shop Owner, Shop Manager, Sales Staff
    permission_matrix = [
        {
            'module': 'Executive Dashboard & KPIs',
            'desc': 'Real-time sales, revenue cards, low-stock alerts and charts',
            'admin': True, 'owner': True, 'manager': True, 'staff': True
        },
        {
            'module': 'Point of Sale (POS) & Billing',
            'desc': 'Product catalog barcode scanning, live cart, tax & discount calculation',
            'admin': True, 'owner': True, 'manager': True, 'staff': True
        },
        {
            'module': 'Printable Invoices & Receipts',
            'desc': 'Tax invoice generation, thermal/A4 printing, reprint invoice',
            'admin': True, 'owner': True, 'manager': True, 'staff': True
        },
        {
            'module': 'Warranty Lookup & Tracking',
            'desc': 'Serial number search, expiry date calculations, certificate view',
            'admin': True, 'owner': True, 'manager': True, 'staff': True
        },
        {
            'module': 'Customer CRM (View & Register)',
            'desc': 'Customer registration, address, purchase and warranty history',
            'admin': True, 'owner': True, 'manager': True, 'staff': True
        },
        {
            'module': 'Product & Category Catalog CRUD',
            'desc': 'Add, edit, delete products, categories, SKU pricing & specifications',
            'admin': True, 'owner': True, 'manager': True, 'staff': False
        },
        {
            'module': 'Inventory Stock Adjustments',
            'desc': 'Restock deliveries, write-offs for damaged goods, physical stock audit',
            'admin': True, 'owner': True, 'manager': True, 'staff': False
        },
        {
            'module': 'Sales & Financial Reports',
            'desc': '14-day revenue charts, gross profit, category breakdown, inventory valuation',
            'admin': True, 'owner': True, 'manager': True, 'staff': False
        },
        {
            'module': 'Staff Users & Roles Administration',
            'desc': 'Create, edit staff accounts, assign roles, password reset',
            'admin': True, 'owner': True, 'manager': False, 'staff': False
        },
        {
            'module': 'System Configuration & DB Maintenance',
            'desc': 'Store profile, GSTIN rates, tax settings and database migrations',
            'admin': True, 'owner': False, 'manager': False, 'staff': False
        }
    ]

    return render_template(
        'users.html',
        users=users_list,
        matrix=permission_matrix
    )


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

    valid_roles = ['System Administrator', 'Shop Owner', 'Shop Manager', 'Sales Staff', 'Admin', 'Manager']
    if not username or not full_name or not password or role not in valid_roles:
        flash('Please fill in all required user fields.', 'danger')
        return redirect(url_for('users'))

    existing = db.query_one("SELECT user_id FROM USER WHERE username = %s", (username,))
    if existing:
        flash(f'Username "{username}" is already taken.', 'warning')
        return redirect(url_for('users'))

    avatar = get_avatar(username, full_name)
    p_hash = generate_password_hash(password)
    try:
        db.execute("""
            INSERT INTO USER (username, password_hash, full_name, role, avatar, email, phone, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'Active')
        """, (username, p_hash, full_name, role, avatar, email, phone))
        flash(f'User account "{full_name}" ({username}) created successfully.', 'success')
    except Exception as e:
        flash(f'Failed to create user: {str(e)}', 'danger')

    return redirect(url_for('users'))


@app.route('/users/edit/<int:user_id>', methods=['POST'])
@login_required
@roles_required('Admin', 'Shop Owner')
def user_edit(user_id):
    full_name = request.form.get('full_name', '').strip()
    role = request.form.get('role', 'Sales Staff')
    status = request.form.get('status', 'Active')
    email = request.form.get('email', '').strip()
    phone = request.form.get('phone', '').strip()
    new_password = request.form.get('password', '').strip()

    valid_roles = ['System Administrator', 'Shop Owner', 'Shop Manager', 'Sales Staff', 'Admin', 'Manager']
    if role not in valid_roles:
        flash('Invalid role selected.', 'danger')
        return redirect(url_for('users'))

    user = db.query_one("SELECT username FROM USER WHERE user_id = %s", (user_id,))
    username = user['username'] if user else ''
    avatar = get_avatar(username, full_name)

    try:
        if new_password:
            p_hash = generate_password_hash(new_password)
            db.execute("""
                UPDATE USER
                SET full_name = %s, role = %s, status = %s, email = %s, phone = %s, avatar = %s, password_hash = %s
                WHERE user_id = %s
            """, (full_name, role, status, email, phone, avatar, p_hash, user_id))
            flash(f'User #{user_id} updated with new password.', 'success')
        else:
            db.execute("""
                UPDATE USER
                SET full_name = %s, role = %s, status = %s, email = %s, phone = %s, avatar = %s
                WHERE user_id = %s
            """, (full_name, role, status, email, phone, avatar, user_id))
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

    sales_by_user = db.query_one("SELECT COUNT(*) as count FROM SALE WHERE user_id = %s", (user_id,))
    if sales_by_user and sales_by_user['count'] > 0:
        flash(f'User has processed {sales_by_user["count"]} sales invoices. Set status to "Inactive" instead to preserve audit records.', 'warning')
        return redirect(url_for('users'))

    try:
        db.execute("DELETE FROM USER WHERE user_id = %s", (user_id,))
        flash('User account deleted successfully.', 'success')
    except Exception as e:
        flash(f'Failed to delete user: {str(e)}', 'danger')

    return redirect(url_for('users'))


# ==========================================================
# APPLICATION ENTRYPOINT
# ==========================================================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"Starting Electrodesk Management System on http://127.0.0.1:{port}")
    app.run(host='0.0.0.0', port=port, debug=config.DEBUG)
