"""Категорії (з вкладеністю) і товари: CRUD, пошук і фільтрація."""
from . import execute, like_pattern, now, query_all, query_one

PRODUCT_FIELDS = ('name', 'slug', 'category_id', 'price', 'stock', 'players_min', 'players_max',
                  'age', 'minutes', 'emoji', 'short', 'description', 'is_bestseller')

# Сортування: ключ із запиту -> безпечний фрагмент SQL (значення від користувача в SQL не потрапляє)
SORT_OPTIONS = {
    'popular': ('Спочатку популярні', 'p.is_bestseller DESC, p.name COLLATE NOCASE'),
    'price_asc': ('Спочатку дешевші', 'p.price ASC'),
    'price_desc': ('Спочатку дорожчі', 'p.price DESC'),
    'name': ('За назвою', 'p.name COLLATE NOCASE'),
    'new': ('Новинки', 'p.id DESC'),
}


# ------------------------------------------------------------------ категорії

def list_categories():
    """Усі категорії з назвою батьківської та кількістю товарів."""
    return query_all(
        'SELECT c.*, parent.name AS parent_name, '
        '(SELECT COUNT(*) FROM products p WHERE p.category_id = c.id) AS products_count, '
        '(SELECT COUNT(*) FROM categories ch WHERE ch.parent_id = c.id) AS children_count '
        'FROM categories c LEFT JOIN categories parent ON parent.id = c.parent_id '
        'ORDER BY COALESCE(parent.name, c.name), c.parent_id IS NOT NULL, c.name'
    )


def category_tree():
    """Дерево [(категорія, [підкатегорії])] для меню каталогу."""
    rows = list_categories()
    roots = [row for row in rows if row['parent_id'] is None]
    return [(root, [row for row in rows if row['parent_id'] == root['id']]) for root in roots]


def get_category(category_id):
    return query_one('SELECT * FROM categories WHERE id = ?', (category_id,))


def get_category_by_slug(slug):
    return query_one('SELECT * FROM categories WHERE slug = ?', (slug,))


def category_with_descendants(category_id):
    """id категорії та всіх її нащадків (рекурсивний CTE) — щоб фільтр «Стратегії» показав і підкатегорії."""
    rows = query_all(
        'WITH RECURSIVE tree(id) AS ('
        '  SELECT id FROM categories WHERE id = ? '
        '  UNION ALL SELECT c.id FROM categories c JOIN tree ON c.parent_id = tree.id'
        ') SELECT id FROM tree', (category_id,))
    return [row['id'] for row in rows]


def save_category(data, category_id=None):
    params = (data['name'], data['slug'], data['emoji'], data['color'], data['parent_id'])
    if category_id is None:
        return execute('INSERT INTO categories (name, slug, emoji, color, parent_id) VALUES (?, ?, ?, ?, ?)', params)
    execute('UPDATE categories SET name = ?, slug = ?, emoji = ?, color = ?, parent_id = ? WHERE id = ?',
            (*params, category_id))
    return category_id


def delete_category(category_id):
    """Кидає sqlite3.IntegrityError, якщо в категорії є товари або підкатегорії (ON DELETE RESTRICT)."""
    execute('DELETE FROM categories WHERE id = ?', (category_id,))


# ------------------------------------------------------------------- товари

PRODUCT_SELECT = (
    'SELECT p.*, c.name AS category_name, c.slug AS category_slug, c.emoji AS category_emoji, '
    'c.color AS category_color FROM products p JOIN categories c ON c.id = p.category_id'
)


def search_products(filters=None):
    """Пошук і фільтрація товарів (рівень 3).

    filters: q (текст), category_id, min_price, max_price, players, in_stock, sort.
    Усі значення передаються як параметри запиту — SQL-ін'єкція неможлива.
    """
    filters = filters or {}
    where, params = [], []

    if filters.get('q'):
        where.append("(uk_lower(p.name) LIKE ? ESCAPE '\\' OR uk_lower(p.short) LIKE ? ESCAPE '\\' "
                     "OR uk_lower(p.description) LIKE ? ESCAPE '\\')")
        params += [like_pattern(filters['q'])] * 3
    if filters.get('category_id'):
        ids = category_with_descendants(filters['category_id'])
        where.append(f'p.category_id IN ({",".join("?" * len(ids))})')
        params += ids
    if filters.get('min_price') is not None:
        where.append('p.price >= ?')
        params.append(filters['min_price'])
    if filters.get('max_price') is not None:
        where.append('p.price <= ?')
        params.append(filters['max_price'])
    if filters.get('players'):
        where.append('p.players_min <= ? AND p.players_max >= ?')
        params += [filters['players'], filters['players']]
    if filters.get('in_stock'):
        where.append('p.stock > 0')

    sql = PRODUCT_SELECT
    if where:
        sql += ' WHERE ' + ' AND '.join(where)
    sql += ' ORDER BY ' + SORT_OPTIONS.get(filters.get('sort'), SORT_OPTIONS['popular'])[1]
    return query_all(sql, params)


def bestsellers(limit=3):
    return query_all(PRODUCT_SELECT + ' WHERE p.is_bestseller = 1 ORDER BY p.id LIMIT ?', (limit,))


def get_product(product_id):
    return query_one(PRODUCT_SELECT + ' WHERE p.id = ?', (product_id,))


def get_product_by_slug(slug):
    return query_one(PRODUCT_SELECT + ' WHERE p.slug = ?', (slug,))


def get_products_by_ids(ids):
    ids = list(ids)
    if not ids:
        return []
    return query_all(PRODUCT_SELECT + f' WHERE p.id IN ({",".join("?" * len(ids))}) ORDER BY p.name', ids)


def related_products(product, limit=3):
    return query_all(PRODUCT_SELECT + ' WHERE p.category_id = ? AND p.id != ? LIMIT ?',
                     (product['category_id'], product['id'], limit))


def save_product(data, product_id=None):
    values = tuple(data[field] for field in PRODUCT_FIELDS)
    if product_id is None:
        columns = ', '.join(PRODUCT_FIELDS)
        return execute(f'INSERT INTO products ({columns}, created_at) VALUES ({", ".join("?" * len(PRODUCT_FIELDS))}, ?)',
                       (*values, now()))
    assignments = ', '.join(f'{field} = ?' for field in PRODUCT_FIELDS)
    execute(f'UPDATE products SET {assignments} WHERE id = ?', (*values, product_id))
    return product_id


def delete_product(product_id):
    """Кидає sqlite3.IntegrityError, якщо товар є в замовленнях (ON DELETE RESTRICT)."""
    execute('DELETE FROM products WHERE id = ?', (product_id,))


def price_range():
    row = query_one('SELECT MIN(price) AS low, MAX(price) AS high FROM products')
    return (row['low'] or 0, row['high'] or 0)
