"""Тесты реальных движков: изображение (Pollinations) и TTS.

Сеть и системный TTS не вызываются: сетевой слой подменяется через monkeypatch,
поэтому тесты детерминированы и работают офлайн.
"""
import io
import os

import pytest
from PIL import Image

from app import generator
from app.config import Config

BASE_CFG = {k: getattr(Config, k) for k in dir(Config) if not k.startswith("_")}


def _png_bytes(size=(128, 128)):
    """Возвращает «шумный» PNG, заведомо превышающий порог отбраковки (1024 Б)."""
    raw = os.urandom(size[0] * size[1] * 3)
    img = Image.frombytes("RGB", size, raw)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


# --------------------------------------------------------------------------
# Изображения
# --------------------------------------------------------------------------


def test_build_image_url_encodes_prompt():
    url = generator.build_image_url("кот на окне", {"size": "512x512"}, BASE_CFG)
    assert url.startswith("https://image.pollinations.ai/prompt/")
    assert "%20" in url          # пробелы закодированы
    assert "width=512" in url and "height=512" in url
    assert "model=" in url


def test_image_real_success(tmp_path, monkeypatch):
    cfg = dict(BASE_CFG, USE_REAL_IMAGE=True, IMAGE_RETRIES=1, IMAGE_RETRY_DELAY=0)
    monkeypatch.setattr(generator, "fetch_bytes",
                        lambda url, timeout, headers=None: _png_bytes())
    out = str(tmp_path / "real.png")
    res = generator.generate("image", "кот", {"size": "256x256"}, out, cfg)
    assert res["engine"] == "pollinations"
    assert os.path.getsize(out) >= 1024


def test_image_real_retries_then_succeeds(tmp_path, monkeypatch):
    cfg = dict(BASE_CFG, USE_REAL_IMAGE=True, IMAGE_RETRIES=3, IMAGE_RETRY_DELAY=0)
    calls = {"n": 0}

    def flaky(url, timeout, headers=None):
        calls["n"] += 1
        if calls["n"] < 3:
            raise OSError("временный сбой сервиса")
        return _png_bytes()

    monkeypatch.setattr(generator, "fetch_bytes", flaky)
    out = str(tmp_path / "retry.png")
    res = generator.generate("image", "море", {"size": "256x256"}, out, cfg)
    assert res["engine"] == "pollinations"
    assert calls["n"] == 3


def test_image_real_falls_back_to_mock(tmp_path, monkeypatch):
    cfg = dict(BASE_CFG, USE_REAL_IMAGE=True, IMAGE_RETRIES=2, IMAGE_RETRY_DELAY=0)

    def boom(url, timeout, headers=None):
        raise OSError("нет сети")

    monkeypatch.setattr(generator, "fetch_bytes", boom)
    out = str(tmp_path / "fallback.png")
    res = generator.generate("image", "город", {"size": "256x256"}, out, cfg)
    assert res["engine"] == "mock"
    assert os.path.exists(out)
    with open(out, "rb") as fh:
        assert fh.read(8) == b"\x89PNG\r\n\x1a\n"


def test_image_real_rejects_tiny_response(tmp_path, monkeypatch):
    cfg = dict(BASE_CFG, USE_REAL_IMAGE=True, IMAGE_RETRIES=1, IMAGE_RETRY_DELAY=0)
    monkeypatch.setattr(generator, "fetch_bytes",
                        lambda url, timeout, headers=None: b"")
    out = str(tmp_path / "tiny.png")
    res = generator.generate("image", "дом", {"size": "256x256"}, out, cfg)
    assert res["engine"] == "mock"  # пустой ответ → откат


# --------------------------------------------------------------------------
# Аудио (TTS)
# --------------------------------------------------------------------------


def test_audio_real_falls_back_when_powershell_fails(tmp_path, monkeypatch):
    cfg = dict(BASE_CFG, USE_REAL_AUDIO=True)

    def boom(*args, **kwargs):
        raise OSError("powershell недоступен")

    monkeypatch.setattr(generator.subprocess, "run", boom)
    out = str(tmp_path / "a.wav")
    res = generator.generate("audio", "тестовая фраза", {}, out, cfg)
    assert res["engine"] == "mock"
    assert os.path.exists(out)


def test_audio_real_returns_none_for_empty_text(tmp_path):
    res = generator.generate_audio_real("   ", {}, str(tmp_path / "x.wav"), dict(BASE_CFG))
    assert res is None


@pytest.mark.skipif(os.name != "nt", reason="TTS доступен только в Windows")
def test_audio_real_live(tmp_path):
    """Реальная озвучка (запускается только если явно задан RUN_LIVE_TTS=1)."""
    if os.environ.get("RUN_LIVE_TTS") != "1":
        pytest.skip("живой TTS-тест отключён (RUN_LIVE_TTS!=1)")
    out = str(tmp_path / "live.wav")
    res = generator.generate_audio_real(
        "Проверка синтеза речи.", {}, out, dict(BASE_CFG))
    assert res and os.path.getsize(out) > 1024
