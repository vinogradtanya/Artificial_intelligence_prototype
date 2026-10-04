"""Конфигурация учебного прототипа.

Все параметры можно переопределить переменными окружения (см. .env.example).
"""
import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))


class Config:
    """Базовая конфигурация приложения."""

    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")

    # --- База данных -----------------------------------------------------
    DATABASE = os.environ.get(
        "DATABASE", os.path.join(BASE_DIR, "storage", "prototype.db")
    )
    SCHEMA_FILE = os.path.join(BASE_DIR, "schema.sql")

    # --- Хранилище сгенерированных артефактов ----------------------------
    STORAGE_DIR = os.environ.get(
        "STORAGE_DIR", os.path.join(BASE_DIR, "storage", "media")
    )

    # --- Модель монетизации (токены) -------------------------------------
    START_BALANCE = 100

    # Базовая стоимость генерации в токенах
    TOKEN_COST = {"text": 10, "image": 50, "audio": 30}

    # Тарифные коэффициенты (скидка на стоимость генерации)
    TARIFF_COST_FACTOR = {"free": 1.0, "pro": 0.8, "business": 0.5}

    # Бонус к пополнению баланса в зависимости от тарифа
    TARIFF_TOPUP_BONUS = {"free": 0.0, "pro": 0.05, "business": 0.10}

    TARIFFS = ("free", "pro", "business")
    CONTENT_TYPES = ("text", "image", "audio")

    # --- Опциональный реальный AI API для текста -------------------------
    USE_REAL_API = os.environ.get("USE_REAL_API", "0") == "1"
    HF_API_TOKEN = os.environ.get("HF_API_TOKEN", "")
    HF_TEXT_MODEL = os.environ.get("HF_TEXT_MODEL", "google/flan-t5-base")
    HF_API_URL = os.environ.get(
        "HF_API_URL", "https://api-inference.huggingface.co/models"
    )
    HTTP_TIMEOUT = int(os.environ.get("HTTP_TIMEOUT", "20"))

    # --- Реальная генерация изображений (Pollinations.AI, бесплатно) -----
    # При сбое (нет сети / ошибка сервиса) — автоматический откат к mock.
    USE_REAL_IMAGE = os.environ.get("USE_REAL_IMAGE", "1") == "1"
    POLLINATIONS_URL = os.environ.get(
        "POLLINATIONS_URL", "https://image.pollinations.ai/prompt"
    )
    # turbo — лёгкая бесплатная модель (надёжнее по квоте); flux — качественнее.
    POLLINATIONS_MODEL = os.environ.get("POLLINATIONS_MODEL", "turbo")
    POLLINATIONS_REFERRER = os.environ.get("POLLINATIONS_REFERRER", "aics-prototype")
    IMAGE_TIMEOUT = int(os.environ.get("IMAGE_TIMEOUT", "45"))
    IMAGE_RETRIES = int(os.environ.get("IMAGE_RETRIES", "3"))
    IMAGE_RETRY_DELAY = float(os.environ.get("IMAGE_RETRY_DELAY", "6"))

    # --- Реальная озвучка текста (TTS, Windows SAPI5) --------------------
    # Использует системные голоса Windows через System.Speech (офлайн).
    USE_REAL_AUDIO = os.environ.get("USE_REAL_AUDIO", "1") == "1"
    TTS_VOICE = os.environ.get("TTS_VOICE", "")  # "" — авто (приоритет ru-RU)
    TTS_RATE = int(os.environ.get("TTS_RATE", "0"))  # -10..10
    TTS_TIMEOUT = int(os.environ.get("TTS_TIMEOUT", "60"))

    # --- AI-ассистент (помощник-справочник + LLM-подсказки промптов) ------
    # Офлайн-справочник работает всегда. Подсказки через LLM включаются, если
    # задан ASSISTANT_API_KEY (бесплатные ключи: Groq, OpenRouter, HuggingFace, Gemini).
    ASSISTANT_API_URL = os.environ.get(
        "ASSISTANT_API_URL", "https://api.groq.com/openai/v1/chat/completions"
    )
    ASSISTANT_API_KEY = os.environ.get("ASSISTANT_API_KEY", "")
    ASSISTANT_MODEL = os.environ.get("ASSISTANT_MODEL", "llama-3.1-8b-instant")
    ASSISTANT_TIMEOUT = int(os.environ.get("ASSISTANT_TIMEOUT", "45"))
    ASSISTANT_MAX_TOKENS = int(os.environ.get("ASSISTANT_MAX_TOKENS", "400"))


class TestConfig(Config):
    """Конфигурация для автотестов: изолированная БД, только mock-движки."""

    TESTING = True
    WTF_CSRF_ENABLED = False
    # В тестах отключаем обращения к сети и к системному TTS —
    # используются детерминированные mock-генераторы.
    USE_REAL_API = False
    USE_REAL_IMAGE = False
    USE_REAL_AUDIO = False
    ASSISTANT_API_KEY = ""  # LLM-подсказки выключены в тестах
