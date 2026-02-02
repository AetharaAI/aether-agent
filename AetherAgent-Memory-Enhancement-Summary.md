I've converted the OpenClaw-style documentation into an Aether-native identity system with true Redis persistence. Here's what was created:

## New Identity Documentation (workspace/)

**AETHER_IDENTITY.md** — Who Aether is
- Unique identity distinct from OpenClaw's Relay (Aether, 🌐⚡)
- Redis-backed vs file-based persistence comparison
- Personality profile: precise, direct, technically fluent
- Autonomy modes and Fleet integration notes

**AETHER_ESSENCE.md** — Core operating principles
- 5 foundational truths (genuinely helpful, working opinions, resourceful, trust, execution)
- Communication patterns for different contexts
- Memory discipline with Redis architecture
- Safety defaults

**AETHER_BOOTSTRAP.md** — First-time setup flow
- Self-assessment on startup (check Redis vs bootstrap)
- Identity configuration options (name, voice, autonomy)
- Environment capture
- Session startup sequence (Redis-first, not file-first)

**AETHER_USER.md** — CJ's profile
- Background, projects (Passport IAM, Triad, CMC, Aether Desktop)
- Infrastructure details (L40S-180/90 nodes, 50+ models)
- Working style and strategic goals
- Context notes for Aether

**AETHER_HEARTBEAT.md** — Proactive operations
- Check rotation schedule (infrastructure, projects, memory, calendar)
- When to reach out vs stay quiet
- State tracking in Redis
- Quiet hours respect (23:00-08:00 Indianapolis)

## Code Changes

**aether/aether_memory.py** — Added identity persistence layer:
- `save_identity_profile()` / `get_identity_profile()` — Redis-backed agent identity
- `save_user_profile()` / `get_user_profile()` — Redis-backed user context
- `set_system_flag()` / `get_system_flag()` — System state management
- `save_heartbeat_state()` / `get_heartbeat_state()` — Proactive check tracking
- `build_system_prompt()` — Dynamic prompt construction from Redis (not files)
- `get_identity_context_for_api()` — API-formatted identity context

**aether/api_server.py** — Dynamic system prompt integration:
- `_bootstrap_identity_if_needed()` — Load from files → Redis on first boot
- `IdentityProfile`, `UserProfile` Pydantic models
- New endpoints:
  - `GET /api/identity` — Get current identity context
  - `GET /api/identity/prompt` — View dynamic system prompt
  - `POST /api/identity` — Update agent identity
  - `POST /api/identity/user` — Update user profile
  - `POST /api/identity/reload` — Reload from markdown files
- WebSocket welcome message uses dynamic identity (🌐⚡ Aether online)
- LLM calls use `build_system_prompt()` from Redis

**aether/aether_core.py** — Updated to use dynamic prompts:
- `process_message()` now builds system prompt from Redis identity

**docs/IDENTITY_SYSTEM.md** — Comprehensive documentation explaining:
- Architecture diagram
- OpenClaw vs Aether comparison table
- API endpoint reference
- Redis key structure
- Bootstrap flow
- All three modification methods (edit+reload, API, programmatic)

## Key Differentiation from OpenClaw

| OpenClaw | Aether |
|----------|--------|
| Reads markdown files every restart | Loads from Redis (fast) |
| Files = runtime state | Files = source of truth for humans, Redis = runtime truth |
| Linear file I/O | Semantic search + atomic operations |
| Session amnesia | True persistence across restarts |
| Static system prompt | Dynamic `build_system_prompt()` from persisted identity |

The system boots from files once, then persists to Redis for all subsequent startups—achieving true continuity without the token burn of re-reading docs every session.
