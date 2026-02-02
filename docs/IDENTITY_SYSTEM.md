# Aether Identity System

**True persistence for AI agent identity and context.**

Unlike OpenClaw's file-based approach where agents re-read markdown files on every restart, Aether uses Redis-backed persistence for identity, user profiles, and system configuration. This enables true continuity across sessions.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        AETHER AGENT                              │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │   Identity   │◄──►│    Redis     │◄──►│   Identity   │      │
│  │   Profile    │    │   Backend    │    │    Docs      │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│         │                   │                   │               │
│         ▼                   ▼                   ▼               │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Dynamic System Prompt Builder                │  │
│  │   Combines identity + user profile + memory context      │  │
│  └──────────────────────────────────────────────────────────┘  │
│                              │                                  │
│                              ▼                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                  LLM (NVIDIA/Kimi/etc)                    │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## OpenClaw vs Aether Approach

| Aspect | OpenClaw | Aether |
|--------|----------|--------|
| **Storage** | Markdown files | Redis hashes/keys |
| **Persistence** | Files survive restart | True persistence + caching |
| **Startup** | Re-read all docs | Load from Redis (fast) |
| **Updates** | Edit files | API calls or file reload |
| **Search** | Linear file read | Semantic + full-text |
| **Access** | Filesystem only | API + filesystem |
| **Multi-instance** | File conflicts possible | Redis atomic operations |

---

## Identity Files

### Source Documentation (Markdown)

Located in `workspace/`:

| File | Purpose | Redis Key |
|------|---------|-----------|
| `AETHER_IDENTITY.md` | Who Aether is (name, emoji, voice) | `aether:identity:profile` |
| `AETHER_ESSENCE.md` | Core principles and behaviors | Included in profile |
| `AETHER_USER.md` | CJ's profile and preferences | `aether:user:profile` |
| `AETHER_BOOTSTRAP.md` | First-time setup flow | Reference only |
| `AETHER_HEARTBEAT.md` | Proactive check framework | Reference only |

### Redis Key Structure

```
aether:identity:profile     → Aether's self-concept
aether:user:profile         → User (CJ) profile
aether:system:flags         → System state flags
aether:system:heartbeat_state → Heartbeat tracking
```

---

## API Endpoints

### Get Identity Context
```bash
GET /api/identity
```
Returns current identity and user context from Redis.

### Get System Prompt
```bash
GET /api/identity/prompt
```
Returns the dynamically built system prompt.

### Update Identity
```bash
POST /api/identity
{
  "name": "Aether",
  "emoji": "🌐⚡",
  "voice": "efficient",
  "autonomy_default": "semi"
}
```

### Update User Profile
```bash
POST /api/identity/user
{
  "name": "CJ",
  "timezone": "America/Indianapolis",
  "projects": ["Passport IAM", "Triad Intelligence"]
}
```

### Reload from Files
```bash
POST /api/identity/reload
```
Reloads identity from markdown files (useful after editing docs).

---

## System Prompt Building

The [`build_system_prompt()`](aether/aether_memory.py) method dynamically constructs the LLM system prompt from:

1. **Identity Profile**
   - Name, emoji, voice style
   - Core values and principles
   - Autonomy mode defaults

2. **User Profile**
   - User name and timezone
   - Active projects and priorities
   - Communication preferences

3. **Memory Architecture**
   - Redis-backed persistence
   - Checkpoint/rollback capabilities
   - Semantic search integration

4. **Safety Guidelines**
   - When to ask vs execute
   - Autonomy mode behaviors
   - Context management rules

---

## Bootstrap Flow

```python
On Startup:
1. Connect to Redis
2. Check for existing identity in Redis
   ├─ If exists: Load from Redis (fast)
   └─ If empty: 
      1. Read AETHER_IDENTITY.md
      2. Parse key fields
      3. Store in Redis
      4. Mark bootstrap_complete
3. Same flow for user profile
4. Begin normal operation
```

---

## Modifying Identity

### Method 1: Edit Markdown + Reload
```bash
# Edit the docs
vim workspace/AETHER_IDENTITY.md

# Reload via API
curl -X POST http://localhost:8000/api/identity/reload
```

### Method 2: Direct API Update
```bash
# Update directly (skips files)
curl -X POST http://localhost:8000/api/identity \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Aether Pro",
    "emoji": "🚀",
    "voice": "conversational"
  }'
```

### Method 3: Programmatic (Python)
```python
await memory.save_identity_profile({
    "name": "Aether",
    "emoji": "🌐⚡",
    "voice": "efficient",
    "autonomy_default": "semi",
    "core_values": ["..."]
})
```

---

## Persistent Memory Keys

### Identity
```
Key: aether:identity:profile
Type: String (JSON)
Content: {
  "name": "Aether",
  "emoji": "🌐⚡",
  "voice": "efficient",
  "autonomy_default": "semi",
  "description": "Autonomous execution engine",
  "core_values": [...],
  "created_at": "2026-02-02T08:00:00",
  "updated_at": "2026-02-02T08:00:00"
}
```

### User
```
Key: aether:user:profile
Type: String (JSON)
Content: {
  "name": "CJ",
  "timezone": "America/Indianapolis",
  "role": "Founder/CTO",
  "projects": ["Passport IAM", "Triad Intelligence"],
  "priorities": [...]
}
```

### System Flags
```
Key: aether:system:flags
Type: Hash
Content: {
  "bootstrap_complete": "true",
  "first_boot_at": "2026-02-02T08:00:00",
  "maintenance_mode": "false"
}
```

---

## Comparison: Session Restart

### OpenClaw Style
```python
# Every restart:
1. Read IDENTITY.md
2. Read USER.md
3. Read SOUL.md
4. Read memory/YYYY-MM-DD.md
5. Reconstruct context
6. Begin responding

# Problems:
- Token burn re-reading files
- No memory of session state
- Filesystem I/O on every boot
```

### Aether Style
```python
# Every restart:
1. Connect to Redis
2. Get aether:identity:profile (1 Redis GET)
3. Get aether:user:profile (1 Redis GET)
4. Load recent memory (RedisSearch)
5. Begin responding

# Advantages:
- Fast startup (ms not seconds)
- True state persistence
- Semantic memory search
- Checkpoint/rollback
```

---

## Future Enhancements

- [ ] Voice style switching per conversation
- [ ] Multi-user support with per-user identity adaptation
- [ ] Identity versioning with rollback
- [ ] Automatic profile updates from behavior analysis
- [ ] Identity "moods" for different contexts (work/casual)

---

## Key Insight

**OpenClaw treats identity as documentation.**  
**Aether treats identity as state.**

The markdown files are the *source of truth* for humans.  
Redis is the *runtime truth* for the agent.

Both can coexist. Edit the markdown for major changes. Use the API for dynamic updates. Reload when needed. Persist always.
