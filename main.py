from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import flet as ft

from config import APP_NAME, THEMES
from database import (
    add_message,
    authenticate_user,
    create_user,
    get_recent_messages,
    get_profile,
    init_db,
    list_all_users,
    save_settings,  
    upsert_profile,
)
from security import login_limiter, normalize_username, is_valid_username

AVATARS = ["😀", "😎", "🤖", "👑", "🛡️", "🔥", "🎮", "💎", "🧠", "⚡"]
EMOJIS = [
    "😀", "😎", "😂", "🤣", "😁", "😍",
    "🔥", "❤️", "👍", "👎", "💡", "⚡",
    "🎉", "🎮", "💻", "🚀", "⭐", "🛡️",
]

ONLINE_USERS: dict[int, dict[str, Any]] = {}


def now_hm() -> str:
    return datetime.now().strftime("%H:%M")


def theme_palette(name: str) -> dict[str, str]:
    return THEMES.get(name, THEMES["dark"])


def push_message(author: dict[str, Any], text: str, profile: dict[str, Any] | None = None) -> dict[str, Any]:
    profile = profile or {}
    return add_message(author["id"], text)


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
        self.root_control: ft.Control | None = None
        self.state = AppState()
        self.messages_column: ft.ListView | None = None
        self.online_column: ft.Column | None = None
        self.profile_name: ft.Text | None = None
        self.profile_avatar: ft.Text | None = None
        self.messages_at_bottom = True
        self.emoji_panel: ft.Container | None = None
        self.composer: ft.Container | None = None
        self.messages_scroll_position = 0.0

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
        if self.state.user and self.state.profile and self.state.profile.get("theme") != theme:
            upsert_profile(
                self.state.user["id"],
                display_name=self.state.profile["display_name"],
                avatar=self.state.profile["avatar"],
                bio=self.state.profile["bio"],
                theme=theme,
            )
            self.state.profile["theme"] = theme
        self.apply_theme()
        self.refresh_root_for_theme()

    def refresh_root_for_theme(self) -> None:
        if not self.root_control or not self.page.controls:
            self.page.update()
            return

        message_text = self.state.message_field.value if self.state.message_field else ""
        scroll_position = self.messages_scroll_position
        was_at_bottom = self.messages_at_bottom
        emoji_open = self.state.emoji_open

        self.root_control = self.build_chat() if self.state.user else self.build_auth()
        self.page.controls[0] = self.root_control
        self.page.update()

        if self.state.user:
            if self.state.message_field:
                self.state.message_field.value = message_text
                self.state.message_field.update()
            self.messages_at_bottom = was_at_bottom
            if self.messages_column:
                self.messages_column.scroll_to(
                    offset=-1 if was_at_bottom else scroll_position,
                )
            if self.emoji_panel:
                self.emoji_panel.visible = emoji_open
        self.page.update()

    def next_theme(self) -> None:
        order = list(THEMES.keys())
        idx = order.index(self.state.theme)
        self.set_theme(order[(idx + 1) % len(order)])

    def login(self, username: str, password: str, remember: bool) -> None:
        username = normalize_username(username)
        if not username or not password:
            self.state.error = "Введіть логін і пароль"
            self.render()
            return

        if not is_valid_username(username):
            self.state.error = "Логін: 3–32 символи, тільки латиница, цифри, _, -, ."
            self.render()
            return

        allowed, retry_after = login_limiter.check(username.lower())
        if not allowed:
            self.state.error = f"Дуже багато спроб. Спробуйте через {retry_after} сек."
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
        self.state.success = "Успішний вхід"
        self.apply_theme()
        self.render()
        self.page.pubsub.send_all({"type": "presence", "users": list(ONLINE_USERS.values())})

    def register(self, username: str, password: str, display_name: str, avatar: str) -> None:
        username = normalize_username(username)
        display_name = (display_name or "").strip()
        avatar = (avatar or "😀").strip()[:4] or "😀"

        if not username or not password:
            self.state.error = "Введіть логін і пароль"
            self.render()
            return

        if not is_valid_username(username):
            self.state.error = "Логін: 3–32 символи, тільки латиница, цифри, _, -, ."
            self.render()
            return

        ok, msg = create_user(username, password, avatar=avatar, display_name=display_name or username)
        if not ok:
            self.state.error = msg
            self.render()
            return

        self.state.error = ""
        self.state.success = "Аккаунт створено. Тепер увійдіть."
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
        self.page.pubsub.send_all({"type": "presence", "users": list(ONLINE_USERS.values())})

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

        message = push_message(self.state.user, text, self.state.profile)
        self.state.message_field.value = ""
        self.page.pubsub.send_all({"type": "message", "message": message})

    def add_emoji(self, emoji: str) -> None:
        if not self.state.message_field:
            return
        self.state.message_field.value = (self.state.message_field.value or "") + emoji
        self.page.update()

    def toggle_emoji_panel(self) -> None:
        self.state.emoji_open = not self.state.emoji_open
        if not self.emoji_panel:
            return

        was_at_bottom = self.messages_at_bottom
        self.emoji_panel.visible = self.state.emoji_open
        self.emoji_panel.update()
        if self.composer:
            self.composer.update()
        self.page.update()
        if was_at_bottom and self.messages_column:
            self.messages_column.scroll_to(offset=-1, duration=120)

    def open_profile(self) -> None:
        if not self.state.user:
            return

        profile = self.state.profile or get_profile(self.state.user["id"]) or {}
        display_name_field = ft.TextField(
            label="Ім'я в чаті",
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
            label="Про мене",
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
            self.state.profile = {
                **(self.state.profile or {}),
                "display_name": (display_name_field.value or "").strip() or self.state.user["username"],
                "avatar": (avatar_dd.value or "😀").strip()[:4] or "😀",
                "bio": (bio_field.value or "").strip(),
                "theme": theme_dd.value,
            }
            self.set_theme(theme_dd.value)
            online_user = ONLINE_USERS.get(self.state.user["id"])
            if online_user:
                online_user.update(
                    display_name=self.state.profile["display_name"],
                    avatar=self.state.profile["avatar"],
                )
            if self.profile_name and self.profile_avatar:
                self.profile_name.value = self.state.profile["display_name"]
                self.profile_avatar.value = self.state.profile["avatar"]
            self.refresh_online_users(list(ONLINE_USERS.values()))
            self.page.pubsub.send_all({"type": "presence", "users": list(ONLINE_USERS.values())})
            self.snack("Профіль оновлено")
            dlg.open = False
            self.page.update()

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Профіль"),
            content=ft.Container(
                width=360,
                content=ft.Column(
                    [display_name_field, avatar_dd, bio_field, theme_dd],
                    tight=True,
                    spacing=10,
                ),
            ),
            actions=[
                ft.TextButton("Відміна", on_click=lambda e: self.close_dialog(dlg)),
                ft.FilledButton("Зберегти", on_click=save),
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

    def _profile_avatar_control(self) -> ft.Text:
        self.profile_avatar = ft.Text(
            self.state.profile.get("avatar", "😀") if self.state.profile else "😀",
            size=26,
        )
        return self.profile_avatar

    def _profile_name_control(self) -> ft.Text:
        p = self.palette()
        self.profile_name = ft.Text(
            self.state.profile.get("display_name", self.state.user["username"])
            if self.state.profile else self.state.user["username"],
            color=p["text"],
            weight=ft.FontWeight.BOLD,
        )
        return self.profile_name

    def append_message(self, msg: dict[str, Any], force_scroll: bool = False) -> None:
        if not self.messages_column or not self.state.user:
            return

        should_scroll = force_scroll or self.messages_at_bottom
        self.messages_column.controls.append(self.build_message(msg))
        if len(self.messages_column.controls) > 70:
            del self.messages_column.controls[0]
        self.messages_column.update()
        self.page.update()
        if should_scroll:
            self.messages_at_bottom = True
            self.messages_column.scroll_to(
                offset=-1,
                duration=180,
                curve=ft.AnimationCurve.EASE_OUT,
            )

    def on_messages_scroll(self, event: ft.OnScrollEvent) -> None:
        self.messages_scroll_position = event.pixels
        self.messages_at_bottom = (
            event.max_scroll_extent - event.pixels <= 24
        )

    def refresh_online_users(self, users: list[dict[str, Any]]) -> None:
        if not self.online_column:
            return
        self.online_column.controls = [self.build_online_user(user) for user in users]
        self.online_column.update()

    def build_online_user(self, user: dict[str, Any]) -> ft.Control:
        p = self.palette()
        return ft.Container(
            padding=8,
            bgcolor=p["panel_2"],
            content=ft.Row(
                [
                    ft.Text(user["avatar"], size=14),
                    ft.Column(
                        [
                            ft.Text(user["display_name"], color=p["text"], size=12),
                            ft.Text(user["username"], color=p["muted"], size=10),
                        ],
                        spacing=0,
                        tight=True,
                    ),
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )

    def render(self) -> None:
        self.apply_theme()
        self.page.clean()

        if self.state.user:
            self.root_control = self.build_chat()
        else:
            self.root_control = self.build_auth()

        self.page.add(self.root_control)

        self.page.update()
        if self.state.user and self.messages_column:
            self.messages_column.scroll_to(offset=-1)
#МЕНЮ АВТОРІЗАЦІІ!!! -----------------------------------------
    def build_auth(self) -> ft.Control:
        p = self.palette()

        title = ft.Column(
            [
                ft.Container(
                    width=72,
                    height=72,
                    border_radius=20,
                    alignment=ft.Alignment(0, 0),
                    bgcolor=p["accent"],
                    content=ft.Text("LoGi", size=30, weight=ft.FontWeight.BOLD, color="white"),
                ),
                ft.Text(APP_NAME, size=30, weight=ft.FontWeight.BOLD, color=p["text"]),
                ft.Text("Найкращий чат(кращий ніж у MAX точно)", size=13, color=p["muted"]),
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
                    ft.Text("• Гнучкий інтерфейс", color=p["text"]),
                    ft.Text("• Швидка реєстрація", color=p["text"]),
                    ft.Text("• Багато функцій", color=p["text"]),
                    ft.Text("• Гнучкість налаштування", color=p["text"]),
                    ft.Text("• Темні акцентні теми", color=p["text"]),
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

        login_username = ft.TextField(label="Логін", width=320)
        login_password = ft.TextField(label="Пароль", width=320, password=True, can_reveal_password=True)
        login_remember = ft.Checkbox(label="Запам'ятати мене", value=True)

        reg_username = ft.TextField(label="Логін", width=320)
        reg_display_name = ft.TextField(label="Ім'я в чаті", width=320)
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
            bgcolor=p["panel"],
            border=ft.Border.all(1, p["danger"]),
            content=ft.Text(self.state.error, color=p["danger"], size=12),
        )

        success_box = ft.Container(
            visible=bool(self.state.success),
            padding=10,
            border_radius=12,
            bgcolor=p["panel"],
            border=ft.Border.all(1, p["accent"]),
            content=ft.Text(self.state.success, color=p["accent"], size=12),
        )

        login_form = ft.Column(
            [
                ft.Text("Вхід", size=20, weight=ft.FontWeight.BOLD, color=p["text"]),
                login_username,
                login_password,
                login_remember,
                ft.Row(
                    [
                        ft.FilledButton(
                            "Ввійти",
                            on_click=lambda e: self.login(
                                login_username.value,
                                login_password.value,
                                login_remember.value,
                            ),
                        ),
                        ft.TextButton("Реєстрація", on_click=lambda e: self.toggle_mode("register")),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
            ],
            spacing=10,
            tight=True,
        )

        register_form = ft.Column(
            [
                ft.Text("Реєстрація", size=20, weight=ft.FontWeight.BOLD, color=p["text"]),
                reg_username,
                reg_display_name,
                reg_password,
                reg_avatar,
                ft.Row(
                    [
                        ft.FilledButton(
                            "Створити обліковий запис",
                            on_click=lambda e: self.register(
                                reg_username.value,
                                reg_password.value,
                                reg_display_name.value,
                                reg_avatar.value,
                            ),
                        ),
                        ft.TextButton("Вхід", on_click=lambda e: self.toggle_mode("login")),
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
            border=ft.Border.all(1, p["stroke"]),
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.OutlinedButton("Вхід", on_click=lambda e: self.toggle_mode("login")),
                            ft.OutlinedButton("Реєстрація", on_click=lambda e: self.toggle_mode("register")),
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
#МЕНЮ АВТОРІЗАЦІІ!!! -----------------------------------------

    def build_message(self, msg: dict[str, Any]) -> ft.Control:
        p = self.palette()
        own = self.state.user and msg["user_id"] == self.state.user["id"]
        bubble_bg = p["bubble_self"] if own else p["bubble_other"]
        text_color = "white" if own else p["text"]

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
            alignment=ft.Alignment(1, 0) if own else ft.Alignment(-1, 0),
            content=ft.Container(
                padding=12,
                border_radius=18,
                bgcolor=bubble_bg,
                border=ft.Border.all(1, p["stroke"]),
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

        self.online_column = ft.Column(
            [self.build_online_user(user) for user in ONLINE_USERS.values()],
            spacing=8,
            scroll=ft.ScrollMode.AUTO,
        )

        sidebar = ft.Container(
            width=230,
            padding=14,
            border_radius=24,
            bgcolor=p["panel"],
            border=ft.Border.all(1, p["stroke"]),
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Container(
                                width=44,
                                height=44,
                                border_radius=14,
                                alignment=ft.Alignment(0, 0),
                                bgcolor=p["accent"],
                                content=ft.Text("L", color="white", weight=ft.FontWeight.BOLD),
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
                    ft.TextButton("👤 Профіль", on_click=lambda e: self.open_profile()),
                    ft.TextButton("🎨 Тема", on_click=lambda e: self.open_theme_menu()),
                    ft.TextButton("🚪 Вийти", on_click=lambda e: self.logout()),
                    ft.Divider(height=10, color=p["stroke"]),
                    ft.Text("Онлайн", size=12, color=p["muted"]),
                    self.online_column,
                ],
                spacing=8,
                scroll=ft.ScrollMode.AUTO,
            ),
        )

        self.state.message_field = ft.TextField(
            hint_text="Введіть повідомлення...",
            expand=True,
            on_submit=lambda e: self.send_message(),
        )

        self.messages_column = ft.ListView(
            controls=[self.build_message(msg) for msg in get_recent_messages(70)],
            spacing=10,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            build_controls_on_demand=True,
            on_scroll=self.on_messages_scroll,
        )

        self.emoji_panel = ft.Container(
            visible=self.state.emoji_open,
            padding=8,
            border_radius=14,
            bgcolor=p["panel_2"],
            content=ft.Row(
                wrap=True,
                spacing=6,
                run_spacing=6,
                controls=[
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

        self.composer = ft.Container(
            padding=12,
            border_radius=20,
            bgcolor=p["panel"],
            border=ft.Border.all(1, p["stroke"]),
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.IconButton(
                                icon=ft.Icons.EMOJI_EMOTIONS,
                                tooltip="Эмодзі",
                                on_click=lambda e: self.toggle_emoji_panel(),
                            ),
                            self.state.message_field,
                            ft.FilledButton("Відправити", on_click=lambda e: self.send_message()),
                        ],
                        spacing=10,
                        vertical_alignment=ft.CrossAxisAlignment.END,
                    ),
                    self.emoji_panel,
                ],
                spacing=10,
                tight=True,
            ),
        )

        chat_area = ft.Container(
            height=640,
            expand=True,
            padding=16,
            border_radius=24,
            bgcolor=p["panel_2"],
            border=ft.Border.all(1, p["stroke"]),
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Column(
                                [
                                    ft.Text("Чат", size=20, weight=ft.FontWeight.BOLD, color=p["text"]),
                                    ft.Text("Один загальний канал", size=11, color=p["muted"]),
                                ],
                                spacing=0,
                                tight=True,
                            ),
                            ft.TextButton(f"Тема: {self.state.theme}", on_click=lambda e: self.next_theme()),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Divider(height=1, color=p["stroke"]),
                    ft.Container(expand=True, content=self.messages_column),
                    self.composer,
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
            border=ft.Border.all(1, p["stroke"]),
            content=ft.Column(
                [
                    ft.Text("Профіль", size=12, color=p["muted"]),
                    ft.Container(
                        padding=12,
                        border_radius=16,
                        bgcolor=p["panel_2"],
                        content=ft.Column(
                            [
                                self._profile_avatar_control(),
                                self._profile_name_control(),
                                ft.Text(self.state.user["username"], color=p["muted"], size=11),
                                ft.Text(
                                    f"Role: {self.state.user.get('role', 'user')}",
                                    color=p["muted"],
                                    size=11,
                                ),
                                ft.TextButton("Змінити", on_click=lambda e: self.open_profile()),
                            ],
                            spacing=4,
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                    ),
                    ft.Divider(height=10, color=p["stroke"]),
                    ft.Text("Теми", size=12, color=p["muted"]),
                    ft.Row(
                        [
                            ft.OutlinedButton("Dark", on_click=lambda e: self.set_theme("dark")),
                            ft.OutlinedButton("Purp", on_click=lambda e: self.set_theme("purple")),
                            ft.OutlinedButton("Emer", on_click=lambda e: self.set_theme("emerald")),
                        ],
                        wrap=True,
                    ),
                    ft.Divider(height=10, color=p["stroke"]),
                    ft.Text("Всі користувачі", size=12, color=p["muted"]),
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
    page.scroll = None

    app = LogicordApp(page)

    def on_pubsub(data):
        if not isinstance(data, dict):
            return
        if data.get("type") == "message":
            message = data.get("message") or {}
            own_message = bool(
                app.state.user
                and message.get("user_id") == app.state.user["id"]
            )
            app.append_message(message, force_scroll=own_message)
        elif data.get("type") == "presence":
            users = data.get("users") or []
            ONLINE_USERS.clear()
            ONLINE_USERS.update({user["id"]: user for user in users})
            app.refresh_online_users(users)

    page.pubsub.subscribe(on_pubsub)

    app.render()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8550"))
    ft.app(target=main, view=ft.AppView.WEB_BROWSER, host="0.0.0.0", port=port)