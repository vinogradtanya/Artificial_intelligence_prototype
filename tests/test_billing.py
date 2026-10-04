"""Тесты имитации баланса токенов: пополнение, бонусы, тарифы."""
from tests.conftest import register


def _user(app, username="tester"):
    from app import models

    with app.app_context():
        return models.get_user_by_username(username)


def test_topup_increases_balance(user_client, app):
    before = _user(app)["token_balance"]
    resp = user_client.post("/cabinet/topup", data={"amount": "500"})
    assert resp.status_code == 302
    assert _user(app)["token_balance"] == before + 500


def test_topup_creates_transaction(user_client, app):
    from app import models

    user_client.post("/cabinet/topup", data={"amount": "300"})
    with app.app_context():
        uid = _user(app)["id"]
        txs = models.list_transactions(user_id=uid, kind="topup")
    assert any(t["amount"] == 300 for t in txs)


def test_topup_bonus_for_tariff(app, client):
    register(client)
    client.post("/login", data={"login": "tester", "password": "secret1"})
    client.post("/cabinet/tariff", data={"tariff": "business"})  # бонус 10%
    before = _user(app)["token_balance"]
    client.post("/cabinet/topup", data={"amount": "1000"})
    # 1000 + 10% = 1100
    assert _user(app)["token_balance"] == before + 1100


def test_topup_rejects_invalid_amount(user_client, app):
    before = _user(app)["token_balance"]
    user_client.post("/cabinet/topup", data={"amount": "-5"})
    assert _user(app)["token_balance"] == before


def test_tariff_reduces_generation_cost(app, client):
    register(client)
    client.post("/login", data={"login": "tester", "password": "secret1"})
    client.post("/cabinet/tariff", data={"tariff": "business"})
    before = _user(app)["token_balance"]
    client.post("/projects/new",
                data={"content_type": "image", "prompt": "город", "size": "512x512"})
    # image: 50 * 0.5 = 25
    assert _user(app)["token_balance"] == before - 25


def test_tariff_change_rejects_unknown(user_client, app):
    user_client.post("/cabinet/tariff", data={"tariff": "gold"})
    assert _user(app)["tariff"] == "free"


def test_profile_update_email(user_client, app):
    user_client.post("/cabinet/profile",
                     data={"email": "new@example.com", "password": "", "password2": ""})
    assert _user(app)["email"] == "new@example.com"
