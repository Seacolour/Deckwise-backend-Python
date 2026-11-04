"""Verify the graph's model/tool loop and document write guard without a provider key."""

import asyncio
import json

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool

from app.agent.graph import build_agent_graph
from app.agent.tools import tools_for_project


class ScriptedModel:
    def bind_tools(self, _tools):
        return self

    async def ainvoke(self, messages):
        if any(isinstance(message, ToolMessage) for message in messages):
            return AIMessage(content="工具已执行")
        return AIMessage(content="", tool_calls=[{
            "name": "echo", "args": {"value": "ok"}, "id": "call-1",
        }])


def test_langgraph_runs_model_tool_model() -> None:
    @tool
    def echo(value: str) -> str:
        """Return a value to the model."""
        return value

    graph = build_agent_graph(ScriptedModel(), [echo], "AGENT", 1, 1)
    result = asyncio.run(graph.ainvoke({
        "messages": [HumanMessage(content="test")], "active_document_id": None,
        "tool_rounds": 0,
    }))
    assert [type(message) for message in result["messages"]] == [
        HumanMessage, AIMessage, ToolMessage, AIMessage,
    ]
    assert result["messages"][2].content == "ok"
    assert result["messages"][-1].content == "工具已执行"


def test_document_save_requires_a_successful_read() -> None:
    tools = tools_for_project(1, 1, "AGENT")
    save = next(item for item in tools if item.name == "document_save")
    result = json.loads(save.invoke({
        "document_id": 1, "version": 1, "draft_content": "unsafe",
    }))
    assert result["success"] is False and result["code"] == 40903
    assert all(item.name != "document_save" for item in tools_for_project(1, 1, "ASK"))


def test_semantic_search_is_only_registered_when_embeddings_are_available() -> None:
    ordinary = {item.name for item in tools_for_project(1, 1, "ASK")}
    enabled = {item.name for item in tools_for_project(1, 1, "ASK", semantic_search_enabled=True)}
    assert "semantic_file_search" not in ordinary
    assert "semantic_file_search" in enabled


def test_agent_can_use_semantic_search_tool(monkeypatch) -> None:
    from app.services import rag_service

    async def fake_search(user_id, project_id, query, limit=3, cache_key=None):
        assert (user_id, project_id, query, limit, cache_key) == (7, 11, "苹果", 3, None)
        return {"matches": [{"file_name": "fruit.txt", "snippet": "苹果属于水果"}],
                "indexed_new": 1, "total_fragments": 1}

    class RagModel:
        def bind_tools(self, tools):
            assert "semantic_file_search" in {item.name for item in tools}
            return self

        async def ainvoke(self, messages):
            if any(isinstance(item, ToolMessage) for item in messages):
                return AIMessage(content="资料说明苹果属于水果。")
            return AIMessage(content="", tool_calls=[{
                "name": "semantic_file_search", "args": {"query": "苹果"}, "id": "rag-call",
            }])

    monkeypatch.setattr(rag_service, "search_project_files", fake_search)
    graph = build_agent_graph(RagModel(), tools_for_project(7, 11, "ASK", semantic_search_enabled=True),
                              "ASK", 7, 11)
    result = asyncio.run(graph.ainvoke({
        "messages": [HumanMessage(content="苹果是什么？")], "active_document_id": None,
        "tool_rounds": 0,
    }))
    assert json.loads(result["messages"][2].content)["matches"][0]["file_name"] == "fruit.txt"
    assert result["messages"][-1].content == "资料说明苹果属于水果。"


def test_image_url_reaches_model_without_entering_graph_state() -> None:
    class RecordingModel:
        def __init__(self):
            self.messages = []

        def bind_tools(self, _tools):
            return self

        async def ainvoke(self, messages):
            self.messages = messages
            return AIMessage(content="看到了图片")

    model = RecordingModel()
    graph = build_agent_graph(model, [], "ASK", 1, 1,
                              image_urls=["https://private.example.test/image.png"])
    result = asyncio.run(graph.ainvoke({
        "messages": [HumanMessage(content="图中是什么？")], "active_document_id": None,
        "tool_rounds": 0,
    }))
    assert result["messages"][0].content == "图中是什么？"
    input_blocks = model.messages[-1].content
    assert input_blocks[0] == {"type": "text", "text": "图中是什么？"}
    assert input_blocks[1]["image_url"]["url"] == "https://private.example.test/image.png"
