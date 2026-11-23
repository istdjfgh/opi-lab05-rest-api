"""Спільне для всіх версій API: помилки у JSON, ключ доступу, читання тіла запиту.

Формат помилки залежить від версії (визначається за адресою):
    v1: {"error": "текст", "details": {"поле": "помилка"}}
    v2: {"error": {"status": 400, "code": "validation_error", "message": "текст", "fields": {...}}}
Зміна формату помилок — один з прикладів «ламаючої» зміни, заради якої і потрібне версіонування.
"""
import hmac
from functools import wraps

from flask import current_app, jsonify, request
from werkzeug.exceptions import HTTPException

ERROR_CODES = {
    400: 'bad_request', 401: 'unauthorized', 404: 'not_found', 405: 'method_not_allowed',
    409: 'conflict', 415: 'unsupported_media_type', 500: 'internal_error',
}
DEFAULT_MESSAGES = {
    400: 'Некоректний запит.',
    401: 'Потрібен коректний ключ API у заголовку X-API-Key.',
    404: 'Ресурс не знайдено.',
    405: 'Метод не підтримується для цієї адреси.',
    409: 'Конфлікт із поточним станом даних.',
    415: 'Тіло запиту має бути JSON (Content-Type: application/json).',
    500: 'Внутрішня помилка сервера.',
}


class ApiError(Exception):
    """Виняток, який перетворюється на JSON-відповідь з потрібним кодом статусу."""

    def __init__(self, status, message=None, fields=None, code=None):
        super().__init__(message)
        self.status = status
        self.message = message or DEFAULT_MESSAGES.get(status, 'Помилка.')
        self.fields = fields or {}
        self.code = code or ERROR_CODES.get(status, 'error')


class ValidationError(ApiError):
    def __init__(self, fields, message='Дані не пройшли перевірку.'):
        super().__init__(400, message, fields, code='validation_error')


def error_response(error):
    if request.path.startswith('/api/v1'):
        body = {'error': error.message}
        if error.fields:
            body['details'] = error.fields
    else:
        body = {'error': {'status': error.status, 'code': error.code, 'message': error.message}}
        if error.fields:
            body['error']['fields'] = error.fields
    response = jsonify(body)
    response.status_code = error.status
    return response


def http_error_response(error):
    """Стандартна HTTP-помилка Flask (404, 405, ...) -> JSON у форматі поточної версії API."""
    response = error_response(ApiError(error.code, DEFAULT_MESSAGES.get(error.code, error.description)))
    if error.code == 405 and getattr(error, 'valid_methods', None):
        response.headers['Allow'] = ', '.join(sorted(error.valid_methods))
    return response


def register_error_handlers(app):
    """Для адрес /api/... помилки віддаються в JSON, для сайту — HTML-сторінкою (як раніше)."""
    app.register_error_handler(ApiError, error_response)

    def wants_json():
        return request.path.startswith('/api/')

    @app.errorhandler(HTTPException)
    def http_error(error):
        if not wants_json():
            return error  # далі спрацюють HTML-обробники сайту з app.py
        return http_error_response(error)

    @app.errorhandler(Exception)
    def unexpected_error(error):
        if isinstance(error, HTTPException):
            return http_error(error)
        current_app.logger.exception('Необроблена помилка: %s', error)
        if wants_json():
            return error_response(ApiError(500))
        return 'Внутрішня помилка сервера', 500


def json_body():
    """Тіло запиту як словник. 415 — якщо не JSON, 400 — якщо JSON зламаний або це не об’єкт."""
    if not request.is_json:
        raise ApiError(415)
    data = request.get_json(silent=True)
    if data is None:
        raise ApiError(400, 'Тіло запиту містить некоректний JSON.')
    if not isinstance(data, dict):
        raise ApiError(400, 'Тіло запиту має бути JSON-об’єктом {...}.')
    return data


def require_api_key(view):
    """Операції, що змінюють дані, і службові дані доступні лише з ключем API.

    Ключ передається в кожному запиті (заголовок X-API-Key) — сервер не зберігає
    стан входу між запитами, що відповідає принципу stateless у REST.
    """
    @wraps(view)
    def wrapper(*args, **kwargs):
        sent = request.headers.get('X-API-Key', '')
        expected = current_app.config['API_KEY']
        if not sent or not hmac.compare_digest(sent.encode(), expected.encode()):
            raise ApiError(401)
        return view(*args, **kwargs)
    return wrapper


def int_arg(name, default, low, high):
    """Цілий параметр рядка запиту з перевіркою меж (400 при помилці)."""
    raw = request.args.get(name)
    if raw is None or raw == '':
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ValidationError({name: 'має бути цілим числом'}) from None
    if not low <= value <= high:
        raise ValidationError({name: f'має бути від {low} до {high}'})
    return value


def created(body, location):
    """201 Created + заголовок Location з адресою нового ресурсу."""
    response = jsonify(body)
    response.status_code = 201
    response.headers['Location'] = location
    return response
