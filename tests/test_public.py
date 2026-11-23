"""Інтеграційні тести публічної частини: сторінки, каталог, кошик, оформлення, відгуки."""
import pytest

from conftest import product_id


@pytest.mark.parametrize('url', ['/', '/catalog', '/about', '/delivery', '/contacts', '/feedback', '/cart',
                                 '/catalog/carcassonne'])
def test_pages_open(client, url):
    response = client.get(url)
    assert response.status_code == 200
    assert 'Кубик' in response.text


def test_home_shows_bestsellers_from_db(client):
    page = client.get('/').text
    assert 'Каркасон' in page and 'Тераформування Марса' in page


def test_unknown_product_is_404(client):
    response = client.get('/catalog/no-such-game')
    assert response.status_code == 404 and 'Такої сторінки немає' in response.text


def test_catalog_search_and_filters(client):
    page = client.get('/catalog?q=марс').text
    assert 'Тераформування Марса' in page and 'Доббль' not in page
    page = client.get('/catalog?category=kids&sort=price_asc').text
    assert page.index('Доббль') < page.index('Містеріум Кідс')
    page = client.get('/catalog?in_stock=1&category=area-control').text
    assert 'Маленький світ' in page and 'Кемет' not in page


def test_catalog_ignores_bad_filter_values(client):
    assert client.get('/catalog?min_price=abc&players=999&sort=DROP').status_code == 200


def test_cart_add_update_remove(client, db_row):
    pid = product_id(db_row, 'codenames')
    client.post(f'/cart/add/{pid}', data={'quantity': 2})
    assert 'Кодові імена' in client.get('/cart').text
    with client.session_transaction() as s:
        assert s['cart'] == {str(pid): 2}
    client.post(f'/cart/update/{pid}', data={'quantity': 5})
    with client.session_transaction() as s:
        assert s['cart'][str(pid)] == 5
    client.post(f'/cart/remove/{pid}')
    with client.session_transaction() as s:
        assert s['cart'] == {}


def test_cart_respects_stock(client, db_row):
    pid = product_id(db_row, 'mysterium-kids')  # залишок 1
    client.post(f'/cart/add/{pid}', data={'quantity': 5})
    with client.session_transaction() as s:
        assert s['cart'][str(pid)] == 1
    page = client.post(f'/cart/add/{pid}', data={'quantity': 1}, follow_redirects=True).text
    assert 'більше немає в наявності' in page


def test_cannot_add_missing_product(client):
    assert client.post('/cart/add/9999').status_code == 404


def test_promo_code_applies_discount(client, db_row):
    client.post(f'/cart/add/{product_id(db_row, "carcassonne")}', data={'quantity': 1})
    page = client.post('/cart/promo', data={'code': 'welcome10'}, follow_redirects=True).text
    assert 'WELCOME10 застосовано' in page and '1 035 грн' in page
    page = client.post('/cart/promo', data={'code': 'NOPE'}, follow_redirects=True).text
    assert 'не існує' in page


def test_checkout_requires_cart(client):
    response = client.get('/checkout')
    assert response.status_code == 302 and '/catalog' in response.headers['Location']


def test_checkout_validation_keeps_values(client, db_row):
    client.post(f'/cart/add/{product_id(db_row, "dobble")}')
    page = client.post('/checkout', data={'name': 'Іван', 'email': 'bad', 'phone': '12', 'city': '', 'address': ''}).text
    assert 'коректну адресу' in page and 'формат +380' in page and 'обов’язкове поле' in page
    assert 'value="Іван"' in page


def test_checkout_creates_order_and_clears_cart(client, db_row):
    pid = product_id(db_row, 'dobble')
    stock_before = db_row('SELECT stock FROM products WHERE id = ?', (pid,))['stock']
    client.post(f'/cart/add/{pid}', data={'quantity': 2})
    client.post('/cart/promo', data={'code': 'WELCOME10'})
    response = client.post('/checkout', data={'name': 'Петро Іваненко', 'email': 'Petro@Example.com',
                                              'phone': '+380 67 123 45 67', 'city': 'Луцьк',
                                              'address': 'НП №5', 'comment': 'Подарункове пакування'})
    assert response.status_code == 302
    page = client.get(response.headers['Location']).text
    assert 'Дякуємо, Петро' in page and '702 грн' in page
    order = db_row('SELECT * FROM orders ORDER BY id DESC LIMIT 1')
    assert order['total'] == 702 and order['promo_code'] == 'WELCOME10' and order['status'] == 'Нове'
    assert db_row('SELECT email FROM customers WHERE id = ?', (order['customer_id'],))['email'] == 'petro@example.com'
    assert db_row('SELECT stock FROM products WHERE id = ?', (pid,))['stock'] == stock_before - 2
    with client.session_transaction() as s:
        assert s['cart'] == {} and 'promo' not in s


def test_order_page_visible_only_to_its_buyer(client, app):
    assert client.get('/order/1').status_code == 404
    other = app.test_client()
    assert other.get('/order/1').status_code == 404


def test_feedback_validation_and_save(client, db_row):
    page = client.post('/feedback', data={'name': 'А', 'email': 'x', 'message': 'коротко'}).text
    assert 'щонайменше 2' in page and 'Оцінка' in page and 'щонайменше 10' in page
    response = client.post('/feedback', data={'name': 'Марія', 'email': 'maria@example.com', 'rating': '5',
                                              'message': 'Чудовий магазин, все сподобалось!'})
    assert response.status_code == 302
    row = db_row('SELECT * FROM feedback ORDER BY id DESC LIMIT 1')
    assert row['name'] == 'Марія' and row['rating'] == 5 and row['is_read'] == 0


def test_user_input_is_escaped(client):
    client.post('/feedback', data={'name': '<script>alert(1)</script>', 'email': 'x@example.com', 'rating': '5',
                                   'message': '<b>жирний</b> текст відгуку'})
    page = client.get('/feedback').text
    assert '<script>alert(1)</script>' not in page and '&lt;script&gt;' in page
