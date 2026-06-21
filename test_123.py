from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import jwt
import time

SECRET = "ECHOSHADE_SECRET"

app = FastAPI()

# Простая база
users = {}  # username: password
messages = {
    "general": [],
    "random": [],
    "dev-room": []
}

connections = {
    "general": set(),
    "random": set(),
    "dev-room": set()
}

class Auth(BaseModel):
    username: str
    password: str


def create_token(username):
    return jwt.encode({"user": username, "exp": time.time() + 86400}, SECRET, algorithm="HS256")


def decode_token(token):
    return jwt.decode(token, SECRET, algorithms=["HS256"])["user"]


@app.post("/api/register")
def register(data: Auth):
    if data.username in users:
        return {"detail": "Пользователь уже существует"}
    users[data.username] = data.password
    return {"status": "ok"}


@app.post("/api/login")
def login(data: Auth):
    if users.get(data.username) != data.password:
        return {"detail": "Неверные данные"}
    return {"token": create_token(data.username), "username": data.username}


@app.get("/api/messages/{channel}")
def get_history(channel: str):
    return messages.get(channel, [])


@app.websocket("/ws/{channel}")
async def websocket_endpoint(websocket: WebSocket, channel: str):
    token = websocket.query_params.get("token")
    try:
        username = decode_token(token)
    except:
        await websocket.close()
        return

    await websocket.accept()
    connections[channel].add(websocket)

    try:
        while True:
            text = await websocket.receive_text()
            msg = {"username": username, "content": text}
            messages[channel].append(msg)

            # рассылаем всем
            for ws in list(connections[channel]):
                try:
                    await ws.send_json(msg)
                except:
                    connections[channel].remove(ws)

    except WebSocketDisconnect:
        connections[channel].remove(websocket)
