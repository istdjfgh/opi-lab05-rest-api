"""Перевірка даних з HTML-форм.

Кожна функція приймає request.form і повертає (очищені дані, {поле: помилка}).
Шаблони показують помилки біля полів, а введені значення не губляться.
"""
import re
from datetime import date

EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
PHONE_RE = re.compile(r'^\+?[\d\s()\-]{10,20}$')
SLUG_RE = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')
COLOR_RE = re.compile(r'^#[0-9a-fA-F]{6}$')


def _text(form, field, max_len, required=True, min_len=0, label='Поле'):
    value = form.get(field, '').strip()
    if required and not value:
        return value, f'{label}: обов’язкове поле.'
    if value and len(value) < min_len:
        return value, f'{label}: щонайменше {min_len} символи.'
    if len(value) > max_len:
        return value, f'{label}: не більше {max_len} символів.'
    return value, None


def _number(form, field, cast, low, high, label, required=True):
    raw = form.get(field, '').strip().replace(',', '.')
    if not raw:
        return None, (f'{label}: обов’язкове поле.' if required else None)
    try:
        value = cast(raw)
    except ValueError:
        return None, f'{label}: потрібне число.'
    if not low <= value <= high:
        return value, f'{label}: від {low} до {high}.'
    return value, None


def _collect(pairs):
    """[(поле, (значення, помилка)), ...] -> (дані, помилки)."""
    data = {field: result[0] for field, result in pairs}
    errors = {field: result[1] for field, result in pairs if result[1]}
    return data, errors


def _email(form, field='email'):
    value = form.get(field, '').strip().lower()
    if not value:
        return value, 'Email: обов’язкове поле.'
    if not EMAIL_RE.match(value) or len(value) > 120:
        return value, 'Email: вкажіть коректну адресу, наприклад name@example.com.'
    return value, None


def _phone(form, required=True):
    value = form.get('phone', '').strip()
    if not value:
        return value, ('Телефон: обов’язкове поле.' if required else None)
    if not PHONE_RE.match(value):
        return value, 'Телефон: формат +380 67 123 45 67.'
    return value, None


# ------------------------------------------------------------------ сайт

def feedback_form(form):
    return _collect([
        ('name', _text(form, 'name', 60, min_len=2, label='Ім’я')),
        ('email', _email(form)),
        ('rating', _number(form, 'rating', int, 1, 5, 'Оцінка')),
        ('message', _text(form, 'message', 1000, min_len=10, label='Повідомлення')),
    ])


def checkout_form(form):
    return _collect([
        ('name', _text(form, 'name', 80, min_len=2, label='Ім’я та прізвище')),
        ('email', _email(form)),
        ('phone', _phone(form)),
        ('city', _text(form, 'city', 60, label='Місто')),
        ('address', _text(form, 'address', 200, min_len=3, label='Адреса / відділення')),
        ('comment', _text(form, 'comment', 500, required=False, label='Коментар')),
    ])


# ------------------------------------------------------------------ адмін-панель

def product_form(form, category_ids):
    data, errors = _collect([
        ('name', _text(form, 'name', 80, min_len=2, label='Назва')),
        ('slug', _text(form, 'slug', 80, label='Slug')),
        ('price', _number(form, 'price', float, 0, 100000, 'Ціна')),
        ('stock', _number(form, 'stock', int, 0, 10000, 'Залишок')),
        ('players_min', _number(form, 'players_min', int, 1, 20, 'Гравців від')),
        ('players_max', _number(form, 'players_max', int, 1, 20, 'Гравців до')),
        ('age', _number(form, 'age', int, 0, 99, 'Вік')),
        ('minutes', _number(form, 'minutes', int, 1, 600, 'Тривалість')),
        ('emoji', _text(form, 'emoji', 8, label='Емодзі')),
        ('short', _text(form, 'short', 160, label='Короткий опис')),
        ('description', _text(form, 'description', 2000, required=False, label='Опис')),
    ])
    data['category_id'] = int(form['category_id']) if form.get('category_id', '').isdigit() else None
    data['is_bestseller'] = 1 if form.get('is_bestseller') else 0
    if data['category_id'] not in category_ids:
        errors['category_id'] = 'Оберіть категорію.'
    if data['slug'] and not SLUG_RE.match(data['slug']):
        errors['slug'] = 'Slug: лише малі латинські літери, цифри й дефіси (наприклад, ticket-to-ride).'
    if not errors.get('players_max') and not errors.get('players_min') and data['players_min'] > data['players_max']:
        errors['players_max'] = '«До» не може бути менше за «від».'
    if data['price'] is not None and not errors.get('price'):
        data['price'] = round(data['price'], 2)
    return data, errors


def category_form(form, allowed_parents):
    data, errors = _collect([
        ('name', _text(form, 'name', 40, min_len=2, label='Назва')),
        ('slug', _text(form, 'slug', 40, label='Slug')),
        ('emoji', _text(form, 'emoji', 8, label='Емодзі')),
        ('color', _text(form, 'color', 7, label='Колір')),
    ])
    parent = form.get('parent_id', '')
    data['parent_id'] = int(parent) if parent.isdigit() else None
    if data['parent_id'] is not None and data['parent_id'] not in allowed_parents:
        errors['parent_id'] = 'Оберіть батьківську категорію зі списку.'
    if data['slug'] and not SLUG_RE.match(data['slug']):
        errors['slug'] = 'Slug: лише малі латинські літери, цифри й дефіси.'
    if data['color'] and not COLOR_RE.match(data['color']):
        errors['color'] = 'Колір у форматі #RRGGBB.'
    return data, errors


def customer_form(form):
    return _collect([
        ('name', _text(form, 'name', 80, min_len=2, label='Ім’я')),
        ('email', _email(form)),
        ('phone', _phone(form, required=False)),
        ('city', _text(form, 'city', 60, required=False, label='Місто')),
        ('note', _text(form, 'note', 500, required=False, label='Нотатка')),
    ])


def promo_form(form):
    data, errors = _collect([
        ('code', _text(form, 'code', 30, min_len=3, label='Код')),
        ('discount_percent', _number(form, 'discount_percent', int, 1, 90, 'Знижка, %')),
        ('min_total', _number(form, 'min_total', float, 0, 100000, 'Мінімальна сума', required=False)),
        ('max_uses', _number(form, 'max_uses', int, 1, 100000, 'Ліміт використань', required=False)),
    ])
    data['code'] = data['code'].upper()
    data['min_total'] = data['min_total'] or 0
    data['is_active'] = 1 if form.get('is_active') else 0
    if data['code'] and not re.match(r'^[A-Z0-9_-]+$', data['code']):
        errors['code'] = 'Код: латинські літери, цифри, «-» і «_».'
    valid_until = form.get('valid_until', '').strip()
    data['valid_until'] = valid_until or None
    if valid_until:
        try:
            date.fromisoformat(valid_until)
        except ValueError:
            errors['valid_until'] = 'Дата у форматі РРРР-ММ-ДД.'
    return data, errors


def parse_catalog_filters(args, sort_options):
    """GET-параметри каталогу -> словник фільтрів (некоректні значення ігноруються)."""
    def to_float(name):
        try:
            value = float(args.get(name, '').replace(',', '.'))
            return value if value >= 0 else None
        except ValueError:
            return None

    players = args.get('players', '')
    category = args.get('category', '')
    sort = args.get('sort', 'popular')
    return {
        'q': args.get('q', '').strip()[:80],
        'category': category,
        'min_price': to_float('min_price'),
        'max_price': to_float('max_price'),
        'players': int(players) if players.isdigit() and 1 <= int(players) <= 20 else None,
        'in_stock': args.get('in_stock') == '1',
        'sort': sort if sort in sort_options else 'popular',
    }
