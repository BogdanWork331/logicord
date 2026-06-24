from __future__ import annotations

import os
from pathlib import Path

APP_NAME = "Logicord"
APP_SLUG = "logicord"
APP_VERSION = "1.0.0"

BASE_DIR = Path(__file__).resolve().parent.parent
ASSETS_DIR = BASE_DIR / "assets"
DB_FILE = os.environ.get("LOGICORD_DB", str(BASE_DIR / "logicord.db"))

DEFAULT_THEME = os.environ.get("LOGICORD_THEME", "dark")
DEFAULT_BACKGROUND = os.environ.get("LOGICORD_BACKGROUND", "aurora")
DEFAULT_LANGUAGE = os.environ.get("LOGICORD_LANGUAGE", "ru")

DEFAULT_CHANNEL_NAME = "general"

LOGIN_RATE_LIMIT_MAX = int(os.environ.get("LOGICORD_LOGIN_MAX_ATTEMPTS", "5"))
LOGIN_RATE_LIMIT_WINDOW_SEC = int(os.environ.get("LOGICORD_LOGIN_WINDOW_SEC", "600"))