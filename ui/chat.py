from __future__ import annotations

from datetime import datetime
import flet as ft

from core.config import APP_NAME
from core.database import (
    list_channels,
    list_messages,
    list_pinned_messages,
    list_notifications,
    get_profile,
)
from .components import (
    app_header,
    avatar_circle,
    channel_item,
    empty_state,
    glass_panel,
    section_title,
    status_dot,
    user_item,
    action_icon,
)
from .theme import get_theme_config, get_background_config


def format_time(value: str | None) -> str:
    if not value:
        return ""
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.strftime("%H:%M")
    except Exception:
        return ""


def build_message_bubble(app, msg: dict, is_own: bool) -> ft.Container:
    state = app.state
    cfg = get_theme_config(state.theme)
    author_name = msg.get("display_name") or msg.get("username") or "unknown"
    avatar_b64 = msg.get("avatar_b64")
    online = app.is_user_online(msg.get("author_id"))

    action_buttons = []
    if is_own or app.is_admin:
        action_buttons.append(
            ft.IconButton(
                icon=ft.icons.EDIT_OUTLINED,
                icon_size=16,
                tooltip="Edit",
                on_click=lambda e, m=msg: app.open_edit_dialog(m),
            )
        )
        action_buttons.append(
            ft.IconButton(
                icon=ft.icons.DELETE_OUTLINE,
                icon_size=16,
                tooltip="Delete",
                on_click=lambda e, m=msg: app.delete_message(m["id"]),
            )
        )
    if app.is_admin:
        action_buttons.append(
            ft.IconButton(
                icon=ft.icons.PUSH_PIN_OUTLINED if not msg["pinned"] else ft.icons.PUSH_PIN,
                icon_size=16,
                tooltip="Pin",
                on_click=lambda e, m=msg: app.toggle_pin(m["id"]),
            )
        )

    bubble_bg = cfg["accent"] if is_own else ft.colors.with_opacity(0.10, cfg["text"])
    bubble_text_color = ft.colors.WHITE if is_own else cfg["text"]

    message_box = ft.Container(
        expand=False,
        padding=14,
        border_radius=18,
        bgcolor=bubble_bg,
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Row(
                            [
                                avatar_circle(author_name, avatar_b64, size=36),
                                ft.Column(
                                    [
                                        ft.Row(
                                            [
                                                ft.Text(author_name, size=13, weight=ft.FontWeight.BOLD, color=bubble_text_color),
                                                status_dot(online),
                                            ],
                                            spacing=6,
                                        ),
                                        ft.Text(
                                            f"@{msg.get('username', '')} • {format_time(msg.get('created_at'))}" + (" • edited" if msg.get("edited_at") else ""),
                                            size=10,
                                            color=ft.colors.with_opacity(0.80, bubble_text_color),
                                        ),
                                    ],
                                    spacing=0,
                                    tight=True,
                                ),
                            ],
                            spacing=10,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        ft.Row(action_buttons, spacing=0, tight=True),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.START,
                ),
                ft.Container(height=4),
                ft.Markdown(
                    value=msg["content"],
                    selectable=True,
                ),
            ],
            spacing=2,
            tight=True,
        ),
    )
    return message_box


def build_chat_view(app) -> ft.Control:
    state = app.state
    cfg = get_theme_config(state.theme)
    bg_cfg = get_background_config(state.background)

    channels = list_channels()
    selected_channel = app.current_channel()

    pinned_messages = list_pinned_messages(selected_channel["id"]) if selected_channel else []
    messages = list_messages(selected_channel["id"]) if selected_channel else []

    left_sidebar_items = [
        ft.Container(
            padding=10,
            child=ft.Column(
                [
                    app_header(state.theme),
                    ft.Container(height=4),
                    ft.Text("Channels", size=12, color=cfg["muted"]),
                    ft.Divider(height=1, color=ft.colors.with_opacity(0.08, cfg["text"])),
                ],
                spacing=8,
            ),
        )
    ]

    for ch in channels:
        left_sidebar_items.append(
            channel_item(
                ch["name"],
                selected=(selected_channel and ch["id"] == selected_channel["id"]),
                on_click=lambda e, c_id=ch["id"]: app.select_channel(c_id),
                theme_name=state.theme,
                is_private=bool(ch["is_private"]),
            )
        )

    left_sidebar_items.append(
        ft.Container(
            padding=8,
            content=ft.FilledButton(
                "New channel",
                icon=ft.icons.ADD,
                on_click=lambda e: app.open_create_channel_dialog(),
            ),
        )
    )

    online_users = app.list_online_users()
    user_controls = [
        ft.Row(
            [
                ft.Text("People", size=13, color=cfg["muted"]),
                ft.Text(f"{len(online_users)} online", size=11, color=cfg["muted"]),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )
    ]
    for user in online_users:
        profile = get_profile(user["id"])
        user_controls.append(
            user_item(
                user["username"],
                profile["display_name"] if profile else None,
                online=True,
                theme_name=state.theme,
            )
        )

    notifications = list_notifications(state.user["id"])[:3]
    notifications_box = ft.Column(
        [
            ft.Text("Notifications", size=13, color=cfg["muted"]),
            *[
                ft.Container(
                    padding=10,
                    border_radius=12,
                    bgcolor=ft.colors.with_opacity(0.09, cfg["text"]),
                    content=ft.Column(
                        [
                            ft.Text(n["title"], color=cfg["text"], weight=ft.FontWeight.BOLD, size=12),
                            ft.Text(n["body"], color=cfg["muted"], size=11),
                        ],
                        spacing=2,
                    ),
                )
                for n in notifications
            ],
        ],
        spacing=8,
    )

    left_sidebar = ft.Container(
        width=290,
        padding=12,
        content=ft.Column(
            [
                *left_sidebar_items,
            ],
            spacing=8,
            scroll=ft.ScrollMode.AUTO,
        ),
        bgcolor=ft.colors.with_opacity(0.18, cfg["surface"]),
        border_radius=24,
    )

    pinned_box = ft.Column(
        [
            ft.Text("Pinned", size=13, color=cfg["muted"]),
            *[
                ft.Container(
                    padding=10,
                    border_radius=12,
                    bgcolor=ft.colors.with_opacity(0.10, cfg["text"]),
                    content=ft.Text(
                        f"#{p.get('id')} — {p.get('content')[:80]}",
                        size=11,
                        color=cfg["text"],
                    ),
                )
                for p in pinned_messages
            ],
        ],
        spacing=8,
    )

    messages_list = ft.Column(
        controls=[
            *[
                ft.Container(
                    padding=ft.padding.only(bottom=10),
                    content=ft.Row(
                        [build_message_bubble(app, msg, is_own=(msg["author_id"] == state.user["id"]))],
                        alignment=ft.MainAxisAlignment.START if msg["author_id"] != state.user["id"] else ft.MainAxisAlignment.END,
                    ),
                )
                for msg in messages
            ]
        ],
        spacing=0,
        scroll=ft.ScrollMode.AUTO,
        expand=True,
        auto_scroll=True,
    )

    def send_handler(e):
        app.send_current_message()

    composer = ft.Container(
        padding=12,
        border_radius=20,
        bgcolor=ft.colors.with_opacity(0.12, cfg["text"]),
        content=ft.Row(
            [
                ft.IconButton(
                    icon=ft.icons.ATTACH_FILE,
                    tooltip="Attach file",
                    on_click=lambda e: app.toast("Вложение пока фейковое"),
                ),
                ft.IconButton(
                    icon=ft.icons.EMOJI_EMOTIONS,
                    tooltip="Emoji picker",
                    on_click=lambda e: app.open_emoji_picker(),
                ),
                ft.TextField(
                    hint_text="Write a message...",
                    expand=True,
                    multiline=True,
                    min_lines=1,
                    max_lines=4,
                    autofocus=True,
                    on_submit=send_handler,
                ),
                ft.FilledButton(
                    "Send",
                    icon=ft.icons.SEND,
                    on_click=send_handler,
                ),
            ],
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.END,
        ),
    )

    center_header = ft.Row(
        [
            ft.Column(
                [
                    ft.Text(
                        f"#{selected_channel['name'] if selected_channel else 'general'}",
                        size=20,
                        weight=ft.FontWeight.BOLD,
                        color=cfg["text"],
                    ),
                    ft.Text(
                        f"{APP_NAME} workspace",
                        size=11,
                        color=cfg["muted"],
                    ),
                ],
                spacing=0,
                tight=True,
            ),
            ft.Row(
                [
                    action_icon(ft.icons.SETTINGS_OUTLINED, "Settings", lambda e: app.open_settings_dialog(), theme_name=state.theme),
                    action_icon(ft.icons.SWAP_HORIZ, "Theme", lambda e: app.toggle_theme(), theme_name=state.theme),
                    action_icon(ft.icons.LOGOUT, "Logout", lambda e: app.logout(), theme_name=state.theme),
                ],
                spacing=0,
            ),
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    center_panel = ft.Container(
        expand=True,
        padding=16,
        content=ft.Column(
            [
                center_header,
                ft.Container(height=10),
                glass_panel(pinned_box, theme_name=state.theme, padding=14, radius=20) if pinned_messages else ft.Container(height=0),
                ft.Container(height=8),
                ft.Container(
                    expand=True,
                    border_radius=20,
                    bgcolor=ft.colors.with_opacity(0.12, cfg["surface"]),
                    padding=14,
                    content=messages_list if messages else empty_state(
                        "No messages yet",
                        "Start the conversation in this channel.",
                        theme_name=state.theme,
                    ),
                ),
                composer,
            ],
            spacing=12,
            expand=True,
        ),
    )

    right_sidebar = ft.Container(
        width=290,
        padding=12,
        content=ft.Column(
            [
                glass_panel(
                    ft.Column(user_controls, spacing=2),
                    theme_name=state.theme,
                    padding=14,
                    radius=20,
                ),
                notifications_box,
                ft.Container(height=4),
                ft.Container(
                    padding=14,
                    border_radius=20,
                    bgcolor=ft.colors.with_opacity(0.12, cfg["text"]),
                    content=ft.Column(
                        [
                            ft.Text("Profile", color=cfg["text"], weight=ft.FontWeight.BOLD),
                            ft.Text(state.user["username"], color=cfg["muted"], size=12),
                            ft.Text(f"Role: {state.user.get('role', 'user')}", color=cfg["muted"], size=12),
                            ft.TextButton("Open profile settings", on_click=lambda e: app.open_settings_dialog()),
                        ],
                        spacing=4,
                    ),
                ),
            ],
            spacing=10,
            scroll=ft.ScrollMode.AUTO,
        ),
        bgcolor=ft.colors.with_opacity(0.18, cfg["surface"]),
        border_radius=24,
    )

    shell = ft.Container(
        expand=True,
        gradient=bg_cfg["gradient"],
        padding=16,
        content=ft.Row(
            [
                left_sidebar,
                center_panel,
                right_sidebar,
            ],
            spacing=16,
            expand=True,
        ),
    )
    return shell