"""API v2: конверт data/meta/links, пагінація, вкладені об’єкти, формат помилок."""
KEY = {'X-API-Key': 'test-key'}


def test_index_lists_resources(client):
    links = client.get('/api/v2/').json['data']['links']
    assert links['products'] == '/api/v2/products' and links['docs'] == '/apidocs/'


def test_v2_has_no_deprecation_header(client):
    assert 'Deprecation' not in client.get('/api/v2/products').headers


def test_products_page_envelope(client):
    body = client.get('/api/v2/products?per_page=5&page=2').json
    assert body['meta'] == {'page': 2, 'per_page': 5, 'total': 12, 'pages': 3}
    assert len(body['data']) == 5
    assert body['links']['next'] == '/api/v2/products?page=3&per_page=5'
    assert body['links']['prev'] == '/api/v2/products?page=1&per_page=5'


def test_last_page_has_no_next(client):
    body = client.get('/api/v2/products?per_page=5&page=3').json
    assert len(body['data']) == 2 and body['links']['next'] is None


def test_pagination_keeps_filters_in_links(client):
    body = client.get('/api/v2/products?category=strategy&per_page=2').json
    assert body['meta']['total'] == 4
    assert body['links']['next'] == '/api/v2/products?page=2&per_page=2&category=strategy'


def test_product_shape(client):
    product = client.get('/api/v2/products/1').json['data']
    assert product['price'] == {'amount': 1150.0, 'currency': 'UAH'}
    assert product['players'] == {'min': 2, 'max': 5}
    assert product['category'] == {'id': 1, 'name': 'Сімейні', 'slug': 'family'}
    assert product['in_stock'] is True
    assert product['links'] == {'self': '/api/v2/products/1', 'html': '/catalog/carcassonne'}


def test_category_tree(client):
    data = client.get('/api/v2/categories').json['data']
    strategy = next(c for c in data if c['slug'] == 'strategy')
    assert {c['slug'] for c in strategy['children']} == {'economic', 'area-control'}
    assert strategy['links']['products'] == '/api/v2/products?category=strategy'


def test_create_patch_delete_product(client):
    body = {'name': 'Вінгспен', 'slug': 'wingspan', 'category_id': 1, 'price': 2190, 'stock': 4, 'players_min': 1,
            'players_max': 5, 'age': 10, 'minutes': 70, 'emoji': '🐦', 'short': 'Птахи.'}
    response = client.post('/api/v2/products', json=body, headers=KEY)
    assert response.status_code == 201 and response.json['data']['price']['amount'] == 2190
    pid = response.json['data']['id']
    patched = client.patch(f'/api/v2/products/{pid}', json={'stock': 0}, headers=KEY).json['data']
    assert patched['stock'] == 0 and patched['in_stock'] is False
    put = client.put(f'/api/v2/products/{pid}', json={**body, 'price': 1990}, headers=KEY).json['data']
    assert put['price']['amount'] == 1990 and put['stock'] == 4
    assert client.delete(f'/api/v2/products/{pid}', headers=KEY).status_code == 204


def test_orders_paginated_and_detail(client):
    body = client.get('/api/v2/orders?per_page=4', headers=KEY).json
    assert body['meta']['total'] == 6 and len(body['data']) == 4
    order = client.get('/api/v2/orders/1', headers=KEY).json['data']
    assert order['totals']['currency'] == 'UAH' and order['items'][0]['product']['links']['self'].startswith('/api/v2/')


def test_create_order_and_change_status(client):
    order = {'customer': {'name': 'Ганна Лисенко', 'email': 'hanna@example.com', 'phone': '+380501112233',
                          'city': 'Ковель'}, 'address': 'НП 2', 'items': [{'product_id': 7, 'quantity': 3}]}
    response = client.post('/api/v2/orders', json=order)
    assert response.status_code == 201 and response.json['data']['totals']['total'] == 1770
    oid = response.json['data']['id']
    data = client.patch(f'/api/v2/orders/{oid}', json={'status': 'Підтверджене'}, headers=KEY).json['data']
    assert data['status'] == 'Підтверджене'


def test_promo_check_envelope(client):
    data = client.post('/api/v2/promo-codes/check', json={'code': 'WELCOME10', 'subtotal': 1000}).json['data']
    assert data == {'code': 'WELCOME10', 'valid': True, 'reason': None, 'discount_percent': 10,
                    'discount': 100.0, 'total': 900.0}


def test_v2_error_format(client):
    error = client.get('/api/v2/products/999').json['error']
    assert error == {'status': 404, 'code': 'not_found', 'message': 'Товар з id=999 не знайдено.'}
    error = client.post('/api/v2/products', json={'price': 'дорого'}, headers=KEY).json['error']
    assert error['code'] == 'validation_error' and error['fields']['price'] == 'має бути числом'


def test_v2_pagination_validation(client):
    error = client.get('/api/v2/products?per_page=500').json['error']
    assert error['status'] == 400 and error['fields'] == {'per_page': 'має бути від 1 до 50'}
    assert client.get('/api/v2/products?page=abc').status_code == 400
