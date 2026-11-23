"""Клієнти (рівень 2) і промокоди (рівень 3)."""
import sqlite3

from flask import abort, flash, redirect, render_template, request, url_for

import forms
from models import customers, orders
from security import admin_required

from . import admin_bp


# ------------------------------------------------------------------ клієнти

@admin_bp.get('/customers')
@admin_required
def customer_list():
    q = request.args.get('q', '').strip()[:80]
    return render_template('admin/customers.html', customers=customers.list_customers(q), q=q)


@admin_bp.get('/customers/<int:customer_id>')
@admin_required
def customer_detail(customer_id):
    customer = customers.get_customer(customer_id)
    if customer is None:
        abort(404)
    history = orders.list_orders(customer_id=customer_id)
    spent = sum(o['total'] for o in history if o['status'] != 'Скасоване')
    return render_template('admin/customer_detail.html', customer=customer, history=history, spent=spent)


def _customer_form(customer=None):
    values, errors = (dict(customer) if customer else {}), {}
    if request.method == 'POST':
        values, errors = forms.customer_form(request.form)
        if not errors:
            try:
                saved_id = customers.save_customer(values, customer['id'] if customer else None)
            except sqlite3.IntegrityError:
                errors['email'] = 'Клієнт з таким email уже є.'
            else:
                flash(f'Клієнта «{values["name"]}» збережено.', 'success')
                return redirect(url_for('admin.customer_detail', customer_id=saved_id))
        flash('Перевірте поля форми.', 'error')
    return render_template('admin/customer_form.html', values=values, errors=errors, customer=customer)


@admin_bp.route('/customers/new', methods=['GET', 'POST'])
@admin_required
def customer_new():
    return _customer_form()


@admin_bp.route('/customers/<int:customer_id>/edit', methods=['GET', 'POST'])
@admin_required
def customer_edit(customer_id):
    customer = customers.get_customer(customer_id)
    if customer is None:
        abort(404)
    return _customer_form(customer)


@admin_bp.post('/customers/<int:customer_id>/delete')
@admin_required
def customer_delete(customer_id):
    try:
        customers.delete_customer(customer_id)
        flash('Клієнта видалено.', 'success')
    except sqlite3.IntegrityError:
        flash('У клієнта є замовлення — видалення заборонено, щоб не втратити історію.', 'error')
        return redirect(url_for('admin.customer_detail', customer_id=customer_id))
    return redirect(url_for('admin.customer_list'))


# ------------------------------------------------------------------ промокоди

@admin_bp.route('/promos', methods=['GET', 'POST'])
@admin_required
def promos():
    values, errors = {'is_active': 1, 'discount_percent': 10}, {}
    if request.method == 'POST':
        values, errors = forms.promo_form(request.form)
        if not errors:
            try:
                orders.save_promo(values)
                flash(f'Промокод {values["code"]} створено.', 'success')
                return redirect(url_for('admin.promos'))
            except sqlite3.IntegrityError:
                errors['code'] = 'Такий код уже існує.'
        flash('Перевірте поля форми.', 'error')
    return render_template('admin/promos.html', promos=orders.list_promos(), values=values, errors=errors)


@admin_bp.route('/promos/<int:promo_id>/edit', methods=['GET', 'POST'])
@admin_required
def promo_edit(promo_id):
    promo = orders.get_promo(promo_id)
    if promo is None:
        abort(404)
    values, errors = dict(promo), {}
    if request.method == 'POST':
        values, errors = forms.promo_form(request.form)
        if not errors:
            try:
                orders.save_promo(values, promo_id)
                flash('Промокод збережено.', 'success')
                return redirect(url_for('admin.promos'))
            except sqlite3.IntegrityError:
                errors['code'] = 'Такий код уже існує.'
        flash('Перевірте поля форми.', 'error')
    return render_template('admin/promo_form.html', values=values, errors=errors, promo=promo)


@admin_bp.post('/promos/<int:promo_id>/toggle')
@admin_required
def promo_toggle(promo_id):
    orders.toggle_promo(promo_id)
    return redirect(url_for('admin.promos'))


@admin_bp.post('/promos/<int:promo_id>/delete')
@admin_required
def promo_delete(promo_id):
    orders.delete_promo(promo_id)
    flash('Промокод видалено.', 'success')
    return redirect(url_for('admin.promos'))
