"""On-demand Skills and the docs MCP wrapper expose only intended read tools."""

import asyncio
import json

from app.agent.tools import tools_for_project
from app.agent.tools.langchain_docs_search import make_langchain_docs_search_tool
from app.agent.tools.skills import make_skill_tools
from app.services import mcp_docs_service
from app.services import skill_service


def test_local_skills_are_discoverable_and_read_by_name() -> None:
    listed, read = make_skill_tools()
    names = {item["name"] for item in json.loads(listed.invoke({}))["skills"]}
    assert names == {"document-review", "source-grounded-answer"}
    found = json.loads(read.invoke({"name": "source-grounded-answer"}))
    assert found["success"] and "semantic_file_search" in found["instructions"]
    denied = json.loads(read.invoke({"name": "../../.env"}))
    assert denied["success"] is False


def test_skill_frontmatter_accepts_windows_line_endings(tmp_path) -> None:
    path = tmp_path / "sample-skill" / "SKILL.md"
    path.parent.mkdir()
    path.write_bytes(b"---\r\nname: sample-skill\r\ndescription: Demo\r\n---\r\n\r\n# Steps\r\nRead first.\r\n")
    parsed = skill_service._parse(path)
    assert parsed.name == "sample-skill" and "Read first." in parsed.instructions


def test_docs_mcp_is_opt_in_and_returns_bounded_sources(monkeypatch) -> None:
    async def fake_search(query: str):
        assert query == "LangGraph Stores"
        return [{"title": "Stores", "url": "https://docs.langchain.com/oss/python/langgraph/stores",
                 "excerpt": "Search with a store."}]

    monkeypatch.setattr(mcp_docs_service, "search_docs", fake_search)
    names = {item.name for item in tools_for_project(1, 1, "ASK")}
    assert "langchain_docs_search" not in names
    enabled = {item.name for item in tools_for_project(1, 1, "ASK", docs_mcp_enabled=True)}
    assert "langchain_docs_search" in enabled
    assert "submit_feedback" not in enabled

    result = json.loads(asyncio.run(make_langchain_docs_search_tool().ainvoke({"query": "LangGraph Stores"})))
    assert result["success"] and result["results"][0]["title"] == "Stores"
