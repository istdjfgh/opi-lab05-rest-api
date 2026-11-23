"""Клієнти (рівень 2): CRUD і прив'язка замовлень."""
from . import execute, get_db, like_pattern, now, query_all, query_one


def list_customers(q=''):
    sql = ('SELECT c.*, COUNT(o.id) AS orders_count, COALESCE(SUM(o.total), 0) AS orders_total '
           'FROM customers c LEFT JOIN orders o ON o.customer_id = c.id AND o.status != \'Скасоване\' ')
    params = []
    if q:
        sql += ("WHERE uk_lower(c.name) LIKE ? ESCAPE '\\' OR uk_lower(c.email) LIKE ? ESCAPE '\\' "
                "OR c.phone LIKE ? ESCAPE '\\' ")
        params = [like_pattern(q)] * 3
    return query_all(sql + 'GROUP BY c.id ORDER BY c.name COLLATE NOCASE', params)


def get_customer(customer_id):
    return query_one('SELECT * FROM customers WHERE id = ?', (customer_id,))


def find_by_email(email):
    return query_one('SELECT * FROM customers WHERE email = ?', (email.strip(),))


def save_customer(data, customer_id=None):
    params = (data['name'], data['email'], data['phone'], data['city'], data['note'])
    if customer_id is None:
        return execute('INSERT INTO customers (name, email, phone, city, note, created_at) VALUES (?, ?, ?, ?, ?, ?)',
                       (*params, now()))
    execute('UPDATE customers SET name = ?, email = ?, phone = ?, city = ?, note = ? WHERE id = ?',
            (*params, customer_id))
    return customer_id


def upsert_customer(data, db=None):
    """Знаходить клієнта за email або створює нового; оновлює ім'я, телефон і місто.

    Викликається всередині транзакції оформлення замовлення, тому приймає те саме з'єднання.
    """
    db = db or get_db()
    row = db.execute('SELECT id FROM customers WHERE email = ?', (data['email'],)).fetchone()
    if row:
        db.execute('UPDATE customers SET name = ?, phone = ?, city = ? WHERE id = ?',
                   (data['name'], data['phone'], data['city'], row['id']))
        return row['id']
    cursor = db.execute(
        'INSERT INTO customers (name, email, phone, city, note, created_at) VALUES (?, ?, ?, ?, ?, ?)',
        (data['name'], data['email'], data['phone'], data['city'], '', now()))
    return cursor.lastrowid


def delete_customer(customer_id):
    """Кидає sqlite3.IntegrityError, якщо в клієнта є замовлення (ON DELETE RESTRICT)."""
    execute('DELETE FROM customers WHERE id = ?', (customer_id,))
