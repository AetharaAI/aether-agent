# AetherOps Changelog

> **Local Development** changelog. For production changes see [CHANGELOG-PROD.md](./CHANGELOG-PROD.md).

---

## [Unreleased] — 2026-02-19

### Port Standardization
- **API port changed**: `16399 → 8100` (aligns with production)
- Updated `ui/.env.local` `VITE_API_URL` and `VITE_WS_URL` to `http://localhost:8100`
- Updated `docker-compose.yml` VITE build args defaults to port 8100
- Added `localhost:8100` and `localhost:16398` to CORS `allow_origins` in `api_server.py`

### Bug Fixes
- **REDIS_URL**: Fixed incorrect internal port `6381 → 6379` in `docker-compose.yml`
  - `6381` is the host-mapped port; inside Docker network redis-stack always listens on `6379`
- **LITELLM_2 vars**: Added missing `LITELLM_2_MODEL_BASE_URL` and `LITELLM_2_MODEL_NAME` to `docker-compose.yml`

### MongoDB
- Added `MONGO_DB_NAME` and `MONGO_LEDGER_DB_NAME` env vars for dev/prod separation
- Seeded `aether_agent.tools` (prod) and `aether_agent_dev.tools` (dev) — 23 tools each
- MongoDB now owned by triad shared infra; Redis Stack is local per-instance

### Memory Convergence Features
- Vector embedding integration — hybrid BM25 + bge-m3 search (`aether_memory.py`)
- Temporal decay — 30-day half-life, `MEMORY_DECAY_HALF_LIFE` env var
- MMR diversity re-ranking — Jaccard-based, `MEMORY_MMR_LAMBDA` env var
- Agentic flush — silent LLM turn saves context before 75% compression threshold
- Upgraded `qdrant_adapter.py` — dual-mode (local FastEmbed / external TEI), mismatch auto-recovery
- Live endpoints: `https://embed.aetherpro.us/v1/embeddings` (1024-dim bge-m3), `https://embed.aetherpro.us/rerank`
- Context management: warning at 75%, emergency compress + auto-checkpoint at 85%

---

## [v3.1.0] — 2026-02-17 (Initial Production Launch)

See [CHANGELOG-PROD.md](./CHANGELOG-PROD.md) for production entry.
