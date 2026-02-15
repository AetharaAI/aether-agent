"""
AetherOps Skills System

Skills are high-level workflows that can combine multiple tools and prompts
to accomplish complex tasks. Similar to Anthropic's Claude Code skills.

A skill consists of:
- Metadata (name, description, category, tags)
- Parameters (user inputs)
- Workflow steps (tools to call, prompts to run)
- Output format

Skills vs Tools:
- Tools: Low-level atomic operations (read file, execute command)
- Skills: High-level workflows (commit changes, review PR, run tests)
"""

from .registry import SkillRegistry, Skill, SkillMetadata, SkillParameter
from .loader import load_skills_from_directory

__all__ = [
    "SkillRegistry",
    "Skill",
    "SkillMetadata",
    "SkillParameter",
    "load_skills_from_directory",
]
