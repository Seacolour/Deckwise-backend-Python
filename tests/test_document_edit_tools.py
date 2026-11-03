"""Local document edits must stay scoped, exact, and version checked."""

import json
from types import SimpleNamespace

from app.agent.tools import tools_for_project
from app.agent.tools.document_diff import make_document_diff_tool
from app.agent.tools.document_edit_session import DocumentEditSession
from app.core.error_codes import ErrorCode
from app.core.exceptions import BusinessError
from app.services import document_service


def _tool(tools, name):
    return next(item for item in tools if item.name == name)


def test_locate_diff_save_uses_project_and_version(monkeypatch) -> None:
    original = "# Report\nKeep this line\nTarget line\nFinal line"
    saved = []

    def get_document(user_id, document_id, _versions, expected_project_id):
        assert (user_id, document_id, expected_project_id) == (7, 21, 11)
        return SimpleNamespace(id="21", title="Report", version=3, draftContent=original)

    def update_draft(user_id, document_id, body, expected_project_id):
        saved.append((user_id, document_id, body.version, body.draftContent, expected_project_id))
        return SimpleNamespace(id="21", version=4)

    monkeypatch.setattr(document_service, "get_document", get_document)
    monkeypatch.setattr(document_service, "update_draft", update_draft)
    tools = tools_for_project(7, 11, "AGENT")

    located = json.loads(_tool(tools, "document_locate").invoke({
        "document_id": 21, "query": "Target",
    }))
    assert located["version"] == 3
    assert located["matches"][0]["start_line"] == 3
    assert located["matches"][0]["before"] == "Target line"
    full_replace_without_read = json.loads(_tool(tools, "document_save").invoke({
        "document_id": 21, "version": 3, "draft_content": "unsafe full replacement",
    }))
    assert full_replace_without_read["success"] is False and saved == []

    patched = json.loads(_tool(tools, "document_diff").invoke({
        "document_id": 21, "hunks": [{
            "op": "REPLACE", "before": "Target line", "after": "Changed line", "start_line": 3,
        }],
    }))
    assert patched["success"] and patched["must_call_document_save"]
    assert saved == []

    result = json.loads(_tool(tools, "document_save").invoke({"document_id": 21, "version": 3}))
    assert result["success"] and result["version"] == 4
    assert saved == [(7, 21, 3, original.replace("Target line", "Changed line"), 11)]


def test_diff_rejects_ambiguous_or_stale_hunks_atomically() -> None:
    sessions = {21: DocumentEditSession(3, "same\nsame\ntail")}
    diff = make_document_diff_tool(sessions)
    ambiguous = json.loads(diff.invoke({"document_id": 21, "hunks": [
        {"op": "REPLACE", "before": "same", "after": "changed"},
    ]}))
    assert ambiguous["success"] is False and ambiguous["matches"] == 2

    partial = json.loads(diff.invoke({"document_id": 21, "hunks": [
        {"op": "REPLACE", "before": "same", "after": "changed", "start_line": 1},
        {"op": "REPLACE", "before": "missing", "after": "wrong"},
    ]}))
    assert partial["success"] is False
    assert sessions[21].content == "same\nsame\ntail"
    assert sessions[21].modified is False


def test_create_uses_fixed_project_and_conflict_does_not_save(monkeypatch) -> None:
    created = []

    def create_document(user_id, body):
        created.append((user_id, body.projectId, body.title, body.draftContent))
        return SimpleNamespace(id="31", title=body.title, version=1)

    def get_document(_user_id, _document_id, _versions, expected_project_id):
        assert expected_project_id == 11
        return SimpleNamespace(id="21", title="Report", version=3, draftContent="old")

    def reject_update(*_args, **_kwargs):
        raise BusinessError(409, ErrorCode.REVISION_CONFLICT, "文档版本已变化")

    monkeypatch.setattr(document_service, "create_document", create_document)
    monkeypatch.setattr(document_service, "get_document", get_document)
    monkeypatch.setattr(document_service, "update_draft", reject_update)
    tools = tools_for_project(7, 11, "AGENT")
    result = json.loads(_tool(tools, "document_create").invoke({
        "title": "From file", "content": "# Summary",
    }))
    assert result["success"] and result["document_id"] == "31"
    assert created == [(7, 11, "From file", "# Summary")]

    _tool(tools, "document_read").invoke({"document_id": 21})
    conflict = json.loads(_tool(tools, "document_save").invoke({
        "document_id": 21, "version": 3, "draft_content": "new",
    }))
    assert conflict["success"] is False and conflict["code"] == 40903
    assert all(item.name not in {"document_create", "document_diff", "document_save"}
               for item in tools_for_project(7, 11, "ASK"))
