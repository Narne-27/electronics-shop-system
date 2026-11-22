"""
Electrodesk regression tests.  Run:  python test_app.py
Uses a throw-away SQLite file, never your real electrodesk.db.
"""
import io
import os
import json
import tempfile
import unittest
import datetime
from unittest import mock

import config

_TMP_DIR = tempfile.mkdtemp(prefix='electrodesk_test_')
config.SQLITE_DB_PATH = os.path.join(_TMP_DIR, 'test.db')
config.DB_TYPE = 'sqlite'

import db          # noqa: E402
import init_db     # noqa: E402
import app as app_module   # noqa: E402

flask_app = app_module.app
flask_app.config['TESTING'] = True


def fresh_db():
    if os.path.exists(config.SQLITE_DB_PATH):
        os.remove(config.SQLITE_DB_PATH)
    init_db.init_sqlite_db()


def login(username, password):
    c = flask_app.test_client()
    r = c.post('/login', data={'username': username, 'password': password})
    assert r.status_code == 302, f'login failed for {username}'
    return c


def simple_product(min_stock=6):
    """A product that does not require a serial number."""
    return db.query_one("""
        SELECT p.* FROM PRODUCT p JOIN CATEGORY c ON p.category_id = c.category_id
        WHERE LOWER(c.category_name) NOT LIKE '%phone%' AND LOWER(c.category_name) NOT LIKE '%laptop%'
          AND LOWER(c.category_name) NOT LIKE '%tv%' AND LOWER(c.category_name) NOT LIKE '%display%'
          AND LOWER(c.category_name) NOT LIKE '%tablet%' AND p.stock_quantity >= %s
        ORDER BY p.product_id LIMIT 1
    """, (min_stock,))


def stock_of(pid):
    return db.query_one("SELECT stock_quantity AS s FROM PRODUCT WHERE product_id = %s", (pid,))['s']


def sale_count():
    return db.query_one("SELECT COUNT(*) AS c FROM SALE")['c']


class Base(unittest.TestCase):
    def setUp(self):
        fresh_db()
        self.sai = login('sai', 'sai123')
        self.admin = login('admin', 'admin123')
        self.owner = login('suresh', 'suresh123')
        self.prod = simple_product()
        self.pid = self.prod['product_id']

    def checkout(self, client, **extra):
        body = {'items': [{'product_id': self.pid, 'quantity': extra.pop('qty', 1)}], 'payment_method': 'Cash'}
        body.update(extra)
        r = client.post('/api/pos/checkout', json=body)
        return r.status_code, r.get_json()


class TestSecurity(Base):
    def test_open_redirect_blocked(self):
        for evil in ('https://evil.example.com', '//evil.example.com', '/\\evil.example.com', 'javascript:alert(1)'):
            c = flask_app.test_client()
            r = c.post('/login?next=' + evil, data={'username': 'sai', 'password': 'sai123'})
            self.assertNotIn('evil', r.headers['Location'], evil)
        c = flask_app.test_client()
        r = c.post('/login?next=/dashboard', data={'username': 'sai', 'password': 'sai123'})
        self.assertTrue(r.headers['Location'].endswith('/dashboard'))

    def test_cross_site_post_blocked(self):
        r = self.admin.post('/inventory/adjust', data={}, headers={'Origin': 'https://evil.example.com'})
        self.assertEqual(r.status_code, 403)

    def test_cost_price_not_sent_to_sales_staff(self):
        self.assertNotIn('"cost_price"', self.sai.get('/pos').get_data(as_text=True))
        self.assertIn('"cost_price"', self.admin.get('/pos').get_data(as_text=True))

    def test_deactivated_user_loses_access_immediately(self):
        db.execute("UPDATE USER SET status = 'Inactive' WHERE username = 'sai'")
        r = self.sai.get('/pos')
        self.assertEqual(r.status_code, 302)
        self.assertIn('/login', r.headers['Location'])

    def test_user_management_rules(self):
        a = self.admin
        a.post('/users/add', data={'username': 'blank', 'full_name': 'Blank', 'role': 'Sales Staff', 'password': ''})
        self.assertIsNone(db.query_one("SELECT 1 FROM USER WHERE username = 'blank'"))
        a.post('/users/add', data={'username': 'weird', 'full_name': 'Weird', 'role': 'banana', 'password': 'secret1'})
        self.assertIsNone(db.query_one("SELECT 1 FROM USER WHERE username = 'weird'"))
        a.post('/users/add', data={'username': 'boss2', 'full_name': 'Boss', 'role': 'Shop Owner', 'password': 'secret1'})
        self.assertIsNone(db.query_one("SELECT 1 FROM USER WHERE username = 'boss2'"), 'admin must not create owners')
        a.post('/users/add', data={'username': 'newstaff', 'full_name': 'New Staff', 'role': 'Sales Staff', 'password': 'secret1'})
        self.assertIsNotNone(db.query_one("SELECT 1 FROM USER WHERE username = 'newstaff'"))
        me = db.query_one("SELECT user_id FROM USER WHERE username = 'admin'")['user_id']
        a.post(f'/users/edit/{me}', data={'full_name': 'Ram', 'role': 'Sales Staff', 'status': 'Inactive'})
        row = db.query_one("SELECT role, status FROM USER WHERE user_id = %s", (me,))
        self.assertEqual((row['role'], row['status']), ('System Administrator', 'Active'))
        owner = db.query_one("SELECT user_id FROM USER WHERE username = 'suresh'")['user_id']
        a.post(f'/users/edit/{owner}', data={'full_name': 'Suresh', 'role': 'Shop Owner', 'status': 'Active', 'password': 'hijack1'})
        c = flask_app.test_client()
        r = c.post('/login', data={'username': 'suresh', 'password': 'hijack1'}, follow_redirects=False)
        self.assertEqual(r.status_code, 200, 'admin must not be able to reset the owner password')   # 200 = login page re-shown


class TestCheckout(Base):
    def test_normal_sale_server_side_totals(self):
        before = stock_of(self.pid)
        status, body = self.checkout(self.sai, qty=2, tax_rate=0)      # client tax_rate must be ignored
        self.assertEqual(status, 200, body)
        sale = db.query_one("SELECT * FROM SALE WHERE invoice_number = %s", (body['invoice_number'],))
        expected_tax = round(self.prod['selling_price'] * 2 * (self.prod['tax_rate'] / 100), 2)
        self.assertAlmostEqual(sale['tax_amount'], expected_tax, places=2)
        self.assertAlmostEqual(sale['grand_total'], sale['subtotal'] + expected_tax, places=2)
        self.assertEqual(stock_of(self.pid), before - 2)
        self.assertEqual(db.query_one("SELECT COUNT(*) AS c FROM STOCK_MOVEMENT WHERE reference_id = %s", (body['invoice_number'],))['c'], 1)

    def test_tampered_values_rejected(self):
        before, n = stock_of(self.pid), sale_count()
        price = self.prod['selling_price']
        self.assertEqual(self.checkout(self.sai, exchange_value=price * 10)[0], 403)   # free goods via exchange
        self.assertEqual(self.checkout(self.sai, discount_amount=-5000)[0], 400)       # negative discount
        self.assertEqual(self.checkout(self.sai, qty=-3)[0], 400)                      # negative quantity
        self.assertEqual(self.checkout(self.sai, qty=0)[0], 400)
        self.assertEqual(self.checkout(self.sai, discount_amount='abc')[0], 400)       # no 500 on junk
        self.assertEqual(self.checkout(self.sai, emi_months=999)[0], 400)
        self.assertEqual((stock_of(self.pid), sale_count()), (before, n))

    def test_discount_over_10_percent_needs_owner(self):
        price = self.prod['selling_price']
        big = round(price * 0.2, 2)
        self.assertEqual(self.checkout(self.sai, discount_amount=big)[0], 403)
        self.assertEqual(self.checkout(self.sai, discount_amount=big, owner_pin='9999')[0], 200)
        self.assertEqual(self.checkout(self.owner, discount_amount=big)[0], 200)
        # a discount can never exceed the bill
        status, body = self.checkout(self.owner, discount_amount=price * 50)
        self.assertEqual(status, 200)
        self.assertEqual(db.query_one("SELECT grand_total AS g FROM SALE WHERE invoice_number = %s", (body['invoice_number'],))['g'], 0.0)

    def test_cannot_oversell(self):
        stock = stock_of(self.pid)
        self.assertEqual(self.checkout(self.sai, qty=stock + 1)[0], 400)
        two_lines = {'items': [{'product_id': self.pid, 'quantity': stock}, {'product_id': self.pid, 'quantity': 1}], 'payment_method': 'Cash'}
        self.assertEqual(self.sai.post('/api/pos/checkout', json=two_lines).status_code, 400)
        self.assertEqual(stock_of(self.pid), stock)

    def test_checkout_is_atomic(self):
        before, n = stock_of(self.pid), sale_count()
        real = db.Transaction.execute

        def boom(self_tx, sql, params=()):
            if 'STOCK_MOVEMENT' in sql and 'Customer Sale' in sql:
                raise RuntimeError('simulated crash mid-checkout')
            return real(self_tx, sql, params)

        with mock.patch.object(db.Transaction, 'execute', boom):
            status, _ = self.checkout(self.sai)
        self.assertEqual(status, 500)
        self.assertEqual((stock_of(self.pid), sale_count()), (before, n), 'partial sale was left behind')

    def test_credit_sale_needs_customer_and_creates_dues(self):
        self.assertEqual(self.checkout(self.sai, payment_method='Pay Later')[0], 400)
        cust = db.query_one("SELECT customer_id FROM CUSTOMER LIMIT 1")['customer_id']
        status, body = self.checkout(self.sai, payment_method='Pay Later', customer_id=cust)
        self.assertEqual(status, 200)
        sale = db.query_one("SELECT * FROM SALE WHERE invoice_number = %s", (body['invoice_number'],))
        self.assertEqual((sale['payment_status'], sale['amount_paid']), ('Pending', 0.0))
        self.assertAlmostEqual(sale['balance_due'], sale['grand_total'], places=2)

    def test_warranty_expiry_is_calendar_accurate(self):
        _, body = self.checkout(self.sai)
        row = db.query_one("""SELECT si.warranty_months m, si.warranty_expiry_date e FROM SALE_ITEM si
                              JOIN SALE s ON s.sale_id = si.sale_id WHERE s.invoice_number = %s""", (body['invoice_number'],))
        today = app_module.get_app_today()
        self.assertEqual(row['e'], app_module.add_months(today, row['m']).strftime('%Y-%m-%d'))
        self.assertEqual(app_module.add_months(datetime.date(2026, 11, 20), 12), datetime.date(2027, 11, 20))
        self.assertEqual(app_module.add_months(datetime.date(2026, 1, 31), 1), datetime.date(2026, 2, 28))

    def test_emi_rates_from_settings_are_used(self):
        self.admin.post('/settings', data={'action': 'update_settings', 'app_today_mode': 'auto',
                                           'emi_rate_3m': '0', 'emi_rate_6m': '10', 'emi_rate_9m': '14'})
        _, body = self.checkout(self.sai, emi_months=6)
        self.assertEqual(db.query_one("SELECT emi_interest_rate r FROM SALE WHERE invoice_number = %s", (body['invoice_number'],))['r'], 10.0)

    def test_coupon_is_validated_server_side(self):
        self.assertEqual(self.checkout(self.sai, coupon_code='NOPE')[0], 400)
        status, body = self.checkout(self.sai, coupon_code='WELCOME5')
        self.assertEqual(status, 200)
        sale = db.query_one("SELECT * FROM SALE WHERE invoice_number = %s", (body['invoice_number'],))
        self.assertAlmostEqual(sale['discount_amount'], round(sale['subtotal'] * 0.05, 2), places=2)


class TestOperations(Base):
    def _sale(self, **kw):
        status, body = self.checkout(self.sai, **kw)
        self.assertEqual(status, 200, body)
        return db.query_one("SELECT * FROM SALE WHERE invoice_number = %s", (body['invoice_number'],))

    def test_return_only_once(self):
        sale = self._sale(qty=2)
        after_sale = stock_of(self.pid)
        for _ in range(2):
            self.admin.post('/returns/create', data={'invoice_number': sale['invoice_number'], 'refund_amount': '', 'reason': 'x'})
        self.assertEqual(db.query_one("SELECT COUNT(*) c FROM CREDIT_NOTE WHERE sale_id = %s", (sale['sale_id'],))['c'], 1)
        self.assertEqual(stock_of(self.pid), after_sale + 2)

    def test_refund_cannot_exceed_amount_paid(self):
        sale = self._sale()
        self.admin.post('/returns/create', data={'invoice_number': sale['invoice_number'], 'refund_amount': '999999', 'reason': 'x'})
        self.assertEqual(db.query_one("SELECT COUNT(*) c FROM CREDIT_NOTE")['c'], 0)

    def test_dues_payment_cannot_overpay(self):
        cust = db.query_one("SELECT customer_id FROM CUSTOMER LIMIT 1")['customer_id']
        sale = self._sale(payment_method='Pay Later', customer_id=cust)
        due = sale['balance_due']
        self.sai.post('/customer-dues/pay', data={'sale_id': sale['sale_id'], 'amount': str(due + 500), 'payment_method': 'Cash'})
        self.assertEqual(db.query_one("SELECT balance_due b FROM SALE WHERE sale_id = %s", (sale['sale_id'],))['b'], due)
        self.sai.post('/customer-dues/pay', data={'sale_id': sale['sale_id'], 'amount': str(due), 'payment_method': 'Cash'})
        row = db.query_one("SELECT balance_due b, payment_status s FROM SALE WHERE sale_id = %s", (sale['sale_id'],))
        self.assertEqual((row['b'], row['s']), (0.0, 'Paid'))

    def test_inventory_can_be_set_to_zero(self):
        self.admin.post('/inventory/adjust', data={'product_id': self.pid, 'type': 'set', 'quantity': '0'})
        self.assertEqual(stock_of(self.pid), 0)
        self.admin.post('/inventory/adjust', data={'product_id': self.pid, 'type': 'add', 'quantity': '-4'})
        self.assertEqual(stock_of(self.pid), 0)

    def test_product_edit_stock_change_is_audited(self):
        p = db.query_one("SELECT * FROM PRODUCT WHERE product_id = %s", (self.pid,))
        form = {'product_code': p['product_code'], 'product_name': p['product_name'], 'category_id': p['category_id'],
                'brand': p['brand'], 'cost_price': p['cost_price'], 'selling_price': p['selling_price'],
                'stock_quantity': p['stock_quantity'] + 7, 'reorder_level': p['reorder_level'], 'warranty_months': p['warranty_months']}
        self.admin.post(f'/products/edit/{self.pid}', data=form)
        self.assertEqual(db.query_one("SELECT COUNT(*) c FROM STOCK_MOVEMENT WHERE product_id = %s AND reference_id = 'PROD-EDIT'", (self.pid,))['c'], 1)
        form['selling_price'] = 'abc'
        r = self.admin.post(f'/products/edit/{self.pid}', data=form)
        self.assertEqual(r.status_code, 302)    # friendly redirect instead of a 500

    def test_product_delete_keeps_history_when_blocked(self):
        # product has movements AND is referenced by a PO / sale -> must not lose STOCK_MOVEMENT rows
        before = db.query_one("SELECT COUNT(*) c FROM STOCK_MOVEMENT WHERE product_id = %s", (self.pid,))['c']
        self._sale()
        self.admin.post(f'/products/delete/{self.pid}')
        self.assertIsNotNone(db.query_one("SELECT 1 FROM PRODUCT WHERE product_id = %s", (self.pid,)))
        self.assertGreaterEqual(db.query_one("SELECT COUNT(*) c FROM STOCK_MOVEMENT WHERE product_id = %s", (self.pid,))['c'], before)

    def test_csv_export_can_be_reimported(self):
        csv_text = self.admin.get('/products/export.csv').get_data(as_text=True)
        lines = csv_text.strip().splitlines()
        header = lines[0].split(',')
        price_idx = header.index('Selling Price')
        first = lines[1].split(',')
        sku = first[0]
        first[price_idx] = '12345.0'
        lines[1] = ','.join(first)
        data = {'file': (io.BytesIO('\ufeff'.join(['', '\n'.join(lines)]).encode('utf-8')), 'products.csv')}
        r = self.admin.post('/products/import-csv', data=data, content_type='multipart/form-data')
        self.assertEqual(r.status_code, 302)
        self.assertEqual(db.query_one("SELECT selling_price p FROM PRODUCT WHERE product_code = %s", (sku,))['p'], 12345.0)

    def test_quotation_conversion(self):
        self.sai.post('/quotations/create', data={'product_id': self.pid, 'quantity': '1'})
        q = db.query_one("SELECT * FROM QUOTATION ORDER BY quote_id DESC LIMIT 1")
        before = stock_of(self.pid)
        self.sai.post(f"/quotations/convert/{q['quote_id']}")
        sale = db.query_one("SELECT * FROM SALE ORDER BY sale_id DESC LIMIT 1")
        self.assertEqual(sale['payment_status'], 'Pending')       # converting is not a payment
        self.assertAlmostEqual(sale['balance_due'], q['grand_total'], places=2)
        self.assertEqual(stock_of(self.pid), before - 1)
        self.sai.post(f"/quotations/convert/{q['quote_id']}")      # second click does nothing
        self.assertEqual(stock_of(self.pid), before - 1)
        # expired quotation is refused
        self.sai.post('/quotations/create', data={'product_id': self.pid, 'quantity': '1'})
        q2 = db.query_one("SELECT * FROM QUOTATION ORDER BY quote_id DESC LIMIT 1")
        db.execute("UPDATE QUOTATION SET expiry_date = '2000-01-01' WHERE quote_id = %s", (q2['quote_id'],))
        n = sale_count()
        self.sai.post(f"/quotations/convert/{q2['quote_id']}")
        self.assertEqual(sale_count(), n)
        # negative quantity quotation is refused
        n_q = db.query_one("SELECT COUNT(*) c FROM QUOTATION")['c']
        self.sai.post('/quotations/create', data={'product_id': self.pid, 'quantity': '-5'})
        self.assertEqual(db.query_one("SELECT COUNT(*) c FROM QUOTATION")['c'], n_q)


class TestFinance(Base):
    def test_daily_closing_ignores_browser_values_and_unpaid_credit(self):
        cust = db.query_one("SELECT customer_id FROM CUSTOMER LIMIT 1")['customer_id']
        self.checkout(self.sai, payment_method='Pay Later', customer_id=cust)
        today = app_module.get_app_today().strftime('%Y-%m-%d')
        expected = app_module.compute_closing_totals(today)
        self.sai.post('/reports/daily-closing', data={'closing_date': today, 'actual_cash': str(expected['cash']),
                                                      'expected_cash': '999999', 'expected_total': '999999'})
        row = db.query_one("SELECT * FROM DAILY_CLOSING WHERE closing_date = %s", (today,))
        self.assertEqual(row['expected_cash'], expected['cash'])
        self.assertEqual(row['cash_difference'], 0.0)
        # staff cannot overwrite a finalised closing
        self.sai.post('/reports/daily-closing', data={'closing_date': today, 'actual_cash': '0'})
        self.assertEqual(db.query_one("SELECT actual_cash a FROM DAILY_CLOSING WHERE closing_date = %s", (today,))['a'], expected['cash'])
        # a manager can amend it
        login('geetha', 'geetha123').post('/reports/daily-closing', data={'closing_date': today, 'actual_cash': '1'})
        self.assertEqual(db.query_one("SELECT actual_cash a FROM DAILY_CLOSING WHERE closing_date = %s", (today,))['a'], 1.0)

    def _gst_csv_totals(self):
        lines = self.admin.get('/reports/gst/export.csv').get_data(as_text=True).strip().splitlines()[1:]
        rows = [l.split(',') for l in lines if l]
        return sum(int(r[2]) for r in rows), round(sum(float(r[3]) for r in rows), 2)

    def test_gst_report_excludes_refunded_and_uses_net_taxable(self):
        status, body = self.checkout(self.sai, discount_amount=round(self.prod['selling_price'] * 0.05, 2))
        self.assertEqual(status, 200)
        sale = db.query_one("SELECT * FROM SALE WHERE invoice_number = %s", (body['invoice_number'],))
        expect = db.query_one("""SELECT COUNT(*) c, SUM(subtotal - COALESCE(discount_amount,0) - COALESCE(exchange_value,0)) t
                                 FROM SALE WHERE payment_status <> 'Refunded'""")
        self.assertEqual(self._gst_csv_totals(), (expect['c'], round(expect['t'], 2)))
        n_before, taxable_before = self._gst_csv_totals()
        self.admin.post('/returns/create', data={'invoice_number': sale['invoice_number'], 'refund_amount': '', 'reason': 'x'})
        n_after, taxable_after = self._gst_csv_totals()
        self.assertEqual(n_after, n_before - 1)
        self.assertAlmostEqual(taxable_before - taxable_after, sale['subtotal'] - sale['discount_amount'], places=1)

    def test_settings_validation_and_banner_clear(self):
        self.admin.post('/settings', data={'action': 'update_settings', 'offers_banner': 'Diwali sale', 'app_today_mode': 'auto',
                                           'emi_rate_3m': '0', 'emi_rate_6m': '12', 'emi_rate_9m': '14'})
        self.admin.post('/settings', data={'action': 'update_settings', 'offers_banner': '', 'app_today_mode': 'auto',
                                           'emi_rate_3m': '0', 'emi_rate_6m': '12', 'emi_rate_9m': '14'})
        self.assertEqual(db.query_one("SELECT setting_value v FROM STORE_SETTING WHERE setting_key = 'offers_banner'")['v'], '')
        self.admin.post('/settings', data={'action': 'update_settings', 'app_today_mode': 'manual', 'app_today': 'not-a-date',
                                           'emi_rate_3m': '0', 'emi_rate_6m': '12', 'emi_rate_9m': '14'})
        self.assertNotEqual(db.query_one("SELECT setting_value v FROM STORE_SETTING WHERE setting_key = 'app_today_mode'")['v'], 'manual')
        self.assertEqual(self.sai.post('/settings', data={'action': 'update_settings'}).status_code, 302)  # blocked role

    def test_auto_mode_uses_real_date(self):
        db.upsert_setting('app_today_mode', 'auto')
        self.assertEqual(app_module.get_app_today(), datetime.date.today())


class TestBackupRestore(Base):
    def _counts(self):
        return {t: db.query_one(f"SELECT COUNT(*) c FROM {t}")['c'] for t in app_module.BACKUP_TABLES}

    def test_restore_really_restores(self):
        backup = self.admin.get('/settings/backup-json').get_data()
        original = self._counts()
        self.checkout(self.sai, qty=2)
        db.execute("INSERT INTO CUSTOMER (customer_name, phone) VALUES ('Temp Person', '9000000001')")
        self.assertNotEqual(self._counts(), original)
        r = self.admin.post('/settings/restore-json', data={'file': (io.BytesIO(backup), 'b.json')}, content_type='multipart/form-data')
        self.assertEqual(r.status_code, 302)
        restored = self._counts()
        for t in original:
            if t != 'AUDIT_LOG':
                self.assertEqual(restored[t], original[t], t)

    def test_bad_restore_leaves_data_untouched(self):
        original = self._counts()
        for payload in (b'not json', json.dumps({'tables': {}}).encode(), json.dumps({'tables': {'USER': [{'username': 'x', 'status': 'Inactive'}]}}).encode()):
            self.admin.post('/settings/restore-json', data={'file': (io.BytesIO(payload), 'b.json')}, content_type='multipart/form-data')
        broken = json.dumps({'tables': {'USER': [{'user_id': 1, 'username': 'a', 'password_hash': 'x', 'full_name': 'A', 'role': 'Sales Staff', 'status': 'Active'}],
                                        'SALE_ITEM': [{'item_id': 1, 'sale_id': 99999, 'product_id': 99999}]}}).encode()
        self.admin.post('/settings/restore-json', data={'file': (io.BytesIO(broken), 'b.json')}, content_type='multipart/form-data')
        self.assertEqual(self._counts()['PRODUCT'], original['PRODUCT'])
        self.assertEqual(self._counts()['USER'], original['USER'])


class TestSecondPassAudit(Base):
    """Defects found during the independent audit of the first fix release."""

    def test_zero_rated_product_is_not_taxed(self):
        db.execute("UPDATE PRODUCT SET tax_rate = 0 WHERE product_id = %s", (self.pid,))
        status, body = self.checkout(self.sai)
        self.assertEqual(status, 200)
        self.assertEqual(db.query_one("SELECT tax_amount t FROM SALE WHERE invoice_number = %s", (body['invoice_number'],))['t'], 0.0)
        self.sai.post('/quotations/create', data={'product_id': self.pid, 'quantity': '1'})
        self.assertEqual(db.query_one("SELECT tax_amount t FROM QUOTATION ORDER BY quote_id DESC LIMIT 1")['t'], 0.0)

    def test_returned_serial_can_be_resold(self):
        ph = db.query_one("""SELECT p.product_id FROM PRODUCT p JOIN CATEGORY c ON p.category_id = c.category_id
                             WHERE LOWER(c.category_name) LIKE '%phone%' AND p.stock_quantity > 2 LIMIT 1""")['product_id']
        def sell(sn):
            return self.sai.post('/api/pos/checkout', json={'items': [{'product_id': ph, 'quantity': 1, 'serial_number': sn}], 'payment_method': 'Cash'})
        first = sell('IMEI-AUDIT-1')
        self.assertEqual(first.status_code, 200)
        self.assertEqual(sell('IMEI-AUDIT-1').status_code, 400)          # still unique while the sale stands
        self.admin.post('/returns/create', data={'invoice_number': first.get_json()['invoice_number'], 'refund_amount': '', 'reason': 'x'})
        self.assertEqual(sell('IMEI-AUDIT-1').status_code, 200)          # free again after the return

    def test_restore_of_older_backup_keeps_audit_log(self):
        data = json.loads(self.admin.get('/settings/backup-json').get_data())
        audit_before = db.query_one("SELECT COUNT(*) c FROM AUDIT_LOG")['c']
        del data['tables']['AUDIT_LOG']
        r = self.admin.post('/settings/restore-json', data={'file': (io.BytesIO(json.dumps(data).encode()), 'old.json')},
                            content_type='multipart/form-data')
        self.assertEqual(r.status_code, 302)
        self.assertGreaterEqual(db.query_one("SELECT COUNT(*) c FROM AUDIT_LOG")['c'], audit_before)

    def test_fractional_and_boolean_quantities_rejected(self):
        before = stock_of(self.pid)
        self.assertEqual(self.checkout(self.sai, qty=1.9)[0], 400)
        self.assertEqual(self.checkout(self.sai, qty=True)[0], 400)
        self.assertEqual(self.checkout(self.sai, qty='2')[0], 200)       # numeric strings still fine
        self.assertEqual(stock_of(self.pid), before - 2)

    def test_exact_ten_percent_never_needs_owner(self):
        for price in (1699.0, 999.0, 33333.0, 7.0, 12345.67):
            db.execute("UPDATE PRODUCT SET selling_price = %s WHERE product_id = %s", (price, self.pid))
            self.assertEqual(self.checkout(self.sai, discount_amount=round(price * 0.10, 2))[0], 200, price)
            self.assertEqual(self.checkout(self.sai, coupon_code='FESTIVE10')[0], 200, price)
            self.assertEqual(self.checkout(self.sai, discount_amount=round(price * 0.11, 2))[0], 403, price)

    def test_concurrent_checkouts_cannot_oversell(self):
        import threading
        db.execute("UPDATE PRODUCT SET stock_quantity = 1 WHERE product_id = %s", (self.pid,))
        results = []

        def buy():
            results.append(self.checkout(login('sai', 'sai123'))[0])

        threads = [threading.Thread(target=buy) for _ in range(6)]
        for th in threads:
            th.start()
        for th in threads:
            th.join()
        self.assertEqual(results.count(200), 1, results)
        self.assertEqual(stock_of(self.pid), 0)


class TestMySQLScriptSplitter(unittest.TestCase):
    def test_all_tables_survive_comment_stripping(self):
        with open(os.path.join(config.BASE_DIR, 'schema_mysql.sql'), encoding='utf-8') as fh:
            stmts = init_db._split_mysql_script(fh.read())
        self.assertEqual(sum(1 for s in stmts if s.upper().startswith('CREATE TABLE')), 22)
        self.assertFalse(any(s.startswith('--') for s in stmts))
        sale = next(s for s in stmts if 'CREATE TABLE IF NOT EXISTS SALE (' in s)
        self.assertIn('cgst_amount', sale)
        self.assertIn('sgst_amount', sale)


if __name__ == '__main__':
    unittest.main(verbosity=2)
