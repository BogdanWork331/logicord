from __future__ import annotations

import flet as ft


THEME_PRESETS = {
    "dark": {
        "seed": "#6C7DFF",
        "page_bg": "#0B1020",
        "surface": "#12192C",
        "surface_2": "#17213A",
        "text": "#F3F6FF",
        "muted": "#AAB3D1",
        "accent": "#7C8CFF",
        "danger": "#FF6B8B",
        "success": "#4DD4AC",
    },
    "light": {
        "seed": "#4F46E5",
        "page_bg": "#EEF2FF",
        "surface": "#FFFFFF",
        "surface_2": "#F4F7FF",
        "text": "#111827",
        "muted": "#6B7280",
        "accent": "#4F46E5",
        "danger": "#E11D48",
        "success": "#059669",
    },
}

BACKGROUND_PRESETS = {
    "aurora": {
        "gradient": ft.LinearGradient(
            begin=ft.Alignment.top_left,
            end=ft.Alignment.bottom_right,
            colors=["#0B1020", "#132749", "#1E3A8A"],
        )
    },
    "midnight": {
        "gradient": ft.LinearGradient(
            begin=ft.Alignment.top_left,
            end=ft.Alignment.bottom_right,
            colors=["#050816", "#10172A", "#1E1B4B"],
        )
    },
    "sunset": {
        "gradient": ft.LinearGradient(
            begin=ft.Alignment.top_left,
            end=ft.Alignment.bottom_right,
            colors=["#1B1B3A", "#4B2E83", "#B5478C"],
        )
    },
    "paper": {
        "gradient": ft.LinearGradient(
            begin=ft.Alignment.top_left,
            end=ft.Alignment.bottom_right,
            colors=["#F8FAFF", "#ECF2FF", "#DEE9FF"],
        )
    },
}


def get_theme_config(theme_name: str) -> dict:
    return THEME_PRESETS.get(theme_name, THEME_PRESETS["dark"])


def get_background_config(background_name: str) -> dict:
    return BACKGROUND_PRESETS.get(background_name, BACKGROUND_PRESETS["aurora"])


def build_page_theme(theme_name: str) -> ft.Theme:
    cfg = get_theme_config(theme_name)
    return ft.Theme(
        color_scheme=ft.ColorScheme(
            primary=cfg["accent"],
            secondary=cfg["accent"],
            surface=cfg["surface"],
            on_surface=cfg["text"],
        ),
        use_material3=True,
    )