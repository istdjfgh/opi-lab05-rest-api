"""Замовлення, позиції замовлень, статуси та промокоди."""
from datetime import date

from . import execute, get_db, now, query_all, query_one
from .catalog import get_products_by_ids
from .customers import upsert_customer

ORDER_STATUSES = ['Нове', 'Підтверджене', 'Відправлене', 'Доставлене', 'Скасоване']
STATUS_COLORS = {
    'Нове': '#1c7ed6', 'Підтверджене': '#7048e8', 'Відправлене': '#f08c00',
    'Доставлене': '#2f9e44', 'Скасоване': '#868e96',
}


class OrderError(ValueError):
    """Помилка оформлення замовлення, текст якої можна показати користувачу."""


# ------------------------------------------------------------------ промокоди

def list_promos():
    return query_all('SELECT * FROM promo_codes ORDER BY is_active DESC, code')


def get_promo(promo_id):
    return query_one('SELECT * FROM promo_codes WHERE id = ?', (promo_id,))


def find_promo(code):
    return query_one('SELECT * FROM promo_codes WHERE code = ?', (code.strip(),))


def check_promo(code, subtotal, today=None):
    """Повертає (промокод, None) або (None, причина відмови)."""
    promo = find_promo(code) if code else None
    today = (today or date.today()).isoformat()
    if promo is None:
        return None, 'Такого промокоду не існує.'
    if not promo['is_active']:
        return None, 'Промокод вимкнено.'
    if promo['valid_until'] and promo['valid_until'] < today:
        return None, 'Термін дії промокоду минув.'
    if promo['max_uses'] is not None and promo['used_count'] >= promo['max_uses']:
        return None, 'Промокод уже використано максимальну кількість разів.'
    if subtotal < promo['min_total']:
        return None, f'Промокод діє для замовлень від {promo["min_total"]:.0f} грн.'
    return promo, None


def calc_discount(subtotal, promo):
    return round(subtotal * promo['discount_percent'] / 100, 2) if promo else 0.0


def save_promo(data, promo_id=None):
    params = (data['code'], data['discount_percent'], data['min_total'], data['valid_until'],
              data['max_uses'], data['is_active'])
    if promo_id is None:
        return execute('INSERT INTO promo_codes (code, discount_percent, min_total, valid_until, max_uses, is_active) '
                       'VALUES (?, ?, ?, ?, ?, ?)', params)
    execute('UPDATE promo_codes SET code = ?, discount_percent = ?, min_total = ?, valid_until = ?, '
            'max_uses = ?, is_active = ? WHERE id = ?', (*params, promo_id))
    return promo_id


def toggle_promo(promo_id):
    execute('UPDATE promo_codes SET is_active = 1 - is_active WHERE id = ?', (promo_id,))


def delete_promo(promo_id):
    execute('DELETE FROM promo_codes WHERE id = ?', (promo_id,))


# ------------------------------------------------------------------ кошик → замовлення

def cart_lines(cart):
    """Кошик із сесії {id: кількість} -> рядки з товарами з БД і проміжна сума."""
    products = get_products_by_ids(int(pid) for pid in cart)
    lines = [{'product': p, 'quantity': cart[str(p['id'])], 'line_total': p['price'] * cart[str(p['id'])]}
             for p in products]
    return lines, round(sum(line['line_total'] for line in lines), 2)


def create_order(customer, address, comment, cart, promo_code=None):
    """Створює замовлення однією транзакцією і повертає його id.

    Ціни беруться з БД, а не з браузера; перевіряється наявність на складі;
    залишки зменшуються; лічильник промокоду збільшується.
    Якщо щось піде не так — відкочується все (rollback).
    """
    lines, subtotal = cart_lines(cart)
    if not lines:
        raise OrderError('Кошик порожній.')
    for line in lines:
        if line['quantity'] > line['product']['stock']:
            raise OrderError(f'«{line["product"]["name"]}»: на складі лише {line["product"]["stock"]} шт.')

    promo, reason = check_promo(promo_code, subtotal) if promo_code else (None, None)
    if promo_code and promo is None:
        raise OrderError(reason)
    discount = calc_discount(subtotal, promo)

    db = get_db()
    with db:
        customer_id = upsert_customer(customer, db=db)
        cursor = db.execute(
            'INSERT INTO orders (customer_id, address, comment, status, subtotal, discount, total, promo_code, created_at) '
            'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (customer_id, address, comment, ORDER_STATUSES[0], subtotal, discount,
             round(subtotal - discount, 2), promo['code'] if promo else None, now()))
        order_id = cursor.lastrowid
        db.executemany(
            'INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES (?, ?, ?, ?)',
            [(order_id, line['product']['id'], line['quantity'], line['product']['price']) for line in lines])
        db.executemany('UPDATE products SET stock = stock - ? WHERE id = ?',
                       [(line['quantity'], line['product']['id']) for line in lines])
        if promo:
            db.execute('UPDATE promo_codes SET used_count = used_count + 1 WHERE id = ?', (promo['id'],))
    return order_id


# ------------------------------------------------------------------ читання й керування

ORDER_SELECT = (
    'SELECT o.*, c.name AS customer_name, c.email AS customer_email, c.phone AS customer_phone, '
    '(SELECT SUM(quantity) FROM order_items WHERE order_id = o.id) AS items_count '
    'FROM orders o JOIN customers c ON c.id = o.customer_id'
)


def list_orders(status=None, customer_id=None):
    where, params = [], []
    if status:
        where.append('o.status = ?')
        params.append(status)
    if customer_id:
        where.append('o.customer_id = ?')
        params.append(customer_id)
    sql = ORDER_SELECT + (' WHERE ' + ' AND '.join(where) if where else '') + ' ORDER BY o.id DESC'
    return query_all(sql, params)


def get_order(order_id):
    """Замовлення та його позиції (JOIN order_items -> products)."""
    order = query_one(ORDER_SELECT + ' WHERE o.id = ?', (order_id,))
    items = query_all(
        'SELECT oi.*, p.name, p.slug, p.emoji, oi.quantity * oi.unit_price AS line_total '
        'FROM order_items oi JOIN products p ON p.id = oi.product_id WHERE oi.order_id = ? ORDER BY oi.id',
        (order_id,))
    return order, items


def update_status(order_id, status):
    if status not in ORDER_STATUSES:
        raise ValueError(f'Невідомий статус: {status}')
    execute('UPDATE orders SET status = ? WHERE id = ?', (status, order_id))


def delete_order(order_id):
    """Позиції видаляються каскадно (ON DELETE CASCADE)."""
    execute('DELETE FROM orders WHERE id = ?', (order_id,))


def stats():
    """Показники для головної сторінки адмін-панелі."""
    by_status = {row['status']: row['n'] for row in
                 query_all('SELECT status, COUNT(*) AS n FROM orders GROUP BY status')}
    revenue = query_one("SELECT COALESCE(SUM(total), 0) AS s FROM orders WHERE status != 'Скасоване'")['s']
    return {
        'orders': sum(by_status.values()),
        'by_status': by_status,
        'revenue': revenue,
        'products': query_one('SELECT COUNT(*) AS n FROM products')['n'],
        'low_stock': query_one('SELECT COUNT(*) AS n FROM products WHERE stock <= 2')['n'],
        'customers': query_one('SELECT COUNT(*) AS n FROM customers')['n'],
        'unread_feedback': query_one('SELECT COUNT(*) AS n FROM feedback WHERE is_read = 0')['n'],
    }
