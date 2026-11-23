"""Відгуки: CRUD (Create — форма на сайті; Read, Update, Delete — адмін-панель)."""
from . import execute, now, query_all, query_one


def add_feedback(name, email, rating, message):
    return execute('INSERT INTO feedback (name, email, rating, message, created_at) VALUES (?, ?, ?, ?, ?)',
                   (name, email, rating, message, now()))


def list_feedback(only_unread=False):
    sql = 'SELECT * FROM feedback'
    if only_unread:
        sql += ' WHERE is_read = 0'
    return query_all(sql + ' ORDER BY is_read, id DESC')


def latest_public(limit=3):
    """Останні позитивні відгуки для головної сторінки."""
    return query_all('SELECT name, rating, message FROM feedback WHERE rating >= 4 ORDER BY id DESC LIMIT ?', (limit,))


def get_feedback(feedback_id):
    return query_one('SELECT * FROM feedback WHERE id = ?', (feedback_id,))


def mark_read(feedback_id, is_read=True):
    execute('UPDATE feedback SET is_read = ? WHERE id = ?', (int(is_read), feedback_id))


def delete_feedback(feedback_id):
    execute('DELETE FROM feedback WHERE id = ?', (feedback_id,))


def average_rating():
    row = query_one('SELECT AVG(rating) AS avg, COUNT(*) AS n FROM feedback')
    return (round(row['avg'], 1) if row['avg'] else None), row['n']
