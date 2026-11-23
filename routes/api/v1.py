"""REST API версії 1: /api/v1/...

Відповіді — «плоскі» JSON-об’єкти та списки; помилки — {"error": "...", "details": {...}}.
Версія підтримується для сумісності, нові клієнти мають використовувати v2
(про це повідомляють заголовки Deprecation і Link у кожній відповіді v1).
Опис кожного ендпоінта у форматі OpenAPI (YAML у docstring) читає flasgger і показує на /apidocs/.
"""
from flask import Blueprint, jsonify, request, url_for

from models import catalog, customers, feedback, orders

from . import services
from .common import created, json_body, require_api_key

api_v1 = Blueprint('api_v1', __name__, url_prefix='/api/v1')


@api_v1.after_request
def mark_as_previous_version(response):
    response.headers['Deprecation'] = 'true'
    response.headers['Link'] = '</api/v2/>; rel="successor-version"'
    return response


# ------------------------------------------------------------------ серіалізація

def product_json(row):
    data = dict(row)
    data['is_bestseller'] = bool(data['is_bestseller'])
    return data


def order_json(order, items=None):
    data = dict(order)
    if items is not None:
        data['items'] = [dict(item) for item in items]
    return data


# ------------------------------------------------------------------ службові

@api_v1.get('/health')
def health():
    """Перевірка, що API працює
    ---
    tags: [Службові]
    responses:
      200:
        description: Сервіс доступний
        schema:
          type: object
          properties:
            status: {type: string, example: ok}
            version: {type: string, example: v1}
    """
    return jsonify({'status': 'ok', 'version': 'v1'})


@api_v1.get('/stats')
@require_api_key
def stats():
    """Статистика магазину (кількість замовлень за статусами, виручка)
    ---
    tags: [Службові]
    security: [{ApiKeyAuth: []}]
    responses:
      200: {description: Показники магазину}
      401: {description: Немає або неправильний ключ API, schema: {$ref: '#/definitions/ErrorV1'}}
    """
    return jsonify(orders.stats())


# ------------------------------------------------------------------ товари

@api_v1.get('/products')
def list_products():
    """Список товарів з пошуком, фільтрами й сортуванням
    ---
    tags: [Товари]
    parameters:
      - {name: q, in: query, type: string, description: Пошук у назві й описі (без урахування регістру)}
      - {name: category, in: query, type: string, description: 'slug категорії; для батьківської — разом із підкатегоріями', example: strategy}
      - {name: min_price, in: query, type: number}
      - {name: max_price, in: query, type: number}
      - {name: players, in: query, type: integer, description: Кількість гравців}
      - {name: in_stock, in: query, type: integer, enum: [1], description: 'Лише в наявності'}
      - {name: sort, in: query, type: string, enum: [popular, price_asc, price_desc, name, new], default: popular}
    responses:
      200:
        description: Масив товарів
        schema: {type: array, items: {$ref: '#/definitions/ProductV1'}}
      400: {description: Некоректний параметр (невідома категорія чи сортування), schema: {$ref: '#/definitions/ErrorV1'}}
    """
    products = catalog.search_products(services.product_filters(request.args))
    return jsonify([product_json(p) for p in products])


@api_v1.get('/products/<int:product_id>')
def get_product(product_id):
    """Один товар за id
    ---
    tags: [Товари]
    parameters:
      - {name: product_id, in: path, type: integer, required: true, example: 1}
    responses:
      200: {description: Дані товару, schema: {$ref: '#/definitions/ProductV1'}}
      404: {description: Товар не знайдено, schema: {$ref: '#/definitions/ErrorV1'}}
    """
    return jsonify(product_json(services.get_product(product_id)))


@api_v1.post('/products')
@require_api_key
def create_product():
    """Створити товар
    ---
    tags: [Товари]
    security: [{ApiKeyAuth: []}]
    parameters:
      - {name: body, in: body, required: true, schema: {$ref: '#/definitions/ProductInput'}}
    responses:
      201: {description: Товар створено (заголовок Location — адреса нового товару), schema: {$ref: '#/definitions/ProductV1'}}
      400: {description: Помилки валідації по полях, schema: {$ref: '#/definitions/ErrorV1'}}
      401: {description: Немає ключа API}
      409: {description: Такий slug уже існує}
      415: {description: Тіло запиту не JSON}
    """
    product = services.create_product(json_body())
    return created(product_json(product), url_for('api_v1.get_product', product_id=product['id']))


@api_v1.put('/products/<int:product_id>')
@require_api_key
def replace_product(product_id):
    """Повністю замінити товар (потрібні всі обов’язкові поля)
    ---
    tags: [Товари]
    security: [{ApiKeyAuth: []}]
    parameters:
      - {name: product_id, in: path, type: integer, required: true}
      - {name: body, in: body, required: true, schema: {$ref: '#/definitions/ProductInput'}}
    responses:
      200: {description: Оновлений товар, schema: {$ref: '#/definitions/ProductV1'}}
      400: {description: Помилки валідації, schema: {$ref: '#/definitions/ErrorV1'}}
      401: {description: Немає ключа API}
      404: {description: Товар не знайдено}
      409: {description: Такий slug уже існує}
    """
    return jsonify(product_json(services.update_product(product_id, json_body(), partial=False)))


@api_v1.patch('/products/<int:product_id>')
@require_api_key
def patch_product(product_id):
    """Частково змінити товар (лише передані поля, наприклад ціну чи залишок)
    ---
    tags: [Товари]
    security: [{ApiKeyAuth: []}]
    parameters:
      - {name: product_id, in: path, type: integer, required: true}
      - name: body
        in: body
        required: true
        schema:
          type: object
          example: {price: 999.0, stock: 12}
    responses:
      200: {description: Оновлений товар, schema: {$ref: '#/definitions/ProductV1'}}
      400: {description: Помилки валідації, schema: {$ref: '#/definitions/ErrorV1'}}
      401: {description: Немає ключа API}
      404: {description: Товар не знайдено}
    """
    return jsonify(product_json(services.update_product(product_id, json_body(), partial=True)))


@api_v1.delete('/products/<int:product_id>')
@require_api_key
def delete_product(product_id):
    """Видалити товар
    ---
    tags: [Товари]
    security: [{ApiKeyAuth: []}]
    parameters:
      - {name: product_id, in: path, type: integer, required: true}
    responses:
      204: {description: Видалено (порожнє тіло)}
      401: {description: Немає ключа API}
      404: {description: Товар не знайдено}
      409: {description: Товар є в замовленнях — видалення заборонене}
    """
    services.delete_product(product_id)
    return '', 204


# ------------------------------------------------------------------ категорії

@api_v1.get('/categories')
def list_categories():
    """Усі категорії (плоский список з parent_id і кількістю товарів)
    ---
    tags: [Категорії]
    responses:
      200:
        description: Масив категорій
        schema: {type: array, items: {$ref: '#/definitions/Category'}}
    """
    return jsonify([dict(c) for c in catalog.list_categories()])


@api_v1.get('/categories/<int:category_id>')
def get_category(category_id):
    """Одна категорія
    ---
    tags: [Категорії]
    parameters:
      - {name: category_id, in: path, type: integer, required: true}
    responses:
      200: {description: Категорія, schema: {$ref: '#/definitions/Category'}}
      404: {description: Категорію не знайдено}
    """
    return jsonify(dict(services.get_category(category_id)))


@api_v1.post('/categories')
@require_api_key
def create_category():
    """Створити категорію (parent_id — для підкатегорії)
    ---
    tags: [Категорії]
    security: [{ApiKeyAuth: []}]
    parameters:
      - {name: body, in: body, required: true, schema: {$ref: '#/definitions/CategoryInput'}}
    responses:
      201: {description: Створено, schema: {$ref: '#/definitions/Category'}}
      400: {description: Помилки валідації}
      401: {description: Немає ключа API}
      409: {description: Такий slug уже існує}
    """
    category = services.create_category(json_body())
    return created(dict(category), url_for('api_v1.get_category', category_id=category['id']))


@api_v1.delete('/categories/<int:category_id>')
@require_api_key
def delete_category(category_id):
    """Видалити категорію
    ---
    tags: [Категорії]
    security: [{ApiKeyAuth: []}]
    parameters:
      - {name: category_id, in: path, type: integer, required: true}
    responses:
      204: {description: Видалено}
      404: {description: Категорію не знайдено}
      409: {description: У категорії є товари або підкатегорії}
    """
    services.delete_category(category_id)
    return '', 204


# ------------------------------------------------------------------ замовлення

@api_v1.get('/orders')
@require_api_key
def list_orders():
    """Список замовлень (новіші першими)
    ---
    tags: [Замовлення]
    security: [{ApiKeyAuth: []}]
    parameters:
      - {name: status, in: query, type: string, enum: [Нове, Підтверджене, Відправлене, Доставлене, Скасоване]}
    responses:
      200: {description: Масив замовлень, schema: {type: array, items: {$ref: '#/definitions/Order'}}}
      400: {description: Невідомий статус}
      401: {description: Немає ключа API}
    """
    status = services.order_status_filter(request.args)
    return jsonify([order_json(o) for o in orders.list_orders(status=status)])


@api_v1.get('/orders/<int:order_id>')
@require_api_key
def get_order(order_id):
    """Замовлення з позиціями
    ---
    tags: [Замовлення]
    security: [{ApiKeyAuth: []}]
    parameters:
      - {name: order_id, in: path, type: integer, required: true}
    responses:
      200: {description: Замовлення та items, schema: {$ref: '#/definitions/Order'}}
      401: {description: Немає ключа API}
      404: {description: Замовлення не знайдено}
    """
    return jsonify(order_json(*services.get_order(order_id)))


@api_v1.post('/orders')
def create_order():
    """Оформити замовлення (публічний ендпоінт — як кнопка «Оформити» на сайті)
    ---
    tags: [Замовлення]
    description: Ціни беруться з бази, залишки списуються, клієнт знаходиться за email або створюється. Усе — однією транзакцією.
    parameters:
      - {name: body, in: body, required: true, schema: {$ref: '#/definitions/OrderInput'}}
    responses:
      201: {description: Замовлення створено, schema: {$ref: '#/definitions/Order'}}
      400: {description: Помилки валідації (поля клієнта, позиції, промокод), schema: {$ref: '#/definitions/ErrorV1'}}
      409: {description: Недостатньо товару на складі}
      415: {description: Тіло запиту не JSON}
    """
    order, items = services.create_order(json_body())
    return created(order_json(order, items), url_for('api_v1.get_order', order_id=order['id']))


@api_v1.patch('/orders/<int:order_id>')
@require_api_key
def change_order_status(order_id):
    """Змінити статус замовлення
    ---
    tags: [Замовлення]
    security: [{ApiKeyAuth: []}]
    parameters:
      - {name: order_id, in: path, type: integer, required: true}
      - {name: body, in: body, required: true, schema: {$ref: '#/definitions/StatusInput'}}
    responses:
      200: {description: Оновлене замовлення, schema: {$ref: '#/definitions/Order'}}
      400: {description: Недопустимий статус}
      401: {description: Немає ключа API}
      404: {description: Замовлення не знайдено}
    """
    return jsonify(order_json(*services.change_status(order_id, json_body())))


@api_v1.delete('/orders/<int:order_id>')
@require_api_key
def delete_order(order_id):
    """Видалити замовлення (позиції видаляються каскадно)
    ---
    tags: [Замовлення]
    security: [{ApiKeyAuth: []}]
    parameters:
      - {name: order_id, in: path, type: integer, required: true}
    responses:
      204: {description: Видалено}
      401: {description: Немає ключа API}
      404: {description: Замовлення не знайдено}
    """
    services.delete_order(order_id)
    return '', 204


# ------------------------------------------------------------------ клієнти

@api_v1.get('/customers')
@require_api_key
def list_customers():
    """Клієнти з кількістю й сумою замовлень
    ---
    tags: [Клієнти]
    security: [{ApiKeyAuth: []}]
    parameters:
      - {name: q, in: query, type: string, description: Пошук за іменем, email або телефоном}
    responses:
      200: {description: Масив клієнтів, schema: {type: array, items: {$ref: '#/definitions/Customer'}}}
      401: {description: Немає ключа API}
    """
    return jsonify([dict(c) for c in customers.list_customers(request.args.get('q', '').strip()[:80])])


@api_v1.get('/customers/<int:customer_id>')
@require_api_key
def get_customer(customer_id):
    """Клієнт та історія його замовлень
    ---
    tags: [Клієнти]
    security: [{ApiKeyAuth: []}]
    parameters:
      - {name: customer_id, in: path, type: integer, required: true}
    responses:
      200: {description: Клієнт з полем orders}
      401: {description: Немає ключа API}
      404: {description: Клієнта не знайдено}
    """
    customer, history = services.get_customer(customer_id)
    return jsonify({**dict(customer), 'orders': [order_json(o) for o in history]})


# ------------------------------------------------------------------ відгуки й промокоди

@api_v1.get('/feedback')
def list_feedback():
    """Відгуки відвідувачів (email не публікується)
    ---
    tags: [Відгуки]
    responses:
      200: {description: Масив відгуків, schema: {type: array, items: {$ref: '#/definitions/Feedback'}}}
    """
    public = ('id', 'name', 'rating', 'message', 'created_at')
    return jsonify([{k: f[k] for k in public} for f in feedback.list_feedback()])


@api_v1.post('/feedback')
def create_feedback():
    """Залишити відгук
    ---
    tags: [Відгуки]
    parameters:
      - {name: body, in: body, required: true, schema: {$ref: '#/definitions/FeedbackInput'}}
    responses:
      201: {description: Відгук збережено, schema: {$ref: '#/definitions/Feedback'}}
      400: {description: Помилки валідації, schema: {$ref: '#/definitions/ErrorV1'}}
    """
    item = services.create_feedback(json_body())
    public = {k: item[k] for k in ('id', 'name', 'rating', 'message', 'created_at')}
    return created(public, url_for('api_v1.list_feedback'))


@api_v1.post('/promo-codes/check')
def check_promo():
    """Перевірити промокод для суми замовлення
    ---
    tags: [Промокоди]
    parameters:
      - {name: body, in: body, required: true, schema: {$ref: '#/definitions/PromoCheckInput'}}
    responses:
      200: {description: 'Результат перевірки (valid=false з причиною, якщо код не діє)', schema: {$ref: '#/definitions/PromoCheckResult'}}
      400: {description: Помилки валідації}
    """
    return jsonify(services.check_promo(json_body()))
