"""Exercise the login API against the local database without sending an email."""

import os
import secrets
import sys
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import get_engine  # noqa: E402
from app.main import app  # noqa: E402
from app.services import email_service  # noqa: E402


def main() -> None:
    email = f"login-check-{secrets.token_hex(8)}@qq.com"
    sent_codes: list[str] = []
    original_sender = email_service.send_login_email
    previous_key = os.environ.get("APP_RESEND_API_KEY")
    previous_from = os.environ.get("APP_RESEND_FROM")
    email_service.send_login_email = lambda _email, code: sent_codes.append(code)
    os.environ["APP_RESEND_API_KEY"] = "test-key"
    os.environ["APP_RESEND_FROM"] = "test@example.test"

    try:
        with TestClient(app) as client:
            assert client.get("/api/user/get/login").status_code == 401
            sent = client.post("/api/user/login/email-code", json={"email": email})
            assert sent.status_code == 200 and sent.json()["data"] is True, (sent.status_code, sent.text)
            assert len(sent_codes) == 1

            cooldown = client.post("/api/user/login/email-code", json={"email": email})
            assert cooldown.status_code == 200 and len(sent_codes) == 1

            wrong = client.post("/api/user/login", json={"email": email, "code": "000000"})
            assert wrong.status_code == 400

            logged_in = client.post(
                "/api/user/login",
                json={"email": email, "code": sent_codes[0], "locale": "zh-CN", "timeZone": "Asia/Shanghai"},
            )
            assert logged_in.status_code == 200, logged_in.text
            assert logged_in.json()["data"]["user"]["email"] == email
            assert "HttpOnly" in logged_in.headers["set-cookie"]

            current = client.get("/api/user/get/login")
            assert current.status_code == 200 and current.json()["data"]["email"] == email

            logged_out = client.post("/api/user/logout")
            assert logged_out.status_code == 200 and logged_out.json()["data"] is True
            assert client.get("/api/user/get/login").status_code == 401

        print("login flow OK: send, cooldown, invalid code, login, cookie probe, logout")
    finally:
        email_service.send_login_email = original_sender
        if previous_key is None:
            os.environ.pop("APP_RESEND_API_KEY", None)
        else:
            os.environ["APP_RESEND_API_KEY"] = previous_key
        if previous_from is None:
            os.environ.pop("APP_RESEND_FROM", None)
        else:
            os.environ["APP_RESEND_FROM"] = previous_from
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
