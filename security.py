from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

import bcrypt

USERNAME_RE = re.compile(r"^[a-zA-Z0-9_.-]{3,32}$")


def normalize_username(value: str) -> str:
    return (value or "").strip()


def is_valid_username(value: str) -> bool:
    return bool(USERNAME_RE.fullmatch((value or "").strip()))


def hash_password(password: str) -> str:
    password = (password or "").strip()
    if not password:
        raise ValueError("Password cannot be empty")
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        return bcrypt.checkpw(
            (password or "").encode("utf-8"),
            (stored_hash or "").encode("utf-8"),
        )
    except Exception:
        return False


@dataclass
class RateBucket:
    attempts: list[float] = field(default_factory=list)


class LoginRateLimiter:
    def __init__(self, max_attempts: int = 5, window_sec: int = 300) -> None:
        self.max_attempts = max_attempts
        self.window_sec = window_sec
        self._buckets: dict[str, RateBucket] = {}

    def check(self, key: str) -> tuple[bool, int]:
        now = time.time()
        bucket = self._buckets.setdefault(key, RateBucket())

        cutoff = now - self.window_sec
        bucket.attempts = [ts for ts in bucket.attempts if ts >= cutoff]

        if len(bucket.attempts) >= self.max_attempts:
            retry_after = int(max(1, self.window_sec - (now - bucket.attempts[0])))
            return False, retry_after

        bucket.attempts.append(now)
        return True, 0


login_limiter = LoginRateLimiter(max_attempts=5, window_sec=300)