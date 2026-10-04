"""Генерация контента.

Движки выбираются конфигурацией, у каждого есть автоматический откат к mock:

* **Изображение** — реальная AI-генерация через бесплатный сервис
  Pollinations.AI (`USE_REAL_IMAGE=1`, по умолчанию вкл.). При отсутствии сети
  или ошибке сервиса формируется детерминированная PNG-заглушка (градиент + текст).
* **Аудио** — реальная озвучка текста промпта (Windows SAPI5 `System.Speech`,
  по умолчанию вкл.). При неудаче формируется мелодия-заглушка (WAV).
* **Текст** — mock по ключевым словам; при `USE_REAL_API=1` и наличии
  `HF_API_TOKEN` используется бесплатный Hugging Face Inference API.

Mock-режим детерминирован (результат зависит от SHA-256 хеша промпта), что удобно
для тестов и демонстраций.
"""
import hashlib
import io
import json
import math
import os
import random
import struct
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import wave

from PIL import Image, ImageDraw, ImageFont


def _seed(prompt: str, params: dict | None = None) -> int:
    payload = (prompt or "") + json.dumps(params or {}, sort_keys=True, ensure_ascii=False)
    return int(hashlib.sha256(payload.encode("utf-8")).hexdigest(), 16)


def _rng(prompt: str, params=None) -> random.Random:
    return random.Random(_seed(prompt, params))


# --------------------------------------------------------------------------
# Mock-генерация текста (шаблоны по ключевым словам)
# --------------------------------------------------------------------------

_TEXT_TEMPLATES = [
    (
        ("стих", "поэм", "poem", "рифм"),
        "«{t}»\n\nВ тишине рождается строка,\n"
        "За словом слово — как река.\n"
        "Ты тему дал, и вот ответ:\n"
        "{t} — вплетён в рассветный свет.",
    ),
    (
        ("сказк", "истори", "story", "рассказ"),
        "Сказка о «{t}»\n\n"
        "Жил-был в далёком краю герой, что мечтал о {t}.\n"
        "Шёл он через леса и реки, встречал добрых и злых.\n"
        "Но упорство его вело вперёд, и {t} стало явью.\n"
        "Мораль: путь осилит идущий.",
    ),
    (
        ("поздрав", "greeting", "открытк"),
        "Поздравление\n\n"
        "Дорогой друг! От всей души поздравляю тебя!\n"
        "Пусть «{t}» приносит радость каждый день,\n"
        "пусть удача сопутствует во всех начинаниях.\n"
        "Счастья, здоровья и вдохновения!",
    ),
    (
        ("слоган", "slogan", "реклам", "бренд"),
        "Идеи слоганов для «{t}»:\n"
        "1. «{t}» — просто, быстро, надёжно.\n"
        "2. Всё начинается с «{t}».\n"
        "3. «{t}»: твой надёжный выбор.\n"
        "4. Меняй мир вместе с «{t}».",
    ),
    (
        ("код", "code", "функци", "python", "программ"),
        "# Пример кода по запросу: {t}\n"
        "def solution(data):\n"
        '    """Черновик решения задачи: {t}."""\n'
        "    result = []\n"
        "    for item in data:\n"
        "        result.append(item)\n"
        "    return result",
    ),
]


def generate_text(prompt: str, params: dict | None = None) -> str:
    """Возвращает заранее подготовленный текст по ключевым словам промпта."""
    params = params or {}
    low = (prompt or "").lower()
    topic = (prompt or "").strip() or "без темы"

    body = None
    for keywords, template in _TEXT_TEMPLATES:
        if any(k in low for k in keywords):
            body = template.format(t=topic)
            break

    if body is None:
        rng = _rng(prompt, params)
        openers = [
            "Вот сгенерированный текст по вашему запросу.",
            "Ниже — результат генерации на основе промпта.",
            "Сформирован следующий текст:",
        ]
        body = (
            f"{rng.choice(openers)}\n\n"
            f"Тема: «{topic}».\n"
            "Данный фрагмент создан Mock-генератором учебного прототипа. "
            "В продуктивной версии здесь был бы ответ языковой модели.\n"
        )

    length = int(params.get("length", 0) or 0)
    if length > 0:
        body = body + "\n\n" + " ".join(
            ["Дополнительный абзац для набора длины."] * max(1, length // 20)
        )
    return body


# --------------------------------------------------------------------------
# Mock-генерация изображения (Pillow)
# --------------------------------------------------------------------------


def _load_font(size: int):
    try:
        return ImageFont.truetype("arial.ttf", size)
    except Exception:
        try:
            return ImageFont.load_default(size)
        except Exception:
            return ImageFont.load_default()


def generate_image(prompt: str, params: dict | None = None, out_path: str | None = None) -> str:
    """Рисует PNG-заглушку с градиентом и текстом промпта.

    Размер и палитра детерминированно зависят от промпта.
    """
    params = params or {}
    size_param = str(params.get("size", "512x512")).lower().split("x")
    try:
        w, h = int(size_param[0]), int(size_param[1])
    except (ValueError, IndexError):
        w, h = 512, 512
    w = max(128, min(w, 1024))
    h = max(128, min(h, 1024))

    rng = _rng(prompt, params)
    c1 = (rng.randint(40, 200), rng.randint(40, 200), rng.randint(40, 200))
    c2 = (rng.randint(40, 200), rng.randint(40, 200), rng.randint(40, 200))

    img = Image.new("RGB", (w, h), c1)
    draw = ImageDraw.Draw(img)

    for y in range(h):
        t = y / max(1, h - 1)
        r = int(c1[0] * (1 - t) + c2[0] * t)
        g = int(c1[1] * (1 - t) + c2[1] * t)
        b = int(c1[2] * (1 - t) + c2[2] * t)
        draw.line([(0, y), (w, y)], fill=(r, g, b))

    font = _load_font(max(14, w // 24))
    max_chars = max(10, w // max(8, w // 24) - 2)
    lines, cur = [], ""
    for word in (prompt or "без промпта").strip().split():
        candidate = (cur + " " + word).strip()
        if len(candidate) <= max_chars:
            cur = candidate
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)

    line_h = max(18, h // 20)
    y = max(10, (h - len(lines) * line_h) // 2)
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        draw.text(((w - (bbox[2] - bbox[0])) / 2, y), line, fill=(255, 255, 255), font=font)
        y += line_h

    draw.text((10, h - 20), "MOCK GENERATOR", fill=(255, 255, 255),
              font=_load_font(max(10, w // 40)))

    if out_path is None:
        out_path = os.path.join(os.getcwd(), "mock_image.png")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    img.save(out_path, format="PNG")
    return out_path


# --------------------------------------------------------------------------
# Mock-генерация аудио (стандартный модуль wave)
# --------------------------------------------------------------------------


def generate_audio(prompt: str, params: dict | None = None, out_path: str | None = None) -> str:
    """Создаёт WAV-файл с короткой мелодией, детерминированной промптом."""
    params = params or {}
    try:
        duration = float(params.get("duration", 3) or 3)
    except (TypeError, ValueError):
        duration = 3.0
    duration = max(0.5, min(duration, 15.0))

    sample_rate = 16000
    rng = _rng(prompt, params)
    base = rng.choice([220, 262, 294, 330, 349, 392, 440])
    scale = [0, 2, 4, 5, 7, 9, 11, 12]
    n_notes = max(3, int(duration))
    note_len = duration / n_notes

    frames = bytearray()
    for _ in range(n_notes):
        freq = base * (2 ** (rng.choice(scale) / 12.0))
        n_samples = int(sample_rate * note_len)
        for s in range(n_samples):
            env = math.sin(math.pi * s / max(1, n_samples))
            value = 0.5 * env * (
                math.sin(2 * math.pi * freq * s / sample_rate)
                + 0.5 * math.sin(2 * math.pi * freq * 2 * s / sample_rate)
            )
            frames += struct.pack("<h", int(max(-1.0, min(1.0, value)) * 32767))

    if out_path is None:
        out_path = os.path.join(os.getcwd(), "mock_audio.wav")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with wave.open(out_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(bytes(frames))
    return out_path


# --------------------------------------------------------------------------
# Реальная генерация изображения (Pollinations.AI, бесплатный сервис)
# --------------------------------------------------------------------------


def build_image_url(prompt: str, params: dict | None, config: dict) -> str:
    """Формирует URL запроса к Pollinations.AI по промпту и размеру."""
    params = params or {}
    size_param = str(params.get("size", "512x512")).lower().split("x")
    try:
        w, h = int(size_param[0]), int(size_param[1])
    except (ValueError, IndexError):
        w, h = 512, 512
    w = max(128, min(w, 1024))
    h = max(128, min(h, 1024))
    base = config.get("POLLINATIONS_URL", "https://image.pollinations.ai/prompt")
    quoted = urllib.parse.quote((prompt or "abstract art").strip(), safe="")
    model = config.get("POLLINATIONS_MODEL", "turbo")
    referrer = config.get("POLLINATIONS_REFERRER", "aics-prototype")
    return (f"{base}/{quoted}?width={w}&height={h}&model={model}"
            f"&nologo=true&referrer={urllib.parse.quote(referrer, safe='')}")


def fetch_bytes(url: str, timeout: int, headers: dict | None = None) -> bytes:
    """Скачивает содержимое URL (в тестах подменяется через monkeypatch)."""
    req = urllib.request.Request(url, headers=headers or {
        "User-Agent": "AICS-Prototype/1.0 (+educational)",
        "Accept": "image/*",
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def generate_image_real(prompt: str, params: dict | None, out_path: str, config: dict):
    """Загружает реальное изображение по промпту и сохраняет его как PNG.

    Возвращает путь к файлу или None — тогда вызывающий код откатывается к mock.
    Сервис может отвечать нестабильно (пустой ответ, HTTP 402 при исчерпании
    анонимной квоты), поэтому выполняются повторные попытки.
    """
    if not out_path:
        out_path = os.path.join(os.getcwd(), "image.png")
    attempts = max(1, int(config.get("IMAGE_RETRIES", 3) or 1))
    delay = float(config.get("IMAGE_RETRY_DELAY", 3) or 0)
    url = build_image_url(prompt, params, config)

    for attempt in range(attempts):
        try:
            raw = fetch_bytes(url, config.get("IMAGE_TIMEOUT", 120))
            if len(raw) < 1024:
                raise ValueError("слишком короткий ответ сервиса")
            img = Image.open(io.BytesIO(raw)).convert("RGB")
            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            img.save(out_path, format="PNG")
            if os.path.getsize(out_path) >= 1024:
                return out_path
        except Exception:
            pass  # любая ошибка — повтор/откат к mock
        if attempt < attempts - 1 and delay:
            time.sleep(delay)
    return None


# --------------------------------------------------------------------------
# Реальная озвучка текста (Windows SAPI5 через System.Speech, офлайн)
# --------------------------------------------------------------------------

# Скрипт PowerShell синтезирует речь из файла в WAV. Пользовательский текст
# передаётся через переменные окружения (не в командной строке) — это исключает
# инъекцию команд.
_TTS_PS = r"""
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
if ($env:AICS_TTS_VOICE) {
    try { $synth.SelectVoice($env:AICS_TTS_VOICE) } catch { }
} else {
    $ru = $synth.GetInstalledVoices() | Where-Object { $_.VoiceInfo.Culture.Name -like 'ru*' } | Select-Object -First 1
    if ($ru) { try { $synth.SelectVoice($ru.VoiceInfo.Name) } catch { } }
}
try { $synth.Rate = [int]$env:AICS_TTS_RATE } catch { }
$synth.SetOutputToWaveFile($env:AICS_TTS_OUT)
$text = [System.IO.File]::ReadAllText($env:AICS_TTS_TEXT, [System.Text.Encoding]::UTF8)
$synth.Speak($text)
$synth.Dispose()
"""


def generate_audio_real(prompt: str, params: dict | None, out_path: str, config: dict):
    """Озвучивает текст промпта голосом Windows и сохраняет WAV.

    Возвращает путь к файлу или None при неудаче (в этом случае используется mock).
    """
    if os.name != "nt":
        return None
    text = (prompt or "").strip()
    if not text:
        return None
    if not out_path:
        out_path = os.path.join(os.getcwd(), "audio.wav")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    text_file = out_path + ".txt"
    with open(text_file, "w", encoding="utf-8") as fh:
        fh.write(text)

    env = dict(os.environ)
    env["AICS_TTS_TEXT"] = text_file
    env["AICS_TTS_OUT"] = out_path
    env["AICS_TTS_VOICE"] = (config.get("TTS_VOICE") or "").strip()
    env["AICS_TTS_RATE"] = str(config.get("TTS_RATE", 0))

    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive",
             "-ExecutionPolicy", "Bypass", "-Command", _TTS_PS],
            env=env, capture_output=True, timeout=config.get("TTS_TIMEOUT", 60),
        )
        if os.path.exists(out_path) and os.path.getsize(out_path) > 1024:
            return out_path
        return None
    except Exception:
        return None
    finally:
        try:
            os.remove(text_file)
        except OSError:
            pass


# --------------------------------------------------------------------------
# Опциональный реальный API (Hugging Face Inference API)
# --------------------------------------------------------------------------


def generate_text_real(prompt: str, params: dict | None, config: dict):
    """Пробует бесплатный HF Inference API; при ошибке возвращает None."""
    token = config.get("HF_API_TOKEN")
    if not token:
        return None
    import urllib.error
    import urllib.request

    url = f"{config['HF_API_URL']}/{config['HF_TEXT_MODEL']}"
    payload = json.dumps({"inputs": prompt, "parameters": params or {}}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=config.get("HTTP_TIMEOUT", 20)) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if isinstance(data, list) and data:
            item = data[0]
            if isinstance(item, dict) and "generated_text" in item:
                return item["generated_text"]
            if isinstance(item, str):
                return item
        return None
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return None  # Откат к mock-генератору


# --------------------------------------------------------------------------
# Единая точка входа
# --------------------------------------------------------------------------


def generate(content_type: str, prompt: str, params: dict, out_path: str, config: dict):
    """Диспетчер генерации.

    Возвращает словарь {"result_text", "result_path", "engine"}.
    """
    params = params or {}
    if content_type == "text":
        text, engine = None, "mock"
        if config.get("USE_REAL_API"):
            text = generate_text_real(prompt, params, config)
            if text:
                engine = "hf"
        if not text:
            text = generate_text(prompt, params)
        return {"result_text": text, "result_path": None, "engine": engine}

    if content_type == "image":
        path, engine = None, "mock"
        if config.get("USE_REAL_IMAGE"):
            path = generate_image_real(prompt, params, out_path, config)
            if path:
                engine = "pollinations"
        if path is None:
            path = generate_image(prompt, params, out_path)
        return {"result_text": None, "result_path": os.path.basename(path), "engine": engine}

    if content_type == "audio":
        path, engine = None, "mock"
        if config.get("USE_REAL_AUDIO"):
            path = generate_audio_real(prompt, params, out_path, config)
            if path:
                engine = "sapi5-tts"
        if path is None:
            path = generate_audio(prompt, params, out_path)
        return {"result_text": None, "result_path": os.path.basename(path), "engine": engine}

    raise ValueError(f"Неизвестный тип контента: {content_type}")


def estimate_tokens(content_type: str, tariff: str, config) -> int:
    """Считает стоимость генерации в токенах с учётом тарифа."""
    base = config["TOKEN_COST"].get(content_type, 0)
    factor = config["TARIFF_COST_FACTOR"].get(tariff, 1.0)
    return int(round(base * factor))
