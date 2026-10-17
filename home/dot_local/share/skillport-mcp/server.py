"""Live read-only MCP access to the user's installed Agent Skills."""

import os
import re
from pathlib import Path, PurePosixPath

import yaml
from fastmcp import FastMCP

NAME = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
HEADER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.S)
TEXT_SUFFIXES = {".md", ".txt", ".json", ".yaml", ".yml", ".py", ".toml"}
MAX_BYTES = 256_000

mcp = FastMCP(
    "SkillPort Local Skills",
    instructions=(
        "Search the user's local Agent Skills before relevant coding, testing, "
        "software architecture or agentic workflow tasks. Read the complete "
        "SKILL.md of matching skills before following them."
    ),
)


def root() -> Path:
    return Path(os.environ.get("SKILLPORT_SKILLS_ROOT", "~/.agents/skills")).expanduser()


def directory(name: str) -> Path:
    if not NAME.fullmatch(name):
        raise ValueError("Invalid skill name")
    candidate = root() / name
    if not (candidate / "SKILL.md").is_file():
        raise ValueError("Skill not found")
    # Direct child symlinks are allowed: SkillPort installs them from Git repositories.
    return candidate.resolve(strict=True)


def read_text(path: Path, base: Path) -> str:
    resolved = path.resolve(strict=True)
    if not resolved.is_relative_to(base) or not resolved.is_file():
        raise ValueError("Resource is outside the selected skill")
    if resolved.stat().st_size > MAX_BYTES:
        raise ValueError("Skill resource too large")
    return resolved.read_text("utf-8")


def metadata(name: str) -> dict:
    base = directory(name)
    match = HEADER.match(read_text(base / "SKILL.md", base))
    if not match:
        raise ValueError("Invalid skill frontmatter")
    frontmatter = yaml.safe_load(match.group(1))
    if not isinstance(frontmatter, dict) or not isinstance(frontmatter.get("description"), str):
        raise ValueError("Missing skill description")
    return {"name": name, "description": frontmatter["description"]}


@mcp.tool(description=(
    "Before tasks involving Python tests, coding, software design, "
    "agent instructions, shell or developer tooling, look up relevant personal "
    "Agent Skills. Return names and descriptions; then call read_skill on any "
    "relevant result. Reads the user's currently installed skills live."
))
def search_skills(query: str, limit: int = 20, offset: int = 0) -> dict:
    if not 1 <= limit <= 50 or offset < 0:
        raise ValueError("Invalid pagination")
    catalog = []
    if root().is_dir():
        for child in sorted(root().iterdir()):
            if NAME.fullmatch(child.name):
                try:
                    catalog.append(metadata(child.name))
                except (OSError, ValueError, UnicodeError, yaml.YAMLError):
                    continue
    terms = set(re.findall(r"[a-z0-9]+", query.casefold()))
    catalog.sort(key=lambda item: (
        -sum(3 if term in item["name"] else 1 for term in terms
             if term in (item["name"] + " " + item["description"].casefold())),
        item["name"],
    ))
    return {"skills": catalog[offset:offset + limit], "total": len(catalog),
            "next_offset": offset + limit if offset + limit < len(catalog) else None}


@mcp.tool(description=(
    "Read the complete, up-to-date SKILL.md for an exact name returned by "
    "search_skills. Skill descriptions alone are not complete instructions."
))
def read_skill(name: str) -> dict:
    base = directory(name)
    return {**metadata(name), "instructions": read_text(base / "SKILL.md", base)}


@mcp.tool(description=(
    "Read an explicitly referenced text resource from an already selected "
    "Agent Skill, such as references/testing.md. Never accesses arbitrary files."
))
def read_skill_resource(name: str, path: str) -> dict:
    base = directory(name)
    rel = PurePosixPath(path)
    if (not path or rel.is_absolute() or any(part.startswith(".") for part in rel.parts)
            or rel.suffix.lower() not in TEXT_SUFFIXES):
        raise ValueError("Invalid skill resource path")
    return {"name": name, "path": path, "content": read_text(base / path, base)}


if __name__ == "__main__":
    mcp.run(transport="stdio")
