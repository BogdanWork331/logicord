FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV FLET_FORCE_WEB_SERVER=true
ENV FLET_SERVER_IP=0.0.0.0

CMD FLET_SERVER_PORT=$PORT python main.py