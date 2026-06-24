from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import flet as ft

from core.config import APP_NAME, DEFAULT_BACKGROUND, DEFAULT_LANGUAGE, DEFAULT_THEME
from core.database import (
    init_db,
    create_user,
    authenticate_user,
    get_profile,
    upsert_profile,
    save_settings,
    get_settings,
    list_channels,
    get_channel_by_name,
    create_channel,
    create_message,
    update_message,
    delete_message,
    pin_message,
    get_user_by_id,
    get_channel,
)
from core.logger import setup_logging
from core.security import login_rate_limiter, normalize_username, is_valid_username
from ui.auth import build_auth_view
from ui.chat import build_chat_view
from ui.theme import build_page_theme


logger = setup_logging()


@dataclass
class AppState:
    user: dict[str, Any] | None = None
    profile: dict[str, Any] | None = None
    theme: str = DEFAULT_THEME
    background: str = DEFAULT_BACKGROUND
    language: str = DEFAULT_LANGUAGE
    remember_me: bool = False
    selected_channel_id: int | None = None
    message_input: ft.TextField | None = None
    online_users: dict[int, dict[str, Any]] | None = None


class LogicordApp:
    def __init__(self, page: ft.Page) -> None:
        self.page = page
        self.state = AppState(
            online_users={},
        )
        self._emoji_input: ft.TextField | None = None

    @property
    def is_admin(self) -> bool:
        return bool(self.state.user and self.state.user.get("role") == "admin")

    def toast(self, message: str) -> None:
        self.page.snack_bar = ft.SnackBar(ft.Text(message), open=True)
        self.page.update()

    def init_session(self) -> None:
        self.page.title = APP_NAME
        self.page.padding = 0
        self.page.spacing = 0
        self.page.theme_mode = ft.ThemeMode.DARK
        self.page.theme = build_page_theme(self.state.theme)
        self.page.bgcolor = None
        self.page.window_min_width = 1100
        self.page.window_min_height = 720

        self.page.pubsub.subscribe(self._on_pubsub)

        stored_user_id = self.page.session.get("user_id")
        if stored_user_id:
            user = get_user_by_id(int(stored_user_id))
            if user:
                self.state.user = user
                self.state.profile = get_profile(user["id"])
                settings = get_settings(user["id"])
                self.state.theme = settings["theme"]
                self.state.background = settings["background"]
                self.state.language = settings["language"]
                self.state.remember_me = bool(settings["remember_me"])
                self.state.selected_channel_id = self._default_channel_id()
                self.mark_online(user)
                self.apply_theme()
                self.render_chat()
                return

        self.apply_theme()
        self.render_auth()

    def _default_channel_id(self) -> int | None:
        channel = get_channel_by_name("general")
        return channel["id"] if channel else None

    def apply_theme(self) -> None:
        self.page.theme = build_page_theme(self.state.theme)
        self.page.theme_mode = ft.ThemeMode.DARK if self.state.theme == "dark" else ft.ThemeMode.LIGHT
        self.page.update()

    def render_auth(self) -> None:
        self.page.clean()
        self.page.add(build_auth_view(self))
        self.page.update()

    def render_chat(self) -> None:
        if self.state.user is None:
            self.render_auth()
            return

        if self.state.selected_channel_id is None:
            self.state.selected_channel_id = self._default_channel_id()

        self.page.clean()
        self.page.add(build_chat_view(self))
        self.page.update()

    def set_theme(self, theme: str, rerender: bool = False) -> None:
        if theme not in {"dark", "light"}:
            return
        self.state.theme = theme
        if self.state.user:
            save_settings(
                self.state.user["id"],
                theme=theme,
                background=self.state.background,
                language=self.state.language,
                remember_me=self.state.remember_me,
            )
            upsert_profile(self.state.user["id"], theme=theme)
        self.apply_theme()
        if rerender:
            self.render_auth() if self.state.user is None else self.render_chat()

    def toggle_theme(self) -> None:
        self.set_theme("light" if self.state.theme == "dark" else "dark", rerender=True)

    def set_background(self, background: str, rerender: bool = False) -> None:
        self.state.background = background
        if self.state.user:
            save_settings(
                self.state.user["id"],
                theme=self.state.theme,
                background=background,
                language=self.state.language,
                remember_me=self.state.remember_me,
            )
            upsert_profile(self.state.user["id"], background=background)
        if rerender:
            self.render_auth() if self.state.user is None else self.render_chat()

    def set_language(self, language: str, rerender: bool = False) -> None:
        self.state.language = language
        if self.state.user:
            save_settings(
                self.state.user["id"],
                theme=self.state.theme,
                background=self.state.background,
                language=language,
                remember_me=self.state.remember_me,
            )
            upsert_profile(self.state.user["id"], language=language)
        if rerender:
            self.render_auth() if self.state.user is None else self.render_chat()

    def login(self, username: str, password: str, remember: bool = False) -> tuple[bool, str]:
        username = normalize_username(username)
        if not username or not password:
            return False, "Введите логин и пароль"

        if not is_valid_username(username):
            return False, "Логин: 3–32 символа, только латиница, цифры, _, -, ."

        ok_rate, retry_after = login_rate_limiter.check(username.lower())
        if not ok_rate:
            return False, f"Слишком много попыток. Повторите через {retry_after} сек."

        ok, message, user = authenticate_user(username, password)
        if not ok or not user:
            return False, message

        self.state.user = user
        self.state.profile = get_profile(user["id"])
        settings = get_settings(user["id"])
        self.state.theme = settings["theme"]
        self.state.background = settings["background"]
        self.state.language = settings["language"]
        self.state.remember_me = bool(remember)

        save_settings(
            user["id"],
            theme=self.state.theme,
            background=self.state.background,
            language=self.state.language,
            remember_me=remember,
        )
        upsert_profile(user["id"], status_text="online")
        self.mark_online(user)
        self.page.session.set("user_id", user["id"])
        self.apply_theme()
        self.toast(f"Добро пожаловать, {user['username']}!")
        return True, "OK"

    def register(self, username: str, password: str, display_name: str | None = None) -> tuple[bool, str]:
        username = normalize_username(username)
        display_name = (display_name or "").strip() or None

        if not username or not password:
            return False, "Введите логин и пароль"
        if not is_valid_username(username):
            return False, "Логин: 3–32 символа, только латиница, цифры, _, -, ."

        ok, message = create_user(username, password)
        if not ok:
            return False, message

        user = authenticate_user(username, password)[2]
        if user and display_name:
            upsert_profile(user["id"], display_name=display_name)

        return True, "Аккаунт создан. Теперь войдите."

    def logout(self) -> None:
        if self.state.user:
            upsert_profile(self.state.user["id"], status_text="offline")
            self.mark_offline(self.state.user)
            self.page.session.remove("user_id")
        self.state.user = None
        self.state.profile = None
        self.state.selected_channel_id = None
        self.render_auth()

    def mark_online(self, user: dict[str, Any]) -> None:
        if self.state.online_users is None:
            self.state.online_users = {}
        self.state.online_users[user["id"]] = {
            "id": user["id"],
            "username": user["username"],
            "role": user.get("role", "user"),
        }

    def mark_offline(self, user: dict[str, Any]) -> None:
        if self.state.online_users is not None:
            self.state.online_users.pop(user["id"], None)

    def is_user_online(self, user_id: int | None) -> bool:
        if user_id is None or self.state.online_users is None:
            return False
        return int(user_id) in self.state.online_users

    def list_online_users(self) -> list[dict[str, Any]]:
        if not self.state.online_users:
            return []
        return list(self.state.online_users.values())

    def current_channel(self) -> dict[str, Any] | None:
        if self.state.selected_channel_id is None:
            return None
        return get_channel(self.state.selected_channel_id)

    def select_channel(self, channel_id: int) -> None:
        self.state.selected_channel_id = channel_id
        self.render_chat()

    def send_current_message(self) -> None:
        if not self.state.user:
            return
        if not self.state.selected_channel_id:
            self.state.selected_channel_id = self._default_channel_id()

        if not self.page.controls:
            return

        textfield = self._find_message_input()
        if textfield is None:
            return

        content = (textfield.value or "").strip()
        if not content:
            return

        try:
            create_message(self.state.selected_channel_id, self.state.user["id"], content)
            textfield.value = ""
            self.page.pubsub.send_all(
                {
                    "type": "refresh",
                    "channel_id": self.state.selected_channel_id,
                }
            )
            self.toast("Сообщение отправлено")
            self.render_chat()
        except Exception as exc:
            logger.exception("Failed to send message")
            self.toast(f"Ошибка отправки: {exc}")

    def _find_message_input(self) -> ft.TextField | None:
        # Current v1 rebuilds screen; locate by searching page controls is not reliable.
        # We keep the method for compatibility; actual input control is handled by build_chat_view.
        return getattr(self.state, "message_input", None)

    def open_edit_dialog(self, msg: dict[str, Any]) -> None:
        if not self.state.user:
            return

        value = msg["content"]

        field = ft.TextField(value=value, multiline=True, min_lines=4, max_lines=8, autofocus=True)

        def save(e):
            ok, info = update_message(msg["id"], self.state.user["id"], field.value or "", is_admin=self.is_admin)
            if ok:
                dlg.open = False
                self.page.update()
                self.page.pubsub.send_all({"type": "refresh", "channel_id": msg["channel_id"]})
                self.render_chat()
                self.toast("Сообщение обновлено")
            else:
                self.toast(info)

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Edit message"),
            content=field,
            actions=[
                ft.TextButton("Cancel", on_click=lambda e: self._close_dialog(dlg)),
                ft.FilledButton("Save", on_click=save),
            ],
        )
        self.page.dialog = dlg
        dlg.open = True
        self.page.update()

    def delete_message(self, message_id: int) -> None:
        if not self.state.user:
            return
        ok, info = delete_message(message_id, self.state.user["id"], is_admin=self.is_admin)
        if ok:
            self.toast("Сообщение удалено")
            self.page.pubsub.send_all({"type": "refresh", "channel_id": self.state.selected_channel_id})
            self.render_chat()
        else:
            self.toast(info)

    def toggle_pin(self, message_id: int) -> None:
        if not self.state.user:
            return
        ok, info = pin_message(message_id, is_admin=self.is_admin, pinned=True)
        if ok:
            self.toast("Сообщение закреплено")
            self.page.pubsub.send_all({"type": "refresh", "channel_id": self.state.selected_channel_id})
            self.render_chat()
        else:
            self.toast(info)

    def open_create_channel_dialog(self) -> None:
        if not self.state.user:
            return

        name_field = ft.TextField(label="Channel name", autofocus=True)

        def create(e):
            ok, info = create_channel(name_field.value or "", created_by=self.state.user["id"], is_private=False)
            if ok:
                dlg.open = False
                self.page.update()
                self.toast("Канал создан")
                self.render_chat()
            else:
                self.toast(info)

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("New channel"),
            content=name_field,
            actions=[
                ft.TextButton("Cancel", on_click=lambda e: self._close_dialog(dlg)),
                ft.FilledButton("Create", on_click=create),
            ],
        )
        self.page.dialog = dlg
        dlg.open = True
        self.page.update()

    def open_emoji_picker(self) -> None:
        if not self.state.user:
            return

        emojis = ["😀", "🔥", "😂", "👍", "💡", "🎉", "❤️", "✨"]

        def insert_emoji(emoji: str) -> None:
            field = getattr(self.state, "message_input", None)
            if field is None:
                self.toast(emoji)
                return
            field.value = (field.value or "") + emoji
            self.page.update()

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Emoji"),
            content=ft.Container(
                width=320,
                content=ft.Wrap(
                    spacing=8,
                    run_spacing=8,
                    children=[
                        ft.ElevatedButton(e, on_click=lambda ev, em=e: (insert_emoji(em), self._close_dialog(dlg))) for e in emojis
                    ],
                ),
            ),
            actions=[ft.TextButton("Close", on_click=lambda e: self._close_dialog(dlg))],
        )
        self.page.dialog = dlg
        dlg.open = True
        self.page.update()

    def open_settings_dialog(self) -> None:
        if not self.state.user:
            return

        profile = self.state.profile or get_profile(self.state.user["id"]) or {}
        display_name = ft.TextField(label="Display name", value=profile.get("display_name") or self.state.user["username"])
        bio = ft.TextField(label="Bio", value=profile.get("bio") or "", multiline=True, min_lines=3, max_lines=6)
        theme = ft.Dropdown(
            label="Theme",
            value=self.state.theme,
            options=[ft.dropdown.Option("dark"), ft.dropdown.Option("light")],
        )
        background = ft.Dropdown(
            label="Background",
            value=self.state.background,
            options=[
                ft.dropdown.Option("aurora"),
                ft.dropdown.Option("midnight"),
                ft.dropdown.Option("sunset"),
                ft.dropdown.Option("paper"),
            ],
        )
        language = ft.Dropdown(
            label="Language",
            value=self.state.language,
            options=[
                ft.dropdown.Option("ru", "Русский"),
                ft.dropdown.Option("en", "English"),
                ft.dropdown.Option("uk", "Українська"),
            ],
        )

        def save(e):
            upsert_profile(
                self.state.user["id"],
                display_name=display_name.value,
                bio=bio.value,
                theme=theme.value,
                background=background.value,
                language=language.value,
                status_text="online",
            )
            save_settings(
                self.state.user["id"],
                theme=theme.value,
                background=background.value,
                language=language.value,
                remember_me=self.state.remember_me,
            )
            self.state.profile = get_profile(self.state.user["id"])
            self.state.theme = theme.value
            self.state.background = background.value
            self.state.language = language.value
            self.apply_theme()
            dlg.open = False
            self.page.update()
            self.render_chat()
            self.toast("Настройки сохранены")

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Profile settings"),
            content=ft.Container(
                width=420,
                content=ft.Column(
                    [display_name, bio, theme, background, language],
                    tight=True,
                    spacing=10,
                ),
            ),
            actions=[
                ft.TextButton("Cancel", on_click=lambda e: self._close_dialog(dlg)),
                ft.FilledButton("Save", on_click=save),
            ],
        )
        self.page.dialog = dlg
        dlg.open = True
        self.page.update()

    def open_admin_panel(self) -> None:
        if not self.is_admin:
            self.toast("Недостаточно прав")
            return

        stats = {
            "users": len([]),
        }

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Admin panel"),
            content=ft.Column(
                [
                    ft.Text("Logicord admin dashboard"),
                    ft.Text(f"Current user: {self.state.user['username']}"),
                    ft.Text("Moderation actions can be extended here."),
                ],
                tight=True,
            ),
            actions=[ft.TextButton("Close", on_click=lambda e: self._close_dialog(dlg))],
        )
        self.page.dialog = dlg
        dlg.open = True
        self.page.update()

    def _close_dialog(self, dlg: ft.AlertDialog) -> None:
        dlg.open = False
        self.page.update()

    def _on_pubsub(self, data) -> None:
        if isinstance(data, dict) and data.get("type") == "refresh":
            if self.state.user and data.get("channel_id") == self.state.selected_channel_id:
                self.render_chat()


def main(page: ft.Page):
    init_db()
    app = LogicordApp(page)
    app.init_session()


if __name__ == "__main__":
    port = int(__import__("os").environ.get("PORT", "8550"))
    ft.app(target=main, view=ft.AppView.WEB_BROWSER, host="0.0.0.0", port=port)