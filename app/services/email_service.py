"""Resend transport for login codes."""

from uuid import uuid4

import httpx

from app.core.config import resend_settings


def send_login_email(email: str, code: str) -> None:
    api_key, sender = resend_settings()
    if not api_key or not sender:
        raise RuntimeError("Resend sender configuration is missing")

    with httpx.Client(timeout=15) as client:
        response = client.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Idempotency-Key": str(uuid4()),
            },
            json={
                "from": sender,
                "to": [email],
                "subject": "Deckwise 登录验证码",
                "text": f"您的登录验证码是：{code}，5 分钟内有效。如非本人操作，请忽略。",
            },
        )
        response.raise_for_status()
