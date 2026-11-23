"""CSRF-захист і поведінка без вимкнених перевірок."""
import re

import pytest

import seed_data
from app import create_app


@pytest.fixture()
def strict_client(tmp_path):
    """Клієнт із увімкненою перевіркою CSRF (як у робочому режимі)."""
    app = create_app({'TESTING': True, 'DATABASE': str(tmp_path / 'csrf.sqlite'), 'ADMIN_PASSWORD': 'test-pass'})
    with app.app_context():
        seed_data.seed()
    return app.test_client()


def token_from(page):
    return re.search(r'name="_csrf" value="([^"]+)"', page).group(1)


def test_post_without_token_is_rejected(strict_client):
    response = strict_client.post('/feedback', data={'name': 'Bot', 'email': 'b@example.com', 'rating': '5',
                                                     'message': 'спам спам спам спам'})
    assert response.status_code == 400 and 'Форма застаріла' in response.text


def test_post_with_wrong_token_is_rejected(strict_client):
    strict_client.get('/feedback')
    assert strict_client.post('/admin/login', data={'password': 'test-pass', '_csrf': 'forged'}).status_code == 400


def test_post_with_valid_token_passes(strict_client):
    token = token_from(strict_client.get('/admin/login').text)
    response = strict_client.post('/admin/login', data={'password': 'test-pass', '_csrf': token})
    assert response.status_code == 302


def test_admin_delete_needs_token_even_when_logged_in(strict_client):
    token = token_from(strict_client.get('/admin/login').text)
    strict_client.post('/admin/login', data={'password': 'test-pass', '_csrf': token})
    assert strict_client.post('/admin/orders/1/delete').status_code == 400
    assert strict_client.get('/admin/orders/1').status_code == 200


def test_every_post_form_has_token(strict_client):
    token = token_from(strict_client.get('/admin/login').text)
    strict_client.post('/admin/login', data={'password': 'test-pass', '_csrf': token})
    for url in ('/', '/catalog', '/feedback', '/admin/orders/1', '/admin/products', '/admin/categories',
                '/admin/promos', '/admin/feedback', '/admin/customers/1'):
        page = strict_client.get(url).text
        forms = re.findall(r'<form[^>]*method="post"[^>]*>(.*?)</form>', page, flags=re.S | re.I)
        assert all('name="_csrf"' in form for form in forms), url


def test_session_cookie_is_httponly(strict_client):
    response = strict_client.get('/admin/login')
    assert 'HttpOnly' in response.headers.get('Set-Cookie', '')
