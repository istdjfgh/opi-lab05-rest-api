"""Перевірка JSON-тіл запитів до REST API.

На відміну від forms.py (HTML-форми, де все приходить рядками), у JSON важливі ТИПИ:
"price": "100" — це рядок, а не число, тому такий запит відхиляється з поясненням.
Кожна функція повертає (очищені дані, {поле: помилка}); порожній словник помилок — дані коректні.
Невідомі поля теж вважаються помилкою — так клієнт одразу бачить опечатку в назві поля.
"""
from datetime import date

from forms import COLOR_RE, EMAIL_RE, PHONE_RE, SLUG_RE
from models.orders import ORDER_STATUSES

MAX_ITEMS_IN_ORDER = 20
MAX_QUANTITY = 10


class Rules:
    """Перевірки окремих значень. Повертають текст помилки або None."""

    @staticmethod
    def text(value, low, high, required=True):
        if value is None or (isinstance(value, str) and not value.strip()):
            return 'обов’язкове поле' if required else None
        if not isinstance(value, str):
            return 'має бути рядком'
        if not low <= len(value.strip()) <= high:
            return f'довжина від {low} до {high} символів'
        return None

    @staticmethod
    def integer(value, low, high):
        # bool у Python — підклас int, тому true/false явно відкидаємо
        if isinstance(value, bool) or not isinstance(value, int):
            return 'має бути цілим числом'
        if not low <= value <= high:
            return f'має бути від {low} до {high}'
        return None

    @staticmethod
    def number(value, low, high):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return 'має бути числом'
        if not low <= value <= high:
            return f'має бути від {low} до {high}'
        return None

    @staticmethod
    def pattern(value, regex, message):
        error = Rules.text(value, 1, 120)
        if error:
            return error
        return None if regex.match(value.strip()) else message


def _unknown(data, allowed):
    return {key: 'невідоме поле' for key in data if key not in allowed}


def _clean_strings(data):
    return {k: v.strip() if isinstance(v, str) else v for k, v in data.items()}


# ------------------------------------------------------------------ товари

PRODUCT_RULES = {
    'name': lambda v: Rules.text(v, 2, 80),
    'slug': lambda v: Rules.pattern(v, SLUG_RE, 'лише малі латинські літери, цифри й дефіси'),
    'category_id': lambda v: Rules.integer(v, 1, 10**9),
    'price': lambda v: Rules.number(v, 0, 100000),
    'stock': lambda v: Rules.integer(v, 0, 10000),
    'players_min': lambda v: Rules.integer(v, 1, 20),
    'players_max': lambda v: Rules.integer(v, 1, 20),
    'age': lambda v: Rules.integer(v, 0, 99),
    'minutes': lambda v: Rules.integer(v, 1, 600),
    'emoji': lambda v: Rules.text(v, 1, 8),
    'short': lambda v: Rules.text(v, 1, 160),
    'description': lambda v: Rules.text(v, 0, 2000, required=False),
    'is_bestseller': lambda v: None if isinstance(v, bool) else 'має бути true або false',
}
PRODUCT_DEFAULTS = {'description': '', 'is_bestseller': False}


def validate_product(data, category_ids, existing=None, partial=False):
    """POST/PUT — повний набір полів; PATCH (partial=True) — лише змінені, решта з existing."""
    errors = _unknown(data, PRODUCT_RULES)
    if partial:
        merged = {**{k: existing[k] for k in PRODUCT_RULES}, **data}
        if not isinstance(merged['is_bestseller'], bool) and 'is_bestseller' not in data:
            merged['is_bestseller'] = bool(merged['is_bestseller'])
        checked = data.keys() & PRODUCT_RULES.keys()
    else:
        merged = {**PRODUCT_DEFAULTS, **data}
        checked = PRODUCT_RULES.keys()

    for field in checked:
        error = PRODUCT_RULES[field](merged.get(field))
        if error:
            errors[field] = error
    if 'category_id' not in errors and merged.get('category_id') not in category_ids:
        errors['category_id'] = 'категорії з таким id не існує'
    players_ok = not {'players_min', 'players_max'} & errors.keys()
    if players_ok and None not in (merged.get('players_min'), merged.get('players_max')) \
            and merged['players_min'] > merged['players_max']:
        errors['players_max'] = 'не може бути менше за players_min'
    if errors:
        return None, errors
    clean = _clean_strings({k: merged[k] for k in PRODUCT_RULES})
    clean['description'] = clean['description'] or ''
    clean['price'] = round(float(clean['price']), 2)
    clean['is_bestseller'] = int(clean['is_bestseller'])
    return clean, {}


# ------------------------------------------------------------------ категорії

CATEGORY_RULES = {
    'name': lambda v: Rules.text(v, 2, 40),
    'slug': lambda v: Rules.pattern(v, SLUG_RE, 'лише малі латинські літери, цифри й дефіси'),
    'emoji': lambda v: Rules.text(v, 1, 8),
    'color': lambda v: Rules.pattern(v, COLOR_RE, 'колір у форматі #RRGGBB'),
    'parent_id': lambda v: None if v is None else Rules.integer(v, 1, 10**9),
}


def validate_category(data, top_level_ids):
    errors = _unknown(data, CATEGORY_RULES)
    data = {'parent_id': None, **data}
    for field, rule in CATEGORY_RULES.items():
        error = rule(data.get(field))
        if error:
            errors[field] = error
    if 'parent_id' not in errors and data['parent_id'] is not None and data['parent_id'] not in top_level_ids:
        errors['parent_id'] = 'батьком може бути лише категорія верхнього рівня'
    return (None, errors) if errors else (_clean_strings({k: data[k] for k in CATEGORY_RULES}), {})


# ------------------------------------------------------------------ замовлення

CUSTOMER_RULES = {
    'name': lambda v: Rules.text(v, 2, 80),
    'email': lambda v: Rules.pattern(v, EMAIL_RE, 'некоректна адреса email'),
    'phone': lambda v: Rules.pattern(v, PHONE_RE, 'формат +380 67 123 45 67'),
    'city': lambda v: Rules.text(v, 2, 60),
}


def _validate_customer(customer):
    if not isinstance(customer, dict):
        return {'customer': 'має бути об’єктом {name, email, phone, city}'}
    errors = {f'customer.{k}': 'невідоме поле' for k in customer if k not in CUSTOMER_RULES}
    for field, rule in CUSTOMER_RULES.items():
        error = rule(customer.get(field))
        if error:
            errors[f'customer.{field}'] = error
    return errors


def _validate_items(items):
    if not isinstance(items, list) or not items:
        return {'items': 'має бути непорожнім списком позицій [{product_id, quantity}]'}, {}
    if len(items) > MAX_ITEMS_IN_ORDER:
        return {'items': f'не більше {MAX_ITEMS_IN_ORDER} позицій'}, {}
    errors, cart = {}, {}
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            errors[f'items[{index}]'] = 'має бути об’єктом {product_id, quantity}'
            continue
        item_errors = {}
        for field, error in (('product_id', Rules.integer(item.get('product_id'), 1, 10**9)),
                             ('quantity', Rules.integer(item.get('quantity'), 1, MAX_QUANTITY))):
            if error:
                item_errors[f'items[{index}].{field}'] = error
        if not item_errors and str(item['product_id']) in cart:
            item_errors[f'items[{index}].product_id'] = 'товар уже є в замовленні — збільште quantity'
        if not item_errors:
            cart[str(item['product_id'])] = item['quantity']
        errors.update(item_errors)
    return errors, cart


def validate_order(data):
    """Повертає (дані, помилки); дані містять cart у форматі моделей {"id": кількість}."""
    allowed = {'customer', 'address', 'comment', 'items', 'promo_code'}
    errors = _unknown(data, allowed)
    errors.update(_validate_customer(data.get('customer')))
    for field, error in (('address', Rules.text(data.get('address'), 3, 200)),
                         ('comment', Rules.text(data.get('comment'), 0, 500, required=False)),
                         ('promo_code', Rules.text(data.get('promo_code'), 3, 30, required=False))):
        if error:
            errors[field] = error
    item_errors, cart = _validate_items(data.get('items'))
    errors.update(item_errors)
    if errors:
        return None, errors
    customer = _clean_strings(data['customer'])
    customer['email'] = customer['email'].lower()
    return {
        'customer': customer,
        'address': data['address'].strip(),
        'comment': (data.get('comment') or '').strip(),
        'promo_code': (data.get('promo_code') or '').strip().upper() or None,
        'cart': cart,
    }, {}


def validate_status(data):
    errors = _unknown(data, {'status'})
    if data.get('status') not in ORDER_STATUSES:
        errors['status'] = 'допустимі значення: ' + ', '.join(ORDER_STATUSES)
    return (None, errors) if errors else ({'status': data['status']}, {})


# ------------------------------------------------------------------ відгуки і промокоди

FEEDBACK_RULES = {
    'name': lambda v: Rules.text(v, 2, 60),
    'email': lambda v: Rules.pattern(v, EMAIL_RE, 'некоректна адреса email'),
    'rating': lambda v: Rules.integer(v, 1, 5),
    'message': lambda v: Rules.text(v, 10, 1000),
}


def validate_feedback(data):
    errors = _unknown(data, FEEDBACK_RULES)
    for field, rule in FEEDBACK_RULES.items():
        error = rule(data.get(field))
        if error:
            errors[field] = error
    return (None, errors) if errors else (_clean_strings({k: data[k] for k in FEEDBACK_RULES}), {})


def validate_promo_check(data):
    errors = _unknown(data, {'code', 'subtotal', 'date'})
    for field, error in (('code', Rules.text(data.get('code'), 3, 30)),
                         ('subtotal', Rules.number(data.get('subtotal'), 0, 10**7))):
        if error:
            errors[field] = error
    when = None
    if data.get('date') is not None:
        try:
            when = date.fromisoformat(data['date'])
        except (TypeError, ValueError):
            errors['date'] = 'дата у форматі YYYY-MM-DD'
    if errors:
        return None, errors
    return {'code': data['code'].strip().upper(), 'subtotal': float(data['subtotal']), 'date': when}, {}
