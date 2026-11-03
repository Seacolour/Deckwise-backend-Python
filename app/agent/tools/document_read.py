"""LangChain document-read tool scoped to one user's project."""

import json

from langchain_core.tools import BaseTool, tool

from app.core.exceptions import BusinessError
from app.agent.tools.document_edit_session import DocumentEditSession
from app.services import document_service


def make_document_read_tool(user_id: int, project_id: int, edit_sessions: dict[int, DocumentEditSession]) -> BaseTool:
    @tool
    def document_read(document_id: int) -> str:
        """Read the full Markdown draft and current version of a document in this project.

        Call this before editing so document_save can use the latest version.
        """
        try:
            document = document_service.get_document(
                user_id, document_id, False, expected_project_id=project_id,
            )
        except BusinessError as error:
            return json.dumps({"success": False, "error": error.message}, ensure_ascii=False)
        content = document.draftContent or ""
        if len(content) > 80_000:
            return json.dumps({"success": False, "error": "文档过长，当前 Agent 无法安全读取完整草稿"}, ensure_ascii=False)
        edit_sessions[document_id] = DocumentEditSession(document.version, content, full_read=True)
        return json.dumps({
            "success": True, "document_id": document.id,
            "title": document.title, "version": document.version,
            "draft_content": content,
        }, ensure_ascii=False)

    return document_read
