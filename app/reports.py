"""Отчёты: история генераций, история транзакций и экспорт в CSV/JSON."""
import csv
import io
import json

from flask import Blueprint, Response, current_app, g, render_template, request

from . import models
from .security import login_required

bp = Blueprint("reports", __name__)


def _filters():
    return {
        "date_from": request.args.get("date_from") or None,
        "date_to": request.args.get("date_to") or None,
        "type": request.args.get("type") or None,
    }


@bp.route("/history")
@login_required
def history():
    f = _filters()
    scope_all = request.args.get("scope") == "all" and g.user["role"] == "admin"
    gens = models.list_generations(
        user_id=None if scope_all else g.user["id"],
        content_type=f["type"], date_from=f["date_from"], date_to=f["date_to"], limit=1000,
    )
    return render_template(
        "history.html", generations=gens, content_types=current_app.config["CONTENT_TYPES"],
        filters={"type": f["type"] or "", "date_from": f["date_from"] or "",
                 "date_to": f["date_to"] or "", "scope": "all" if scope_all else ""},
    )


@bp.route("/transactions")
@login_required
def transactions():
    f = _filters()
    scope_all = request.args.get("scope") == "all" and g.user["role"] == "admin"
    txs = models.list_transactions(
        user_id=None if scope_all else g.user["id"],
        date_from=f["date_from"], date_to=f["date_to"], limit=1000,
    )
    return render_template(
        "transactions.html", transactions=txs,
        filters={"date_from": f["date_from"] or "", "date_to": f["date_to"] or "",
                 "scope": "all" if scope_all else ""},
    )


# ==========================================================================
# Экспорт (CSV / JSON)
# ==========================================================================


def _csv_response(rows, filename, columns):
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    # BOM для корректного открытия в Excel
    data = "\ufeff" + buf.getvalue()
    return Response(
        data, mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


def _json_response(rows, filename):
    data = json.dumps(rows, ensure_ascii=False, indent=2, default=str)
    return Response(
        data, mimetype="application/json",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@bp.route("/export/generations.<fmt>")
@login_required
def export_generations(fmt):
    f = _filters()
    scope_all = request.args.get("scope") == "all" and g.user["role"] == "admin"
    gens = models.list_generations(
        user_id=None if scope_all else g.user["id"],
        content_type=f["type"], date_from=f["date_from"], date_to=f["date_to"], limit=5000,
    )
    if fmt == "json":
        return _json_response(gens, "generations.json")
    columns = ["id", "username", "content_type", "prompt", "status",
               "tokens_spent", "created_at"]
    return _csv_response(gens, "generations.csv", columns)


@bp.route("/export/transactions.<fmt>")
@login_required
def export_transactions(fmt):
    f = _filters()
    scope_all = request.args.get("scope") == "all" and g.user["role"] == "admin"
    txs = models.list_transactions(
        user_id=None if scope_all else g.user["id"],
        date_from=f["date_from"], date_to=f["date_to"], limit=5000,
    )
    if fmt == "json":
        return _json_response(txs, "transactions.json")
    columns = ["id", "username", "amount", "kind", "description", "created_at"]
    return _csv_response(txs, "transactions.csv", columns)
