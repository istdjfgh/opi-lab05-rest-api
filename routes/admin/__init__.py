"""Адмін-панель (/admin). Усі сторінки, крім входу, вимагають авторизації.

Модулі: core (вхід, дашборд, замовлення, відгуки), catalog (товари, категорії),
people (клієнти — рівень 2, промокоди — рівень 3).
"""
from flask import Blueprint

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

from . import catalog, core, people  # noqa: E402,F401  — реєструють маршрути в admin_bp
