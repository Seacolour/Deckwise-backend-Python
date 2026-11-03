"""Run a document edit through FastAPI, then inspect persistence."""

import asyncio
import json
import os
import secrets
import sys
from pathlib import Path

from fastapi.testclient import TestClient
import httpx
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.security import COOKIE_NAME, new_session_token  # noqa: E402
from app.db.checkpoint import (  # noqa: E402
    checkpoint_enabled, checkpoint_thread_id, open_checkpointer, selector_loop_factory,
)
from app.db.session import get_engine  # noqa: E402
from app.main import app  # noqa: E402
from app.repositories import auth_redis_repository  # noqa: E402
from app.services.model_service import available_models  # noqa: E402
from app.services import model_service  # noqa: E402
from app.agent.tools import tools_for_project  # noqa: E402


class ScriptedDocumentModel:
    """Exercise the real graph and tools without provider availability."""

    def __init__(self, document_id: int):
        self.document_id = document_id
        self.read_only = False

    def bind_tools(self, tools):
        self.read_only = all(item.name != "document_save" for item in tools)
        return self

    async def ainvoke(self, messages):
        if self.read_only:
            return AIMessage(content="当前文档已有测试内容。")
        results = [item for item in messages if isinstance(item, ToolMessage)]
        if not results:
            return AIMessage(content="", tool_calls=[{
                "name": "document_read", "args": {"document_id": self.document_id}, "id": "read-1",
            }])
        latest = json.loads(results[-1].content)
        if "draft_content" in latest:
            return AIMessage(content="", tool_calls=[{
                "name": "document_save",
                "args": {"document_id": self.document_id, "version": latest["version"],
                         "draft_content": latest["draft_content"] + "本轮联调成功。\n"},
                "id": "save-1",
            }])
        return AIMessage(content="已保存。")


def main() -> None:
    models = available_models()
    if not models:
        raise SystemExit("No configured conversation model in .env")
    email = f"agent-check-{secrets.token_hex(8)}@example.test"
    token = new_session_token()
    with get_engine().begin() as connection:
        user_id = connection.scalar(text("""
            INSERT INTO backend_data.users (email, email_verified, sign_up_provider)
            VALUES (:email, true, 'email') RETURNING id
        """), {"email": email})
    auth_redis_repository.create_web_session(token, user_id)
    headers = {"cookie": f"{COOKIE_NAME}={token}"}
    session_id: str | None = None
    original_model_resolver = model_service.resolve_chat_model
    try:
        base_url = os.getenv("DECKWISE_CHECK_BASE_URL")
        client_context = (httpx.Client(base_url=base_url, timeout=120) if base_url
                          else TestClient(app, backend_options={"loop_factory": selector_loop_factory}))
        with client_context as client:
            project = client.post("/api/projects/create", json={"name": "Agent 联调"}, headers=headers)
            assert project.status_code == 200, project.text
            project_id = project.json()["data"]["id"]
            document = client.post("/api/documents/create", headers=headers, json={
                "projectId": project_id, "title": "测试文章", "draftContent": "# 测试文章\n\n原有内容。\n",
            })
            assert document.status_code == 200, document.text
            document_id = document.json()["data"]["id"]
            session = client.post(f"/api/projects/{project_id}/create", headers=headers,
                                  json={"title": "编辑测试文章"})
            assert session.status_code == 200, session.text
            session_id = session.json()["data"]["id"]
            if os.getenv("DECKWISE_TEST_FAKE_MODEL") == "1":
                model_service.resolve_chat_model = lambda _model_id: ScriptedDocumentModel(int(document_id))

            stream_prefix = "/sse" if os.getenv("DECKWISE_CHECK_WEB_PROXY") == "1" else "/api"
            stream = client.post(f"{stream_prefix}/sessions/{session_id}/sendRPC", headers=headers, json={
                "message": "请修改当前文档：在末尾添加一行‘本轮联调成功。’，保留原有内容。完成后说明已保存。",
                "mode": "AGENT", "model": models[0].id,
                "clientContext": {"activeDocument": {"documentId": document_id, "type": "markdown"}},
            })
            assert stream.status_code == 200, stream.text[:1000]
            assert "event: done" in stream.text, stream.text[-1000:]
            events = [json.loads(line[6:]) for line in stream.text.splitlines()
                      if line.startswith("data: {")]
            event_types = [event["type"] for event in events]
            names = [event.get("name") for event in events if event["type"] in {"tool_call", "tool_result"}]
            updated = client.get(f"/api/documents/{document_id}", headers=headers)
            history = client.get(f"/api/sessions/{session_id}/messages/after-seq", headers=headers)
            print("SSE event types:", event_types)
            print("SSE tool names:", names)
            print("document version:", updated.json()["data"]["version"])
            assert "document_read" in names and "document_save" in names
            assert "本轮联调成功。" in updated.json()["data"]["draftContent"]
            assert updated.json()["data"]["version"] == 2
            assert history.status_code == 200 and len(history.json()["data"]) >= 3, history.text
            assert any(item["role"] == "assistant" and item["type"] == "text"
                       for item in history.json()["data"])
            ask = client.post(f"{stream_prefix}/sessions/{session_id}/sendRPC", headers=headers, json={
                "message": "请用一句话概括当前文档。不要修改。",
                "mode": "ASK", "model": models[0].id,
                "clientContext": {"activeDocument": {"documentId": document_id, "type": "markdown"}},
            })
            assert ask.status_code == 200 and "event: done" in ask.text, ask.text[-1000:]
            assert '"name":"document_save"' not in ask.text
            assert client.get(f"/api/documents/{document_id}", headers=headers).json()["data"]["version"] == 2
            assert client.post(f"/api/sessions/{session_id}/abort", headers=headers, json={}).status_code == 200
            scoped_tools = tools_for_project(user_id, int(project_id), "AGENT")
            read_tool = next(tool for tool in scoped_tools if tool.name == "document_read")
            other_project = client.post("/api/projects/create", json={"name": "其他项目"}, headers=headers)
            other_project_id = other_project.json()["data"]["id"]
            other_document = client.post("/api/documents/create", headers=headers, json={
                "projectId": other_project_id, "title": "隔离文档", "draftContent": "不能跨项目读取",
            })
            other_document_id = other_document.json()["data"]["id"]
            denied = json.loads(read_tool.invoke({"document_id": int(other_document_id)}))
            assert denied["success"] is False
            read = json.loads(read_tool.invoke({"document_id": int(document_id)}))
            assert read["success"] and read["version"] == 2
            external = client.put(f"/api/documents/{document_id}/draft", headers=headers,
                                  json={"version": 2, "draftContent": "外部更新"})
            assert external.status_code == 200 and external.json()["data"]["version"] == 3
            stale = json.loads(scoped_tools[-1].invoke({
                "document_id": int(document_id), "version": 2, "draft_content": "旧内容",
            }))
            assert stale["success"] is False and stale["code"] == 40903, stale
            current = client.get(f"/api/documents/{document_id}", headers=headers).json()["data"]
            assert current["version"] == 3 and current["draftContent"] == "外部更新"
            print("Agent flow OK: model tools, SSE, persisted document and messages")
        if checkpoint_enabled():
            async def inspect_state() -> None:
                async with open_checkpointer() as saver:
                    config = {"configurable": {"thread_id": checkpoint_thread_id(user_id, int(session_id))}}
                    saved = await saver.aget_tuple(config)
                    assert saved is not None
                    messages = saved.checkpoint["channel_values"]["messages"]
                    assert sum(isinstance(item, HumanMessage) for item in messages) == 2
                    thread_id = config["configurable"]["thread_id"]
                    with get_engine().connect() as db:
                        before = db.scalar(text("SELECT count(*) FROM public.checkpoints WHERE thread_id = :id"),
                                           {"id": thread_id})
                    await saver.aprune([thread_id], strategy="keep_latest")
                    pruned = await saver.aget_tuple(config)
                    assert pruned is not None
                    assert sum(isinstance(item, HumanMessage)
                               for item in pruned.checkpoint["channel_values"]["messages"]) == 2
                    with get_engine().connect() as db:
                        after = db.scalar(text("SELECT count(*) FROM public.checkpoints WHERE thread_id = :id"),
                                          {"id": thread_id})
                    assert before > after == 1
                    print(f"checkpoint flow OK: two turns restored, rows {before}->{after} after prune")
            asyncio.run(inspect_state(), loop_factory=selector_loop_factory)
    finally:
        model_service.resolve_chat_model = original_model_resolver
        if checkpoint_enabled() and session_id is not None:
            async def remove_state() -> None:
                async with open_checkpointer() as saver:
                    await saver.adelete_thread(checkpoint_thread_id(user_id, int(session_id)))
            asyncio.run(remove_state(), loop_factory=selector_loop_factory)
        auth_redis_repository.revoke_web_session(token)
        with get_engine().begin() as connection:
            connection.execute(text("DELETE FROM backend_data.users WHERE email = :email"), {"email": email})


if __name__ == "__main__":
    main()
