import flet as ft

def main(page: ft.Page):
    page.title = "Logicord"
    page.theme_mode = "dark"
    page.vertical_alignment = ft.MainAxisAlignment.CENTER
    # Текстове поле чату (список повідомлень)
    chat = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True)
    
    # Поле введення тексту
    message_input = ft.TextField(hint_text="Напишіть повідомлення...", expand=True)

    # Функція, яка ловить повідомлення від інших (через PubSub)
    def on_message(msg):
        chat.controls.append(ft.Text(msg))
        page.update()

    page.pubsub.subscribe(on_message)

    # Функція відправки
    def send_click(e):
        if message_input.value.strip():
            # Розсилаємо повідомлення всім, хто відкрив додаток
            page.pubsub.send_all(f"Користувач: {message_input.value}")
            message_input.value = ""
            page.update()

    # Функція додавання емодзі
    def add_emoji(e):
        message_input.value += e.control.content.value
        message_input.focus()
        page.update()

    # Панель з емодзі
    emoji_row = ft.Row([
        ft.ElevatedButton(content = ft.Text("😀"), on_click=add_emoji),
        ft.ElevatedButton(content = ft.Text("🔥"), on_click=add_emoji),
        ft.ElevatedButton(content = ft.Text("😂"), on_click=add_emoji),
    ])

    # Збираємо інтерфейс докупи
    page.add(
        chat,
        emoji_row,
        ft.Row([message_input, ft.ElevatedButton("Надіслати", on_click=send_click)])
    )
        
    
ft.app(target = main, view=ft.AppView.WEB_BROWSER)
