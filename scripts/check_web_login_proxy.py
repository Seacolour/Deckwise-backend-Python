"""Check cookie login through the running Next.js /api proxy without email delivery."""

import os
import secrets
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.security import code_digest  # noqa: E402
from app.db.session import get_engine  # noqa: E402


def main() -> None:
    email = f"proxy-check-{secrets.token_hex(8)}@qq.com"
    code = "123456"
    salt = secrets.token_bytes(16)
    now = datetime.now(timezone.utc)

    try:
        with get_engine().begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO backend_data.email_login_codes "
                    "(email, code_salt, code_hash, sent_at, expires_at) "
                    "VALUES (:email, :salt, :digest, :sent_at, :expires_at)"
                ),
                {
                    "email": email,
                    "salt": salt,
                    "digest": code_digest(code, salt),
                    "sent_at": now,
                    "expires_at": now + timedelta(minutes=5),
                },
            )

        web_url = os.getenv("DECKWISE_WEB_URL", "http://localhost:3000")
        with httpx.Client(base_url=web_url, timeout=15) as client:
            login = client.post("/api/user/login", json={"email": email, "code": code})
            assert login.status_code == 200, (login.status_code, login.text)
            assert login.json()["data"]["user"]["email"] == email
            assert "deckwise_session=" in login.headers.get("set-cookie", "")

            probe = client.get("/api/user/get/login")
            assert probe.status_code == 200, (probe.status_code, probe.text)
            assert probe.json()["data"]["email"] == email

            logout = client.post("/api/user/logout")
            assert logout.status_code == 200 and logout.json()["data"] is True
            assert client.get("/api/user/get/login").status_code == 401

        print("Web proxy login OK: cookie forwarded, session probe, logout")
    finally:
        with get_engine().begin() as connection:
            connection.execute(
                text("DELETE FROM backend_data.email_login_codes WHERE email = :email"),
                {"email": email},
            )
            connection.execute(
                text("DELETE FROM backend_data.users WHERE email = :email"),
                {"email": email},
            )


if __name__ == "__main__":
    main()
