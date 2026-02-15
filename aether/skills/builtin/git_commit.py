"""
Git Commit Skill

Analyzes staged changes and creates a commit with an AI-generated message.
"""

from dataclasses import dataclass, field
from ..registry import (
    Skill,
    SkillMetadata,
    SkillParameter,
    SkillResult,
    SkillCategory,
    ParameterType,
)


class GitCommitSkill(Skill):
    """
    Create a git commit with AI-generated commit message.

    This skill:
    1. Runs `git status` and `git diff --staged`
    2. Analyzes changes to generate appropriate commit message
    3. Creates commit with the message
    4. Reports commit hash and summary
    """

    metadata = SkillMetadata(
        name="Git Commit",
        slug="git-commit",
        description="Create a git commit with AI-generated commit message based on staged changes",
        category=SkillCategory.GIT,
        tags=["git", "version-control", "commit"],
        version="1.0.0",
        author="AetherOps",
        examples=[
            "Create a commit for my staged changes",
            "Commit the changes with a good message",
            "Git commit with AI message",
        ],
        requires_approval=False,  # Commits are generally safe
    )

    parameters = [
        SkillParameter(
            name="message",
            type=ParameterType.STRING,
            description="Optional custom commit message (overrides AI generation)",
            required=False,
            default=None,
        ),
        SkillParameter(
            name="push",
            type=ParameterType.BOOLEAN,
            description="Push to remote after committing",
            required=False,
            default=False,
        ),
    ]

    async def execute(self, context, **kwargs) -> SkillResult:
        """Execute git commit skill"""
        tools = context.get("tools")
        llm = context.get("llm")

        message_override = kwargs.get("message")
        should_push = kwargs.get("push", False)

        messages = []
        tool_calls = []

        try:
            # 1. Check git status
            status_result = await tools.execute("terminal_execute", command="git status")
            tool_calls.append("terminal_execute: git status")

            if not status_result.success:
                return SkillResult(
                    success=False,
                    error="Failed to run git status",
                    messages=messages,
                    tool_calls=tool_calls,
                )

            # Check if there are staged changes
            if "Changes to be committed" not in status_result.data:
                return SkillResult(
                    success=False,
                    error="No staged changes to commit. Run `git add` first.",
                    messages=messages,
                    tool_calls=tool_calls,
                )

            # 2. Get diff of staged changes
            diff_result = await tools.execute("terminal_execute", command="git diff --staged")
            tool_calls.append("terminal_execute: git diff --staged")

            if not diff_result.success:
                return SkillResult(
                    success=False,
                    error="Failed to get staged diff",
                    messages=messages,
                    tool_calls=tool_calls,
                )

            # 3. Generate commit message (if not provided)
            if message_override:
                commit_message = message_override
                messages.append(f"Using provided message: {commit_message}")
            else:
                # Use LLM to generate commit message
                prompt = f"""Analyze these git changes and generate a concise, conventional commit message.

Status:
{status_result.data}

Diff:
{diff_result.data[:3000]}  # Truncate to avoid token limits

Follow conventional commit format:
- type(scope): description
- Types: feat, fix, docs, style, refactor, test, chore
- Keep under 72 characters
- Be specific about what changed

Output ONLY the commit message, nothing else."""

                commit_message = await llm.generate(prompt)
                messages.append(f"Generated commit message: {commit_message}")

            # 4. Create commit
            # Escape the message for shell
            escaped_message = commit_message.replace('"', '\\"').replace('$', '\\$')
            commit_command = f'git commit -m "{escaped_message}"'

            commit_result = await tools.execute("terminal_execute", command=commit_command)
            tool_calls.append(f"terminal_execute: {commit_command}")

            if not commit_result.success:
                return SkillResult(
                    success=False,
                    error=f"Failed to create commit: {commit_result.error}",
                    messages=messages,
                    tool_calls=tool_calls,
                )

            messages.append(f"✓ Committed: {commit_message}")

            # 5. Push if requested
            if should_push:
                push_result = await tools.execute("terminal_execute", command="git push")
                tool_calls.append("terminal_execute: git push")

                if push_result.success:
                    messages.append("✓ Pushed to remote")
                else:
                    messages.append(f"⚠ Push failed: {push_result.error}")

            return SkillResult(
                success=True,
                data={
                    "commit_message": commit_message,
                    "pushed": should_push,
                },
                messages=messages,
                tool_calls=tool_calls,
            )

        except Exception as e:
            return SkillResult(
                success=False,
                error=f"Unexpected error: {str(e)}",
                messages=messages,
                tool_calls=tool_calls,
            )
