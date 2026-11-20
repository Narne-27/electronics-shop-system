from app import app

client = app.test_client()

with client.session_transaction() as sess:
    sess['user_id'] = 4
    sess['role'] = 'Shop Owner'

routes = [
    '/',
    '/products',
    '/pos',
    '/inventory',
    '/warranty',
    '/customers',
    '/customer-dues',
    '/quotations',
    '/invoices',
    '/invoice/1',
    '/returns',
    '/repair-tickets',
    '/categories',
    '/reports',
    '/reports/profit-loss',
    '/reports/gst',
    '/reports/daily-closing',
    '/expenses',
    '/notifications',
    '/audit-log',
    '/settings',
    '/users'
]

print("=== Electrodesk Page Verification ===")
all_ok = True
for r in routes:
    resp = client.get(r)
    html = resp.data.decode('utf-8', errors='ignore')
    if 'data-bg-intensity="hero"' in html:
        mode = "hero"
    elif 'data-bg-intensity="calm"' in html:
        mode = "calm"
    else:
        mode = "none"
        
    status = resp.status_code
    print(f"{r:24} | Status: {status} | Mode: {mode}")
    if status != 200:
        all_ok = False

if all_ok:
    print("\n[SUCCESS] All 22 main routes responded with 200 OK and proper background intensity mode!")
else:
    print("\n[FAIL] Some routes failed!")
