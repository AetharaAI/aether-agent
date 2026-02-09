"""
Persi Core Agent
Main agent class that coordinates reasoning, memory, and tools.
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from anthropic import AsyncAnthropic
import structlog

from persi.memory.manager import MemoryManager
from persi.tools.registry import ToolRegistry
from persi.config.settings import Settings, ModelProvider
from persi.core.minimax_handler import (
    MiniMaxResponseHandler,
    create_minimax_messages,
    create_minimax_tools
)
from persi.models.inference_server import (
    create_openai_messages,
    create_openai_tools
)
from persi.clients.openai_compatible_client import (
    OpenAICompatibleClient,
    OpenAICompatibleResponseHandler
)

logger = structlog.get_logger()


class PersiAgent:
    """
    Persi - Personal Intelligence Agent

    Main agent that handles:
    - Reasoning via LLM (LiteLLM, OpenRouter, Anthropic, Gemini)
    - Memory management (short-term + long-term)
    - Tool execution
    - Personality/persona
    - Agent coordination

    Provider determines transport semantics (HTTP method, endpoint, auth).
    Model name is opaque and does not affect client behavior.
    """

    def __init__(
        self,
        settings: Settings,
        memory_manager: MemoryManager,
        tool_registry: ToolRegistry
    ):
        self.settings = settings
        self.memory = memory_manager
        self.tools = tool_registry

        # Get provider from settings
        provider = settings.model.provider

        # Initialize client based on provider
        if provider == ModelProvider.LITELLM:
            self._init_litellm_client()
        elif provider == ModelProvider.OPENROUTER:
            self._init_openrouter_client()
        elif provider == ModelProvider.ANTHROPIC:
            self._init_anthropic_client()
        elif provider == ModelProvider.GEMINI:
            self._init_gemini_client()
        else:
            # Default to litellm
            logger.warning(f"Unknown provider {provider}, defaulting to litellm")
            self._init_litellm_client()

        # Load personality
        self.personality = self._load_personality()

        # State
        self.conversation_id: Optional[str] = None
        self.context: Dict[str, Any] = {}
        self.show_thinking: bool = False  # Set to True to see reasoning

    def _init_litellm_client(self):
        """Initialize LiteLLM client (OpenAI-compatible)."""
        self.client = OpenAICompatibleClient(
            api_key=self.settings.model.api_key,
            base_url=self.settings.model.base_url,
            model_name=self.settings.model.name,
            max_tokens=self.settings.model.max_tokens,
            temperature=self.settings.model.temperature
        )
        self.response_handler = OpenAICompatibleResponseHandler()
        logger.info("Persi agent initialized with LiteLLM", model=self.settings.model.name)

    def _init_openrouter_client(self):
        """Initialize OpenRouter client (OpenAI-compatible)."""
        self.client = OpenAICompatibleClient(
            api_key=self.settings.model.api_key,
            base_url=self.settings.model.base_url,
            model_name=self.settings.model.name,
            max_tokens=self.settings.model.max_tokens,
            temperature=self.settings.model.temperature
        )
        self.response_handler = OpenAICompatibleResponseHandler()
        logger.info("Persi agent initialized with OpenRouter", model=self.settings.model.name)

    def _init_anthropic_client(self):
        """Initialize Anthropic client."""
        self.client = AsyncAnthropic(
            api_key=self.settings.model.api_key,
            base_url=self.settings.model.base_url if self.settings.model.base_url else None
        )
        # Use MiniMax handler for thinking blocks (Anthropic format)
        self.response_handler = MiniMaxResponseHandler()
        logger.info("Persi agent initialized with Anthropic", model=self.settings.model.name)

    def _init_gemini_client(self):
        """Initialize Gemini client placeholder."""
        # TODO: Implement Gemini client
        # For now, raise error to indicate not yet implemented
        raise NotImplementedError(
            "Gemini provider is not yet implemented. "
            "Use litellm, openrouter, or anthropic instead."
        )

    def _load_personality(self) -> str:
        """Load personality configuration from file."""
        personality_file = Path(self.settings.personality_file)

        if personality_file.exists():
            return personality_file.read_text()
        else:
            logger.warning("Personality file not found, using default")
            return self._default_personality()

    def _default_personality(self) -> str:
        """Default personality if file doesn't exist."""
        return """You are Persi, Cory's Personal Intelligence Agent for AetherPro Technologies.

You help manage operations, coordinate projects, and handle technical tasks.
You're professional but conversational, direct and solution-oriented.
You never say "I can't" without offering alternatives.

Cory is a master electrician turned solo founder building AI platforms.
He's self-taught, uses AI to build, and runs everything himself.
You respect that hustle and help him get shit done.
"""

    def _build_system_prompt(self) -> str:
        """Build the complete system prompt with personality + context."""

        # Base personality
        prompt = self.personality

        # Add current context
        prompt += f"\n\nCurrent time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

        if self.context.get("location"):
            prompt += f"\nCory's location: {self.context['location']}"

        # Add available tools
        tool_descriptions = self.tools.get_tool_descriptions()
        if tool_descriptions:
            prompt += "\n\nAvailable tools:\n"
            for tool in tool_descriptions:
                prompt += f"- {tool['name']}: {tool['description']}\n"

        # Add execution mode
        prompt += f"\n\nExecution mode: {self.settings.execution_mode}"
        if self.settings.execution_mode == "autonomous":
            prompt += "\nYou can execute safe commands without asking for confirmation."
        elif self.settings.execution_mode == "semi_autonomous":
            prompt += "\nExecute safe commands automatically, but ask before risky operations."
        else:
            prompt += "\nAsk for confirmation before executing any commands."

        return prompt

    async def chat(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Main chat interface.

        Args:
            message: User's message
            context: Optional context (location, urgency, etc.)

        Returns:
            Persi's response
        """

        # Update context
        if context:
            self.context.update(context)

        # Get conversation history from memory
        history = await self.memory.get_recent_conversation(
            conversation_id=self.conversation_id,
            limit=10
        )

        # Handle based on provider
        provider = self.settings.model.provider
        if provider == ModelProvider.ANTHROPIC:
            return await self._handle_anthropic_chat(history, message, context)
        else:
            return await self._handle_openai_compatible_chat(history, message, context)

    async def _handle_openai_compatible_chat(
        self,
        history: List[Dict[str, Any]],
        message: str,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Handle chat using OpenAI-compatible API (LiteLLM, OpenRouter).

        Args:
            history: Conversation history
            message: User message
            context: Optional context

        Returns:
            Assistant response
        """
        try:
            # Build messages in OpenAI format
            messages = create_openai_messages(
                conversation_history=history,
                current_message=message
            )

            # Add system prompt
            system_prompt = self._build_system_prompt()
            messages.insert(0, {
                "role": "system",
                "content": system_prompt
            })

            # Get tools in OpenAI format
            tools = None
            if self.settings.model.allow_tool_calls:
                tools = create_openai_tools(self.tools.get_anthropic_tools())

            # Make API call
            async with self.client as client:
                response = await client.chat_completion(
                    messages=messages,
                    tools=tools,
                    max_tokens=self.settings.model.max_tokens,
                    temperature=self.settings.model.temperature
                )

                # Parse response
                parsed = self.response_handler.parse_response(response)

                # Handle response based on tool use
                assistant_message = await self._handle_openai_response(
                    parsed=parsed,
                    original_message=message,
                    messages=messages
                )

                # Store in memory
                await self.memory.store_conversation(
                    conversation_id=self.conversation_id,
                    user_message=message,
                    assistant_message=assistant_message,
                    context=self.context
                )

                return assistant_message

        except Exception as e:
            logger.error("Error in OpenAI-compatible chat", error=str(e))
            return f"Error: {str(e)}"

    async def _handle_openai_response(
        self,
        parsed: Dict[str, Any],
        original_message: str,
        messages: List[Dict[str, Any]]
    ) -> str:
        """
        Handle OpenAI-compatible response with tool execution.

        Args:
            parsed: Parsed response from handler
            original_message: Original user message
            messages: Messages sent in the original request

        Returns:
            Final assistant message
        """
        # If there are tool uses, execute them
        if parsed["has_tool_calls"]:
            tool_results = []

            for tool_use in parsed["tool_uses"]:
                tool_name = tool_use["name"]
                tool_input = tool_use["input"]
                tool_id = tool_use["id"]

                logger.info(
                    "Executing tool",
                    tool=tool_name,
                    input=tool_input
                )

                # Check if we need confirmation
                if self._needs_confirmation(tool_name, tool_input):
                    logger.warning("Tool requires confirmation but executing anyway", tool=tool_name)

                # Execute tool
                try:
                    result = await self.tools.execute_tool(
                        tool_name,
                        **tool_input
                    )

                    tool_results.append({
                        "id": tool_id,
                        "tool": tool_name,
                        "result": result,
                        "is_error": False
                    })

                    logger.info("Tool execution successful", tool=tool_name)

                except Exception as e:
                    logger.error(
                        "Tool execution failed",
                        tool=tool_name,
                        error=str(e)
                    )
                    tool_results.append({
                        "id": tool_id,
                        "tool": tool_name,
                        "error": str(e),
                        "is_error": True
                    })

            # Return original response with tool results appended
            if tool_results:
                result_texts = []
                for result in tool_results:
                    if result["is_error"]:
                        result_texts.append(f"Tool {result['tool']} failed: {result['error']}")
                    else:
                        result_texts.append(f"Tool {result['tool']} executed successfully")

                return f"{parsed['text_response']}\n\n{chr(10).join(result_texts)}"

        # Return text response
        return self.response_handler.format_response_for_display(
            parsed["text_response"],
            parsed.get("usage")
        )

    async def _handle_anthropic_chat(
        self,
        history: List[Dict[str, Any]],
        message: str,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Handle chat using Anthropic API (supports thinking blocks).

        Args:
            history: Conversation history
            message: User message
            context: Optional context

        Returns:
            Assistant response
        """
        try:
            # Build messages in MiniMax format (Anthropic-compatible)
            messages = create_minimax_messages(
                conversation_history=history,
                current_message=message
            )

            # Get tools in MiniMax format
            tools = create_minimax_tools(self.tools.get_anthropic_tools())

            response = await self.client.messages.create(
                model=self.settings.model.name,
                max_tokens=4096,
                system=self._build_system_prompt(),
                messages=messages,
                tools=tools if tools else None
            )

            # Parse response (handles thinking blocks!)
            parsed = self.response_handler.parse_response(response)

            # Handle response
            assistant_message = await self._handle_anthropic_response(
                parsed=parsed,
                original_message=message,
                original_response=response,
                messages=messages
            )

            # Store in memory
            await self.memory.store_conversation(
                conversation_id=self.conversation_id,
                user_message=message,
                assistant_message=assistant_message,
                context=self.context
            )

            return assistant_message

        except Exception as e:
            logger.error("Error in Anthropic chat", error=str(e))
            return f"Error: {str(e)}"

    async def _handle_anthropic_response(
        self,
        parsed: Dict[str, Any],
        original_message: str,
        original_response: Any,
        messages: List[Dict[str, Any]]
    ) -> str:
        """
        Handle Anthropic response with thinking blocks and tool use.

        Args:
            parsed: Parsed response from MiniMaxResponseHandler
            original_message: Original user message
            original_response: Original API response object
            messages: Messages sent in the original request

        Returns:
            Final assistant message
        """
        response_parts = []

        # Add thinking if enabled
        if parsed["has_thinking"] and self.show_thinking:
            thinking_text = self.response_handler.format_thinking_for_display(
                parsed["thinking"],
                show_thinking=True
            )
            response_parts.append(thinking_text)

        # If there are text responses and no tool use, return them
        if parsed["text_responses"] and not parsed["needs_tool_execution"]:
            text = self.response_handler.combine_text_responses(parsed["text_responses"])
            response_parts.append(text)
            return "\n\n".join(response_parts)

        # Handle tool execution
        if parsed["needs_tool_execution"]:
            tool_results = []

            for tool_use in parsed["tool_uses"]:
                tool_name = tool_use["name"]
                tool_input = tool_use["input"]
                tool_id = tool_use["id"]

                logger.info(
                    "Executing tool",
                    tool=tool_name,
                    input=tool_input
                )

                if self._needs_confirmation(tool_name, tool_input):
                    logger.warning("Tool requires confirmation but executing anyway", tool=tool_name)

                try:
                    result = await self.tools.execute_tool(
                        tool_name,
                        **tool_input
                    )

                    tool_results.append({
                        "id": tool_id,
                        "tool": tool_name,
                        "result": result,
                        "is_error": False
                    })

                    logger.info("Tool execution successful", tool=tool_name)

                except Exception as e:
                    logger.error(
                        "Tool execution failed",
                        tool=tool_name,
                        error=str(e)
                    )
                    tool_results.append({
                        "id": tool_id,
                        "tool": tool_name,
                        "error": str(e),
                        "is_error": True
                    })

            # Build follow-up messages with tool results
            follow_up_messages = messages.copy()
            assistant_content = []
            for block in original_response.content:
                block_type = getattr(block, 'type', None)

                if block_type == "thinking":
                    assistant_content.append({
                        "type": "thinking",
                        "thinking": getattr(block, 'thinking', '')
                    })
                elif block_type == "text":
                    assistant_content.append({
                        "type": "text",
                        "text": getattr(block, 'text', '')
                    })
                elif block_type == "tool_use":
                    assistant_content.append({
                        "type": "tool_use",
                        "id": getattr(block, 'id', ''),
                        "name": getattr(block, 'name', ''),
                        "input": getattr(block, 'input', {})
                    })

            follow_up_messages.append({
                "role": "assistant",
                "content": assistant_content
            })

            tool_result_content = self.response_handler.build_tool_result_message(tool_results)
            follow_up_messages.append({
                "role": "user",
                "content": tool_result_content
            })

            # Call again with proper message sequence
            response = await self.client.messages.create(
                model=self.settings.model.name,
                max_tokens=4096,
                system=self._build_system_prompt(),
                messages=follow_up_messages
            )

            # Parse follow-up response
            follow_up_parsed = self.response_handler.parse_response(response)

            if follow_up_parsed["has_thinking"] and self.show_thinking:
                thinking_text = self.response_handler.format_thinking_for_display(
                    follow_up_parsed["thinking"],
                    show_thinking=True
                )
                response_parts.append(thinking_text)

            if follow_up_parsed["text_responses"]:
                text = self.response_handler.combine_text_responses(
                    follow_up_parsed["text_responses"]
                )
                response_parts.append(text)

            return "\n\n".join(response_parts)

        # Fallback
        return self.response_handler.combine_text_responses(parsed["text_responses"])

    def _needs_confirmation(self, tool_name: str, tool_input: Dict) -> bool:
        """Check if a tool execution needs user confirmation."""

        if self.settings.execution_mode == "autonomous":
            return False

        if self.settings.execution_mode == "interactive":
            return True

        # Semi-autonomous: check against safe list
        if tool_name in ["file_read", "directory_list", "get_status"]:
            return False

        # Check if command is in safe list (for shell tool)
        if tool_name == "shell_execute":
            command = tool_input.get("command", "")
            for safe_cmd in self.settings.safe_commands:
                if command.startswith(safe_cmd):
                    return False

        return True

    async def execute_command(self, command: str) -> str:
        """
        Execute a direct command (for CLI usage).

        Args:
            command: Command to execute

        Returns:
            Result
        """
        return await self.chat(command)

    async def get_projects_status(self) -> List[Dict[str, Any]]:
        """Get status of all projects."""
        projects = await self.memory.get_projects()
        return projects

    async def get_tasks(self, filter_status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get tasks, optionally filtered by status."""
        tasks = await self.memory.get_tasks(status=filter_status)
        return tasks

    async def delegate_to_agent(
        self,
        agent_name: str,
        task: str,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Delegate a task to another agent (Mini-Flux, Aletheia, etc.).

        Args:
            agent_name: Name of the agent to delegate to
            task: Task description
            params: Optional parameters

        Returns:
            Result from the agent
        """

        logger.info(
            "Delegating to agent",
            agent=agent_name,
            task=task
        )

        # TODO: Implement agent coordination via AetherOS
        # For now, return placeholder
        return {
            "status": "delegated",
            "agent": agent_name,
            "task": task,
            "message": "Agent coordination will be implemented in Phase 4"
        }

    def set_conversation_id(self, conversation_id: str):
        """Set the current conversation ID."""
        self.conversation_id = conversation_id

    def update_context(self, **kwargs):
        """Update agent context."""
        self.context.update(kwargs)
