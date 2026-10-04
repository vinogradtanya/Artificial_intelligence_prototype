"""AI-ассистент: «Помощник-справочник» + подсказки промптов через LLM-API.

Два режима, оба с офлайн-откатом:

1. **Помощник-справочник** — отвечает на вопросы о работе системы по локальной
   базе знаний (`KNOWLEDGE_BASE`). Работает офлайн, детерминирован, без ключей.
2. **Подсказки промптов** — при заданном `ASSISTANT_API_KEY` обращается к
   любому OpenAI-совместимому LLM-API (Groq, OpenRouter, HuggingFace Router,
   Gemini, локальная Ollama и т.п.). При отсутствии ключа/ошибке/таймауте
   возвращает детерминированные советы из `PROMPT_HINTS`.
"""
import json
import re
import urllib.error
import urllib.request

from flask import Blueprint, current_app, g, jsonify, render_template, request

from . import models
from .security import login_required

# ==========================================================================
# База знаний (офлайн)
# Формат: (id, заголовок, "ключевые слова через пробел", ответ)
# ==========================================================================

KNOWLEDGE_BASE = [
    ("start", "Начало работы",
     "начать старт регистрац войти вход логин пароль аккаунт зарегистрироваться",
     "Чтобы начать: 1) откройте «Регистрация» и укажите логин (не менее 3 символов), "
     "email и пароль (не менее 6 символов); 2) войдите по логину или email. "
     "Новому пользователю начисляется стартовый баланс — 100 токенов."),
    ("tariffs", "Тарифы",
     "тариф free pro business коэффициент скидка план подписка",
     "Доступны тарифы: free (коэффициент ×1.0, бонус пополнения 0%), "
     "pro (×0.8, бонус 5%), business (×0.5, бонус 10%). Сменить тариф можно в разделе "
     "«Кабинет». Тариф влияет на стоимость генерации и бонус при пополнении."),
    ("tokens", "Токены и стоимость",
     "токен токены баланс стоимость списание сколько стоит стоят стоить цена хватает средств",
     "Базовая стоимость генерации: текст — 10, изображение — 50, аудио — 30 токенов. "
     "Итоговая стоимость = базовая × коэффициент тарифа. Токены списываются только "
     "при успешной генерации."),
    ("topup", "Пополнение баланса",
     "пополнить баланс оплата платёж платеж купить токены деньги пополнение",
     "Раздел «Кабинет» → «Пополнение баланса»: введите сумму и нажмите «Пополнить». "
     "Это имитация оплаты — реальный платёж не проводится, баланс увеличивается, "
     "а в истории появляется транзакция. Бонус зависит от тарифа."),
    ("moderation", "Модерация промптов",
     "модерация запрещённые запрещенные отклонён отклонен отклонили нецензурный нельзя блокировка промпта",
     "Промпт проверяется по списку запрещённых слов. Если найдено запрещённое слово, "
     "генерация отклоняется (статус rejected), и токены НЕ списываются. "
     "Попробуйте переформулировать запрос."),
    ("generate", "Создание генерации",
     "сгенерировать создать генерация промпт новый проект параметры как сделать",
     "Раздел «Генерация»: выберите тип контента (текст / изображение / аудио), "
     "введите промпт, при необходимости задайте параметры (длина, размер, длительность) "
     "и нажмите «Сгенерировать»."),
    ("image", "Изображения",
     "изображение картинка рисунок png jpeg фото нарисовать иллюстрация",
     "Изображения генерируются реальной AI-моделью по вашему промпту (бесплатный сервис "
     "Pollinations.AI) и сохраняются в PNG. Доступны размеры от 256×256 до 1024×1024. "
     "Если сервис недоступен, создаётся заглушка (mock)."),
    ("audio", "Аудио и озвучка",
     "аудио звук голос озвучка речь wav мелодия tts произнести говорит",
     "Аудио создаётся реальным синтезом речи: текст промпта озвучивается системным голосом "
     "Windows (движок SAPI5, работает офлайн). Если синтез недоступен, формируется "
     "мелодия-заглушка."),
    ("text", "Текстовая генерация",
     "текст стих слоган сказка поздравление рассказ код статья",
     "Текст формируется встроенным генератором по ключевым словам промпта (mock-режим). "
     "Опционально можно подключить бесплатный Hugging Face API (переменная USE_REAL_API=1 "
     "и токен HF_API_TOKEN)."),
    ("library", "Библиотека",
     "библиотека результат сохранено скачать найти результат удалить запись",
     "Раздел «Библиотека» содержит ваши успешные генерации с фильтрами по типу и датам. "
     "Откройте запись, чтобы посмотреть или скачать результат (текст, PNG, WAV), "
     "или удалите её."),
    ("history", "История генераций",
     "история фильтр дата период статистика генераций за неделю месяц",
     "Раздел «История» показывает все ваши генерации, включая отклонённые модерацией, "
     "с фильтрами по типу контента и датам. Администратор может переключить область "
     "на «Все пользователи»."),
    ("transactions", "Транзакции",
     "транзакции транзакция движение средств расход списание по датам пополнения",
     "Раздел «Транзакции» — история пополнений и списаний токенов с фильтрами по датам."),
    ("export", "Экспорт отчётов",
     "экспорт csv json выгрузка скачать отчёт отчет excel pdf таблица",
     "На страницах «История» и «Транзакции» есть кнопки «Экспорт CSV» и «Экспорт JSON». "
     "Форматы PDF и Excel не поддерживаются — это вне объёма учебного прототипа."),
    ("admin", "Администратор",
     "админ администратор роли заблокировать пользователя статистика системы журнал аудит",
     "Администратор дополнительно видит статистику системы, может блокировать и "
     "разблокировать пользователей и просматривать журнал действий (аудит). "
     "Заблокированный пользователь не может войти в систему."),
    ("profile", "Профиль",
     "профиль сменить пароль изменить email почту данные восстановить пароль",
     "Раздел «Кабинет» → «Профиль»: можно изменить email и пароль. Логин изменить нельзя. "
     "Восстановление пароля в прототипе не реализовано."),
    ("offline", "Если сервис недоступен",
     "не работает ошибка нет интернета недоступен заглушка mock откат сбой",
     "Если внешний сервис недоступен (нет сети, лимит, сбой), система автоматически "
     "создаёт заглушку, и генерация всё равно завершается успешно. Движок указан в "
     "сообщении после генерации: pollinations / sapi5-tts / llm / mock."),
    ("limits", "Ограничения прототипа",
     "ограничения прототип учебный не для продакшн сколько пользователей резервное копирование",
     "Это учебный прототип: используется SQLite, один узел, отсутствуют резервное "
     "копирование и восстановление пароля. Объём данных — десятки пользователей."),
    ("assistant", "О помощнике",
     "ассистент помощник кто ты что умеешь справка помощь бот",
     "Я «Помощник-справочник»: отвечаю на вопросы о работе системы (офлайн, по базе знаний) "
     "и помогаю составить промпт. Подсказки на основе ИИ включаются при заданном "
     "бесплатном ключе LLM-API (переменная ASSISTANT_API_KEY)."),
    ("prompt", "Как писать промпт",
     "улучшить промпт подсказка промпт как написать сформулировать текст запроса",
     "Откройте вкладку «Подсказка к промпту», укажите тип контента и ваш промпт — "
     "ассистент предложит улучшенную формулировку и советы. Чем конкретнее промпт "
     "(объект, стиль, детали), тем лучше результат."),
]

QUICK_QUESTIONS = [
    "Как пополнить баланс?",
    "Сколько стоят генерации?",
    "Почему промпт отклонён?",
    "Как озвучивается аудио?",
    "Как экспортировать отчёт?",
    "Что умеет ассистент?",
]


# ==========================================================================
# Помощник-справочник (офлайн, детерминированный)
# ==========================================================================

_WORD_RE = re.compile(r"[^\w]+", re.UNICODE)


def _norm(text: str) -> str:
    """Нормализует текст: нижний регистр, разделители → пробелы."""
    return _WORD_RE.sub(" ", (text or "").lower())


def _matches(keyword: str, word: str) -> bool:
    """Грубое сравнение с учётом словоформ (по 5-символьному префиксу)."""
    if keyword == word:
        return True
    if len(keyword) >= 5 and len(word) >= 5:
        return keyword[:5] == word[:5]
    return False


def search_knowledge(question: str, limit: int = 3):
    """Ищет записи базы знаний по ключевым словам вопроса."""
    words = set(_norm(question).split())
    if not words:
        return []
    scored = []
    for entry_id, title, keywords, answer in KNOWLEDGE_BASE:
        hits = sum(1 for kw in keywords.split() if any(_matches(kw, w) for w in words))
        if hits:
            scored.append({"id": entry_id, "title": title, "answer": answer,
                           "score": hits})
    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[:limit]


def answer_local(question: str):
    """Формирует ответ справочника (офлайн). Возвращает словарь результата."""
    matches = search_knowledge(question)
    if not matches:
        return {
            "answer": "Не нашёл ответа на этот вопрос. Попробуйте один из популярных "
                      "вопросов ниже или переформулируйте запрос.",
            "source": None, "related": [], "engine": "local", "found": False,
        }
    best = matches[0]
    return {"answer": best["answer"], "source": best["title"],
            "related": matches[1:], "engine": "local", "found": True}


# ==========================================================================
# Подсказки по промптам
# ==========================================================================

PROMPT_HINTS = {
    "text": [
        "Укажите жанр и объём: «стих, 8 строк, про осень».",
        "Задайте тон: официальный, дружеский, рекламный.",
        "Добавьте аудиторию: «для школьников», «для соцсетей».",
    ],
    "image": [
        "Опишите объект, детали и обстановку: «рыжий кот на деревянном стуле».",
        "Укажите стиль: реализм, акварель, киберпанк, минимализм.",
        "Добавьте свет и композицию: «мягкий свет», «крупный план».",
    ],
    "audio": [
        "Для озвучки просто введите готовый текст — он будет прочитан голосом.",
        "Разбивайте длинный текст на короткие фразы.",
        "Числа и сокращения лучше писать словами: «пять», «и так далее».",
    ],
}

GENERIC_HINTS = [
    "Чем конкретнее промпт, тем лучше результат.",
    "Укажите цель, аудиторию и формат результата.",
]

PROMPT_SUFFIX = {
    "image": ", высокая детализация, мягкий естественный свет, цифровая живопись, 4К",
    "text": ". Жанр: на ваш выбор. Тон: дружеский. Объём: средний.",
    "audio": " (прочитать спокойным голосом, с короткими паузами между фразами)",
}


def prompt_hints_local(prompt: str, content_type: str):
    """Возвращает (улучшенный_промпт, список_советов) без обращения к LLM."""
    prompt = (prompt or "").strip()
    hints = PROMPT_HINTS.get(content_type, []) + GENERIC_HINTS
    improved = (prompt + PROMPT_SUFFIX.get(content_type, "")).strip() or prompt
    return improved, hints


# ==========================================================================
# Реальный LLM (OpenAI-совместимый API) с откатом на офлайн-режим
# ==========================================================================

SYSTEM_PROMPT = ("Ты — встроенный ассистент русскоязычного сервиса генерации контента. "
                 "Отвечай ВСЕГДА только на русском языке, кратко и по делу, "
                 "без лишних любезностей.")


def llm_chat(messages, config, max_tokens=None):
    """Вызов OpenAI-совместимого LLM-API. Возвращает текст или None.

    Работает с любым провайдером (Groq, OpenRouter, HuggingFace Router, Gemini,
    локальная Ollama): достаточно задать ASSISTANT_API_URL/KEY/MODEL.
    При отсутствии ключа или любой ошибке возвращает None (вызывающий код
    откатывается к офлайн-справочнику).
    """
    url = (config.get("ASSISTANT_API_URL") or "").strip()
    key = (config.get("ASSISTANT_API_KEY") or "").strip()
    if not url or not key:
        return None
    payload = {
        "model": config.get("ASSISTANT_MODEL", ""),
        "messages": messages,
        "temperature": 0.6,
        "max_tokens": max_tokens or config.get("ASSISTANT_MAX_TOKENS", 400),
    }
    try:
        req = urllib.request.Request(
            url, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {key}",
                     "User-Agent": "AICS-Prototype/1.0"})
        with urllib.request.urlopen(
                req, timeout=config.get("ASSISTANT_TIMEOUT", 45)) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        content = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
        return content.strip() or None
    except Exception:
        return None  # нет сети / лимит / неверный ключ → офлайн-режим


def ask(question: str, config):
    """Ответ ассистента: сначала LLM, при недоступности — справочник."""
    question = (question or "").strip()
    base = answer_local(question)
    if question and config.get("ASSISTANT_API_KEY"):
        llm = llm_chat([{"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": question}], config)
        if llm:
            base = dict(base, answer=llm, engine="llm",
                        source=base.get("source") or "LLM-ассистент")
    return base


def improve_prompt(prompt: str, content_type: str, config):
    """Подсказка по промпту: сначала LLM, при недоступности — офлайн-эвристика."""
    prompt = (prompt or "").strip()
    improved, hints = prompt_hints_local(prompt, content_type)

    if config.get("ASSISTANT_API_KEY"):
        user_msg = (
            f"Тип контента: {content_type}.\n"
            f"Промпт пользователя: «{prompt}».\n"
            "Отвечай ТОЛЬКО на русском языке: и сам улучшенный промпт, и советы. "
            "Не используй английские слова — пиши термины по-русски "
            "(например: «высокая детализация», «мягкий свет», «цифровая живопись»).\n"
            "Предложи один улучшенный промпт и 3 коротких совета. Формат ответа:\n"
            "Улучшенный промпт: ...\nСоветы:\n- ...\n- ...\n- ..."
        )
        llm = llm_chat([{"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_msg}], config)
        if llm:
            return {"improved": improved, "hints": hints, "llm_text": llm, "engine": "llm"}

    return {"improved": improved, "hints": hints, "llm_text": None, "engine": "local"}


# ==========================================================================
# Веб-интерфейс ассистента
# ==========================================================================

bp = Blueprint("assistant", __name__)


def _render(ask_result=None, improve_result=None, question="", prompt="",
            content_type="text"):
    return render_template(
        "assistant.html",
        questions=QUICK_QUESTIONS, ask_result=ask_result, improve_result=improve_result,
        question=question, prompt=prompt, content_type=content_type,
        llm_enabled=bool(current_app.config.get("ASSISTANT_API_KEY")),
        content_types=current_app.config["CONTENT_TYPES"],
    )


@bp.route("/assistant")
@login_required
def index():
    question = request.args.get("q", "").strip()
    ask_result = ask(question, current_app.config) if question else None
    return _render(ask_result=ask_result, question=question)


@bp.route("/assistant/ask", methods=["POST"])
@login_required
def ask_route():
    question = request.form.get("question", "").strip()
    if not question:
        return _render(question=""), 400
    result = ask(question, current_app.config)
    models.write_audit(g.user["id"], "assistant_ask", question[:80])
    return _render(ask_result=result, question=question)


@bp.route("/assistant/improve", methods=["POST"])
@login_required
def improve_route():
    prompt = request.form.get("prompt", "").strip()
    content_type = request.form.get("content_type", "text")
    if content_type not in current_app.config["CONTENT_TYPES"]:
        content_type = "text"
    if not prompt:
        return _render(prompt="", content_type=content_type), 400
    result = improve_prompt(prompt, content_type, current_app.config)
    return _render(improve_result=result, prompt=prompt, content_type=content_type)


@bp.route("/assistant/api/ask")
@login_required
def api_ask():
    """JSON-эндпоинт для программного доступа."""
    result = ask(request.args.get("q", "").strip(), current_app.config)
    result.pop("related", None)
    return jsonify(result)
