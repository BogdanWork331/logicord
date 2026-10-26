from __future__ import annotations

import os
import mimetypes
import urllib.request
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

LANGUAGES = {"ru": "Русский", "uk": "Українська", "en": "English", "fr": "Français"}

# Source strings are the existing UI text; all four translations are kept together
# so changing the language updates the whole interface consistently.
TRANSLATIONS: dict[str, dict[str, str]] = {
    "ЯЗЫК / LANGUAGE": {"ru": "ЯЗЫК", "uk": "МОВА", "en": "LANGUAGE", "fr": "LANGUE"},
    "Роль": {"ru": "Роль", "uk": "Роль", "en": "Role", "fr": "Rôle"},
    "Зберегти файл": {"ru": "Сохранить файл", "uk": "Зберегти файл", "en": "Save file", "fr": "Enregistrer le fichier"},
    "Язык / Language": {"ru": "Язык", "uk": "Мова", "en": "Language", "fr": "Langue"},
    "Введіть логін і пароль": {"ru": "Введите логин и пароль", "uk": "Введіть логін і пароль", "en": "Enter username and password", "fr": "Saisissez le nom d'utilisateur et le mot de passe"},
    "Логін: 3–32 символи, тільки латиница, цифри, _, -, .": {"ru": "Логин: 3–32 символа, латиница, цифры, _, -, .", "uk": "Логін: 3–32 символи, латиниця, цифри, _, -, .", "en": "Username: 3–32 characters; letters, numbers, _, -, .", "fr": "Identifiant : 3–32 caractères, lettres, chiffres, _, -, ."},
    "Успішний вхід": {"ru": "Вы успешно вошли", "uk": "Успішний вхід", "en": "Signed in successfully", "fr": "Connexion réussie"},
    "Аккаунт створено. Тепер увійдіть.": {"ru": "Аккаунт создан. Теперь войдите.", "uk": "Обліковий запис створено. Тепер увійдіть.", "en": "Account created. You can now sign in.", "fr": "Compte créé. Vous pouvez maintenant vous connecter."},
    "Ім'я в чаті": {"ru": "Имя в чате", "uk": "Ім'я в чаті", "en": "Chat display name", "fr": "Nom affiché dans le chat"},
    "Про мене": {"ru": "Обо мне", "uk": "Про мене", "en": "About me", "fr": "À propos de moi"},
    "Аватар": {"ru": "Аватар", "uk": "Аватар", "en": "Avatar", "fr": "Avatar"},
    "Тема": {"ru": "Тема", "uk": "Тема", "en": "Theme", "fr": "Thème"},
    "Профіль": {"ru": "Профиль", "uk": "Профіль", "en": "Profile", "fr": "Profil"},
    "Відміна": {"ru": "Отмена", "uk": "Скасувати", "en": "Cancel", "fr": "Annuler"},
    "Зберегти": {"ru": "Сохранить", "uk": "Зберегти", "en": "Save", "fr": "Enregistrer"},
    "Закрыть": {"ru": "Закрыть", "uk": "Закрити", "en": "Close", "fr": "Fermer"},
    "Профіль оновлено": {"ru": "Профиль обновлён", "uk": "Профіль оновлено", "en": "Profile updated", "fr": "Profil mis à jour"},
    "Наразі нікого немає онлайн": {"ru": "Сейчас никого нет в сети", "uk": "Наразі нікого немає онлайн", "en": "Nobody is online right now", "fr": "Personne n'est en ligne pour le moment"},
    "Користувач": {"ru": "Пользователь", "uk": "Користувач", "en": "User", "fr": "Utilisateur"},
    "У мережі": {"ru": "В сети", "uk": "У мережі", "en": "Online", "fr": "En ligne"},
    "Найкращий чат у MAX, точно!": {"ru": "Лучший чат в MAX, точно!", "uk": "Найкращий чат у MAX, точно!", "en": "The best chat on MAX, for sure!", "fr": "Le meilleur chat sur MAX, c'est sûr !"},
    "Гнучкий інтерфейс": {"ru": "Гибкий интерфейс", "uk": "Гнучкий інтерфейс", "en": "Flexible interface", "fr": "Interface flexible"},
    "Швидка реєстрація": {"ru": "Быстрая регистрация", "uk": "Швидка реєстрація", "en": "Quick registration", "fr": "Inscription rapide"},
    "Багато функцій": {"ru": "Много функций", "uk": "Багато функцій", "en": "Lots of features", "fr": "Nombreuses fonctionnalités"},
    "Гнучкість налаштування": {"ru": "Гибкие настройки", "uk": "Гнучкість налаштування", "en": "Flexible settings", "fr": "Paramètres flexibles"},
    "Темні акцентні теми": {"ru": "Тёмные акцентные темы", "uk": "Темні акцентні теми", "en": "Dark accent themes", "fr": "Thèmes sombres accentués"},
    "ОБЕРІТЬ СВОЮ ТЕМУ": {"ru": "ВЫБЕРИТЕ ТЕМУ", "uk": "ОБЕРІТЬ СВОЮ ТЕМУ", "en": "CHOOSE YOUR THEME", "fr": "CHOISISSEZ VOTRE THÈME"},
    "Логін": {"ru": "Логин", "uk": "Логін", "en": "Username", "fr": "Identifiant"},
    "Пароль": {"ru": "Пароль", "uk": "Пароль", "en": "Password", "fr": "Mot de passe"},
    "Запам'ятати мене": {"ru": "Запомнить меня", "uk": "Запам'ятати мене", "en": "Remember me", "fr": "Se souvenir de moi"},
    "Вхід": {"ru": "Вход", "uk": "Вхід", "en": "Sign in", "fr": "Connexion"},
    "Реєстрація": {"ru": "Регистрация", "uk": "Реєстрація", "en": "Register", "fr": "Inscription"},
    "Увійти": {"ru": "Войти", "uk": "Увійти", "en": "Sign in", "fr": "Se connecter"},
    "Створити обліковий запис": {"ru": "Создать аккаунт", "uk": "Створити обліковий запис", "en": "Create account", "fr": "Créer un compte"},
    "Натисніть, щоб відкрити": {"ru": "Нажмите, чтобы открыть", "uk": "Натисніть, щоб відкрити", "en": "Click to open", "fr": "Cliquez pour ouvrir"},
    "Відео": {"ru": "Видео", "uk": "Відео", "en": "Video", "fr": "Vidéo"},
    "Файл": {"ru": "Файл", "uk": "Файл", "en": "File", "fr": "Fichier"},
    "Простір спілкування": {"ru": "Пространство для общения", "uk": "Простір спілкування", "en": "Your space to chat", "fr": "Votre espace de discussion"},
    "РОБОЧИЙ ПРОСТІР": {"ru": "РАБОЧАЯ ОБЛАСТЬ", "uk": "РОБОЧИЙ ПРОСТІР", "en": "WORKSPACE", "fr": "ESPACE DE TRAVAIL"},
    "Загальний чат": {"ru": "Общий чат", "uk": "Загальний чат", "en": "General chat", "fr": "Chat général"},
    "Ви вже перебуваєте в загальному чаті": {"ru": "Вы уже находитесь в общем чате", "uk": "Ви вже перебуваєте в загальному чаті", "en": "You're already in the general chat", "fr": "Vous êtes déjà dans le chat général"},
    "НАЛАШТУВАННЯ": {"ru": "НАСТРОЙКИ", "uk": "НАЛАШТУВАННЯ", "en": "SETTINGS", "fr": "PARAMÈTRES"},
    "👤  Профіль": {"ru": "👤  Профиль", "uk": "👤  Профіль", "en": "👤  Profile", "fr": "👤  Profil"},
    "🎨  Змінити тему": {"ru": "🎨  Сменить тему", "uk": "🎨  Змінити тему", "en": "🎨  Change theme", "fr": "🎨  Changer de thème"},
    "УЧАСНИКИ ОНЛАЙН": {"ru": "УЧАСТНИКИ В СЕТИ", "uk": "УЧАСНИКИ ОНЛАЙН", "en": "ONLINE MEMBERS", "fr": "MEMBRES EN LIGNE"},
    "🚪  Вийти з акаунта": {"ru": "🚪  Выйти из аккаунта", "uk": "🚪  Вийти з акаунта", "en": "🚪  Log out", "fr": "🚪  Déconnexion"},
    "Напишіть повідомлення…": {"ru": "Напишите сообщение…", "uk": "Напишіть повідомлення…", "en": "Write a message…", "fr": "Écrire un message…"},
    "Додати файл": {"ru": "Прикрепить файл", "uk": "Додати файл", "en": "Attach file", "fr": "Joindre un fichier"},
    "Емодзі": {"ru": "Эмодзи", "uk": "Емодзі", "en": "Emoji", "fr": "Emoji"},
    "Надіслати": {"ru": "Отправить", "uk": "Надіслати", "en": "Send", "fr": "Envoyer"},
    "Спілкуйтеся та діліться файлами": {"ru": "Общайтесь и делитесь файлами", "uk": "Спілкуйтеся та діліться файлами", "en": "Chat and share files", "fr": "Discutez et partagez des fichiers"},
    "ВАШ ПРОФІЛЬ": {"ru": "ВАШ ПРОФИЛЬ", "uk": "ВАШ ПРОФІЛЬ", "en": "YOUR PROFILE", "fr": "VOTRE PROFIL"},
    "Редагувати профіль": {"ru": "Редактировать профиль", "uk": "Редагувати профіль", "en": "Edit profile", "fr": "Modifier le profil"},
    "ШВИДКІ ТЕМИ": {"ru": "БЫСТРЫЕ ТЕМЫ", "uk": "ШВИДКІ ТЕМИ", "en": "QUICK THEMES", "fr": "THÈMES RAPIDES"},
    "ОНЛАЙН ЗАРАЗ": {"ru": "СЕЙЧАС В СЕТИ", "uk": "ОНЛАЙН ЗАРАЗ", "en": "ONLINE NOW", "fr": "EN LIGNE"},
    "Натисніть, щоб завантажити": {"ru": "Нажмите, чтобы скачать", "uk": "Натисніть, щоб завантажити", "en": "Click to download", "fr": "Cliquez pour télécharger"},
    "Виберіть файли": {"ru": "Выберите файлы", "uk": "Виберіть файли", "en": "Choose files", "fr": "Choisir des fichiers"},
    "Файл доступний у повідомленні, але шлях не збережено": {"ru": "Файл доступен в сообщении, но путь не сохранён", "uk": "Файл доступний у повідомленні, але шлях не збережено", "en": "The file is attached, but its path was not saved", "fr": "Le fichier est joint, mais son chemin n'a pas été enregistré"},
    "Зображення завелике (максимум 8 MB)": {"ru": "Изображение слишком большое (максимум 8 МБ)", "uk": "Зображення завелике (максимум 8 MB)", "en": "Image is too large (8 MB maximum)", "fr": "Image trop volumineuse (8 Mo maximum)"},
    "Файл завеликий (максимум 8 MB)": {"ru": "Файл слишком большой (максимум 8 МБ)", "uk": "Файл завеликий (максимум 8 MB)", "en": "File is too large (8 MB maximum)", "fr": "Fichier trop volumineux (8 Mo maximum)"},
    "Дуже багато спроб. Спробуйте через {seconds} сек.": {"ru": "Слишком много попыток. Повторите через {seconds} сек.", "uk": "Дуже багато спроб. Спробуйте через {seconds} сек.", "en": "Too many attempts. Try again in {seconds} seconds.", "fr": "Trop de tentatives. Réessayez dans {seconds} secondes."},
}

AVATARS = ["😀", "😎", "🤖", "👑", "🛡️", "🔥", "🎮", "💎", "🧠", "⚡"]
EMOJIS = [
    "😀", "😎", "😂", "🤣", "😁", "😍",
    "🔥", "❤️", "👍", "👎", "💡", "⚡",
    "🎉", "🎮", "💻", "🚀", "⭐", "🛡️",
]

ONLINE_USERS: dict[int, dict[str, Any]] = {}
# Each open app session is tracked separately so logging out on one device does not
# accidentally mark the same account offline on another device.
ONLINE_SESSIONS: dict[str, dict[str, Any]] = {}


def now_hm() -> str:
    return datetime.now().strftime("%H:%M")


def theme_palette(name: str) -> dict[str, str]:
    return THEMES.get(name, THEMES["dark"])


MAX_ATTACHMENT_BYTES = 8 * 1024 * 1024


def push_message(
    author: dict[str, Any],
    text: str,
    profile: dict[str, Any] | None = None,
    **attachment: Any,
) -> dict[str, Any]:
    return add_message(author["id"], text, **attachment)


@dataclass
class AppState:
    user: dict[str, Any] | None = None
    profile: dict[str, Any] | None = None
    theme: str = "dark"
    language: str = "ru"  # ru is the default language
    mode: str = "login"  # login | register
    error: str = ""
    success: str = ""
    emoji_open: bool = False
    message_field: ft.TextField | None = None


class LogicordApp:
    def __init__(self, page: ft.Page) -> None:
        self.page = page
        self.session_id = str(id(page))
        self.root_control: ft.Control | None = None
        self.state = AppState()
        self.messages_column: ft.ListView | None = None
        self.online_column: ft.Column | None = None
        self.all_online_column: ft.Column | None = None
        self.online_count_label: ft.Text | None = None
        self.profile_name: ft.Text | None = None
        self.profile_avatar: ft.Text | None = None
        self.messages_at_bottom = True
        self.emoji_panel: ft.Container | None = None
        self.composer: ft.Container | None = None
        self.messages_scroll_position = 0.0
        self._scrolling_to_latest = False
        self.file_picker = ft.FilePicker()

    def tr(self, text: str) -> str:
        """Translate a UI string for the currently selected language."""
        return TRANSLATIONS.get(text, {}).get(self.state.language, text)

    def set_language(self, language: str) -> None:
        if language not in LANGUAGES:
            return
        if self.state.language == language:
            return
        self.state.language = language
        self.render()

    def language_picker(self) -> ft.Control:
        """Compact flag-based language selector used on auth and chat screens."""
        return ft.Row(
            [
                self.pill_button(
                    f"{flag} {code}",
                    lambda e, lang=lang: self.set_language(lang),
                    self.state.language == lang,
                )
                for lang, flag, code in [
                    ("ru", "🇷🇺", "RU"),
                    ("uk", "🇺🇦", "UA"),
                    ("en", "🇬🇧", "EN"),
                    ("fr", "🇫🇷", "FR"),
                ]
            ],
            spacing=6,
            wrap=True,
            alignment=ft.MainAxisAlignment.CENTER,
        )

    def palette(self) -> dict[str, str]:
        return theme_palette(self.state.theme)

    def pill_button(self, label: str, on_click, selected: bool = False) -> ft.OutlinedButton:
        """Outlined pill buttons matching the original Logicord auth mockup."""
        p = self.palette()
        return ft.OutlinedButton(
            label,
            on_click=on_click,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=24),
                side=ft.BorderSide(1, p["accent"] if selected else p["muted"]),
                color=p["text"],
                padding=ft.Padding(18, 7, 18, 7),
            ),
        )

    def primary_button(self, label: str, on_click) -> ft.FilledButton:
        p = self.palette()
        return ft.FilledButton(
            label,
            on_click=on_click,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=24),
                padding=ft.Padding(20, 10, 20, 10),
                bgcolor=p["accent"],
                color="#FFFFFF",
            ),
        )

    def _rebuild_online_users(self) -> list[dict[str, Any]]:
        """Rebuild the online list from active sessions in this server process."""
        ONLINE_USERS.clear()
        for user in ONLINE_SESSIONS.values():
            uid = user.get("id")
            if uid is not None:
                ONLINE_USERS[uid] = dict(user)
        return list(ONLINE_USERS.values())

    def _broadcast_presence(self) -> None:
        users = self._rebuild_online_users()
        try:
            self.page.pubsub.send_all({"type": "presence", "users": users})
        except Exception:
            # The page can already be disconnecting; local state is still updated.
            pass

    def disconnect(self) -> None:
        """Clean up presence when a browser tab/session disconnects."""
        ONLINE_SESSIONS.pop(self.session_id, None)
        self._broadcast_presence()

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
                if was_at_bottom:
                    self.scroll_to_latest(force=True)
                else:
                    self.messages_column.scroll_to(offset=scroll_position)
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
            self.state.error = self.tr("Введіть логін і пароль")
            self.render()
            return

        if not is_valid_username(username):
            self.state.error = self.tr("Логін: 3–32 символи, тільки латиница, цифри, _, -, .")
            self.render()
            return

        allowed, retry_after = login_limiter.check(username.lower())
        if not allowed:
            self.state.error = self.tr("Дуже багато спроб. Спробуйте через {seconds} сек.").format(seconds=retry_after)
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

        ONLINE_SESSIONS[self.session_id] = {
            "id": user["id"],
            "username": user["username"],
            "display_name": self.state.profile.get("display_name") or user["username"],
            "avatar": self.state.profile.get("avatar") or "😀",
            "role": user.get("role", "user"),
            "session_id": self.session_id,
        }

        save_settings(user["id"], remember_me=remember)
        self.state.error = ""
        self.state.success = self.tr("Успішний вхід")
        self.apply_theme()
        self.render()
        self._broadcast_presence()

    def register(self, username: str, password: str, display_name: str, avatar: str) -> None:
        username = normalize_username(username)
        display_name = (display_name or "").strip()
        avatar = (avatar or "😀").strip()[:4] or "😀"

        if not username or not password:
            self.state.error = self.tr("Введіть логін і пароль")
            self.render()
            return

        if not is_valid_username(username):
            self.state.error = self.tr("Логін: 3–32 символи, тільки латиница, цифри, _, -, .")
            self.render()
            return

        ok, msg = create_user(username, password, avatar=avatar, display_name=display_name or username)
        if not ok:
            self.state.error = msg
            self.render()
            return

        self.state.error = ""
        self.state.success = self.tr("Аккаунт створено. Тепер увійдіть.")
        self.state.mode = "login"
        self.render()

    def logout(self) -> None:
        ONLINE_SESSIONS.pop(self.session_id, None)
        self.state.user = None
        self.state.profile = None
        self.state.emoji_open = False
        self.state.error = ""
        self.state.success = ""
        self.render()
        self._broadcast_presence()

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

        if self.send_image_url(text):
            self.state.message_field.value = ""
            self.state.message_field.update()
            return

        message = push_message(self.state.user, text, self.state.profile)
        self.state.message_field.value = ""
        self.state.message_field.update()
        self.page.pubsub.send_all({"type": "message", "message": message})

    def _message_kind(self, file_name: str, content_type: str | None = None) -> str:
        mime = content_type or mimetypes.guess_type(file_name)[0] or ""
        if mime.startswith("image/"):
            return "image"
        if mime.startswith("video/"):
            return "video"
        return "file"

    def _send_attachment(self, file_name: str, data: bytes | None, path: str | None = None) -> None:
        if not self.state.user:
            return
        if data and len(data) > MAX_ATTACHMENT_BYTES:
            self.snack(self.tr("Файл завеликий (максимум 8 MB)"))
            return
        kind = self._message_kind(file_name)
        message = push_message(
            self.state.user,
            "",
            self.state.profile,
            kind=kind,
            file_name=file_name,
            file_path=path,
            file_data=data,
        )
        self.page.pubsub.send_all({"type": "message", "message": message})

    async def choose_files(self, e: ft.ControlEvent | None = None) -> None:
        files = await self.file_picker.pick_files(
            dialog_title=self.tr("Виберіть файли"),
            allow_multiple=True,
            with_data=True,
        )
        for file in files or []:
            self._send_attachment(file.name, file.bytes, file.path)

    def send_image_url(self, url: str) -> bool:
        if not url.lower().startswith(("http://", "https://")):
            return False
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "Logicord/1.0"})
            with urllib.request.urlopen(request, timeout=5) as response:
                content_type = response.headers.get_content_type()
                if not content_type.startswith("image/"):
                    return False
                data = response.read(MAX_ATTACHMENT_BYTES + 1)
            if len(data) > MAX_ATTACHMENT_BYTES:
                self.snack(self.tr("Зображення завелике (максимум 8 MB)"))
                return True
        except Exception:
            return False
        name = os.path.basename(url.split("?", 1)[0]) or "image"
        message = push_message(
            self.state.user,
            "",
            self.state.profile,
            kind="image",
            file_name=name,
            file_url=url,
            file_data=data,
        )
        self.page.pubsub.send_all({"type": "message", "message": message})
        return True

    async def open_attachment(self, msg: dict[str, Any]) -> None:
        if msg.get("file_data"):
            target = await self.file_picker.save_file(
                dialog_title=self.tr("Зберегти файл"),
                file_name=msg.get("file_name") or "download",
                src_bytes=msg["file_data"],
            )
            if target and not self.page.web:
                with open(target, "wb") as output:
                    output.write(msg["file_data"])
            return
        target = msg.get("file_url") or msg.get("file_path")
        if not target:
            self.snack(self.tr("Файл доступний у повідомленні, але шлях не збережено"))
            return
        if msg.get("file_url"):
            self.page.launch_url(target)
        elif hasattr(os, "startfile"):
            os.startfile(target)

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
            self.scroll_to_latest()

    def open_profile(self) -> None:
        if not self.state.user:
            return

        profile = self.state.profile or get_profile(self.state.user["id"]) or {}
        display_name_field = ft.TextField(
            label=self.tr("Ім'я в чаті"),
            value=profile.get("display_name") or self.state.user["username"],
            width=320,
        )
        avatar_dd = ft.Dropdown(
            label=self.tr("Аватар"),
            value=profile.get("avatar") or "😀",
            width=320,
            options=[ft.dropdown.Option(a) for a in AVATARS],
        )
        bio_field = ft.TextField(
            label=self.tr("Про мене"),
            value=profile.get("bio") or "",
            multiline=True,
            min_lines=3,
            max_lines=5,
            width=320,
        )
        theme_dd = ft.Dropdown(
            label=self.tr("Тема"),
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
            online_user = ONLINE_SESSIONS.get(self.session_id)
            if online_user:
                online_user.update(
                    display_name=self.state.profile["display_name"],
                    avatar=self.state.profile["avatar"],
                )
            if self.profile_name and self.profile_avatar:
                self.profile_name.value = self.state.profile["display_name"]
                self.profile_avatar.value = self.state.profile["avatar"]
            self._broadcast_presence()
            self.snack(self.tr("Профіль оновлено"))
            dlg.open = False
            self.page.update()

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text(self.tr("Профіль")),
            content=ft.Container(
                width=360,
                content=ft.Column(
                    [display_name_field, avatar_dd, bio_field, theme_dd],
                    tight=True,
                    spacing=10,
                ),
            ),
            actions=[
                ft.TextButton(self.tr("Відміна"), on_click=lambda e: self.close_dialog(dlg)),
                ft.FilledButton(self.tr("Зберегти"), on_click=save),
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
            title=ft.Text(self.tr("Тема")),
            content=ft.Column(
                [
                    self.pill_button("Dark", lambda e: self._choose_theme("dark", dlg), self.state.theme == "dark"),
                    self.pill_button("Purple", lambda e: self._choose_theme("purple", dlg), self.state.theme == "purple"),
                    self.pill_button("Emerald", lambda e: self._choose_theme("emerald", dlg), self.state.theme == "emerald"),
                ],
                tight=True,
            ),
            actions=[ft.TextButton(self.tr("Закрыть"), on_click=lambda e: self.close_dialog(dlg))],
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

    def scroll_to_latest(self, force: bool = False) -> None:
        if not self.messages_column or (not force and not self.messages_at_bottom):
            return
        if not self.messages_column.controls:
            return
        self.messages_at_bottom = True
        self._scrolling_to_latest = True
        self.messages_column.auto_scroll = True
        self.messages_column.scroll_to(
            offset=-1,
            duration=90,
            curve=ft.AnimationCurve.LINEAR,
        )

    def append_message(self, msg: dict[str, Any], force_scroll: bool = False) -> None:
        if not self.messages_column or not self.state.user:
            return

        should_scroll = force_scroll or self.messages_at_bottom
        self.messages_column.controls.append(self.build_message(msg))
        if len(self.messages_column.controls) > 70:
            del self.messages_column.controls[0]
        self.messages_column.auto_scroll = should_scroll
        self.messages_column.update()
        if should_scroll:
            self.scroll_to_latest(force=True)
        else:
            self.messages_column.auto_scroll = False

    def on_messages_scroll(self, event: ft.OnScrollEvent) -> None:
        if self._scrolling_to_latest and event.max_scroll_extent - event.pixels <= 24:
            self._scrolling_to_latest = False
            self.messages_at_bottom = True
            self.messages_scroll_position = event.pixels
            self.messages_column.auto_scroll = True
            return
        self.messages_scroll_position = event.pixels
        self.messages_at_bottom = (
            event.max_scroll_extent - event.pixels <= 24
        )
        self.messages_column.auto_scroll = self.messages_at_bottom

    def refresh_online_users(self, users: list[dict[str, Any]]) -> None:
        users = sorted(users, key=lambda u: (u.get("display_name") or u.get("username", "")).lower())
        online_controls = (
            [self.build_online_user(user) for user in users]
            if users else [ft.Container(
                padding=12,
                content=ft.Text(self.tr("Наразі нікого немає онлайн"), color=self.palette()["muted"], size=11),
            )]
        )
        if self.online_column:
            self.online_column.controls = online_controls
            self.online_column.update()
        if self.all_online_column:
            self.all_online_column.controls = [
                self.build_online_user(user) for user in users
            ] if users else [ft.Container(
                padding=12,
                content=ft.Text(self.tr("Наразі нікого немає онлайн"), color=self.palette()["muted"], size=11),
            )]
            self.all_online_column.update()
        if self.online_count_label:
            self.online_count_label.value = str(len(users))
            self.online_count_label.update()

    def build_online_user(self, user: dict[str, Any]) -> ft.Control:
        p = self.palette()
        return ft.Container(
            padding=8,
            border_radius=11,
            bgcolor=p["panel_2"],
            content=ft.Row(
                [
                    ft.Stack(
                        controls=[
                            ft.Container(
                                width=31, height=31, border_radius=16,
                                bgcolor=p["bg"], alignment=ft.Alignment(0, 0),
                                content=ft.Text(user.get("avatar") or "😀", size=16),
                            ),
                            ft.Container(
                                width=8, height=8, border_radius=4,
                                bgcolor="#43D9A3", border=ft.Border.all(1, p["panel_2"]),
                            ),
                        ],
                    ),
                    ft.Column(
                        [
                            ft.Text(user.get("display_name") or user.get("username", self.tr("Користувач")),
                                    color=p["text"], size=11, max_lines=1),
                            ft.Text(self.tr("У мережі"), color="#43D9A3", size=10),
                        ], spacing=1, tight=True, expand=True,
                    ),
                ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER,
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
            self.scroll_to_latest(force=True)
#МЕНЮ АВТОРІЗАЦІІ!!! -----------------------------------------
    def build_auth(self) -> ft.Control:
        p = self.palette()

        # Left branding panel: gradient, glow and compact feature list.
        logo = ft.Container(
            width=78,
            height=78,
            border_radius=23,
            alignment=ft.Alignment(0, 0),
            gradient=ft.LinearGradient(
                begin=ft.Alignment(-1, -1),
                end=ft.Alignment(1, 1),
                colors=[p["accent"], "#6255F5", "#3930A8"],
            ),
            shadow=ft.BoxShadow(
                blur_radius=26,
                spread_radius=1,
                color=p["accent"],
                offset=ft.Offset(0, 0),
            ),
            content=ft.Text("LoGi", size=27, weight=ft.FontWeight.BOLD, color="#FFFFFF"),
        )
        title = ft.Column(
            [
                logo,
                ft.Text(APP_NAME, size=31, weight=ft.FontWeight.BOLD, color=p["text"]),
                ft.Text(
                    self.tr("Найкращий чат у MAX, точно!"),
                    size=13,
                    color=p["muted"],
                    text_align=ft.TextAlign.CENTER,
                ),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=11,
            tight=True,
        )

        features = [
            (ft.Icons.BOLT, self.tr("Гнучкий інтерфейс")),
            (ft.Icons.SHIELD_OUTLINED, self.tr("Швидка реєстрація")),
            (ft.Icons.PALETTE_OUTLINED, self.tr("Багато функцій")),
            (ft.Icons.TUNE, self.tr("Гнучкість налаштування")),
            (ft.Icons.AUTO_AWESOME, self.tr("Темні акцентні теми")),
        ]
        feature_rows = []
        for icon, label in features:
            feature_rows.append(
                ft.Row(
                    [
                        ft.Container(
                            width=36,
                            height=36,
                            border_radius=12,
                            bgcolor=p["panel_2"],
                            border=ft.Border.all(1, p["stroke"]),
                            alignment=ft.Alignment(0, 0),
                            content=ft.Icon(icon, size=19, color=p["accent"]),
                        ),
                        ft.Text(label, size=13, color=p["text"], weight=ft.FontWeight.W_500),
                    ],
                    spacing=11,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                )
            )

        intro = ft.Container(
            expand=1,
            padding=30,
            border_radius=24,
            gradient=ft.LinearGradient(
                begin=ft.Alignment(-1, -1),
                end=ft.Alignment(1, 1),
                colors=[p["panel"], p["bg"], p["panel_2"]],
            ),
            border=ft.Border.all(1, p["stroke"]),
            content=ft.Column(
                [
                    title,
                    ft.Container(height=14),
                    ft.Column(feature_rows, spacing=11, tight=True),
                    ft.Container(height=10),
                    ft.Text(self.tr("ЯЗЫК / LANGUAGE") if self.state.language == "ru" else self.tr("ЯЗЫК / LANGUAGE"), size=10, color=p["muted"], weight=ft.FontWeight.BOLD),
                    self.language_picker(),
                    ft.Container(height=10),
                    ft.Text(self.tr("ОБЕРІТЬ СВОЮ ТЕМУ"), size=10, color=p["muted"], weight=ft.FontWeight.BOLD),
                    ft.Row(
                        [
                            self.pill_button("Dark", lambda e: self.set_theme("dark"), self.state.theme == "dark"),
                            self.pill_button("Purple", lambda e: self.set_theme("purple"), self.state.theme == "purple"),
                            self.pill_button("Emerald", lambda e: self.set_theme("emerald"), self.state.theme == "emerald"),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=8,
                        wrap=True,
                    ),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=7,
                scroll=ft.ScrollMode.AUTO,
            ),
        )

        # Authentication controls intentionally keep the original workflow and layout.
        login_username = ft.TextField(label=self.tr("Логін"), width=320, prefix_icon=ft.Icons.PERSON_OUTLINE, on_submit=lambda e: self.login(login_username.value, login_password.value, login_remember.value))
        login_password = ft.TextField(
            label=self.tr("Пароль"), width=320, password=True,
            can_reveal_password=True, prefix_icon=ft.Icons.LOCK_OUTLINE,
            on_submit=lambda e: self.login(login_username.value, login_password.value, login_remember.value),
        )
        login_remember = ft.Checkbox(label=self.tr("Запам'ятати мене"), value=True)

        reg_username = ft.TextField(label=self.tr("Логін"), width=320, prefix_icon=ft.Icons.PERSON_OUTLINE, on_submit=lambda e: self.register(reg_username.value, reg_password.value, reg_display_name.value, reg_avatar.value))
        reg_display_name = ft.TextField(label=self.tr("Ім'я в чаті"), width=320, prefix_icon=ft.Icons.BADGE_OUTLINED)
        reg_password = ft.TextField(
            label=self.tr("Пароль"), width=320, password=True,
            can_reveal_password=True, prefix_icon=ft.Icons.LOCK_OUTLINE,
            on_submit=lambda e: self.register(
                reg_username.value, reg_password.value,
                reg_display_name.value, reg_avatar.value,
            ),
        )
        reg_avatar = ft.Dropdown(
            label=self.tr("Аватар"), width=320, value="😀",
            options=[ft.dropdown.Option(a) for a in AVATARS],
        )

        error_box = ft.Container(
            visible=bool(self.state.error), padding=10, border_radius=12,
            bgcolor=p["panel"], border=ft.Border.all(1, p["danger"]),
            content=ft.Text(self.state.error, color=p["danger"], size=12),
        )
        success_box = ft.Container(
            visible=bool(self.state.success), padding=10, border_radius=12,
            bgcolor=p["panel"], border=ft.Border.all(1, p["accent"]),
            content=ft.Text(self.state.success, color=p["accent"], size=12),
        )

        login_form = ft.Column(
            [
                ft.Text(self.tr("Вхід"), size=20, weight=ft.FontWeight.BOLD, color=p["text"]),
                login_username, login_password, login_remember,
                ft.Row(
                    [
                        self.primary_button(
                            self.tr("Увійти"),
                            lambda e: self.login(
                                login_username.value, login_password.value, login_remember.value
                            ),
                        ),
                        ft.TextButton(self.tr("Реєстрація"), on_click=lambda e: self.toggle_mode("register")),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
            ], spacing=10, tight=True,
        )
        # Registration-only visual refresh. Login UI and all other controls stay unchanged.
        # Compact field styling keeps the registration form balanced inside the existing card.
        for field in (reg_username, reg_display_name, reg_password):
            field.height = 42
            field.text_size = 12
            field.color = p["text"]
            field.cursor_color = p["accent"]
            field.bgcolor = p["panel"]
            field.border_color = p["stroke"]
            field.focused_border_color = p["accent"]
            field.border_width = 1
            field.focused_border_width = 1.5
            field.border_radius = 9
            field.content_padding = ft.Padding(12, 8, 12, 8)
            field.label_style = ft.TextStyle(color=p["muted"], size=12)

        reg_avatar.height = 42
        reg_avatar.text_size = 12
        reg_avatar.color = p["text"]
        reg_avatar.bgcolor = p["panel"]
        reg_avatar.border_color = p["stroke"]
        reg_avatar.focused_border_color = p["accent"]
        reg_avatar.border_width = 1
        reg_avatar.border_radius = 9
        reg_avatar.content_padding = ft.Padding(12, 8, 12, 8)
        reg_avatar.label_style = ft.TextStyle(color=p["muted"], size=12)

        register_form = ft.Column(
            controls=[
                ft.Text(
                    self.tr("Реєстрація"),
                    size=20,
                    weight=ft.FontWeight.BOLD,
                    color=p["text"],
                ),
                ft.Text(
                    self.tr("Простір спілкування"),
                    size=11,
                    color=p["muted"],
                ),
                ft.Container(height=2),
                reg_username,
                reg_display_name,
                reg_password,
                reg_avatar,
                ft.Container(height=2),
                ft.FilledButton(
                    self.tr("Створити обліковий запис"),
                    width=320,
                    height=44,
                    on_click=lambda e: self.register(
                        reg_username.value,
                        reg_password.value,
                        reg_display_name.value,
                        reg_avatar.value,
                    ),
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=9),
                        padding=ft.Padding(16, 10, 16, 10),
                        bgcolor=p["accent"],
                        color="#FFFFFF",
                        overlay_color=p["accent"],
                    ),
                ),
                ft.Container(
                    width=320,
                    padding=ft.Padding(0, 2, 0, 0),
                    alignment=ft.Alignment(0, 0),
                    content=ft.TextButton(
                        self.tr("Вхід"),
                        on_click=lambda e: self.toggle_mode("login"),
                        style=ft.ButtonStyle(
                            color=p["accent"],
                            padding=ft.Padding(8, 3, 8, 3),
                        ),
                    ),
                ),
            ],
            spacing=7,
            tight=True,
            horizontal_alignment=ft.CrossAxisAlignment.START,
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
                            self.pill_button(self.tr("Вхід"), lambda e: self.toggle_mode("login"), self.state.mode == "login"),
                            self.pill_button(self.tr("Реєстрація"), lambda e: self.toggle_mode("register"), self.state.mode == "register"),
                        ],
                        alignment=ft.MainAxisAlignment.START,
                    ),
                    ft.Container(height=8),
                    login_form if self.state.mode == "login" else register_form,
                    error_box,
                    success_box,
                ], spacing=12, tight=True,
            ),
        )

        return ft.Container(
            expand=True,
            padding=12,
            content=ft.Row([intro, form_card], spacing=14, expand=True),
        )

    def build_message(self, msg: dict[str, Any]) -> ft.Control:
        p = self.palette()
        own = bool(self.state.user and msg.get("user_id") == self.state.user["id"])
        bubble_bg = p["bubble_self"] if own else p["bubble_other"]
        text_color = "#FFFFFF" if own else p["text"]
        avatar = msg.get("avatar") or "😀"
        display_name = msg.get("display_name") or msg.get("username") or self.tr("Користувач")

        header = ft.Row(
            [
                ft.Text(display_name, size=12, weight=ft.FontWeight.BOLD, color=text_color),
                ft.Text(msg.get("time", ""), size=10, color=text_color),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            spacing=18,
        )

        kind = msg.get("kind", "text")
        if kind == "image" and (msg.get("file_data") or msg.get("file_url") or msg.get("file_path")):
            body: ft.Control = ft.Image(
                src=msg.get("file_data") or msg.get("file_url") or msg.get("file_path"),
                width=320, height=240, fit=ft.BoxFit.CONTAIN,
                border_radius=12, cache_width=640, cache_height=480,
            )
        elif kind in ("video", "file"):
            async def download_attachment(e: ft.ControlEvent, message: dict[str, Any] = msg) -> None:
                await self.open_attachment(message)

            is_video = kind == "video"
            body = ft.Container(
                padding=12,
                border_radius=12,
                bgcolor=p["panel_2"],
                on_click=download_attachment,
                content=ft.Row(
                    [
                        ft.Container(
                            width=40, height=40, border_radius=11,
                            bgcolor=p["panel"], alignment=ft.Alignment(0, 0),
                            content=ft.Icon(
                                ft.Icons.VIDEO_FILE if is_video else ft.Icons.INSERT_DRIVE_FILE_OUTLINED,
                                color=p["accent"], size=22,
                            ),
                        ),
                        ft.Column(
                            [
                                ft.Text(msg.get("file_name") or (self.tr("Відео") if is_video else self.tr("Файл")),
                                        color=text_color, weight=ft.FontWeight.BOLD, size=12),
                                ft.Text(self.tr("Натисніть, щоб відкрити"), color=p["muted"], size=10),
                            ], spacing=3, tight=True, expand=True,
                        ),
                        ft.Icon(ft.Icons.DOWNLOAD_OUTLINED, color=p["muted"], size=18),
                    ], spacing=10,
                ),
            )
        else:
            body = ft.Text(msg.get("text", ""), color=text_color, size=13, selectable=True)

        bubble = ft.Container(
            padding=13,
            border_radius=ft.BorderRadius(18, 18, 5 if own else 18, 18),
            bgcolor=bubble_bg,
            border=ft.Border.all(1, p["stroke"]),
            content=ft.Column([header, ft.Container(height=5), body], spacing=0, tight=True),
        )
        return ft.Container(
            key=f"message-{msg.get('id', id(msg))}",
            alignment=ft.Alignment(1, 0) if own else ft.Alignment(-1, 0),
            padding=ft.Padding(6, 2, 6, 2),
            content=ft.Row(
                [
                    *([] if own else [
                        ft.Container(
                            width=34, height=34, border_radius=17,
                            bgcolor=p["panel"], alignment=ft.Alignment(0, 0),
                            content=ft.Text(avatar, size=17),
                        )
                    ]),
                    ft.Container(content=bubble, width=520),
                    *([] if not own else [
                        ft.Container(
                            width=34, height=34, border_radius=17,
                            bgcolor=p["panel"], alignment=ft.Alignment(0, 0),
                            content=ft.Text(avatar, size=17),
                        )
                    ]),
                ],
                alignment=ft.MainAxisAlignment.END if own else ft.MainAxisAlignment.START,
                vertical_alignment=ft.CrossAxisAlignment.START,
                spacing=8,
            ),
        )

    def build_chat(self) -> ft.Control:
        p = self.palette()

        self.online_column = ft.Column(
            [self.build_online_user(user) for user in ONLINE_USERS.values()] or [
                ft.Container(padding=12, content=ft.Text(self.tr("Наразі нікого немає онлайн"), color=p["muted"], size=11))
            ],
            spacing=7,
            scroll=ft.ScrollMode.AUTO,
        )

        brand = ft.Row(
            [
                ft.Container(
                    width=43, height=43, border_radius=14,
                    alignment=ft.Alignment(0, 0),
                    gradient=ft.LinearGradient(
                        begin=ft.Alignment(-1, -1), end=ft.Alignment(1, 1),
                        colors=[p["accent"], "#5146E5"],
                    ),
                    content=ft.Text("L", color="white", size=22, weight=ft.FontWeight.BOLD),
                ),
                ft.Column(
                    [
                        ft.Text(APP_NAME, size=17, weight=ft.FontWeight.BOLD, color=p["text"]),
                        ft.Row(
                            [ft.Container(width=7, height=7, border_radius=4, bgcolor="#43D9A3"),
                             ft.Text(self.tr("Простір спілкування"), size=10, color=p["muted"])],
                            spacing=5,
                        ),
                    ], spacing=2, tight=True, expand=True,
                ),
            ], spacing=10,
        )

        self.online_count_label = ft.Text(str(len(ONLINE_USERS)), size=10, color=p["accent"])
        sidebar = ft.Container(
            width=224, padding=14, border_radius=22,
            bgcolor=p["panel"], border=ft.Border.all(1, p["stroke"]),
            content=ft.Column(
                [
                    brand,
                    ft.Container(height=8),
                    ft.Divider(height=1, color=p["stroke"]),
                    ft.Text(self.tr("РОБОЧИЙ ПРОСТІР"), size=10, color=p["muted"], weight=ft.FontWeight.BOLD),
                    ft.Container(
                        padding=ft.Padding(11, 9, 11, 9), border_radius=12,
                        bgcolor=p["panel_2"],
                        on_click=lambda e: self.snack(self.tr("Ви вже перебуваєте в загальному чаті")),
                        ink=True,
                        content=ft.Row(
                            [ft.Icon(ft.Icons.CHAT_BUBBLE_OUTLINE, color=p["accent"], size=19),
                             ft.Text(self.tr("Загальний чат"), color=p["text"], size=13, weight=ft.FontWeight.W_500),
                             ft.Container(expand=True),
                             ft.Icon(ft.Icons.CHEVRON_RIGHT, color=p["muted"], size=17)], spacing=8,
                        ),
                    ),
                    ft.Text(self.tr("Язык / Language"), size=10, color=p["muted"], weight=ft.FontWeight.BOLD),
                    self.language_picker(),
                    ft.Text(self.tr("НАЛАШТУВАННЯ"), size=10, color=p["muted"], weight=ft.FontWeight.BOLD),
                    ft.TextButton(self.tr("👤  Профіль"), on_click=lambda e: self.open_profile(), style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12), padding=ft.Padding(12, 8, 12, 8))),
                    ft.TextButton(self.tr("🎨  Змінити тему"), on_click=lambda e: self.open_theme_menu(), style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12), padding=ft.Padding(12, 8, 12, 8))),
                    ft.Divider(height=1, color=p["stroke"]),
                    ft.Row(
                        [ft.Text(self.tr("УЧАСНИКИ ОНЛАЙН"), size=10, color=p["muted"], weight=ft.FontWeight.BOLD),
                         ft.Container(expand=True),
                         ft.Container(padding=ft.Padding(6, 2, 6, 2), border_radius=8,
                                      bgcolor=p["panel_2"], content=self.online_count_label)],
                    ),
                    ft.Container(expand=True, content=self.online_column),
                    ft.Divider(height=1, color=p["stroke"]),
                    ft.TextButton(self.tr("🚪  Вийти з акаунта"), on_click=lambda e: self.logout(), style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12), padding=ft.Padding(12, 8, 12, 8))),
                ], spacing=8, expand=True,
            ),
        )

        self.state.message_field = ft.TextField(
            hint_text=self.tr("Напишіть повідомлення…"),
            expand=True,
            multiline=True,
            min_lines=1,
            max_lines=4,
            text_size=14,
            border=ft.InputBorder.NONE,
            filled=False,
            content_padding=ft.Padding(8, 10, 8, 10),
            on_submit=lambda e: self.send_message(),
        )
        self.messages_column = ft.ListView(
            controls=[self.build_message(msg) for msg in get_recent_messages(70)],
            spacing=5, scroll=ft.ScrollMode.AUTO, expand=True,
            auto_scroll=False, on_scroll=self.on_messages_scroll,
        )

        self.emoji_panel = ft.Container(
            visible=self.state.emoji_open,
            padding=10, border_radius=14, bgcolor=p["panel_2"],
            border=ft.Border.all(1, p["stroke"]),
            content=ft.Row(
                wrap=True, spacing=6, run_spacing=6,
                controls=[
                    ft.OutlinedButton(e, width=42, height=36,
                                      on_click=lambda ev, emoji=e: self.add_emoji(emoji))
                    for e in EMOJIS
                ],
            ),
        )
        self.composer = ft.Container(
            padding=10, border_radius=18, bgcolor=p["panel"],
            border=ft.Border.all(1, p["stroke"]),
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.IconButton(icon=ft.Icons.ATTACH_FILE, tooltip=self.tr("Додати файл"), on_click=self.choose_files),
                            ft.IconButton(icon=ft.Icons.EMOJI_EMOTIONS_OUTLINED, tooltip=self.tr("Емодзі"),
                                          on_click=lambda e: self.toggle_emoji_panel()),
                            self.state.message_field,
                            ft.Container(
                                border_radius=13, bgcolor=p["accent"],
                                content=ft.IconButton(
                                    icon=ft.Icons.SEND_ROUNDED, icon_color="#FFFFFF",
                                    tooltip=self.tr("Надіслати"), on_click=lambda e: self.send_message(),
                                ),
                            ),
                        ], spacing=5, vertical_alignment=ft.CrossAxisAlignment.END,
                    ),
                    self.emoji_panel,
                ], spacing=8, tight=True,
            ),
        )

        chat_area = ft.Container(
            expand=True, padding=16, border_radius=22,
            bgcolor=p["panel_2"], border=ft.Border.all(1, p["stroke"]),
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Container(
                                width=42, height=42, border_radius=14,
                                bgcolor=p["panel"], alignment=ft.Alignment(0, 0),
                                content=ft.Icon(ft.Icons.FORUM_OUTLINED, color=p["accent"], size=21),
                            ),
                            ft.Column(
                                [
                                    ft.Text(self.tr("Загальний чат"), size=18, weight=ft.FontWeight.BOLD, color=p["text"]),
                                    ft.Text(self.tr("Спілкуйтеся та діліться файлами"), size=11, color=p["muted"]),
                                ], spacing=2, tight=True, expand=True,
                            ),
                            ft.OutlinedButton(
                                f"{self.state.theme.title()}",
                                icon=ft.Icons.PALETTE_OUTLINED,
                                on_click=lambda e: self.open_theme_menu(),
                            ),
                        ], spacing=11,
                    ),
                    ft.Divider(height=1, color=p["stroke"]),
                    ft.Container(expand=True, content=self.messages_column),
                    self.composer,
                ], spacing=12, expand=True,
            ),
        )

        profile = self.state.profile or {}
        self.all_online_column = ft.Column(
            [self.build_online_user(user) for user in ONLINE_USERS.values()] or [
                ft.Container(padding=12, content=ft.Text(self.tr("Наразі нікого немає онлайн"), color=p["muted"], size=11))
            ],
            spacing=7,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )
        right_panel = ft.Container(
            width=220, padding=14, border_radius=22,
            bgcolor=p["panel"], border=ft.Border.all(1, p["stroke"]),
            content=ft.Column(
                [
                    ft.Text(self.tr("ВАШ ПРОФІЛЬ"), size=10, color=p["muted"], weight=ft.FontWeight.BOLD),
                    ft.Container(
                        padding=14, border_radius=17, bgcolor=p["panel_2"],
                        content=ft.Column(
                            [
                                ft.Container(
                                    width=66, height=66, border_radius=33,
                                    bgcolor=p["bg"], alignment=ft.Alignment(0, 0),
                                    border=ft.Border.all(2, p["accent"]),
                                    content=self._profile_avatar_control(),
                                ),
                                self._profile_name_control(),
                                ft.Text("@" + self.state.user["username"], color=p["muted"], size=11),
                                ft.Container(
                                    padding=ft.Padding(8, 4, 8, 4), border_radius=9,
                                    bgcolor=p["panel"],
                                    content=ft.Text(
                                        str(self.state.user.get("role", "user")).upper(),
                                        color=p["accent"], size=10, weight=ft.FontWeight.BOLD,
                                    ),
                                ),
                                ft.OutlinedButton(self.tr("Редагувати профіль"), icon=ft.Icons.EDIT_OUTLINED,
                                                  on_click=lambda e: self.open_profile()),
                            ], spacing=7, horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                    ),
                    ft.Divider(height=1, color=p["stroke"]),
                    ft.Text(self.tr("ШВИДКІ ТЕМИ"), size=10, color=p["muted"], weight=ft.FontWeight.BOLD),
                    ft.Row(
                        [
                            ft.IconButton(icon=ft.Icons.DARK_MODE_OUTLINED, tooltip="Dark",
                                          on_click=lambda e: self.set_theme("dark")),
                            ft.IconButton(icon=ft.Icons.LENS, icon_color="#8175FF", tooltip="Purple",
                                          on_click=lambda e: self.set_theme("purple")),
                            ft.IconButton(icon=ft.Icons.LENS, icon_color="#34D399", tooltip="Emerald",
                                          on_click=lambda e: self.set_theme("emerald")),
                        ], alignment=ft.MainAxisAlignment.SPACE_AROUND,
                    ),
                    ft.Divider(height=1, color=p["stroke"]),
                    ft.Row(
                        [
                            ft.Text(self.tr("ОНЛАЙН ЗАРАЗ"), size=10, color=p["muted"], weight=ft.FontWeight.BOLD),
                            ft.Container(expand=True),
                            ft.Icon(ft.Icons.CIRCLE, size=7, color="#43D9A3"),
                        ],
                    ),
                    ft.Container(expand=True, content=self.all_online_column),
                ], spacing=9, expand=True,
            ),
        )

        return ft.Container(
            expand=True, padding=12,
            content=ft.Row([sidebar, chat_area, right_panel], spacing=12, expand=True),
        )


def main(page: ft.Page):
    init_db()

    page.title = APP_NAME
    page.padding = 0
    page.spacing = 0
    page.window_min_width = 980
    page.window_min_height = 700
    page.bgcolor = "#0B1020"
    page.scroll = None

    app = LogicordApp(page)
    page.services.append(app.file_picker)

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
            ONLINE_USERS.update({user["id"]: user for user in users if user.get("id") is not None})
            app.refresh_online_users(users)

    page.pubsub.subscribe(on_pubsub)
    # Flet invokes this when the browser session disconnects. It prevents stale online badges.
    try:
        page.on_disconnect = lambda e: app.disconnect()
    except Exception:
        pass

    app.render()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8550"))
    ft.run(main, view=ft.AppView.WEB_BROWSER, host="0.0.0.0", port=port)