"""Read-only on-demand access to repository-owned Agent Skills."""

import json

from langchain_core.tools import BaseTool, tool

from app.core.exceptions import BusinessError
from app.services import skill_service


def make_skill_tools(enabled_names: set[str] | None = None) -> list[BaseTool]:
    allowed = enabled_names if enabled_names is not None else set(skill_service.catalog())
    if not allowed:
        return []

    @tool
    def skill_list() -> str:
        """List available task Skills with a short description of when to use each one."""
        return json.dumps({"skills": [item for item in skill_service.list_skills()
                                      if item["name"] in allowed]}, ensure_ascii=False)

    @tool
    def skill_read(name: str) -> str:
        """Read one listed Skill's instructions by exact name, before applying its workflow."""
        if name not in allowed:
            return json.dumps({"success": False, "error": "Skill 未启用或不存在"}, ensure_ascii=False)
        try:
            result = skill_service.read_skill(name)
        except BusinessError as error:
            return json.dumps({"success": False, "error": error.message}, ensure_ascii=False)
        return json.dumps({"success": True, **result}, ensure_ascii=False)

    return [skill_list, skill_read]
