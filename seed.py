"""Наполнение БД: гарантирует наличие администратора и (опционально) демо-данных."""
import random

from app import create_app, models

DEFAULT_ADMIN = ("admin", "admin@example.com", "admin123")
DEMO_USERS = [
    ("ivan", "ivan@example.com", "user123"),
    ("petr", "petr@example.com", "user123"),
    ("anna", "anna@example.com", "user123"),
    ("olga", "olga@example.com", "user123"),
    ("sergey", "sergey@example.com", "user123"),
]
DEMO_PROMPTS = {
    "text": ["стих про осень", "сказка про дракона", "слоган для бренда кофе",
             "поздравление с днём рождения", "пример кода на python"],
    "image": ["закат над морем", "космический пейзаж", "город будущего",
              "лес утром", "милый котёнок"],
    "audio": ["спокойная мелодия", "мелодия для рекламы", "звук природы",
              "весёлая мелодия", "фоновая музыка"],
}


def ensure_admin(app):
    """Создаёт администратора по умолчанию, если его ещё нет."""
    with app.app_context():
        if models.get_user_by_username(DEFAULT_ADMIN[0]) is None:
            uid = models.create_user(*DEFAULT_ADMIN, role="admin", balance=0)
            models.change_balance(uid, 1000, "topup", "Стартовый баланс администратора")
            print(f"[seed] создан администратор: {DEFAULT_ADMIN[0]} / {DEFAULT_ADMIN[2]}")
            return uid
    return None


def seed_demo(app, generations_per_user=4):
    """Создаёт демонстрационных пользователей и генерации (для отчётов).

    Имитирует работу 10–20 пользователей из урезанного ТЗ.
    """
    from app import generator  # локальный импорт

    rng = random.Random(42)
    with app.app_context():
        for username, email, password in DEMO_USERS:
            if models.get_user_by_username(username) is not None:
                continue
            uid = models.create_user(username, email, password, balance=0)
            models.change_balance(uid, app.config["START_BALANCE"], "topup",
                                  "Стартовый бонус при регистрации")
            for _ in range(generations_per_user):
                ctype = rng.choice(["text", "image", "audio"])
                prompt = rng.choice(DEMO_PROMPTS[ctype])
                params = {"size": "512x512"} if ctype == "image" else \
                         ({"duration": 2} if ctype == "audio" else {"length": 0})
                cost = generator.estimate_tokens(ctype, "free", app.config)
                if ctype == "text":
                    res = generator.generate(ctype, prompt, params, None, app.config)
                    models.create_generation(uid, ctype, prompt, params, "success",
                                             result_text=res["result_text"],
                                             tokens_spent=cost)
                else:
                    ext = "png" if ctype == "image" else "wav"
                    import os
                    import secrets
                    from datetime import datetime
                    fname = f"{datetime.now():%Y%m%d_%H%M%S}_{secrets.token_hex(3)}.{ext}"
                    out = os.path.join(app.config["STORAGE_DIR"], str(uid), fname)
                    generator.generate(ctype, prompt, params, out, app.config)
                    models.create_generation(uid, ctype, prompt, params, "success",
                                             result_path=f"{uid}/{fname}", tokens_spent=cost)
                models.change_balance(uid, -cost, "generation", f"Генерация {ctype}")
            print(f"[seed] создан демо-пользователь {username} с генерациями")


def seed_all(app):
    ensure_admin(app)
    seed_demo(app)


if __name__ == "__main__":
    application = create_app()
    seed_all(application)
    print("[seed] Готово.")
