"""Магазин: каталог з пошуком і фільтрами, сторінка товару, кошик (у сесії), промокод, оформлення."""
from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for

import forms
from models import catalog, orders

shop_bp = Blueprint('shop', __name__)

MAX_QUANTITY = 10


def get_cart():
    """Кошик у сесії: {"id товару": кількість} (ключі — рядки, бо сесія серіалізується в JSON)."""
    return dict(session.get('cart', {}))


def save_cart(cart):
    session['cart'] = cart
    if not cart:
        session.pop('promo', None)


def read_quantity():
    try:
        return max(1, min(int(request.form.get('quantity', 1)), MAX_QUANTITY))
    except ValueError:
        return 1


# ------------------------------------------------------------------ каталог

@shop_bp.get('/catalog', endpoint='catalog')
def catalog_page():
    filters = forms.parse_catalog_filters(request.args, catalog.SORT_OPTIONS)
    category = catalog.get_category_by_slug(filters['category']) if filters['category'] else None
    query = {**filters, 'category_id': category['id'] if category else None}
    products = catalog.search_products(query)
    active = any([filters['q'], category, filters['min_price'] is not None,
                  filters['max_price'] is not None, filters['players'], filters['in_stock']])
    return render_template('catalog.html', products=products, filters=filters, category=category,
                           tree=catalog.category_tree(), sort_options=catalog.SORT_OPTIONS,
                           price_range=catalog.price_range(), filters_active=active)


@shop_bp.get('/catalog/<slug>')
def product_page(slug):
    product = catalog.get_product_by_slug(slug)
    if product is None:
        abort(404)
    return render_template('product.html', product=product, related=catalog.related_products(product),
                           in_cart=get_cart().get(str(product['id']), 0))


# ------------------------------------------------------------------ кошик

@shop_bp.post('/cart/add/<int:product_id>')
def add_to_cart(product_id):
    product = catalog.get_product(product_id)
    if product is None:
        abort(404)
    cart = get_cart()
    key = str(product_id)
    wanted = min(cart.get(key, 0) + read_quantity(), MAX_QUANTITY, product['stock'])
    if wanted <= cart.get(key, 0):
        flash(f'«{product["name"]}»: більше немає в наявності.', 'error')
    else:
        cart[key] = wanted
        save_cart(cart)
        flash(f'«{product["name"]}» додано до кошика.', 'success')
    return redirect(request.form.get('next') or url_for('shop.cart'))


@shop_bp.get('/cart')
def cart():
    lines, subtotal = orders.cart_lines(get_cart())
    promo, promo_error = None, None
    if session.get('promo'):
        promo, promo_error = orders.check_promo(session['promo'], subtotal)
    discount = orders.calc_discount(subtotal, promo)
    return render_template('cart.html', lines=lines, subtotal=subtotal, promo=promo, promo_error=promo_error,
                           discount=discount, total=round(subtotal - discount, 2), max_quantity=MAX_QUANTITY)


@shop_bp.post('/cart/update/<int:product_id>')
def update_cart(product_id):
    cart = get_cart()
    product = catalog.get_product(product_id)
    if product and str(product_id) in cart:
        cart[str(product_id)] = min(read_quantity(), product['stock']) or 1
        save_cart(cart)
    return redirect(url_for('shop.cart'))


@shop_bp.post('/cart/remove/<int:product_id>')
def remove_from_cart(product_id):
    cart = get_cart()
    cart.pop(str(product_id), None)
    save_cart(cart)
    flash('Товар прибрано з кошика.', 'success')
    return redirect(url_for('shop.cart'))


@shop_bp.post('/cart/promo')
def apply_promo():
    """Рівень 3: застосування промокоду до кошика."""
    code = request.form.get('code', '').strip().upper()
    if request.form.get('action') == 'remove' or not code:
        session.pop('promo', None)
        return redirect(url_for('shop.cart'))
    _, subtotal = orders.cart_lines(get_cart())
    promo, error = orders.check_promo(code, subtotal)
    if promo:
        session['promo'] = promo['code']
        flash(f'Промокод {promo["code"]} застосовано: −{promo["discount_percent"]}%.', 'success')
    else:
        session.pop('promo', None)
        flash(error, 'error')
    return redirect(url_for('shop.cart'))


# ------------------------------------------------------------------ оформлення

@shop_bp.route('/checkout', methods=['GET', 'POST'])
def checkout():
    cart_now = get_cart()
    if not cart_now:
        flash('Кошик порожній — додайте гру з каталогу.', 'error')
        return redirect(url_for('shop.catalog'))

    values, errors = {}, {}
    if request.method == 'POST':
        values, errors = forms.checkout_form(request.form)
        if not errors:
            customer = {k: values[k] for k in ('name', 'email', 'phone', 'city')}
            address = f'{values["city"]}, {values["address"]}'
            try:
                order_id = orders.create_order(customer, address, values['comment'], cart_now, session.get('promo'))
            except orders.OrderError as error:
                flash(str(error), 'error')
            else:
                save_cart({})
                session.pop('promo', None)  # промокод діє на одне замовлення
                session.setdefault('my_orders', []).append(order_id)
                session.modified = True
                return redirect(url_for('shop.order_success', order_id=order_id))
        else:
            flash('Перевірте поля форми.', 'error')

    lines, subtotal = orders.cart_lines(cart_now)
    promo = orders.check_promo(session['promo'], subtotal)[0] if session.get('promo') else None
    discount = orders.calc_discount(subtotal, promo)
    return render_template('checkout.html', values=values, errors=errors, lines=lines, subtotal=subtotal,
                           promo=promo, discount=discount, total=round(subtotal - discount, 2))


@shop_bp.get('/order/<int:order_id>')
def order_success(order_id):
    """Сторінку замовлення бачить лише той, хто його оформив (id зберігається в сесії)."""
    if order_id not in session.get('my_orders', []):
        abort(404)
    order, items = orders.get_order(order_id)
    if order is None:
        abort(404)
    return render_template('order_success.html', order=order, items=items)
