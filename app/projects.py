"""Создание проекта (генерации), библиотека результатов и выдача медиафайлов."""
import os
import secrets
from datetime import datetime

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    g,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)

from . import generator, models, moderation
from .security import login_required

bp = Blueprint("projects", __name__)

_EXT = {"image": "png", "audio": "wav"}


def _collect_params(content_type, form):
    """Извлекает параметры генерации из формы в зависимости от типа контента."""
    if content_type == "text":
        return {"length": int(form.get("length", 0) or 0)}
    if content_type == "image":
        size = form.get("size", "512x512")
        if size not in ("256x256", "512x512", "768x768", "1024x1024"):
            size = "512x512"
        return {"size": size, "style": form.get("style", "gradient")}
    if content_type == "audio":
        try:
            duration = float(form.get("duration", 3) or 3)
        except ValueError:
            duration = 3.0
        return {"duration": duration, "voice": form.get("voice", "default")}
    return {}


@bp.route("/projects/new", methods=["GET", "POST"])
@login_required
def new_project():
    config = current_app.config
    if request.method == "POST":
        content_type = request.form.get("content_type", "")
        prompt = request.form.get("prompt", "").strip()

        if content_type not in config["CONTENT_TYPES"]:
            flash("Выберите корректный тип контента.", "danger")
            return redirect(url_for("projects.new_project"))
        if len(prompt) < 3:
            flash("Введите промпт (не менее 3 символов).", "danger")
            return redirect(url_for("projects.new_project"))

        params = _collect_params(content_type, request.form)

        # 1. Модерация промпта
        is_ok, matched = moderation.check_prompt(prompt)
        if not is_ok:
            models.create_generation(
                g.user["id"], content_type, prompt, params, "rejected",
                result_text="Промпт отклонён модерацией. Найдено: " + ", ".join(matched),
            )
            flash("Промпт отклонён модерацией: найдены запрещённые слова — "
                  + ", ".join(matched), "danger")
            return redirect(url_for("projects.new_project"))

        # 2. Проверка баланса
        cost = generator.estimate_tokens(content_type, g.user["tariff"], config)
        if g.user["token_balance"] < cost:
            models.create_generation(
                g.user["id"], content_type, prompt, params, "error",
                result_text="Недостаточно токенов на балансе.",
                tokens_spent=0,
            )
            flash(f"Недостаточно токенов (нужно {cost}, доступно "
                  f"{g.user['token_balance']}). Пополните баланс.", "warning")
            return redirect(url_for("main.cabinet"))

        # 3. Генерация (mock или опциональный API)
        out_path = None
        if content_type in _EXT:
            filename = f"{datetime.now():%Y%m%d_%H%M%S}_{secrets.token_hex(4)}.{_EXT[content_type]}"
            out_path = os.path.join(config["STORAGE_DIR"], str(g.user["id"]), filename)
        result = generator.generate(content_type, prompt, params, out_path, config)

        rel_path = None
        if result["result_path"]:
            rel_path = f"{g.user['id']}/{result['result_path']}"

        # 4. Списание токенов и сохранение
        models.change_balance(
            g.user["id"], -cost, "generation",
            f"Генерация {content_type}: {prompt[:60]}",
        )
        gen_id = models.create_generation(
            g.user["id"], content_type, prompt, params, "success",
            result_text=result["result_text"], result_path=rel_path,
            tokens_spent=cost,
        )
        if result["engine"] == "mock" and content_type in _EXT:
            flash("Генерация выполнена, но внешний сервис был недоступен или "
                  "ограничил частоту запросов — создана резервная заглушка. "
                  "Повторите генерацию через несколько секунд.", "warning")
        else:
            flash(f"Генерация выполнена (движок: {result['engine']}). "
                  f"Списано {cost} токенов.", "success")
        return redirect(url_for("projects.view_generation", gen_id=gen_id))

    return render_template(
        "project_new.html",
        token_cost=config["TOKEN_COST"],
        factors=config["TARIFF_COST_FACTOR"],
    )


@bp.route("/library")
@login_required
def library():
    content_type = request.args.get("type") or None
    date_from = request.args.get("date_from") or None
    date_to = request.args.get("date_to") or None
    gens = models.list_generations(
        user_id=g.user["id"], content_type=content_type,
        date_from=date_from, date_to=date_to, status="success", limit=500,
    )
    return render_template(
        "library.html", generations=gens, content_types=current_app.config["CONTENT_TYPES"],
        filters={"type": content_type or "", "date_from": date_from or "", "date_to": date_to or ""},
    )


@bp.route("/library/<int:gen_id>")
@login_required
def view_generation(gen_id):
    gen = models.get_generation(gen_id)
    if gen is None:
        abort(404)
    if gen["user_id"] != g.user["id"] and g.user["role"] != "admin":
        abort(403)
    return render_template("generation_view.html", gen=gen)


@bp.route("/library/<int:gen_id>/delete", methods=["POST"])
@login_required
def delete_generation(gen_id):
    gen = models.get_generation(gen_id)
    if gen is None:
        abort(404)
    if gen["user_id"] != g.user["id"]:
        abort(403)
    models.delete_generation(gen_id, g.user["id"])
    flash("Запись удалена из библиотеки.", "info")
    return redirect(url_for("projects.library"))


@bp.route("/media/<path:rel_path>")
@login_required
def media(rel_path):
    """Выдача сгенерированных файлов с проверкой прав доступа."""
    owner = rel_path.split("/", 1)[0]
    if owner != str(g.user["id"]) and g.user["role"] != "admin":
        abort(403)
    return send_from_directory(current_app.config["STORAGE_DIR"], rel_path)
