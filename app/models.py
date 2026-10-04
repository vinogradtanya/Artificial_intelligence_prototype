"""Слой доступа к данным (тонкая обёртка над SQL) и бизнес-логика.

Все функции используют соединение из app.db.get_db().
"""
import json
from datetime import datetime

from werkzeug.security import check_password_hash, generate_password_hash

from .db import get_db

ISO = "%Y-%m-%d %H:%M:%S"


def now() -> str:
    return datetime.now().strftime(ISO)


def row_to_dict(row):
    return dict(row) if row is not None else None


# ==========================================================================
# Пользователи
# ==========================================================================


def create_user(username, email, password, role="user", tariff="free", balance=None):
    from flask import current_app

    if balance is None:
        balance = current_app.config["START_BALANCE"]
    db = get_db()
    cur = db.execute(
        "INSERT INTO users (username, email, password_hash, role, tariff,"
        " token_balance, is_blocked, created_at) VALUES (?, ?, ?, ?, ?, ?, 0, ?)",
        (
            username.strip(),
            email.strip().lower(),
            generate_password_hash(password),
            role,
            tariff,
            balance,
            now(),
        ),
    )
    db.commit()
    return cur.lastrowid


def get_user_by_id(user_id):
    return row_to_dict(
        get_db().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    )


def get_user_by_username(username):
    return row_to_dict(
        get_db().execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    )


def get_user_by_email(email):
    return row_to_dict(
        get_db()
        .execute("SELECT * FROM users WHERE email = ?", (email.strip().lower(),))
        .fetchone()
    )


def get_user_by_login(login):
    """Поиск по логину ИЛИ email (для формы входа)."""
    user = get_user_by_username(login)
    if user is None and "@" in (login or ""):
        user = get_user_by_email(login)
    return user


def verify_password(user, password):
    return bool(user) and check_password_hash(user["password_hash"], password)


def set_blocked(user_id, blocked: bool):
    db = get_db()
    db.execute("UPDATE users SET is_blocked = ? WHERE id = ?", (1 if blocked else 0, user_id))
    db.commit()


def set_tariff(user_id, tariff):
    db = get_db()
    db.execute("UPDATE users SET tariff = ? WHERE id = ?", (tariff, user_id))
    db.commit()


def update_profile(user_id, email=None, password=None):
    db = get_db()
    if email:
        db.execute("UPDATE users SET email = ? WHERE id = ?", (email.strip().lower(), user_id))
    if password:
        db.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (generate_password_hash(password), user_id),
        )
    db.commit()


def list_users(limit=200):
    rows = get_db().execute(
        "SELECT * FROM users ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    return [dict(r) for r in rows]


# ==========================================================================
# Баланс и транзакции
# ==========================================================================


def add_transaction(user_id, amount, kind, description=""):
    db = get_db()
    db.execute(
        "INSERT INTO transactions (user_id, amount, kind, description, created_at)"
        " VALUES (?, ?, ?, ?, ?)",
        (user_id, int(amount), kind, description, now()),
    )
    db.commit()


def change_balance(user_id, delta, kind, description=""):
    """Изменяет баланс и пишет транзакцию. Возвращает новый баланс."""
    db = get_db()
    db.execute(
        "UPDATE users SET token_balance = token_balance + ? WHERE id = ?",
        (int(delta), user_id),
    )
    db.execute(
        "INSERT INTO transactions (user_id, amount, kind, description, created_at)"
        " VALUES (?, ?, ?, ?, ?)",
        (user_id, int(delta), kind, description, now()),
    )
    db.commit()
    row = db.execute("SELECT token_balance FROM users WHERE id = ?", (user_id,)).fetchone()
    return row["token_balance"] if row else None


def list_transactions(user_id=None, date_from=None, date_to=None, kind=None, limit=500):
    sql = "SELECT t.*, u.username FROM transactions t JOIN users u ON u.id = t.user_id WHERE 1=1"
    args = []
    if user_id is not None:
        sql += " AND t.user_id = ?"
        args.append(user_id)
    if date_from:
        sql += " AND t.created_at >= ?"
        args.append(date_from + " 00:00:00")
    if date_to:
        sql += " AND t.created_at <= ?"
        args.append(date_to + " 23:59:59")
    if kind:
        sql += " AND t.kind = ?"
        args.append(kind)
    sql += " ORDER BY t.created_at DESC, t.id DESC LIMIT ?"
    args.append(limit)
    return [dict(r) for r in get_db().execute(sql, args).fetchall()]


# ==========================================================================
# Генерации (проекты)
# ==========================================================================


def create_generation(
    user_id, content_type, prompt, params, status,
    result_text=None, result_path=None, tokens_spent=0,
):
    db = get_db()
    cur = db.execute(
        "INSERT INTO generations (user_id, content_type, prompt, params, status,"
        " result_text, result_path, tokens_spent, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            user_id,
            content_type,
            prompt,
            json.dumps(params or {}, ensure_ascii=False),
            status,
            result_text,
            result_path,
            int(tokens_spent),
            now(),
        ),
    )
    db.commit()
    return cur.lastrowid


def get_generation(gen_id):
    return row_to_dict(
        get_db().execute("SELECT * FROM generations WHERE id = ?", (gen_id,)).fetchone()
    )


def delete_generation(gen_id, user_id):
    db = get_db()
    db.execute("DELETE FROM generations WHERE id = ? AND user_id = ?", (gen_id, user_id))
    db.commit()


def list_generations(user_id=None, content_type=None, date_from=None, date_to=None,
                     status=None, limit=500):
    sql = ("SELECT g.*, u.username FROM generations g JOIN users u ON u.id = g.user_id"
           " WHERE 1=1")
    args = []
    if user_id is not None:
        sql += " AND g.user_id = ?"
        args.append(user_id)
    if content_type:
        sql += " AND g.content_type = ?"
        args.append(content_type)
    if status:
        sql += " AND g.status = ?"
        args.append(status)
    if date_from:
        sql += " AND g.created_at >= ?"
        args.append(date_from + " 00:00:00")
    if date_to:
        sql += " AND g.created_at <= ?"
        args.append(date_to + " 23:59:59")
    sql += " ORDER BY g.created_at DESC, g.id DESC LIMIT ?"
    args.append(limit)
    return [dict(r) for r in get_db().execute(sql, args).fetchall()]


# ==========================================================================
# Журнал аудита и статистика администратора
# ==========================================================================


def write_audit(actor_id, action, target=""):
    db = get_db()
    db.execute(
        "INSERT INTO audit_log (actor_id, action, target, created_at) VALUES (?, ?, ?, ?)",
        (actor_id, action, str(target), now()),
    )
    db.commit()


def list_audit(limit=200):
    rows = get_db().execute(
        "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    return [dict(r) for r in rows]


def admin_stats():
    """Собирает сводную статистику для панели администратора."""
    db = get_db()
    stats = {}
    stats["users_total"] = db.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
    stats["users_blocked"] = db.execute(
        "SELECT COUNT(*) c FROM users WHERE is_blocked = 1"
    ).fetchone()["c"]
    stats["users_admins"] = db.execute(
        "SELECT COUNT(*) c FROM users WHERE role = 'admin'"
    ).fetchone()["c"]
    stats["gen_total"] = db.execute("SELECT COUNT(*) c FROM generations").fetchone()["c"]
    stats["gen_success"] = db.execute(
        "SELECT COUNT(*) c FROM generations WHERE status = 'success'"
    ).fetchone()["c"]
    stats["gen_rejected"] = db.execute(
        "SELECT COUNT(*) c FROM generations WHERE status = 'rejected'"
    ).fetchone()["c"]
    stats["tokens_spent"] = (
        db.execute("SELECT COALESCE(SUM(tokens_spent), 0) s FROM generations").fetchone()["s"]
    )
    stats["by_type"] = [
        dict(r)
        for r in db.execute(
            "SELECT content_type, COUNT(*) c, COALESCE(SUM(tokens_spent),0) tokens"
            " FROM generations GROUP BY content_type ORDER BY c DESC"
        ).fetchall()
    ]
    stats["by_tariff"] = [
        dict(r)
        for r in db.execute(
            "SELECT tariff, COUNT(*) c FROM users GROUP BY tariff ORDER BY c DESC"
        ).fetchall()
    ]
    stats["top_users"] = [
        dict(r)
        for r in db.execute(
            "SELECT u.username, COUNT(g.id) c, COALESCE(SUM(g.tokens_spent),0) tokens"
            " FROM users u LEFT JOIN generations g ON g.user_id = u.id"
            " GROUP BY u.id ORDER BY c DESC LIMIT 10"
        ).fetchall()
    ]
    return stats
