"""JSON navigation preserves pointer semantics and bounds model-facing output."""

import json

import pytest

from app.agent.tools.json_read import make_json_read_tools
from app.core.exceptions import BusinessError
from app.services import file_service, json_structure_service


def test_json_pointer_escaping_and_structure() -> None:
    document = {"a/b": {"~key": [{"secret": "visible only by path"}, 2]}, "other": True}
    root = json_structure_service.structure(document, max_depth=1)
    assert root["children"][0]["path"] == "/a~1b"
    selected = json_structure_service.structure(document, "/a~1b/~0key", max_depth=1)
    assert selected["type"] == "array" and selected["size"] == 2
    leaf = json_structure_service.subtree(document, "/a~1b/~0key/0/secret")
    assert leaf["value"] == "visible only by path"
    for path in ("a/b", "/a~2b", "/a~1b/~0key/00", "/missing"):
        with pytest.raises(BusinessError):
            json_structure_service.resolve_pointer(document, path)


def test_structure_and_subtree_are_bounded() -> None:
    document = {f"key-{index}": {"value": "x" * 500} for index in range(60)}
    root = json_structure_service.structure(document, max_depth=2, max_keys=3)
    assert len(root["children"]) == 3 and root["truncated"] is True
    with pytest.raises(BusinessError, match="子树过大"):
        json_structure_service.subtree(document, "/key-0/value", max_bytes=256)
    with pytest.raises(BusinessError, match="节点过多"):
        json_structure_service.subtree(document, "", max_nodes=5)


def test_json_tools_recheck_scoped_file_service_for_each_read(monkeypatch) -> None:
    calls = []

    def read_project_json(user_id, project_id, file_id):
        calls.append((user_id, project_id, file_id))
        if file_id != 15:
            raise BusinessError(404, 40400, "文件不存在")
        return {"items": [{"name": "first"}, {"name": "second"}]}

    monkeypatch.setattr(file_service, "read_project_json", read_project_json)
    structure_tool, subtree_tool = make_json_read_tools(7, 11)
    structure = json.loads(structure_tool.invoke({"file_id": 15}))
    assert structure["success"] and structure["file_id"] == 15
    selected = json.loads(subtree_tool.invoke({"file_id": 15, "path": "/items/1"}))
    assert selected["value"] == {"name": "second"}
    assert calls == [(7, 11, 15), (7, 11, 15)]
    bad = json.loads(subtree_tool.invoke({"file_id": 16, "path": "/items"}))
    assert bad["success"] is False and calls[-1] == (7, 11, 16)
