"""LangChain document-save tool using the existing versioned service."""

import json

from langchain_core.tools import BaseTool, tool

from app.agent.tools.document_edit_session import DocumentEditSession
from app.core.exceptions import BusinessError
from app.schemas.document import DocumentDraftUpdateRequest
from app.services import document_service


def make_document_save_tool(user_id: int, project_id: int, edit_sessions: dict[int, DocumentEditSession]) -> BaseTool:
    @tool
    def document_save(document_id: int, version: int, draft_content: str | None = None) -> str:
        """Persist a document_diff working copy, or a complete draft after document_read.

        Omit draft_content to save pending document_diff changes. A stale version
        is rejected; read the document again before retrying.
        """
        session = edit_sessions.get(document_id)
        if session is None or session.version != version:
            return json.dumps({
                "success": False, "error": "请先读取文档当前版本再保存",
                "code": 40903, "document_id": document_id,
            }, ensure_ascii=False)
        if session.modified:
            if draft_content is not None:
                return json.dumps({"success": False, "error": "已有局部修改，请省略 draft_content 以保存工作副本"}, ensure_ascii=False)
            content = session.content
        elif draft_content is not None:
            if not session.full_read:
                return json.dumps({"success": False, "error": "提交整份草稿前必须调用 document_read"}, ensure_ascii=False)
            content = draft_content
        else:
            return json.dumps({"success": False, "error": "没有待保存的修改"}, ensure_ascii=False)
        if len(content) > 500_000:
            return json.dumps({"success": False, "error": "文档过长，未保存"}, ensure_ascii=False)
        try:
            saved = document_service.update_draft(
                user_id, document_id,
                DocumentDraftUpdateRequest(version=version, draftContent=content),
                expected_project_id=project_id,
            )
        except BusinessError as error:
            return json.dumps({
                "success": False, "error": error.message, "code": int(error.code),
                "document_id": document_id,
            }, ensure_ascii=False)
        edit_sessions.pop(document_id, None)
        return json.dumps({
            "success": True, "document_id": saved.id, "version": saved.version,
        }, ensure_ascii=False)

    return document_save
