"""Інтеграційні тести адмін-панелі: вхід, CRUD для всіх таблиць, обмеження зв'язків."""
import pytest

from conftest import product_id

ADMIN_PAGES = ['/admin/', '/admin/orders', '/admin/orders/1', '/admin/products', '/admin/products/new',
               '/admin/categories', '/admin/customers', '/admin/customers/1', '/admin/promos', '/admin/feedback']

NEW_PRODUCT = {'name': 'Вінгспен', 'slug': 'wingspan', 'category_id': '1', 'price': '2190', 'stock': '4',
               'players_min': '1', 'players_max': '5', 'age': '10', 'minutes': '70', 'emoji': '🐦',
               'short': 'Колекціонуйте птахів у заповіднику.', 'description': '', 'is_bestseller': '1'}


@pytest.mark.parametrize('url', ADMIN_PAGES)
def test_admin_requires_login(client, url):
    response = client.get(url)
    assert response.status_code == 302 and '/admin/login' in response.headers['Location']


@pytest.mark.parametrize('url', ADMIN_PAGES)
def test_admin_pages_open_after_login(admin, url):
    assert admin.get(url).status_code == 200


def test_wrong_password(client):
    page = client.post('/admin/login', data={'password': 'nope'}).text
    assert 'Неправильний пароль' in page
    with client.session_transaction() as s:
        assert not s.get('is_admin')


def test_login_redirects_only_to_local_next(client):
    response = client.post('/admin/login?next=https://evil.example.com/', data={'password': 'test-pass'})
    assert response.headers['Location'] in ('/admin/', 'http://localhost/admin/')
    client.post('/admin/logout')
    response = client.post('/admin/login?next=/admin/orders', data={'password': 'test-pass'})
    assert response.headers['Location'].endswith('/admin/orders')


def test_logout(admin):
    admin.post('/admin/logout')
    assert admin.get('/admin/').status_code == 302


def test_dashboard_shows_stats(admin):
    page = admin.get('/admin/').text
    assert 'замовлень' in page and 'Нові відгуки' in page and 'Ірина' in page


# ------------------------------------------------------------------ товари

def test_product_create_edit_delete(admin, db_row):
    response = admin.post('/admin/products/new', data=NEW_PRODUCT)
    assert response.status_code == 302
    row = db_row("SELECT * FROM products WHERE slug = 'wingspan'")
    assert row['price'] == 2190 and row['is_bestseller'] == 1
    assert 'Вінгспен' in admin.get('/catalog/wingspan').text

    admin.post(f'/admin/products/{row["id"]}/edit', data={**NEW_PRODUCT, 'price': '1999.5', 'is_bestseller': ''})
    row = db_row("SELECT * FROM products WHERE slug = 'wingspan'")
    assert row['price'] == 1999.5 and row['is_bestseller'] == 0

    admin.post(f'/admin/products/{row["id"]}/delete')
    assert db_row("SELECT * FROM products WHERE slug = 'wingspan'") is None


def test_product_validation(admin):
    bad = {**NEW_PRODUCT, 'name': '', 'slug': 'Погано!', 'price': '-5', 'players_min': '4', 'players_max': '2',
           'category_id': '999'}
    page = admin.post('/admin/products/new', data=bad).text
    assert 'обов’язкове поле' in page and 'Slug: лише малі' in page and 'від 0 до 100000' in page
    assert 'не може бути менше' in page and 'Оберіть категорію' in page


def test_product_duplicate_slug(admin):
    page = admin.post('/admin/products/new', data={**NEW_PRODUCT, 'slug': 'carcassonne'}).text
    assert 'уже використовується' in page


def test_product_in_orders_cannot_be_deleted(admin, db_row):
    pid = product_id(db_row, 'carcassonne')
    page = admin.post(f'/admin/products/{pid}/delete', follow_redirects=True).text
    assert 'не можна видалити' in page and db_row('SELECT id FROM products WHERE id = ?', (pid,))


def test_admin_product_search(admin):
    page = admin.get('/admin/products?q=пандем').text
    assert 'Пандемія' in page and 'Каркасон' not in page


# ------------------------------------------------------------------ категорії

def test_category_create_nested_and_delete(admin, db_row):
    strategy = db_row("SELECT id FROM categories WHERE slug = 'strategy'")['id']
    admin.post('/admin/categories', data={'name': 'Варгейми', 'slug': 'wargames', 'emoji': '⚔️',
                                          'color': '#495057', 'parent_id': str(strategy)})
    row = db_row("SELECT * FROM categories WHERE slug = 'wargames'")
    assert row['parent_id'] == strategy
    admin.post(f'/admin/categories/{row["id"]}/delete')
    assert db_row("SELECT * FROM categories WHERE slug = 'wargames'") is None


def test_category_cannot_be_nested_three_levels(admin, db_row):
    economic = db_row("SELECT id FROM categories WHERE slug = 'economic'")['id']
    page = admin.post('/admin/categories', data={'name': 'Глибока', 'slug': 'deep', 'emoji': '🎲',
                                                 'color': '#000000', 'parent_id': str(economic)}).text
    assert 'зі списку' in page


def test_category_with_children_cannot_become_child(admin, db_row):
    strategy = db_row("SELECT * FROM categories WHERE slug = 'strategy'")
    family = db_row("SELECT id FROM categories WHERE slug = 'family'")['id']
    page = admin.post(f'/admin/categories/{strategy["id"]}/edit',
                      data={**{k: strategy[k] for k in ('name', 'slug', 'emoji', 'color')}, 'parent_id': str(family)}).text
    assert 'має підкатегорії' in page


def test_category_with_products_cannot_be_deleted(admin, db_row):
    cid = db_row("SELECT id FROM categories WHERE slug = 'party'")['id']
    page = admin.post(f'/admin/categories/{cid}/delete', follow_redirects=True).text
    assert 'спочатку перенесіть' in page


def test_category_validation(admin):
    page = admin.post('/admin/categories', data={'name': 'X', 'slug': 'Bad Slug', 'emoji': '', 'color': 'red'}).text
    assert 'щонайменше 2' in page and 'Slug: лише' in page and '#RRGGBB' in page


# ------------------------------------------------------------------ замовлення

def test_order_status_change(admin, db_row):
    admin.post('/admin/orders/6/status', data={'status': 'Підтверджене'})
    assert db_row('SELECT status FROM orders WHERE id = 6')['status'] == 'Підтверджене'
    page = admin.post('/admin/orders/6/status', data={'status': 'Хакнуте'}, follow_redirects=True).text
    assert 'Невідомий статус' in page
    assert db_row('SELECT status FROM orders WHERE id = 6')['status'] == 'Підтверджене'


def test_order_filter_by_status(admin):
    page = admin.get('/admin/orders?status=Скасоване').text
    assert '№5' in page and '№1<' not in page


def test_order_delete(admin, db_row):
    admin.post('/admin/orders/2/delete')
    assert db_row('SELECT id FROM orders WHERE id = 2') is None
    assert admin.get('/admin/orders/2').status_code == 404


# ------------------------------------------------------------------ клієнти

def test_customer_crud(admin, db_row):
    response = admin.post('/admin/customers/new', data={'name': 'Ганна Лисенко', 'email': 'hanna@example.com',
                                                        'phone': '', 'city': 'Луцьк', 'note': 'VIP'})
    assert response.status_code == 302
    row = db_row("SELECT * FROM customers WHERE email = 'hanna@example.com'")
    admin.post(f'/admin/customers/{row["id"]}/edit', data={**row, 'city': 'Ковель'})
    assert db_row('SELECT city FROM customers WHERE id = ?', (row['id'],))['city'] == 'Ковель'
    admin.post(f'/admin/customers/{row["id"]}/delete')
    assert db_row('SELECT id FROM customers WHERE id = ?', (row['id'],)) is None


def test_customer_duplicate_email(admin):
    page = admin.post('/admin/customers/new', data={'name': 'Двійник', 'email': 'OLENA.KOVAL@example.com'}).text
    assert 'уже є' in page


def test_customer_with_orders_cannot_be_deleted(admin, db_row):
    page = admin.post('/admin/customers/1/delete', follow_redirects=True).text
    assert 'видалення заборонено' in page and db_row('SELECT id FROM customers WHERE id = 1')


def test_customer_search_is_case_insensitive_for_cyrillic(admin):
    page = admin.get('/admin/customers?q=олена').text
    assert 'Олена Коваль' in page and 'Андрій Мельник' not in page


def test_customer_detail_shows_history(admin):
    page = admin.get('/admin/customers/1').text
    assert 'Історія замовлень' in page and '№1' in page and '№6' in page


# ------------------------------------------------------------------ промокоди і відгуки

def test_promo_crud_and_toggle(admin, db_row):
    admin.post('/admin/promos', data={'code': 'spring15', 'discount_percent': '15', 'min_total': '',
                                      'valid_until': '2027-05-31', 'max_uses': '', 'is_active': '1'})
    row = db_row("SELECT * FROM promo_codes WHERE code = 'SPRING15'")
    assert row['discount_percent'] == 15 and row['min_total'] == 0 and row['max_uses'] is None
    admin.post(f'/admin/promos/{row["id"]}/toggle')
    assert db_row('SELECT is_active FROM promo_codes WHERE id = ?', (row['id'],))['is_active'] == 0
    admin.post(f'/admin/promos/{row["id"]}/edit', data={'code': 'SPRING20', 'discount_percent': '20',
                                                       'is_active': '1'})
    assert db_row('SELECT code FROM promo_codes WHERE id = ?', (row['id'],))['code'] == 'SPRING20'
    admin.post(f'/admin/promos/{row["id"]}/delete')
    assert db_row('SELECT id FROM promo_codes WHERE id = ?', (row['id'],)) is None


def test_promo_validation(admin):
    page = admin.post('/admin/promos', data={'code': 'ab', 'discount_percent': '95', 'valid_until': '31.12.2027'}).text
    assert 'щонайменше 3' in page and 'від 1 до 90' in page and 'РРРР-ММ-ДД' in page
    page = admin.post('/admin/promos', data={'code': 'ЗНИЖКА', 'discount_percent': '10'}).text
    assert 'латинські літери' in page
    page = admin.post('/admin/promos', data={'code': 'WELCOME10', 'discount_percent': '5'}).text
    assert 'уже існує' in page


def test_feedback_read_toggle_and_delete(admin, db_row):
    fid = db_row('SELECT id FROM feedback WHERE is_read = 0 LIMIT 1')['id']
    admin.post(f'/admin/feedback/{fid}/read')
    assert db_row('SELECT is_read FROM feedback WHERE id = ?', (fid,))['is_read'] == 1
    admin.post(f'/admin/feedback/{fid}/delete')
    assert db_row('SELECT id FROM feedback WHERE id = ?', (fid,)) is None
