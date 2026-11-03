"""Check model availability and daily check-in with temporary accounts."""

import os
import secrets
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
from fastapi.testclient import TestClient
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.security import COOKIE_NAME, new_session_token  # noqa: E402
from app.db.session import get_engine  # noqa: E402
from app.db.checkpoint import selector_loop_factory  # noqa: E402
from app.main import app  # noqa: E402
from app.repositories import auth_redis_repository  # noqa: E402


def _request(client: httpx.Client, method: str, path: str, token: str, **kwargs) -> httpx.Response:
    return client.request(method, path, headers={"cookie": f"{COOKIE_NAME}={token}"}, **kwargs)


def main() -> None:
    suffix = secrets.token_hex(8)
    emails = [f"checkin-{suffix}-a@example.test", f"checkin-{suffix}-b@example.test"]
    tokens = [new_session_token(), new_session_token()]
    user_ids: list[int] = []
    today = datetime.now(ZoneInfo("Asia/Shanghai")).date()

    try:
        with get_engine().begin() as connection:
            for email in emails:
                user_ids.append(connection.scalar(text("""
                    INSERT INTO backend_data.users (email, email_verified, sign_up_provider)
                    VALUES (:email, true, 'email') RETURNING id
                """), {"email": email}))
            connection.execute(text("""
                UPDATE backend_data.users SET preferred_time_zone = 'Asia/Shanghai' WHERE id = :user_id
            """), {"user_id": user_ids[1]})
            connection.execute(text("""
                INSERT INTO backend_data.user_checkin_status
                    (user_id, streak_count, longest_streak, last_checkin_date)
                VALUES (:user_id, 1, 1, :yesterday)
            """), {"user_id": user_ids[1], "yesterday": today - timedelta(days=1)})
        for token, user_id in zip(tokens, user_ids):
            auth_redis_repository.create_web_session(token, user_id)

        base_url = os.getenv("DECKWISE_CHECK_BASE_URL")
        client_context = (httpx.Client(base_url=base_url, timeout=15) if base_url else
                          TestClient(app, backend_options={"loop_factory": selector_loop_factory}))
        with client_context as client:
            anonymous = client.get("/api/models/available")
            assert anonymous.status_code == 401, anonymous.text
            models = _request(client, "GET", "/api/models/available", tokens[0])
            assert models.status_code == 200 and isinstance(models.json()["data"], list), models.text
            assert models.json()["data"] == [], models.text

            initial = _request(client, "GET", "/api/user/checkin/status", tokens[0])
            assert initial.status_code == 200, initial.text
            assert initial.json()["data"] == {
                "streakCount": 0, "longestStreak": 0, "lastCheckinDate": None,
            }
            body = {"deviceType": "web", "timeZone": "Asia/Shanghai", "locale": "zh-CN", "country": "CN"}
            first = _request(client, "POST", "/api/user/checkin", tokens[0], json=body)
            assert first.status_code == 200, first.text
            assert first.json()["data"] == {
                "checkedIn": True, "rewardPoints": 500,
                "streakAfter": 1, "longestStreak": 1, "date": today.isoformat(),
            }, first.text
            repeated = _request(client, "POST", "/api/user/checkin", tokens[0], json=body)
            assert repeated.status_code == 200 and repeated.json()["data"]["rewardPoints"] == 0, repeated.text
            status = _request(client, "GET", "/api/user/checkin/status", tokens[0])
            assert status.json()["data"] == {
                "streakCount": 1, "longestStreak": 1, "lastCheckinDate": today.isoformat(),
            }

            consecutive = _request(client, "POST", "/api/user/checkin", tokens[1], json={"deviceType": "web"})
            assert consecutive.status_code == 200 and consecutive.json()["data"]["streakAfter"] == 2, consecutive.text
            assert _request(client, "GET", "/api/user/checkin/status", tokens[1]).json()["data"]["streakCount"] == 2

        with get_engine().connect() as connection:
            count = connection.scalar(text("""
                SELECT count(*) FROM backend_data.user_checkin_log WHERE user_id = :user_id
            """), {"user_id": user_ids[0]})
            zone = connection.scalar(text("""
                SELECT preferred_time_zone FROM backend_data.users WHERE id = :user_id
            """), {"user_id": user_ids[0]})
        assert count == 1 and zone == "Asia/Shanghai"
        print("model/check-in flow OK: auth, catalog, daily idempotence, streak, persistence")
    finally:
        for token in tokens:
            auth_redis_repository.revoke_web_session(token)
        with get_engine().begin() as connection:
            connection.execute(text("DELETE FROM backend_data.users WHERE email = ANY(:emails)"), {"emails": emails})


if __name__ == "__main__":
    main()
