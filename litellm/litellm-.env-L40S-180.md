# ===============================
# LiteLLM Core
# ===============================
LITELLM_MODE=proxy
LITELLM_LOG=INFO
DISABLE_AUTH=false

# Master key (admin only, not clients)
LITELLM_MASTER_KEY=sk-aether-master-pro

# ===============================
# Database (CONTROL PLANE)
# ===============================
LITELLM_DATABASE_URL=postgresql://redwatch_ops:redwatch_ops_gmccmg_2026_infra@100.87.16.38:5440/litellm
LITELLM_DB_POOL_MIN=2
LITELLM_DB_POOL_MAX=20

# ===============================
# Redis (rate limits, cache)
# ===============================
LITELLM_REDIS_URL=redis://:redwatch_ops_gmccmg_2026_infra@100.87.16.38:6380/0

# ===============================
# Security / Ops
# ===============================
LITELLM_ALLOW_ORG_HEADER=true
LITELLM_EXPOSE_METRICS=true
