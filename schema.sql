-- Chat Messages Table for Conversation Memory
CREATE TABLE IF NOT EXISTS chat_messages (
    id SERIAL PRIMARY KEY,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_session ON chat_messages(session_id);

-- Agent Registry Table (v2.0 with Passport-IAM Security)
CREATE TABLE IF NOT EXISTS agent_registry (
    id TEXT PRIMARY KEY,          -- Unique Agent ID (e.g. percy.perceptor.us)
    name TEXT NOT NULL,           -- Human readable name
    owner_id TEXT,                -- Passport User ID who owns this agent
    client_id TEXT,               -- Passport OIDC Client ID (API Key identifier)
    public_key TEXT,              -- Optional: Agent's public key for signature verification
    status TEXT DEFAULT 'idle',   -- idle, busy, offline, blocked
    capabilities TEXT[],          -- ['search', 'code_review', 'browser']
    security_level TEXT DEFAULT 'standard', -- standard, verified, trusted
    is_verified BOOLEAN DEFAULT FALSE,
    metadata JSONB DEFAULT '{}',  -- Extensible metadata (manifest, etc.)
    last_seen TIMESTAMP DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Index for ownership lookups
CREATE INDEX IF NOT EXISTS idx_agent_registry_owner ON agent_registry(owner_id);
CREATE INDEX IF NOT EXISTS idx_agent_registry_client ON agent_registry(client_id);

-- Optional: Task Queue Table (if not using Redis Streams exclusively)
CREATE TABLE IF NOT EXISTS task_queue (
    task_id TEXT PRIMARY KEY,
    target_agent TEXT NOT NULL,
    task_type TEXT NOT NULL,
    payload JSONB,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
