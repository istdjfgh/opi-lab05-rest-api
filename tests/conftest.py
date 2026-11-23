"""Спільні фікстури: окрема тимчасова БД для кожного тесту з тестовими даними з seed_data.

Заповнення БД (~40 транзакцій) виконується один раз на сесію в «шаблонний» файл,
а кожен тест отримує його копію — тести ізольовані й водночас швидкі.
"""
import os
import shutil
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import seed_data  # noqa: E402
from app import create_app  # noqa: E402
from models import query_one  # noqa: E402

CONFIG = {
    'TESTING': True,
    'CSRF_DISABLED': True,          # CSRF перевіряється окремо в test_security.py
    'ADMIN_PASSWORD': 'test-pass',
    'API_KEY': 'test-key',
    'SECRET_KEY': 'test',
}


@pytest.fixture(scope='session')
def seeded_db(tmp_path_factory):
    path = tmp_path_factory.mktemp('template') / 'seeded.sqlite'
    with create_app({**CONFIG, 'DATABASE': str(path)}).app_context():
        seed_data.seed()
    return path


@pytest.fixture()
def app(tmp_path, seeded_db):
    database = tmp_path / 'test.sqlite'
    shutil.copy(seeded_db, database)
    return create_app({**CONFIG, 'DATABASE': str(database)})


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def admin(client):
    response = client.post('/admin/login', data={'password': 'test-pass'})
    assert response.status_code == 302
    return client


@pytest.fixture()
def db_row(app):
    """Виконати SELECT і отримати один рядок (у контексті застосунку)."""
    def run(sql, params=()):
        with app.app_context():
            row = query_one(sql, params)
            return dict(row) if row else None
    return run


def product_id(db_row, slug):
    return db_row('SELECT id FROM products WHERE slug = ?', (slug,))['id']
