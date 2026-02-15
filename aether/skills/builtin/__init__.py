"""
Built-in AetherOps Skills

Pre-packaged skills for common development workflows.
"""

from .git_commit import GitCommitSkill

__all__ = [
    "GitCommitSkill",
]


def register_builtin_skills(registry):
    """Register all built-in skills"""
    registry.register(GitCommitSkill())
    # Add more built-in skills here as they're created
    return registry
