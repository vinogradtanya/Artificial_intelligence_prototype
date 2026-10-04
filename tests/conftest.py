"""Общие фикстуры автотестов."""
import os
import tempfile

import pytest

from app import create_app
from app.config import TestConfig


@pytest.fixture
def app():
    """Приложение с изолированной БД и хранилищем во временном каталоге."""
    tmp = tempfile.mkdtemp(prefix="aics_test_")

    class Cfg(TestConfig):
        DATABASE = os.path.join(tmp, "test.db")
        STORAGE_DIR = os.path.join(tmp, "media")
        SECRET_KEY = "test-secret"
        START_BALANCE = 100

    application = create_app(Cfg)
    yield application


@pytest.fixture
def client(app):
    return app.test_client()


# --------------------------------------------------------------------------
# Вспомогательные функции
# --------------------------------------------------------------------------


def register(client, username="tester", email="tester@example.com", password="secret1"):
    return client.post(
        "/register",
        data={"username": username, "email": email,
              "password": password, "password2": password},
        follow_redirects=False,
    )


def login(client, login_value="tester", password="secret1"):
    return client.post(
        "/login",
        data={"login": login_value, "password": password},
        follow_redirects=False,
    )


@pytest.fixture
def user_client(client):
    """Клиент с зарегистрированным и вошедшим пользователем."""
    register(client)
    login(client)
    return client


def make_user(app, username, email=None, password="secret1",
              role="user", tariff="free", balance=100):
    """Создаёт пользователя напрямую в БД и возвращает его id."""
    from app import models

    with app.app_context():
        uid = models.create_user(username, email or f"{username}@example.com",
                                 password, role=role, tariff=tariff, balance=0)
        if balance:
            models.change_balance(uid, balance, "topup", "тестовое пополнение")
        return uid
