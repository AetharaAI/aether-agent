# AetherOps - Master Vision & Changelog

**Live URL**: [aetherops.aetherpro.us](https://aetherops.aetherpro.us)
**Repository**: aether_project
**Branch**: contained
**Last Updated**: 2026-02-14

---

## What Is AetherOps?

AetherOps is a **provider-agnostic, model-agnostic Agentic Operating Environment** built on async Python (FastAPI + WebSockets). It is designed to be the most capable open agentic harness available - combining the best architectural patterns from Agent Zero, OpenClaw, and Claude Code while surpassing all of them in production readiness, extensibility, and hybrid deployment.

The core thesis: **One interface, any model, any provider, any tool - self-hosted or cloud.**

---

## Architecture Overview

```
                    +------------------+
                    |   AetherOps UI   |  (React + TypeScript)
                    |  :16398 (nginx)  |
                    +--------+---------+
                             | WebSocket + REST
                    +--------+---------+
                    |  Aether API      |  (FastAPI, async Python)
                    |  :16399 (uvicorn)|
                    +--------+---------+
                             |
          +------------------+------------------+
          |                  |                  |
   +------+------+   +------+------+   +-------+------+
   | Provider    |   | Tool        |   | Memory       |
   | Router      |   | Registry    |   | System       |
   | (any LLM)   |   | (12+ tools) |   | (Redis+Qdrant)|
   +--------------+   +-------------+   +--------------+
```

### Current Stack
- **Backend**: Python 3.11, FastAPI, asyncio, aiohttp
- **Frontend**: React, TypeScript, Tailwind CSS, Vite
- **Memory**: Redis Stack (short-term, identity, scratchpad) + Qdrant (long-term vectors)
- **Database**: PostgreSQL (conversation history, sessions)
- **Deployment**: Docker Compose (3 services: API, UI, Redis)
- **ASR**: Speechmatics (cloud, highly accurate)
- **LLM Proxy**: LiteLLM (self-hosted at api.blackboxaudio.tech)

---

## Competitive Advantages

### vs Agent Zero
| Capability | Agent Zero | AetherOps |
|-----------|-----------|-----------|
| Runtime | Flask + threads (sync) | FastAPI + asyncio (async-native) |
| Communication | HTTP polling | WebSocket bidirectional streaming |
| Provider switching | Config file, restart required | Hot-swap mid-conversation, zero downtime |
| Memory | FAISS files (local) | Redis Stack + Qdrant (production-grade) |
| Model support | Config-only | Dynamic provider router, 14+ providers |
| Deployment | Single container | Docker Compose with health checks |
| Skills | SKILL.md files | Python class registry + API endpoints |
| Tool calling | Text parsing | Native tool_call API (OpenAI + Anthropic format) |

### vs OpenClaw
| Capability | OpenClaw | AetherOps |
|-----------|---------|-----------|
| Language | TypeScript/Node.js | Python (async) + TypeScript UI |
| Tool ecosystem | Strong TS-native tools | Python tools + planned TS bridge |
| Provider support | Limited | 14+ providers, hot-swappable |
| Self-hosted models | Not focused | Core design goal |
| Voice/Audio | Not included | ASR (Speechmatics) + planned TTS |
| Vision/OCR | Not included | Planned dedicated model pipeline |

### vs Claude Code
| Capability | Claude Code | AetherOps |
|-----------|------------|-----------|
| Model lock-in | Anthropic only | Any provider, any model |
| Deployment | CLI tool | Full web application |
| Self-hosted | No | Yes, entire stack |
| Voice | No | ASR + planned TTS |
| Vision | No | Planned vision/OCR pipeline |
| Multi-model | No | Warm orchestration planned |

---

## Changelog

### 2026-02-14 (Session 3) - Image Upload Fix & Vision Support

#### Fixed
- **Image upload never reaching the model**: `_build_user_content()` only checked `url` and `path` keys on attachments, but the frontend sends image data in the `content` field (base64 data URL from `FileReader.readAsDataURL()`). Images were silently dropped. Now checks all three sources: `url`, `path`, and `content`.
- **Anthropic image format conversion**: Both `_build_anthropic_payload()` and `_complete_with_tools_anthropic()` now convert OpenAI `image_url` blocks to Anthropic `image` source format (`type: "base64"`, `media_type`, `data`). Previously, multimodal content was passed through unconverted and would fail on Anthropic's API.

#### Changed
- **litellm-2 model swap**: Replaced `qwen3-30b-thinking` with `Nanbeige4-3B-Thinking-2511` in hardcoded model list.

#### Files Modified
- `aether/agent_runtime_v2.py` — `_build_user_content()` now handles `content` field from frontend
- `aether/nvidia_kit.py` — `_build_anthropic_payload()` and `_complete_with_tools_anthropic()` convert `image_url` to Anthropic image format
- `aether/api_server.py` — Updated `LITELLM_2_MODELS`

### 2026-02-14 (Session 2) - Triple LLM Client Routing & litellm-2 Models

#### Implemented
- **Three-way tool calling router**: `tool_format` config property added to provider registry. NVIDIAKit now routes tool calls based on provider type:
  - `openai` — Native OpenAI function calling (LiteLLM, Groq, Together, Mistral, OpenRouter, etc.)
  - `anthropic` — Anthropic Messages API tool calling (Claude models)
  - `text` — Text-based tool calling (MiniMax, HuggingFace). No native tool API sent; agent runtime parses `tool_call` blocks from text output.
- **litellm-2 GPU instance models**: Added `minicpm-v-4.5` (vision) and `qwen3-30b-thinking` to hardcoded model list with dynamic fetch fallback.
- **Refactored model fetching**: Extracted `_fetch_models_dynamic()` helper. litellm-2 tries dynamic `/v1/models` first, falls back to hardcoded models if gateway returns 502.

#### Fixed
- **MiniMax tool calling errors**: MiniMax was receiving OpenAI-format native tool calls which it doesn't support reliably. Now uses `tool_format: text` — tools are described in the system prompt and parsed from text output.
- **Tool format propagated through hot-swap**: `_handle_model_update()` now passes `tool_format` from provider config when creating new NVIDIAKit instances.

#### Files Modified
- `config/provider-registry.yaml` — Added `tool_format` to all 16 providers
- `aether/provider_router.py` — Exposes `tool_format` in config and LLM config
- `aether/nvidia_kit.py` — `LLMConfig.tool_format`, `_complete_without_native_tools()`, routing in `complete_with_tools()`
- `aether/agent_websocket.py` — Passes `tool_format` on session init and hot-swap
- `aether/api_server.py` — `LITELLM_2_MODELS`, `_fetch_models_dynamic()`, litellm-2 fallback logic

### 2026-02-14 - Provider Agnosticism & Hot Model Swapping

#### Fixed
- **Hot model swap bug**: Model name wasn't updating during hot-swap because backend tried to read from a stale Python module import. Fixed by sending `model_id` directly from frontend in the WebSocket `update_model` message.
- **Anthropic API key missing from Docker**: `ANTHROPIC_API_KEY` and 8 other provider keys were never passed to the container via `docker-compose.yml`. All provider keys now included.
- **Anthropic API format**: NVIDIAKit was sending OpenAI-format requests to Anthropic. Added full Anthropic Messages API support:
  - `x-api-key` header (not `Authorization: Bearer`)
  - `anthropic-version: 2023-06-01` header
  - `/v1/messages` endpoint (not `/chat/completions`)
  - System message extraction (separate `system` field)
  - Tool format conversion (`input_schema` not `parameters`)
  - Response parsing (content blocks, input_tokens/output_tokens)
- **Model dropdown styling**: White text on white background. Added explicit dark theme classes.
- **Provider detection**: Hardcoded `"litellm" if "litellm" in url else "nvidia"` replaced with actual provider name from `provider_router`.
- **API key error messages**: No longer says "add NVIDIA_API_KEY" when using Anthropic.
- **Model validation**: Relaxed to allow unlisted models (some providers have models not in their `/models` response).

#### Implemented
- **Provider selector UI**: Dropdown above model selector, fetches from `/api/providers`, switches via `/api/provider/set`, auto-refreshes model list.
- **Dynamic provider-aware model fetching**: Each provider returns its own models (hardcoded for Anthropic/Minimax/Nvidia, dynamic for OpenAI-compatible providers).
- **Hot model swapping**: `update_model` WebSocket message recreates LLM client without reconnecting. No session loss, no context loss, sub-second swap.
- **Anthropic-style Skills system**: Full architecture with `SkillMetadata`, `SkillParameter`, `SkillRegistry`, `SkillResult`. API endpoints for listing, executing, and filtering skills by category. Built-in `git-commit` skill.
- **Context gauge button**: Small circular indicator next to input area showing context window utilization.

#### Files Modified
- `aether/agent_websocket.py` - Hot-swap handler, provider detection
- `aether/nvidia_kit.py` - Anthropic API format, provider-agnostic headers
- `aether/api_server.py` - Provider-aware model fetching, skills endpoints, relaxed validation
- `aether/provider_router.py` - Provider routing logic
- `docker-compose.yml` - All provider API keys
- `ui/client/src/hooks/useAgentRuntime.ts` - `updateModel(modelId, provider)` method
- `ui/client/src/components/AetherPanelV2.tsx` - Provider selector, dropdown styling, hot-swap calls

#### Files Created
- `aether/skills/__init__.py` - Skills module
- `aether/skills/registry.py` - Core skill system (335 lines)
- `aether/skills/loader.py` - Skill loader
- `aether/skills/builtin/__init__.py` - Built-in skill registration
- `aether/skills/builtin/git_commit.py` - Git commit skill
- `config/provider-registry.yaml` - Provider configuration (14 providers)
- `ui/client/src/components/ContextGaugeButton.tsx` - Context gauge UI

### Previous Sessions
- **Tools benchmark**: 20-task benchmark completed, all tools functional
- **Qwen3-next as default model**: ASR integration working
- **UI onboarding flow**: Initial setup experience
- **Enhanced memory system**: Redis-backed identity, daily logs, long-term summaries, checkpoints
- **Fabric integration**: WebSocket stability fixes

---

## Roadmap - The Long Game

### Phase 1: Stability & Polish (Current)
> Get the current system rock-solid before adding complexity.

- [x] Provider-agnostic LLM routing (14+ providers)
- [x] Hot model swapping (zero-downtime)
- [x] Anthropic API format support
- [x] Skills system architecture
- [x] Redis Stack memory
- [x] Qdrant vector storage
- [x] WebSocket streaming with tool execution
- [x] ASR via Speechmatics
- [ ] Fix context gauge / token counter (debug logging in place)
- [ ] Verify Anthropic API key works end-to-end in production
- [ ] Update hardcoded model lists (add minimax-m2.5, etc.)
- [ ] Production deployment to aetherops.aetherpro.us

### Phase 2: Self-Correction & Memory Intelligence
> Make the agent learn from its mistakes and successes.

- [ ] **RepairableException pattern**: 3-tier error system
  - `RepairableToolError` - Feed error back to LLM for self-correction
  - `FatalToolError` - Stop the loop
  - `InterventionRequired` - Ask user for help
  - This replaces generic try/catch and makes the agent self-healing

- [ ] **Solution memory**: Auto-extract successful problem-solution pairs
  - Store in Qdrant with semantic embeddings
  - On new tasks, query solutions store first
  - Inject relevant solutions into context
  - The agent gets better over time

- [ ] **Lifecycle hooks / extension system**: Based on Agent Zero's pattern
  - `before_llm_call` - Modify prompt, inject context
  - `after_llm_response` - Post-process, extract metadata
  - `before_tool_execute` - Validation, permission checks
  - `after_tool_execute` - Logging, result transformation
  - `session_start` / `session_end` - Memory consolidation
  - Plugins register into hooks without modifying core code

### Phase 3: Multi-Model Orchestration (Warm Orchestration)
> The main agent becomes a conductor, delegating to specialized models.

- [ ] **Model roles in provider registry**:
  ```yaml
  roles:
    chat: litellm/qwen3-next        # Main conversation
    utility: litellm/qwen3-mini     # Memory ops, summarization
    vision: self-hosted/qwen3-vl    # Vision/OCR tasks
    embedding: nvidia/nv-embedqa    # Vector embeddings
    tts: self-hosted/tts-model      # Voice synthesis
  ```

- [ ] **Utility LLM for background tasks**: Small/fast model for:
  - Memory query reformulation
  - Context compression
  - Solution extraction
  - Relevance filtering
  - Saves cost and latency vs using the main model

- [ ] **Subordinate agent spawning**:
  - Main agent can call `spawn_subordinate(task, tools_subset)` as a tool
  - Child gets clean context focused on subtask
  - Result flows back to parent
  - Enables complex task decomposition

- [ ] **Vision/OCR model pipeline**:
  - Dedicated self-hosted vision model (e.g., Qwen3-VL, phi-4-mm)
  - Main agent delegates vision tasks: screenshot analysis, browser control, form filling, document OCR
  - Computer use capabilities without needing a vision-capable main model
  - The vision model is a tool, not the primary interface

### Phase 4: Voice & Audio Pipeline
> Full voice-first interaction, all self-hosted.

- [ ] **Self-hosted ASR**: Replace Speechmatics cloud with local model
  - Whisper-large-v3 or equivalent
  - Maintain same accuracy level
  - Zero-latency local inference

- [ ] **Dedicated TTS model**: Aether's voice
  - Self-hosted text-to-speech
  - Consistent voice identity across sessions
  - Streaming TTS for real-time responses
  - Voice style/personality configuration

- [ ] **Full voice pipeline**: ASR -> Agent -> TTS
  - End-to-end voice conversations
  - No cloud dependencies for audio

### Phase 5: Tool Ecosystem Expansion
> Best of both worlds: Python power + TypeScript ecosystem.

- [ ] **OpenClaw-style TypeScript tools bridge**:
  - Run TS-based tools alongside Python tools
  - Access the rich npm/TypeScript tool ecosystem
  - Unified tool registry across languages

- [ ] **SKILL.md standard support**:
  - Parse SKILL.md files (YAML frontmatter + markdown)
  - Compatible with Claude Code, Cursor, Codex
  - Non-developers can write skills as markdown
  - Community skill sharing

- [ ] **MCP server integration**:
  - Act as MCP client to connect to external tool servers
  - Support Stdio, SSE, and Streamable HTTP transports
  - Auto-discover tools from MCP servers

- [ ] **Enhanced Docker sandboxing**:
  - Agent Zero-style isolated Linux environment per task
  - Full system access within sandbox (apt install, etc.)
  - Clean separation between agent runtime and execution environment

### Phase 6: Embedding & Knowledge Pipeline
> Smart document ingestion and retrieval.

- [ ] **Best embedding model selection**:
  - Evaluate: Nvidia NV-EmbedQA, Google Gemini embeddings, Cohere embed-v3, local sentence-transformers
  - Benchmark against Qdrant for retrieval quality
  - Support both API-based and self-hosted embeddings

- [ ] **Knowledge import pipeline**:
  - Drop files into a directory -> auto-vectorize into Qdrant
  - MD5 change detection for automatic re-embedding
  - Support: PDF, markdown, code files, web pages
  - Three-stage RAG: query reformulation -> vector search -> relevance filtering

- [ ] **Qdrant optimization**:
  - Collection schemas per memory category (solutions, knowledge, fragments)
  - Filtered search with metadata (timestamps, categories, tags)
  - Quantization for large collections

### Phase 7: Production & Scale
> Deploy, monitor, advertise.

- [ ] **Production deployment**: aetherops.aetherpro.us
- [ ] **Multi-tenant support**: Multiple users, isolated sessions
- [ ] **Auth/OIDC integration**: User accounts, API keys
- [ ] **Usage tracking & billing**: Per-provider cost tracking
- [ ] **Health dashboard**: Provider status, model availability, memory usage
- [ ] **Horizontal scaling**: Multiple API server instances behind load balancer

---

## The Hybrid Model Philosophy

AetherOps is designed as a **hybrid system**:

```
Self-Hosted (Power Users)          Cloud (Accessibility)
========================          =====================
LiteLLM proxy -> local models     Anthropic API
Self-hosted vision/OCR model      OpenRouter / OpenAI
Self-hosted TTS model             Speechmatics ASR
Self-hosted ASR model             Groq / Together / etc.
Self-hosted embeddings            Nvidia / Cohere embeddings
Local Qdrant                      Hosted Qdrant
Local Redis                       Hosted Redis
```

If you have GPUs, run everything locally. If you don't, swap in API keys and the entire system works identically. The `provider_router` and model roles system make this seamless.

---

## Provider Registry (Current)

| Provider | Type | Status |
|----------|------|--------|
| LiteLLM (primary) | OpenAI-compatible proxy | Active, default |
| LiteLLM-2 | OpenAI-compatible proxy | Available |
| Anthropic | Native API | Supported (Anthropic format) |
| OpenAI | Native API | Available |
| OpenRouter | OpenAI-compatible | Available |
| Minimax | OpenAI-compatible | Available |
| Nvidia | OpenAI-compatible | Available |
| Groq | OpenAI-compatible | Available |
| Together | OpenAI-compatible | Available |
| Mistral | OpenAI-compatible | Available |
| Perplexity | OpenAI-compatible | Available |
| Cohere | Native API | Available |
| Google | OpenAI-compatible | Available |
| Qwen | OpenAI-compatible | Available |
| Kimi | OpenAI-compatible | Available |
| HuggingFace | HuggingFace API | Available |

---

## Self-Hosted Model Targets

| Role | Current | Target |
|------|---------|--------|
| **Chat (primary)** | qwen3-next-instruct (via LiteLLM) | Same, or best available |
| **Vision/OCR** | None | qwen3-vl-thinking, phi-4-mm, or step-3-vl |
| **Embedding** | None (Qdrant direct) | TBD - evaluating options |
| **ASR** | Speechmatics (cloud) | Whisper-large-v3 or equivalent |
| **TTS** | None | TBD - self-hosted voice model |
| **Utility** | Same as chat | Small/fast model for background ops |

---

## Design Principles

1. **Incremental complexity** - Add one capability at a time. Don't create soup.
2. **Provider agnosticism** - Never lock in to one provider or model.
3. **Self-hosted first, cloud fallback** - Power users run everything locally.
4. **Async-native** - Everything is asyncio. No threads, no blocking.
5. **Tool-first** - The agent's power comes from tools, not prompt engineering.
6. **Memory makes intelligence** - Solution recall, context compression, identity persistence.
7. **Production-grade** - Docker, health checks, proper logging, error handling.

---

*AetherOps: One agent to rule them all.*
