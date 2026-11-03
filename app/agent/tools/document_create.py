"""Create a Markdown document inside the current project."""

import json

from langchain_core.tools import BaseTool, tool

from app.core.exceptions import BusinessError
from app.schemas.document import DocumentCreateRequest
from app.services import document_service


def make_document_create_tool(user_id: int, project_id: int) -> BaseTool:
    @tool
    def document_create(title: str, content: str = "") -> str:
        """Create a Markdown document in this project with a title and optional initial content."""
        if len(content) > 80_000:
            return json.dumps({"success": False, "error": "初始内容过长"}, ensure_ascii=False)
        try:
            created = document_service.create_document(
                user_id, DocumentCreateRequest(projectId=project_id, title=title, draftContent=content),
            )
        except (BusinessError, ValueError) as error:
            return json.dumps({"success": False, "error": getattr(error, "message", "文档参数无效")}, ensure_ascii=False)
        return json.dumps({"success": True, "document_id": created.id,
                           "title": created.title, "version": created.version}, ensure_ascii=False)

    return document_create
