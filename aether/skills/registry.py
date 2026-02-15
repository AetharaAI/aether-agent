"""
Skills Registry

Manages registration, discovery, and execution of high-level agent skills.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Callable, Awaitable
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class SkillCategory(str, Enum):
    """Skill categories for organization"""
    GIT = "git"
    CODE = "code"
    TESTING = "testing"
    DEPLOYMENT = "deployment"
    ANALYSIS = "analysis"
    DOCUMENTATION = "documentation"
    SYSTEM = "system"
    WORKFLOW = "workflow"
    CUSTOM = "custom"


class ParameterType(str, Enum):
    """Skill parameter types"""
    STRING = "string"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"


@dataclass
class SkillParameter:
    """Skill parameter definition"""
    name: str
    type: ParameterType
    description: str
    required: bool = False
    default: Any = None
    enum: Optional[List[Any]] = None  # For choice parameters

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "type": self.type.value,
            "description": self.description,
            "required": self.required,
            "default": self.default,
            "enum": self.enum,
        }


@dataclass
class SkillMetadata:
    """Skill metadata for discovery and documentation"""
    name: str
    slug: str  # URL-safe identifier
    description: str
    category: SkillCategory
    tags: List[str] = field(default_factory=list)
    version: str = "1.0.0"
    author: str = "AetherOps"
    examples: List[str] = field(default_factory=list)
    requires_approval: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "slug": self.slug,
            "description": self.description,
            "category": self.category.value,
            "tags": self.tags,
            "version": self.version,
            "author": self.author,
            "examples": self.examples,
            "requires_approval": self.requires_approval,
        }


@dataclass
class SkillResult:
    """Result of skill execution"""
    success: bool
    data: Any = None
    error: Optional[str] = None
    messages: List[str] = field(default_factory=list)  # User-facing messages
    tool_calls: List[str] = field(default_factory=list)  # Tools invoked

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "messages": self.messages,
            "tool_calls": self.tool_calls,
        }


class Skill:
    """
    Base class for agent skills.

    A skill is a high-level workflow that combines multiple tools and prompts.

    Example:
        class CommitSkill(Skill):
            metadata = SkillMetadata(
                name="Commit Changes",
                slug="commit",
                description="Create a git commit with AI-generated message",
                category=SkillCategory.GIT,
                tags=["git", "version-control"],
            )

            parameters = [
                SkillParameter(
                    name="message",
                    type=ParameterType.STRING,
                    description="Optional commit message override",
                    required=False,
                ),
            ]

            async def execute(self, context, **kwargs) -> SkillResult:
                # Skill logic here
                return SkillResult(success=True, messages=["Committed successfully"])
    """

    metadata: SkillMetadata
    parameters: List[SkillParameter] = field(default_factory=list)

    async def execute(self, context: Any, **kwargs) -> SkillResult:
        """
        Execute the skill.

        Args:
            context: Execution context (agent runtime, tools, etc)
            **kwargs: Skill parameters

        Returns:
            SkillResult with execution outcome
        """
        raise NotImplementedError("Skills must implement execute()")

    def to_dict(self) -> Dict[str, Any]:
        """Get skill info for API/UI"""
        return {
            "metadata": self.metadata.to_dict(),
            "parameters": [p.to_dict() for p in self.parameters],
        }


class SkillRegistry:
    """
    Registry for agent skills.

    Manages skill registration, discovery, and execution.
    """

    def __init__(self):
        self._skills: Dict[str, Skill] = {}
        self._categories: Dict[SkillCategory, List[str]] = {}

    def register(self, skill: Skill) -> "SkillRegistry":
        """Register a skill"""
        slug = skill.metadata.slug
        if slug in self._skills:
            logger.warning(f"Overwriting existing skill: {slug}")

        self._skills[slug] = skill

        # Add to category index
        category = skill.metadata.category
        if category not in self._categories:
            self._categories[category] = []
        if slug not in self._categories[category]:
            self._categories[category].append(slug)

        logger.info(f"Registered skill: {skill.metadata.name} ({slug})")
        return self

    def unregister(self, slug: str) -> bool:
        """Unregister a skill by slug"""
        if slug in self._skills:
            skill = self._skills[slug]
            del self._skills[slug]

            # Remove from category index
            category = skill.metadata.category
            if category in self._categories:
                self._categories[category] = [
                    s for s in self._categories[category] if s != slug
                ]

            logger.info(f"Unregistered skill: {slug}")
            return True
        return False

    def get(self, slug: str) -> Optional[Skill]:
        """Get a skill by slug"""
        return self._skills.get(slug)

    def list_skills(
        self,
        category: Optional[SkillCategory] = None,
        tags: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        List available skills with optional filtering.

        Args:
            category: Filter by category
            tags: Filter by tags (any match)

        Returns:
            List of skill metadata dictionaries
        """
        skills = list(self._skills.values())

        # Filter by category
        if category:
            skills = [s for s in skills if s.metadata.category == category]

        # Filter by tags
        if tags:
            skills = [
                s for s in skills
                if any(tag in s.metadata.tags for tag in tags)
            ]

        return [s.to_dict() for s in skills]

    def list_categories(self) -> Dict[str, List[str]]:
        """Get skills organized by category"""
        return {
            cat.value: [
                self._skills[slug].metadata.name
                for slug in slugs
            ]
            for cat, slugs in self._categories.items()
        }

    async def execute(
        self,
        slug: str,
        context: Any,
        **kwargs
    ) -> SkillResult:
        """
        Execute a skill by slug.

        Args:
            slug: Skill identifier
            context: Execution context
            **kwargs: Skill parameters

        Returns:
            SkillResult
        """
        skill = self._skills.get(slug)
        if not skill:
            return SkillResult(
                success=False,
                error=f"Skill not found: {slug}",
            )

        try:
            logger.info(f"Executing skill: {skill.metadata.name}")
            result = await skill.execute(context, **kwargs)
            logger.info(f"Skill {slug} completed: success={result.success}")
            return result
        except Exception as e:
            logger.error(f"Skill {slug} failed: {e}", exc_info=True)
            return SkillResult(
                success=False,
                error=f"Skill execution failed: {str(e)}",
            )

    def __len__(self) -> int:
        """Number of registered skills"""
        return len(self._skills)

    def __contains__(self, slug: str) -> bool:
        """Check if skill is registered"""
        return slug in self._skills
