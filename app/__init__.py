"""Фабрика Flask-приложения учебного прототипа."""
import os

from flask import Flask

from . import db
from .config import Config


def create_app(config_object=Config):
    """Создаёт и настраивает приложение.

    :param config_object: класс/строка конфигурации (Config или TestConfig).
    """
    app = Flask(__name__)
    app.config.from_object(config_object)

    # Каталоги для БД и медиафайлов
    db_path = app.config.get("DATABASE")
    if db_path and db_path != ":memory:":
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
    os.makedirs(app.config["STORAGE_DIR"], exist_ok=True)

    db.init_app(app)

    from . import security
    security.init_app(app)

    from . import admin, assistant, auth, main, projects, reports

    app.register_blueprint(auth.bp)
    app.register_blueprint(main.bp)
    app.register_blueprint(projects.bp)
    app.register_blueprint(reports.bp)
    app.register_blueprint(admin.bp)
    app.register_blueprint(assistant.bp)

    # Создание схемы БД (идемпотентно)
    with app.app_context():
        db.init_db()

    return app
