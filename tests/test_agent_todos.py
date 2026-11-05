"""A Todo plan updates LangGraph state and survives the model/tool loop."""

import asyncio
import json

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool

from app.agent.graph import build_agent_graph
from app.agent.tools import tools_for_project
from app.agent.tools.write_todos import write_todos


def test_todos_progress_with_real_tool_results() -> None:
    @tool
    def echo(value: str) -> str:
        """Return a small tool result."""
        return value

    plan = [{"content": "读取资料", "status": "in_progress"},
            {"content": "生成摘要", "status": "pending"}]

    class Model:
        def bind_tools(self, tools):
            assert {item.name for item in tools} == {"write_todos", "echo"}
            return self

        async def ainvoke(self, messages):
            results = [item for item in messages if isinstance(item, ToolMessage)]
            match len(results):
                case 0:
                    name, args = "write_todos", {"todos": plan}
                case 1:
                    name, args = "echo", {"value": "资料已读"}
                case 2:
                    name, args = "write_todos", {"todos": [
                        {"content": "读取资料", "status": "completed"},
                        {"content": "生成摘要", "status": "in_progress"},
                    ]}
                case 3:
                    name, args = "echo", {"value": "摘要已生成"}
                case 4:
                    name, args = "write_todos", {"todos": [
                        {"content": "读取资料", "status": "completed"},
                        {"content": "生成摘要", "status": "completed"},
                    ]}
                case _:
                    assert "本轮计划" in messages[0].content
                    return AIMessage(content="已完成摘要。")
            return AIMessage(content="", tool_calls=[{
                "name": name, "args": args, "id": f"call-{len(results)}",
            }])

    graph = build_agent_graph(Model(), [write_todos, echo], "AGENT", 7, 11)
    result = asyncio.run(graph.ainvoke({
        "messages": [HumanMessage(content="读取资料并生成摘要")],
        "active_document_id": None, "tool_rounds": 0, "todos": [],
    }))
    assert result["todos"] == [
        {"content": "读取资料", "status": "completed"},
        {"content": "生成摘要", "status": "completed"},
    ]
    assert result["tool_rounds"] == 5
    assert result["messages"][-1].content == "已完成摘要。"
    updates = [json.loads(item.content) for item in result["messages"]
               if isinstance(item, ToolMessage) and item.name == "write_todos"]
    assert [item["todos"][0]["status"] for item in updates] == [
        "in_progress", "completed", "completed",
    ]


@pytest.mark.parametrize("bad_todos", [
    [{"content": "第一步", "status": "in_progress"}, {"content": "第二步", "status": "in_progress"}],
    [{"content": f"步骤 {index}", "status": "pending"} for index in range(7)],
    [{"content": " ", "status": "pending"}, {"content": "第二步", "status": "pending"}],
])
def test_invalid_plan_does_not_change_state(bad_todos) -> None:
    class Model:
        def bind_tools(self, _tools):
            return self

        async def ainvoke(self, messages):
            if any(isinstance(item, ToolMessage) for item in messages):
                return AIMessage(content="计划无效。")
            return AIMessage(content="", tool_calls=[{
                "name": "write_todos", "args": {"todos": bad_todos}, "id": "invalid-plan",
            }])

    graph = build_agent_graph(Model(), [write_todos], "AGENT", 7, 11)
    result = asyncio.run(graph.ainvoke({
        "messages": [HumanMessage(content="做两个任务")],
        "active_document_id": None, "tool_rounds": 0, "todos": [],
    }))
    assert result["todos"] == []
    feedback = next(item for item in result["messages"] if isinstance(item, ToolMessage))
    assert json.loads(feedback.content)["success"] is False


def test_update_cannot_rewrite_existing_step() -> None:
    initial = [{"content": "读取资料", "status": "in_progress"},
               {"content": "整理结论", "status": "pending"}]

    class Model:
        def bind_tools(self, _tools):
            return self

        async def ainvoke(self, messages):
            results = [item for item in messages if isinstance(item, ToolMessage)]
            if not results:
                todos = initial
            elif len(results) == 1:
                todos = [{"content": "更换目标", "status": "completed"}, initial[1]]
            else:
                return AIMessage(content="计划更新被拒绝。")
            return AIMessage(content="", tool_calls=[{
                "name": "write_todos", "args": {"todos": todos}, "id": f"plan-{len(results)}",
            }])

    graph = build_agent_graph(Model(), [write_todos], "AGENT", 7, 11)
    result = asyncio.run(graph.ainvoke({
        "messages": [HumanMessage(content="分步处理")],
        "active_document_id": None, "tool_rounds": 0, "todos": [],
    }))
    assert result["todos"] == initial
    feedback = [item for item in result["messages"] if isinstance(item, ToolMessage)]
    assert json.loads(feedback[-1].content)["success"] is False


def test_todo_tool_is_agent_only() -> None:
    assert "write_todos" not in {item.name for item in tools_for_project(7, 11, "ASK")}
    assert "write_todos" in {item.name for item in tools_for_project(7, 11, "AGENT")}


def test_todo_command_and_regular_tool_results_both_survive_a_batch() -> None:
    @tool
    def echo(value: str) -> str:
        """Return an ordinary tool result."""
        return value

    class Model:
        def bind_tools(self, _tools):
            return self

        async def ainvoke(self, messages):
            if any(isinstance(item, ToolMessage) for item in messages):
                return AIMessage(content="继续处理。")
            return AIMessage(content="", tool_calls=[
                {"name": "write_todos", "args": {"todos": [
                    {"content": "读取", "status": "in_progress"},
                    {"content": "总结", "status": "pending"},
                ]}, "id": "plan"},
                {"name": "echo", "args": {"value": "ready"}, "id": "ordinary"},
            ])

    graph = build_agent_graph(Model(), [write_todos, echo], "AGENT", 7, 11)
    result = asyncio.run(graph.ainvoke({
        "messages": [HumanMessage(content="读取并总结")],
        "active_document_id": None, "tool_rounds": 0, "todos": [],
    }))
    assert result["todos"][0]["status"] == "in_progress"
    assert {item.name for item in result["messages"] if isinstance(item, ToolMessage)} == {
        "write_todos", "echo",
    }
