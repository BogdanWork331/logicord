from __future__ import annotations

import flet as ft

from core.config import APP_NAME
from .theme import get_theme_config


def glass_panel(content: ft.Control, theme_name: str = "dark", padding: int = 16, radius: int = 22) -> ft.Container:
    cfg = get_theme_config(theme_name)
    return ft.Container(
        content=content,
        padding=padding,
        border_radius=radius,
        bgcolor=ft.colors.with_opacity(0.82, cfg["surface"]),
        border=ft.border.all(1, ft.colors.with_opacity(0.10, cfg["text"])),
    )


def app_badge(theme_name: str = "dark") -> ft.Container:
    cfg = get_theme_config(theme_name)
    return ft.Container(
        width=42,
        height=42,
        alignment=ft.alignment.center,
        border_radius=14,
        bgcolor=cfg["accent"],
        content=ft.Text("L", size=22, weight=ft.FontWeight.BOLD, color=ft.colors.WHITE),
    )


def app_header(theme_name: str = "dark") -> ft.Row:
    cfg = get_theme_config(theme_name)
    return ft.Row(
        [
            app_badge(theme_name),
            ft.Column(
                [
                    ft.Text(APP_NAME, size=18, weight=ft.FontWeight.BOLD, color=cfg["text"]),
                    ft.Text("Modern messenger workspace", size=12, color=cfg["muted"]),
                ],
                spacing=0,
                tight=True,
            ),
        ],
        spacing=12,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )


def section_title(title: str, subtitle: str | None = None, theme_name: str = "dark") -> ft.Column:
    cfg = get_theme_config(theme_name)
    controls = [ft.Text(title, size=18, weight=ft.FontWeight.BOLD, color=cfg["text"])]
    if subtitle:
        controls.append(ft.Text(subtitle, size=12, color=cfg["muted"]))
    return ft.Column(controls, spacing=2)


def status_dot(online: bool) -> ft.Container:
    return ft.Container(
        width=10,
        height=10,
        border_radius=999,
        bgcolor="#22C55E" if online else "#6B7280",
    )


def avatar_circle(
    username: str,
    avatar_b64: str | None = None,
    size: int = 42,
) -> ft.Control:
    initials = (username[:1] or "?").upper()
    if avatar_b64:
        return ft.Container(
            width=size,
            height=size,
            border_radius=999,
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
            content=ft.Image(src_base64=avatar_b64, fit=ft.ImageFit.COVER),
        )

    return ft.Container(
        width=size,
        height=size,
        border_radius=999,
        alignment=ft.alignment.center,
        bgcolor="#6C7DFF",
        content=ft.Text(initials, color=ft.colors.WHITE, weight=ft.FontWeight.BOLD),
    )


def channel_item(
    name: str,
    selected: bool,
    on_click,
    theme_name: str = "dark",
    is_private: bool = False,
) -> ft.Container:
    cfg = get_theme_config(theme_name)
    prefix = "@" if is_private else "#"
    return ft.Container(
        border_radius=14,
        bgcolor=ft.colors.with_opacity(0.16, cfg["accent"]) if selected else None,
        padding=10,
        content=ft.Row(
            [
                ft.Text(prefix, size=16, color=cfg["muted"]),
                ft.Text(name, color=cfg["text"], weight=ft.FontWeight.W_600),
            ],
            spacing=8,
        ),
        on_click=on_click,
    )


def user_item(username: str, display_name: str | None, online: bool, theme_name: str = "dark") -> ft.Container:
    cfg = get_theme_config(theme_name)
    label = display_name or username
    return ft.Container(
        padding=8,
        border_radius=12,
        content=ft.Row(
            [
                status_dot(online),
                ft.Column(
                    [
                        ft.Text(label, color=cfg["text"], weight=ft.FontWeight.W_600),
                        ft.Text(username, color=cfg["muted"], size=11),
                    ],
                    spacing=0,
                    tight=True,
                ),
            ],
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )


def error_text(message: str = "") -> ft.Text:
    return ft.Text(message, color="#FF6B8B", size=12)


def success_text(message: str = "") -> ft.Text:
    return ft.Text(message, color="#4DD4AC", size=12)


def empty_state(title: str, subtitle: str, theme_name: str = "dark") -> ft.Container:
    cfg = get_theme_config(theme_name)
    return ft.Container(
        expand=True,
        alignment=ft.alignment.center,
        content=ft.Column(
            [
                ft.Icon(ft.icons.CHAT_BUBBLE_OUTLINE, size=42, color=cfg["muted"]),
                ft.Text(title, color=cfg["text"], size=18, weight=ft.FontWeight.BOLD),
                ft.Text(subtitle, color=cfg["muted"], size=12),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
        ),
    )


def action_icon(icon, tooltip: str, on_click, theme_name: str = "dark") -> ft.IconButton:
    cfg = get_theme_config(theme_name)
    return ft.IconButton(
        icon=icon,
        icon_color=cfg["text"],
        tooltip=tooltip,
        on_click=on_click,
    )