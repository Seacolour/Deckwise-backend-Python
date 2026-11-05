"""Agent-facing user memory management through the shared business service."""

import json
from typing import Literal

from langchain_core.tools import BaseTool, tool

from app.core.error_codes import ErrorCode
from app.core.exceptions import BusinessError
from app.services import user_memory_service


def make_manage_user_memory_tool(user_id: int) -> BaseTool:
    @tool
    def manage_user_memory(
        action: Literal["create", "update", "delete", "list"],
        memory_id: int | None = None,
        title: str | None = None,
        content: str | None = None,
    ) -> str:
        """Manage stable facts about this user for future conversations. Never store secrets or temporary task text."""
        try:
            if action == "list":
                items = user_memory_service.list_memories(user_id)[:20]
                return json.dumps({"success": True, "memories": [
                    {"memory_id": item.id, "title": item.title,
                     "content": item.content[:500], "source": item.source}
                    for item in items
                ]}, ensure_ascii=False)
            if action == "create":
                if title is None or content is None:
                    raise ValueError("create requires title and content")
                item = user_memory_service.create_memory(user_id, title, content, source="ai")
                return json.dumps({"success": True, "memory_id": item.id,
                                   "title": item.title, "source": item.source}, ensure_ascii=False)
            if memory_id is None or memory_id <= 0:
                raise ValueError("update/delete requires memory_id")
            if action == "delete":
                user_memory_service.delete_memory(user_id, memory_id)
                return json.dumps({"success": True, "memory_id": memory_id}, ensure_ascii=False)
            if title is None and content is None:
                raise ValueError("update requires title or content")
            existing = next((item for item in user_memory_service.list_memories(user_id)
                             if item.id == str(memory_id)), None)
            if existing is None:
                raise BusinessError(404, ErrorCode.NOT_FOUND, "记忆不存在")
            updated = user_memory_service.update_memory(
                user_id, memory_id, title if title is not None else existing.title,
                content if content is not None else existing.content,
            )
            return json.dumps({"success": True, "memory_id": updated.id,
                               "title": updated.title, "source": updated.source}, ensure_ascii=False)
        except (BusinessError, ValueError) as error:
            return json.dumps({"success": False,
                               "error": error.message if isinstance(error, BusinessError) else str(error)},
                              ensure_ascii=False)

    return manage_user_memory
