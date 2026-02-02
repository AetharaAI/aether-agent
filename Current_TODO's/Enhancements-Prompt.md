Below is a **single, copy-paste prompt** you can hand to your internal coding agent. It folds in everything you asked for — **implementation plan first, collapsible thinking blocks, a modular skeleton, a provider layer, safer memory usage, and UI fixes — without blowing up what already works.**

Use this **verbatim**:

---

## **PROMPT FOR INTERNAL CODING AGENT**

You are enhancing the Aether Agent system incrementally. **Do not rewrite everything.** Make minimal, safe changes that can be tested step-by-step.

### **0) REQUIRED: Propose an Implementation Plan First**

Before writing any code, respond with a concise plan that includes:

* What files you will change
* What risks exist
* How we can test each step
* What can be rolled back if it breaks

Wait for approval before coding.

---

### **1) UI — Collapsible “Thinking Blocks” (Top Priority)**

Goal: The UI must cleanly separate *reasoning* from *final answer*.

Implement this behavior:

* The LLM’s chain-of-thought should appear as a **collapsible block labeled:**
  **“Aether Reasoning (click to expand)”**
* Default state: **collapsed**
* Expanded state: scrollable panel with monospace text
* The **final answer must appear cleanly below**, never mixed with reasoning.

Where this should live:

* In the WebSocket message renderer in `ui/client/src/components/AetherPanel.tsx`
* Add a small chevron icon (▶ / ▼) for expand/collapse
* Preserve streaming behavior — reasoning can stream inside the collapsible block

---

### **2) Fix the Context Gauge in the UI**

The existing “Context Usage” gauge should reflect **real system state**, not a fake percentage.

Wire it to:

* `/api/context/stats`

Gauge behavior:

* 0–100% based on:

  * Redis working memory size
  * Checkpoint count
  * Daily memory hash size
* If the API is unavailable, display: **“Context: Unknown”** (don’t crash the UI).

Add a tooltip that says:

> “Aether compresses context automatically when limits are reached.”

---

### 3) Make the Architecture Explicit (NO REFACTOR)

Do NOT refactor, rewrite, or move working code.

The goal is to **label and organize concepts, not change behavior.**

Using the existing file layout, clearly identify these layers in comments, README, and docstrings only:

AETHER CORE (conceptual map — not folder changes)

- Identity Layer  
  (aether_memory.py + identity-related helpers)

- Memory Layer (Redis Stack)  
  (your existing Redis usage, checkpoints, compression, keys)

- Context Layer  
  (context stats, limits, compression, rolling windows)

- LLM Provider Layer — NEW *concept only*  
  (create a small folder `aether/providers/` that contains EMPTY stubs only)

- Tool Layer  
  (aether/tools/registry.py — see next section)

Rules:
- Do NOT rename existing modules.
- Do NOT split files unless absolutely necessary.
- Prefer **comments, docstrings, and diagrams** over code movement.
- Treat this as “drawing clean boundaries on a working map,” not rebuilding the map.


### **4) Add a Pluggable Provider Layer (Skeleton Only)**

Prepare for multi-model support **without wiring real clients yet.**

Create a new module:

`aether/providers/`

Define an interface like:

```
ProviderClient:
- generate()
- stream()
- health_check()
```

Stub providers (no API calls yet):

* openai_provider.py
* nvidia_provider.py
* anthropic_provider.py
* openrouter_provider.py
* gemini_provider.py

Default remains **my local model**.
We will integrate real APIs later.

---

### **5) Make Tools First-Class (Agent-Accessible)**

Expose a formal tool registry so the agent can call things safely.

Create:
`aether/tools/registry.py`

Register at minimum:

* checkpoint()
* compress_context()
* get_context_stats()
* terminal_exec()
* file_upload()

Each tool must:

* Log calls to Redis
* Be permissioned (semi vs autonomous mode matters)

---

### **6) Memory Safety Fix (Important)**

Right now Redis is growing forever.

Add:

* Automatic daily compression via `/api/context/compress`
* Keep only last **7 days** of raw memory hashes
* Older data remains in compressed form

No user-facing behavior change — just quieter, safer persistence.

---

### **7) Address the Logs You Shared**

Based on your logs:

* Redis warnings about memory overcommit are **fine for now**, but:

  * Add a startup note in logs:
    `"Running in dev memory mode — production requires vm.overcommit_memory=1"`

* WebSocket reconnects are normal — do **not** panic.
  But add:

  * Auto-retry with exponential backoff
  * Small UI toast: “Reconnecting to Aether…”

---

### **8) Keep Everything Incremental**

Deliver changes in this order:

1. Collapsible thinking blocks
2. Fix context gauge
3. Create modular folder structure
4. Add provider skeleton
5. Add tool registry
6. Memory safety improvements

Each step must be testable before moving on.

---

### **9) Constraints**

* Do **NOT** add WhatsApp, Telegram, or daemon gateways.
* Do **NOT** introduce remote backdoors or telemetry.
* Keep everything self-hosted and auditable.
* Preserve Docker compatibility.

---

If you want, next we can:

* design your onboarding flow, or
* harden this into a real product roadmap for AetherPro.

You’re not building a toy agent — you’re building a sovereign one.

