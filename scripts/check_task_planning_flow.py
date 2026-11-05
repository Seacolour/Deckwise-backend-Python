"""Real DeepSeek check of per-turn Todo planning and document editing."""

import json
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
    with get_engine().connect() as db:
        user_id = db.scalar(text("""
            SELECT c.user_id FROM backend_data.user_model_credentials AS c
            JOIN backend_data.user_mcp_connections AS n ON n.user_id = c.user_id
            WHERE c.provider_id = 'deepseek' AND n.provider_id = 'notion'
              AND n.status = 'connected'
            ORDER BY n.updated_at DESC LIMIT 1
        """))
    if user_id is None:
        raise SystemExit("Configure DeepSeek BYOK for a connected local test user")
    token = new_session_token()
    project_id = None
    try:
        auth_redis_repository.create_web_session(token, user_id)
        headers = {"cookie": f"{COOKIE_NAME}={token}"}
        with TestClient(app, backend_options={"loop_factory": selector_loop_factory}) as client:
            project = client.post("/api/projects/create", headers=headers,
                                  json={"name": f"任务计划联调 {secrets.token_hex(5)}"})
            assert project.status_code == 200, project.text
            project_id = int(project.json()["data"]["id"])
            document = client.post("/api/documents/create", headers=headers, json={
                "projectId": project_id, "title": "计划测试文档",
                "draftContent": "# 计划测试文档\n\n待核查结论：苹果是蔬菜。\n\n参考资料：苹果是水果。\n",
            })
            assert document.status_code == 200, document.text
            document_id = int(document.json()["data"]["id"])
            session = client.post(f"/api/projects/{project_id}/create", headers=headers,
                                  json={"title": "多步骤编辑与待办"})
            assert session.status_code == 200, session.text
            session_id = session.json()["data"]["id"]
            stream = client.post(f"/api/sessions/{session_id}/sendRPC", headers=headers, json={
                "message": "请先建立任务计划，阅读当前文档，把“苹果是蔬菜”改成“苹果是水果”，保存文档，并根据每一步的实际工具结果更新待办状态。",
                "mode": "AGENT", "model": "deepseek-chat",
                "clientContext": {"activeDocument": {"documentId": document_id, "type": "markdown"}},
            })
            assert stream.status_code == 200, stream.text[:300]
            events = [json.loads(line[6:]) for line in stream.text.splitlines()
                      if line.startswith("data: {")]
            calls = [item["name"] for item in events if item.get("type") == "tool_call"]
            plans = [json.loads(item["result_json"])["todos"] for item in events
                     if item.get("type") == "tool_result" and item.get("name") == "write_todos"
                     and json.loads(item["result_json"]).get("success") is True]
            saved = client.get(f"/api/documents/{document_id}", headers=headers)
            assert saved.status_code == 200
            print("planning tool calls=", calls, "plan_updates=", len(plans),
                  "last_statuses=", [todo["status"] for todo in plans[-1]] if plans else [],
                  "document_version=", saved.json()["data"]["version"],
                  "done=", "event: done" in stream.text)
            assert calls and calls[0] == "write_todos"
            assert len(plans) >= 2
            assert "document_save" in calls
            assert all(todo["status"] == "completed" for todo in plans[-1])
            assert "苹果是蔬菜" not in saved.json()["data"]["draftContent"]
            assert saved.json()["data"]["version"] > 1
            assert "event: done" in stream.text
    finally:
        auth_redis_repository.revoke_web_session(token)
        if project_id is not None:
            with get_engine().begin() as db:
                db.execute(text("DELETE FROM backend_data.projects WHERE id = :id AND owner_id = :user_id"),
                           {"id": project_id, "user_id": user_id})


if __name__ == "__main__":
    main()
