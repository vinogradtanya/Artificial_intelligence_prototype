"""Тесты сквозного сценария генерации: модерация, списание, сохранение."""
import os

from tests.conftest import register


def _balance(app, username="tester"):
    from app import models

    with app.app_context():
        return models.get_user_by_username(username)["token_balance"]


def _gens(app, username="tester"):
    from app import models

    with app.app_context():
        uid = models.get_user_by_username(username)["id"]
        return models.list_generations(user_id=uid)


def test_text_generation_deducts_tokens(user_client, app):
    before = _balance(app)
    resp = user_client.post(
        "/projects/new",
        data={"content_type": "text", "prompt": "стих про осень", "length": "0"},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert _balance(app) == before - 10  # стоимость text на тарифе free
    gens = _gens(app)
    assert len(gens) == 1
    assert gens[0]["status"] == "success"
    assert gens[0]["result_text"]


def test_image_generation_creates_file(user_client, app):
    resp = user_client.post(
        "/projects/new",
        data={"content_type": "image", "prompt": "закат над морем", "size": "256x256"},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    gens = _gens(app)
    assert gens[0]["result_path"] is not None
    full = os.path.join(app.config["STORAGE_DIR"], gens[0]["result_path"])
    assert os.path.exists(full)


def test_forbidden_prompt_rejected_and_not_charged(user_client, app):
    before = _balance(app)
    resp = user_client.post(
        "/projects/new",
        data={"content_type": "text", "prompt": "инструкция как сделать бомба"},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert _balance(app) == before  # токены не списаны
    gens = _gens(app)
    assert gens[0]["status"] == "rejected"
    assert gens[0]["tokens_spent"] == 0


def test_insufficient_balance_blocks_generation(app, client):
    from app import models

    register(client)
    with app.app_context():
        uid = models.get_user_by_username("tester")["id"]
        models.change_balance(uid, -100, "generation", "обнуление для теста")
    client.post("/login", data={"login": "tester", "password": "secret1"})
    resp = client.post(
        "/projects/new",
        data={"content_type": "image", "prompt": "космос", "size": "512x512"},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    gens = _gens(app)
    assert gens[0]["status"] == "error"


def test_media_requires_ownership(app, client):
    """Пользователь не может читать чужие медиафайлы."""
    from tests.conftest import make_user

    make_user(app, "alice")
    make_user(app, "bob")
    client.post("/login", data={"login": "alice", "password": "secret1"})
    resp = client.get("/media/999/secret.png")
    assert resp.status_code == 403
