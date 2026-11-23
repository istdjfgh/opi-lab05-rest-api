"""Логіка API, спільна для v1 і v2: робота з моделями, перевірки, конфлікти.

Версії відрізняються лише форматом відповіді (serializers у v1.py / v2.py),
а правила — однакові, тому вони зібрані тут і не дублюються.
"""
import sqlite3

import api_validation as validate
from forms import parse_catalog_filters
from models import catalog, customers, feedback, orders

from .common import ApiError, ValidationError


def _not_found(what):
    return ApiError(404, f'{what} не знайдено.')


# ------------------------------------------------------------------ товари

def product_filters(args):
    """Параметри рядка запиту -> фільтри моделі. Невідома категорія — 400, а не порожній список."""
    filters = parse_catalog_filters(args, catalog.SORT_OPTIONS)
    if args.get('sort') and args['sort'] not in catalog.SORT_OPTIONS:
        raise ValidationError({'sort': 'допустимі значення: ' + ', '.join(catalog.SORT_OPTIONS)})
    category = None
    if filters['category']:
        category = catalog.get_category_by_slug(filters['category'])
        if category is None:
            raise ValidationError({'category': f'категорії «{filters["category"]}» не існує'})
    filters['category_id'] = category['id'] if category else None
    return filters


def get_product(product_id):
    product = catalog.get_product(product_id)
    if product is None:
        raise _not_found(f'Товар з id={product_id}')
    return product


def _category_ids():
    return {c['id'] for c in catalog.list_categories()}


def _save_product(data, product_id=None):
    try:
        return catalog.save_product(data, product_id)
    except sqlite3.IntegrityError:
        raise ApiError(409, 'Товар з таким slug уже існує.', {'slug': 'має бути унікальним'}) from None


def create_product(body):
    data, errors = validate.validate_product(body, _category_ids())
    if errors:
        raise ValidationError(errors)
    return get_product(_save_product(data))


def update_product(product_id, body, partial):
    """PUT (partial=False) замінює всі поля, PATCH (partial=True) — лише передані."""
    existing = get_product(product_id)
    if partial and not body:
        raise ValidationError({'body': 'передайте хоча б одне поле для зміни'})
    data, errors = validate.validate_product(body, _category_ids(), existing=existing, partial=partial)
    if errors:
        raise ValidationError(errors)
    _save_product(data, product_id)
    return get_product(product_id)


def delete_product(product_id):
    get_product(product_id)
    try:
        catalog.delete_product(product_id)
    except sqlite3.IntegrityError:
        raise ApiError(409, 'Товар є в замовленнях, тому його не можна видалити. '
                            'Щоб зняти з продажу, встановіть stock = 0 (PATCH).') from None


# ------------------------------------------------------------------ категорії

def get_category(category_id):
    category = next((c for c in catalog.list_categories() if c['id'] == category_id), None)
    if category is None:
        raise _not_found(f'Категорію з id={category_id}')
    return category


def create_category(body):
    top_level = {c['id'] for c in catalog.list_categories() if c['parent_id'] is None}
    data, errors = validate.validate_category(body, top_level)
    if errors:
        raise ValidationError(errors)
    try:
        return get_category(catalog.save_category(data))
    except sqlite3.IntegrityError:
        raise ApiError(409, 'Категорія з таким slug уже існує.', {'slug': 'має бути унікальним'}) from None


def delete_category(category_id):
    get_category(category_id)
    try:
        catalog.delete_category(category_id)
    except sqlite3.IntegrityError:
        raise ApiError(409, 'У категорії є товари або підкатегорії — спочатку перенесіть їх.') from None


# ------------------------------------------------------------------ замовлення

def order_status_filter(args):
    status = args.get('status', '')
    if status and status not in orders.ORDER_STATUSES:
        raise ValidationError({'status': 'допустимі значення: ' + ', '.join(orders.ORDER_STATUSES)})
    return status or None


def get_order(order_id):
    order, items = orders.get_order(order_id)
    if order is None:
        raise _not_found(f'Замовлення з id={order_id}')
    return order, items


def create_order(body):
    data, errors = validate.validate_order(body)
    if errors:
        raise ValidationError(errors)
    known = {str(p['id']) for p in catalog.get_products_by_ids(int(pid) for pid in data['cart'])}
    missing = [pid for pid in data['cart'] if pid not in known]
    if missing:
        raise ValidationError({'items': f'товарів з id {", ".join(missing)} не існує'})
    if data['promo_code']:
        _, subtotal = orders.cart_lines(data['cart'])
        promo, reason = orders.check_promo(data['promo_code'], subtotal)
        if promo is None:
            raise ValidationError({'promo_code': reason})
    try:
        order_id = orders.create_order(data['customer'], data['address'], data['comment'],
                                       data['cart'], data['promo_code'])
    except orders.OrderError as error:   # не вистачає товару на складі
        raise ApiError(409, str(error)) from None
    return get_order(order_id)


def change_status(order_id, body):
    get_order(order_id)
    data, errors = validate.validate_status(body)
    if errors:
        raise ValidationError(errors)
    orders.update_status(order_id, data['status'])
    return get_order(order_id)


def delete_order(order_id):
    get_order(order_id)
    orders.delete_order(order_id)


# ------------------------------------------------------------------ клієнти, відгуки, промокоди

def get_customer(customer_id):
    customer = next((c for c in customers.list_customers() if c['id'] == customer_id), None)
    if customer is None:
        raise _not_found(f'Клієнта з id={customer_id}')
    return customer, orders.list_orders(customer_id=customer_id)


def create_feedback(body):
    data, errors = validate.validate_feedback(body)
    if errors:
        raise ValidationError(errors)
    return feedback.get_feedback(feedback.add_feedback(**data))


def check_promo(body):
    data, errors = validate.validate_promo_check(body)
    if errors:
        raise ValidationError(errors)
    promo, reason = orders.check_promo(data['code'], data['subtotal'], today=data['date'])
    discount = orders.calc_discount(data['subtotal'], promo)
    return {
        'code': data['code'],
        'valid': promo is not None,
        'reason': reason,
        'discount_percent': promo['discount_percent'] if promo else 0,
        'discount': discount,
        'total': round(data['subtotal'] - discount, 2),
    }
