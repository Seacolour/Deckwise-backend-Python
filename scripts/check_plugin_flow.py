"""Check user-scoped MCP and Skill switches through the Web API."""

import json
import secrets
import sys
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agent.tools import tools_for_project  # noqa: E402
from app.core.security import COOKIE_NAME, new_session_token  # noqa: E402
from app.db.checkpoint import selector_loop_factory  # noqa: E402
from app.db.session import get_engine  # noqa: E402
from app.main import app  # noqa: E402
from app.repositories import auth_redis_repository  # noqa: E402
from app.services import agent_plugin_service  # noqa: E402


def main() -> None:
    marker = secrets.token_hex(8)
    emails = [f"plugin-check-{marker}-a@example.test", f"plugin-check-{marker}-b@example.test"]
    tokens = [new_session_token(), new_session_token()]
    with get_engine().begin() as db:
        user_ids = [db.scalar(text("""
            INSERT INTO backend_data.users (email, email_verified, sign_up_provider)
            VALUES (:email, true, 'email') RETURNING id
        """), {"email": email}) for email in emails]
    try:
        for token, user_id in zip(tokens, user_ids):
            auth_redis_repository.create_web_session(token, user_id)
        headers = [{"cookie": f"{COOKIE_NAME}={token}"} for token in tokens]
        with TestClient(app, backend_options={"loop_factory": selector_loop_factory}) as client:
            assert client.get("/api/user/agent-plugins").status_code == 401
            initial = client.get("/api/user/agent-plugins", headers=headers[0])
            assert initial.status_code == 200
            states = {item["id"]: item["enabled"] for item in initial.json()["data"]}
            assert states == {"docs-langchain": False, "notion": False,
                              "skill:document-review": True,
                              "skill:source-grounded-answer": True}
            enabled = client.put("/api/user/agent-plugins/docs-langchain", headers=headers[0],
                                 json={"enabled": True})
            assert enabled.status_code == 200 and enabled.json()["data"]["enabled"] is True
            disabled = client.put("/api/user/agent-plugins/skill:document-review", headers=headers[0],
                                  json={"enabled": False})
            assert disabled.status_code == 200 and disabled.json()["data"]["enabled"] is False
            assert client.put("/api/user/agent-plugins/unknown", headers=headers[0],
                              json={"enabled": True}).status_code == 404
            second = client.get("/api/user/agent-plugins", headers=headers[1])
            assert {item["id"]: item["enabled"] for item in second.json()["data"]} == states
        selected = agent_plugin_service.enabled_plugin_ids(user_ids[0])
        tools = tools_for_project(user_ids[0], 1, "ASK",
                                  docs_mcp_enabled="docs-langchain" in selected,
                                  enabled_skill_names={item.removeprefix("skill:") for item in selected
                                                       if item.startswith("skill:")})
        names = {item.name for item in tools}
        assert "langchain_docs_search" in names and "skill_read" in names
        read = next(item for item in tools if item.name == "skill_read")
        assert json.loads(read.invoke({"name": "document-review"}))["success"] is False
        assert json.loads(read.invoke({"name": "source-grounded-answer"}))["success"] is True
        print("plugin flow OK: user isolation, MCP switch, Skill allowlist")
    finally:
        for token in tokens:
            auth_redis_repository.revoke_web_session(token)
        with get_engine().begin() as db:
            db.execute(text("DELETE FROM backend_data.users WHERE email = ANY(:emails)"), {"emails": emails})


if __name__ == "__main__":
    main()
