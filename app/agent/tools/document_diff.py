"""Apply exact line edits to a per-turn working copy; never write the database."""

import json
from typing import Literal

from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, Field

from app.agent.tools.document_edit_session import DocumentEditSession


class EditHunk(BaseModel):
    op: Literal["INSERT", "DELETE", "REPLACE"]
    before: str = Field(min_length=1, max_length=5_000, description="Exact source line or lines from document_locate")
    after: str = Field(default="", max_length=5_000, description="Replacement lines, or lines inserted after before")
    start_line: int | None = Field(default=None, ge=1, description="1-based line from document_locate; required when before repeats")


def make_document_diff_tool(edit_sessions: dict[int, DocumentEditSession]) -> BaseTool:
    @tool
    def document_diff(document_id: int, hunks: list[EditHunk]) -> str:
        """Apply small line edits to the working copy after document_read or document_locate.

        Each before must match exact complete lines. INSERT adds after below
        the anchor line; REPLACE substitutes before; DELETE removes before.
        Call document_save with the same version and no draft_content to persist.
        """
        session = edit_sessions.get(document_id)
        if session is None:
            return json.dumps({"success": False, "error": "请先读取或定位文档", "code": 40903}, ensure_ascii=False)
        if not hunks or len(hunks) > 10:
            return json.dumps({"success": False, "error": "每次需提供 1 到 10 个修改块"}, ensure_ascii=False)
        lines = session.content.split("\n")
        for number, hunk in enumerate(hunks, start=1):
            before = hunk.before.split("\n")
            candidates = [index for index in range(len(lines) - len(before) + 1)
                          if lines[index:index + len(before)] == before]
            if hunk.start_line is not None:
                candidates = [index for index in candidates if index + 1 == hunk.start_line]
            if len(candidates) != 1:
                return json.dumps({
                    "success": False, "error": "原文不匹配或匹配位置不唯一，请重新定位",
                    "hunk_index": number, "matches": len(candidates),
                }, ensure_ascii=False)
            index = candidates[0]
            if hunk.op == "REPLACE":
                replacement = hunk.after.split("\n")
            elif hunk.op == "DELETE":
                replacement = []
            else:
                replacement = [*before, *hunk.after.split("\n")]
            lines[index:index + len(before)] = replacement
        content = "\n".join(lines)
        if len(content) > 500_000:
            return json.dumps({"success": False, "error": "修改后文档过长"}, ensure_ascii=False)
        session.content = content
        session.modified = True
        return json.dumps({
            "success": True, "document_id": document_id, "version": session.version,
            "applied_count": len(hunks), "must_call_document_save": True,
            "content_preview": content[:300],
        }, ensure_ascii=False)

    return document_diff
