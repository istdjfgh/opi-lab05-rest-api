"""Наповнення бази тестовими даними.

    python seed_data.py          # очистити таблиці й заповнити заново

Дані додаються через ті самі функції моделей, що й у застосунку
(save_category, save_product, create_order, ...), тому seed заодно
перевіряє, що CRUD-функції працюють.
"""
from datetime import datetime, timedelta

from app import create_app
from models import catalog, customers, feedback, get_db, orders

CATEGORIES = [
    # (slug, назва, емодзі, колір, slug батьківської)
    ('family', 'Сімейні', '👨‍👩‍👧', '#1c7ed6', None),
    ('strategy', 'Стратегії', '♟️', '#7048e8', None),
    ('economic', 'Економічні', '💰', '#5f3dc4', 'strategy'),
    ('area-control', 'Контроль територій', '🗺️', '#9c36b5', 'strategy'),
    ('party', 'Вечіркові', '🎉', '#e8590c', None),
    ('coop', 'Кооперативні', '🤝', '#2f9e44', None),
    ('kids', 'Дитячі', '🧸', '#f08c00', None),
]

PRODUCTS = [
    # slug, назва, категорія, ціна, залишок, гравців від/до, вік, хв, емодзі, хіт, короткий опис
    ('carcassonne', 'Каркасон', 'family', 1150, 14, 2, 5, 7, 35, '🏰', 1,
     'Класика: викладайте плитки й будуйте середньовічні міста та дороги.'),
    ('ticket-to-ride', 'Квиток на потяг: Європа', 'family', 1890, 6, 2, 5, 8, 60, '🚂', 1,
     'Прокладайте залізничні маршрути між столицями Європи.'),
    ('terraforming-mars', 'Тераформування Марса', 'economic', 2450, 3, 1, 5, 12, 120, '🪐', 1,
     'Корпорації змагаються, хто зробить Марс придатним для життя.'),
    ('brass', 'Брасс: Бірмінгем', 'economic', 2690, 2, 2, 4, 14, 120, '🏭', 0,
     'Промислова революція: будуйте фабрики, канали й залізниці.'),
    ('kemet', 'Кемет', 'area-control', 2990, 0, 2, 5, 14, 120, '🏺', 0,
     'Боги Єгипту, піраміди та битви за контроль над Нілом.'),
    ('small-world', 'Маленький світ', 'area-control', 1750, 9, 2, 5, 8, 80, '🧝', 0,
     'Фентезійні раси борються за місце на тісній мапі.'),
    ('codenames', 'Кодові імена', 'party', 590, 25, 2, 8, 10, 15, '🕵️', 1,
     'Капітани підказують одним словом, команди вгадують агентів.'),
    ('alias', 'Аліас', 'party', 450, 18, 4, 12, 12, 40, '🗣️', 0,
     'Поясніть слово, не називаючи його, поки біжить пісочний годинник.'),
    ('pandemic', 'Пандемія', 'coop', 1390, 7, 2, 4, 8, 45, '🧬', 0,
     'Разом рятуйте світ від чотирьох хвороб, поки не пізно.'),
    ('spirit-island', 'Острів духів', 'coop', 2890, 4, 1, 4, 13, 120, '🌋', 0,
     'Духи острова об’єднуються проти колонізаторів.'),
    ('dobble', 'Доббль', 'kids', 390, 30, 2, 8, 6, 15, '👀', 0,
     'Знайди однаковий символ на двох картках швидше за всіх.'),
    ('mysterium-kids', 'Містеріум Кідс', 'kids', 990, 1, 2, 6, 6, 30, '👻', 0,
     'Привид підказує мелодіями, де сховано скарб.'),
]

CUSTOMERS = [
    ('Олена Коваль', 'olena.koval@example.com', '+380671112233', 'Луцьк'),
    ('Андрій Мельник', 'andrii.melnyk@example.com', '+380502223344', 'Київ'),
    ('Ірина Шевчук', 'iryna.shevchuk@example.com', '+380933334455', 'Львів'),
    ('Максим Бондар', 'maksym.bondar@example.com', '+380964445566', 'Рівне'),
    ('Софія Ткач', 'sofiia.tkach@example.com', '+380675556677', 'Луцьк'),
]

PROMOS = [
    # код, %, мін. сума, діє до, ліміт, активний
    ('WELCOME10', 10, 0, None, None, 1),
    ('PARTY15', 15, 1000, '2027-12-31', 100, 1),
    ('BLACKFRIDAY30', 30, 2000, '2025-11-30', 50, 1),   # прострочений — для перевірки
    ('STAFF50', 50, 0, None, 5, 0),                    # вимкнений
]

FEEDBACK = [
    ('Олена', 'olena.koval@example.com', 5, 'Замовляла «Каркасон» на подарунок — доставили наступного дня, все запаковано ідеально.', 1),
    ('Андрій', 'andrii.melnyk@example.com', 5, 'Порадили «Тераформування Марса», граємо вже третій вечір поспіль. Дякую за консультацію!', 1),
    ('Ірина', 'iryna.shevchuk@example.com', 4, 'Великий вибір вечіркових ігор. Хотілося б більше дитячих новинок.', 0),
    ('Максим', 'maksym.bondar@example.com', 5, 'Ігротека по п’ятницях — топ! Познайомився з новою компанією.', 0),
]

# (індекс клієнта, {slug: кількість}, промокод, статус, днів тому)
ORDERS = [
    (0, {'carcassonne': 1, 'dobble': 2}, 'WELCOME10', 'Доставлене', 20),
    (1, {'terraforming-mars': 1}, None, 'Доставлене', 14),
    (2, {'codenames': 2, 'alias': 1}, 'PARTY15', 'Відправлене', 6),
    (3, {'pandemic': 1, 'small-world': 1}, None, 'Підтверджене', 3),
    (4, {'ticket-to-ride': 1}, None, 'Скасоване', 2),
    (0, {'spirit-island': 1}, None, 'Нове', 0),
]

TABLES = ('order_items', 'orders', 'promo_codes', 'feedback', 'customers', 'products', 'categories')


def clear():
    db = get_db()
    with db:
        for table in TABLES:          # спочатку дочірні таблиці — інакше спрацює FOREIGN KEY
            db.execute(f'DELETE FROM {table}')
        db.execute('DELETE FROM sqlite_sequence')


def seed():
    clear()
    category_ids = {}
    for slug, name, emoji, color, parent in CATEGORIES:
        category_ids[slug] = catalog.save_category({
            'name': name, 'slug': slug, 'emoji': emoji, 'color': color,
            'parent_id': category_ids.get(parent),
        })

    product_ids = {}
    for (slug, name, cat, price, stock, pmin, pmax, age, minutes, emoji, hit, short) in PRODUCTS:
        product_ids[slug] = catalog.save_product({
            'name': name, 'slug': slug, 'category_id': category_ids[cat], 'price': price, 'stock': stock,
            'players_min': pmin, 'players_max': pmax, 'age': age, 'minutes': minutes, 'emoji': emoji,
            'short': short, 'description': short + ' Повні правила українською, усі компоненти в коробці.',
            'is_bestseller': hit,
        })

    for code, percent, min_total, valid_until, max_uses, active in PROMOS:
        orders.save_promo({'code': code, 'discount_percent': percent, 'min_total': min_total,
                           'valid_until': valid_until, 'max_uses': max_uses, 'is_active': active})

    for name, email, rating, message, is_read in FEEDBACK:
        feedback_id = feedback.add_feedback(name, email, rating, message)
        feedback.mark_read(feedback_id, bool(is_read))

    db = get_db()
    for index, items, promo, status, days_ago in ORDERS:
        name, email, phone, city = CUSTOMERS[index]
        cart = {str(product_ids[slug]): qty for slug, qty in items.items()}
        order_id = orders.create_order({'name': name, 'email': email, 'phone': phone, 'city': city},
                                       f'{city}, відділення Нової пошти №{index + 3}', '', cart, promo)
        created = (datetime.now() - timedelta(days=days_ago, hours=index)).strftime('%Y-%m-%d %H:%M:%S')
        with db:
            db.execute('UPDATE orders SET status = ?, created_at = ? WHERE id = ?', (status, created, order_id))

    # Клієнт без замовлень (створений менеджером вручну)
    customers.save_customer({'name': 'Тарас Гончар', 'email': 'taras.honchar@example.com', 'phone': '+380981234567',
                             'city': 'Ковель', 'note': 'Цікавиться турнірами з «Каркасону».'})


if __name__ == '__main__':
    application = create_app()
    with application.app_context():
        seed()
        counts = {t: get_db().execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0] for t in TABLES}
    print('Базу заповнено:', ', '.join(f'{t}={n}' for t, n in counts.items()))
