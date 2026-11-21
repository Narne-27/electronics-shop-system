"""
Unit and integration tests for the Delivery & Logistics module
"""

import pytest
import json
from app import app
import db

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_delivery_workflow(client):
    # 1. Login as admin
    res = client.post('/login', data={'username': 'admin', 'password': 'admin123'}, follow_redirects=True)
    assert res.status_code == 200

    # 2. View deliveries page
    res = client.get('/deliveries')
    assert res.status_code == 200
    assert b'Delivery &amp; Logistics' in res.data or b'Delivery & Logistics' in res.data
    assert b'DEL-2026-0001' in res.data

    # 3. Create delivery order
    sale = db.query_one("SELECT sale_id FROM SALE ORDER BY sale_id DESC LIMIT 1")
    sale_id = sale['sale_id']

    res = client.post('/deliveries/create', data={
        'sale_id': str(sale_id),
        'recipient_name': 'Rohit Sharma',
        'recipient_phone': '+91 98888 77777',
        'delivery_address': 'Flat 204, Palm Grove, Bandra, Mumbai',
        'delivery_charges': '150',
        'expected_date': '2026-11-25',
        'assigned_to': '',
        'tracking_notes': 'Please call before delivery'
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b'Rohit Sharma' in res.data

    new_del = db.query_one("SELECT delivery_id, delivery_number, status FROM DELIVERY_ORDER WHERE recipient_name = 'Rohit Sharma'")
    assert new_del is not None
    assert new_del['status'] == 'Pending'
    del_id = new_del['delivery_id']

    # 4. Assign delivery personnel
    vikram = db.query_one("SELECT user_id FROM USER WHERE username = 'vikram'")
    vid = vikram['user_id']

    res = client.post(f'/deliveries/{del_id}/assign', data={
        'assigned_to': str(vid),
        'remarks': 'Assigned to Vikram for morning route'
    }, follow_redirects=True)
    assert res.status_code == 200
    check_del = db.query_one("SELECT status, assigned_to FROM DELIVERY_ORDER WHERE delivery_id = %s", (del_id,))
    assert check_del['status'] == 'Assigned'
    assert check_del['assigned_to'] == vid

    # 5. Update status to 'Out for Delivery'
    res = client.post(f'/deliveries/{del_id}/update-status', data={
        'status': 'Out for Delivery',
        'remarks': 'Van dispatched from warehouse'
    }, follow_redirects=True)
    assert res.status_code == 200
    check_del = db.query_one("SELECT status FROM DELIVERY_ORDER WHERE delivery_id = %s", (del_id,))
    assert check_del['status'] == 'Out for Delivery'

    # 6. Mark 'Delivered'
    res = client.post(f'/deliveries/{del_id}/update-status', data={
        'status': 'Delivered',
        'remarks': 'Package delivered and OTP confirmed'
    }, follow_redirects=True)
    assert res.status_code == 200
    check_del = db.query_one("SELECT status, delivered_at FROM DELIVERY_ORDER WHERE delivery_id = %s", (del_id,))
    assert check_del['status'] == 'Delivered'
    assert check_del['delivered_at'] is not None

    # 7. Check History JSON endpoint
    res = client.get(f'/deliveries/{del_id}/history')
    assert res.status_code == 200
    data = json.loads(res.data)
    assert data['delivery']['delivery_number'] == new_del['delivery_number']
    assert len(data['logs']) >= 4  # Pending -> Assigned -> Out for Delivery -> Delivered

    # 8. Edit delivery details
    res = client.post(f'/deliveries/{del_id}/edit', data={
        'recipient_name': 'Rohit Sharma (Verified)',
        'recipient_phone': '+91 98888 77777',
        'delivery_address': 'Flat 204, Palm Grove, Bandra West, Mumbai',
        'delivery_charges': '150',
        'expected_date': '2026-11-25',
        'tracking_notes': 'Delivered successfully'
    }, follow_redirects=True)
    assert res.status_code == 200
    check_del = db.query_one("SELECT recipient_name FROM DELIVERY_ORDER WHERE delivery_id = %s", (del_id,))
    assert 'Verified' in check_del['recipient_name']

    # 9. Role-based access: Delivery Staff restriction
    client.get('/logout')
    res = client.post('/login', data={'username': 'vikram', 'password': 'delivery123'}, follow_redirects=True)
    assert res.status_code == 200

    # Delivery staff cannot assign staff
    res = client.post(f'/deliveries/{del_id}/assign', data={'assigned_to': '1'}, follow_redirects=True)
    assert b'Access denied' in res.data

    # Cleanup test delivery
    db.execute("DELETE FROM DELIVERY_LOG WHERE delivery_id = %s", (del_id,))
    db.execute("DELETE FROM DELIVERY_ORDER WHERE delivery_id = %s", (del_id,))
