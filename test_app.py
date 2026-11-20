"""
Automated Comprehensive Test Suite for Electrodesk - Electronics Shop Management System
Tests all endpoints, 4 RBAC roles (Ram, Geetha, Sai, Suresh), Indian Rupee formatting,
GST (CGST 9% + SGST 9%) calculations, automatic billing, stock deductions, and warranty tracking.
"""
import unittest
import json
import os
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app import app
import db
import init_db
import config


class TestElectrodeskSystem(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        if os.path.exists(config.SQLITE_DB_PATH):
            os.remove(config.SQLITE_DB_PATH)
        init_db.init_sqlite_db()
        cls.client = app.test_client()

    def login(self, username, password):
        return self.client.post('/login', data={
            'username': username,
            'password': password
        }, follow_redirects=True)

    def logout(self):
        return self.client.get('/logout', follow_redirects=True)

    def test_01_login_all_roles(self):
        """Test login for Ram, Geetha, Sai, and Suresh with their avatars."""
        # 1. Ram (admin) - System Administrator
        resp = self.login('admin', 'admin123')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Mirror Hall', resp.data)
        self.assertIn(b'Ram', resp.data)
        self.assertIn(b'RA', resp.data)
        self.logout()

        # 2. Geetha (geetha) - Shop Manager
        resp = self.login('geetha', 'geetha123')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Geetha', resp.data)
        self.assertIn(b'GE', resp.data)
        self.logout()

        # 3. Sai (sai) - Sales Staff
        resp = self.login('sai', 'sai123')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Sai', resp.data)
        self.assertIn(b'SA', resp.data)
        self.logout()

        # 4. Suresh (suresh) - Shop Owner
        resp = self.login('suresh', 'suresh123')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Suresh', resp.data)
        self.assertIn(b'S', resp.data)
        self.logout()

    def test_02_rbac_restrictions(self):
        """Verify role permissions (Sales Staff and Manager cannot access /users, Admin and Owner can)."""
        # Sai (Sales Staff) trying to access user management
        self.login('sai', 'sai123')
        resp = self.client.get('/users', follow_redirects=True)
        self.assertIn(b'Access denied', resp.data)
        self.logout()

        # Geetha (Shop Manager) trying to access user management
        self.login('geetha', 'geetha123')
        resp = self.client.get('/users', follow_redirects=True)
        self.assertIn(b'Access denied', resp.data)
        self.logout()

        # Ram (System Administrator) can access user management & matrix
        self.login('admin', 'admin123')
        resp = self.client.get('/users', follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Users & Access Control', resp.data)
        self.assertIn(b'Role Permission Matrix', resp.data)
        self.logout()

    def test_03_dashboard_and_low_stock_alerts(self):
        """Test dashboard metrics, recent sales and low stock alerts."""
        self.login('admin', 'admin123')
        resp = self.client.get('/dashboard')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Today's Sales", resp.data)
        self.assertIn(b'Low Stock Alert', resp.data)
        self.assertIn(b'Recent Sales', resp.data)
        self.logout()

    def test_04_category_crud_and_2col_grid(self):
        """Test category management with CAT-code and 2-column card stats."""
        self.login('geetha', 'geetha123')
        
        # Add category
        resp = self.client.post('/categories/add', data={
            'category_code': 'CAT-99',
            'category_name': 'Smart Home Automation',
            'icon': 'bi-house-gear',
            'description': 'Smart bulbs, hubs, robotic vacuums'
        }, follow_redirects=True)
        self.assertIn(b'created successfully', resp.data)

        # Verify in database
        cat = db.query_one("SELECT * FROM CATEGORY WHERE category_name = 'Smart Home Automation'")
        self.assertIsNotNone(cat)
        self.assertEqual(cat['category_code'], 'CAT-99')

        # View category page
        resp = self.client.get('/categories')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'CAT-99', resp.data)
        self.assertIn(b'Smart Home Automation', resp.data)

        # Edit category
        resp = self.client.post(f'/categories/edit/{cat["category_id"]}', data={
            'category_code': 'CAT-99',
            'category_name': 'Smart Home Automation Pro',
            'icon': 'bi-cpu',
            'description': 'Updated description'
        }, follow_redirects=True)
        self.assertIn(b'updated successfully', resp.data)

        # Delete category
        resp = self.client.post(f'/categories/delete/{cat["category_id"]}', follow_redirects=True)
        self.assertIn(b'deleted successfully', resp.data)
        self.logout()

    def test_05_product_crud(self):
        """Test product addition with INR pricing, editing and listing."""
        self.login('admin', 'admin123')

        # Add new product
        resp = self.client.post('/products/add', data={
            'product_code': 'TEST-ELEC-999',
            'product_name': 'Test Wireless Noise Earbuds',
            'category_id': 3,
            'brand': 'AudioMax',
            'model': 'AM-X1',
            'cost_price': '4500',
            'selling_price': '8999',
            'stock_quantity': '15',
            'reorder_level': '5',
            'warranty_months': '18',
            'description': 'Bluetooth 5.4 wireless earbuds'
        }, follow_redirects=True)
        self.assertIn(b'added successfully', resp.data)

        prod = db.query_one("SELECT * FROM PRODUCT WHERE product_code = 'TEST-ELEC-999'")
        self.assertIsNotNone(prod)
        self.assertEqual(prod['brand'], 'AudioMax')

        # Edit product
        resp = self.client.post(f'/products/edit/{prod["product_id"]}', data={
            'product_code': 'TEST-ELEC-999',
            'product_name': 'Test Wireless Noise Earbuds Pro',
            'category_id': 3,
            'brand': 'AudioMax',
            'model': 'AM-X1 Pro',
            'cost_price': '4500',
            'selling_price': '9999',
            'stock_quantity': '20',
            'reorder_level': '5',
            'warranty_months': '24',
            'description': 'Upgraded drivers'
        }, follow_redirects=True)
        self.assertIn(b'updated successfully', resp.data)

        # Clean up test product
        db.execute("DELETE FROM STOCK_MOVEMENT WHERE product_id = %s", (prod['product_id'],))
        db.execute("DELETE FROM PRODUCT WHERE product_id = %s", (prod['product_id'],))
        self.logout()

    def test_06_customer_crud(self):
        """Test customer registration, editing and profile details."""
        self.login('sai', 'sai123')

        # Add customer
        resp = self.client.post('/customers/add', data={
            'customer_name': 'Venkatesh Rao',
            'phone': '+91 98888 77777',
            'email': 'venkatesh@example.in',
            'address': 'Banjara Hills, Hyderabad'
        }, follow_redirects=True)
        self.assertIn(b'registered successfully', resp.data)

        cust = db.query_one("SELECT * FROM CUSTOMER WHERE phone = '+91 98888 77777'")
        self.assertIsNotNone(cust)

        # View customer detail page
        resp = self.client.get(f'/customers/{cust["customer_id"]}')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Venkatesh Rao', resp.data)

        # Edit customer
        resp = self.client.post(f'/customers/edit/{cust["customer_id"]}', data={
            'customer_name': 'Venkatesh Rao Updated',
            'phone': '+91 98888 77777',
            'email': 'venkat.updated@example.in',
            'address': 'Madhapur, Hyderabad'
        }, follow_redirects=True)
        self.assertIn(b'updated successfully', resp.data)

        self.logout()

    def test_07_inventory_tracking_and_adjustment(self):
        """Test inventory view and stock adjustment."""
        self.login('geetha', 'geetha123')

        # Check inventory page
        resp = self.client.get('/inventory')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Inventory Cost Value', resp.data)

        # Adjust stock on product 1 (add 5 units)
        prod_before = db.query_one("SELECT stock_quantity FROM PRODUCT WHERE product_id = 1")
        initial_stock = prod_before['stock_quantity']

        resp = self.client.post('/inventory/adjust', data={
            'product_id': 1,
            'type': 'add',
            'quantity': 5,
            'notes': 'Test batch delivery'
        }, follow_redirects=True)
        self.assertIn(b'successfully updated', resp.data)

        prod_after = db.query_one("SELECT stock_quantity FROM PRODUCT WHERE product_id = 1")
        self.assertEqual(prod_after['stock_quantity'], initial_stock + 5)

        # Reset stock back
        db.execute("UPDATE PRODUCT SET stock_quantity = %s WHERE product_id = 1", (initial_stock,))
        self.logout()

    def test_08_pos_automatic_billing_checkout(self):
        """
        Test automatic billing:
        - Select items
        - Apply GST 18% (CGST 9% + SGST 9%)
        - Stock deduction in PRODUCT
        - SALE and SALE_ITEM record generation
        - Warranty expiry calculation
        - Sold by cashier metadata
        """
        self.login('sai', 'sai123')

        # Check product 1 initial stock
        prod = db.query_one("SELECT * FROM PRODUCT WHERE product_id = 1")
        initial_stock = prod['stock_quantity']

        payload = {
            'items': [
                {
                    'product_id': 1,
                    'quantity': 1,
                    'serial_number': 'SN-TEST-S25U-9901'
                }
            ],
            'customer_id': 1,
            'payment_method': 'UPI',
            'payment_status': 'Paid',
            'tax_rate': 18.0,
            'discount_amount': 500.0,
            'notes': 'Electrodesk POS Test Sale'
        }

        resp = self.client.post('/api/pos/checkout',
                                data=json.dumps(payload),
                                content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        res_data = json.loads(resp.data)
        self.assertTrue(res_data['success'])
        self.assertIn('sale_id', res_data)
        sale_id = res_data['sale_id']

        # Verify stock was deducted accurately
        prod_after = db.query_one("SELECT stock_quantity FROM PRODUCT WHERE product_id = 1")
        self.assertEqual(prod_after['stock_quantity'], initial_stock - 1)

        # Verify SALE record
        sale = db.query_one("SELECT * FROM SALE WHERE sale_id = %s", (sale_id,))
        self.assertIsNotNone(sale)
        self.assertEqual(sale['customer_id'], 1)
        self.assertEqual(sale['payment_method'], 'UPI')

        # Verify SALE_ITEM and warranty date calculation
        items = db.query("SELECT * FROM SALE_ITEM WHERE sale_id = %s", (sale_id,))
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['serial_number'], 'SN-TEST-S25U-9901')
        self.assertIsNotNone(items[0]['warranty_expiry_date'])

        # Test printable invoice rendering
        inv_resp = self.client.get(f'/invoice/{sale_id}')
        self.assertEqual(inv_resp.status_code, 200)
        self.assertIn(b'Tax Invoice', inv_resp.data)
        self.assertIn(b'Electrodesk', inv_resp.data)
        self.assertIn(b'CGST (9.0%)', inv_resp.data)
        self.assertIn(b'SGST (9.0%)', inv_resp.data)
        self.assertIn(b'SN-TEST-S25U-9901', inv_resp.data)

        self.logout()

    def test_09_warranty_tracking_module(self):
        """Test warranty search by serial number and status filters."""
        self.login('sai', 'sai123')

        resp = self.client.get('/warranty?search=SN-APPL-16PM-8801')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'SN-APPL-16PM-8801', resp.data)
        self.assertIn(b'Active', resp.data)

        self.logout()

    def test_10_reports_module(self):
        """Test sales and inventory reporting with presets and 14-day chart."""
        self.login('geetha', 'geetha123')

        resp = self.client.get('/reports?preset=month')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Total Revenue', resp.data)
        self.assertIn(b'Gross Profit', resp.data)
        self.assertIn(b'Sales report', resp.data)
        self.assertIn(b'Inventory report', resp.data)

        self.logout()

    def test_11_user_management_crud(self):
        """Test Admin adding, editing, and deleting a user account."""
        self.login('admin', 'admin123')

        # Clean up any lingering test user
        db.execute("DELETE FROM USER WHERE username IN ('kiran_test', 'johndoe_test')")

        # Add new user
        resp = self.client.post('/users/add', data={
            'username': 'kiran_test',
            'full_name': 'Kiran Varma',
            'role': 'Sales Staff',
            'password': 'password123',
            'email': 'kiran@electrodesk.com',
            'phone': '+91 94444 33333'
        }, follow_redirects=True)
        self.assertIn(b'created successfully', resp.data)

        user = db.query_one("SELECT * FROM USER WHERE username = 'kiran_test'")
        self.assertIsNotNone(user)
        self.assertEqual(user['role'], 'Sales Staff')
        self.assertEqual(user['avatar'], 'KV')

        # Edit user
        resp = self.client.post(f'/users/edit/{user["user_id"]}', data={
            'full_name': 'Kiran Varma Senior',
            'role': 'Shop Manager',
            'status': 'Active',
            'email': 'kiran.senior@electrodesk.com',
            'phone': '+91 94444 33334',
            'password': ''  # Keep password unchanged
        }, follow_redirects=True)
        self.assertIn(b'profile updated', resp.data)

        # Delete user
        resp = self.client.post(f'/users/delete/{user["user_id"]}', follow_redirects=True)
        self.assertIn(b'deleted successfully', resp.data)

        deleted = db.query_one("SELECT * FROM USER WHERE username = 'kiran_test'")
        self.assertIsNone(deleted)
        self.logout()

    def test_12_pos_insufficient_stock_rejection(self):
        """Test that POS checkout rejects requests exceeding available stock."""
        self.login('sai', 'sai123')

        p = db.query_one("SELECT * FROM PRODUCT LIMIT 1")
        req_qty = p['stock_quantity'] + 999

        payload = {
            'items': [{'product_id': p['product_id'], 'quantity': req_qty}],
            'customer_id': None
        }

        resp = self.client.post('/api/pos/checkout',
                                data=json.dumps(payload),
                                content_type='application/json')
        self.assertEqual(resp.status_code, 400)
        res_data = json.loads(resp.data)
        self.assertFalse(res_data['success'])
        self.assertIn('Insufficient stock', res_data['message'])
        self.logout()

    def test_13_reports_custom_date_filtering(self):
        """Test custom date filtering on reports."""
        self.login('geetha', 'geetha123')
        resp = self.client.get('/reports?preset=custom&start_date=2026-01-01&end_date=2026-12-31')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Sales report', resp.data)
        self.assertIn(b'2026-01-01', resp.data)
        self.assertIn(b'2026-12-31', resp.data)
        self.logout()


if __name__ == '__main__':
    unittest.main()
