from __future__ import annotations

import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

from security import hash_password, verify_password, is_valid_username

DB_FILE = os.environ.get("LOGICORD_DB", "users.db")
_CONN: sqlite3.Connection | None = None
_DB_LOCK = threading.RLock()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def get_conn() -> Iterator[sqlite3.Connection]:
    global _CONN
    with _DB_LOCK:
        if _CONN is None:
            _CONN = sqlite3.connect(DB_FILE, timeout=30, check_same_thread=False)
            _CONN.row_factory = sqlite3.Row
            _CONN.execute("PRAGMA journal_mode=WAL")
            _CONN.execute("PRAGMA synchronous=NORMAL")
        try:
            yield _CONN
            _CONN.commit()
        except Exception:
            _CONN.rollback()
            raise


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {k: row[k] for k in row.keys()}


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
                user_id INTEGER UNIQUE NOT NULL,
                display_name TEXT NOT NULL,
                avatar TEXT NOT NULL DEFAULT '😀',
                bio TEXT NOT NULL DEFAULT '',
                theme TEXT NOT NULL DEFAULT 'dark',
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS settings (
                user_id INTEGER PRIMARY KEY,
                remember_me INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                text TEXT NOT NULL,
                kind TEXT NOT NULL DEFAULT 'text',
                file_name TEXT,
                file_path TEXT,
                file_url TEXT,
                file_data BLOB,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_messages_created_at
                ON messages(created_at, id);
            """
        )
        message_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(messages)")
        }
        for name, definition in (
            ("kind", "TEXT NOT NULL DEFAULT 'text'"),
            ("file_name", "TEXT"),
            ("file_path", "TEXT"),
            ("file_url", "TEXT"),
            ("file_data", "BLOB"),
        ):
            if name not in message_columns:
                conn.execute(f"ALTER TABLE messages ADD COLUMN {name} {definition}")


def create_user(
    username: str,
    password: str,
    avatar: str = "😀",
    display_name: str | None = None,
) -> tuple[bool, str]:
    username = (username or "").strip()
    password = (password or "").strip()
    display_name = (display_name or "").strip() or username
    avatar = (avatar or "😀").strip()[:4] or "😀"

    if not username or not password:
        return False, "Введіть логін та пароль"
    if not is_valid_username(username):
        return False, "Логін: 3–32 символа, тільки латиниця, цифри, _, -, ."
    if len(password) < 6:
        return False, "Пароль повинен бути мінімум 6 символів"

    try:
        pwd_hash = hash_password(password)
        with get_conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO users (username, password_hash, role, created_at)
                VALUES (?, ?, 'user', ?)
                """,
                (username, pwd_hash, utc_now()),
            )
            user_id = cur.lastrowid
            conn.execute(
                """
                INSERT INTO profiles (user_id, display_name, avatar, bio, theme)
                VALUES (?, ?, ?, '', 'dark')
                """,
                (user_id, display_name, avatar),
            )
            conn.execute(
                """
                INSERT INTO settings (user_id, remember_me)
                VALUES (?, 0)
                """,
                (user_id,),
            )
        return True, "Аккаунт створено"
    except sqlite3.IntegrityError:
        return False, "Користувач вже існує"
    except Exception as exc:
        return False, f"Помилка реєстрації: {exc}"


def get_user_by_username(username: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        cur = conn.execute("SELECT * FROM users WHERE username = ?", ((username or "").strip(),))
        return row_to_dict(cur.fetchone())


def get_user_by_id(user_id: int) -> dict[str, Any] | None:
    with get_conn() as conn:
        cur = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        return row_to_dict(cur.fetchone())


def authenticate_user(username: str, password: str) -> tuple[bool, str, dict[str, Any] | None]:
    user = get_user_by_username(username)
    if not user:
        return False, "Користувач не знайдений", None
    if not verify_password(password, user["password_hash"]):
        return False, "Невірний пароль", None
    return True, "OK", user


def get_profile(user_id: int) -> dict[str, Any] | None:
    with get_conn() as conn:
        cur = conn.execute("SELECT * FROM profiles WHERE user_id = ?", (user_id,))
        return row_to_dict(cur.fetchone())


def add_message(
    user_id: int,
    text: str,
    kind: str = "text",
    file_name: str | None = None,
    file_path: str | None = None,
    file_url: str | None = None,
    file_data: bytes | None = None,
) -> dict[str, Any]:
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO messages
                (user_id, text, kind, file_name, file_path, file_url, file_data, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, text, kind, file_name, file_path, file_url, file_data, utc_now()),
        )
        message_id = cur.lastrowid
        row = conn.execute(
            """
            SELECT m.id, m.user_id, u.username,
                   COALESCE(p.display_name, u.username) AS display_name,
                   COALESCE(p.avatar, '😀') AS avatar,
                   m.text, m.kind, m.file_name, m.file_path, m.file_url, m.file_data,
                   strftime('%H:%M', m.created_at) AS time
            FROM messages m
            JOIN users u ON u.id = m.user_id
            LEFT JOIN profiles p ON p.user_id = m.user_id
            WHERE m.id = ?
            """,
            (message_id,),
        ).fetchone()
    return row_to_dict(row) or {}


def get_recent_messages(limit: int = 70) -> list[dict[str, Any]]:
    limit = max(1, min(limit, 70))
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT m.id, m.user_id, u.username,
                   COALESCE(p.display_name, u.username) AS display_name,
                   COALESCE(p.avatar, '😀') AS avatar,
                   m.text, m.kind, m.file_name, m.file_path, m.file_url, m.file_data,
                   strftime('%H:%M', m.created_at) AS time
            FROM messages m
            JOIN users u ON u.id = m.user_id
            LEFT JOIN profiles p ON p.user_id = m.user_id
            ORDER BY m.id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [row_to_dict(row) for row in reversed(rows)]


def upsert_profile(
    user_id: int,
    display_name: str | None = None,
    avatar: str | None = None,
    bio: str | None = None,
    theme: str | None = None,
) -> None:
    current = get_profile(user_id) or {
        "display_name": "",
        "avatar": "😀",
        "bio": "",
        "theme": "dark",
    }

    display_name = (display_name if display_name is not None else current["display_name"]).strip() or current["display_name"]
    avatar = (avatar if avatar is not None else current["avatar"]).strip()[:4] or current["avatar"]
    bio = (bio if bio is not None else current["bio"]).strip()
    theme = (theme if theme is not None else current["theme"]).strip()

    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO profiles (user_id, display_name, avatar, bio, theme)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                display_name=excluded.display_name,
                avatar=excluded.avatar,
                bio=excluded.bio,
                theme=excluded.theme
            """,
            (user_id, display_name, avatar, bio, theme),
        )


def get_settings(user_id: int) -> dict[str, Any]:
    with get_conn() as conn:
        cur = conn.execute("SELECT * FROM settings WHERE user_id = ?", (user_id,))
        row = row_to_dict(cur.fetchone())
    if row is None:
        row = {"user_id": user_id, "remember_me": 0}
    return row


def save_settings(user_id: int, remember_me: bool) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO settings (user_id, remember_me)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                remember_me=excluded.remember_me
            """,
            (user_id, 1 if remember_me else 0),
        )


def list_all_users() -> list[dict[str, Any]]:
    with get_conn() as conn:
        cur = conn.execute(
            """
            SELECT u.id, u.username, u.role, p.display_name, p.avatar, p.theme
            FROM users u
            LEFT JOIN profiles p ON p.user_id = u.id
            ORDER BY u.username ASC
            """
        )
        return [row_to_dict(r) for r in cur.fetchall()]