from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

from security import hash_password, verify_password, is_valid_username

DB_FILE = os.environ.get("LOGICORD_DB", "users.db")


def utc_now() -> str:
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
            """
        )


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