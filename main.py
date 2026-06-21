import flet as ft
import json
import os
import hashlib

USERS_FILE = "users.json"

def load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_users(users):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def main(page: ft.Page):
    page.title = "Echoshade"
    page.theme_mode = "dark"
    page.bgcolor = "#0f0f0f"
    page.vertical_alignment = ft.MainAxisAlignment.CENTER
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER

    users = load_users()
    current_username = {"value": None}  # mutable holder for closure

    # ---------- CHAT UI ----------
    def open_chat(username: str):
        page.clean()
        current_username["value"] = username

        header = ft.Row([
            ft.Text(f"Echoshade — {username}", size=20, weight="bold"),
            ft.Spacer(),
            ft.ElevatedButton("Выйти", on_click=lambda e: show_auth())
        ], alignment=ft.MainAxisAlignment.CENTER)

        chat = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True)
        message_input = ft.TextField(hint_text="Напишіть повідомлення...", expand=True)

        def on_message(msg):
            # msg is a plain string sent via pubsub
            chat.controls.append(ft.Text(msg))
            page.update()

        # Подписываемся на pubsub (каждый клиент)
        page.pubsub.subscribe(on_message)

        def send_click(e):
            text = (message_input.value or "").strip()
            if not text:
                return
            sender = current_username["value"] or "Unknown"
            page.pubsub.send_all(f"{sender}: {text}")
            message_input.value = ""
            page.update()

        emoji_row = ft.Row([
            ft.ElevatedButton("😀", on_click=lambda e: (message_input.__setattr__("value", (message_input.value or "") + "😀"), message_input.focus(), page.update())),
            ft.ElevatedButton("🔥", on_click=lambda e: (message_input.__setattr__("value", (message_input.value or "") + "🔥"), message_input.focus(), page.update())),
            ft.ElevatedButton("😂", on_click=lambda e: (message_input.__setattr__("value", (message_input.value or "") + "😂"), message_input.focus(), page.update())),
        ])

        page.add(
            header,
            ft.Divider(),
            chat,
            emoji_row,
            ft.Row([message_input, ft.ElevatedButton("Надіслати", on_click=send_click)], alignment=ft.MainAxisAlignment.CENTER)
        )

    # ---------- AUTH / REGISTER UI ----------
    username_field = ft.TextField(label="Имя пользователя", width=320)
    password_field = ft.TextField(label="Пароль", password=True, can_reveal_password=True, width=320)
    reg_username = ft.TextField(label="Имя пользователя (регистрация)", width=320)
    reg_password = ft.TextField(label="Пароль (регистрация)", password=True, can_reveal_password=True, width=320)
    auth_error = ft.Text("", color="red")
    reg_error = ft.Text("", color="red")
    reg_success = ft.Text("", color="green")

    def do_login(e):
        login = (username_field.value or "").strip()
        pwd = (password_field.value or "").strip()
        if not login or not pwd:
            auth_error.value = "Введите логин и пароль"
            page.update()
            return
        u = users.get(login)
        if not u:
            auth_error.value = "Пользователь не найден"
            page.update()
            return
        if u.get("password_hash") != hash_password(pwd):
            auth_error.value = "Неверный пароль"
            page.update()
            return
        auth_error.value = ""
        page.update()
        open_chat(login)

    def do_register(e):
        login = (reg_username.value or "").strip()
        pwd = (reg_password.value or "").strip()
        if not login or not pwd:
            reg_error.value = "Введите логин и пароль"
            reg_success.value = ""
            page.update()
            return
        if login in users:
            reg_error.value = "Пользователь уже существует"
            reg_success.value = ""
            page.update()
            return
        users[login] = {"password_hash": hash_password(pwd)}
        save_users(users)
        reg_error.value = ""
        reg_success.value = "Регистрация успешна. Теперь войдите."
        reg_username.value = ""
        reg_password.value = ""
        page.update()

    def show_auth():
        page.clean()
        username_field.value = ""
        password_field.value = ""
        auth_error.value = ""
        reg_error.value = ""
        reg_success.value = ""

        auth_card = ft.Container(
            content=ft.Column(
                [
                    ft.Text("Echoshade", size=28, weight="bold"),
                    ft.Text("Вход", size=16),
                    username_field,
                    password_field,
                    ft.Row([ft.ElevatedButton("Войти", on_click=do_login)], alignment=ft.MainAxisAlignment.CENTER),
                    auth_error,
                    ft.Divider(height=20),
                    ft.Text("Регистрация", size=16),
                    reg_username,
                    reg_password,
                    ft.Row([ft.ElevatedButton("Зарегистрироваться", on_click=do_register)], alignment=ft.MainAxisAlignment.CENTER),
                    reg_error,
                    reg_success
                ],
                spacing=10,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER
            ),
            padding=24,
            width=420,
            bgcolor="#181818",
            border_radius=12
        )

        page.add(ft.Column([auth_card], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER))

    # стартовый экран
    show_auth()

if __name__ == "__main__":
    # Render предоставляет PORT в окружении; привязываемся к нему и к 0.0.0.0
    port = int(os.environ.get("PORT", "8550"))
    ft.app(target=main, view=ft.AppView.WEB_BROWSER, host="0.0.0.0", port=port)
