"""A connected user's Notion MCP reads are bound into the actual SSE graph turn."""

import asyncio
import json
from contextlib import contextmanager
from types import SimpleNamespace

from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import tool

from app.schemas.agent import UserMessageSendRequest
from app.services import agent_service


def test_agent_turn_discovers_notion_for_authorized_user(monkeypatch) -> None:
    @tool("notion-search")
    async def search(query: str) -> list[dict]:
        """Search a Notion page."""
        return [{"type": "text", "text": f"found page for {query}"}]

    @tool("notion-fetch")
    async def fetch(id: str) -> list[dict]:
        """Read a Notion page."""
        return [{"type": "text", "text": id}]

    class Adapter:
        def __init__(self, _client):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        async def list_tools(self):
            return [search, fetch]

    class Model:
        def bind_tools(self, tools):
            assert {"notion_search", "notion_fetch"} <= {item.name for item in tools}
            assert "notion-delete-pages" not in {item.name for item in tools}
            return self

        async def ainvoke(self, messages):
            if any(isinstance(item, ToolMessage) for item in messages):
                return AIMessage(content="已读取 Notion 来源。")
            return AIMessage(content="", tool_calls=[{
                "name": "notion_search", "args": {"query": "Agent"}, "id": "notion-call",
            }])

    @contextmanager
    def fake_session():
        yield object()

    class Request:
        app = SimpleNamespace(state=SimpleNamespace(checkpointer=None))

        async def is_disconnected(self):
            return False

    persisted = []
    monkeypatch.setattr(agent_service, "session_scope", fake_session)
    monkeypatch.setattr(agent_service.session_service, "require_owned_session",
                        lambda _db, _user_id, _session_id: SimpleNamespace(project_id=11))
    monkeypatch.setattr(agent_service.session_service, "prepare_turn",
                        lambda *_args, **_kwargs: (11, []))
    monkeypatch.setattr(agent_service.session_service, "persist_turn_events",
                        lambda *_args: persisted.append(_args))
    monkeypatch.setattr(agent_service.model_service, "resolve_chat_model", lambda *_args: Model())
    monkeypatch.setattr(agent_service.model_credential_service, "configured_providers", lambda *_args: set())
    monkeypatch.setattr(agent_service.agent_plugin_service, "enabled_plugin_ids", lambda *_args: {"notion"})
    monkeypatch.setattr(agent_service.notion_mcp_connection_service, "access_token", lambda *_args: "demo-token")
    import langchain.mcp
    monkeypatch.setattr(langchain.mcp, "MCPAdapter", Adapter)

    async def run():
        body = UserMessageSendRequest(message="查询我的 Notion Agent 页面", model="demo")
        result = await agent_service.start_turn(7, 13, body, Request())
        return [frame async for frame in result]

    frames = asyncio.run(run())
    events = [json.loads(frame[6:]) for frame in frames if frame.startswith("data: ") and "[DONE]" not in frame]
    assert any(item.get("type") == "tool_call" and item.get("name") == "notion_search" for item in events)
    assert any(item.get("type") == "tool_result" and item.get("name") == "notion_search" for item in events)
    assert any(item.get("type") == "text" and "已读取 Notion" in item.get("payload", "") for item in events)
    assert persisted and persisted[0][-1] == "final"
