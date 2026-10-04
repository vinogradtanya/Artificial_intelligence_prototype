"""Дымовые тесты: рендеринг всех страниц приложения без ошибок шаблонов."""
from tests.conftest import make_user


def test_user_pages_render(user_client):
    for path in ["/", "/cabinet", "/projects/new", "/library", "/history", "/transactions"]:
        resp = user_client.get(path)
        assert resp.status_code == 200, f"{path} -> {resp.status_code}"


def test_register_and_login_pages_render(client):
    assert client.get("/register").status_code == 200
    assert client.get("/login").status_code == 200


def test_image_result_page_renders(user_client):
    user_client.post("/projects/new",
                     data={"content_type": "image", "prompt": "лес утром", "size": "256x256"})
    resp = user_client.get("/library")
    assert resp.status_code == 200
    resp = user_client.get("/library/1")
    assert resp.status_code == 200
    assert "<img" in resp.get_data(as_text=True)


def test_audio_result_page_renders(user_client):
    user_client.post("/projects/new",
                     data={"content_type": "audio", "prompt": "мелодия", "duration": "1"})
    resp = user_client.get("/library/1")
    assert resp.status_code == 200
    assert "<audio" in resp.get_data(as_text=True)


def test_media_served_to_owner(user_client, app):
    user_client.post("/projects/new",
                     data={"content_type": "image", "prompt": "море", "size": "256x256"})
    from app import models

    with app.app_context():
        uid = models.get_user_by_username("tester")["id"]
        gen = models.list_generations(user_id=uid)[0]
    resp = user_client.get(f"/media/{gen['result_path']}")
    assert resp.status_code == 200
    assert resp.data[:8] == b"\x89PNG\r\n\x1a\n"  # корректная PNG-подпись


def test_admin_pages_render(app, client):
    make_user(app, "root", role="admin")
    client.post("/login", data={"login": "root", "password": "secret1"})
    for path in ["/admin/", "/admin/users", "/admin/audit"]:
        resp = client.get(path)
        assert resp.status_code == 200, f"{path} -> {resp.status_code}"
