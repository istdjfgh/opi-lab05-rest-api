"""Форма зворотного зв'язку (Create для таблиці feedback)."""
from flask import Blueprint, flash, redirect, render_template, request, url_for

import forms
from models import feedback

feedback_bp = Blueprint('feedback', __name__)


# endpoint 'feedback.feedback' (як у меню); функцію названо інакше, щоб не затіняти модуль models.feedback
@feedback_bp.route('/feedback', methods=['GET', 'POST'], endpoint='feedback')
def feedback_page():
    values, errors = {}, {}
    if request.method == 'POST':
        values, errors = forms.feedback_form(request.form)
        if not errors:
            feedback.add_feedback(values['name'], values['email'], values['rating'], values['message'])
            flash('Дякуємо! Ваш відгук надіслано.', 'success')
            # Post/Redirect/Get: оновлення сторінки не відправить форму вдруге
            return redirect(url_for('feedback.feedback'))
        flash('Перевірте поля форми.', 'error')
    avg, count = feedback.average_rating()
    return render_template('feedback.html', values=values, errors=errors,
                           reviews=feedback.latest_public(6), avg_rating=avg, reviews_count=count)
