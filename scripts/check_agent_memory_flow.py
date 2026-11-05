"""Real Agent write and new-session recall; removes its temporary data."""

import asyncio
import json
import secrets
import sys
from pathlib import Path

from fastapi.testclient import TestClient
from langgraph.store.postgres import AsyncPostgresStore
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.security import COOKIE_NAME, new_session_token  # noqa: E402
from app.db.checkpoint import checkpoint_conninfo, selector_loop_factory  # noqa: E402
from app.db.session import get_engine  # noqa: E402
from app.main import app  # noqa: E402
from app.repositories import auth_redis_repository  # noqa: E402
from app.services import memory_retrieval_service, user_memory_service  # noqa: E402


async def remove_index(user_id: int, memory_ids: list[str]) -> None:
    async with AsyncPostgresStore.from_conn_string(checkpoint_conninfo()) as store:
        for memory_id in memory_ids:
            await store.adelete(memory_retrieval_service._namespace(user_id), memory_id)


def main() -> None:
    with get_engine().connect() as db:
        user_id = db.scalar(text("""
            SELECT n.user_id FROM backend_data.user_mcp_connections AS n
            JOIN backend_data.user_model_credentials AS c ON c.user_id = n.user_id
            WHERE n.provider_id = 'notion' AND n.status = 'connected'
              AND c.provider_id = 'deepseek'
            ORDER BY n.updated_at DESC LIMIT 1
        """))
    if user_id is None:
        raise SystemExit("Configure DeepSeek BYOK for a connected local test user")
    marker = secrets.token_hex(5)
    title = f"记忆联调 {marker}"
    content = f"长期偏好：回答中使用标记 {marker}。"
    token = new_session_token()
    project_id = None
    created_ids: list[str] = []
    try:
        auth_redis_repository.create_web_session(token, user_id)
        headers = {"cookie": f"{COOKIE_NAME}={token}"}
        with TestClient(app, backend_options={"loop_factory": selector_loop_factory}) as client:
            project = client.post("/api/projects/create", headers=headers,
                                  json={"name": f"记忆对话联调 {marker}"})
            assert project.status_code == 200, project.text
            project_id = int(project.json()["data"]["id"])
            first_session = client.post(f"/api/projects/{project_id}/create", headers=headers,
                                        json={"title": "保存长期记忆"})
            assert first_session.status_code == 200
            first_id = first_session.json()["data"]["id"]
            first = client.post(f"/api/sessions/{first_id}/sendRPC", headers=headers, json={
                "message": f"请使用 manage_user_memory 工具创建长期记忆，标题是“{title}”，内容是“{content}”。保存成功后简短确认。",
                "mode": "AGENT", "model": "deepseek-chat",
            })
            assert first.status_code == 200 and "event: done" in first.text
            events = [json.loads(line[6:]) for line in first.text.splitlines()
                      if line.startswith("data: {")]
            calls = [item["name"] for item in events if item.get("type") == "tool_call"]
            assert "manage_user_memory" in calls, calls
            created = [json.loads(item["result_json"]) for item in events
                       if item.get("type") == "tool_result" and item.get("name") == "manage_user_memory"]
            assert any(item.get("success") and item.get("source") == "ai" for item in created), created
            created_ids = [str(item["memory_id"]) for item in created if item.get("success")]
            assert created_ids
            recalled = asyncio.run(memory_retrieval_service.relevant_context(user_id, "我希望回答使用什么标记？"),
                                   loop_factory=selector_loop_factory)
            assert marker in recalled
            second_session = client.post(f"/api/projects/{project_id}/create", headers=headers,
                                         json={"title": "新会话回忆"})
            assert second_session.status_code == 200
            second_id = second_session.json()["data"]["id"]
            second = client.post(f"/api/sessions/{second_id}/sendRPC", headers=headers, json={
                "message": "根据你记住的长期偏好，我希望回答时使用什么标记？",
                "mode": "ASK", "model": "deepseek-chat",
            })
            assert second.status_code == 200 and "event: done" in second.text
            text_events = [json.loads(line[6:]).get("payload", "") for line in second.text.splitlines()
                           if line.startswith("data: {") and json.loads(line[6:]).get("type") == "text"]
            assert marker in "".join(text_events)
            print("Agent memory OK: source=ai, cross-session recall, user-scoped semantic Store")
    finally:
        for item in user_memory_service.list_memories(user_id):
            if item.title == title and item.id not in created_ids:
                created_ids.append(item.id)
        for memory_id in created_ids:
            user_memory_service.delete_memory(user_id, int(memory_id))
        asyncio.run(remove_index(user_id, created_ids), loop_factory=selector_loop_factory)
        auth_redis_repository.revoke_web_session(token)
        if project_id is not None:
            with get_engine().begin() as db:
                db.execute(text("DELETE FROM backend_data.projects WHERE id = :id AND owner_id = :user_id"),
                           {"id": project_id, "user_id": user_id})


if __name__ == "__main__":
    main()
