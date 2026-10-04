"""Точка входа учебного прототипа «AI Content Studio».

Запуск dev-сервера:
    python run.py

Дополнительные команды Flask CLI:
    flask --app run init-db     # создать схему БД
    flask --app run seed        # создать администратора
"""
import os

from app import create_app, db
from seed import ensure_admin

app = create_app()


@app.cli.command("init-db")
def init_db_command():
    """Создаёт таблицы БД (идемпотентно)."""
    db.init_db()
    print("База данных инициализирована.")


@app.cli.command("seed")
def seed_command():
    """Создаёт администратора по умолчанию."""
    ensure_admin(app)
    print("Готово.")


if __name__ == "__main__":
    ensure_admin(app)  # гарантируем наличие администратора при первом запуске
    app.run(
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "5000")),
        debug=os.environ.get("FLASK_DEBUG", "1") == "1",
    )
