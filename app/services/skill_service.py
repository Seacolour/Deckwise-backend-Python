"""Discover trusted local SKILL.md packages without arbitrary path access."""

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.core.error_codes import ErrorCode
from app.core.exceptions import BusinessError

SKILLS_DIR = Path(__file__).resolve().parents[1] / "agent" / "skills"
MAX_SKILL_CHARS = 6_000
_SLUG = re.compile(r"[a-z][a-z0-9-]{0,63}\Z")


@dataclass(frozen=True)
class SkillDefinition:
    name: str
    description: str
    instructions: str


def _parse(path: Path) -> SkillDefinition:
    content = path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
    if len(content) > MAX_SKILL_CHARS or not content.startswith("---\n"):
        raise ValueError(f"Invalid skill package: {path.parent.name}")
    try:
        frontmatter, instructions = content[4:].split("\n---\n", 1)
    except ValueError as error:
        raise ValueError(f"Missing skill frontmatter: {path.parent.name}") from error
    fields = dict(line.split(":", 1) for line in frontmatter.splitlines() if ":" in line)
    name = fields.get("name", "").strip()
    description = fields.get("description", "").strip()
    if not _SLUG.fullmatch(name) or name != path.parent.name or not description or not instructions.strip():
        raise ValueError(f"Invalid skill metadata: {path.parent.name}")
    return SkillDefinition(name, description, instructions.strip())


@lru_cache(maxsize=1)
def catalog() -> dict[str, SkillDefinition]:
    definitions = [_parse(path) for path in sorted(SKILLS_DIR.glob("*/SKILL.md"))]
    return {item.name: item for item in definitions}


def list_skills() -> list[dict[str, str]]:
    return [{"name": item.name, "description": item.description} for item in catalog().values()]


def read_skill(name: str) -> dict[str, str]:
    skill = catalog().get(name)
    if skill is None:
        raise BusinessError(404, ErrorCode.NOT_FOUND, "Skill 不存在")
    return {"name": skill.name, "description": skill.description,
            "instructions": skill.instructions}
