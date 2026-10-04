-- =============================================================================
-- Схема БД учебного прототипа генератора контента
-- СУБД: SQLite (для прототипа). Совместима с PostgreSQL/MySQL на уровне DDL
-- (см. docs/ТЗ.md, раздел "Перспективные требования").
-- =============================================================================

-- Пользователи системы. Две роли: 'user' и 'admin'.
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT    NOT NULL UNIQUE,
    email         TEXT    NOT NULL UNIQUE,
    password_hash TEXT    NOT NULL,
    role          TEXT    NOT NULL DEFAULT 'user',   -- user | admin
    tariff        TEXT    NOT NULL DEFAULT 'free',   -- free | pro | business
    token_balance INTEGER NOT NULL DEFAULT 100,
    is_blocked    INTEGER NOT NULL DEFAULT 0,        -- 0 | 1
    created_at    TEXT    NOT NULL
);

-- Проекты генерации (история запросов пользователя).
CREATE TABLE IF NOT EXISTS generations (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER NOT NULL,
    content_type TEXT    NOT NULL,                   -- text | image | audio
    prompt       TEXT    NOT NULL,
    params       TEXT    NOT NULL DEFAULT '{}',      -- JSON с параметрами
    status       TEXT    NOT NULL,                   -- success | rejected | error
    result_text  TEXT,                               -- результат для текста
    result_path  TEXT,                               -- файл-артефакт (image/audio)
    tokens_spent INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT    NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_gen_user ON generations (user_id);
CREATE INDEX IF NOT EXISTS idx_gen_type ON generations (content_type);
CREATE INDEX IF NOT EXISTS idx_gen_date ON generations (created_at);

-- Транзакции по балансу токенов (пополнения и списания).
CREATE TABLE IF NOT EXISTS transactions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    amount      INTEGER NOT NULL,                    -- >0 пополнение, <0 списание
    kind        TEXT    NOT NULL,                    -- topup | generation
    description TEXT,
    created_at  TEXT    NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_tx_user ON transactions (user_id);
CREATE INDEX IF NOT EXISTS idx_tx_date ON transactions (created_at);

-- Журнал действий администратора (блокировка и т.п.) — для отчётности.
CREATE TABLE IF NOT EXISTS audit_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_id   INTEGER,
    action     TEXT    NOT NULL,
    target     TEXT,
    created_at TEXT    NOT NULL
);
