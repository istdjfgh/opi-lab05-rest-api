"""API v1: усі ендпоінти, коди відповідей, вплив на базу даних."""
import pytest

KEY = {'X-API-Key': 'test-key'}

NEW_PRODUCT = {'name': 'Вінгспен', 'slug': 'wingspan', 'category_id': 1, 'price': 2190, 'stock': 4,
               'players_min': 1, 'players_max': 5, 'age': 10, 'minutes': 70, 'emoji': '🐦',
               'short': 'Колекціонуйте птахів у заповіднику.'}

ORDER = {'customer': {'name': 'Петро Іваненко', 'email': 'Petro@Example.com', 'phone': '+380 67 123 45 67',
                      'city': 'Луцьк'},
         'address': 'Відділення №5', 'items': [{'product_id': 11, 'quantity': 2}]}


def test_health(client):
    response = client.get('/api/v1/health')
    assert response.status_code == 200 and response.json == {'status': 'ok', 'version': 'v1'}
    assert response.headers['Deprecation'] == 'true' and 'successor-version' in response.headers['Link']


def test_list_products(client):
    data = client.get('/api/v1/products').json
    assert len(data) == 12
    assert {'id', 'name', 'slug', 'price', 'stock', 'category_name', 'is_bestseller'} <= data[0].keys()
    assert isinstance(data[0]['is_bestseller'], bool)


def test_products_filters_and_sorting(client):
    data = client.get('/api/v1/products?category=strategy&sort=price_asc').json
    assert [p['slug'] for p in data] == ['small-world', 'terraforming-mars', 'brass', 'kemet']
    assert [p['slug'] for p in client.get('/api/v1/products?q=МАРС').json] == ['terraforming-mars']
    data = client.get('/api/v1/products?in_stock=1&max_price=500').json
    assert {p['slug'] for p in data} == {'alias', 'dobble'}


def test_get_product(client):
    response = client.get('/api/v1/products/1')
    assert response.status_code == 200 and response.json['slug'] == 'carcassonne'


def test_create_product(client):
    response = client.post('/api/v1/products', json=NEW_PRODUCT, headers=KEY)
    assert response.status_code == 201
    body = response.json
    assert body['id'] == 13 and body['description'] == '' and body['is_bestseller'] is False
    assert response.headers['Location'].endswith('/api/v1/products/13')
    assert client.get(response.headers['Location']).json['name'] == 'Вінгспен'


def test_put_replaces_product(client):
    replacement = {**NEW_PRODUCT, 'slug': 'carcassonne', 'name': 'Каркасон (нове видання)', 'price': 1290}
    response = client.put('/api/v1/products/1', json=replacement, headers=KEY)
    assert response.status_code == 200
    assert response.json['name'] == 'Каркасон (нове видання)' and response.json['price'] == 1290


def test_put_requires_all_fields(client):
    response = client.put('/api/v1/products/1', json={'price': 10}, headers=KEY)
    assert response.status_code == 400 and 'name' in response.json['details']


def test_patch_changes_only_given_fields(client):
    before = client.get('/api/v1/products/2').json
    response = client.patch('/api/v1/products/2', json={'stock': 0, 'price': 1799.99}, headers=KEY)
    after = response.json
    assert response.status_code == 200 and after['stock'] == 0 and after['price'] == 1799.99
    assert after['name'] == before['name'] and after['players_max'] == before['players_max']


def test_delete_product(client):
    new_id = client.post('/api/v1/products', json=NEW_PRODUCT, headers=KEY).json['id']
    response = client.delete(f'/api/v1/products/{new_id}', headers=KEY)
    assert response.status_code == 204 and response.data == b''
    assert client.get(f'/api/v1/products/{new_id}').status_code == 404


def test_delete_product_in_orders_is_conflict(client):
    response = client.delete('/api/v1/products/1', headers=KEY)
    assert response.status_code == 409 and 'stock = 0' in response.json['error']


def test_duplicate_slug_is_conflict(client):
    response = client.post('/api/v1/products', json={**NEW_PRODUCT, 'slug': 'dobble'}, headers=KEY)
    assert response.status_code == 409 and response.json['details'] == {'slug': 'має бути унікальним'}


def test_categories(client):
    data = client.get('/api/v1/categories').json
    assert len(data) == 7
    economic = next(c for c in data if c['slug'] == 'economic')
    assert economic['parent_name'] == 'Стратегії' and economic['products_count'] == 2
    assert client.get(f'/api/v1/categories/{economic["id"]}').json['slug'] == 'economic'


def test_create_and_delete_category(client):
    response = client.post('/api/v1/categories', json={'name': 'Варгейми', 'slug': 'wargames', 'emoji': '⚔️',
                                                       'color': '#495057', 'parent_id': 2}, headers=KEY)
    assert response.status_code == 201 and response.json['parent_id'] == 2
    assert client.delete(f'/api/v1/categories/{response.json["id"]}', headers=KEY).status_code == 204


def test_category_rules(client):
    response = client.post('/api/v1/categories', json={'name': 'Глибока', 'slug': 'deep', 'emoji': '🎲',
                                                       'color': '#000000', 'parent_id': 3}, headers=KEY)
    assert response.status_code == 400 and 'верхнього рівня' in response.json['details']['parent_id']
    assert client.delete('/api/v1/categories/5', headers=KEY).status_code == 409


def test_create_order_public(client):
    stock_before = client.get('/api/v1/products/11').json['stock']
    response = client.post('/api/v1/orders', json={**ORDER, 'promo_code': 'welcome10'})
    assert response.status_code == 201
    order = response.json
    assert order['status'] == 'Нове' and order['subtotal'] == 780 and order['discount'] == 78 and order['total'] == 702
    assert order['customer_email'] == 'petro@example.com' and order['items'][0]['unit_price'] == 390
    assert client.get('/api/v1/products/11').json['stock'] == stock_before - 2
    assert response.headers['Location'].endswith(f'/api/v1/orders/{order["id"]}')


def test_order_out_of_stock_is_conflict(client):
    response = client.post('/api/v1/orders', json={**ORDER, 'items': [{'product_id': 3, 'quantity': 9}]})
    assert response.status_code == 409 and 'на складі' in response.json['error']


def test_order_unknown_product_and_bad_promo(client):
    response = client.post('/api/v1/orders', json={**ORDER, 'items': [{'product_id': 999, 'quantity': 1}]})
    assert response.status_code == 400 and '999' in response.json['details']['items']
    response = client.post('/api/v1/orders', json={**ORDER, 'promo_code': 'STAFF50'})
    assert response.status_code == 400 and response.json['details']['promo_code'] == 'Промокод вимкнено.'


def test_orders_require_key_and_filter(client):
    assert client.get('/api/v1/orders').status_code == 401
    data = client.get('/api/v1/orders?status=Доставлене', headers=KEY).json
    assert len(data) == 2 and all(o['status'] == 'Доставлене' for o in data)
    assert client.get('/api/v1/orders?status=Загублене', headers=KEY).status_code == 400


def test_get_order_with_items(client):
    order = client.get('/api/v1/orders/1', headers=KEY).json
    assert len(order['items']) == 2 and sum(i['line_total'] for i in order['items']) == order['subtotal']


def test_change_status_and_delete_order(client):
    response = client.patch('/api/v1/orders/6', json={'status': 'Відправлене'}, headers=KEY)
    assert response.status_code == 200 and response.json['status'] == 'Відправлене'
    response = client.patch('/api/v1/orders/6', json={'status': 'Загублене'}, headers=KEY)
    assert response.status_code == 400 and 'допустимі' in response.json['details']['status']
    assert client.delete('/api/v1/orders/6', headers=KEY).status_code == 204
    assert client.get('/api/v1/orders/6', headers=KEY).status_code == 404


def test_customers(client):
    data = client.get('/api/v1/customers?q=олена', headers=KEY).json
    assert [c['name'] for c in data] == ['Олена Коваль']
    customer = client.get(f'/api/v1/customers/{data[0]["id"]}', headers=KEY).json
    assert len(customer['orders']) == 2
    assert client.get('/api/v1/customers/999', headers=KEY).status_code == 404


def test_feedback(client):
    data = client.get('/api/v1/feedback').json
    assert len(data) == 4 and 'email' not in data[0]
    response = client.post('/api/v1/feedback', json={'name': 'Марія', 'email': 'maria@example.com', 'rating': 5,
                                                     'message': 'Чудовий магазин, швидка доставка!'})
    assert response.status_code == 201 and 'email' not in response.json


@pytest.mark.parametrize('body, valid, total', [
    ({'code': 'party15', 'subtotal': 1500}, True, 1275),
    ({'code': 'PARTY15', 'subtotal': 500}, False, 500),
    ({'code': 'BLACKFRIDAY30', 'subtotal': 3000, 'date': '2025-11-01'}, True, 2100),
    ({'code': 'BLACKFRIDAY30', 'subtotal': 3000, 'date': '2026-11-23'}, False, 3000),
])
def test_promo_check(client, body, valid, total):
    data = client.post('/api/v1/promo-codes/check', json=body).json
    assert data['valid'] is valid and data['total'] == total
    assert (data['reason'] is None) is valid


def test_stats(client):
    data = client.get('/api/v1/stats', headers=KEY).json
    assert data['orders'] == 6 and data['products'] == 12
