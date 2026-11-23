"""Модульні тести шару моделей: схема, зв'язки, транзакції, пошук."""
import sqlite3
from datetime import date

import pytest

from models import catalog, customers, get_db, orders


def test_schema_has_all_tables(app):
    with app.app_context():
        names = {r['name'] for r in get_db().execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {'categories', 'products', 'feedback', 'customers', 'orders', 'order_items', 'promo_codes'} <= names


def test_foreign_keys_are_enabled(app):
    with app.app_context():
        assert get_db().execute('PRAGMA foreign_keys').fetchone()[0] == 1


def test_category_tree_is_nested(app):
    with app.app_context():
        tree = dict((root['slug'], [c['slug'] for c in children]) for root, children in catalog.category_tree())
    assert tree['strategy'] == ['area-control', 'economic'] or set(tree['strategy']) == {'economic', 'area-control'}
    assert tree['family'] == []


def test_category_with_descendants_uses_recursive_query(app):
    with app.app_context():
        strategy = catalog.get_category_by_slug('strategy')
        ids = catalog.category_with_descendants(strategy['id'])
        slugs = {catalog.get_category(i)['slug'] for i in ids}
    assert slugs == {'strategy', 'economic', 'area-control'}


def test_search_by_parent_category_includes_children(app):
    with app.app_context():
        strategy = catalog.get_category_by_slug('strategy')
        found = {p['slug'] for p in catalog.search_products({'category_id': strategy['id']})}
    assert {'terraforming-mars', 'brass', 'kemet', 'small-world'} == found


def test_search_filters_combine(app):
    with app.app_context():
        found = catalog.search_products({'min_price': 1000, 'max_price': 2000, 'players': 5, 'in_stock': True,
                                         'sort': 'price_asc'})
    prices = [p['price'] for p in found]
    assert prices == sorted(prices)
    assert all(1000 <= p['price'] <= 2000 and p['players_min'] <= 5 <= p['players_max'] and p['stock'] > 0
               for p in found)
    assert {p['slug'] for p in found} == {'carcassonne', 'ticket-to-ride', 'small-world'}


@pytest.mark.parametrize('query', ['марс', 'МАРС', 'Марс', 'тераформ'])
def test_search_ignores_case_for_cyrillic(app, query):
    with app.app_context():
        assert [p['slug'] for p in catalog.search_products({'q': query})] == ['terraforming-mars']


def test_search_wildcards_are_literal(app):
    with app.app_context():
        assert catalog.search_products({'q': '%'}) == []
        assert catalog.search_products({'q': '_'}) == []


def test_search_text_is_parameterized(app):
    """Спроба SQL-ін'єкції — просто рядок пошуку, таблиці цілі."""
    with app.app_context():
        assert catalog.search_products({'q': "'; DROP TABLE products; --"}) == []
        assert get_db().execute('SELECT COUNT(*) FROM products').fetchone()[0] == 12


def test_delete_category_with_products_is_restricted(app):
    with app.app_context():
        with pytest.raises(sqlite3.IntegrityError):
            catalog.delete_category(catalog.get_category_by_slug('party')['id'])


def test_delete_product_used_in_order_is_restricted(app):
    with app.app_context():
        with pytest.raises(sqlite3.IntegrityError):
            catalog.delete_product(catalog.get_product_by_slug('carcassonne')['id'])


def test_unique_slug_constraint(app):
    with app.app_context():
        product = dict(catalog.get_product_by_slug('dobble'))
        with pytest.raises(sqlite3.IntegrityError):
            catalog.save_product({**product, 'name': 'Копія'})


@pytest.mark.parametrize('code, subtotal, reason', [
    ('NOPE', 500, 'не існує'),
    ('STAFF50', 500, 'вимкнено'),
    ('BLACKFRIDAY30', 5000, 'минув'),
    ('PARTY15', 500, 'від 1000'),
])
def test_promo_rejections(app, code, subtotal, reason):
    with app.app_context():
        promo, error = orders.check_promo(code, subtotal, today=date(2026, 11, 23))
    assert promo is None and reason in error


def test_promo_is_case_insensitive_and_limited(app):
    with app.app_context():
        promo, error = orders.check_promo('welcome10', 100)
        assert promo['code'] == 'WELCOME10' and error is None
        get_db().execute("UPDATE promo_codes SET max_uses = used_count WHERE code = 'WELCOME10'")
        get_db().commit()
        assert 'максимальну' in orders.check_promo('WELCOME10', 100)[1]


def test_create_order_is_one_transaction(app):
    with app.app_context():
        dobble = catalog.get_product_by_slug('dobble')
        customer = {'name': 'Нова Людина', 'email': 'new@example.com', 'phone': '+380670000000', 'city': 'Луцьк'}
        order_id = orders.create_order(customer, 'Луцьк, НП 1', '', {str(dobble['id']): 3}, 'WELCOME10')
        order, items = orders.get_order(order_id)
        assert order['subtotal'] == 1170 and order['discount'] == 117 and order['total'] == 1053
        assert items[0]['quantity'] == 3 and items[0]['unit_price'] == 390
        assert catalog.get_product(dobble['id'])['stock'] == dobble['stock'] - 3
        assert orders.find_promo('WELCOME10')['used_count'] == 2


def test_create_order_fails_when_out_of_stock_and_changes_nothing(app):
    with app.app_context():
        mars = catalog.get_product_by_slug('terraforming-mars')
        before = get_db().execute('SELECT COUNT(*) FROM orders').fetchone()[0]
        with pytest.raises(orders.OrderError, match='на складі'):
            orders.create_order({'name': 'X Y', 'email': 'x@example.com', 'phone': '+380670000000', 'city': 'Київ'},
                                'Київ', '', {str(mars['id']): 99})
        assert get_db().execute('SELECT COUNT(*) FROM orders').fetchone()[0] == before
        assert customers.find_by_email('x@example.com') is None


def test_upsert_customer_reuses_existing_email(app):
    with app.app_context():
        before = len(customers.list_customers())
        cid = customers.upsert_customer({'name': 'Олена К.', 'email': 'olena.koval@example.com',
                                         'phone': '+380671112233', 'city': 'Луцьк'})
        get_db().commit()
        assert len(customers.list_customers()) == before
        assert customers.get_customer(cid)['name'] == 'Олена К.'


def test_delete_order_cascades_items(app):
    with app.app_context():
        orders.delete_order(1)
        assert get_db().execute('SELECT COUNT(*) FROM order_items WHERE order_id = 1').fetchone()[0] == 0


def test_customer_list_aggregates_orders(app):
    with app.app_context():
        olena = next(c for c in customers.list_customers() if c['email'] == 'olena.koval@example.com')
    assert olena['orders_count'] == 2 and olena['orders_total'] > 0


def test_stats_excludes_cancelled_revenue(app):
    with app.app_context():
        data = orders.stats()
        cancelled = get_db().execute("SELECT SUM(total) FROM orders WHERE status = 'Скасоване'").fetchone()[0]
        all_total = get_db().execute('SELECT SUM(total) FROM orders').fetchone()[0]
    assert data['orders'] == 6 and data['revenue'] == pytest.approx(all_total - cancelled)
    assert data['unread_feedback'] == 2
