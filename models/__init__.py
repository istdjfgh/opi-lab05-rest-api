"""Робота з базою даних SQLite.

З'єднання відкривається один раз на запит (зберігається в `g`) і закривається
в `close_db` після відповіді. Модулі пакета (products, orders, ...) містять
функції CRUD для окремих таблиць. Усі запити параметризовані (`?`).
"""
import os
import sqlite3
from datetime import datetime

from flask import current_app, g

SCHEMA_PATH = os.path.join(os.path.dirname(__file__), 'schema.sql')


def now():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def get_db():
    """З'єднання для поточного запиту (створюється при першому зверненні)."""
    if 'db' not in g:
        g.db = sqlite3.connect(current_app.config['DATABASE'])
        g.db.row_factory = sqlite3.Row             # рядки як словники: row['name']
        g.db.execute('PRAGMA foreign_keys = ON')   # SQLite за замовчуванням не перевіряє FOREIGN KEY
        # Вбудовані LOWER()/LIKE у SQLite не знають кирилиці («Марс» ≠ «марс»),
        # тому реєструємо власну функцію на основі Python str.lower().
        g.db.create_function('uk_lower', 1, _uk_lower, deterministic=True)
    return g.db


def _uk_lower(value):
    return value.lower() if isinstance(value, str) else value


def like_pattern(text):
    """Шаблон для `uk_lower(колонка) LIKE ? ESCAPE '\\'`: нижній регістр, % і _ екрановані."""
    escaped = text.lower().replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
    return f'%{escaped}%'


def close_db(exception=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db():
    """Створює таблиці (безпечно викликати повторно)."""
    with open(SCHEMA_PATH, encoding='utf-8') as file:
        get_db().executescript(file.read())


def query_all(sql, params=()):
    return get_db().execute(sql, params).fetchall()


def query_one(sql, params=()):
    return get_db().execute(sql, params).fetchone()


def execute(sql, params=()):
    """INSERT/UPDATE/DELETE в окремій транзакції. Повертає id нового рядка."""
    db = get_db()
    with db:  # commit при успіху, rollback при винятку
        cursor = db.execute(sql, params)
    return cursor.lastrowid
