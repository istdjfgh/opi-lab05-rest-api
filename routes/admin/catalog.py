"""Керування товарами та категоріями (з вкладеністю)."""
import sqlite3

from flask import abort, flash, redirect, render_template, request, url_for

import forms
from models import catalog
from security import admin_required

from . import admin_bp


# ------------------------------------------------------------------ товари

@admin_bp.get('/products')
@admin_required
def products():
    filters = forms.parse_catalog_filters(request.args, catalog.SORT_OPTIONS)
    return render_template('admin/products.html', products=catalog.search_products({'q': filters['q'], 'sort': 'name'}),
                           q=filters['q'])


def _product_form(product=None):
    """Спільна логіка створення і редагування товару."""
    categories = catalog.list_categories()
    values = dict(product) if product else {'emoji': '🎲', 'players_min': 2, 'players_max': 4, 'age': 8,
                                            'minutes': 30, 'stock': 5}
    errors = {}
    if request.method == 'POST':
        values, errors = forms.product_form(request.form, {c['id'] for c in categories})
        if not errors:
            try:
                catalog.save_product(values, product['id'] if product else None)
            except sqlite3.IntegrityError:
                errors['slug'] = 'Такий slug уже використовується іншим товаром.'
            else:
                flash(f'Товар «{values["name"]}» збережено.', 'success')
                return redirect(url_for('admin.products'))
        flash('Перевірте поля форми.', 'error')
    return render_template('admin/product_form.html', values=values, errors=errors,
                           categories=categories, product=product)


@admin_bp.route('/products/new', methods=['GET', 'POST'])
@admin_required
def product_new():
    return _product_form()


@admin_bp.route('/products/<int:product_id>/edit', methods=['GET', 'POST'])
@admin_required
def product_edit(product_id):
    product = catalog.get_product(product_id)
    if product is None:
        abort(404)
    return _product_form(product)


@admin_bp.post('/products/<int:product_id>/delete')
@admin_required
def product_delete(product_id):
    try:
        catalog.delete_product(product_id)
        flash('Товар видалено.', 'success')
    except sqlite3.IntegrityError:
        flash('Товар є в замовленнях — його не можна видалити (історія замовлень зламається). '
              'Поставте залишок 0, щоб зняти з продажу.', 'error')
    return redirect(url_for('admin.products'))


# ------------------------------------------------------------------ категорії

def _allowed_parents(category_id=None):
    """Батьком може бути лише категорія верхнього рівня і не сама категорія (вкладеність — 2 рівні)."""
    return {c['id'] for c in catalog.list_categories() if c['parent_id'] is None and c['id'] != category_id}


@admin_bp.route('/categories', methods=['GET', 'POST'])
@admin_required
def categories():
    """Список категорій + форма додавання на тій самій сторінці."""
    values, errors = {'emoji': '🎲', 'color': '#d9480f'}, {}
    if request.method == 'POST':
        values, errors = forms.category_form(request.form, _allowed_parents())
        if not errors:
            try:
                catalog.save_category(values)
                flash(f'Категорію «{values["name"]}» додано.', 'success')
                return redirect(url_for('admin.categories'))
            except sqlite3.IntegrityError:
                errors['slug'] = 'Такий slug уже існує.'
        flash('Перевірте поля форми.', 'error')
    return render_template('admin/categories.html', tree=catalog.category_tree(), values=values, errors=errors,
                           parents=[c for c in catalog.list_categories() if c['parent_id'] is None])


@admin_bp.route('/categories/<int:category_id>/edit', methods=['GET', 'POST'])
@admin_required
def category_edit(category_id):
    category = catalog.get_category(category_id)
    if category is None:
        abort(404)
    values, errors = dict(category), {}
    if request.method == 'POST':
        values, errors = forms.category_form(request.form, _allowed_parents(category_id))
        has_children = any(c['parent_id'] == category_id for c in catalog.list_categories())
        if values['parent_id'] and has_children:
            errors['parent_id'] = 'Категорія має підкатегорії, тому не може стати вкладеною.'
        if not errors:
            try:
                catalog.save_category(values, category_id)
                flash('Категорію збережено.', 'success')
                return redirect(url_for('admin.categories'))
            except sqlite3.IntegrityError:
                errors['slug'] = 'Такий slug уже існує.'
        flash('Перевірте поля форми.', 'error')
    parents = [c for c in catalog.list_categories() if c['id'] in _allowed_parents(category_id)]
    return render_template('admin/category_form.html', values=values, errors=errors, parents=parents,
                           category=category)


@admin_bp.post('/categories/<int:category_id>/delete')
@admin_required
def category_delete(category_id):
    try:
        catalog.delete_category(category_id)
        flash('Категорію видалено.', 'success')
    except sqlite3.IntegrityError:
        flash('У категорії є товари або підкатегорії — спочатку перенесіть їх.', 'error')
    return redirect(url_for('admin.categories'))
