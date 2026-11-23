"""Інформаційні сторінки сайту."""
from datetime import datetime

from flask import Blueprint, render_template

import content
from models import catalog, feedback

main_bp = Blueprint('main', __name__)


@main_bp.get('/')
def home():
    avg, reviews = feedback.average_rating()
    return render_template('home.html', bestsellers=catalog.bestsellers(), advantages=content.ADVANTAGES,
                           tree=catalog.category_tree(), reviews=feedback.latest_public(),
                           avg_rating=avg, reviews_count=reviews)


@main_bp.get('/about')
def about():
    return render_template('about.html', years=datetime.now().year - content.SHOP['founded'])


@main_bp.get('/delivery')
def delivery():
    return render_template('delivery.html', methods=content.DELIVERY_METHODS,
                           payments=content.PAYMENT_METHODS, faq=content.FAQ)


@main_bp.get('/contacts')
def contacts():
    return render_template('contacts.html', hours=content.OPENING_HOURS)
