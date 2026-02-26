Alright. Below is a **concrete implementation spec** you can hand to a coder and start building immediately. This assumes your current reality: **Passport (agent identity), AetherOps (tools), Mongo (ledger-ish agent notes), Postgres, Redis/Valkey, Qdrant + reranker**, and you’re adding **OTel + Continuity Engine**.

---

# Continuity Illusion Engine (CIE) — Implementation Spec v1

**Goal:** Persistent identity + continuity contracts + deterministic prompt compilation + replayable provenance, across model swaps and context resets.

## 0) Non-negotiable invariants

1. **Immutable event truth** (append-only): no rewriting history.
2. **Continuity Contracts are versioned artifacts**: every run consumes vN and produces vN+1.
3. **Deterministic context assembly**: same inputs → same context pack (within configured randomness).
4. **Provenance for every state change**: trace/span IDs or event IDs recorded.
5. **Vector is never truth**: Qdrant is a retrieval helper only.

---

# 1) Services Layout (microservices, minimal count)

## 1.1 Required services

1. **cie-gateway (API)**

   * Receives user messages / attachments
   * Calls Context Governor → Executive Model → returns response
   * Emits OTel trace root for each run

2. **cie-governor (Context Governor / Prompt Compiler)**

   * Deterministic pack builder (budgeting, dedupe, scope routing)
   * Pulls state + memories from stores
   * Produces `ContextPack` + `WriteIntent`

3. **cie-steward (Memory Steward)**

   * Async consumer of “run completed” events
   * Turns raw events into:

     * episodic memories
     * procedural memories
     * semantic memory docs
     * state updates (Self/World/Thread)
   * Reconciliation + conflict tracking

4. **cie-reconciler (can be inside steward initially)**

   * Detect conflicts across state versions
   * Resolves via rules
   * Writes conflict objects

5. **cie-telemetry (OTel Collector)**

   * Receives traces/logs/metrics
   * Exports to storage targets

## 1.2 Storage services

* **Postgres**: canonical state + memory objects + contracts + indices
* **Mongo** (optional v1): agent-authored “notes” / structured scratchpad
* **Valkey/Redis**: hot cache, queues, rate limiting, working sets
* **Qdrant**: vector search helper (semantic retrieval)
* **Object storage** (MinIO/S3) optional: large artifacts, trace payload archives

---

# 2) Process Orchestration (runtime flow)

## 2.1 Request lifecycle (sync path)

**R0**: request arrives at gateway → creates `run_id`, root `trace_id`

**R1**: gateway calls governor:

* Input: user message + `agent_id` + `session_id` + attachments metadata
* Output: `context_pack`, `write_intent`, `context_pack_hash`

**R2**: gateway invokes **Executive model** (your “brain”):

* Sends context_pack + user message
* Receives response + tool plan or tool calls

**R3**: tool calls execute (AetherOps tools)

* Each tool call is a child span with hashes of args/results

**R4**: gateway returns final output to user

**R5**: gateway emits `RunCompleted` event to queue (Redis stream / NATS / Kafka)

* Steward consumes it async

## 2.2 Memory lifecycle (async path)

**M1**: steward consumes RunCompleted (with trace_id and run_id)
**M2**: steward fetches run details (from Postgres run record, logs, or trace export)
**M3**: steward generates memory artifacts + state updates
**M4**: reconciler resolves conflicts
**M5**: steward writes:

* state vN+1
* new continuity contract vN+1
* memories + embeddings
* evaluation metrics

---

# 3) Data Model — Postgres Schemas (exact)

### 3.1 Extensions

```sql
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS uuid-ossp;
```

### 3.2 Agent identity (Passport linkage)

```sql
CREATE TABLE agent_identity (
  agent_id            UUID PRIMARY KEY,
  passport_id         TEXT NOT NULL,
  issuer              TEXT NOT NULL,
  subject             TEXT NOT NULL,
  public_key_jwk      JSONB NOT NULL,
  capabilities        JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX agent_identity_passport_id_idx ON agent_identity(passport_id);
```

### 3.3 Sessions

```sql
CREATE TABLE cie_session (
  session_id          UUID PRIMARY KEY,
  agent_id            UUID NOT NULL REFERENCES agent_identity(agent_id),
  user_id             TEXT,
  project_id          TEXT,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_active_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX cie_session_agent_idx ON cie_session(agent_id);
CREATE INDEX cie_session_project_idx ON cie_session(project_id);
```

### 3.4 Runs (every model invocation chain)

```sql
CREATE TABLE cie_run (
  run_id              UUID PRIMARY KEY,
  session_id          UUID NOT NULL REFERENCES cie_session(session_id),
  agent_id            UUID NOT NULL REFERENCES agent_identity(agent_id),
  trace_id            TEXT NOT NULL,                  -- from OTel
  model_id            TEXT NOT NULL,                  -- e.g. qwen3-next-80b
  intent              TEXT,
  status              TEXT NOT NULL DEFAULT 'completed', -- completed/failed
  started_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  completed_at        TIMESTAMPTZ,
  tokens_in           INT,
  tokens_out          INT,
  latency_ms          INT,
  user_input          TEXT NOT NULL,
  response_output     TEXT,
  context_pack_hash   TEXT NOT NULL,
  continuity_contract_id UUID,
  tool_summary        JSONB NOT NULL DEFAULT '{}'::jsonb,
  error               JSONB
);

CREATE INDEX cie_run_session_idx ON cie_run(session_id, started_at DESC);
CREATE INDEX cie_run_trace_idx ON cie_run(trace_id);
```

### 3.5 Immutable events (append-only facts)

Use this as the canonical “truth” mirror of telemetry that you can query fast.

```sql
CREATE TABLE cie_event (
  event_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id              UUID NOT NULL REFERENCES cie_run(run_id),
  trace_id            TEXT NOT NULL,
  span_id             TEXT,
  event_type          TEXT NOT NULL, -- prompt_built/tool_called/tool_result/memory_write/etc
  occurred_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  payload             JSONB NOT NULL,
  payload_hash        TEXT NOT NULL
);

CREATE INDEX cie_event_run_idx ON cie_event(run_id, occurred_at);
CREATE INDEX cie_event_type_idx ON cie_event(event_type);
CREATE INDEX cie_event_trace_span_idx ON cie_event(trace_id, span_id);
```

### 3.6 Rolling state (Self/World/Thread)

Versioned. Small. Always present.

```sql
CREATE TABLE cie_state (
  state_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id          UUID NOT NULL REFERENCES cie_session(session_id),
  agent_id            UUID NOT NULL REFERENCES agent_identity(agent_id),
  state_type          TEXT NOT NULL, -- self/world/thread
  version             INT NOT NULL,
  content             JSONB NOT NULL,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  provenance          JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE UNIQUE INDEX cie_state_unique_version
  ON cie_state(session_id, agent_id, state_type, version);

CREATE INDEX cie_state_latest_idx
  ON cie_state(session_id, agent_id, state_type, version DESC);
```

### 3.7 Open loops (tracked obligations)

```sql
CREATE TABLE cie_open_loop (
  loop_id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id          UUID NOT NULL REFERENCES cie_session(session_id),
  agent_id            UUID NOT NULL REFERENCES agent_identity(agent_id),
  status              TEXT NOT NULL DEFAULT 'open', -- open/closed/snoozed
  title               TEXT NOT NULL,
  details             TEXT,
  tags                TEXT[] NOT NULL DEFAULT '{}'::text[],
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  closed_at           TIMESTAMPTZ,
  provenance          JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX cie_open_loop_status_idx ON cie_open_loop(session_id, status);
```

### 3.8 Memory objects (episodic/procedural/semantic)

```sql
CREATE TABLE cie_memory (
  memory_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id          UUID REFERENCES cie_session(session_id),
  agent_id            UUID NOT NULL REFERENCES agent_identity(agent_id),
  scope               TEXT NOT NULL,  -- global/project:<id>/task:<id>/session:<id>
  memory_type         TEXT NOT NULL,  -- episodic/procedural/semantic/preference/fact
  importance          INT NOT NULL DEFAULT 50,  -- 0..100
  confidence          INT NOT NULL DEFAULT 70,  -- 0..100
  ttl_days            INT,                     -- optional decay
  content             JSONB NOT NULL,          -- normalized schema per type
  source_event_ids    UUID[] NOT NULL DEFAULT '{}'::uuid[],
  source_trace_ids    TEXT[] NOT NULL DEFAULT '{}'::text[],
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX cie_memory_scope_idx ON cie_memory(agent_id, scope);
CREATE INDEX cie_memory_type_idx ON cie_memory(agent_id, memory_type);
CREATE INDEX cie_memory_importance_idx ON cie_memory(agent_id, importance DESC);
```

### 3.9 Semantic documents (for vector indexing)

Separate table to manage embeddings + Qdrant IDs.

```sql
CREATE TABLE cie_semantic_doc (
  doc_id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  memory_id           UUID REFERENCES cie_memory(memory_id) ON DELETE CASCADE,
  agent_id            UUID NOT NULL REFERENCES agent_identity(agent_id),
  scope               TEXT NOT NULL,
  title               TEXT,
  text                TEXT NOT NULL,
  qdrant_point_id     TEXT, -- point id in qdrant
  embedding_model     TEXT NOT NULL,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX cie_semantic_scope_idx ON cie_semantic_doc(agent_id, scope);
```

### 3.10 Continuity Contracts (the artifact the model “lives in”)

```sql
CREATE TABLE cie_continuity_contract (
  contract_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id          UUID NOT NULL REFERENCES cie_session(session_id),
  agent_id            UUID NOT NULL REFERENCES agent_identity(agent_id),
  version             INT NOT NULL,
  self_state_id       UUID NOT NULL REFERENCES cie_state(state_id),
  world_state_id      UUID NOT NULL REFERENCES cie_state(state_id),
  thread_state_id     UUID NOT NULL REFERENCES cie_state(state_id),
  open_loop_ids       UUID[] NOT NULL DEFAULT '{}'::uuid[],
  included_memory_ids UUID[] NOT NULL DEFAULT '{}'::uuid[],
  context_budget       JSONB NOT NULL,   -- budgets used
  pack                JSONB NOT NULL,    -- final assembled pack (structured)
  pack_hash           TEXT NOT NULL,
  provenance          JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX cie_contract_unique_version
  ON cie_continuity_contract(session_id, agent_id, version);

CREATE INDEX cie_contract_latest_idx
  ON cie_continuity_contract(session_id, agent_id, version DESC);
```

### 3.11 Conflicts (identity drift prevention)

```sql
CREATE TABLE cie_conflict (
  conflict_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id          UUID NOT NULL REFERENCES cie_session(session_id),
  agent_id            UUID NOT NULL REFERENCES agent_identity(agent_id),
  conflict_type       TEXT NOT NULL, -- preference/world_fact/procedure/etc
  left_ref            JSONB NOT NULL,
  right_ref           JSONB NOT NULL,
  resolution          JSONB,
  status              TEXT NOT NULL DEFAULT 'open', -- open/resolved
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  resolved_at         TIMESTAMPTZ
);

CREATE INDEX cie_conflict_status_idx ON cie_conflict(session_id, status);
```

### 3.12 Evaluation (to stop vibes)

```sql
CREATE TABLE cie_eval (
  eval_id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id              UUID NOT NULL REFERENCES cie_run(run_id),
  session_id          UUID NOT NULL REFERENCES cie_session(session_id),
  agent_id            UUID NOT NULL REFERENCES agent_identity(agent_id),
  retrieval_precision NUMERIC,
  regret_rate         NUMERIC,
  contradiction_count INT,
  loop_closure_delta  INT,
  notes               JSONB,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

---

# 4) Qdrant Collections (exact)

Use one collection per agent or per environment namespace. Keep it simple.

**Collection:** `cie_semantic_v1`

Payload fields:

* `agent_id` (uuid string)
* `scope` (string)
* `doc_id` (uuid string)
* `memory_id` (uuid string)
* `type` (string)
* `importance` (int)
* `created_at` (iso)

Point ID: `qdrant_point_id` stored back in Postgres.

Reranker: run after top-k vector retrieval.

---

# 5) Redis / Valkey (queues + hot cache)

## 5.1 Streams

* `cie.run_completed` (RunCompleted events)
* `cie.memory_written` (optional)
* `cie.contract_created` (optional)

## 5.2 Hot caches

* `cie:latest_contract:{session_id}` → contract_id + pack_hash
* `cie:latest_state:{session_id}:{type}` → state_id + version
* `cie:tool_health:{tool_name}` → last status, latency averages

---

# 6) Context Governor: deterministic algorithms (spec)

## 6.1 Inputs

* `session_id`, `agent_id`
* `user_message`
* `attachments_meta[]`
* `model_id` (brain model)
* `token_budget` profile for model

## 6.2 Steps (mandatory)

1. **Intent classify** (deterministic rules first)

   * keyword + tool registry match
   * fallback: lightweight model classifier if unclear

2. **Scope determination**

   * default scope: `session:<session_id>`
   * if project_id present: also `project:<project_id>`
   * always include `global`

3. **Load latest states**

   * `SelfState vN`, `WorldState vN`, `ThreadState vN`

4. **Load open loops**

   * open only, sorted by importance + recency

5. **Select procedures**

   * from `cie_memory` where `memory_type='procedural'`
   * rank by tag match + last-used + failure proximity

6. **Retrieve episodic**

   * use keyword search in Postgres content OR semantic (optional)
   * rank by scope match + importance + recency

7. **Semantic retrieval (Qdrant)**

   * only if intent indicates missing knowledge
   * retrieve top 20; rerank; keep top 5-10 max

8. **Budget packing**

   * strict caps per section
   * dedupe via content hashes
   * prune low salience

9. **Emit Continuity Contract pack**

   * structured JSON + also a compiled text block for the brain model

10. **Emit WriteIntent**

* what should be written after the run completes

## 6.3 Output format

```json
{
  "context_pack": {
    "continuity_header": "...",
    "self_state": {...},
    "world_state": {...},
    "thread_state": {...},
    "open_loops": [...],
    "procedures": [...],
    "episodic": [...],
    "semantic": [...],
    "provenance": {...},
    "budgets_used": {...}
  },
  "write_intent": {
    "candidate_memories": [...],
    "candidate_state_updates": [...],
    "signals": {...}
  }
}
```

---

# 7) Memory Steward: write rules (spec)

## 7.1 Inputs

* RunCompleted event (run_id, trace_id)
* run transcript (user input, response, tool summary)
* context_pack metadata
* tool call outcomes
* any errors

## 7.2 Outputs

* new episodic memories (problem → solution)
* new procedures (if repeatable)
* new facts/preferences (if stable)
* updated rolling states
* conflict objects if contradictions
* new continuity contract vN+1

## 7.3 State update policy

Only update rolling state if:

* the signal is stable (preference, principle, confirmed infra change)
* provenance exists (tool output, explicit user statement, trace evidence)
  Otherwise write as episodic only.

---

# 8) OpenTelemetry instrumentation (required span naming)

Root span: `cie.run`

Child spans:

* `cie.governor.build_pack`
* `cie.brain.infer`
* `cie.tool.<tool_name>`
* `cie.steward.process_run` (async)
* `cie.memory.write`
* `cie.contract.create`

Required attributes (every span where relevant):

* `session_id`, `run_id`, `agent_id`
* `trace_id`, `span_id`
* `model_id`
* `prompt_hash`, `context_pack_hash`
* `memory_ids_injected`
* `tool_args_hash`, `tool_result_hash`
* `tokens_in`, `tokens_out`, `latency_ms`
* `status`, `error`

---

# 9) Deployment: docker-compose baseline (service map)

(You didn’t ask for compose text yet, so here’s the layout, not the file.)

* `cie-gateway` (FastAPI)
* `cie-governor` (FastAPI or internal gRPC)
* `cie-steward` (worker)
* `postgres`
* `valkey`
* `qdrant`
* `otel-collector`
* optional: `prometheus`, `loki`, `tempo` (or ClickHouse)

---

# 10) v1 Build Plan (fastest path)

**Day 1**

* Create Postgres schema
* Add run/session tables
* Implement governor pack builder v0 (no semantic retrieval yet)
* Add OTel spans in gateway/governor/tool runner

**Day 2**

* Implement steward v0: write episodes + update rolling state
* Create continuity contract v0 and force every run to consume it

**Day 3**

* Add Qdrant semantic retrieval + reranker
* Add conflict tracking
* Add eval metrics

---

# 11) What to implement first (ROI)

1. **Continuity Contract + versioning**
2. **Deterministic Context Governor budgets + dedupe**
3. **OTel provenance**
4. **Steward writing episodes/procedures**
5. **Semantic retrieval + rerank**
6. **Replay + evaluation harness**

---

If you want to move immediately from spec → code, next message I’ll output:

* the **exact Alembic migration** for all tables above
* a **FastAPI skeleton** for `cie-gateway`, `cie-governor`, `cie-steward`
* the **Redis stream event schema** (`RunCompleted`)
* and a minimal **docker-compose.yml** wiring Postgres/Valkey/Qdrant/OTel collector.

No questions, no delays—just paste-and-run scaffolding.

