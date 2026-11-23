-- ============================================================
-- Схема бази даних магазину «Кубик» (SQLite).
-- Скрипт ідемпотентний: CREATE ... IF NOT EXISTS можна виконувати повторно.
-- ============================================================

-- Категорії з вкладеністю: parent_id посилається на цю ж таблицю
-- (наприклад, «Стратегії» -> «Економічні»). NULL — категорія верхнього рівня.
CREATE TABLE IF NOT EXISTS categories (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    name      TEXT    NOT NULL,
    slug      TEXT    NOT NULL UNIQUE,
    emoji     TEXT    NOT NULL DEFAULT '🎲',
    color     TEXT    NOT NULL DEFAULT '#d9480f',
    parent_id INTEGER REFERENCES categories (id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS products (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT    NOT NULL,
    slug          TEXT    NOT NULL UNIQUE,
    category_id   INTEGER NOT NULL REFERENCES categories (id) ON DELETE RESTRICT,
    price         REAL    NOT NULL CHECK (price >= 0),
    stock         INTEGER NOT NULL DEFAULT 0 CHECK (stock >= 0),
    players_min   INTEGER NOT NULL DEFAULT 1 CHECK (players_min >= 1),
    players_max   INTEGER NOT NULL DEFAULT 4 CHECK (players_max >= players_min),
    age           INTEGER NOT NULL DEFAULT 8,
    minutes       INTEGER NOT NULL DEFAULT 30,
    emoji         TEXT    NOT NULL DEFAULT '🎲',
    short         TEXT    NOT NULL DEFAULT '',
    description   TEXT    NOT NULL DEFAULT '',
    is_bestseller INTEGER NOT NULL DEFAULT 0 CHECK (is_bestseller IN (0, 1)),
    created_at    TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS feedback (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT    NOT NULL,
    email      TEXT    NOT NULL,
    rating     INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    message    TEXT    NOT NULL,
    is_read    INTEGER NOT NULL DEFAULT 0 CHECK (is_read IN (0, 1)),
    created_at TEXT    NOT NULL
);

-- Рівень 2: клієнти. Email унікальний — повторне замовлення з тим самим
-- email прив'язується до наявного клієнта, тож видно історію його замовлень.
CREATE TABLE IF NOT EXISTS customers (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT    NOT NULL,
    email      TEXT    NOT NULL UNIQUE COLLATE NOCASE,
    phone      TEXT    NOT NULL DEFAULT '',
    city       TEXT    NOT NULL DEFAULT '',
    note       TEXT    NOT NULL DEFAULT '',
    created_at TEXT    NOT NULL
);

-- Рівень 3: промокоди зі знижкою у відсотках.
CREATE TABLE IF NOT EXISTS promo_codes (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    code             TEXT    NOT NULL UNIQUE COLLATE NOCASE,
    discount_percent INTEGER NOT NULL CHECK (discount_percent BETWEEN 1 AND 90),
    min_total        REAL    NOT NULL DEFAULT 0 CHECK (min_total >= 0),
    valid_until      TEXT,                 -- NULL = безстроковий; формат YYYY-MM-DD
    max_uses         INTEGER,              -- NULL = без обмеження
    used_count       INTEGER NOT NULL DEFAULT 0,
    is_active        INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1))
);

CREATE TABLE IF NOT EXISTS orders (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL REFERENCES customers (id) ON DELETE RESTRICT,
    address     TEXT    NOT NULL,
    comment     TEXT    NOT NULL DEFAULT '',
    status      TEXT    NOT NULL,
    subtotal    REAL    NOT NULL,
    discount    REAL    NOT NULL DEFAULT 0,
    total       REAL    NOT NULL,
    promo_code  TEXT,                       -- код зберігаємо текстом: історія не зміниться, якщо промокод видалять
    created_at  TEXT    NOT NULL
);

-- Проміжна таблиця зв'язку «багато-до-багатьох» між замовленнями і товарами.
-- unit_price фіксує ціну на момент покупки.
CREATE TABLE IF NOT EXISTS order_items (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id   INTEGER NOT NULL REFERENCES orders (id)   ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products (id) ON DELETE RESTRICT,
    quantity   INTEGER NOT NULL CHECK (quantity > 0),
    unit_price REAL    NOT NULL CHECK (unit_price >= 0),
    UNIQUE (order_id, product_id)
);

CREATE INDEX IF NOT EXISTS idx_products_category ON products (category_id);
CREATE INDEX IF NOT EXISTS idx_orders_customer   ON orders (customer_id);
CREATE INDEX IF NOT EXISTS idx_orders_status     ON orders (status);
CREATE INDEX IF NOT EXISTS idx_items_order       ON order_items (order_id);
