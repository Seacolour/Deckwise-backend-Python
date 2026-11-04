"""Exercise Notion OAuth state and per-user storage without contacting Notion."""

import os
import secrets
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient
import httpx
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.mcp_credential_cipher import decrypt, encrypt  # noqa: E402
from app.core.security import COOKIE_NAME, new_session_token  # noqa: E402
from app.db.checkpoint import selector_loop_factory  # noqa: E402
from app.db.session import get_engine, session_scope  # noqa: E402
from app.main import app  # noqa: E402
from app.repositories import auth_redis_repository, mcp_connection_repository  # noqa: E402
from app.services import notion_mcp_connection_service, notion_mcp_oauth_client  # noqa: E402


def main() -> None:
    marker = secrets.token_hex(8)
    emails = [f"notion-check-{marker}-{letter}@example.test" for letter in ("a", "b")]
    tokens = [new_session_token(), new_session_token()]
    with get_engine().begin() as db:
        users = [db.scalar(text("""
            INSERT INTO backend_data.users (email, email_verified, sign_up_provider)
            VALUES (:email, true, 'email') RETURNING id
        """), {"email": email}) for email in emails]
    original = {name: getattr(notion_mcp_oauth_client, name)
                for name in ("discover", "register", "exchange", "refresh")}
    calls = {"register": 0, "exchange": 0, "refresh": 0}
    metadata = {"authorization_endpoint": "https://mcp.notion.com/authorize",
                "token_endpoint": "https://mcp.notion.com/token",
                "registration_endpoint": "https://mcp.notion.com/register"}

    def register(_redirect_uri, _metadata):
        calls["register"] += 1
        return {"client_id": "test-notion-client", "client_secret": None}

    def exchange(_code, _verifier, _redirect_uri, _client_id, _secret, _metadata):
        calls["exchange"] += 1
        return {"access_token": "test-access", "refresh_token": "test-refresh",
                "expires_in": 3600, "workspace_id": "workspace-a", "workspace_name": "Demo Workspace"}

    def refresh(_token, _client_id, _secret, _metadata):
        calls["refresh"] += 1
        return {"access_token": "renewed-access", "refresh_token": "renewed-refresh",
                "expires_in": 3600}

    notion_mcp_oauth_client.discover = lambda: metadata
    notion_mcp_oauth_client.register = register
    notion_mcp_oauth_client.exchange = exchange
    notion_mcp_oauth_client.refresh = refresh
    try:
        for token, user_id in zip(tokens, users):
            auth_redis_repository.create_web_session(token, user_id)
        headers = [{"cookie": f"{COOKIE_NAME}={token}"} for token in tokens]
        with TestClient(app, backend_options={"loop_factory": selector_loop_factory}) as client:
            assert client.post("/api/user/agent-plugins/notion/connect").status_code == 401
            assert client.put("/api/user/agent-plugins/notion", json={"enabled": True},
                              headers=headers[0]).status_code == 409
            started = client.post("/api/user/agent-plugins/notion/connect", headers=headers[0])
            assert started.status_code == 200, started.text
            url = started.json()["data"]["authorizationUrl"]
            assert urlparse(url).netloc == "mcp.notion.com"
            state = parse_qs(urlparse(url).query)["state"][0]
            pending = client.get("/api/user/agent-plugins", headers=headers[0]).json()["data"]
            notion = next(item for item in pending if item["id"] == "notion")
            assert notion["connectionStatus"] == "authorizing" and not notion["enabled"]
            assert client.get("/api/user/agent-plugins", headers=headers[1]).json()["data"][1]["connectionStatus"] == "disconnected"
            assert client.put("/api/user/agent-plugins/notion", json={"enabled": True},
                              headers=headers[0]).status_code == 409
            # The callback is bound to both the application user and the same Web session.
            wrong = client.post("/api/user/agent-plugins/notion/callback", headers=headers[1],
                                json={"code": "demo-code", "state": state})
            assert wrong.status_code == 400
            completed = client.post("/api/user/agent-plugins/notion/callback", headers=headers[0],
                                    json={"code": "demo-code", "state": state})
            assert completed.status_code == 200, completed.text
            assert completed.json()["data"]["enabled"] is True
            assert completed.json()["data"]["workspaceName"] == "Demo Workspace"
            assert client.post("/api/user/agent-plugins/notion/callback", headers=headers[0],
                               json={"code": "demo-code", "state": state}).status_code == 400
            retry = client.post("/api/user/agent-plugins/notion/connect", headers=headers[0])
            retry_state = parse_qs(urlparse(retry.json()["data"]["authorizationUrl"]).query)["state"][0]
            assert calls["register"] == 1  # Persisted DCR identity survives a retry.
            completed = client.post("/api/user/agent-plugins/notion/callback", headers=headers[0],
                                    json={"code": "demo-code", "state": retry_state})
            assert completed.status_code == 200, completed.text
            assert client.post("/api/user/agent-plugins/notion/callback", headers=headers[0],
                               json={"code": "demo-code", "state": retry_state}).status_code == 400
            assert client.get("/api/user/agent-plugins", headers=headers[1]).json()["data"][1]["enabled"] is False
            assert notion_mcp_connection_service.access_token(users[0]) == "test-access"
            with session_scope() as db:
                row = mcp_connection_repository.find(db, users[0], lock=True)
                data = decrypt(users[0], "notion", row["credential_ciphertext"], row["nonce"], row["key_version"])
                data["expires_at"] = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
                ciphertext, nonce, version = encrypt(users[0], "notion", data)
                mcp_connection_repository.upsert(db, users[0], "notion", "connected", ciphertext,
                                                 nonce, version, row["workspace_id"], row["workspace_name"])
            assert notion_mcp_connection_service.access_token(users[0]) == "renewed-access"
            assert calls["refresh"] == 1
            assert notion_mcp_connection_service.access_token(users[0]) == "renewed-access"
            assert calls["refresh"] == 1
            assert client.put("/api/user/agent-plugins/notion", json={"enabled": False},
                              headers=headers[0]).status_code == 200
            assert notion_mcp_connection_service.access_token(users[0]) == "renewed-access"
            with session_scope() as db:
                row = mcp_connection_repository.find(db, users[0], lock=True)
                data = decrypt(users[0], "notion", row["credential_ciphertext"], row["nonce"], row["key_version"])
                data["expires_at"] = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
                ciphertext, nonce, version = encrypt(users[0], "notion", data)
                mcp_connection_repository.upsert(db, users[0], "notion", "connected", ciphertext,
                                                 nonce, version, row["workspace_id"], row["workspace_name"])

            def invalid_grant(*_args):
                raise notion_mcp_oauth_client.ReauthorizationRequired

            notion_mcp_oauth_client.refresh = invalid_grant
            try:
                notion_mcp_connection_service.access_token(users[0])
                raise AssertionError("invalid grant should require reconnection")
            except Exception as error:
                from app.core.exceptions import BusinessError
                assert isinstance(error, BusinessError) and error.status == 409
            reconnect = client.get("/api/user/agent-plugins", headers=headers[0]).json()["data"][1]
            assert reconnect["connectionStatus"] == "reconnect_required" and not reconnect["enabled"]
            assert client.delete("/api/user/agent-plugins/notion/connection", headers=headers[0]).json()["data"] is True
            after = client.get("/api/user/agent-plugins", headers=headers[0]).json()["data"][1]
            assert after["connectionStatus"] == "disconnected" and not after["enabled"]
            assert client.put("/api/user/agent-plugins/notion", json={"enabled": True},
                              headers=headers[0]).status_code == 409
        base_url = os.getenv("DECKWISE_CHECK_BASE_URL")
        if base_url:
            with httpx.Client(base_url=base_url, cookies={COOKIE_NAME: tokens[0]},
                              timeout=10, trust_env=False) as web:
                listed = web.get("/api/user/agent-plugins")
                assert listed.status_code == 200, f"web plugin list status={listed.status_code} body={listed.text[:200]}"
                notion = next(item for item in listed.json()["data"] if item["id"] == "notion")
                assert notion["connectionStatus"] == "disconnected" and not notion["enabled"]
                denied = web.put("/api/user/agent-plugins/notion", json={"enabled": True})
                assert denied.status_code == 409, denied.text
        print("Notion connection flow OK: OAuth state, user isolation, refresh, disconnect")
    finally:
        for name, value in original.items():
            setattr(notion_mcp_oauth_client, name, value)
        for token in tokens:
            auth_redis_repository.revoke_web_session(token)
        with get_engine().begin() as db:
            db.execute(text("DELETE FROM backend_data.users WHERE email = ANY(:emails)"), {"emails": emails})


if __name__ == "__main__":
    main()
