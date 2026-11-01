"""Small, explicit primitives for email codes and opaque Web sessions."""

import hashlib
import secrets
from datetime import timedelta

COOKIE_NAME = "deckwise_session"
CODE_LIFETIME = timedelta(minutes=5)
CODE_COOLDOWN = timedelta(minutes=1)
SESSION_LIFETIME = timedelta(days=30)
MAX_CODE_ATTEMPTS = 5


def new_email_code() -> str:
    return f"{secrets.randbelow(900_000) + 100_000:06d}"


def code_digest(code: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", code.encode("ascii"), salt, 200_000)


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def token_digest(token: str) -> bytes:
    return hashlib.sha256(token.encode("utf-8")).digest()
