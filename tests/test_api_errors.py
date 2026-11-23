"""Обробка помилок і валідація вхідних даних API (рівень 3), документація (рівень 2)."""
import pytest

KEY = {'X-API-Key': 'test-key'}


@pytest.mark.parametrize('url', ['/api/v1/nope', '/api/v2/nope', '/api/v1/products/abc'])
def test_unknown_url_returns_json_404(client, url):
    response = client.get(url)
    assert response.status_code == 404 and response.is_json


def test_site_404_is_still_html(client):
    response = client.get('/no-such-page')
    assert response.status_code == 404 and 'text/html' in response.content_type


def test_method_not_allowed_has_allow_header(client):
    response = client.delete('/api/v1/health')
    assert response.status_code == 405 and response.is_json
    assert response.headers['Allow'] == 'GET, HEAD, OPTIONS'


@pytest.mark.parametrize('headers', [{}, {'X-API-Key': 'wrong'}, {'X-API-Key': ''}])
def test_write_requires_valid_key(client, headers):
    response = client.post('/api/v1/products', json={}, headers=headers)
    assert response.status_code == 401 and 'X-API-Key' in response.json['error']


def test_not_json_body_is_415(client):
    response = client.post('/api/v1/feedback', data='name=Bot', content_type='application/x-www-form-urlencoded')
    assert response.status_code == 415


@pytest.mark.parametrize('raw, message', [('{"name": ', 'некоректний JSON'), ('[1, 2]', 'JSON-об’єктом')])
def test_broken_or_non_object_json_is_400(client, raw, message):
    response = client.post('/api/v1/feedback', data=raw, content_type='application/json')
    assert response.status_code == 400 and message in response.json['error']


def test_types_are_checked(client):
    body = {'name': 'Гра', 'slug': 'game', 'category_id': '1', 'price': '100', 'stock': 1.5, 'players_min': True,
            'players_max': 4, 'age': 8, 'minutes': 30, 'emoji': '🎲', 'short': 'Опис', 'is_bestseller': 'yes'}
    details = client.post('/api/v1/products', json=body, headers=KEY).json['details']
    assert details == {'category_id': 'має бути цілим числом', 'price': 'має бути числом',
                       'stock': 'має бути цілим числом', 'players_min': 'має бути цілим числом',
                       'is_bestseller': 'має бути true або false'}


def test_ranges_patterns_and_unknown_fields(client):
    body = {'name': 'Гра', 'slug': 'Погана Адреса', 'category_id': 999, 'price': -1, 'stock': 1,
            'players_min': 6, 'players_max': 2, 'age': 8, 'minutes': 30, 'emoji': '🎲', 'short': 'Опис',
            'colour': 'red'}
    details = client.post('/api/v1/products', json=body, headers=KEY).json['details']
    assert details['slug'].startswith('лише малі') and details['price'] == 'має бути від 0 до 100000'
    assert details['category_id'] == 'категорії з таким id не існує'
    assert details['players_max'] == 'не може бути менше за players_min'
    assert details['colour'] == 'невідоме поле'


def test_patch_validates_only_sent_fields_but_keeps_rules(client):
    assert client.patch('/api/v1/products/1', json={}, headers=KEY).status_code == 400
    response = client.patch('/api/v1/products/1', json={'players_max': 1}, headers=KEY)  # min = 2
    assert response.status_code == 400 and 'players_max' in response.json['details']


def test_order_validation_paths(client):
    body = {'customer': {'name': 'І', 'email': 'bad', 'phone': '12', 'city': 'Луцьк', 'age': 20},
            'address': '', 'items': [{'product_id': 1, 'quantity': 0}, {'product_id': 'x', 'quantity': 1}, 5]}
    details = client.post('/api/v1/orders', json=body).json['details']
    assert set(details) == {'customer.name', 'customer.email', 'customer.phone', 'customer.age', 'address',
                            'items[0].quantity', 'items[1].product_id', 'items[2]'}


def test_order_duplicate_items_rejected(client):
    body = {'customer': {'name': 'Іван Петренко', 'email': 'i@example.com', 'phone': '+380671234567', 'city': 'Луцьк'},
            'address': 'НП 1', 'items': [{'product_id': 1, 'quantity': 1}, {'product_id': 1, 'quantity': 2}]}
    details = client.post('/api/v1/orders', json=body).json['details']
    assert 'збільште quantity' in details['items[1].product_id']


def test_empty_items_rejected(client):
    details = client.post('/api/v1/orders', json={'items': []}).json['details']
    assert 'непорожнім' in details['items'] and 'customer' in details


def test_bad_query_params(client):
    assert client.get('/api/v1/products?category=nope').json['details'] == {'category': 'категорії «nope» не існує'}
    assert 'sort' in client.get('/api/v1/products?sort=DROP').json['details']


def test_sql_injection_in_search_is_harmless(client):
    assert client.get("/api/v1/products?q=' OR 1=1 --").json == []
    assert len(client.get('/api/v1/products').json) == 12


def test_unexpected_error_returns_json_500(app, monkeypatch):
    from models import catalog

    def boom(*args, **kwargs):
        raise RuntimeError('база недоступна')
    monkeypatch.setattr(catalog, 'search_products', boom)
    response = app.test_client().get('/api/v2/products')
    assert response.status_code == 500
    assert response.json == {'error': {'status': 500, 'code': 'internal_error', 'message': 'Внутрішня помилка сервера.'}}


def test_api_is_exempt_from_csrf_but_site_is_not(tmp_path):
    import seed_data
    from app import create_app
    app = create_app({'TESTING': True, 'DATABASE': str(tmp_path / 'c.sqlite'), 'API_KEY': 'k'})
    with app.app_context():
        seed_data.seed()
    client = app.test_client()
    ok = client.post('/api/v1/feedback', json={'name': 'Марія', 'email': 'm@example.com', 'rating': 5,
                                               'message': 'Відгук через API без CSRF-токена.'})
    assert ok.status_code == 201
    assert client.post('/feedback', data={'name': 'Марія'}).status_code == 400


# ------------------------------------------------------------------ документація

@pytest.mark.parametrize('spec, prefix, count', [('/apispec_v1.json', '/api/v1', 12), ('/apispec_v2.json', '/api/v2', 7)])
def test_openapi_specs(client, spec, prefix, count):
    data = client.get(spec).json
    assert data['info']['title'].startswith('API магазину')
    assert data['securityDefinitions']['ApiKeyAuth']['name'] == 'X-API-Key'
    assert all(path.startswith(prefix) for path in data['paths'])
    assert len(data['paths']) == count
    assert 'ProductInput' in data['definitions']


def test_every_endpoint_is_documented(client, app):
    documented = set()
    for spec in ('/apispec_v1.json', '/apispec_v2.json'):
        for path, methods in client.get(spec).json['paths'].items():
            documented |= {(path, m.upper()) for m in methods if m != 'parameters'}
    for rule in app.url_map.iter_rules():
        if rule.rule.startswith('/api/'):
            path = rule.rule.replace('<int:', '{').replace('>', '}')
            for method in rule.methods - {'HEAD', 'OPTIONS'}:
                assert (path, method) in documented, (path, method)


def test_swagger_ui_page(client):
    response = client.get('/apidocs/')
    assert response.status_code == 200 and b'swagger' in response.data.lower()
