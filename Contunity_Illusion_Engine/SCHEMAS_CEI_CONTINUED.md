```text
CIE/
  docker-compose.yml
  services/
    common/
      __init__.py
      config.py
      db.py
      models.py
      telemetry.py
      redis_bus.py
      schemas.py
      util.py
    cie_gateway/
      __init__.py
      main.py
    cie_governor/
      __init__.py
      main.py
    cie_steward/
      __init__.py
      worker.py
  alembic.ini
  alembic/
    env.py
    script.py.mako
    versions/
      0001_cie_initial.py
  pyproject.toml  (or requirements.txt)
```

Below are the **exact deliverables** you asked for.

---

## 1) Alembic migration: `alembic/versions/0001_cie_initial.py`

```python
"""cie initial

Revision ID: 0001_cie_initial
Revises:
Create Date: 2026-02-21

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0001_cie_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Extensions (safe to run even if already enabled)
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")
    op.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";")

    # -------------------------
    # agent_identity
    # -------------------------
    op.create_table(
        "agent_identity",
        sa.Column("agent_id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("passport_id", sa.Text(), nullable=False),
        sa.Column("issuer", sa.Text(), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("public_key_jwk", sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column("capabilities", sa.dialects.postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("agent_identity_passport_id_idx", "agent_identity", ["passport_id"], unique=False)

    # -------------------------
    # cie_session
    # -------------------------
    op.create_table(
        "cie_session",
        sa.Column("session_id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("agent_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_identity.agent_id"), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=True),
        sa.Column("project_id", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("last_active_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("cie_session_agent_idx", "cie_session", ["agent_id"], unique=False)
    op.create_index("cie_session_project_idx", "cie_session", ["project_id"], unique=False)

    # -------------------------
    # cie_run
    # -------------------------
    op.create_table(
        "cie_run",
        sa.Column("run_id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("cie_session.session_id"), nullable=False),
        sa.Column("agent_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_identity.agent_id"), nullable=False),
        sa.Column("trace_id", sa.Text(), nullable=False),
        sa.Column("model_id", sa.Text(), nullable=False),
        sa.Column("intent", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'completed'")),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("tokens_in", sa.Integer(), nullable=True),
        sa.Column("tokens_out", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("user_input", sa.Text(), nullable=False),
        sa.Column("response_output", sa.Text(), nullable=True),
        sa.Column("context_pack_hash", sa.Text(), nullable=False),
        sa.Column("continuity_contract_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("tool_summary", sa.dialects.postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("error", sa.dialects.postgresql.JSONB(), nullable=True),
    )
    op.create_index("cie_run_session_idx", "cie_run", ["session_id", "started_at"], unique=False)
    op.create_index("cie_run_trace_idx", "cie_run", ["trace_id"], unique=False)

    # -------------------------
    # cie_event (append-only)
    # -------------------------
    op.create_table(
        "cie_event",
        sa.Column("event_id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("run_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("cie_run.run_id"), nullable=False),
        sa.Column("trace_id", sa.Text(), nullable=False),
        sa.Column("span_id", sa.Text(), nullable=True),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("occurred_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("payload", sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column("payload_hash", sa.Text(), nullable=False),
    )
    op.create_index("cie_event_run_idx", "cie_event", ["run_id", "occurred_at"], unique=False)
    op.create_index("cie_event_type_idx", "cie_event", ["event_type"], unique=False)
    op.create_index("cie_event_trace_span_idx", "cie_event", ["trace_id", "span_id"], unique=False)

    # -------------------------
    # cie_state (versioned)
    # -------------------------
    op.create_table(
        "cie_state",
        sa.Column("state_id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("session_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("cie_session.session_id"), nullable=False),
        sa.Column("agent_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_identity.agent_id"), nullable=False),
        sa.Column("state_type", sa.Text(), nullable=False),  # self/world/thread
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content", sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("provenance", sa.dialects.postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.create_index("cie_state_latest_idx", "cie_state", ["session_id", "agent_id", "state_type", "version"], unique=False)
    op.create_index(
        "cie_state_unique_version",
        "cie_state",
        ["session_id", "agent_id", "state_type", "version"],
        unique=True,
    )

    # -------------------------
    # cie_open_loop
    # -------------------------
    op.create_table(
        "cie_open_loop",
        sa.Column("loop_id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("session_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("cie_session.session_id"), nullable=False),
        sa.Column("agent_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_identity.agent_id"), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'open'")),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("tags", sa.dialects.postgresql.ARRAY(sa.Text()), nullable=False, server_default=sa.text("'{}'::text[]")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("closed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("provenance", sa.dialects.postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.create_index("cie_open_loop_status_idx", "cie_open_loop", ["session_id", "status"], unique=False)

    # -------------------------
    # cie_memory
    # -------------------------
    op.create_table(
        "cie_memory",
        sa.Column("memory_id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("session_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("cie_session.session_id"), nullable=True),
        sa.Column("agent_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_identity.agent_id"), nullable=False),
        sa.Column("scope", sa.Text(), nullable=False),       # global/project:<id>/task:<id>/session:<id>
        sa.Column("memory_type", sa.Text(), nullable=False), # episodic/procedural/semantic/preference/fact
        sa.Column("importance", sa.Integer(), nullable=False, server_default=sa.text("50")),
        sa.Column("confidence", sa.Integer(), nullable=False, server_default=sa.text("70")),
        sa.Column("ttl_days", sa.Integer(), nullable=True),
        sa.Column("content", sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column("source_event_ids", sa.dialects.postgresql.ARRAY(sa.dialects.postgresql.UUID(as_uuid=True)), nullable=False, server_default=sa.text("'{}'::uuid[]")),
        sa.Column("source_trace_ids", sa.dialects.postgresql.ARRAY(sa.Text()), nullable=False, server_default=sa.text("'{}'::text[]")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("cie_memory_scope_idx", "cie_memory", ["agent_id", "scope"], unique=False)
    op.create_index("cie_memory_type_idx", "cie_memory", ["agent_id", "memory_type"], unique=False)
    op.create_index("cie_memory_importance_idx", "cie_memory", ["agent_id", "importance"], unique=False)

    # -------------------------
    # cie_semantic_doc
    # -------------------------
    op.create_table(
        "cie_semantic_doc",
        sa.Column("doc_id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("memory_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("cie_memory.memory_id", ondelete="CASCADE"), nullable=True),
        sa.Column("agent_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_identity.agent_id"), nullable=False),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("qdrant_point_id", sa.Text(), nullable=True),
        sa.Column("embedding_model", sa.Text(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("cie_semantic_scope_idx", "cie_semantic_doc", ["agent_id", "scope"], unique=False)

    # -------------------------
    # cie_continuity_contract
    # -------------------------
    op.create_table(
        "cie_continuity_contract",
        sa.Column("contract_id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("session_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("cie_session.session_id"), nullable=False),
        sa.Column("agent_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_identity.agent_id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("self_state_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("cie_state.state_id"), nullable=False),
        sa.Column("world_state_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("cie_state.state_id"), nullable=False),
        sa.Column("thread_state_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("cie_state.state_id"), nullable=False),
        sa.Column("open_loop_ids", sa.dialects.postgresql.ARRAY(sa.dialects.postgresql.UUID(as_uuid=True)), nullable=False, server_default=sa.text("'{}'::uuid[]")),
        sa.Column("included_memory_ids", sa.dialects.postgresql.ARRAY(sa.dialects.postgresql.UUID(as_uuid=True)), nullable=False, server_default=sa.text("'{}'::uuid[]")),
        sa.Column("context_budget", sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column("pack", sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column("pack_hash", sa.Text(), nullable=False),
        sa.Column("provenance", sa.dialects.postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index(
        "cie_contract_unique_version",
        "cie_continuity_contract",
        ["session_id", "agent_id", "version"],
        unique=True,
    )
    op.create_index("cie_contract_latest_idx", "cie_continuity_contract", ["session_id", "agent_id", "version"], unique=False)

    # FK from run to continuity contract (added after contract exists)
    op.create_foreign_key(
        "cie_run_contract_fk",
        "cie_run",
        "cie_continuity_contract",
        ["continuity_contract_id"],
        ["contract_id"],
        ondelete=None,
    )

    # -------------------------
    # cie_conflict
    # -------------------------
    op.create_table(
        "cie_conflict",
        sa.Column("conflict_id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("session_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("cie_session.session_id"), nullable=False),
        sa.Column("agent_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_identity.agent_id"), nullable=False),
        sa.Column("conflict_type", sa.Text(), nullable=False),
        sa.Column("left_ref", sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column("right_ref", sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column("resolution", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'open'")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("resolved_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index("cie_conflict_status_idx", "cie_conflict", ["session_id", "status"], unique=False)

    # -------------------------
    # cie_eval
    # -------------------------
    op.create_table(
        "cie_eval",
        sa.Column("eval_id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("run_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("cie_run.run_id"), nullable=False),
        sa.Column("session_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("cie_session.session_id"), nullable=False),
        sa.Column("agent_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_identity.agent_id"), nullable=False),
        sa.Column("retrieval_precision", sa.Numeric(), nullable=True),
        sa.Column("regret_rate", sa.Numeric(), nullable=True),
        sa.Column("contradiction_count", sa.Integer(), nullable=True),
        sa.Column("loop_closure_delta", sa.Integer(), nullable=True),
        sa.Column("notes", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )


def downgrade() -> None:
    # Drop in reverse dependency order
    op.drop_table("cie_eval")
    op.drop_table("cie_conflict")
    op.drop_constraint("cie_run_contract_fk", "cie_run", type_="foreignkey")
    op.drop_table("cie_continuity_contract")
    op.drop_table("cie_semantic_doc")
    op.drop_table("cie_memory")
    op.drop_table("cie_open_loop")
    op.drop_table("cie_state")
    op.drop_table("cie_event")
    op.drop_table("cie_run")
    op.drop_table("cie_session")
    op.drop_index("agent_identity_passport_id_idx", table_name="agent_identity")
    op.drop_table("agent_identity")
```

---

## 2) FastAPI skeletons (gateway, governor, steward)

### 2.1 `services/common/config.py`

```python
from pydantic import BaseModel
import os


class Settings(BaseModel):
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql+asyncpg://cie:cie@postgres:5432/cie")
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://valkey:6379/0")

    GOVERNOR_URL: str = os.getenv("GOVERNOR_URL", "http://cie-governor:8011")
    OTEL_EXPORTER_OTLP_ENDPOINT: str = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317")

    # For v0 you can stub out model calls; later replace with LiteLLM/vLLM endpoints.
    EXEC_MODEL_ID: str = os.getenv("EXEC_MODEL_ID", "stub-model")
    ENV: str = os.getenv("ENV", "dev")


settings = Settings()
```

### 2.2 `services/common/db.py`

```python
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from services.common.config import settings

engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def get_db() -> AsyncSession:
    async with SessionLocal() as session:
        yield session
```

### 2.3 `services/common/telemetry.py` (OTel minimal)

```python
from services.common.config import settings

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter


def init_tracing(service_name: str) -> None:
    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)

    exporter = OTLPSpanExporter(endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT, insecure=True)
    provider.add_span_processor(BatchSpanProcessor(exporter))

    trace.set_tracer_provider(provider)


def tracer(service_name: str):
    return trace.get_tracer(service_name)
```

### 2.4 `services/common/util.py`

```python
import hashlib
import json
from typing import Any


def stable_hash(obj: Any) -> str:
    # Deterministic JSON hashing
    payload = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
```

### 2.5 `services/common/redis_bus.py`

```python
from redis.asyncio import Redis
from services.common.config import settings

redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)

RUN_COMPLETED_STREAM = "cie.run_completed"

async def publish_run_completed(event: dict) -> str:
    # XADD returns entry id
    return await redis.xadd(RUN_COMPLETED_STREAM, event, maxlen=10000, approximate=True)
```

### 2.6 `services/common/schemas.py`

```python
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
from uuid import UUID


class AttachmentMeta(BaseModel):
    attachment_id: str
    mime: str
    size_bytes: int
    sha256: Optional[str] = None


class BudgetProfile(BaseModel):
    identity: int = 500
    thread: int = 400
    procedures: int = 300
    episodes: int = 600
    semantic: int = 800
    tail: int = 400


class ContextPack(BaseModel):
    continuity_header: str
    self_state: Dict[str, Any]
    world_state: Dict[str, Any]
    thread_state: Dict[str, Any]
    open_loops: List[Dict[str, Any]] = Field(default_factory=list)
    procedures: List[Dict[str, Any]] = Field(default_factory=list)
    episodic: List[Dict[str, Any]] = Field(default_factory=list)
    semantic: List[Dict[str, Any]] = Field(default_factory=list)
    provenance: Dict[str, Any] = Field(default_factory=dict)
    budgets_used: Dict[str, int] = Field(default_factory=dict)


class WriteIntent(BaseModel):
    candidate_memories: List[Dict[str, Any]] = Field(default_factory=list)
    candidate_state_updates: List[Dict[str, Any]] = Field(default_factory=list)
    signals: Dict[str, Any] = Field(default_factory=dict)


class BuildPackRequest(BaseModel):
    session_id: UUID
    agent_id: UUID
    model_id: str
    user_message: str
    attachments: List[AttachmentMeta] = Field(default_factory=list)
    budget: BudgetProfile = Field(default_factory=BudgetProfile)


class BuildPackResponse(BaseModel):
    context_pack: ContextPack
    context_pack_hash: str
    write_intent: WriteIntent


class ChatRequest(BaseModel):
    session_id: UUID
    agent_id: UUID
    user_message: str
    model_id: Optional[str] = None
    attachments: List[AttachmentMeta] = Field(default_factory=list)


class ChatResponse(BaseModel):
    run_id: UUID
    trace_id: str
    response: str
    context_pack_hash: str
```

---

### 2.7 `services/cie_governor/main.py` (deterministic v0)

```python
from fastapi import FastAPI, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import uuid4

from services.common.telemetry import init_tracing, tracer
from services.common.db import get_db
from services.common.schemas import BuildPackRequest, BuildPackResponse, ContextPack, WriteIntent
from services.common.util import stable_hash

SERVICE = "cie-governor"
init_tracing(SERVICE)
tr = tracer(SERVICE)

app = FastAPI(title="CIE Governor", version="0.1.0")


async def _latest_state(db: AsyncSession, session_id, agent_id, state_type: str) -> dict:
    q = text("""
        SELECT content
        FROM cie_state
        WHERE session_id = :session_id AND agent_id = :agent_id AND state_type = :state_type
        ORDER BY version DESC
        LIMIT 1
    """)
    row = (await db.execute(q, {"session_id": session_id, "agent_id": agent_id, "state_type": state_type})).first()
    return row[0] if row else {}


async def _open_loops(db: AsyncSession, session_id, agent_id) -> list[dict]:
    q = text("""
        SELECT loop_id, title, details, tags, created_at
        FROM cie_open_loop
        WHERE session_id = :session_id AND agent_id = :agent_id AND status = 'open'
        ORDER BY created_at DESC
        LIMIT 20
    """)
    rows = (await db.execute(q, {"session_id": session_id, "agent_id": agent_id})).all()
    return [
        {"loop_id": str(r[0]), "title": r[1], "details": r[2], "tags": r[3], "created_at": r[4].isoformat()}
        for r in rows
    ]


async def _procedures(db: AsyncSession, agent_id, scopes: list[str]) -> list[dict]:
    q = text("""
        SELECT memory_id, content, importance, confidence, scope
        FROM cie_memory
        WHERE agent_id = :agent_id
          AND memory_type = 'procedural'
          AND scope = ANY(:scopes)
        ORDER BY importance DESC, updated_at DESC
        LIMIT 20
    """)
    rows = (await db.execute(q, {"agent_id": agent_id, "scopes": scopes})).all()
    return [
        {"memory_id": str(r[0]), "content": r[1], "importance": r[2], "confidence": r[3], "scope": r[4]}
        for r in rows
    ]


async def _episodes(db: AsyncSession, agent_id, scopes: list[str]) -> list[dict]:
    q = text("""
        SELECT memory_id, content, importance, confidence, scope
        FROM cie_memory
        WHERE agent_id = :agent_id
          AND memory_type = 'episodic'
          AND scope = ANY(:scopes)
        ORDER BY importance DESC, created_at DESC
        LIMIT 30
    """)
    rows = (await db.execute(q, {"agent_id": agent_id, "scopes": scopes})).all()
    return [
        {"memory_id": str(r[0]), "content": r[1], "importance": r[2], "confidence": r[3], "scope": r[4]}
        for r in rows
    ]


@app.post("/build-pack", response_model=BuildPackResponse)
async def build_pack(req: BuildPackRequest, db: AsyncSession = Depends(get_db)) -> BuildPackResponse:
    with tr.start_as_current_span("cie.governor.build_pack") as span:
        span.set_attribute("session_id", str(req.session_id))
        span.set_attribute("agent_id", str(req.agent_id))
        span.set_attribute("model_id", req.model_id)

        scopes = ["global", f"session:{req.session_id}"]
        # You can add project scope later by reading cie_session.project_id
        # scopes.append(f"project:{project_id}")

        self_state = await _latest_state(db, req.session_id, req.agent_id, "self")
        world_state = await _latest_state(db, req.session_id, req.agent_id, "world")
        thread_state = await _latest_state(db, req.session_id, req.agent_id, "thread")

        loops = await _open_loops(db, req.session_id, req.agent_id)
        procedures = await _procedures(db, req.agent_id, scopes)
        episodic = await _episodes(db, req.agent_id, scopes)

        # v0: no semantic retrieval yet; keep placeholder
        semantic: list[dict] = []

        continuity_header = (
            "You are a persistent agent operating under a continuity contract.\n"
            "Maintain identity coherence and follow procedures when applicable.\n"
            "Treat the following state as current truth unless contradicted by tool outputs."
        )

        pack = ContextPack(
            continuity_header=continuity_header,
            self_state=self_state,
            world_state=world_state,
            thread_state=thread_state,
            open_loops=loops,
            procedures=procedures[:10],
            episodic=episodic[:10],
            semantic=semantic,
            provenance={"scopes": scopes},
            budgets_used={
                "identity": req.budget.identity,
                "thread": req.budget.thread,
                "procedures": req.budget.procedures,
                "episodes": req.budget.episodes,
                "semantic": req.budget.semantic,
                "tail": req.budget.tail,
            },
        )

        # v0 WriteIntent: just a placeholder. Steward will compute real write intents from run.
        write_intent = WriteIntent(
            candidate_memories=[],
            candidate_state_updates=[],
            signals={"scopes": scopes, "attachments_count": len(req.attachments)},
        )

        pack_hash = stable_hash(pack.model_dump())
        span.set_attribute("context_pack_hash", pack_hash)

        return BuildPackResponse(context_pack=pack, context_pack_hash=pack_hash, write_intent=write_intent)
```

---

### 2.8 `services/cie_gateway/main.py` (sync flow + emits RunCompleted)

```python
from fastapi import FastAPI, HTTPException
from uuid import uuid4
import time
import httpx

from services.common.config import settings
from services.common.telemetry import init_tracing, tracer
from services.common.schemas import ChatRequest, ChatResponse, BuildPackRequest
from services.common.redis_bus import publish_run_completed
from services.common.util import stable_hash

SERVICE = "cie-gateway"
init_tracing(SERVICE)
tr = tracer(SERVICE)

app = FastAPI(title="CIE Gateway", version="0.1.0")


async def call_executive_model_stub(context_pack: dict, user_message: str) -> str:
    # Replace this with LiteLLM/vLLM call.
    # This stub is deterministic and lets you wire the pipeline end-to-end today.
    return (
        "STUB_RESPONSE\n"
        "I received a continuity pack and your message.\n"
        f"Message: {user_message}\n"
        "Next: integrate real model endpoint.\n"
    )


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    run_id = uuid4()
    trace_id = f"trace-{run_id}"  # v0 placeholder; real OTel trace_id will exist in telemetry backend

    model_id = req.model_id or settings.EXEC_MODEL_ID

    with tr.start_as_current_span("cie.run") as root:
        root.set_attribute("run_id", str(run_id))
        root.set_attribute("session_id", str(req.session_id))
        root.set_attribute("agent_id", str(req.agent_id))
        root.set_attribute("model_id", model_id)

        started = time.time()

        # 1) Build context pack
        with tr.start_as_current_span("cie.governor.build_pack") as span:
            governor_req = BuildPackRequest(
                session_id=req.session_id,
                agent_id=req.agent_id,
                model_id=model_id,
                user_message=req.user_message,
                attachments=req.attachments,
            )
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    r = await client.post(f"{settings.GOVERNOR_URL}/build-pack", json=governor_req.model_dump(mode="json"))
                    r.raise_for_status()
                    governor_out = r.json()
            except Exception as e:
                raise HTTPException(status_code=502, detail=f"Governor error: {e}")

        context_pack = governor_out["context_pack"]
        context_pack_hash = governor_out["context_pack_hash"]
        write_intent = governor_out.get("write_intent", {})

        root.set_attribute("context_pack_hash", context_pack_hash)

        # 2) Executive inference (stub)
        with tr.start_as_current_span("cie.brain.infer") as span:
            span.set_attribute("model_id", model_id)
            response = await call_executive_model_stub(context_pack, req.user_message)

        latency_ms = int((time.time() - started) * 1000)

        # 3) Publish RunCompleted to Redis stream for steward
        event = {
            "schema_version": "1",
            "event_type": "RunCompleted",
            "run_id": str(run_id),
            "session_id": str(req.session_id),
            "agent_id": str(req.agent_id),
            "trace_id": trace_id,
            "model_id": model_id,
            "intent": "",

            "started_at_ms": str(int(started * 1000)),
            "completed_at_ms": str(int(time.time() * 1000)),
            "latency_ms": str(latency_ms),

            "tokens_in": "0",
            "tokens_out": "0",

            "context_pack_hash": context_pack_hash,
            "context_pack_ref": "",  # optional: store pack in DB and reference id
            "write_intent_json": stable_hash(write_intent),  # v0: hash only; later store full

            "tool_summary_json": "{}",  # gateway can fill after real tool calls
            "user_input_sha": stable_hash(req.user_message),
            "response_output_sha": stable_hash(response),
            "status": "completed",
            "error_json": "",
        }
        await publish_run_completed(event)

        return ChatResponse(
            run_id=run_id,
            trace_id=trace_id,
            response=response,
            context_pack_hash=context_pack_hash,
        )
```

---

### 2.9 `services/cie_steward/worker.py` (Redis stream consumer, v0)

```python
import asyncio
from uuid import UUID, uuid4
from sqlalchemy import text
from services.common.redis_bus import redis, RUN_COMPLETED_STREAM
from services.common.db import SessionLocal
from services.common.telemetry import init_tracing, tracer
from services.common.util import stable_hash

SERVICE = "cie-steward"
init_tracing(SERVICE)
tr = tracer(SERVICE)

GROUP = "cie_steward_group"
CONSUMER = "steward_1"


async def ensure_group():
    try:
        await redis.xgroup_create(RUN_COMPLETED_STREAM, GROUP, id="0-0", mkstream=True)
    except Exception:
        # group probably exists
        pass


async def write_minimal_episode(db, agent_id: str, session_id: str, run_id: str, trace_id: str):
    # v0: write a simple episodic memory that “a run happened”
    mem_content = {
        "type": "episode",
        "summary": f"Run {run_id} completed.",
        "trace_id": trace_id,
    }
    q = text("""
        INSERT INTO cie_memory (memory_id, session_id, agent_id, scope, memory_type, importance, confidence, content, source_trace_ids)
        VALUES (gen_random_uuid(), :session_id, :agent_id, :scope, 'episodic', 40, 80, :content::jsonb, ARRAY[:trace_id])
    """)
    await db.execute(q, {
        "session_id": session_id,
        "agent_id": agent_id,
        "scope": f"session:{session_id}",
        "content": str(mem_content).replace("'", "\""),
        "trace_id": trace_id,
    })


async def ensure_initial_states(db, agent_id: str, session_id: str):
    # Ensure self/world/thread v1 exist. If not, create.
    for stype in ("self", "world", "thread"):
        q = text("""
            SELECT version FROM cie_state
            WHERE session_id=:session_id AND agent_id=:agent_id AND state_type=:stype
            ORDER BY version DESC LIMIT 1
        """)
        row = (await db.execute(q, {"session_id": session_id, "agent_id": agent_id, "stype": stype})).first()
        if row:
            continue
        content = {"version": 1, "state_type": stype, "data": {}}
        ins = text("""
            INSERT INTO cie_state (state_id, session_id, agent_id, state_type, version, content, provenance)
            VALUES (gen_random_uuid(), :session_id, :agent_id, :stype, 1, :content::jsonb, '{}'::jsonb)
        """)
        await db.execute(ins, {
            "session_id": session_id,
            "agent_id": agent_id,
            "stype": stype,
            "content": str(content).replace("'", "\""),
        })


async def create_contract_v0(db, agent_id: str, session_id: str, trace_id: str):
    # Create a v0 continuity contract referencing latest state ids.
    latest = text("""
        SELECT state_type, state_id, version
        FROM cie_state
        WHERE session_id=:session_id AND agent_id=:agent_id
        ORDER BY version DESC
    """)
    rows = (await db.execute(latest, {"session_id": session_id, "agent_id": agent_id})).all()
    by_type = {}
    for stype, sid, ver in rows:
        if stype not in by_type:
            by_type[stype] = (sid, ver)
    if not all(k in by_type for k in ("self", "world", "thread")):
        return

    # get next contract version
    cv = text("""
        SELECT COALESCE(MAX(version), 0) + 1
        FROM cie_continuity_contract
        WHERE session_id=:session_id AND agent_id=:agent_id
    """)
    next_ver = (await db.execute(cv, {"session_id": session_id, "agent_id": agent_id})).scalar_one()

    pack = {
        "continuity_header": "You are operating under a continuity contract (v0).",
        "self_state_id": str(by_type["self"][0]),
        "world_state_id": str(by_type["world"][0]),
        "thread_state_id": str(by_type["thread"][0]),
        "note": "v0 contract created by steward.",
    }
    pack_hash = stable_hash(pack)

    ins = text("""
        INSERT INTO cie_continuity_contract (
          contract_id, session_id, agent_id, version,
          self_state_id, world_state_id, thread_state_id,
          open_loop_ids, included_memory_ids, context_budget,
          pack, pack_hash, provenance
        )
        VALUES (
          gen_random_uuid(), :session_id, :agent_id, :ver,
          :self_state_id, :world_state_id, :thread_state_id,
          '{}'::uuid[], '{}'::uuid[], :budget::jsonb,
          :pack::jsonb, :pack_hash, :prov::jsonb
        )
    """)
    await db.execute(ins, {
        "session_id": session_id,
        "agent_id": agent_id,
        "ver": next_ver,
        "self_state_id": str(by_type["self"][0]),
        "world_state_id": str(by_type["world"][0]),
        "thread_state_id": str(by_type["thread"][0]),
        "budget": '{"identity":500,"thread":400,"procedures":300,"episodes":600,"semantic":800,"tail":400}',
        "pack": str(pack).replace("'", "\""),
        "pack_hash": pack_hash,
        "prov": str({"trace_id": trace_id}).replace("'", "\""),
    })


async def handle_message(message_id: str, fields: dict):
    with tr.start_as_current_span("cie.steward.process_run") as span:
        span.set_attribute("message_id", message_id)
        run_id = fields.get("run_id", "")
        session_id = fields.get("session_id", "")
        agent_id = fields.get("agent_id", "")
        trace_id = fields.get("trace_id", "")

        span.set_attribute("run_id", run_id)
        span.set_attribute("session_id", session_id)
        span.set_attribute("agent_id", agent_id)
        span.set_attribute("trace_id", trace_id)

        async with SessionLocal() as db:
            await ensure_initial_states(db, agent_id, session_id)
            await write_minimal_episode(db, agent_id, session_id, run_id, trace_id)
            await create_contract_v0(db, agent_id, session_id, trace_id)
            await db.commit()


async def main():
    await ensure_group()
    while True:
        resp = await redis.xreadgroup(
            groupname=GROUP,
            consumername=CONSUMER,
            streams={RUN_COMPLETED_STREAM: ">"},
            count=10,
            block=5000,
        )
        if not resp:
            continue
        for stream_name, messages in resp:
            for mid, fields in messages:
                try:
                    await handle_message(mid, fields)
                    await redis.xack(RUN_COMPLETED_STREAM, GROUP, mid)
                except Exception:
                    # Leave pending for retry; in production add DLQ
                    pass


if __name__ == "__main__":
    asyncio.run(main())
```

---

## 3) Redis Stream event schema: `RunCompleted` (v1)

This is exactly what you XADD into `cie.run_completed`. Keep fields as strings (Redis streams love strings).

```json
{
  "schema_version": "1",
  "event_type": "RunCompleted",

  "run_id": "uuid",
  "session_id": "uuid",
  "agent_id": "uuid",
  "trace_id": "otel-trace-id-or-placeholder",
  "model_id": "qwen3-next-80b",
  "intent": "optional-string",

  "started_at_ms": "epoch_ms",
  "completed_at_ms": "epoch_ms",
  "latency_ms": "int",

  "tokens_in": "int",
  "tokens_out": "int",

  "context_pack_hash": "sha256",
  "context_pack_ref": "optional-id-or-url",
  "write_intent_json": "json-or-hash",

  "tool_summary_json": "json",
  "user_input_sha": "sha256",
  "response_output_sha": "sha256",

  "status": "completed|failed",
  "error_json": "json-or-empty"
}
```

**Rule:** if it’s large, store it in Postgres/Object storage and put a `*_ref`. Redis stream is the event bus, not the dumpster.

---

## 4) Minimal `docker-compose.yml` (Postgres + Valkey + Qdrant + OTel Collector + 3 services)

```yaml
version: "3.9"

services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_DB: cie
      POSTGRES_USER: cie
      POSTGRES_PASSWORD: cie
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

  valkey:
    image: valkey/valkey:7
    ports:
      - "6379:6379"

  qdrant:
    image: qdrant/qdrant:v1.12.4
    ports:
      - "6333:6333"
    volumes:
      - qdrantdata:/qdrant/storage

  otel-collector:
    image: otel/opentelemetry-collector-contrib:0.96.0
    command: ["--config=/etc/otelcol/config.yaml"]
    volumes:
      - ./otel-collector-config.yaml:/etc/otelcol/config.yaml:ro
    ports:
      - "4317:4317"  # OTLP gRPC
      - "4318:4318"  # OTLP HTTP

  cie-governor:
    build:
      context: .
      dockerfile: ./services/Dockerfile
      args:
        SERVICE_DIR: services/cie_governor
        APP_MODULE: services.cie_governor.main:app
        PORT: "8011"
    environment:
      DATABASE_URL: postgresql+asyncpg://cie:cie@postgres:5432/cie
      REDIS_URL: redis://valkey:6379/0
      OTEL_EXPORTER_OTLP_ENDPOINT: http://otel-collector:4317
    depends_on:
      - postgres
      - valkey
      - otel-collector
    ports:
      - "8011:8011"

  cie-gateway:
    build:
      context: .
      dockerfile: ./services/Dockerfile
      args:
        SERVICE_DIR: services/cie_gateway
        APP_MODULE: services.cie_gateway.main:app
        PORT: "8010"
    environment:
      DATABASE_URL: postgresql+asyncpg://cie:cie@postgres:5432/cie
      REDIS_URL: redis://valkey:6379/0
      GOVERNOR_URL: http://cie-governor:8011
      OTEL_EXPORTER_OTLP_ENDPOINT: http://otel-collector:4317
      EXEC_MODEL_ID: stub-model
    depends_on:
      - cie-governor
      - valkey
      - otel-collector
    ports:
      - "8010:8010"

  cie-steward:
    build:
      context: .
      dockerfile: ./services/Dockerfile
      args:
        SERVICE_DIR: services/cie_steward
        APP_MODULE: services.cie_steward.worker:main
        PORT: "0"
    environment:
      DATABASE_URL: postgresql+asyncpg://cie:cie@postgres:5432/cie
      REDIS_URL: redis://valkey:6379/0
      OTEL_EXPORTER_OTLP_ENDPOINT: http://otel-collector:4317
    depends_on:
      - postgres
      - valkey
      - otel-collector
    command: ["python", "-m", "services.cie_steward.worker"]

volumes:
  pgdata:
  qdrantdata:
```

### `otel-collector-config.yaml` (minimal)

```yaml
receivers:
  otlp:
    protocols:
      grpc:
      http:

exporters:
  logging:
    verbosity: detailed

processors:
  batch:

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [batch]
      exporters: [logging]
```

This prints traces to logs (enough to validate plumbing). Later you’ll swap `logging` exporter for Tempo/Jaeger/etc.

---

## 5) Single Dockerfile for the three Python services: `services/Dockerfile`

```dockerfile
FROM python:3.11-slim

ARG SERVICE_DIR
ARG APP_MODULE
ARG PORT

WORKDIR /app

# System deps (optional; keep slim)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl \
 && rm -rf /var/lib/apt/lists/*

# Install python deps
COPY pyproject.toml /app/pyproject.toml
# If you prefer requirements.txt, swap this logic.
RUN pip install --no-cache-dir -U pip \
 && pip install --no-cache-dir \
      fastapi==0.115.6 \
      uvicorn[standard]==0.30.6 \
      httpx==0.27.2 \
      sqlalchemy==2.0.36 \
      asyncpg==0.30.0 \
      alembic==1.14.0 \
      pydantic==2.10.4 \
      redis==5.2.1 \
      opentelemetry-api==1.27.0 \
      opentelemetry-sdk==1.27.0 \
      opentelemetry-exporter-otlp==1.27.0

COPY services /app/services
COPY alembic /app/alembic
COPY alembic.ini /app/alembic.ini

EXPOSE ${PORT}

# Default: run as API unless overridden by compose command
CMD ["sh", "-c", "uvicorn ${APP_MODULE} --host 0.0.0.0 --port ${PORT}"]
```

### `pyproject.toml` (minimal placeholder)

```toml
[project]
name = "cie"
version = "0.1.0"
requires-python = ">=3.11"
```

---

## 6) Quick bring-up commands (copy/paste)

```bash
# 1) Bring up infra + services
docker compose up -d --build

# 2) Run alembic migration (inside gateway container is fine)
docker compose exec cie-gateway alembic upgrade head

# 3) Hit the gateway
curl -s http://localhost:8010/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id":"11111111-1111-1111-1111-111111111111",
    "agent_id":"22222222-2222-2222-2222-222222222222",
    "user_message":"Hello continuity engine"
  }' | jq
```

**Note:** you must insert a row into `agent_identity` and `cie_session` first (v0 doesn’t auto-provision). Here’s SQL you can run:

```sql
INSERT INTO agent_identity (agent_id, passport_id, issuer, subject, public_key_jwk, capabilities)
VALUES (
  '22222222-2222-2222-2222-222222222222',
  'passport:test',
  'passportalliance',
  'agent:test',
  '{}'::jsonb,
  '{}'::jsonb
);

INSERT INTO cie_session (session_id, agent_id, user_id, project_id)
VALUES (
  '11111111-1111-1111-1111-111111111111',
  '22222222-2222-2222-2222-222222222222',
  'cj',
  'cie-dev'
);
```

Run it with:

```bash
docker compose exec postgres psql -U cie -d cie -c "<PASTE SQL HERE>"
```

---

## What you get immediately (even with the stub model)

* deterministic governor builds a continuity pack
* gateway emits RunCompleted to Redis stream
* steward consumes it and writes:

  * initial states (self/world/thread)
  * an episodic “run happened” memory
  * a continuity contract v1, v2, v3… each run

That’s the spine. Then you swap the stub executive for your real brain endpoint and start layering in semantic retrieval + rerank + conflict resolution rules.

If you want the next upgrade step after this scaffolding: I’ll drop in (1) Qdrant collection creation + upsert code, (2) reranker hook, and (3) the governor’s deterministic salience scoring + strict token budgeting implementation.

