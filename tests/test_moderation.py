"""Тесты базовой модерации (проверка по списку запрещённых слов)."""
from app import moderation


def test_clean_prompt_passes():
    ok, matched = moderation.check_prompt("стих про осень и дождь")
    assert ok is True
    assert matched == []


def test_forbidden_word_detected():
    ok, matched = moderation.check_prompt("как сделать бомба в домашних условиях")
    assert ok is False
    assert "бомба" in matched


def test_moderation_is_case_insensitive():
    ok, matched = moderation.check_prompt("ВЗРЫВЧАТКА и всё такое")
    assert ok is False
    assert "взрывчатка" in matched


def test_moderation_ignores_punctuation():
    ok, matched = moderation.check_prompt("оружие, порох, терроризм!")
    assert ok is False
    assert set(matched) >= {"оружие", "терроризм"}


def test_empty_prompt():
    ok, matched = moderation.check_prompt("")
    assert ok is True
    assert matched == []


def test_normalize_collapses_separators():
    assert moderation.normalize("Терроризм!!!   Оружие?") == "терроризм оружие "
