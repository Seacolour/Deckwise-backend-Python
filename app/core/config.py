"""Load only environment settings used by implemented features."""

import os
from pathlib import Path

from dotenv import dotenv_values

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def resend_settings() -> tuple[str, str]:
    values = dotenv_values(PROJECT_ROOT / ".env")
    api_key = (os.getenv("APP_RESEND_API_KEY") or values.get("APP_RESEND_API_KEY") or "").strip()
    sender = (os.getenv("APP_RESEND_FROM") or values.get("APP_RESEND_FROM") or "").strip()
    return api_key, sender


def secure_session_cookie() -> bool:
    return os.getenv("APP_WEB_SESSION_COOKIE_SECURE", "false").lower() == "true"


def is_dev_environment() -> bool:
    return os.getenv("DECKWISE_ENV", "prod").lower() in {"dev", "development"}
