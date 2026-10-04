"""Тесты Mock-генератора и расчёта стоимости."""
import os
import wave

from app import generator
from app.config import Config

CFG = {k: getattr(Config, k) for k in dir(Config) if not k.startswith("_")}


def test_text_generation_deterministic():
    a = generator.generate_text("стих про осень", {})
    b = generator.generate_text("стих про осень", {})
    assert a == b
    assert "осень" in a.lower()


def test_text_keyword_template_used():
    text = generator.generate_text("слоган для бренда кофе", {})
    assert "слоган" in text.lower() or "«" in text


def test_image_generation_creates_png(tmp_path):
    out = os.path.join(tmp_path, "img.png")
    path = generator.generate_image("закат над морем", {"size": "256x256"}, out)
    assert os.path.exists(path)
    with open(path, "rb") as fh:
        assert fh.read(8) == b"\x89PNG\r\n\x1a\n"


def test_audio_generation_creates_wav(tmp_path):
    out = os.path.join(tmp_path, "snd.wav")
    path = generator.generate_audio("спокойная мелодия", {"duration": 1}, out)
    assert os.path.exists(path)
    with wave.open(path, "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getframerate() == 16000
        assert wf.getnframes() > 0


def test_generate_dispatcher_text(tmp_path):
    res = generator.generate("text", "обычный запрос", {}, None, CFG)
    assert res["result_text"] and res["engine"] == "mock"
    assert res["result_path"] is None


def test_estimate_tokens_by_tariff():
    assert generator.estimate_tokens("text", "free", CFG) == 10
    assert generator.estimate_tokens("image", "free", CFG) == 50
    assert generator.estimate_tokens("audio", "free", CFG) == 30
    # business: коэффициент 0.5
    assert generator.estimate_tokens("image", "business", CFG) == 25
