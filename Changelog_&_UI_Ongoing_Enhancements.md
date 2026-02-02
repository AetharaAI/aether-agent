You are Aether’s internal lead engineer AI.

Your mission is to extend the system in small, safe steps — not to refactor everything at once.

════════════════════════════════════
PART 1 — CHANGELOG (PUBLIC-FACING)
════════════════════════════════════

Create a clean, human-readable changelog file:
AETHER_CHANGELOG.md

Structure it like this:

1) “Persistence Breakthrough”
Explain plainly that:
- Aether now keeps identity, context, and memory alive across restarts using Redis.
- Markdown remains human source-of-truth; Redis is runtime truth.

2) “What changed under the hood”
At a high level (no code details):
- Redis-backed memory instead of file-only state  
- Proactive heartbeat  
- Dynamic system prompt built from memory  
- Checkpoints + compression  

3) “Why this matters”
Explain that this is the foundation for:
- Passport identities  
- Triad (Redis + Postgres) cloud memory  
- Multi-agent Aether (Percy, Maestro, Relay)  
- UI-first onboarding for non-developers  

Keep it crisp, not hypey.

════════════════════════════════════
PART 2 — MODULAR UI-FIRST ONBOARDING
════════════════════════════════════

Design a new UI screen called:
“Aether Setup”

Important constraint:
This must be a **modular skeleton**, not a final product.

Meaning:
- The onboarding flow should have clearly labeled sections
- Each section should be replaceable or extendable later
- New sections must be addable without rewriting the page

Proposed structure (you may refine wording):

Section 1 — Meet Aether  
- Show Aether’s name  
- Show Aether icon (🌐⚡)  
- Show current autonomy mode (semi/auto)  

Section 2 — Who Are You?  
A simple form that writes to memory via the existing Python layer:
- Name  
- Role  
- Timezone  
- Active projects  

Do NOT assume new REST endpoints exist.  
If needed, assume this writes through the existing memory system.

Section 3 — Memory Preferences  
Two toggles:
- “Remember me across sessions” (default ON)  
- “Enable background heartbeat” (default ON)  

Section 4 — **Providers (PLACEHOLDER ONLY)**  
This is a **future slot**, not an implementation task.

The UI should visually reserve space for a Providers panel that can later support:
- Local / self-hosted models  
- OpenAI  
- NVIDIA  
- Anthropic  
- Gemini  
- OpenRouter  

For now, simply label it:
“Model Providers — coming soon.”

Do NOT implement any clients, keys, or integrations yet.

Section 5 — Done  
Display:
“Aether is now your persistent assistant.”

════════════════════════════════════
PART 3 — CONTEXT GAUGE + MEMORY (PHASED)
════════════════════════════════════

Do NOT redesign memory storage.

Assume Redis is already the source of truth.

Your job is to:
1) Determine how to compute memory usage from existing Redis keys.  
2) Propose a minimal update to /api/context/stats so the UI can show a real gauge.  
3) Avoid creating new endpoints unless absolutely necessary.

If identity APIs like /api/identity do NOT exist yet:
- Do NOT invent them now.  
- Use the current Redis-backed memory layer.  
- Simply recommend lightweight endpoints for a later phase.

════════════════════════════════════
PART 4 — TYPESCRIPT ROLE (LIGHT TOUCH)
════════════════════════════════════

Aether’s brain remains in Python.

TypeScript is for:
- UI  
- Helper utilities  
- Future file/git tools  

Do NOT attempt to replicate Clawdbot.  
Only suggest where TypeScript *could* plug in later.

════════════════════════════════════
PART 5 — OUTPUT
════════════════════════════════════
Propose a full implementation plan first then:
Return:
1) Full AETHER_CHANGELOG.md  
2) A simple bullet-point UI onboarding design  
3) A tiny list of backend tweaks (if any)  

