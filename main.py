from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import flet as ft

from database import (
    authenticate_user,
    create_user,
    get_profile,
    get_user_by_id,
    get_settings,
    init_db,
    list_all_users,
    save_settings,
    upsert_profile,
)
from security import login_limiter, normalize_username, is_valid_username

APP_NAME = "Logicord"

THEMES = {
    "dark": {
        "bg": "#0B1020",
        "panel": "#121A2D",
        "panel_2": "#18223A",
        "stroke": "#25314D",
        "text": "#EEF3FF",
        "muted": "#9CA7C8",
        "accent": "#6C7DFF",
        "accent_2": "#4F67FF",
        "danger": "#FF6B8B",
        "bubble_self": "#6C7DFF",
        "bubble_other": "#1C2742",
    },
    "purple": {
        "bg": "#120E1F",
        "panel": "#1D1730",
        "panel_2": "#2A2145",
        "stroke": "#3A305B",
        "text": "#F5F2FF",
        "muted": "#B5A8D8",
        "accent": "#A855F7",
        "accent_2": "#8B5CF6",
        "danger": "#FB7185",
        "bubble_self": "#A855F7",
        "bubble_other": "#2A2145",
    },
    "emerald": {
        "bg": "#07161A",
        "panel": "#0D2429",
        "panel_2": "#12333A",
        "stroke": "#1C4951",
        "text": "#E9FFFB",
        "muted": "#9BD0C8",
        "accent": "#10B981",
        "accent_2": "#14B8A6",
        "danger": "#FB7185",
        "bubble_self": "#10B981",
        "bubble_other": "#12333A",
    },
}

AVATARS = ["😀", "😎", "🤖", "👑", "🛡️", "🔥", "🎮", "💎", "🧠", "⚡"]
EMOJIS = [
    "😀", "😎", "😂", "🤣", "😁", "😍",
    "🔥", "❤️", "👍", "👎", "💡", "⚡",
    "🎉", "🎮", "💻", "🚀", "⭐", "🛡️",
]

CHAT_MESSAGES: list[dict[str, Any]] = []
ONLINE_USERS: dict[int, dict[str, Any]] = {}


def now_hm() -> str:
    return datetime.now().strftime("%H:%M")


def theme_palette(name: str) -> dict[str, str]:
    return THEMES.get(name, THEMES["dark"])


def push_message(author: dict[str, Any], text: str) -> None:
    profile = get_profile(author["id"]) or {}
    CHAT_MESSAGES.append(
        {
            "id": len(CHAT_MESSAGES) + 1,
            "user_id": author["id"],
            "username": author["username"],
            "display_name": profile.get("display_name") or author["username"],
            "avatar": profile.get("avatar") or "😀",
            "text": text,
            "time": now_hm(),
        }
    )


@dataclass
class AppState:
    user: dict[str, Any] | None = None
    profile: dict[str, Any] | None = None
    theme: str = "dark"
    mode: str = "login"  # login | register
    error: str = ""
    success: str = ""
    emoji_open: bool = False
    message_field: ft.TextField | None = None


class LogicordApp:
    def __init__(self, page: ft.Page) -> None:
        self.page = page
        self.state = AppState()

    def palette(self) -> dict[str, str]:
        return theme_palette(self.state.theme)

    def snack(self, text: str) -> None:
        self.page.snack_bar = ft.SnackBar(content=ft.Text(text))
        self.page.snack_bar.open = True
        self.page.update()

    def apply_theme(self) -> None:
        p = self.palette()
        self.page.bgcolor = p["bg"]
        self.page.theme = ft.Theme(color_scheme_seed=p["accent"])
        self.page.theme_mode = ft.ThemeMode.DARK

    def set_theme(self, theme: str) -> None:
        if theme not in THEMES:
            return
        self.state.theme = theme
        if self.state.user:
            upsert_profile(
                self.state.user["id"],
                display_name=self.state.profile["display_name"] if self.state.profile else self.state.user["username"],
                avatar=self.state.profile["avatar"] if self.state.profile else "😀",
                bio=self.state.profile["bio"] if self.state.profile else "",
                theme=theme,
            )
        self.apply_theme()
        self.render()

    def next_theme(self) -> None:
        order = list(THEMES.keys())
        idx = order.index(self.state.theme)
        self.set_theme(order[(idx + 1) % len(order)])

    def login(self, username: str, password: str, remember: bool) -> None:
        username = normalize_username(username)
        if not username or not password:
            self.state.error = "Введите логин и пароль"
            self.render()
            return

        if not is_valid_username(username):
            self.state.error = "Логин: 3–32 символа, только латиница, цифры, _, -, ."
            self.render()
            return

        allowed, retry_after = login_limiter.check(username.lower())
        if not allowed:
            self.state.error = f"Слишком много попыток. Повторите через {retry_after} сек."
            self.render()
            return

        ok, msg, user = authenticate_user(username, password)
        if not ok or not user:
            self.state.error = msg
            self.render()
            return

        self.state.user = user
        self.state.profile = get_profile(user["id"]) or {
            "display_name": user["username"],
            "avatar": "😀",
            "bio": "",
            "theme": "dark",
        }
        self.state.theme = self.state.profile.get("theme") or "dark"

        ONLINE_USERS[user["id"]] = {
            "id": user["id"],
            "username": user["username"],
            "display_name": self.state.profile.get("display_name") or user["username"],
            "avatar": self.state.profile.get("avatar") or "😀",
            "role": user.get("role", "user"),
        }

        save_settings(user["id"], remember_me=remember)
        self.state.error = ""
        self.state.success = "Успешный вход"
        self.apply_theme()
        self.render()

    def register(self, username: str, password: str, display_name: str, avatar: str) -> None:
        username = normalize_username(username)
        display_name = (display_name or "").strip()
        avatar = (avatar or "😀").strip()[:4] or "😀"

        if not username or not password:
            self.state.error = "Введите логин и пароль"
            self.render()
            return

        if not is_valid_username(username):
            self.state.error = "Логин: 3–32 символа, только латиница, цифры, _, -, ."
            self.render()
            return

        ok, msg = create_user(username, password, avatar=avatar, display_name=display_name or username)
        if not ok:
            self.state.error = msg
            self.render()
            return

        self.state.error = ""
        self.state.success = "Аккаунт создан. Теперь войдите."
        self.state.mode = "login"
        self.render()

    def logout(self) -> None:
        if self.state.user:
            ONLINE_USERS.pop(self.state.user["id"], None)
        self.state.user = None
        self.state.profile = None
        self.state.emoji_open = False
        self.state.error = ""
        self.state.success = ""
        self.render()

    def toggle_mode(self, mode: str) -> None:
        self.state.mode = mode
        self.state.error = ""
        self.state.success = ""
        self.render()

    def send_message(self) -> None:
        if not self.state.user or not self.state.message_field:
            return

        text = (self.state.message_field.value or "").strip()
        if not text:
            return

        push_message(self.state.user, text)
        self.state.message_field.value = ""
        self.page.pubsub.send_all({"type": "refresh"})
        self.render()

    def add_emoji(self, emoji: str) -> None:
        if not self.state.message_field:
            return
        self.state.message_field.value = (self.state.message_field.value or "") + emoji
        self.page.update()

    def toggle_emoji_panel(self) -> None:
        self.state.emoji_open = not self.state.emoji_open
        self.render()

    def open_profile(self) -> None:
        if not self.state.user:
            return

        profile = self.state.profile or get_profile(self.state.user["id"]) or {}
        display_name_field = ft.TextField(
            label="Имя в чате",
            value=profile.get("display_name") or self.state.user["username"],
            width=320,
        )
        avatar_dd = ft.Dropdown(
            label="Аватар",
            value=profile.get("avatar") or "😀",
            width=320,
            options=[ft.dropdown.Option(a) for a in AVATARS],
        )
        bio_field = ft.TextField(
            label="О себе",
            value=profile.get("bio") or "",
            multiline=True,
            min_lines=3,
            max_lines=5,
            width=320,
        )
        theme_dd = ft.Dropdown(
            label="Тема",
            value=self.state.theme,
            width=320,
            options=[ft.dropdown.Option(k) for k in THEMES.keys()],
        )

        def save(e):
            upsert_profile(
                self.state.user["id"],
                display_name=display_name_field.value,
                avatar=avatar_dd.value,
                bio=bio_field.value,
                theme=theme_dd.value,
            )
            self.state.profile = get_profile(self.state.user["id"])
            self.set_theme(theme_dd.value)
            self.snack("Профиль сохранён")
            dlg.open = False
            self.page.update()

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Профиль"),
            content=ft.Container(
                width=360,
                content=ft.Column(
                    [display_name_field, avatar_dd, bio_field, theme_dd],
                    tight=True,
                    spacing=10,
                ),
            ),
            actions=[
                ft.TextButton("Отмена", on_click=lambda e: self.close_dialog(dlg)),
                ft.FilledButton("Сохранить", on_click=save),
            ],
        )
        self.page.dialog = dlg
        dlg.open = True
        self.page.update()

    def close_dialog(self, dlg: ft.AlertDialog) -> None:
        dlg.open = False
        self.page.update()

    def open_theme_menu(self) -> None:
        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Тема"),
            content=ft.Column(
                [
                    ft.TextButton("Dark", on_click=lambda e: self._choose_theme("dark", dlg)),
                    ft.TextButton("Purple", on_click=lambda e: self._choose_theme("purple", dlg)),
                    ft.TextButton("Emerald", on_click=lambda e: self._choose_theme("emerald", dlg)),
                ],
                tight=True,
            ),
            actions=[ft.TextButton("Закрыть", on_click=lambda e: self.close_dialog(dlg))],
        )
        self.page.dialog = dlg
        dlg.open = True
        self.page.update()

    def _choose_theme(self, theme: str, dlg: ft.AlertDialog) -> None:
        self.set_theme(theme)
        dlg.open = False
        self.page.update()

    def render(self) -> None:
        self.apply_theme()
        self.page.clean()

        if self.state.user:
            self.page.add(self.build_chat())
        else:
            self.page.add(self.build_auth())

        self.page.update()

    def build_auth(self) -> ft.Control:
        p = self.palette()

        title = ft.Column(
            [
                ft.Container(
                    width=72,
                    height=72,
                    border_radius=20,
                    alignment=ft.alignment.center,
                    bgcolor=p["accent"],
                    content=ft.Text("L", size=30, weight=ft.FontWeight.BOLD, color=ft.colors.WHITE),
                ),
                ft.Text(APP_NAME, size=30, weight=ft.FontWeight.BOLD, color=p["text"]),
                ft.Text("Простой и быстрый чат", size=13, color=p["muted"]),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=10,
        )

        intro = ft.Container(
            expand=1,
            padding=30,
            border_radius=24,
            bgcolor=p["panel"],
            content=ft.Column(
                [
                    title,
                    ft.Container(height=8),
                    ft.Text("• Лёгкий интерфейс", color=p["text"]),
                    ft.Text("• Быстрая регистрация", color=p["text"]),
                    ft.Text("• Эмодзи-меню", color=p["text"]),
                    ft.Text("• Тёмные акцентные темы", color=p["text"]),
                    ft.Container(height=16),
                    ft.Row(
                        [
                            ft.OutlinedButton("Dark", on_click=lambda e: self.set_theme("dark")),
                            ft.OutlinedButton("Purple", on_click=lambda e: self.set_theme("purple")),
                            ft.OutlinedButton("Emerald", on_click=lambda e: self.set_theme("emerald")),
                        ],
                        wrap=True,
                    ),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=8,
            ),
        )

        login_username = ft.TextField(label="Логин", width=320)
        login_password = ft.TextField(label="Пароль", width=320, password=True, can_reveal_password=True)
        login_remember = ft.Checkbox(label="Запомнить меня", value=True)

        reg_username = ft.TextField(label="Логин", width=320)
        reg_display_name = ft.TextField(label="Имя в чате", width=320)
        reg_password = ft.TextField(label="Пароль", width=320, password=True, can_reveal_password=True)
        reg_avatar = ft.Dropdown(
            label="Аватар",
            width=320,
            value="😀",
            options=[ft.dropdown.Option(a) for a in AVATARS],
        )

        error_box = ft.Container(
            visible=bool(self.state.error),
            padding=10,
            border_radius=12,
            bgcolor="#3A1721",
            content=ft.Text(self.state.error, color="#FFB4C4", size=12),
        )

        success_box = ft.Container(
            visible=bool(self.state.success),
            padding=10,
            border_radius=12,
            bgcolor="#153126",
            content=ft.Text(self.state.success, color="#B8F7D7", size=12),
        )

        login_form = ft.Column(
            [
                ft.Text("Вход", size=20, weight=ft.FontWeight.BOLD, color=p["text"]),
                login_username,
                login_password,
                login_remember,
                ft.Row(
                    [
                        ft.FilledButton(
                            "Войти",
                            on_click=lambda e: self.login(
                                login_username.value,
                                login_password.value,
                                login_remember.value,
                            ),
                        ),
                        ft.TextButton("Регистрация", on_click=lambda e: self.toggle_mode("register")),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
            ],
            spacing=10,
            tight=True,
        )

        register_form = ft.Column(
            [
                ft.Text("Регистрация", size=20, weight=ft.FontWeight.BOLD, color=p["text"]),
                reg_username,
                reg_display_name,
                reg_password,
                reg_avatar,
                ft.Row(
                    [
                        ft.FilledButton(
                            "Создать аккаунт",
                            on_click=lambda e: self.register(
                                reg_username.value,
                                reg_password.value,
                                reg_display_name.value,
                                reg_avatar.value,
                            ),
                        ),
                        ft.TextButton("Вход", on_click=lambda e: self.toggle_mode("login")),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
            ],
            spacing=10,
            tight=True,
        )

        form_card = ft.Container(
            expand=1,
            padding=24,
            border_radius=24,
            bgcolor=p["panel_2"],
            border=ft.border.all(1, p["stroke"]),
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.OutlinedButton("Вход", on_click=lambda e: self.toggle_mode("login")),
                            ft.OutlinedButton("Регистрация", on_click=lambda e: self.toggle_mode("register")),
                        ],
                        alignment=ft.MainAxisAlignment.START,
                    ),
                    ft.Container(height=8),
                    login_form if self.state.mode == "login" else register_form,
                    error_box,
                    success_box,
                ],
                spacing=12,
                tight=True,
            ),
        )

        return ft.Container(
            expand=True,
            padding=20,
            content=ft.Row(
                [
                    intro,
                    form_card,
                ],
                spacing=20,
            ),
        )

    def build_message(self, msg: dict[str, Any]) -> ft.Control:
        p = self.palette()
        own = self.state.user and msg["user_id"] == self.state.user["id"]
        bubble_bg = p["bubble_self"] if own else p["bubble_other"]
        text_color = ft.colors.WHITE if own else p["text"]

        header = ft.Row(
            [
                ft.Text(
                    f'{msg["avatar"]} {msg["display_name"]}',
                    size=12,
                    weight=ft.FontWeight.BOLD,
                    color=text_color,
                ),
                ft.Text(msg["time"], size=10, color=text_color),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

        return ft.Container(
            width=520,
            alignment=ft.alignment.center_right if own else ft.alignment.center_left,
            content=ft.Container(
                padding=12,
                border_radius=18,
                bgcolor=bubble_bg,
                border=ft.border.all(1, p["stroke"]),
                content=ft.Column(
                    [
                        header,
                        ft.Container(height=4),
                        ft.Text(msg["text"], color=text_color, selectable=True),
                    ],
                    spacing=0,
                ),
            ),
        )

    def build_chat(self) -> ft.Control:
        p = self.palette()

        sidebar = ft.Container(
            width=230,
            padding=14,
            border_radius=24,
            bgcolor=p["panel"],
            border=ft.border.all(1, p["stroke"]),
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Container(
                                width=44,
                                height=44,
                                border_radius=14,
                                alignment=ft.alignment.center,
                                bgcolor=p["accent"],
                                content=ft.Text("L", color=ft.colors.WHITE, weight=ft.FontWeight.BOLD),
                            ),
                            ft.Column(
                                [
                                    ft.Text(APP_NAME, size=18, weight=ft.FontWeight.BOLD, color=p["text"]),
                                    ft.Text("Lite chat", size=11, color=p["muted"]),
                                ],
                                spacing=0,
                                tight=True,
                            ),
                        ],
                        spacing=12,
                    ),
                    ft.Divider(height=10, color=p["stroke"]),
                    ft.Text("Меню", size=12, color=p["muted"]),
                    ft.TextButton("💬 Чат", on_click=lambda e: None),
                    ft.TextButton("👤 Профиль", on_click=lambda e: self.open_profile()),
                    ft.TextButton("🎨 Тема", on_click=lambda e: self.open_theme_menu()),
                    ft.TextButton("🚪 Выйти", on_click=lambda e: self.logout()),
                    ft.Divider(height=10, color=p["stroke"]),
                    ft.Text("Онлайн", size=12, color=p["muted"]),
                    *[
                        ft.Container(
                            padding=8,
                            border_radius=12,
                            bgcolor=p["panel_2"],
                            content=ft.Row(
                                [
                                    ft.Text(u["avatar"], size=14),
                                    ft.Column(
                                        [
                                            ft.Text(u["display_name"], color=p["text"], size=12),
                                            ft.Text(u["username"], color=p["muted"], size=10),
                                        ],
                                        spacing=0,
                                        tight=True,
                                    ),
                                ],
                                spacing=8,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                        )
                        for u in ONLINE_USERS.values()
                    ],
                ],
                spacing=8,
                scroll=ft.ScrollMode.AUTO,
            ),
        )

        self.state.message_field = ft.TextField(
            hint_text="Напишите сообщение...",
            expand=True,
            on_submit=lambda e: self.send_message(),
        )

        messages_column = ft.Column(
            [
                *[self.build_message(msg) for msg in CHAT_MESSAGES],
            ],
            spacing=10,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )

        emoji_panel = ft.Container(
            visible=self.state.emoji_open,
            padding=8,
            border_radius=14,
            bgcolor=p["panel_2"],
            content=ft.Wrap(
                spacing=6,
                run_spacing=6,
                children=[
                    ft.OutlinedButton(
                        e,
                        width=44,
                        height=36,
                        on_click=lambda ev, emoji=e: self.add_emoji(emoji),
                    )
                    for e in EMOJIS
                ],
            ),
        )

        composer = ft.Container(
            padding=12,
            border_radius=20,
            bgcolor=p["panel"],
            border=ft.border.all(1, p["stroke"]),
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.IconButton(
                                icon=ft.icons.EMOJI_EMOTIONS,
                                tooltip="Эмодзи",
                                on_click=lambda e: self.toggle_emoji_panel(),
                            ),
                            self.state.message_field,
                            ft.FilledButton("Отправить", on_click=lambda e: self.send_message()),
                        ],
                        spacing=10,
                        vertical_alignment=ft.CrossAxisAlignment.END,
                    ),
                    emoji_panel,
                ],
                spacing=10,
                tight=True,
            ),
        )

        chat_area = ft.Container(
            expand=True,
            padding=16,
            border_radius=24,
            bgcolor=p["panel_2"],
            border=ft.border.all(1, p["stroke"]),
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Column(
                                [
                                    ft.Text("Чат", size=20, weight=ft.FontWeight.BOLD, color=p["text"]),
                                    ft.Text("Один общий канал", size=11, color=p["muted"]),
                                ],
                                spacing=0,
                                tight=True,
                            ),
                            ft.TextButton(f"Тема: {self.state.theme}", on_click=lambda e: self.next_theme()),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Divider(height=1, color=p["stroke"]),
                    ft.Container(expand=True, content=messages_column),
                    composer,
                ],
                spacing=12,
                expand=True,
            ),
        )

        right_panel = ft.Container(
            width=230,
            padding=14,
            border_radius=24,
            bgcolor=p["panel"],
            border=ft.border.all(1, p["stroke"]),
            content=ft.Column(
                [
                    ft.Text("Профиль", size=12, color=p["muted"]),
                    ft.Container(
                        padding=12,
                        border_radius=16,
                        bgcolor=p["panel_2"],
                        content=ft.Column(
                            [
                                ft.Text(self.state.profile.get("avatar", "😀") if self.state.profile else "😀", size=26),
                                ft.Text(
                                    self.state.profile.get("display_name", self.state.user["username"]) if self.state.profile else self.state.user["username"],
                                    color=p["text"],
                                    weight=ft.FontWeight.BOLD,
                                ),
                                ft.Text(self.state.user["username"], color=p["muted"], size=11),
                                ft.Text(
                                    f"Role: {self.state.user.get('role', 'user')}",
                                    color=p["muted"],
                                    size=11,
                                ),
                                ft.TextButton("Изменить", on_click=lambda e: self.open_profile()),
                            ],
                            spacing=4,
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                    ),
                    ft.Divider(height=10, color=p["stroke"]),
                    ft.Text("Темы", size=12, color=p["muted"]),
                    ft.Row(
                        [
                            ft.OutlinedButton("Dark", on_click=lambda e: self.set_theme("dark")),
                            ft.OutlinedButton("Purp", on_click=lambda e: self.set_theme("purple")),
                            ft.OutlinedButton("Emer", on_click=lambda e: self.set_theme("emerald")),
                        ],
                        wrap=True,
                    ),
                    ft.Divider(height=10, color=p["stroke"]),
                    ft.Text("Все пользователи", size=12, color=p["muted"]),
                    *[
                        ft.Container(
                            padding=8,
                            border_radius=12,
                            bgcolor=p["panel_2"],
                            content=ft.Row(
                                [
                                    ft.Text((u["avatar"] if u["avatar"] else "😀"), size=14),
                                    ft.Column(
                                        [
                                            ft.Text(u["display_name"] or u["username"], color=p["text"], size=12),
                                            ft.Text(f"@{u['username']}", color=p["muted"], size=10),
                                        ],
                                        spacing=0,
                                        tight=True,
                                    ),
                                ],
                                spacing=8,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                        )
                        for u in list_all_users()
                    ],
                ],
                spacing=8,
                scroll=ft.ScrollMode.AUTO,
            ),
        )

        return ft.Container(
            expand=True,
            padding=16,
            content=ft.Row(
                [
                    sidebar,
                    chat_area,
                    right_panel,
                ],
                spacing=14,
                expand=True,
            ),
        )


def main(page: ft.Page):
    init_db()

    page.title = APP_NAME
    page.padding = 0
    page.spacing = 0
    page.window_min_width = 980
    page.window_min_height = 680
    page.scroll = ft.ScrollMode.AUTO

    app = LogicordApp(page)

    def on_pubsub(data):
        if isinstance(data, dict) and data.get("type") == "refresh":
            app.render()

    page.pubsub.subscribe(on_pubsub)

    app.render()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8550"))
    ft.app(target=main, view=ft.AppView.WEB_BROWSER, host="0.0.0.0", port=port)