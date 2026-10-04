"""Личный кабинет: профиль, тариф, пополнение баланса (mock)."""
from flask import Blueprint, current_app, flash, g, redirect, render_template, request, url_for

from . import generator, models
from .security import login_required

bp = Blueprint("main", __name__)


def _user_stats(user_id):
    """Краткая статистика пользователя для дашборда."""
    gens = models.list_generations(user_id=user_id, limit=1000)
    by_type = {}
    for gen in gens:
        by_type[gen["content_type"]] = by_type.get(gen["content_type"], 0) + 1
    return {
        "total": len(gens),
        "by_type": by_type,
        "spent": sum(x["tokens_spent"] for x in gens),
    }


@bp.route("/")
@login_required
def dashboard():
    stats = _user_stats(g.user["id"])
    recent = models.list_generations(user_id=g.user["id"], limit=5)
    return render_template("dashboard.html", stats=stats, recent=recent)


@bp.route("/cabinet")
@login_required
def cabinet():
    stats = _user_stats(g.user["id"])
    txs = models.list_transactions(user_id=g.user["id"], limit=10)
    return render_template(
        "cabinet.html",
        stats=stats,
        transactions=txs,
        tariffs=current_app.config["TARIFFS"],
        token_cost=current_app.config["TOKEN_COST"],
        factors=current_app.config["TARIFF_COST_FACTOR"],
        bonuses=current_app.config["TARIFF_TOPUP_BONUS"],
    )


@bp.route("/cabinet/profile", methods=["POST"])
@login_required
def update_profile():
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")
    password2 = request.form.get("password2", "")

    if email and ("@" not in email or "." not in email):
        flash("Некорректный email.", "danger")
        return redirect(url_for("main.cabinet"))

    existing = models.get_user_by_email(email) if email else None
    if existing and existing["id"] != g.user["id"]:
        flash("Этот email уже занят.", "danger")
        return redirect(url_for("main.cabinet"))

    new_password = None
    if password:
        if len(password) < 6:
            flash("Пароль слишком короткий.", "danger")
            return redirect(url_for("main.cabinet"))
        if password != password2:
            flash("Пароли не совпадают.", "danger")
            return redirect(url_for("main.cabinet"))
        new_password = password

    models.update_profile(g.user["id"], email=email or None, password=new_password)
    models.write_audit(g.user["id"], "profile_update", email)
    flash("Профиль обновлён.", "success")
    return redirect(url_for("main.cabinet"))


@bp.route("/cabinet/tariff", methods=["POST"])
@login_required
def change_tariff():
    tariff = request.form.get("tariff", "")
    if tariff not in current_app.config["TARIFFS"]:
        flash("Неизвестный тариф.", "danger")
        return redirect(url_for("main.cabinet"))
    models.set_tariff(g.user["id"], tariff)
    models.write_audit(g.user["id"], "tariff_change", tariff)
    flash(f"Тариф изменён на «{tariff}».", "success")
    return redirect(url_for("main.cabinet"))


@bp.route("/cabinet/topup", methods=["POST"])
@login_required
def topup():
    """Имитация оплаты: без реального платежа просто увеличиваем баланс."""
    try:
        amount = int(request.form.get("amount", "0"))
    except ValueError:
        amount = 0
    if amount <= 0 or amount > 100000:
        flash("Некорректная сумма пополнения.", "danger")
        return redirect(url_for("main.cabinet"))

    bonus = int(round(amount * current_app.config["TARIFF_TOPUP_BONUS"].get(g.user["tariff"], 0)))
    total = amount + bonus
    balance = models.change_balance(
        g.user["id"], total, "topup",
        f"Пополнение (mock-платёж) на {amount} токенов, бонус {bonus}",
    )
    models.write_audit(g.user["id"], "topup", f"+{total}")
    flash(f"Баланс пополнен на {total} токенов (вкл. бонус {bonus}). Текущий баланс: {balance}.", "success")
    return redirect(url_for("main.cabinet"))
