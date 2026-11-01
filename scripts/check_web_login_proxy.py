"""Check cookie login through the running Next.js /api proxy without email delivery."""

import os
import secrets
import sys
from pathlib import Path

import httpx
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.security import code_digest  # noqa: E402
from app.db.session import get_engine  # noqa: E402
from app.repositories import auth_redis_repository  # noqa: E402


def main() -> None:
    email = f"proxy-check-{secrets.token_hex(8)}@qq.com"
    code = "123456"
    salt = secrets.token_bytes(16)
    token: str | None = None

    try:
        assert auth_redis_repository.issue_login_code(email, salt, code_digest(code, salt))

        web_url = os.getenv("DECKWISE_WEB_URL", "http://localhost:3000")
        with httpx.Client(base_url=web_url, timeout=15) as client:
            login = client.post("/api/user/login", json={"email": email, "code": code})
            assert login.status_code == 200, (login.status_code, login.text)
            assert login.json()["data"]["user"]["email"] == email
            assert "deckwise_session=" in login.headers.get("set-cookie", "")
            token = client.cookies.get("deckwise_session")

            probe = client.get("/api/user/get/login")
            assert probe.status_code == 200, (probe.status_code, probe.text)
            assert probe.json()["data"]["email"] == email

            logout = client.post("/api/user/logout")
            assert logout.status_code == 200 and logout.json()["data"] is True
            assert client.get("/api/user/get/login").status_code == 401

        print("Web proxy login OK: cookie forwarded, session probe, logout")
    finally:
        if token:
            auth_redis_repository.revoke_web_session(token)
        auth_redis_repository.get_redis().delete(*auth_redis_repository._email_keys(email))
        with get_engine().begin() as connection:
            connection.execute(
                text("DELETE FROM backend_data.users WHERE email = :email"),
                {"email": email},
            )


if __name__ == "__main__":
    main()
