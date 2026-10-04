"""Панель администратора: статистика, управление пользователями, аудит."""
from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from . import models
from .security import admin_required

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.route("/")
@admin_required
def index():
    return render_template("admin.html", stats=models.admin_stats())


@bp.route("/users")
@admin_required
def users():
    return render_template("admin_users.html", users=models.list_users())


@bp.route("/users/<int:user_id>/block", methods=["POST"])
@admin_required
def block_user(user_id):
    user = models.get_user_by_id(user_id)
    if user is None:
        abort(404)
    if user["id"] == g.user["id"]:
        flash("Нельзя заблокировать самого себя.", "danger")
        return redirect(url_for("admin.users"))
    models.set_blocked(user_id, True)
    models.write_audit(g.user["id"], "block_user", user["username"])
    flash(f"Пользователь {user['username']} заблокирован.", "success")
    return redirect(url_for("admin.users"))


@bp.route("/users/<int:user_id>/unblock", methods=["POST"])
@admin_required
def unblock_user(user_id):
    user = models.get_user_by_id(user_id)
    if user is None:
        abort(404)
    models.set_blocked(user_id, False)
    models.write_audit(g.user["id"], "unblock_user", user["username"])
    flash(f"Пользователь {user['username']} разблокирован.", "success")
    return redirect(url_for("admin.users"))


@bp.route("/audit")
@admin_required
def audit():
    return render_template("admin_audit.html", entries=models.list_audit())
