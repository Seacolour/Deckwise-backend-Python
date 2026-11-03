"""Exercise user-scoped encrypted model credentials and catalog filtering."""

import os
import secrets
import sys
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.security import COOKIE_NAME, new_session_token  # noqa: E402
from app.core.config import setting  # noqa: E402
from app.db.checkpoint import selector_loop_factory  # noqa: E402
from app.db.session import get_engine  # noqa: E402
from app.main import app  # noqa: E402
from app.repositories import auth_redis_repository  # noqa: E402
from app.services import model_service  # noqa: E402


class ScriptedProbe:
    def __init__(self, error: Exception | None = None):
        self.error = error

    async def ainvoke(self, _message):
        if self.error:
            raise self.error
        return "OK"


class RejectedKey(Exception):
    status_code = 401


class RateLimited(Exception):
    status_code = 429


def main() -> None:
    marker = secrets.token_hex(8)
    emails = [f"byok-{marker}-a@example.test", f"byok-{marker}-b@example.test"]
    tokens = [new_session_token(), new_session_token()]
    with get_engine().begin() as db:
        user_ids = [db.scalar(text("""
            INSERT INTO backend_data.users (email, email_verified, sign_up_provider)
            VALUES (:email, true, 'email') RETURNING id
        """), {"email": email}) for email in emails]
    original_builder = model_service.build_chat_model
    try:
        for token, user_id in zip(tokens, user_ids):
            auth_redis_repository.create_web_session(token, user_id)
        headers = [{"cookie": f"{COOKIE_NAME}={token}"} for token in tokens]
        model_service.build_chat_model = lambda *_args, **_kwargs: ScriptedProbe()
        with TestClient(app, backend_options={"loop_factory": selector_loop_factory}) as client:
            assert client.get("/api/models/available", headers=headers[0]).json()["data"] == []
            assert client.get("/api/models/available", headers=headers[1]).json()["data"] == []
            statuses = client.get("/api/user/model-credentials", headers=headers[0])
            assert statuses.status_code == 200
            assert [(item["providerId"], item["configured"]) for item in statuses.json()["data"]] == [
                ("deepseek", False), ("openrouter", False),
            ]
            candidate = client.post("/api/user/model-credentials/deepseek/test", headers=headers[0],
                                    json={"apiKey": "candidate-only-key"})
            assert candidate.status_code == 200 and candidate.json()["data"]["status"] == "valid"
            assert client.get("/api/models/available", headers=headers[0]).json()["data"] == []
            if os.getenv("DECKWISE_REAL_KEY_PROBE") == "1":
                live_key = setting("DECKWISE_TEST_DEEPSEEK_API_KEY", aliases=("DEEPSEEK_API_KEY",))
                if not live_key:
                    raise SystemExit("Set DECKWISE_TEST_DEEPSEEK_API_KEY for the real provider probe")
                model_service.build_chat_model = original_builder
                live_result = client.post("/api/user/model-credentials/deepseek/test", headers=headers[0],
                                          json={"apiKey": live_key})
                assert live_result.status_code == 200 and live_result.json()["data"]["status"] == "valid"
                assert client.get("/api/models/available", headers=headers[0]).json()["data"] == []
                model_service.build_chat_model = lambda *_args, **_kwargs: ScriptedProbe()
            deepseek = client.put("/api/user/model-credentials/deepseek", headers=headers[0],
                                  json={"apiKey": "local-deepseek-test-key"})
            assert deepseek.status_code == 200 and deepseek.json()["data"]["maskedKey"] == "****-key"
            stored = client.post("/api/user/model-credentials/deepseek/test", headers=headers[0], json={})
            assert stored.status_code == 200 and stored.json()["data"]["status"] == "valid"
            model_service.build_chat_model = lambda *_args, **_kwargs: ScriptedProbe(RejectedKey())
            rejected = client.post("/api/user/model-credentials/deepseek/test", headers=headers[0], json={})
            assert rejected.status_code == 200 and rejected.json()["data"]["status"] == "invalid"
            assert "local-deepseek-test-key" not in rejected.text
            model_service.build_chat_model = lambda *_args, **_kwargs: ScriptedProbe(RateLimited())
            limited = client.post("/api/user/model-credentials/deepseek/test", headers=headers[0], json={})
            assert limited.status_code == 200 and limited.json()["data"]["status"] == "unavailable"
            model_service.build_chat_model = lambda *_args, **_kwargs: ScriptedProbe()
            openrouter = client.put("/api/user/model-credentials/openrouter", headers=headers[0],
                                    json={"apiKey": "local-openrouter-test-key"})
            assert openrouter.status_code == 200 and openrouter.json()["data"]["configured"] is True
            openrouter_test = client.post("/api/user/model-credentials/openrouter/test", headers=headers[0], json={})
            assert openrouter_test.status_code == 200
            assert openrouter_test.json()["data"]["modelId"] == "openai/gpt-6-luna"
            response = client.get("/api/models/available", headers=headers[0])
            assert [item["id"] for item in response.json()["data"]] == [
                "deepseek-chat", "openai/gpt-6-luna",
            ]
            assert response.json()["data"][0]["imageSupported"] is False
            assert response.json()["data"][1]["imageSupported"] is True
            assert client.get("/api/models/available", headers=headers[1]).json()["data"] == []
            assert model_service.supports_images(user_ids[0], "openai/gpt-6-luna")
            assert not model_service.supports_images(user_ids[1], "openai/gpt-6-luna")
            assert client.put("/api/user/model-credentials/openai", headers=headers[0],
                              json={"apiKey": "wrong-provider"}).status_code == 400
            assert client.put("/api/user/model-credentials/deepseek", headers=headers[0],
                              json={"apiKey": "bad\nkey"}).status_code == 400
            with get_engine().connect() as db:
                encrypted = db.scalar(text("""
                    SELECT ciphertext FROM backend_data.user_model_credentials
                    WHERE user_id = :user_id AND provider_id = 'deepseek'
                """), {"user_id": user_ids[0]})
            assert encrypted and b"local-deepseek-test-key" not in encrypted
            assert client.delete("/api/user/model-credentials/deepseek", headers=headers[0]).json()["data"] is True
            assert [item["id"] for item in client.get("/api/models/available", headers=headers[0]).json()["data"]] == [
                "openai/gpt-6-luna",
            ]
            assert client.delete("/api/user/model-credentials/deepseek", headers=headers[0]).json()["data"] is False
        print("BYOK flow OK: key probe, encrypted keys, per-user catalog, provider isolation, delete")
    finally:
        model_service.build_chat_model = original_builder
        for token in tokens:
            auth_redis_repository.revoke_web_session(token)
        with get_engine().begin() as db:
            db.execute(text("DELETE FROM backend_data.users WHERE email = ANY(:emails)"), {"emails": emails})


if __name__ == "__main__":
    main()
