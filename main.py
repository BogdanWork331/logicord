import os
import sqlite3
import hashlib
import flet as ft

# Попытка импортировать bcrypt; если нет — будем использовать sha256 (менее безопасно)
try:
    import bcrypt
    HAS_BCRYPT = True
except Exception:
    HAS_BCRYPT = False

DB_FILE = "users.db"

def init_db():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn

def hash_password(password: str) -> str:
    if HAS_BCRYPT:
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    else:
        return hashlib.sha256(password.encode("utf-8")).hexdigest()

def verify_password(password: str, stored_hash: str) -> bool:
    if HAS_BCRYPT:
        try:
            return bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8"))
        except Exception:
            return False
    else:
        return hashlib.sha256(password.encode("utf-8")).hexdigest() == stored_hash

# Инициализация БД
conn = init_db()
cur = conn.cursor()

def create_user(username: str, password: str) -> tuple[bool, str]:
    username = username.strip()
    if not username or not password:
        return False, "Введите логин и пароль"
    try:
        ph = hash_password(password)
        cur.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", (username, ph))
        conn.commit()
        return True, "OK"
    except sqlite3.IntegrityError:
        return False, "Пользователь уже существует"
    except Exception as e:
        return False, f"Ошибка: {e}"

def find_user(username: str):
    cur.execute("SELECT id, username, password_hash FROM users WHERE username = ?", (username,))
    return cur.fetchone()

# Хранилище онлайн пользователей (в рамках одного процесса)
online_users = set()

def main(page: ft.Page):
    page.title = "Echoshade"
    page.theme_mode = "dark"
    page.bgcolor = "#0f0f0f"
    page.vertical_alignment = ft.MainAxisAlignment.CENTER
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER

    current_user = {"name": None}

    # ---------- CHAT ----------
    def open_chat(username: str):
        page.clean()
        current_user["name"] = username
        online_users.add(username)

        # Header: название + список онлайн + кнопка выйти
        header = ft.Row(
            [
                ft.Text("Echoshade", size=20, weight="bold"),
                ft.Text(f"Онлайн: {', '.join(sorted(online_users))}", size=14),
                ft.Row([], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),  # placeholder для выравнивания
                ft.ElevatedButton("Выйти", on_click=lambda e: do_logout(e, username))
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            width=900
        )

        chat = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True)
        message_input = ft.TextField(hint_text="Напишіть повідомлення...", expand=True)

        def on_message(msg):
            chat.controls.append(ft.Text(msg))
            page.update()

        page.pubsub.subscribe(on_message)

        def send_click(e):
            text = (message_input.value or "").strip()
            if not text:
                return
            sender = current_user["name"] or "Unknown"
            page.pubsub.send_all(f"{sender}: {text}")
            message_input.value = ""
            page.update()

        emoji_row = ft.Row(
            [
                ft.ElevatedButton("😀", on_click=lambda e: (message_input.__setattr__("value", (message_input.value or "") + "😀"), message_input.focus(), page.update())),
                ft.ElevatedButton("🔥", on_click=lambda e: (message_input.__setattr__("value", (message_input.value or "") + "🔥"), message_input.focus(), page.update())),
                ft.ElevatedButton("😂", on_click=lambda e: (message_input.__setattr__("value", (message_input.value or "") + "😂"), message_input.focus(), page.update())),
            ],
            alignment=ft.MainAxisAlignment.CENTER
        )

        page.add(
            ft.Column([header, ft.Divider(), chat, emoji_row, ft.Row([message_input, ft.ElevatedButton("Надіслати", on_click=send_click)], alignment=ft.MainAxisAlignment.CENTER)], width=900)
        )

    def do_logout(e, username):
        try:
            online_users.discard(username)
        except Exception:
            pass
        current_user["name"] = None
        # уведомляем остальных, что пользователь вышел
        page.pubsub.send_all(f"System: {username} вышел(а).")
        show_auth()

    # ---------- AUTH / REGISTER UI ----------
    username_field = ft.TextField(label="Имя пользователя", width=320)
    password_field = ft.TextField(label="Пароль", password=True, can_reveal_password=True, width=320)
    auth_error = ft.Text("", color="red")

    reg_username = ft.TextField(label="Имя пользователя (регистрация)", width=320)
    reg_password = ft.TextField(label="Пароль (регистрация)", password=True, can_reveal_password=True, width=320)
    reg_error = ft.Text("", color="red")
    reg_success = ft.Text("", color="green")

    def do_login(e):
        login = (username_field.value or "").strip()
        pwd = (password_field.value or "").strip()
        if not login or not pwd:
            auth_error.value = "Введите логин и пароль"
            page.update()
            return
        row = find_user(login)
        if not row:
            auth_error.value = "Пользователь не найден"
            page.update()
            return
        _, uname, stored_hash = row
        if not verify_password(pwd, stored_hash):
            auth_error.value = "Неверный пароль"
            page.update()
            return
        auth_error.value = ""
        page.update()
        # уведомляем остальных, что пользователь вошёл
        page.pubsub.send_all(f"System: {login} вошёл(ла).")
        open_chat(login)

    def do_register(e):
        login = (reg_username.value or "").strip()
        pwd = (reg_password.value or "").strip()
        ok, msg = create_user(login, pwd)
        if not ok:
            reg_error.value = msg
            reg_success.value = ""
            page.update()
            return
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

    # старт
    show_auth()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8550"))
    # Render требует 0.0.0.0
    ft.app(target=main, view=ft.AppView.WEB_BROWSER, host="0.0.0.0", port=port)
