"""Real model check: one turn reads Notion and a temporary project document."""

import json
import os
import secrets
import sys
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.security import COOKIE_NAME, new_session_token  # noqa: E402
from app.db.checkpoint import selector_loop_factory  # noqa: E402
from app.db.session import get_engine  # noqa: E402
from app.main import app  # noqa: E402
from app.repositories import auth_redis_repository  # noqa: E402


def main() -> None:
    page_id = os.getenv("DECKWISE_TEST_NOTION_PAGE_ID", "").strip()
    if not page_id:
        raise SystemExit("Set DECKWISE_TEST_NOTION_PAGE_ID to a page you may read")
    with get_engine().connect() as db:
        user_id = db.scalar(text("""
            SELECT user_id FROM backend_data.user_mcp_connections
            WHERE provider_id = 'notion' AND status = 'connected'
            ORDER BY updated_at DESC LIMIT 1
        """))
    if user_id is None:
        raise SystemExit("Connect Notion in the Web plugin page first")
    token = new_session_token()
    project_id = None
    try:
        auth_redis_repository.create_web_session(token, user_id)
        headers = {"cookie": f"{COOKIE_NAME}={token}"}
        with TestClient(app, backend_options={"loop_factory": selector_loop_factory}) as client:
            project = client.post("/api/projects/create", headers=headers,
                                  json={"name": f"Notion 跨来源联调 {secrets.token_hex(5)}"})
            assert project.status_code == 200, project.text
            project_id = int(project.json()["data"]["id"])
            document = client.post("/api/documents/create", headers=headers, json={
                "projectId": project_id, "title": "本地方案",
                "draftContent": "# 本地方案\n\n这个临时项目文档说明：FastAPI 负责文档业务和权限，LangGraph 负责 Agent 工具调度。\n",
            })
            assert document.status_code == 200, document.text
            document_id = int(document.json()["data"]["id"])
            session = client.post(f"/api/projects/{project_id}/create", headers=headers,
                                  json={"title": "Notion 与本地文档比较"})
            assert session.status_code == 200, session.text
            session_id = session.json()["data"]["id"]
            prompt = (f"请分别调用 notion_fetch 读取我已授权的 Notion 页面 ID {page_id}，"
                      "再用 document_read 读取当前项目文档。只比较两者内容并给出来源，不要修改文档。")
            stream = client.post(f"/api/sessions/{session_id}/sendRPC", headers=headers, json={
                "message": prompt, "mode": "ASK", "model": "deepseek-chat",
                "clientContext": {"activeDocument": {"documentId": document_id, "type": "markdown"}},
            })
            assert stream.status_code == 200, stream.text[:250]
            events = [json.loads(line[6:]) for line in stream.text.splitlines()
                      if line.startswith("data: {")]
            calls = [item["name"] for item in events if item.get("type") == "tool_call"]
            results = [item["name"] for item in events if item.get("type") == "tool_result"]
            print("cross-source tool calls=", calls, "results=", results,
                  "done=", "event: done" in stream.text)
            assert {"notion_fetch", "document_read"} <= set(calls)
            assert {"notion_fetch", "document_read"} <= set(results)
            assert "document_save" not in calls and "event: done" in stream.text
    finally:
        auth_redis_repository.revoke_web_session(token)
        if project_id is not None:
            with get_engine().begin() as db:
                db.execute(text("DELETE FROM backend_data.projects WHERE id = :id AND owner_id = :user_id"),
                           {"id": project_id, "user_id": user_id})


if __name__ == "__main__":
    main()
