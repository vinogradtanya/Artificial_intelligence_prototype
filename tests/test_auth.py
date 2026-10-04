"""Тесты регистрации, входа и блокировки."""
from tests.conftest import login, make_user, register


def test_register_success(client, app):
    resp = register(client)
    assert resp.status_code == 302  # редирект на страницу входа
    from app import models

    with app.app_context():
        user = models.get_user_by_username("tester")
    assert user is not None
    assert user["token_balance"] == 100  # стартовый баланс
    assert user["password_hash"] != "secret1"  # пароль хранится в виде хеша


def test_register_duplicate_username(client):
    register(client)
    resp = register(client, email="other@example.com")
    assert resp.status_code == 400


def test_register_short_password(client):
    resp = register(client, username="shorty", email="s@example.com", password="123")
    assert resp.status_code == 400


def test_login_success(client, app):
    register(client)
    resp = login(client)
    assert resp.status_code == 302
    # доступ к защищённой странице
    assert client.get("/").status_code == 200


def test_login_wrong_password(client):
    register(client)
    resp = login(client, password="wrong")
    assert resp.status_code == 401


def test_login_by_email(client):
    register(client)
    resp = login(client, login_value="tester@example.com")
    assert resp.status_code == 302


def test_logout(client):
    register(client)
    login(client)
    assert client.get("/logout").status_code == 302
    assert client.get("/").status_code == 302  # снова требуется вход


def test_blocked_user_cannot_login(app, client):
    make_user(app, "blocked", password="secret1")
    from app import models

    with app.app_context():
        uid = models.get_user_by_username("blocked")["id"]
        models.set_blocked(uid, True)
    resp = login(client)  # логин по умолчанию "tester" не подойдёт
    resp = login(client, login_value="blocked")
    assert resp.status_code == 403


def test_protected_page_requires_login(client):
    resp = client.get("/cabinet")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]
