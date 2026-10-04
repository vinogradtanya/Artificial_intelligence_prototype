"""Тесты отчётов и экспорта (CSV / JSON)."""
import csv
import io
import json


def _make_generation(client):
    return client.post(
        "/projects/new",
        data={"content_type": "text", "prompt": "стих про зиму", "length": "0"},
    )


def test_export_generations_csv(user_client):
    _make_generation(user_client)
    resp = user_client.get("/export/generations.csv")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["Content-Type"]
    assert "attachment" in resp.headers["Content-Disposition"]
    text = resp.get_data(as_text=True).lstrip("\ufeff")
    rows = list(csv.DictReader(io.StringIO(text)))
    assert len(rows) == 1
    assert rows[0]["content_type"] == "text"
    assert rows[0]["status"] == "success"


def test_export_generations_json(user_client):
    _make_generation(user_client)
    resp = user_client.get("/export/generations.json")
    assert resp.status_code == 200
    assert "application/json" in resp.headers["Content-Type"]
    data = json.loads(resp.get_data(as_text=True))
    assert isinstance(data, list) and len(data) == 1
    assert data[0]["prompt"] == "стих про зиму"


def test_export_transactions_csv(user_client):
    user_client.post("/cabinet/topup", data={"amount": "100"})
    resp = user_client.get("/export/transactions.csv")
    assert resp.status_code == 200
    text = resp.get_data(as_text=True).lstrip("\ufeff")
    rows = list(csv.DictReader(io.StringIO(text)))
    assert any(int(r["amount"]) == 100 for r in rows)


def test_export_transactions_json(user_client):
    user_client.post("/cabinet/topup", data={"amount": "250"})
    resp = user_client.get("/export/transactions.json")
    data = json.loads(resp.get_data(as_text=True))
    assert any(t["amount"] == 250 for t in data)


def test_history_filters_by_type(user_client):
    _make_generation(user_client)
    resp = user_client.get("/history?type=image")
    assert resp.status_code == 200
    assert "Записей не найдено" in resp.get_data(as_text=True)
    resp = user_client.get("/history?type=text")
    assert "стих про зиму" in resp.get_data(as_text=True)
