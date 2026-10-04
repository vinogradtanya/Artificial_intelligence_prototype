"""Тесты AI-ассистента: справочник (офлайн) и LLM-подсказки (через мок)."""
import json
import re

from app import assistant
from app.config import Config

BASE_CFG = {k: getattr(Config, k) for k in dir(Config) if not k.startswith("_")}


# ==========================================================================
# Помощник-справочник (офлайн)
# ==========================================================================


def test_knowledge_base_well_formed():
    assert len(assistant.KNOWLEDGE_BASE) >= 15
    for entry in assistant.KNOWLEDGE_BASE:
        assert len(entry) == 4, entry


def test_answer_local_tokens_cost():
    res = assistant.answer_local("Сколько стоят генерации?")
    assert res["found"] is True
    assert "токен" in res["answer"].lower()


def test_answer_local_topup():
    res = assistant.answer_local("как пополнить баланс?")
    assert res["found"] is True
    assert res["source"] == "Пополнение баланса"


def test_answer_local_moderation():
    res = assistant.answer_local("почему промпт отклонён модерацией")
    assert res["found"] is True
    assert "отклоняется" in res["answer"].lower()


def test_answer_local_audio():
    res = assistant.answer_local("как озвучивается аудио голосом?")
    assert res["found"] is True
    assert res["source"] == "Аудио и озвучка"


def test_answer_local_export():
    res = assistant.answer_local("как экспортировать отчёт в csv?")
    assert res["found"] is True


def test_answer_local_unknown_question():
    res = assistant.answer_local("расписание поездов до Одессы")
    assert res["found"] is False
    assert res["source"] is None


def test_answer_local_empty():
    assert assistant.answer_local("")["found"] is False


def test_related_topics_returned():
    res = assistant.answer_local("баланс токенов стоимость")
    assert res["found"] is True
    assert isinstance(res["related"], list)


def test_prompt_hints_local_all_types():
    for content_type in ("text", "image", "audio"):
        improved, hints = assistant.prompt_hints_local("кот", content_type)
        assert improved.startswith("кот")
        assert len(hints) >= 3


def test_improved_prompt_and_hints_are_russian():
    """Офлайн-подсказки не должны содержать латиницу (требование рус. языка)."""
    for content_type in ("text", "image", "audio"):
        improved, hints = assistant.prompt_hints_local("рыжий кот", content_type)
        suffix = improved.replace("рыжий кот", "")
        assert not re.search(r"[A-Za-z]", suffix), improved
        assert not any(re.search(r"[A-Za-z]", h) for h in hints)


# ==========================================================================
# Реальный LLM (мок сетевого слоя)
# ==========================================================================


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self._payload).encode("utf-8")


def _patch_llm(monkeypatch, content):
    monkeypatch.setattr(
        assistant.urllib.request, "urlopen",
        lambda req, timeout=45: _FakeResponse(
            {"choices": [{"message": {"content": content}}]}))


def test_llm_chat_without_key_returns_none():
    cfg = dict(BASE_CFG, ASSISTANT_API_KEY="")
    assert assistant.llm_chat([{"role": "user", "content": "hi"}], cfg) is None


def test_llm_chat_success(monkeypatch):
    _patch_llm(monkeypatch, "  привет  ")
    cfg = dict(BASE_CFG, ASSISTANT_API_KEY="test-key")
    assert assistant.llm_chat([{"role": "user", "content": "hi"}], cfg) == "привет"


def test_llm_chat_error_returns_none(monkeypatch):
    def boom(*args, **kwargs):
        raise OSError("сеть недоступна")

    monkeypatch.setattr(assistant.urllib.request, "urlopen", boom)
    cfg = dict(BASE_CFG, ASSISTANT_API_KEY="test-key")
    assert assistant.llm_chat([{"role": "user", "content": "hi"}], cfg) is None


def test_improve_prompt_uses_local_without_key():
    cfg = dict(BASE_CFG, ASSISTANT_API_KEY="")
    res = assistant.improve_prompt("кот на окне", "image", cfg)
    assert res["engine"] == "local"
    assert res["llm_text"] is None
    assert "высокая детализация" in res["improved"]


def test_improve_prompt_uses_llm_with_key(monkeypatch):
    _patch_llm(monkeypatch, "Улучшенный промпт: кот на окне, 4k")
    cfg = dict(BASE_CFG, ASSISTANT_API_KEY="test-key")
    res = assistant.improve_prompt("кот", "image", cfg)
    assert res["engine"] == "llm"
    assert res["llm_text"].startswith("Улучшенный промпт")


def test_ask_prefers_llm_when_key_present(monkeypatch):
    _patch_llm(monkeypatch, "Ответ от LLM")
    cfg = dict(BASE_CFG, ASSISTANT_API_KEY="test-key")
    res = assistant.ask("как пополнить баланс", cfg)
    assert res["engine"] == "llm"
    assert res["answer"] == "Ответ от LLM"


def test_ask_falls_back_to_local_on_llm_error(monkeypatch):
    def boom(*args, **kwargs):
        raise OSError("сеть недоступна")

    monkeypatch.setattr(assistant.urllib.request, "urlopen", boom)
    cfg = dict(BASE_CFG, ASSISTANT_API_KEY="test-key")
    res = assistant.ask("как пополнить баланс", cfg)
    assert res["engine"] == "local"
    assert res["found"] is True


# ==========================================================================
# Маршруты
# ==========================================================================


def test_assistant_requires_login(client):
    assert client.get("/assistant").status_code == 302


def test_assistant_page_renders(user_client):
    resp = user_client.get("/assistant")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "AI-ассистент" in html
    assert "Популярные вопросы" in html


def test_assistant_ask_route(user_client):
    resp = user_client.post("/assistant/ask", data={"question": "как пополнить баланс?"})
    assert resp.status_code == 200
    assert "Пополнение баланса" in resp.get_data(as_text=True)


def test_assistant_ask_empty_question(user_client):
    assert user_client.post("/assistant/ask", data={"question": ""}).status_code == 400


def test_assistant_improve_route(user_client):
    resp = user_client.post("/assistant/improve",
                            data={"prompt": "кот на окне", "content_type": "image"})
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "Улучшенный промпт" in html
    assert "высокая детализация" in html


def test_assistant_api_json(user_client):
    resp = user_client.get("/assistant/api/ask",
                           query_string={"q": "как пополнить баланс"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["found"] is True
    assert data["engine"] == "local"
    assert "related" not in data


def test_assistant_quick_question_link(user_client):
    resp = user_client.get("/assistant", query_string={"q": "что умеет ассистент?"})
    assert resp.status_code == 200
    assert "Ответ" in resp.get_data(as_text=True)
