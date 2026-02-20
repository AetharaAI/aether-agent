# AetherOps Production Changelog

> **Production VM**: `b3-16-us-east-va-1` (AetherOps)
> **Shared Infra (triad)**: `triad.aetherpro.tech` — MongoDB, Qdrant, PostgreSQL, LLM endpoints

---

## Tailscale Network Topology

All inter-service communication routes over the Tailscale private mesh. **Do not expose MongoDB/Qdrant/Postgres publicly.**

| Node | Tailscale IP | Role |
|---|---|---|
| `1tb-dev-partion-24-04` | `100.84.158.99` | Local dev |
| `b3-16-us-east-va-1` | `100.126.30.48` | AetherOps production |
| `triad-r3-64-us-west-or-1` | `100.87.16.38` | Databases & services |

### Recommended firewall on triad
```bash
sudo ufw allow in on tailscale0  # allow all Tailscale traffic
sudo ufw deny 27017              # MongoDB — no public access
sudo ufw deny 6333               # Qdrant  — no public access
sudo ufw deny 5432               # Postgres — no public access
```


## Port & Service Reference

| Service | Internal Port | External Port | Notes |
|---|---|---|---|
| **aether-api** | 8000 | **8100** | FastAPI backend |
| **aether-ui** | 3000 | 16398 | Vite/React frontend |
| **redis-stack** | 6379 | 6381 (host only) | Local to each AetherOps instance |
| **Redis Insight** | 8001 | 8003 (host only) | Redis GUI |
| **MongoDB** | 27017 | — | triad.aetherpro.tech (shared) |
| **Qdrant HTTP** | 6333 | — | triad.aetherpro.tech (shared) |
| **Qdrant gRPC** | 6334 | — | triad.aetherpro.tech (available, disabled by default) |
| **bge-m3 Embeddings** | — | `https://embed.aetherpro.us/v1/embeddings` | L4 GPU cluster |
| **bge-reranker** | — | `https://embed.aetherpro.us/rerank` | L4 GPU cluster |
| **LiteLLM (primary)** | — | `https://api.blackboxaudio.tech/v1` | L40S-180 node |
| **LiteLLM (secondary)** | — | `https://api.aetherpro.tech/v1` | L40S-90 node |

---

## [v3.1.0] — 2026-02-17 — Initial Production Launch

### Infrastructure
- Deployed AetherOS to production VM (`b3-16-us-east-va-1`)
- Vercel SPA routing configured for `operations.aetherpro.us`
- CORS configured for `https://operations.aetherpro.us`
- API port set to `8100:8000`

### Services Live
- Redis Stack (local to VM, AOF persistence, 6GB maxmemory)
- MongoDB connection to triad (`aether_agent` database)
- Qdrant connection to triad (HTTP, gRPC disabled)
- LiteLLM dual-instance support (litellm + litellm-2)
- Dynamic Tool Registry seeded: 23 tools

---

## [v3.1.1] — 2026-02-19

### Memory Convergence (pushed from local)
- **Vector Embedding Integration**: hybrid BM25 + bge-m3 search
  - `EMBEDDING_API_URL=https://embed.aetherpro.us/v1/embeddings`
  - 1024-dim vectors, Qdrant collection auto-created/migrated on startup
- **Cross-encoder Reranker**: `RERANKER_API_URL=https://embed.aetherpro.us/rerank`
  - Applied after score fusion, before temporal decay
- **Temporal Decay**: 30-day half-life (`MEMORY_DECAY_HALF_LIFE=30`)
- **MMR Diversity**: Jaccard-based de-duplication (`MEMORY_MMR_LAMBDA=0.7`)
- **Agentic Flush**: saves critical context to memory before 75% compression
  - `AGENTIC_FLUSH_ENABLED=true`
- **Context Management**: warning at 75%, auto-checkpoint + compress at 85%

### Bug Fixes
- Fixed `python-dateutil` import error — replaced with stdlib `datetime.fromisoformat()`
- Fixed Qdrant collection vector config mismatch (FastEmbed → bge-m3 migration)
- Added missing `LITELLM_2_MODEL_BASE_URL` / `LITELLM_2_MODEL_NAME` to compose

### MongoDB
- Production DB: `aether_agent` / `agent_ledger` (configurable via `MONGO_DB_NAME`)
- Redis Stack: local per-instance (not shared via triad)

---

> **⚠️ Production Change Protocol**: Any change to `api_server.py`, `docker-compose.yml`, or `.env` that affects CORS, ports, or service URLs must be noted here before pushing.
