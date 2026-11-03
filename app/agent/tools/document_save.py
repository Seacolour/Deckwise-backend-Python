"""LangChain document-save tool using the existing versioned service."""

import json

from langchain_core.tools import BaseTool, tool

from app.core.exceptions import BusinessError
from app.schemas.document import DocumentDraftUpdateRequest
from app.services import document_service


def make_document_save_tool(user_id: int, project_id: int, read_versions: dict[int, int]) -> BaseTool:
    @tool
    def document_save(document_id: int, version: int, draft_content: str) -> str:
        """Replace a Markdown draft with complete content using the version from document_read.

        A stale version is rejected. Read the document again before retrying.
        """
        if len(draft_content) > 80_000:
            return json.dumps({"success": False, "error": "文档过长，未保存"}, ensure_ascii=False)
        if read_versions.get(document_id) != version:
            return json.dumps({
                "success": False, "error": "请先读取文档当前版本再保存",
                "code": 40903, "document_id": document_id,
            }, ensure_ascii=False)
        read_versions.pop(document_id, None)
        try:
            saved = document_service.update_draft(
                user_id, document_id,
                DocumentDraftUpdateRequest(version=version, draftContent=draft_content),
                expected_project_id=project_id,
            )
        except BusinessError as error:
            return json.dumps({
                "success": False, "error": error.message, "code": int(error.code),
                "document_id": document_id,
            }, ensure_ascii=False)
        return json.dumps({
            "success": True, "document_id": saved.id, "version": saved.version,
        }, ensure_ascii=False)

    return document_save
