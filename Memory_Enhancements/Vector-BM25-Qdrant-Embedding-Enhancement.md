Memory Convergence: 4 Search Enhancement Features
Upgrade Aether's memory search from full-text-only to a production-grade hybrid retrieval system with vector embeddings, temporal decay, MMR diversity, and intelligent pre-compression flush.

Current State
Capability	Status
RedisSearch full-text	✅ Working
Qdrant adapter	✅ Exists (
qdrant_adapter.py
) — uses FastEmbed all-MiniLM-L6-v2
Qdrant integration in search	❌ Not wired into 
search_semantic()
Temporal decay	❌ Not implemented
MMR diversity	❌ Not implemented
Pre-compression agentic flush	❌ Auto-checkpoint only (mechanical)
Implementation Order
IMPORTANT

Order matters. Features build on each other:

Vector Embeddings — foundation for everything else
Temporal Decay — modifies score calculation (needs scores from step 1)
MMR Diversity — post-processing on scored results (needs step 1+2)
Agentic Flush — independent, can be done anytime but listed last for priority
Feature 1: Vector Embedding Integration
Wire the existing 
QdrantMemory
 adapter into AetherMemory.search_semantic() to enable true semantic search alongside RedisSearch full-text.

Proposed Changes
[MODIFY] 
aether_memory.py
Add 
QdrantMemory
 as optional dependency in 
init
New method: _hybrid_search(query, limit) that:
Runs RedisSearch FT query → gets text_results with BM25-like scores
Runs QdrantMemory.search(query) → gets vector_results with cosine scores
Merges by content key: final = text_weight × text_score + vector_weight × vector_score
Default weights: text_weight=0.3, vector_weight=0.7
Update 
search_semantic()
 to call _hybrid_search() when Qdrant is available, fallback to current behavior if not
New method: _index_to_qdrant(content, source, session_id) — called from 
log_daily()
 to auto-index new entries
Add config: VECTOR_SEARCH_ENABLED env var (default true if Qdrant reachable)
[MODIFY] 
qdrant_adapter.py
Upgrade embedding model config: support EMBEDDING_MODEL env var to point to the L4 cluster endpoint (OpenAI-compatible via vLLM/TEI)
Add add_batch() method for bulk indexing existing daily logs
Add delete_by_session() for cleanup
Embedding Model Decision
IMPORTANT

Choose one — the L4-360 cluster can run any of these:

Model	Dims	Context	vRAM	MTEB Rank
nomic-embed-text-v1.5	768	8192	~1.5 GB	Strong
bge-m3	1024	8192	~2.5 GB	Top-tier
Snowflake Arctic Embed L v2.0	1024	8192	~3 GB	SOTA
all-MiniLM-L6-v2 (current)	384	512	~85 MB	Moderate
Recommendation: nomic-embed-text-v1.5 — best balance of quality, speed, and context length. Serve via TEI on one L4 GPU.

Feature 2: Temporal Decay
Add recency weighting to search results so recent memories rank higher than stale ones.

Proposed Changes
[MODIFY] 
aether_memory.py
New method: _apply_temporal_decay(results, half_life_days=30):
import math
lambda_ = math.log(2) / half_life_days
for result in results:
    age_days = (now - parse(result.timestamp)).days
    result.score *= math.exp(-lambda_ * age_days)
Long-term memory entries and identity data are exempt from decay (evergreen)
Called inside _hybrid_search() after merging scores, before sorting
Config: MEMORY_DECAY_HALF_LIFE env var (default 30)
Feature 3: MMR Diversity
Re-rank search results to avoid near-duplicate snippets flooding the context.

Proposed Changes
[MODIFY] 
aether_memory.py
New method: _apply_mmr(results, lambda_=0.7, limit=None):
Iteratively selects results maximizing: λ × relevance − (1−λ) × max_similarity_to_selected
Similarity measured via Jaccard on tokenized content (word-level)
lambda=1.0 → pure relevance, lambda=0.0 → max diversity
Called inside _hybrid_search() after temporal decay, as final re-ranking step
Config: MEMORY_MMR_LAMBDA env var (default 0.7)
Feature 4: Agentic Flush (Pre-Compression Memory Save)
Before auto-checkpoint and compression, give the agent one silent turn to decide what to save — instead of mechanically dumping the entire state.

Proposed Changes
[MODIFY] 
agent_runtime_v2.py
New method: _agentic_flush():
Inject a system message: "Session nearing compaction. Save any durable memories to daily log now. Reply NO_REPLY if nothing to store."
Call the LLM with this prompt (single turn, no tools)
If response is not NO_REPLY, parse it and call memory.log_daily(content, source="agent", tags=["agentic_flush"])
Track _flush_triggered flag (one per compression cycle)
Integrate into 
_check_and_compress_context()
:
At 75% threshold (warning): trigger agentic flush before showing the warning
Current flow: warning → crash. New flow: flush → warning → checkpoint → compress
Config: AGENTIC_FLUSH_ENABLED env var (default true)
Verification Plan
Automated Tests
# Feature 1: Vector search
python -c "
from aether.aether_memory import AetherMemory
from aether.qdrant_adapter import QdrantMemory
import asyncio
async def test():
    mem = AetherMemory()
    await mem.connect()
    results = await mem.search_semantic('network configuration', limit=5)
    print(f'Hybrid results: {len(results)}')
    for r in results:
        print(f'  [{r.score:.3f}] {r.content[:80]}')
asyncio.run(test())
"
# Feature 2+3: Temporal decay + MMR
python -c "
from aether.aether_memory import AetherMemory
import asyncio
async def test():
    mem = AetherMemory()
    await mem.connect()
    # Log test entries with different dates
    await mem.log_daily('Router configured VLAN 10', date='2026-01-15')
    await mem.log_daily('Router configured VLAN 10 for IoT', date='2026-02-17')
    results = await mem.search_semantic('router VLAN config', limit=5)
    # Recent entry should score higher (temporal decay)
    # Near-duplicate should be deduplicated (MMR)
    for r in results:
        print(f'  [{r.score:.3f}] {r.timestamp[:10]} {r.content[:60]}')
asyncio.run(test())
"
Manual Verification
Start the system, send: "Search memory for network configuration"
Verify results include both text matches AND semantic matches
Verify recent entries rank higher than old ones
Verify no near-duplicate results in top-K
Fill context to 75%, verify agentic flush triggers before warning
