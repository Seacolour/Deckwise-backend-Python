"""Structured, per-turn Todo updates for multi-step Agent work."""

import json
from typing import Literal

from langchain.tools import ToolRuntime, tool
from langchain_core.messages import ToolMessage
from langgraph.types import Command
from pydantic import BaseModel, Field

MAX_TODOS = 6
_STATUS_ORDER = {"pending": 0, "in_progress": 1, "completed": 2}


class TodoItem(BaseModel):
    content: str = Field(description="Concise, concrete task step")
    status: Literal["pending", "in_progress", "completed"] = "pending"


@tool
def write_todos(todos: list[TodoItem], runtime: ToolRuntime) -> Command | str:
    """Create or update 2–6 Todo steps for this Agent turn. Call alone; update statuses after tool results."""
    proposed = [TodoItem.model_validate(item).model_dump() for item in todos]
    for item in proposed:
        item["content"] = item["content"].strip()
    if not 2 <= len(proposed) <= MAX_TODOS or any(
        not item["content"].strip() or len(item["content"]) > 120 for item in proposed
    ):
        return json.dumps({"success": False, "error": "计划须包含 2–6 个不超过 120 字的步骤"}, ensure_ascii=False)
    if len({item["content"].strip() for item in proposed}) != len(proposed):
        return json.dumps({"success": False, "error": "计划步骤不能重复"}, ensure_ascii=False)
    if sum(item["status"] == "in_progress" for item in proposed) > 1:
        return json.dumps({"success": False, "error": "同一时间只能有一个执行中步骤"}, ensure_ascii=False)
    current = runtime.state.get("todos") or []
    if current:
        if [item["content"] for item in current] != [item["content"] for item in proposed]:
            return json.dumps({"success": False, "error": "基础版计划只能更新状态，不能改写步骤"}, ensure_ascii=False)
        if any(_STATUS_ORDER[new["status"]] < _STATUS_ORDER[old["status"]]
               for old, new in zip(current, proposed)):
            return json.dumps({"success": False, "error": "已推进的步骤不能退回旧状态"}, ensure_ascii=False)
    elif any(item["status"] == "completed" for item in proposed):
        return json.dumps({"success": False, "error": "创建计划时不能直接标记步骤完成"}, ensure_ascii=False)
    result = json.dumps({"success": True, "todos": proposed}, ensure_ascii=False)
    return Command(update={
        "todos": proposed,
        "messages": [ToolMessage(content=result, tool_call_id=runtime.tool_call_id)],
    })
