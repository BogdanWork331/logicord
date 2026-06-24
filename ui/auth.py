from __future__ import annotations

import flet as ft

from core.config import APP_NAME
from .components import glass_panel, app_header, error_text, success_text
from .theme import get_theme_config, get_background_config


TEXTS = {
    "ru": {
        "login": "Вход",
        "register": "Регистрация",
        "username": "Имя пользователя",
        "password": "Пароль",
        "display_name": "Отображаемое имя",
        "remember": "Запомнить меня",
        "show_password": "Показать пароль",
        "hide_password": "Скрыть пароль",
        "login_btn": "Войти",
        "register_btn": "Создать аккаунт",
        "forgot": "Восстановить пароль",
        "language": "Язык",
        "theme": "Тема",
        "background": "Фон",
        "welcome_title": "Добро пожаловать в Logicord",
        "welcome_subtitle": "Современное пространство для общения, каналов и сообщений.",
        "reset_fake": "Ссылка на восстановление была отправлена (демо).",
    },
    "en": {
        "login": "Sign in",
        "register": "Register",
        "username": "Username",
        "password": "Password",
        "display_name": "Display name",
        "remember": "Remember me",
        "show_password": "Show password",
        "hide_password": "Hide password",
        "login_btn": "Sign in",
        "register_btn": "Create account",
        "forgot": "Reset password",
        "language": "Language",
        "theme": "Theme",
        "background": "Background",
        "welcome_title": "Welcome to Logicord",
        "welcome_subtitle": "A modern space for chat, channels, and profiles.",
        "reset_fake": "A password reset link has been sent (demo).",
    },
    "uk": {
        "login": "Вхід",
        "register": "Реєстрація",
        "username": "Ім'я користувача",
        "password": "Пароль",
        "display_name": "Відображуване ім'я",
        "remember": "Запам'ятати мене",
        "show_password": "Показати пароль",
        "hide_password": "Приховати пароль",
        "login_btn": "Увійти",
        "register_btn": "Створити акаунт",
        "forgot": "Відновити пароль",
        "language": "Мова",
        "theme": "Тема",
        "background": "Фон",
        "welcome_title": "Ласкаво просимо до Logicord",
        "welcome_subtitle": "Сучасний простір для спілкування, каналів і повідомлень.",
        "reset_fake": "Лінк для відновлення було надіслано (демо).",
    },
}


def t(lang: str, key: str) -> str:
    return TEXTS.get(lang, TEXTS["ru"]).get(key, key)


def build_auth_view(app) -> ft.Control:
    state = app.state
    lang = state.language
    theme_name = state.theme
    cfg = get_theme_config(theme_name)
    bg_cfg = get_background_config(state.background)

    login_username = ft.TextField(label=t(lang, "username"), dense=True)
    login_password = ft.TextField(
        label=t(lang, "password"),
        password=True,
        can_reveal_password=True,
        dense=True,
    )
    login_remember = ft.Checkbox(label=t(lang, "remember"), value=bool(state.remember_me))
    login_error = error_text("")
    login_success = success_text("")

    reg_username = ft.TextField(label=t(lang, "username"), dense=True)
    reg_display_name = ft.TextField(label=t(lang, "display_name"), dense=True)
    reg_password = ft.TextField(
        label=t(lang, "password"),
        password=True,
        can_reveal_password=True,
        dense=True,
    )
    reg_error = error_text("")
    reg_success = success_text("")

    language_dd = ft.Dropdown(
        label=t(lang, "language"),
        value=lang,
        options=[
            ft.dropdown.Option("ru", "Русский"),
            ft.dropdown.Option("en", "English"),
            ft.dropdown.Option("uk", "Українська"),
        ],
        dense=True,
        width=180,
        on_change=lambda e: app.set_language(e.control.value, rerender=True),
    )

    theme_dd = ft.Dropdown(
        label=t(lang, "theme"),
        value=theme_name,
        options=[
            ft.dropdown.Option("dark", "Dark"),
            ft.dropdown.Option("light", "Light"),
        ],
        dense=True,
        width=180,
        on_change=lambda e: app.set_theme(e.control.value, rerender=True),
    )

    background_dd = ft.Dropdown(
        label=t(lang, "background"),
        value=state.background,
        options=[
            ft.dropdown.Option("aurora", "Aurora"),
            ft.dropdown.Option("midnight", "Midnight"),
            ft.dropdown.Option("sunset", "Sunset"),
            ft.dropdown.Option("paper", "Paper"),
        ],
        dense=True,
        width=180,
        on_change=lambda e: app.set_background(e.control.value, rerender=True),
    )

    def do_login(e):
        ok, message = app.login(
            login_username.value,
            login_password.value,
            remember=bool(login_remember.value),
        )
        if ok:
            login_error.value = ""
            login_success.value = message
            app.render_chat()
        else:
            login_error.value = message
            login_success.value = ""
        app.page.update()

    def do_register(e):
        ok, message = app.register(
            reg_username.value,
            reg_password.value,
            display_name=reg_display_name.value,
        )
        if ok:
            reg_error.value = ""
            reg_success.value = message
            reg_username.value = ""
            reg_display_name.value = ""
            reg_password.value = ""
        else:
            reg_error.value = message
            reg_success.value = ""
        app.page.update()

    def fake_reset(e):
        app.toast(t(lang, "reset_fake"))

    left_panel = ft.Container(
        expand=1,
        padding=30,
        border_radius=28,
        content=ft.Column(
            [
                ft.Container(
                    expand=True,
                    alignment=ft.alignment.center,
                    content=ft.Column(
                        [
                            ft.Container(
                                width=96,
                                height=96,
                                border_radius=28,
                                alignment=ft.alignment.center,
                                bgcolor=cfg["accent"],
                                content=ft.Text("L", size=44, weight=ft.FontWeight.BOLD, color=ft.colors.WHITE),
                            ),
                            ft.Text(APP_NAME, size=36, weight=ft.FontWeight.BOLD, color=cfg["text"]),
                            ft.Text(
                                t(lang, "welcome_title"),
                                size=18,
                                weight=ft.FontWeight.W_600,
                                color=cfg["text"],
                            ),
                            ft.Text(
                                t(lang, "welcome_subtitle"),
                                size=13,
                                color=cfg["muted"],
                                text_align=ft.TextAlign.CENTER,
                            ),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=16,
                    ),
                ),
            ]
        ),
    )

    login_card = glass_panel(
        ft.Column(
            [
                ft.Text(t(lang, "login"), size=24, weight=ft.FontWeight.BOLD, color=cfg["text"]),
                ft.Text("Logicord account", size=12, color=cfg["muted"]),
                ft.Divider(height=10, color=ft.colors.with_opacity(0.10, cfg["text"])),
                login_username,
                login_password,
                ft.Row([login_remember], alignment=ft.MainAxisAlignment.START),
                ft.Row(
                    [
                        ft.TextButton(t(lang, "forgot"), on_click=fake_reset),
                        ft.FilledButton(t(lang, "login_btn"), on_click=do_login),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                login_error,
                login_success,
            ],
            spacing=10,
            tight=True,
        ),
        theme_name=theme_name,
        padding=18,
        radius=24,
    )

    register_card = glass_panel(
        ft.Column(
            [
                ft.Text(t(lang, "register"), size=22, weight=ft.FontWeight.BOLD, color=cfg["text"]),
                ft.Divider(height=10, color=ft.colors.with_opacity(0.10, cfg["text"])),
                reg_username,
                reg_display_name,
                reg_password,
                ft.FilledButton(t(lang, "register_btn"), on_click=do_register),
                reg_error,
                reg_success,
            ],
            spacing=10,
            tight=True,
        ),
        theme_name=theme_name,
        padding=18,
        radius=24,
    )

    right_panel = ft.Container(
        expand=1.2,
        padding=30,
        content=ft.Column(
            [
                ft.Row([language_dd, theme_dd, background_dd], wrap=True, alignment=ft.MainAxisAlignment.END),
                ft.Container(height=8),
                login_card,
                register_card,
            ],
            spacing=18,
            scroll=ft.ScrollMode.AUTO,
        ),
    )

    page_shell = ft.Container(
        expand=True,
        gradient=bg_cfg["gradient"],
        padding=20,
        content=ft.Row(
            [
                left_panel,
                right_panel,
            ],
            spacing=20,
        ),
    )

    return page_shell