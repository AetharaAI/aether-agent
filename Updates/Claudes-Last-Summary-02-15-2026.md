Here's the complete rundown of everything done and what you need to know:

All Changes This Session
1. Anthropic tool_use.input Error Fixed
The error messages.1.content.1.tool_use.input: Input should be a valid dictionary is fixed. The runtime stores tool arguments as json.dumps() strings in conversation history, but Anthropic requires a dict. Both _build_anthropic_payload() and _complete_with_tools_anthropic() now parse string arguments back to dicts. Also added consecutive same-role message merging (Anthropic requires strictly alternating user/assistant turns).

2. API Format Routing Uses tool_format Not Provider Name
This was the hidden bug blocking MiniMax. The code checked self.config.provider == "anthropic" for headers (x-api-key) and URL routing (/messages), but MiniMax has provider="minimax" with tool_format="anthropic". Now all API format decisions use tool_format, so both Claude and MiniMax correctly use the Anthropic API format.

3. Context Gauge Fixed
Token usage was stuck at 0% because the frontend polled aether.nvidia (the global instance) but the WebSocket creates a separate NVIDIAKit per session. Now the runtime emits usage_update events through WebSocket after every LLM call. The frontend hook handles these events and updates the gauge in real-time.

4. Graceful Error Handling
The agentic loop now has retry logic with exponential backoff (up to 3 consecutive failures). Tool execution failures are caught and fed back to the LLM as error messages so it can adapt, instead of killing the entire loop.

5. Context Compression Now Preserves Critical Facts
This is the big one for your issue. The old compression kept only the last 10 exchanges truncated to 100 chars — that's why the model kept forgetting model names. The new _extract_critical_context() method preserves:

The original user request (first 500 chars)
Key entities extracted via regex (model names, file paths, URLs)
Last assistant response (400 chars)
Recent tool results (last 5 non-error results)
All critical context is also persisted to Redis so it survives session restarts
6. MiniMax Models Updated
Model IDs updated to match the Anthropic API: MiniMax-M2.5, MiniMax-M2.5-highspeed, MiniMax-M2.1, MiniMax-M2.1-highspeed, MiniMax-M2.

vLLM Tool Calling Flags
MiniCPM-V-4.5: There's no built-in vLLM parser for MiniCPM-V. MiniCPM4 uses custom <|tool_call_start|> markers, not the standard formats. Your options:

Try hermes parser — it works as a generic fallback for many models:

--enable-auto-tool-choice --tool-call-parser hermes
Skip vLLM tool calling entirely — let Aether handle it with tool_format: text in the provider config. Since MiniCPM-V-4.5 is primarily a vision model, this is the safest approach.
Nanbeige4-3B-Thinking: Also no specific parser. Same options — try hermes first, fall back to text-based parsing if it errors.

For your currently running docker-compose, --tool-call-parser openai is set. If that's erroring, swap to hermes in both containers. If hermes also fails, remove the tool calling flags entirely and set tool_format: text for the litellm-2 provider in provider-registry.yaml — Aether's text-based tool parser will handle it.

Sources:

vLLM Tool Calling Docs
MiniCPM-V CookBook vLLM Deployment
OpenBMB MiniCPM MCP Integration