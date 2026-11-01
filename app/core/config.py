"""Load only environment settings used by implemented features."""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import dotenv_values

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def setting(name: str, default: str | None = None, *, aliases: tuple[str, ...] = ()) -> str | None:
    """Prefer process settings, then this project's .env, for the requested keys."""
    names = (name, *aliases)
    for key in names:
        value = os.getenv(key)
        if value is not None:
            return value
    values = dotenv_values(PROJECT_ROOT / ".env")
    for key in names:
        value = values.get(key)
        if value is not None:
            return value
    return default


@dataclass(frozen=True)
class DatabaseSettings:
    host: str
    port: int
    name: str
    user: str
    password: str | None = field(repr=False)


def database_settings() -> DatabaseSettings:
    return DatabaseSettings(
        host=setting("DECKWISE_DB_HOST", "127.0.0.1") or "127.0.0.1",
        port=int(setting("DECKWISE_DB_PORT", "5432") or "5432"),
        name=setting("DECKWISE_DB_NAME", "deckwise_python_dev") or "deckwise_python_dev",
        user=setting("DECKWISE_DB_USER", "postgres") or "postgres",
        password=setting("DECKWISE_DB_PASSWORD", aliases=("DB_PASSWORD", "PGPASSWORD")) or None,
    )


def resend_settings() -> tuple[str, str]:
    api_key = (setting("APP_RESEND_API_KEY") or "").strip()
    sender = (setting("APP_RESEND_FROM") or "").strip()
    return api_key, sender


def secure_session_cookie() -> bool:
    return (setting("APP_WEB_SESSION_COOKIE_SECURE", "false") or "false").lower() == "true"


def redis_url() -> str:
    return (setting("DECKWISE_REDIS_URL", "redis://127.0.0.1:6379/0") or "").strip()


def is_dev_environment() -> bool:
    return (setting("DECKWISE_ENV", "prod") or "prod").lower() in {"dev", "development"}
