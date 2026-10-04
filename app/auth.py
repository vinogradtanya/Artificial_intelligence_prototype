"""Регистрация, вход и выход."""
from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from . import models

bp = Blueprint("auth", __name__)


def _safe_next(target):
    """Защита от open redirect: разрешаем только локальные пути."""
    if target and target.startswith("/") and not target.startswith("//"):
        return target
    return None


@bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        password2 = request.form.get("password2", "")

        errors = []
        if len(username) < 3:
            errors.append("Логин должен содержать не менее 3 символов.")
        if "@" not in email or "." not in email:
            errors.append("Введите корректный email.")
        if len(password) < 6:
            errors.append("Пароль должен содержать не менее 6 символов.")
        if password != password2:
            errors.append("Пароли не совпадают.")
        if models.get_user_by_username(username):
            errors.append("Пользователь с таким логином уже существует.")
        if models.get_user_by_email(email):
            errors.append("Пользователь с таким email уже существует.")

        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("register.html", form=request.form), 400

        start = current_app.config["START_BALANCE"]
        uid = models.create_user(username, email, password, balance=0)
        models.change_balance(uid, start, "topup", "Стартовый бонус при регистрации")
        flash("Регистрация завершена. Войдите в систему.", "success")
        return redirect(url_for("auth.login"))

    return render_template("register.html", form={})


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        login_value = request.form.get("login", "").strip()
        password = request.form.get("password", "")
        user = models.get_user_by_login(login_value)

        if not user or not models.verify_password(user, password):
            flash("Неверный логин или пароль.", "danger")
            return render_template("login.html"), 401
        if user["is_blocked"]:
            flash("Аккаунт заблокирован администратором.", "danger")
            return render_template("login.html"), 403

        session.clear()
        session["user_id"] = user["id"]
        flash("Вы вошли в систему.", "success")
        return redirect(_safe_next(request.args.get("next")) or url_for("main.dashboard"))

    return render_template("login.html")


@bp.route("/logout")
def logout():
    session.clear()
    flash("Вы вышли из системы.", "info")
    return redirect(url_for("auth.login"))
