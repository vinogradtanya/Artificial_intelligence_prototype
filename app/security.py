"""Вспомогательные средства: загрузка текущего пользователя и декораторы прав."""
from functools import wraps

from flask import abort, flash, g, redirect, request, session, url_for

from . import models


def load_user():
    """Загружает пользователя из сессии в g.user; разлогинивает заблокированных."""
    uid = session.get("user_id")
    g.user = models.get_user_by_id(uid) if uid else None
    if g.user and g.user["is_blocked"] and request.endpoint not in ("auth.logout", "static"):
        session.pop("user_id", None)
        g.user = None
        flash("Ваш аккаунт заблокирован администратором.", "danger")


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.get("user") is None:
            flash("Требуется вход в систему.", "warning")
            return redirect(url_for("auth.login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if g.user["role"] != "admin":
            abort(403)
        return view(*args, **kwargs)

    return wrapped


def init_app(app):
    app.before_request(load_user)
