"""Only approved Notion MCP reads can join a user's LangGraph turn."""

import asyncio
import json

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool

from app.agent.graph import build_agent_graph
from app.agent.tools.notion_mcp import make_notion_read_tools
from app.core.exceptions import BusinessError
from app.services import agent_plugin_service


def _discovered():
    @tool("notion-search")
    async def search(query: str) -> list[dict]:
        """Search Notion."""
        return [{"type": "text", "text": f"page-1: {query}"}]

    @tool("notion-fetch")
    async def fetch(id: str) -> list[dict]:
        """Fetch a Notion page."""
        return [{"type": "text", "text": f"{id}: Notion 方案"}]

    @tool("notion-delete-pages")
    async def delete(id: str) -> str:
        """Delete a page."""
        raise AssertionError("write tool must never be exposed")

    return [search, fetch, delete]


def test_notion_read_allowlist_requires_both_tools(monkeypatch) -> None:
    monkeypatch.setattr(agent_plugin_service, "enabled_plugin_ids", lambda _user_id: set())
    with pytest.raises(BusinessError):
        make_notion_read_tools(7, _discovered()[:1])
    tools = make_notion_read_tools(7, _discovered())
    assert {item.name for item in tools} == {"notion_search", "notion_fetch"}
    blocked = json.loads(asyncio.run(tools[0].ainvoke({"query": "Agent"})))
    assert blocked["success"] is False


def test_langgraph_uses_notion_and_local_search_without_write_tools(monkeypatch) -> None:
    monkeypatch.setattr(agent_plugin_service, "enabled_plugin_ids", lambda _user_id: {"notion"})
    notion_tools = make_notion_read_tools(7, _discovered())

    @tool
    def semantic_file_search(query: str) -> str:
        """Search the current project."""
        return f"项目资料：{query}"

    class Model:
        def bind_tools(self, tools):
            assert {item.name for item in tools} == {
                "notion_search", "notion_fetch", "semantic_file_search",
            }
            return self

        async def ainvoke(self, messages):
            results = [item for item in messages if isinstance(item, ToolMessage)]
            if len(results) == 0:
                return AIMessage(content="", tool_calls=[
                    {"name": "notion_search", "args": {"query": "Agent"}, "id": "n-search"},
                    {"name": "semantic_file_search", "args": {"query": "Agent"}, "id": "local-search"},
                ])
            if len(results) == 2:
                return AIMessage(content="", tool_calls=[
                    {"name": "notion_fetch", "args": {"id": "page-1"}, "id": "n-fetch"},
                ])
            return AIMessage(content="已比较 Notion 与项目资料。")

    graph = build_agent_graph(Model(), [*notion_tools, semantic_file_search], "ASK", 7, 11)
    result = asyncio.run(graph.ainvoke({
        "messages": [HumanMessage(content="比较两份 Agent 方案")],
        "active_document_id": None, "tool_rounds": 0,
    }))
    assert [item.name for item in result["messages"] if isinstance(item, ToolMessage)] == [
        "notion_search", "semantic_file_search", "notion_fetch",
    ]
    assert "Notion 方案" in result["messages"][-2].content
    assert result["messages"][-1].content == "已比较 Notion 与项目资料。"
