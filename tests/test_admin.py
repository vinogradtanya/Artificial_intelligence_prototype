"""Тесты роли администратора: статистика и блокировка пользователей."""
from tests.conftest import make_user


def test_non_admin_gets_403(app, client):
    make_user(app, "plain", role="user")
    client.post("/login", data={"login": "plain", "password": "secret1"})
    assert client.get("/admin/").status_code == 403


def test_admin_sees_stats(app, client):
    make_user(app, "root", role="admin")
    make_user(app, "u1", role="user")
    client.post("/login", data={"login": "root", "password": "secret1"})
    resp = client.get("/admin/")
    assert resp.status_code == 200
    assert "Панель администратора" in resp.get_data(as_text=True)


def test_admin_blocks_user(app, client):
    make_user(app, "root", role="admin")
    victim_id = make_user(app, "victim", role="user")
    client.post("/login", data={"login": "root", "password": "secret1"})
    resp = client.post(f"/admin/users/{victim_id}/block")
    assert resp.status_code == 302

    from app import models

    with app.app_context():
        assert models.get_user_by_id(victim_id)["is_blocked"] == 1


def test_admin_cannot_block_self(app, client):
    admin_id = make_user(app, "root", role="admin")
    client.post("/login", data={"login": "root", "password": "secret1"})
    client.post(f"/admin/users/{admin_id}/block")

    from app import models

    with app.app_context():
        assert models.get_user_by_id(admin_id)["is_blocked"] == 0


def test_admin_unblock_user(app, client):
    make_user(app, "root", role="admin")
    uid = make_user(app, "victim", role="user")
    from app import models

    with app.app_context():
        models.set_blocked(uid, True)
    client.post("/login", data={"login": "root", "password": "secret1"})
    client.post(f"/admin/users/{uid}/unblock")
    with app.app_context():
        assert models.get_user_by_id(uid)["is_blocked"] == 0


def test_audit_log_written(app, client):
    make_user(app, "root", role="admin")
    uid = make_user(app, "victim", role="user")
    client.post("/login", data={"login": "root", "password": "secret1"})
    client.post(f"/admin/users/{uid}/block")

    from app import models

    with app.app_context():
        entries = models.list_audit()
    assert any(e["action"] == "block_user" for e in entries)
