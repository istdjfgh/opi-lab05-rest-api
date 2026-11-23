"""REST API версії 2: /api/v2/...

Що змінилося порівняно з v1 (саме через ці «ламаючі» зміни потрібна нова версія):
  * відповіді загорнуті в конверт {"data": ..., "meta": ..., "links": ...};
  * списки розбиті на сторінки (?page=, ?per_page=), у meta — total і pages;
  * ціна — об’єкт {"amount": 1150.0, "currency": "UAH"}, гравці — {"min": 2, "max": 5};
  * категорія вкладена в товар об’єктом, у кожного ресурсу є посилання links.self;
  * помилки — {"error": {"status", "code", "message", "fields"}}.
Правила й перевірки ті самі, що у v1 (services.py).
"""
import math

from flask import Blueprint, jsonify, request, url_for

from models import catalog, orders

from . import services
from .common import created, int_arg, json_body, require_api_key

api_v2 = Blueprint('api_v2', __name__, url_prefix='/api/v2')

CURRENCY = 'UAH'
DEFAULT_PER_PAGE = 10
MAX_PER_PAGE = 50


# ------------------------------------------------------------------ серіалізація

def product_json(p):
    return {
        'id': p['id'],
        'name': p['name'],
        'slug': p['slug'],
        'category': {'id': p['category_id'], 'name': p['category_name'], 'slug': p['category_slug']},
        'price': {'amount': p['price'], 'currency': CURRENCY},
        'stock': p['stock'],
        'in_stock': p['stock'] > 0,
        'players': {'min': p['players_min'], 'max': p['players_max']},
        'age': p['age'],
        'minutes': p['minutes'],
        'emoji': p['emoji'],
        'short': p['short'],
        'description': p['description'],
        'is_bestseller': bool(p['is_bestseller']),
        'created_at': p['created_at'],
        'links': {
            'self': url_for('api_v2.get_product', product_id=p['id']),
            'html': url_for('shop.product_page', slug=p['slug']),
        },
    }


def order_json(order, items=None):
    data = {
        'id': order['id'],
        'status': order['status'],
        'customer': {'id': order['customer_id'], 'name': order['customer_name'], 'email': order['customer_email']},
        'address': order['address'],
        'comment': order['comment'],
        'totals': {
            'subtotal': order['subtotal'], 'discount': order['discount'], 'total': order['total'],
            'currency': CURRENCY, 'promo_code': order['promo_code'],
        },
        'created_at': order['created_at'],
        'links': {'self': url_for('api_v2.get_order', order_id=order['id'])},
    }
    if items is not None:
        data['items'] = [{
            'product': {'id': i['product_id'], 'name': i['name'],
                        'links': {'self': url_for('api_v2.get_product', product_id=i['product_id'])}},
            'quantity': i['quantity'],
            'unit_price': i['unit_price'],
            'line_total': i['line_total'],
        } for i in items]
    return data


def paginate(rows, serialize, endpoint, **params):
    """Конверт зі сторінкою даних, метаданими й посиланнями на сусідні сторінки."""
    page = int_arg('page', 1, 1, 10**6)
    per_page = int_arg('per_page', DEFAULT_PER_PAGE, 1, MAX_PER_PAGE)
    total = len(rows)
    pages = max(1, math.ceil(total / per_page))
    chunk = rows[(page - 1) * per_page: page * per_page]

    def link(number):
        return url_for(endpoint, page=number, per_page=per_page, **params)

    return jsonify({
        'data': [serialize(row) for row in chunk],
        'meta': {'page': page, 'per_page': per_page, 'total': total, 'pages': pages},
        'links': {
            'self': link(page),
            'first': link(1),
            'last': link(pages),
            'next': link(page + 1) if page < pages else None,
            'prev': link(page - 1) if page > 1 else None,
        },
    })


def active_params(*names):
    """Параметри фільтрів, які треба зберегти в посиланнях пагінації."""
    return {name: request.args[name] for name in names if request.args.get(name)}


# ------------------------------------------------------------------ службові

@api_v2.get('/')
def index():
    """Точка входу v2: перелік ресурсів
    ---
    tags: [Службові]
    responses:
      200: {description: Посилання на колекції ресурсів}
    """
    return jsonify({'data': {'version': 'v2', 'links': {
        'products': url_for('api_v2.list_products'),
        'categories': url_for('api_v2.category_tree'),
        'orders': url_for('api_v2.list_orders'),
        'promo_check': url_for('api_v2.check_promo'),
        'docs': '/apidocs/',
    }}})


# ------------------------------------------------------------------ товари

@api_v2.get('/products')
def list_products():
    """Товари посторінково, з пошуком і фільтрами
    ---
    tags: [Товари]
    parameters:
      - {name: q, in: query, type: string}
      - {name: category, in: query, type: string, example: strategy}
      - {name: min_price, in: query, type: number}
      - {name: max_price, in: query, type: number}
      - {name: players, in: query, type: integer}
      - {name: in_stock, in: query, type: integer, enum: [1]}
      - {name: sort, in: query, type: string, enum: [popular, price_asc, price_desc, name, new]}
      - {name: page, in: query, type: integer, default: 1, minimum: 1}
      - {name: per_page, in: query, type: integer, default: 10, minimum: 1, maximum: 50}
    responses:
      200: {description: 'Сторінка товарів: data, meta (page, per_page, total, pages), links', schema: {$ref: '#/definitions/ProductPageV2'}}
      400: {description: Некоректний параметр, schema: {$ref: '#/definitions/ErrorV2'}}
    """
    rows = catalog.search_products(services.product_filters(request.args))
    params = active_params('q', 'category', 'min_price', 'max_price', 'players', 'in_stock', 'sort')
    return paginate(rows, product_json, 'api_v2.list_products', **params)


@api_v2.get('/products/<int:product_id>')
def get_product(product_id):
    """Товар за id
    ---
    tags: [Товари]
    parameters:
      - {name: product_id, in: path, type: integer, required: true, example: 1}
    responses:
      200: {description: '{"data": товар}', schema: {type: object, properties: {data: {$ref: '#/definitions/ProductV2'}}}}
      404: {description: Товар не знайдено, schema: {$ref: '#/definitions/ErrorV2'}}
    """
    return jsonify({'data': product_json(services.get_product(product_id))})


@api_v2.post('/products')
@require_api_key
def create_product():
    """Створити товар (тіло — як у v1, плоскі поля)
    ---
    tags: [Товари]
    security: [{ApiKeyAuth: []}]
    parameters:
      - {name: body, in: body, required: true, schema: {$ref: '#/definitions/ProductInput'}}
    responses:
      201: {description: Створено}
      400: {description: Помилки валідації, schema: {$ref: '#/definitions/ErrorV2'}}
      401: {description: Немає ключа API, schema: {$ref: '#/definitions/ErrorV2'}}
      409: {description: Такий slug уже існує}
    """
    product = services.create_product(json_body())
    return created({'data': product_json(product)}, url_for('api_v2.get_product', product_id=product['id']))


@api_v2.put('/products/<int:product_id>')
@require_api_key
def replace_product(product_id):
    """Повністю замінити товар
    ---
    tags: [Товари]
    security: [{ApiKeyAuth: []}]
    parameters:
      - {name: product_id, in: path, type: integer, required: true}
      - {name: body, in: body, required: true, schema: {$ref: '#/definitions/ProductInput'}}
    responses:
      200: {description: Оновлено}
      400: {description: Помилки валідації}
      404: {description: Товар не знайдено}
    """
    return jsonify({'data': product_json(services.update_product(product_id, json_body(), partial=False))})


@api_v2.patch('/products/<int:product_id>')
@require_api_key
def patch_product(product_id):
    """Частково змінити товар
    ---
    tags: [Товари]
    security: [{ApiKeyAuth: []}]
    parameters:
      - {name: product_id, in: path, type: integer, required: true}
      - {name: body, in: body, required: true, schema: {type: object, example: {stock: 0}}}
    responses:
      200: {description: Оновлено}
      400: {description: Помилки валідації}
      404: {description: Товар не знайдено}
    """
    return jsonify({'data': product_json(services.update_product(product_id, json_body(), partial=True))})


@api_v2.delete('/products/<int:product_id>')
@require_api_key
def delete_product(product_id):
    """Видалити товар
    ---
    tags: [Товари]
    security: [{ApiKeyAuth: []}]
    parameters:
      - {name: product_id, in: path, type: integer, required: true}
    responses:
      204: {description: Видалено}
      404: {description: Товар не знайдено}
      409: {description: Товар є в замовленнях}
    """
    services.delete_product(product_id)
    return '', 204


# ------------------------------------------------------------------ категорії

@api_v2.get('/categories')
def category_tree():
    """Дерево категорій (підкатегорії вкладені в children)
    ---
    tags: [Категорії]
    responses:
      200: {description: '{"data": [категорія з children]}'}
    """
    def node(category, children=()):
        return {
            'id': category['id'], 'name': category['name'], 'slug': category['slug'],
            'emoji': category['emoji'], 'color': category['color'],
            'products_count': category['products_count'],
            'links': {'products': url_for('api_v2.list_products', category=category['slug'])},
            'children': [node(child) for child in children],
        }
    return jsonify({'data': [node(root, children) for root, children in catalog.category_tree()]})


# ------------------------------------------------------------------ замовлення

@api_v2.get('/orders')
@require_api_key
def list_orders():
    """Замовлення посторінково
    ---
    tags: [Замовлення]
    security: [{ApiKeyAuth: []}]
    parameters:
      - {name: status, in: query, type: string, enum: [Нове, Підтверджене, Відправлене, Доставлене, Скасоване]}
      - {name: page, in: query, type: integer, default: 1}
      - {name: per_page, in: query, type: integer, default: 10, maximum: 50}
    responses:
      200: {description: Сторінка замовлень}
      401: {description: Немає ключа API}
    """
    status = services.order_status_filter(request.args)
    return paginate(orders.list_orders(status=status), order_json, 'api_v2.list_orders', **active_params('status'))


@api_v2.get('/orders/<int:order_id>')
@require_api_key
def get_order(order_id):
    """Замовлення з позиціями
    ---
    tags: [Замовлення]
    security: [{ApiKeyAuth: []}]
    parameters:
      - {name: order_id, in: path, type: integer, required: true}
    responses:
      200: {description: '{"data": замовлення з items}'}
      404: {description: Замовлення не знайдено}
    """
    return jsonify({'data': order_json(*services.get_order(order_id))})


@api_v2.post('/orders')
def create_order():
    """Оформити замовлення
    ---
    tags: [Замовлення]
    parameters:
      - {name: body, in: body, required: true, schema: {$ref: '#/definitions/OrderInput'}}
    responses:
      201: {description: Створено}
      400: {description: Помилки валідації, schema: {$ref: '#/definitions/ErrorV2'}}
      409: {description: Недостатньо товару на складі}
    """
    order, items = services.create_order(json_body())
    return created({'data': order_json(order, items)}, url_for('api_v2.get_order', order_id=order['id']))


@api_v2.patch('/orders/<int:order_id>')
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
      200: {description: Оновлено}
      400: {description: Недопустимий статус}
      404: {description: Замовлення не знайдено}
    """
    return jsonify({'data': order_json(*services.change_status(order_id, json_body()))})


@api_v2.post('/promo-codes/check')
def check_promo():
    """Перевірити промокод
    ---
    tags: [Промокоди]
    parameters:
      - {name: body, in: body, required: true, schema: {$ref: '#/definitions/PromoCheckInput'}}
    responses:
      200: {description: '{"data": результат перевірки}'}
      400: {description: Помилки валідації}
    """
    return jsonify({'data': services.check_promo(json_body())})
