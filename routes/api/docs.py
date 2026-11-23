"""Документація API (flasgger → Swagger UI на /apidocs/).

Дві специфікації OpenAPI 2.0 — окремо для v1 і v2 (перемикаються у верхньому меню Swagger UI).
Описи ендпоінтів беруться з docstring функцій у v1.py / v2.py, а спільні схеми даних — звідси.
"""
from flasgger import Swagger

PRODUCT_INPUT = {
    'type': 'object',
    'required': ['name', 'slug', 'category_id', 'price', 'stock', 'players_min', 'players_max',
                 'age', 'minutes', 'emoji', 'short'],
    'properties': {
        'name': {'type': 'string', 'minLength': 2, 'maxLength': 80, 'example': 'Вінгспен'},
        'slug': {'type': 'string', 'pattern': '^[a-z0-9]+(?:-[a-z0-9]+)*$', 'example': 'wingspan'},
        'category_id': {'type': 'integer', 'example': 1},
        'price': {'type': 'number', 'minimum': 0, 'maximum': 100000, 'example': 2190},
        'stock': {'type': 'integer', 'minimum': 0, 'example': 4},
        'players_min': {'type': 'integer', 'minimum': 1, 'maximum': 20, 'example': 1},
        'players_max': {'type': 'integer', 'minimum': 1, 'maximum': 20, 'example': 5},
        'age': {'type': 'integer', 'minimum': 0, 'maximum': 99, 'example': 10},
        'minutes': {'type': 'integer', 'minimum': 1, 'maximum': 600, 'example': 70},
        'emoji': {'type': 'string', 'maxLength': 8, 'example': '🐦'},
        'short': {'type': 'string', 'maxLength': 160, 'example': 'Колекціонуйте птахів у заповіднику.'},
        'description': {'type': 'string', 'maxLength': 2000, 'example': ''},
        'is_bestseller': {'type': 'boolean', 'example': False},
    },
}

PRODUCT_V1 = {
    'type': 'object',
    'properties': {
        'id': {'type': 'integer', 'example': 1},
        **{k: v for k, v in PRODUCT_INPUT['properties'].items()},
        'category_name': {'type': 'string', 'example': 'Сімейні'},
        'category_slug': {'type': 'string', 'example': 'family'},
        'category_emoji': {'type': 'string'},
        'category_color': {'type': 'string', 'example': '#1c7ed6'},
        'created_at': {'type': 'string', 'example': '2026-11-23 12:00:00'},
    },
}

PRODUCT_V2 = {
    'type': 'object',
    'properties': {
        'id': {'type': 'integer', 'example': 1},
        'name': {'type': 'string', 'example': 'Каркасон'},
        'slug': {'type': 'string', 'example': 'carcassonne'},
        'category': {'type': 'object', 'example': {'id': 1, 'name': 'Сімейні', 'slug': 'family'}},
        'price': {'type': 'object', 'example': {'amount': 1150.0, 'currency': 'UAH'}},
        'stock': {'type': 'integer', 'example': 14},
        'in_stock': {'type': 'boolean', 'example': True},
        'players': {'type': 'object', 'example': {'min': 2, 'max': 5}},
        'age': {'type': 'integer'}, 'minutes': {'type': 'integer'},
        'emoji': {'type': 'string'}, 'short': {'type': 'string'}, 'description': {'type': 'string'},
        'is_bestseller': {'type': 'boolean'}, 'created_at': {'type': 'string'},
        'links': {'type': 'object', 'example': {'self': '/api/v2/products/1', 'html': '/catalog/carcassonne'}},
    },
}

DEFINITIONS = {
    'ProductInput': PRODUCT_INPUT,
    'ProductV1': PRODUCT_V1,
    'ProductV2': PRODUCT_V2,
    'ProductPageV2': {
        'type': 'object',
        'properties': {
            'data': {'type': 'array', 'items': {'$ref': '#/definitions/ProductV2'}},
            'meta': {'type': 'object', 'example': {'page': 1, 'per_page': 10, 'total': 12, 'pages': 2}},
            'links': {'type': 'object', 'example': {'self': '/api/v2/products?page=1&per_page=10',
                                                    'next': '/api/v2/products?page=2&per_page=10', 'prev': None}},
        },
    },
    'Category': {
        'type': 'object',
        'properties': {
            'id': {'type': 'integer'}, 'name': {'type': 'string', 'example': 'Економічні'},
            'slug': {'type': 'string', 'example': 'economic'}, 'emoji': {'type': 'string'},
            'color': {'type': 'string', 'example': '#5f3dc4'}, 'parent_id': {'type': 'integer', 'example': 2},
            'parent_name': {'type': 'string'}, 'products_count': {'type': 'integer'},
        },
    },
    'CategoryInput': {
        'type': 'object',
        'required': ['name', 'slug', 'emoji', 'color'],
        'properties': {
            'name': {'type': 'string', 'example': 'Варгейми'}, 'slug': {'type': 'string', 'example': 'wargames'},
            'emoji': {'type': 'string', 'example': '⚔️'}, 'color': {'type': 'string', 'example': '#495057'},
            'parent_id': {'type': 'integer', 'example': 2, 'description': 'id категорії верхнього рівня або null'},
        },
    },
    'Order': {
        'type': 'object',
        'properties': {
            'id': {'type': 'integer'}, 'customer_id': {'type': 'integer'},
            'customer_name': {'type': 'string'}, 'customer_email': {'type': 'string'},
            'address': {'type': 'string'}, 'comment': {'type': 'string'},
            'status': {'type': 'string', 'example': 'Нове'},
            'subtotal': {'type': 'number'}, 'discount': {'type': 'number'}, 'total': {'type': 'number'},
            'promo_code': {'type': 'string', 'example': 'WELCOME10'}, 'created_at': {'type': 'string'},
            'items': {'type': 'array', 'items': {'type': 'object', 'example': {
                'product_id': 1, 'name': 'Каркасон', 'quantity': 2, 'unit_price': 1150.0, 'line_total': 2300.0}}},
        },
    },
    'OrderInput': {
        'type': 'object',
        'required': ['customer', 'address', 'items'],
        'properties': {
            'customer': {'type': 'object', 'example': {'name': 'Ілля Пламетюк', 'email': 'student@example.com',
                                                       'phone': '+380 67 123 45 67', 'city': 'Луцьк'}},
            'address': {'type': 'string', 'example': 'Відділення Нової пошти №3'},
            'comment': {'type': 'string', 'example': 'Подарункове пакування'},
            'items': {'type': 'array', 'example': [{'product_id': 1, 'quantity': 2}, {'product_id': 7, 'quantity': 1}]},
            'promo_code': {'type': 'string', 'example': 'WELCOME10'},
        },
    },
    'StatusInput': {
        'type': 'object', 'required': ['status'],
        'properties': {'status': {'type': 'string', 'enum': ['Нове', 'Підтверджене', 'Відправлене',
                                                             'Доставлене', 'Скасоване'], 'example': 'Відправлене'}},
    },
    'Customer': {
        'type': 'object',
        'properties': {'id': {'type': 'integer'}, 'name': {'type': 'string'}, 'email': {'type': 'string'},
                       'phone': {'type': 'string'}, 'city': {'type': 'string'}, 'note': {'type': 'string'},
                       'orders_count': {'type': 'integer'}, 'orders_total': {'type': 'number'}},
    },
    'Feedback': {
        'type': 'object',
        'properties': {'id': {'type': 'integer'}, 'name': {'type': 'string'}, 'rating': {'type': 'integer'},
                       'message': {'type': 'string'}, 'created_at': {'type': 'string'}},
    },
    'FeedbackInput': {
        'type': 'object', 'required': ['name', 'email', 'rating', 'message'],
        'properties': {'name': {'type': 'string', 'example': 'Марія'},
                       'email': {'type': 'string', 'example': 'maria@example.com'},
                       'rating': {'type': 'integer', 'minimum': 1, 'maximum': 5, 'example': 5},
                       'message': {'type': 'string', 'minLength': 10, 'example': 'Чудовий магазин, швидка доставка!'}},
    },
    'PromoCheckInput': {
        'type': 'object', 'required': ['code', 'subtotal'],
        'properties': {'code': {'type': 'string', 'example': 'PARTY15'},
                       'subtotal': {'type': 'number', 'example': 1500},
                       'date': {'type': 'string', 'format': 'date', 'description': 'дата перевірки (за замовчуванням — сьогодні)'}},
    },
    'PromoCheckResult': {
        'type': 'object',
        'example': {'code': 'PARTY15', 'valid': True, 'reason': None, 'discount_percent': 15,
                    'discount': 225.0, 'total': 1275.0},
    },
    'ErrorV1': {
        'type': 'object',
        'example': {'error': 'Дані не пройшли перевірку.', 'details': {'price': 'має бути числом'}},
    },
    'ErrorV2': {
        'type': 'object',
        'example': {'error': {'status': 400, 'code': 'validation_error', 'message': 'Дані не пройшли перевірку.',
                              'fields': {'price': 'має бути числом'}}},
    },
}

TEMPLATE = {
    'swagger': '2.0',
    'info': {
        'title': 'API магазину настільних ігор «Кубик»',
        'description': (
            'REST API лабораторної роботи 05. Читання каталогу, оформлення замовлень, відгуки й перевірка '
            'промокодів — без ключа. Зміна даних і службові дані — з ключем у заголовку **X-API-Key** '
            '(натисніть Authorize). Для навчального запуску ключ за замовчуванням — `dev-api-key`.'
        ),
        'version': '2.0',
    },
    'consumes': ['application/json'],
    'produces': ['application/json'],
    'securityDefinitions': {'ApiKeyAuth': {'type': 'apiKey', 'in': 'header', 'name': 'X-API-Key'}},
    'definitions': DEFINITIONS,
}

CONFIG = {
    'headers': [],
    'specs': [
        {'endpoint': 'apispec_v1', 'route': '/apispec_v1.json', 'title': 'API v1',
         'rule_filter': lambda rule: rule.rule.startswith('/api/v1'), 'model_filter': lambda tag: True},
        {'endpoint': 'apispec_v2', 'route': '/apispec_v2.json', 'title': 'API v2',
         'rule_filter': lambda rule: rule.rule.startswith('/api/v2'), 'model_filter': lambda tag: True},
    ],
    'static_url_path': '/flasgger_static',
    'swagger_ui': True,
    'specs_route': '/apidocs/',
}


def init_docs(app):
    return Swagger(app, template=TEMPLATE, config=CONFIG)
