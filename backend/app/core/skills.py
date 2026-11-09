"""SKILL.md file system for agent knowledge domains.

Inspired by VenusFactory2 and OpenBioMed:
- Each domain is a directory with a SKILL.md file
- YAML frontmatter provides metadata for plan-time discovery
- Full markdown body provides detailed instructions for execution
- Progressive disclosure: metadata in system prompt, full content on-demand
"""

import os
import re
import yaml
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class Skill:
    name: str
    description: str
    path: str
    category: str = "general"
    tags: list[str] = field(default_factory=list)
    triggers: list[str] = field(default_factory=list)

    def read_content(self) -> str:
        """Read the full SKILL.md content on-demand."""
        skill_path = os.path.join(self.path, "SKILL.md")
        if os.path.exists(skill_path):
            with open(skill_path, "r") as f:
                return f.read()
        return ""


class SkillRegistry:
    """Discovers and manages SKILL.md files."""

    _skills: dict[str, Skill] = {}
    _loaded: bool = False

    @classmethod
    def discover(cls, skills_dir: str | None = None) -> list[Skill]:
        """Scan skills directory for SKILL.md files."""
        if skills_dir is None:
            skills_dir = os.path.join(os.path.dirname(__file__), "..", "skills")

        if not os.path.isdir(skills_dir):
            return []

        for entry in os.scandir(skills_dir):
            if not entry.is_dir():
                continue
            skill_file = os.path.join(entry.path, "SKILL.md")
            if os.path.isfile(skill_file):
                skill = cls._parse_skill(skill_file, entry.path)
                if skill:
                    cls._skills[skill.name] = skill

        cls._loaded = True
        return list(cls._skills.values())

    @classmethod
    def _parse_skill(cls, filepath: str, dirpath: str) -> Skill | None:
        """Parse YAML frontmatter from a SKILL.md file."""
        try:
            with open(filepath, "r") as f:
                content = f.read()

            # Extract YAML frontmatter
            match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
            if not match:
                # No frontmatter — use filename as name
                name = os.path.basename(dirpath)
                return Skill(
                    name=name,
                    description=f"Knowledge domain: {name}",
                    path=dirpath,
                )

            metadata = yaml.safe_load(match.group(1))
            if not isinstance(metadata, dict):
                return None

            name = metadata.get("name", os.path.basename(dirpath))
            return Skill(
                name=name,
                description=metadata.get("description", ""),
                path=dirpath,
                category=metadata.get("category", "general"),
                tags=metadata.get("tags", []),
                triggers=metadata.get("triggers", []),
            )
        except Exception:
            return None

    @classmethod
    def get(cls, name: str) -> Skill | None:
        if not cls._loaded:
            cls.discover()
        return cls._skills.get(name)

    @classmethod
    def list_all(cls) -> list[dict]:
        if not cls._loaded:
            cls.discover()
        return [
            {
                "name": s.name,
                "description": s.description,
                "category": s.category,
                "triggers": s.triggers,
            }
            for s in cls._skills.values()
        ]

    @classmethod
    def search_by_trigger(cls, query: str) -> Skill | None:
        """Find a skill matching the query triggers."""
        if not cls._loaded:
            cls.discover()
        query_lower = query.lower()
        for skill in cls._skills.values():
            for trigger in skill.triggers:
                if trigger.lower() in query_lower:
                    return skill
        return None


def get_skills_metadata() -> list[dict]:
    """Convenience function for plan-time skill injection."""
    return SkillRegistry.list_all()


def read_skill(name: str) -> str:
    """On-demand skill content loading (MLS runtime tool)."""
    skill = SkillRegistry.get(name)
    if skill:
        return skill.read_content()
    return f"Skill '{name}' not found."
