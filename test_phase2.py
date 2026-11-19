"""
Comprehensive Unit Tests for Electrodesk Phase 2 Features (Steps 1 through 6)
"""

import unittest
import os
import datetime
import json
import config
import init_db
from app import app, db, get_app_today, get_inventory_derived_totals


class ElectrodeskPhase2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        # Re-initialize clean test database
        if os.path.exists(config.SQLITE_DB_PATH):
            os.remove(config.SQLITE_DB_PATH)
        init_db.init_sqlite_db()

    def setUp(self):
        self.client = app.test_client()

    def login(self, username, password=None):
        if not password:
            pw_map = {
                'admin': 'admin123',
                'geetha': 'geetha123',
                'sai': 'sai123',
                'suresh': 'suresh123'
            }
            password = pw_map.get(username.lower(), 'admin123')
        return self.client.post('/login', data={'username': username, 'password': password}, follow_redirects=True)

    def logout(self):
        return self.client.get('/logout', follow_redirects=True)

    # -------------------------------------------------------------
    # 1. DERIVED TOTALS CONSISTENCY ACROSS ALL PAGES
    # -------------------------------------------------------------
    def test_01_derived_inventory_totals(self):
        """Derived totals must match identically across Dashboard, Categories, Stock & Reports."""
        totals = get_inventory_derived_totals()
        self.assertGreater(totals['total_units'], 0)
        self.assertGreater(totals['total_skus'], 25)
        self.assertGreater(totals['total_cost_value'], 0)
        self.assertGreater(totals['total_retail_value'], totals['total_cost_value'])

        # Verify against direct PRODUCT queries
        prod_units = db.query_one("SELECT SUM(stock_quantity) as s FROM PRODUCT")['s']
        prod_skus = db.query_one("SELECT COUNT(*) as c FROM PRODUCT")['c']
        self.assertEqual(totals['total_units'], prod_units)
        self.assertEqual(totals['total_skus'], prod_skus)

    # -------------------------------------------------------------
    # 2. WARRANTY STATUS COHORTS AND SERIAL LOOKUP
    # -------------------------------------------------------------
    def test_02_warranty_cohorts_and_counts(self):
        """Warranty page shows exact status groups: >=12 active, 6 expiring, >=6 expired, 3 open claims."""
        self.login('admin')
        res = self.client.get('/warranty')
        self.assertEqual(res.status_code, 200)

        today = get_app_today()
        today_str = today.strftime('%Y-%m-%d')
        exp_30 = (today + datetime.timedelta(days=30)).strftime('%Y-%m-%d')

        # Expiring soon within 30 days
        expiring = db.query("""
            SELECT * FROM SALE_ITEM
            WHERE warranty_expiry_date >= %s AND warranty_expiry_date <= %s
        """, (today_str, exp_30))
        self.assertEqual(len(expiring), 6, "Must have exactly 6 warranties expiring within 30 days")

        # Expired warranties
        expired = db.query("SELECT * FROM SALE_ITEM WHERE warranty_expiry_date < %s", (today_str,))
        self.assertGreaterEqual(len(expired), 6, "Must have >=6 expired warranties")

        # Active warranties
        active = db.query("SELECT * FROM SALE_ITEM WHERE warranty_expiry_date > %s", (exp_30,))
        self.assertGreaterEqual(len(active), 12, "Must have >=12 active warranties")

        # Open claims
        claims = db.query("SELECT * FROM WARRANTY_CLAIM WHERE status = 'Open'")
        self.assertEqual(len(claims), 3, "Must have exactly 3 open warranty claims")
        self.logout()

    # -------------------------------------------------------------
    # 3. POS SALE, STOCK REDUCTION & WARRANTY CREATION
    # -------------------------------------------------------------
    def test_03_pos_sale_checkout_reduces_stock_creates_warranty(self):
        """Checkout reduces stock, creates invoice, records serial, and creates warranty."""
        self.login('sai')  # Sales Staff
        # Pick boAt Airdopes (accessories: no serial strictly required)
        prod = db.query_one("SELECT * FROM PRODUCT WHERE product_code = 'ELEC-AUD-001'")
        self.assertIsNotNone(prod)
        init_stock = prod['stock_quantity']

        payload = {
            'customer_id': 1,
            'payment_method': 'UPI',
            'discount_amount': 0,
            'items': [
                {
                    'product_id': prod['product_id'],
                    'quantity': 2,
                    'serial_number': ''
                }
            ]
        }
        res = self.client.post('/pos/checkout', data=json.dumps(payload), content_type='application/json')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertTrue(data['invoice_number'].startswith('INV-'))

        # Verify stock reduced by 2
        updated_prod = db.query_one("SELECT * FROM PRODUCT WHERE product_code = 'ELEC-AUD-001'")
        self.assertEqual(updated_prod['stock_quantity'], init_stock - 2)

        # Verify stock movement recorded
        movement = db.query_one("""
            SELECT * FROM STOCK_MOVEMENT 
            WHERE product_id = %s ORDER BY movement_id DESC LIMIT 1
        """, (prod['product_id'],))
        self.assertEqual(movement['movement_type'], 'OUT')
        self.assertEqual(movement['quantity'], 2)
        self.logout()

    # -------------------------------------------------------------
    # 4. SERIAL UNIQUENESS & MANDATORY CHECK
    # -------------------------------------------------------------
    def test_04_serial_validation(self):
        """High-value devices require serial number; duplicate serials are rejected."""
        self.login('admin')
        phone = db.query_one("SELECT * FROM PRODUCT WHERE product_code = 'ELEC-SMP-001'")
        self.assertIsNotNone(phone)
        
        # Test missing serial on phone
        payload_missing = {
            'payment_method': 'Cash',
            'items': [{'product_id': phone['product_id'], 'quantity': 1, 'serial_number': ''}]
        }
        res = self.client.post('/pos/checkout', data=json.dumps(payload_missing), content_type='application/json')
        data = res.get_json()
        self.assertFalse(data['success'])
        self.assertIn('strictly required', data['message'])

        # Test duplicate existing serial
        existing_serial = db.query_one("SELECT serial_number FROM SALE_ITEM WHERE serial_number IS NOT NULL AND serial_number != '' LIMIT 1")['serial_number']
        payload_dup = {
            'payment_method': 'Cash',
            'items': [{'product_id': phone['product_id'], 'quantity': 1, 'serial_number': existing_serial}]
        }
        res2 = self.client.post('/pos/checkout', data=json.dumps(payload_dup), content_type='application/json')
        data2 = res2.get_json()
        self.assertFalse(data2['success'])
        self.assertIn('already exists', data2['message'])
        self.logout()

    # -------------------------------------------------------------
    # 5. STAFF RBAC ENFORCEMENT
    # -------------------------------------------------------------
    def test_05_staff_restricted_from_admin_areas(self):
        """Staff (Sai) cannot access audit log, settings, or delete actions."""
        self.login('sai')
        # Audit log restricted
        res_audit = self.client.get('/audit-log', follow_redirects=False)
        self.assertEqual(res_audit.status_code, 302)

        # Settings restricted
        res_set = self.client.get('/settings', follow_redirects=False)
        self.assertEqual(res_set.status_code, 302)

        # Product delete restricted
        res_del = self.client.post('/products/delete/1', follow_redirects=False)
        self.assertEqual(res_del.status_code, 302)
        self.logout()

    # -------------------------------------------------------------
    # 6. RETURNS & CREDIT NOTES (STOCK REVERSAL)
    # -------------------------------------------------------------
    def test_06_returns_credit_note_reverses_stock(self):
        """Processing return creates CN-2026-XXXX and restores inventory stock."""
        self.login('admin')
        sale = db.query_one("SELECT * FROM SALE ORDER BY sale_id ASC LIMIT 1")
        item = db.query_one("SELECT * FROM SALE_ITEM WHERE sale_id = %s LIMIT 1", (sale['sale_id'],))
        prod_before = db.query_one("SELECT * FROM PRODUCT WHERE product_id = %s", (item['product_id'],))

        res = self.client.post('/returns/create', data={
            'invoice_number': sale['invoice_number'],
            'refund_amount': 500.0,
            'reason': 'Test unit return'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        # Verify Credit note created
        cn = db.query_one("SELECT * FROM CREDIT_NOTE WHERE sale_id = %s", (sale['sale_id'],))
        self.assertIsNotNone(cn)
        self.assertTrue(cn['credit_note_number'].startswith('CN-'))

        # Verify stock restored
        prod_after = db.query_one("SELECT * FROM PRODUCT WHERE product_id = %s", (item['product_id'],))
        self.assertGreater(prod_after['stock_quantity'], prod_before['stock_quantity'])
        self.logout()

    # -------------------------------------------------------------
    # 7. CUSTOMER DUES & PARTIAL PAYMENTS
    # -------------------------------------------------------------
    def test_07_customer_dues_payment(self):
        """Recording payment on due invoice reduces balance and updates ledger."""
        self.login('admin')
        due_sale = db.query_one("SELECT * FROM SALE WHERE balance_due > 0 LIMIT 1")
        self.assertIsNotNone(due_sale)
        initial_balance = due_sale['balance_due']

        pay_amount = min(1000.0, initial_balance)
        res = self.client.post('/customer-dues/pay', data={
            'sale_id': due_sale['sale_id'],
            'amount': pay_amount,
            'payment_method': 'UPI',
            'notes': 'Test dues payment'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        updated_sale = db.query_one("SELECT * FROM SALE WHERE sale_id = %s", (due_sale['sale_id'],))
        self.assertEqual(round(updated_sale['balance_due'], 2), round(initial_balance - pay_amount, 2))
        self.logout()

    # -------------------------------------------------------------
    # 8. QUOTATIONS 1-CLICK CONVERSION TO INVOICE
    # -------------------------------------------------------------
    def test_08_quotation_convert_to_invoice(self):
        """Converting a quotation generates a sale invoice and updates quotation status."""
        self.login('admin')
        quote = db.query_one("SELECT * FROM QUOTATION WHERE status != 'Converted' LIMIT 1")
        self.assertIsNotNone(quote)

        res = self.client.post(f'/quotations/convert/{quote["quote_id"]}', follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        updated_quote = db.query_one("SELECT * FROM QUOTATION WHERE quote_id = %s", (quote['quote_id'],))
        self.assertEqual(updated_quote['status'], 'Converted')
        self.logout()

    # -------------------------------------------------------------
    # 9. BACKUP -> RESET -> RESTORE DATA INTEGRITY
    # -------------------------------------------------------------
    def test_09_backup_and_reset_demo(self):
        """JSON backup can be generated, demo data reset, and restored cleanly."""
        self.login('admin')
        # Generate backup
        res_backup = self.client.get('/settings/backup-json')
        self.assertEqual(res_backup.status_code, 200)
        backup_data = json.loads(res_backup.data)
        self.assertIn('tables', backup_data)
        self.assertIn('PRODUCT', backup_data['tables'])
        initial_prod_count = len(backup_data['tables']['PRODUCT'])

        # Reset Demo Data
        res_reset = self.client.post('/settings/reset-demo', follow_redirects=True)
        self.assertEqual(res_reset.status_code, 200)

        # Product count matches seed targets
        curr_prod_count = db.query_one("SELECT COUNT(*) as c FROM PRODUCT")['c']
        self.assertEqual(curr_prod_count, initial_prod_count)
        self.logout()

    # -------------------------------------------------------------
    # 10. PROFIT & LOSS: DERIVED TOTALS, BEST-SELLERS & CATEGORY MARGINS
    # -------------------------------------------------------------
    def test_10_profit_and_loss_derived_totals_and_margins(self):
        """P&L page verifies Gross Revenue, COGS, Gross Profit, Expenses, Net Profit and Category Margins."""
        self.login('admin')
        res = self.client.get('/reports/profit-loss')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Profit & Loss Financial Statement', res.data)
        self.assertIn(b'Top Best-Selling Products', res.data)
        self.assertIn(b'Slow-Moving Inventory Alert', res.data)
        self.assertIn(b'Profit Margin per Category', res.data)

        # Database verification of derived numbers
        rev_row = db.query_one("SELECT COALESCE(SUM(grand_total), 0.0) as rev FROM SALE")
        expected_rev = rev_row['rev'] if rev_row else 0.0

        cogs_row = db.query_one("""
            SELECT COALESCE(SUM(si.quantity * p.cost_price), 0.0) as cogs 
            FROM SALE_ITEM si 
            JOIN PRODUCT p ON si.product_id = p.product_id
        """)
        expected_cogs = cogs_row['cogs'] if cogs_row else 0.0

        ref_row = db.query_one("SELECT COALESCE(SUM(refund_amount), 0.0) as ref FROM CREDIT_NOTE")
        expected_refunds = ref_row['ref'] if ref_row else 0.0

        exp_row = db.query_one("SELECT COALESCE(SUM(amount), 0.0) as exp FROM EXPENSE")
        expected_exp = exp_row['exp'] if exp_row else 0.0

        net_rev = expected_rev - expected_refunds
        expected_gross_profit = net_rev - expected_cogs
        expected_net_profit = expected_gross_profit - expected_exp

        # Verify values in database match expectations
        self.assertGreater(expected_rev, 0)
        self.assertGreater(expected_cogs, 0)
        self.assertGreater(expected_exp, 0)
        self.assertEqual(round(expected_gross_profit - (net_rev - expected_cogs), 2), 0)
        self.assertEqual(round(expected_net_profit - (expected_gross_profit - expected_exp), 2), 0)

        # Verify category margins list
        cat_margins = db.query("""
            SELECT c.category_name, 
                   COALESCE(SUM(si.total_price), 0.0) as rev,
                   COALESCE(SUM(si.quantity * p.cost_price), 0.0) as cogs
            FROM CATEGORY c
            LEFT JOIN PRODUCT p ON c.category_id = p.category_id
            LEFT JOIN SALE_ITEM si ON p.product_id = si.product_id
            GROUP BY c.category_id, c.category_name
        """)
        self.assertGreaterEqual(len(cat_margins), 6)
        self.logout()

    # -------------------------------------------------------------
    # 11. EXPENSES CRUD: ADD, EDIT, DELETE & FEEDING NET PROFIT
    # -------------------------------------------------------------
    def test_11_expenses_crud_feeds_net_profit(self):
        """Adding, editing and deleting expenses updates operational expenses and feeds P&L net profit."""
        self.login('admin')

        # Baseline expenses
        init_exp = db.query_one("SELECT COALESCE(SUM(amount), 0.0) as exp FROM EXPENSE")['exp']

        # 1. Add new expense (e.g. Electricity bill)
        res_add = self.client.post('/expenses/add', data={
            'category': 'Electricity',
            'amount': 12500.0,
            'expense_date': '2026-11-19',
            'payment_method': 'UPI',
            'notes': 'Supplementary showroom lighting bill'
        }, follow_redirects=True)
        self.assertEqual(res_add.status_code, 200)
        self.assertIn(b'recorded successfully', res_add.data)

        # Verify database updated
        new_exp_row = db.query_one("SELECT * FROM EXPENSE WHERE notes = 'Supplementary showroom lighting bill'")
        self.assertIsNotNone(new_exp_row)
        self.assertEqual(new_exp_row['amount'], 12500.0)

        updated_total = db.query_one("SELECT COALESCE(SUM(amount), 0.0) as exp FROM EXPENSE")['exp']
        self.assertEqual(round(updated_total - init_exp, 2), 12500.0)

        # 2. Edit expense (e.g. adjust rent or salary amount)
        res_edit = self.client.post(f'/expenses/edit/{new_exp_row["expense_id"]}', data={
            'category': 'Electricity',
            'amount': 15000.0,
            'expense_date': '2026-11-19',
            'payment_method': 'Bank Transfer',
            'notes': 'Updated showroom lighting bill'
        }, follow_redirects=True)
        self.assertEqual(res_edit.status_code, 200)
        self.assertIn(b'updated successfully', res_edit.data)

        edited_row = db.query_one("SELECT * FROM EXPENSE WHERE expense_id = %s", (new_exp_row['expense_id'],))
        self.assertEqual(edited_row['amount'], 15000.0)
        self.assertEqual(edited_row['payment_method'], 'Bank Transfer')

        # 3. Delete expense
        res_del = self.client.post(f'/expenses/delete/{new_exp_row["expense_id"]}', follow_redirects=True)
        self.assertEqual(res_del.status_code, 200)
        self.assertIn(b'deleted successfully', res_del.data)

        restored_total = db.query_one("SELECT COALESCE(SUM(amount), 0.0) as exp FROM EXPENSE")['exp']
        self.assertEqual(round(restored_total, 2), round(init_exp, 2))

        # 4. RBAC: Sales Staff cannot add expenses
        self.logout()
        self.login('sai')
        res_staff = self.client.post('/expenses/add', data={
            'category': 'Other',
            'amount': 1000.0
        }, follow_redirects=False)
        self.assertEqual(res_staff.status_code, 302)
        self.logout()

    # -------------------------------------------------------------
    # 12. MONTHLY GST SUMMARY AND CSV EXPORT
    # -------------------------------------------------------------
    def test_12_monthly_gst_summary_and_csv_export(self):
        """Monthly GST summary calculates statutory taxes and exports valid CSV."""
        self.login('admin')
        res_gst = self.client.get('/reports/gst')
        self.assertEqual(res_gst.status_code, 200)
        self.assertIn(b'Monthly GST Filing', res_gst.data)
        self.assertIn(b'CGST 9%', res_gst.data)
        self.assertIn(b'SGST 9%', res_gst.data)
        self.assertIn(b'Export GST CSV', res_gst.data)

        # Database verification
        gst_totals = db.query_one("""
            SELECT 
                COALESCE(SUM(subtotal), 0.0) as taxable,
                COALESCE(SUM(cgst_amount), 0.0) as cgst,
                COALESCE(SUM(sgst_amount), 0.0) as sgst,
                COALESCE(SUM(tax_amount), 0.0) as tax,
                COALESCE(SUM(grand_total), 0.0) as turnover
            FROM SALE
        """)
        self.assertGreater(gst_totals['taxable'], 0)
        self.assertEqual(round(gst_totals['cgst'] + gst_totals['sgst'], 2), round(gst_totals['tax'], 2))

        # Test CSV export
        res_csv = self.client.get('/reports/gst/export.csv')
        self.assertEqual(res_csv.status_code, 200)
        self.assertIn('text/csv', res_csv.content_type)
        self.assertIn('electrodesk_gst_summary.csv', res_csv.headers.get('Content-Disposition', ''))

        csv_text = res_csv.data.decode('utf-8')
        self.assertIn('Month', csv_text)
        self.assertIn('Taxable Value', csv_text)
        self.assertIn('CGST', csv_text)
        self.assertIn('SGST', csv_text)
        self.assertIn('Total GST', csv_text)
        self.assertIn('2026-11', csv_text)
        self.logout()

    # -------------------------------------------------------------
    # 13. DAILY CLOSING REPORT: CASH/UPI/CARD & DIFFERENCE FLAG
    # -------------------------------------------------------------
    def test_13_daily_closing_report_and_difference_flag(self):
        """Daily closing verifies cash, UPI, card totals vs expected and calculates difference flag."""
        self.login('geetha')
        today = get_app_today()
        today_str = today.strftime('%Y-%m-%d')

        # 1. View Daily Closing for today
        res = self.client.get(f'/reports/daily-closing?date={today_str}')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Daily Register Closing', res.data)
        self.assertIn(b'Expected Cash Sales', res.data)
        self.assertIn(b'Expected UPI Sales', res.data)
        self.assertIn(b'Expected Card / POS', res.data)

        # Calculate expected numbers from database
        sales_today = db.query("SELECT payment_method, payment_status, grand_total, amount_paid FROM SALE WHERE DATE(sale_date) = %s", (today_str,))
        exp_cash = sum(s['amount_paid'] if s['payment_status'] == 'Partial' else s['grand_total'] for s in sales_today if s['payment_method'] == 'Cash' or s['payment_method'] == 'Partial')
        exp_upi = sum(s['grand_total'] for s in sales_today if s['payment_method'] == 'UPI')
        exp_card = sum(s['grand_total'] for s in sales_today if s['payment_method'] == 'Card')
        exp_total = exp_cash + exp_upi + exp_card

        # 2. Submit Balanced Closing (actual == expected)
        res_post_balanced = self.client.post('/reports/daily-closing', data={
            'closing_date': today_str,
            'expected_cash': exp_cash,
            'actual_cash': exp_cash,
            'expected_upi': exp_upi,
            'expected_card': exp_card,
            'expected_total': exp_total,
            'notes': 'End of day register balancing test'
        }, follow_redirects=True)
        self.assertEqual(res_post_balanced.status_code, 200)
        self.assertIn(b'finalized', res_post_balanced.data)

        closing_record = db.query_one("SELECT * FROM DAILY_CLOSING WHERE closing_date = %s", (today_str,))
        self.assertIsNotNone(closing_record)
        self.assertEqual(closing_record['cash_difference'], 0.0)

        # 3. Submit Discrepancy Closing (shortage of ₹500)
        res_post_short = self.client.post('/reports/daily-closing', data={
            'closing_date': today_str,
            'expected_cash': exp_cash,
            'actual_cash': exp_cash - 500.0,
            'expected_upi': exp_upi,
            'expected_card': exp_card,
            'expected_total': exp_total,
            'notes': 'Cash shortage test'
        }, follow_redirects=True)
        self.assertEqual(res_post_short.status_code, 200)
        self.assertIn(b'Cash Shortage', res_post_short.data)

        updated_closing = db.query_one("SELECT * FROM DAILY_CLOSING WHERE closing_date = %s", (today_str,))
        self.assertEqual(round(updated_closing['cash_difference'], 2), -500.0)
        self.logout()


if __name__ == '__main__':
    unittest.main()
