"""Скриншоти для звіту (lab-reports/screenshots): Swagger UI, запити «Try it out», звіт newman.

Запуск: python scripts/make_screenshots.py   (спочатку python scripts/run_newman.py — для звіту newman)
Застосунок піднімається на тимчасовій БД з тестовими даними, робоча db.sqlite не змінюється.
"""
import html
import os
import sys
import tempfile
import threading

from playwright.sync_api import sync_playwright
from werkzeug.serving import make_server

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import seed_data  # noqa: E402
from app import create_app  # noqa: E402

OUT = os.path.join(ROOT, 'lab-reports', 'screenshots')
NEWMAN = os.path.join(ROOT, 'lab-reports', 'newman')
API_KEY = 'dev-api-key'


def launch(playwright):
    try:
        return playwright.chromium.launch()
    except Exception:
        return playwright.chromium.launch(channel='chrome')


def save(target, name, **kwargs):
    target.screenshot(path=os.path.join(OUT, f'{name}.png'), **kwargs)
    print('✓', name)


def operation(page, method, path):
    selector = f'.opblock-{method}:has(.opblock-summary-path[data-path="{path}"])'
    return page.locator(selector).first


def try_it(page, method, path, name, params=None, body=None):
    """Розгорнути ендпоінт у Swagger UI, виконати запит і зняти блок із запитом і відповіддю."""
    block = operation(page, method, path)
    block.locator('.opblock-summary').click()
    block.locator('button.try-out__btn').click()
    for field, value in (params or {}).items():
        block.locator(f'tr[data-param-name="{field}"] input').fill(str(value))
    if body is not None:
        block.locator('textarea.body-param__text').fill(body)
    block.locator('button.execute').click()
    block.locator('.live-responses-table .response-col_status').first.wait_for()
    page.wait_for_timeout(300)
    save(block, name)
    block.locator('button.try-out__btn').click()   # «Cancel» — вийти з режиму Try it out
    block.locator('.opblock-summary').click()      # згорнути, щоб не заважав наступним


def authorize(page):
    page.locator('button.authorize').first.click()
    page.locator('.modal-ux input').first.fill(API_KEY)
    page.locator('.modal-ux button.authorize').click()
    page.locator('.modal-ux button.btn-done').click()


def swagger(page, base):
    page.goto(base + '/apidocs/')
    page.locator('.opblock').first.wait_for()
    save(page, 'apidocs-v1', full_page=True)

    authorize(page)
    try_it(page, 'get', '/api/v1/products/{product_id}', 'try-get-product-200', {'product_id': 1})
    try_it(page, 'get', '/api/v1/products/{product_id}', 'try-get-product-404', {'product_id': 999})
    try_it(page, 'post', '/api/v1/products', 'try-create-product-400',
           body='{\n  "name": "",\n  "slug": "Погана Адреса",\n  "category_id": 999,\n  "price": "дорого",\n'
                '  "stock": -1,\n  "players_min": 6,\n  "players_max": 2,\n  "age": 8,\n  "minutes": 30,\n'
                '  "emoji": "🎲",\n  "short": "Опис",\n  "colour": "red"\n}')
    try_it(page, 'post', '/api/v1/orders', 'try-create-order-201')
    try_it(page, 'delete', '/api/v1/products/{product_id}', 'try-delete-product-409', {'product_id': 1})

    # Перемкнути Swagger UI на специфікацію v2: адреса /apispec_v2.json у полі вгорі → Explore
    page.locator('.download-url-input').fill('/apispec_v2.json')
    page.locator('.download-url-button').click()
    page.wait_for_timeout(800)
    page.locator('.opblock-summary-path[data-path="/api/v2/products"]').first.wait_for()
    save(page, 'apidocs-v2', full_page=True)
    try_it(page, 'get', '/api/v2/products', 'try-v2-products-page', {'per_page': 2, 'page': 2})
    try_it(page, 'get', '/api/v2/products/{product_id}', 'try-v2-product-404', {'product_id': 999})


def newman_report(page):
    report = os.path.join(NEWMAN, 'report.html')
    if not os.path.exists(report):
        print('! немає lab-reports/newman/report.html — спочатку python scripts/run_newman.py')
        return
    page.goto('file:///' + report.replace(os.sep, '/'))
    page.wait_for_timeout(800)
    save(page, 'newman-summary')
    page.locator('a[href="#pills-requests"], #pills-requests-tab').first.click()
    page.wait_for_timeout(600)
    save(page, 'newman-requests')

    with open(os.path.join(NEWMAN, 'cli.txt'), encoding='utf-8') as file:
        lines = file.read().splitlines()
    start = next(i for i, line in enumerate(lines) if '1. Службові' in line)
    table = next(i for i, line in enumerate(lines) if line.startswith('┌'))
    text = '\n'.join(lines[start:start + 40] + ['   …'] + lines[table:])
    page.set_content('<html><body style="margin:0;background:#1e1e1e"><pre style="margin:0;padding:24px 28px;'
                     'color:#d4d4d4;font:15px/1.2 Consolas,monospace">'
                     f'<span style="color:#6a9955">$ python scripts/run_newman.py</span>\n{html.escape(text)}</pre></body></html>')
    save(page, 'newman-cli', full_page=True)


def main():
    os.makedirs(OUT, exist_ok=True)
    app = create_app({'DATABASE': os.path.join(tempfile.mkdtemp(), 'shots.sqlite'), 'API_KEY': API_KEY})
    with app.app_context():
        seed_data.seed()
    server = make_server('127.0.0.1', 0, app)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f'http://127.0.0.1:{server.server_port}'
    with sync_playwright() as p:
        browser = launch(p)
        swagger(browser.new_page(viewport={'width': 1280, 'height': 900}), base)
        newman_report(browser.new_page(viewport={'width': 1280, 'height': 900}))
        browser.close()
    server.shutdown()


if __name__ == '__main__':
    main()
