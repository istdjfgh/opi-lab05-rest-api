"""Генерує postman_collection.json — колекцію запитів Postman з тестами (pm.test).

Запуск: python scripts/build_postman_collection.py
Колекцію можна імпортувати в Postman / Bruno або запустити з командного рядка:
    npx newman run postman_collection.json
Сценарії розраховані на свіжу БД із seed_data.py (python seed_data.py && python app.py).
Для кожного ресурсу є успішні запити й запити з помилкою (неіснуючий id, порожні поля, без ключа тощо).
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'postman_collection.json')

PRODUCT = {'name': 'Вінгспен', 'slug': 'wingspan', 'category_id': 1, 'price': 2190, 'stock': 4,
           'players_min': 1, 'players_max': 5, 'age': 10, 'minutes': 70, 'emoji': '🐦',
           'short': 'Колекціонуйте птахів у заповіднику.'}
CUSTOMER = {'name': 'Ілля Пламетюк', 'email': 'student@example.com', 'phone': '+380 67 123 45 67', 'city': 'Луцьк'}


def status(code):
    return f'pm.test("Статус {code}", () => pm.response.to.have.status({code}));'


def check(title, expression):
    return f'pm.test("{title}", () => {{ const b = pm.response.json(); {expression}; }});'


JSON_CT = 'pm.test("Відповідь у JSON", () => pm.response.to.be.json);'


def req(name, method, path, tests, body=None, key=False, raw=None, content_type='application/json'):
    headers = []
    if key:
        headers.append({'key': 'X-API-Key', 'value': '{{apiKey}}'})
    request = {'method': method, 'header': headers, 'url': '{{baseUrl}}' + path}
    if body is not None or raw is not None:
        headers.append({'key': 'Content-Type', 'value': content_type})
        request['body'] = {'mode': 'raw', 'raw': raw if raw is not None else json.dumps(body, ensure_ascii=False, indent=2)}
    return {'name': name, 'request': request,
            'event': [{'listen': 'test', 'script': {'type': 'text/javascript', 'exec': tests}}]}


FOLDERS = [
    ('1. Службові', [
        req('GET /health — сервіс працює', 'GET', '/api/v1/health', [
            status(200), JSON_CT, check('status = ok', 'pm.expect(b.status).to.eql("ok")'),
            'pm.test("v1 позначена як попередня версія", () => pm.expect(pm.response.headers.get("Deprecation")).to.eql("true"));']),
        req('GET /stats без ключа → 401', 'GET', '/api/v1/stats', [
            status(401), check('є текст помилки', 'pm.expect(b.error).to.include("X-API-Key")')]),
        req('GET /stats з ключем', 'GET', '/api/v1/stats', [
            status(200), check('є кількість замовлень і товарів', 'pm.expect(b.orders).to.be.a("number"); pm.expect(b.products).to.eql(12)')],
            key=True),
    ]),
    ('2. Товари (v1)', [
        req('GET /products — усі товари', 'GET', '/api/v1/products', [
            status(200), JSON_CT, check('масив із 12 товарів', 'pm.expect(b).to.be.an("array").with.lengthOf(12)'),
            'pm.test("Час відповіді < 500 мс", () => pm.expect(pm.response.responseTime).to.be.below(500));']),
        req('GET /products?category=strategy&sort=price_asc — фільтр з підкатегоріями', 'GET',
            '/api/v1/products?category=strategy&sort=price_asc', [
                status(200), check('4 товари, від дешевшого', 'pm.expect(b.map(p => p.slug)).to.eql(["small-world", "terraforming-mars", "brass", "kemet"])')]),
        req('GET /products?q=МАРС — пошук без урахування регістру', 'GET', '/api/v1/products?q=%D0%9C%D0%90%D0%A0%D0%A1', [
            status(200), check('знайдено «Тераформування Марса»', 'pm.expect(b[0].slug).to.eql("terraforming-mars")')]),
        req('GET /products?category=nope — невідома категорія → 400', 'GET', '/api/v1/products?category=nope', [
            status(400), check('пояснення в details.category', 'pm.expect(b.details.category).to.include("nope")')]),
        req('GET /products/1 — один товар', 'GET', '/api/v1/products/1', [
            status(200), check('це «Каркасон»', 'pm.expect(b.slug).to.eql("carcassonne"); pm.expect(b.price).to.eql(1150)')]),
        req('GET /products/999 — неіснуючий id → 404', 'GET', '/api/v1/products/999', [
            status(404), JSON_CT, check('помилка в JSON', 'pm.expect(b.error).to.include("999")')]),
        req('POST /products без ключа → 401', 'POST', '/api/v1/products', [status(401)], body=PRODUCT),
        req('POST /products з порожніми й хибними полями → 400', 'POST', '/api/v1/products', [
            status(400), check('помилки по полях', 'pm.expect(b.details.name).to.exist; pm.expect(b.details.price).to.eql("має бути числом")')],
            body={'name': '', 'price': 'дорого'}, key=True),
        req('POST /products не JSON → 415', 'POST', '/api/v1/products', [status(415)],
            raw='name=Гра&price=100', content_type='application/x-www-form-urlencoded', key=True),
        req('POST /products — створити товар', 'POST', '/api/v1/products', [
            status(201), check('товар створено', 'pm.expect(b.id).to.be.a("number"); pm.expect(b.name).to.eql("Вінгспен")'),
            'pm.test("Є заголовок Location", () => pm.expect(pm.response.headers.get("Location")).to.include("/api/v1/products/"));',
            'pm.collectionVariables.set("productId", pm.response.json().id);'], body=PRODUCT, key=True),
        req('POST /products з існуючим slug → 409', 'POST', '/api/v1/products', [
            status(409), check('slug має бути унікальним', 'pm.expect(b.details.slug).to.exist')], body=PRODUCT, key=True),
        req('PUT /products/{id} — повна заміна', 'PUT', '/api/v1/products/{{productId}}', [
            status(200), check('ціна й назва оновлені', 'pm.expect(b.price).to.eql(1990); pm.expect(b.name).to.eql("Вінгспен (друге видання)")')],
            body={**PRODUCT, 'name': 'Вінгспен (друге видання)', 'price': 1990}, key=True),
        req('PATCH /products/{id} — змінити лише залишок', 'PATCH', '/api/v1/products/{{productId}}', [
            status(200), check('stock = 0, інші поля без змін', 'pm.expect(b.stock).to.eql(0); pm.expect(b.price).to.eql(1990)')],
            body={'stock': 0}, key=True),
        req('PATCH /products/{id} з players_max < players_min → 400', 'PATCH', '/api/v1/products/{{productId}}', [
            status(400), check('помилка players_max', 'pm.expect(b.details.players_max).to.exist')],
            body={'players_min': 6, 'players_max': 2}, key=True),
        req('DELETE /products/{id} — видалити створений товар', 'DELETE', '/api/v1/products/{{productId}}', [
            status(204), 'pm.test("Порожнє тіло", () => pm.expect(pm.response.text()).to.eql(""));'], key=True),
        req('GET /products/{id} після видалення → 404', 'GET', '/api/v1/products/{{productId}}', [status(404)]),
        req('DELETE /products/1 — товар у замовленнях → 409', 'DELETE', '/api/v1/products/1', [
            status(409), check('пояснення конфлікту', 'pm.expect(b.error).to.include("замовленнях")')], key=True),
    ]),
    ('3. Категорії (v1)', [
        req('GET /categories', 'GET', '/api/v1/categories', [
            status(200), check('7 категорій, є вкладені', 'pm.expect(b).to.have.lengthOf(7); pm.expect(b.some(c => c.parent_id)).to.be.true')]),
        req('POST /categories — підкатегорія «Стратегій»', 'POST', '/api/v1/categories', [
            status(201), check('parent_id = 2', 'pm.expect(b.parent_id).to.eql(2)'),
            'pm.collectionVariables.set("categoryId", pm.response.json().id);'],
            body={'name': 'Варгейми', 'slug': 'wargames', 'emoji': '⚔️', 'color': '#495057', 'parent_id': 2}, key=True),
        req('POST /categories третього рівня → 400', 'POST', '/api/v1/categories', [
            status(400), check('лише 2 рівні вкладеності', 'pm.expect(b.details.parent_id).to.include("верхнього рівня")')],
            body={'name': 'Глибока', 'slug': 'deep', 'emoji': '🎲', 'color': '#000000', 'parent_id': 3}, key=True),
        req('DELETE /categories/5 — є товари → 409', 'DELETE', '/api/v1/categories/5', [status(409)], key=True),
        req('DELETE /categories/{id} — видалити створену', 'DELETE', '/api/v1/categories/{{categoryId}}', [status(204)], key=True),
    ]),
    ('4. Замовлення (v1)', [
        req('POST /orders — оформити з промокодом', 'POST', '/api/v1/orders', [
            status(201), check('суми пораховані сервером', 'pm.expect(b.subtotal).to.eql(780); pm.expect(b.discount).to.eql(78); pm.expect(b.total).to.eql(702)'),
            check('статус «Нове», 1 позиція', 'pm.expect(b.status).to.eql("Нове"); pm.expect(b.items).to.have.lengthOf(1)'),
            'pm.collectionVariables.set("orderId", pm.response.json().id);'],
            body={'customer': CUSTOMER, 'address': 'Відділення Нової пошти №3', 'comment': 'Подарункове пакування',
                  'items': [{'product_id': 11, 'quantity': 2}], 'promo_code': 'WELCOME10'}),
        req('POST /orders — більше, ніж є на складі → 409', 'POST', '/api/v1/orders', [
            status(409), check('пояснення', 'pm.expect(b.error).to.include("на складі")')],
            body={'customer': CUSTOMER, 'address': 'НП 3', 'items': [{'product_id': 3, 'quantity': 9}]}),
        req('POST /orders — некоректні поля → 400', 'POST', '/api/v1/orders', [
            status(400), check('помилки вкладених полів', 'pm.expect(b.details).to.have.property("customer.email"); pm.expect(b.details).to.have.property("items[0].quantity")')],
            body={'customer': {**CUSTOMER, 'email': 'не-email'}, 'address': 'НП 3', 'items': [{'product_id': 1, 'quantity': 0}]}),
        req('GET /orders?status=Нове', 'GET', '/api/v1/orders?status=%D0%9D%D0%BE%D0%B2%D0%B5', [
            status(200), check('лише нові', 'pm.expect(b.every(o => o.status === "Нове")).to.be.true')], key=True),
        req('GET /orders/{id} — з позиціями', 'GET', '/api/v1/orders/{{orderId}}', [
            status(200), check('є items', 'pm.expect(b.items[0].name).to.eql("Доббль")')], key=True),
        req('PATCH /orders/{id} — статус «Відправлене»', 'PATCH', '/api/v1/orders/{{orderId}}', [
            status(200), check('статус змінено', 'pm.expect(b.status).to.eql("Відправлене")')], body={'status': 'Відправлене'}, key=True),
        req('PATCH /orders/{id} — невідомий статус → 400', 'PATCH', '/api/v1/orders/{{orderId}}', [status(400)],
            body={'status': 'Загублене'}, key=True),
        req('DELETE /orders/{id}', 'DELETE', '/api/v1/orders/{{orderId}}', [status(204)], key=True),
        req('GET /orders/{id} після видалення → 404', 'GET', '/api/v1/orders/{{orderId}}', [status(404)], key=True),
    ]),
    ('5. Клієнти, відгуки, промокоди (v1)', [
        req('GET /customers?q=олена', 'GET', '/api/v1/customers?q=%D0%BE%D0%BB%D0%B5%D0%BD%D0%B0', [
            status(200), check('знайдено одного клієнта', 'pm.expect(b).to.have.lengthOf(1); pm.expect(b[0].orders_count).to.eql(2)')], key=True),
        req('GET /customers/1 — з історією замовлень', 'GET', '/api/v1/customers/1', [
            status(200), check('є orders', 'pm.expect(b.orders).to.be.an("array").that.is.not.empty')], key=True),
        req('GET /customers/999 → 404', 'GET', '/api/v1/customers/999', [status(404)], key=True),
        req('GET /feedback — email не публікується', 'GET', '/api/v1/feedback', [
            status(200), check('немає email', 'pm.expect(b[0]).to.not.have.property("email")')]),
        req('POST /feedback', 'POST', '/api/v1/feedback', [status(201)],
            body={'name': 'Марія', 'email': 'maria@example.com', 'rating': 5, 'message': 'Чудовий магазин, швидка доставка!'}),
        req('POST /feedback — оцінка 7 і коротке повідомлення → 400', 'POST', '/api/v1/feedback', [
            status(400), check('дві помилки', 'pm.expect(b.details.rating).to.exist; pm.expect(b.details.message).to.exist')],
            body={'name': 'Марія', 'email': 'maria@example.com', 'rating': 7, 'message': 'ok'}),
        req('POST /promo-codes/check — PARTY15 на 1500 грн', 'POST', '/api/v1/promo-codes/check', [
            status(200), check('знижка 225 грн', 'pm.expect(b.valid).to.be.true; pm.expect(b.discount).to.eql(225)')],
            body={'code': 'party15', 'subtotal': 1500}),
        req('POST /promo-codes/check — сума замала', 'POST', '/api/v1/promo-codes/check', [
            status(200), check('valid=false з причиною', 'pm.expect(b.valid).to.be.false; pm.expect(b.reason).to.include("1000")')],
            body={'code': 'PARTY15', 'subtotal': 500}),
    ]),
    ('6. API v2 і загальні помилки', [
        req('GET /api/v2/ — точка входу', 'GET', '/api/v2/', [
            status(200), check('посилання на ресурси', 'pm.expect(b.data.links.products).to.eql("/api/v2/products")')]),
        req('GET /api/v2/products?per_page=5&page=2 — пагінація', 'GET', '/api/v2/products?per_page=5&page=2', [
            status(200), check('meta', 'pm.expect(b.meta).to.eql({page: 2, per_page: 5, total: 12, pages: 3})'),
            check('links.next / prev', 'pm.expect(b.links.next).to.include("page=3"); pm.expect(b.links.prev).to.include("page=1")')]),
        req('GET /api/v2/products/1 — новий формат товару', 'GET', '/api/v2/products/1', [
            status(200), check('ціна — об’єкт з валютою', 'pm.expect(b.data.price).to.eql({amount: 1150, currency: "UAH"})'),
            check('категорія вкладена', 'pm.expect(b.data.category.slug).to.eql("family")')]),
        req('GET /api/v2/products?per_page=500 → 400 (формат помилки v2)', 'GET', '/api/v2/products?per_page=500', [
            status(400), check('error.code = validation_error', 'pm.expect(b.error.code).to.eql("validation_error"); pm.expect(b.error.fields.per_page).to.exist')]),
        req('GET /api/v2/categories — дерево', 'GET', '/api/v2/categories', [
            status(200), check('у «Стратегій» 2 підкатегорії', 'pm.expect(b.data.find(c => c.slug === "strategy").children).to.have.lengthOf(2)')]),
        req('POST /api/v2/orders', 'POST', '/api/v2/orders', [
            status(201), check('totals у конверті data', 'pm.expect(b.data.totals.total).to.eql(1770); pm.expect(b.data.totals.currency).to.eql("UAH")')],
            body={'customer': CUSTOMER, 'address': 'НП 3', 'items': [{'product_id': 7, 'quantity': 3}]}),
        req('GET /api/v2/products/999 → 404 (формат v2)', 'GET', '/api/v2/products/999', [
            status(404), check('error.status і code', 'pm.expect(b.error.status).to.eql(404); pm.expect(b.error.code).to.eql("not_found")')]),
        req('GET /api/v1/unknown → 404 у JSON', 'GET', '/api/v1/unknown', [status(404), JSON_CT]),
        req('DELETE /api/v1/health → 405 із заголовком Allow', 'DELETE', '/api/v1/health', [
            status(405), 'pm.test("Заголовок Allow", () => pm.expect(pm.response.headers.get("Allow")).to.include("GET"));']),
    ]),
]


def build():
    return {
        'info': {
            'name': 'Кубик — REST API (лабораторна 05)',
            'description': 'Колекція тестових сценаріїв для API магазину настільних ігор «Кубик». '
                           'Запускати на свіжій БД (python seed_data.py). Кожен запит містить тести pm.test.',
            'schema': 'https://schema.getpostman.com/json/collection/v2.1.0/collection.json',
        },
        'variable': [
            {'key': 'baseUrl', 'value': 'http://127.0.0.1:5000'},
            {'key': 'apiKey', 'value': 'dev-api-key'},
            {'key': 'productId', 'value': ''},
            {'key': 'categoryId', 'value': ''},
            {'key': 'orderId', 'value': ''},
        ],
        'item': [{'name': name, 'item': items} for name, items in FOLDERS],
    }


if __name__ == '__main__':
    collection = build()
    with open(OUT, 'w', encoding='utf-8') as file:
        json.dump(collection, file, ensure_ascii=False, indent=2)
    total = sum(len(items) for _, items in FOLDERS)
    print(f'postman_collection.json: {len(FOLDERS)} папок, {total} запитів')
