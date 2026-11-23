"""Безпека: CSRF-токен для всіх POST-форм і вхід до адмін-панелі.

CSRF: у сесії зберігається випадковий токен, кожна форма містить його в прихованому
полі, а before_request порівнює значення. Чужий сайт не знає токен, тож не зможе
від імені адміністратора відправити форму «видалити замовлення».
"""
import hmac
import secrets
from functools import wraps

from flask import abort, current_app, redirect, request, session, url_for


def csrf_token():
    if '_csrf' not in session:
        session['_csrf'] = secrets.token_urlsafe(32)
    return session['_csrf']


def check_csrf():
    """Викликається перед кожним запитом (реєструється в app.py)."""
    if request.method != 'POST' or current_app.config.get('CSRF_DISABLED'):
        return
    # REST API не використовує cookie-сесію: доступ до змін дає ключ X-API-Key у заголовку,
    # а чужий сайт не може додати власний заголовок до запиту, тож CSRF-токен тут не потрібен.
    if request.path.startswith('/api/'):
        return
    sent = request.form.get('_csrf', '')
    if not sent or not hmac.compare_digest(sent, session.get('_csrf', '')):
        abort(400, description='Форма застаріла. Оновіть сторінку й спробуйте ще раз.')


def check_admin_password(password):
    return hmac.compare_digest(password.encode(), current_app.config['ADMIN_PASSWORD'].encode())


def admin_required(view):
    """Декоратор: без входу — перенаправлення на сторінку логіну."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not session.get('is_admin'):
            return redirect(url_for('admin.login', next=request.full_path))
        return view(*args, **kwargs)
    return wrapper
