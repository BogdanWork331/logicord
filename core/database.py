from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

from .config import DB_FILE, DEFAULT_CHANNEL_NAME, DEFAULT_BACKGROUND, DEFAULT_LANGUAGE, DEFAULT_THEME
from .security import hash_password, verify_password


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def get_conn() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DB_FILE, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {k: row[k] for k in row.keys()}


def fetch_one(query: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
    with get_conn() as conn:
        cur = conn.execute(query, params)
        return row_to_dict(cur.fetchone())


def fetch_all(query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    with get_conn() as conn:
        cur = conn.execute(query, params)
        return [row_to_dict(r) for r in cur.fetchall()]


def execute(query: str, params: tuple[Any, ...] = ()) -> int:
    with get_conn() as conn:
        cur = conn.execute(query, params)
        return cur.lastrowid


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                display_name TEXT,
                bio TEXT DEFAULT '',
                avatar_b64 TEXT DEFAULT NULL,
                theme TEXT NOT NULL DEFAULT 'dark',
                background TEXT NOT NULL DEFAULT 'aurora',
                language TEXT NOT NULL DEFAULT 'ru',
                status_text TEXT DEFAULT 'online',
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                is_private INTEGER NOT NULL DEFAULT 0,
                created_by INTEGER,
                created_at TEXT NOT NULL,
                FOREIGN KEY(created_by) REFERENCES users(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id INTEGER NOT NULL,
                author_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                reply_to INTEGER DEFAULT NULL,
                pinned INTEGER NOT NULL DEFAULT 0,
                deleted INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                edited_at TEXT DEFAULT NULL,
                FOREIGN KEY(channel_id) REFERENCES channels(id) ON DELETE CASCADE,
                FOREIGN KEY(author_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS settings (
                user_id INTEGER PRIMARY KEY,
                theme TEXT NOT NULL DEFAULT 'dark',
                background TEXT NOT NULL DEFAULT 'aurora',
                language TEXT NOT NULL DEFAULT 'ru',
                remember_me INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                read_at TEXT DEFAULT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS direct_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_id INTEGER NOT NULL,
                recipient_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                read_at TEXT DEFAULT NULL,
                FOREIGN KEY(sender_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY(recipient_id) REFERENCES users(id) ON DELETE CASCADE
            );
            """
        )

    ensure_default_data()


def ensure_default_data() -> None:
    channel = get_channel_by_name(DEFAULT_CHANNEL_NAME)
    if channel is None:
        create_channel(DEFAULT_CHANNEL_NAME, created_by=None, is_private=False)


def create_user(username: str, password: str, role: str = "user") -> tuple[bool, str]:
    username = (username or "").strip()
    password = (password or "").strip()

    if len(username) < 3:
        return False, "Имя пользователя должно быть минимум 3 символа"
    if len(password) < 6:
        return False, "Пароль должен быть минимум 6 символов"

    try:
        password_hash = hash_password(password)
        with get_conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO users (username, password_hash, role, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (username, password_hash, role, utc_now_iso()),
            )
            user_id = cur.lastrowid
            conn.execute(
                """
                INSERT INTO profiles (user_id, display_name, bio, avatar_b64, theme, background, language, status_text)
                VALUES (?, ?, '', NULL, ?, ?, ?, 'online')
                """,
                (user_id, username, DEFAULT_THEME, DEFAULT_BACKGROUND, DEFAULT_LANGUAGE),
            )
            conn.execute(
                """
                INSERT OR REPLACE INTO settings (user_id, theme, background, language, remember_me)
                VALUES (?, ?, ?, ?, 0)
                """,
                (user_id, DEFAULT_THEME, DEFAULT_BACKGROUND, DEFAULT_LANGUAGE),
            )
        return True, "OK"
    except sqlite3.IntegrityError:
        return False, "Пользователь уже существует"
    except Exception as exc:
        return False, f"Ошибка регистрации: {exc}"


def get_user_by_username(username: str) -> dict[str, Any] | None:
    return fetch_one("SELECT * FROM users WHERE username = ?", ((username or "").strip(),))


def get_user_by_id(user_id: int) -> dict[str, Any] | None:
    return fetch_one("SELECT * FROM users WHERE id = ?", (user_id,))


def authenticate_user(username: str, password: str) -> tuple[bool, str, dict[str, Any] | None]:
    user = get_user_by_username(username)
    if not user:
        return False, "Пользователь не найден", None
    if not verify_password(password, user["password_hash"]):
        return False, "Неверный пароль", None
    return True, "OK", user


def get_profile(user_id: int) -> dict[str, Any] | None:
    return fetch_one("SELECT * FROM profiles WHERE user_id = ?", (user_id,))


def upsert_profile(
    user_id: int,
    display_name: str | None = None,
    bio: str | None = None,
    avatar_b64: str | None = None,
    theme: str | None = None,
    background: str | None = None,
    language: str | None = None,
    status_text: str | None = None,
) -> None:
    current = get_profile(user_id)
    if current is None:
        current = {
            "display_name": None,
            "bio": "",
            "avatar_b64": None,
            "theme": DEFAULT_THEME,
            "background": DEFAULT_BACKGROUND,
            "language": DEFAULT_LANGUAGE,
            "status_text": "online",
        }

    display_name = current["display_name"] if display_name is None else display_name
    bio = current["bio"] if bio is None else bio
    avatar_b64 = current["avatar_b64"] if avatar_b64 is None else avatar_b64
    theme = current["theme"] if theme is None else theme
    background = current["background"] if background is None else background
    language = current["language"] if language is None else language
    status_text = current["status_text"] if status_text is None else status_text

    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO profiles (user_id, display_name, bio, avatar_b64, theme, background, language, status_text)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                display_name=excluded.display_name,
                bio=excluded.bio,
                avatar_b64=excluded.avatar_b64,
                theme=excluded.theme,
                background=excluded.background,
                language=excluded.language,
                status_text=excluded.status_text
            """,
            (user_id, display_name, bio, avatar_b64, theme, background, language, status_text),
        )


def save_settings(user_id: int, theme: str, background: str, language: str, remember_me: bool) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO settings (user_id, theme, background, language, remember_me)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                theme=excluded.theme,
                background=excluded.background,
                language=excluded.language,
                remember_me=excluded.remember_me
            """,
            (user_id, theme, background, language, 1 if remember_me else 0),
        )


def get_settings(user_id: int) -> dict[str, Any]:
    settings = fetch_one("SELECT * FROM settings WHERE user_id = ?", (user_id,))
    if settings is None:
        settings = {
            "user_id": user_id,
            "theme": DEFAULT_THEME,
            "background": DEFAULT_BACKGROUND,
            "language": DEFAULT_LANGUAGE,
            "remember_me": 0,
        }
    return settings


def create_channel(name: str, created_by: int | None, is_private: bool = False) -> tuple[bool, str]:
    name = (name or "").strip().lower().replace(" ", "-")
    if len(name) < 2:
        return False, "Название канала слишком короткое"

    try:
        execute(
            """
            INSERT INTO channels (name, is_private, created_by, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (name, 1 if is_private else 0, created_by, utc_now_iso()),
        )
        return True, "OK"
    except sqlite3.IntegrityError:
        return False, "Канал уже существует"
    except Exception as exc:
        return False, f"Ошибка создания канала: {exc}"


def list_channels() -> list[dict[str, Any]]:
    return fetch_all("SELECT * FROM channels ORDER BY is_private ASC, name ASC")


def get_channel(channel_id: int) -> dict[str, Any] | None:
    return fetch_one("SELECT * FROM channels WHERE id = ?", (channel_id,))


def get_channel_by_name(name: str) -> dict[str, Any] | None:
    return fetch_one("SELECT * FROM channels WHERE name = ?", ((name or "").strip().lower(),))


def create_message(channel_id: int, author_id: int, content: str, reply_to: int | None = None) -> int:
    content = (content or "").strip()
    if not content:
        raise ValueError("Empty message")

    return execute(
        """
        INSERT INTO messages (channel_id, author_id, content, reply_to, pinned, deleted, created_at)
        VALUES (?, ?, ?, ?, 0, 0, ?)
        """,
        (channel_id, author_id, content, reply_to, utc_now_iso()),
    )


def list_messages(channel_id: int, limit: int = 200) -> list[dict[str, Any]]:
    return fetch_all(
        """
        SELECT m.*, u.username, u.role, p.display_name, p.avatar_b64, p.status_text
        FROM messages m
        JOIN users u ON u.id = m.author_id
        LEFT JOIN profiles p ON p.user_id = u.id
        WHERE m.channel_id = ?
        ORDER BY m.created_at ASC, m.id ASC
        LIMIT ?
        """,
        (channel_id, limit),
    )


def update_message(message_id: int, author_id: int, new_content: str, is_admin: bool = False) -> tuple[bool, str]:
    msg = fetch_one("SELECT * FROM messages WHERE id = ?", (message_id,))
    if msg is None:
        return False, "Сообщение не найдено"
    if msg["deleted"]:
        return False, "Сообщение удалено"
    if msg["author_id"] != author_id and not is_admin:
        return False, "Нет прав на редактирование"

    new_content = (new_content or "").strip()
    if not new_content:
        return False, "Пустое сообщение"

    execute(
        """
        UPDATE messages
        SET content = ?, edited_at = ?
        WHERE id = ?
        """,
        (new_content, utc_now_iso(), message_id),
    )
    return True, "OK"


def delete_message(message_id: int, author_id: int, is_admin: bool = False) -> tuple[bool, str]:
    msg = fetch_one("SELECT * FROM messages WHERE id = ?", (message_id,))
    if msg is None:
        return False, "Сообщение не найдено"
    if msg["author_id"] != author_id and not is_admin:
        return False, "Нет прав на удаление"

    execute(
        """
        UPDATE messages
        SET deleted = 1, content = '[message deleted]', edited_at = ?
        WHERE id = ?
        """,
        (utc_now_iso(), message_id),
    )
    return True, "OK"


def pin_message(message_id: int, is_admin: bool = False, pinned: bool = True) -> tuple[bool, str]:
    if not is_admin:
        return False, "Только администратор может закреплять сообщения"

    execute(
        "UPDATE messages SET pinned = ? WHERE id = ?",
        (1 if pinned else 0, message_id),
    )
    return True, "OK"


def list_pinned_messages(channel_id: int) -> list[dict[str, Any]]:
    return fetch_all(
        """
        SELECT m.*, u.username, u.role, p.display_name, p.avatar_b64, p.status_text
        FROM messages m
        JOIN users u ON u.id = m.author_id
        LEFT JOIN profiles p ON p.user_id = u.id
        WHERE m.channel_id = ? AND m.pinned = 1 AND m.deleted = 0
        ORDER BY m.created_at DESC
        """,
        (channel_id,),
    )


def create_notification(user_id: int, title: str, body: str) -> None:
    execute(
        """
        INSERT INTO notifications (user_id, title, body, read_at, created_at)
        VALUES (?, ?, ?, NULL, ?)
        """,
        (user_id, title, body, utc_now_iso()),
    )


def list_notifications(user_id: int) -> list[dict[str, Any]]:
    return fetch_all(
        """
        SELECT * FROM notifications
        WHERE user_id = ?
        ORDER BY created_at DESC
        """,
        (user_id,),
    )


def mark_notification_read(notification_id: int) -> None:
    execute(
        "UPDATE notifications SET read_at = ? WHERE id = ?",
        (utc_now_iso(), notification_id),
    )


def create_direct_message(sender_id: int, recipient_id: int, content: str) -> int:
    return execute(
        """
        INSERT INTO direct_messages (sender_id, recipient_id, content, created_at, read_at)
        VALUES (?, ?, ?, ?, NULL)
        """,
        (sender_id, recipient_id, content, utc_now_iso()),
    )