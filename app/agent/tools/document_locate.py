"""Locate exact source lines before a small document edit."""

import json

from langchain_core.tools import BaseTool, tool

from app.agent.tools.document_edit_session import DocumentEditSession
from app.core.exceptions import BusinessError
from app.services import document_service


def make_document_locate_tool(
    user_id: int, project_id: int, edit_sessions: dict[int, DocumentEditSession],
) -> BaseTool:
    @tool
    def document_locate(document_id: int, query: str, max_results: int = 3, context_lines: int = 2) -> str:
        """Find lines containing query; return exact before text and 1-based line numbers.

        Pass a returned before value and start_line to document_diff. If there
        are multiple matches, choose the intended one explicitly.
        """
        if not query.strip() or len(query) > 300:
            return json.dumps({"success": False, "error": "query 不能为空且最多 300 字符"}, ensure_ascii=False)
        try:
            document = document_service.get_document(
                user_id, document_id, False, expected_project_id=project_id,
            )
        except BusinessError as error:
            return json.dumps({"success": False, "error": error.message}, ensure_ascii=False)
        session = edit_sessions.get(document_id)
        if session is None:
            session = DocumentEditSession(document.version, document.draftContent or "")
            edit_sessions[document_id] = session
        # The working copy may be stale; document_save still checks its base version.
        lines = session.content.split("\n")
        limit = min(max(max_results, 1), 5)
        radius = min(max(context_lines, 0), 3)
        matches = []
        total = 0
        for index, line in enumerate(lines):
            if query not in line:
                continue
            total += 1
            if len(matches) < limit:
                editable = len(line) <= 2_000
                matches.append({
                    "start_line": index + 1,
                    "end_line": index + 1,
                    "before": line if editable else None,
                    "editable": editable,
                    "context_start_line": max(0, index - radius) + 1,
                    "context_lines": [item[:400] for item in lines[max(0, index - radius):index + radius + 1]],
                })
        return json.dumps({
            "success": True, "document_id": document_id,
            "version": session.version, "total_lines": len(lines),
            "total_matches": total, "matches": matches,
        }, ensure_ascii=False)

    return document_locate
