from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

import bcrypt

from .config import LOGIN_RATE_LIMIT_MAX, LOGIN_RATE_LIMIT_WINDOW_SEC


USERNAME_RE = re.compile(r"^[a-zA-Z0-9_.-]{3,32}$")


def normalize_username(value: str) -> str:
    return (value or "").strip()


def is_valid_username(value: str) -> bool:
    return bool(USERNAME_RE.fullmatch(value or ""))


def hash_password(password: str) -> str:
    if not password:
        raise ValueError("Password cannot be empty")
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8"))
    except Exception:
        return False


@dataclass
class RateLimitBucket:
    attempts: list[float] = field(default_factory=list)

    def allow(self) -> tuple[bool, int]:
        now = time.time()
        window_start = now - LOGIN_RATE_LIMIT_WINDOW_SEC
        self.attempts = [ts for ts in self.attempts if ts >= window_start]
        if len(self.attempts) >= LOGIN_RATE_LIMIT_MAX:
            retry_after = int(max(1, LOGIN_RATE_LIMIT_WINDOW_SEC - (now - self.attempts[0])))
            return False, retry_after
        self.attempts.append(now)
        return True, 0


class LoginRateLimiter:
    def __init__(self) -> None:
        self._buckets: dict[str, RateLimitBucket] = {}

    def check(self, key: str) -> tuple[bool, int]:
        bucket = self._buckets.setdefault(key, RateLimitBucket())
        return bucket.allow()


login_rate_limiter = LoginRateLimiter()