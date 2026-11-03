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
