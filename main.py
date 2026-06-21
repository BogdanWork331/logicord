import flet as ft

def main(page: ft.Page):
    page.title = "Echoshade"
    page.theme_mode = "dark"
    page.vertical_alignment = ft.MainAxisAlignment.CENTER
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.bgcolor = "#0f0f0f"

    # ---------------------------
    #  ФУНКЦИЯ: открыть чат
    # ---------------------------
    def open_chat():
        page.clean()

        chat = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True)
        message_input = ft.TextField(hint_text="Напишіть повідомлення...", expand=True)

        def on_message(msg):
            chat.controls.append(ft.Text(msg))
            page.update()

        page.pubsub.subscribe(on_message)

        def send_click(e):
            if message_input.value.strip():
                page.pubsub.send_all(f"Користувач: {message_input.value}")
                message_input.value = ""
                page.update()

        def add_emoji(e):
            message_input.value += e.control.data
            message_input.focus()
            page.update()

        emoji_row = ft.Row([
            ft.ElevatedButton("😀", data="😀", on_click=add_emoji),
            ft.ElevatedButton("🔥", data="🔥", on_click=add_emoji),
            ft.ElevatedButton("😂", data="😂", on_click=add_emoji),
        ])

        page.add(
            chat,
            emoji_row,
            ft.Row([message_input, ft.ElevatedButton("Надіслати", on_click=send_click)])
        )

    # ---------------------------
    #  ЭКРАН АВТОРИЗАЦИИ
    # ---------------------------
    username = ft.TextField(
        label="Имя пользователя",
        width=300,
        bgcolor="#1c1c1c",
        border_color="#3a3a3a"
    )

    password = ft.TextField(
        label="Пароль",
        password=True,
        can_reveal_password=True,
        width=300,
        bgcolor="#1c1c1c",
        border_color="#3a3a3a"
    )

    error_text = ft.Text("", color="red")

    def login_click(e):
        if username.value == "admin" and password.value == "1234":
            open_chat()
        else:
            error_text.value = "Неверный логин или пароль"
            page.update()

    login_box = ft.Container(
        content=ft.Column(
            [
                ft.Text("Echoshade", size=32, weight="bold"),
                username,
                password,
                ft.Row(
                    [
                        ft.ElevatedButton("Войти", on_click=login_click),
                        ft.OutlinedButton("Регистрация")
                    ],
                    alignment=ft.MainAxisAlignment.CENTER
                ),
                error_text
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=15
        ),
        padding=30,
        border_radius=12,
        bgcolor="#181818",
        width=380
    )

    page.add(login_box)


ft.app(target=main, view=ft.AppView.WEB_BROWSER)
