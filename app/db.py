"""Работа с соединением БД (SQLite через стандартную библиотеку)."""
import sqlite3

from flask import current_app, g


def get_db():
    """Возвращает соединение с БД, создавая его при первом обращении."""
    if "db" not in g:
        g.db = sqlite3.connect(
            current_app.config["DATABASE"],
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(exc=None):
    """Закрывает соединение по завершении контекста приложения."""
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Создаёт схему БД (идемпотентно — CREATE TABLE IF NOT EXISTS)."""
    db = get_db()
    with open(current_app.config["SCHEMA_FILE"], encoding="utf-8") as f:
        db.executescript(f.read())
    db.commit()


def init_app(app):
    """Регистрирует обработчик закрытия соединения."""
    app.teardown_appcontext(close_db)
