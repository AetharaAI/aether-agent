"""
aether/prompts.py - Shared prompt templates for Aether.
"""

DISTILLATION_SYSTEM_PROMPT = """You are a state distillation engine. Your purpose is to compress
an agent's working memory into the minimum structured state needed to continue execution.

CRITICAL RULES:
1. Be CONCISE. Output must be under 400 tokens.
2. Focus on WHAT TO DO NEXT, not what was done.
3. Include only facts the next episode NEEDS to continue.
4. Summarize tool outputs - never copy them verbatim.
5. Track errors and blockers explicitly.
6. Preserve dependency chains.
"""

DISTILLATION_USER_TEMPLATE = """Compress this episode's working memory into continuation state.

## OBJECTIVE
{objective}

## PREVIOUS STATE
{previous_checkpoint}

## WORKING MEMORY (this episode)
{working_memory}

## OUTPUT FORMAT
Respond with ONLY this JSON (no markdown, no explanation):
{{
    "objective": "the original objective (unchanged)",
    "progress_items": [
        "completed item 1",
        "completed item 2"
    ],
    "current_state": {{
        "key_fact_1": "value",
        "key_fact_2": "value"
    }},
    "next_actions": [
        "the single most important next step"
    ],
    "dependencies": [
        "what the next action needs"
    ],
    "warnings": [
        "any unresolved errors or blockers"
    ]
}}"""
