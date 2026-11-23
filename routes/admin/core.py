"""Вхід, дашборд, керування замовленнями та відгуками."""
from urllib.parse import urlparse

from flask import abort, flash, redirect, render_template, request, session, url_for

from models import feedback, orders
from security import admin_required, check_admin_password

from . import admin_bp


def safe_next(target):
    """Перенаправляємо лише на внутрішні адреси /admin (захист від open redirect)."""
    if target and urlparse(target).netloc == '' and target.startswith('/admin'):
        return target
    return url_for('admin.dashboard')


# ------------------------------------------------------------------ вхід

@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if check_admin_password(request.form.get('password', '')):
            session['is_admin'] = True
            flash('Вітаємо в адмін-панелі!', 'success')
            return redirect(safe_next(request.args.get('next')))
        flash('Неправильний пароль.', 'error')
    return render_template('admin/login.html')


@admin_bp.post('/logout')
def logout():
    session.pop('is_admin', None)
    flash('Ви вийшли з адмін-панелі.', 'success')
    return redirect(url_for('main.home'))


# ------------------------------------------------------------------ дашборд

@admin_bp.get('/')
@admin_required
def dashboard():
    return render_template('admin/dashboard.html', stats=orders.stats(), recent=orders.list_orders()[:5],
                           statuses=orders.ORDER_STATUSES, unread=feedback.list_feedback(only_unread=True)[:3])


# ------------------------------------------------------------------ замовлення

@admin_bp.get('/orders')
@admin_required
def order_list():
    status = request.args.get('status', '')
    if status not in orders.ORDER_STATUSES:
        status = ''
    return render_template('admin/orders.html', orders=orders.list_orders(status or None),
                           statuses=orders.ORDER_STATUSES, current=status)


@admin_bp.get('/orders/<int:order_id>')
@admin_required
def order_detail(order_id):
    order, items = orders.get_order(order_id)
    if order is None:
        abort(404)
    return render_template('admin/order_detail.html', order=order, items=items, statuses=orders.ORDER_STATUSES)


@admin_bp.post('/orders/<int:order_id>/status')
@admin_required
def order_status(order_id):
    try:
        orders.update_status(order_id, request.form.get('status', ''))
        flash(f'Статус замовлення №{order_id} змінено.', 'success')
    except ValueError as error:
        flash(str(error), 'error')
    return redirect(url_for('admin.order_detail', order_id=order_id))


@admin_bp.post('/orders/<int:order_id>/delete')
@admin_required
def order_delete(order_id):
    orders.delete_order(order_id)
    flash(f'Замовлення №{order_id} видалено.', 'success')
    return redirect(url_for('admin.order_list'))


# ------------------------------------------------------------------ відгуки

@admin_bp.get('/feedback')
@admin_required
def feedback_list():
    return render_template('admin/feedback.html', items=feedback.list_feedback())


@admin_bp.post('/feedback/<int:feedback_id>/read')
@admin_required
def feedback_read(feedback_id):
    item = feedback.get_feedback(feedback_id)
    if item:
        feedback.mark_read(feedback_id, not item['is_read'])
    return redirect(url_for('admin.feedback_list'))


@admin_bp.post('/feedback/<int:feedback_id>/delete')
@admin_required
def feedback_delete(feedback_id):
    feedback.delete_feedback(feedback_id)
    flash('Відгук видалено.', 'success')
    return redirect(url_for('admin.feedback_list'))
