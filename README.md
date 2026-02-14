<div align="center">
  <img src="logos/logo.png" alt="AetherOS Logo" width="200"/>
</div>

# AetherOS - Sovereign AI Operating System

**Version**: 3.1.0  
**Status**: Production / Sovereign Infrastructure  
**Infrastructure**: Self-hosted (Triad Intelligence, Fabric MCP, MCAS)

## 🌌 Overview

AetherOS is a **sovereign, autonomous agentic operating system** designed for high-performance execution on self-hosted infrastructure. Unlike standard AI assistants, AetherOS acts as a complete "operating interface," managing identity, memory, tools, and multi-agent coordination through a vertically integrated stack.

Key Capabilities:
*   **Vertical Integration**: Native connection to Triad Intelligence (Redis, Postgres, Qdrant) and MCAS.
*   **Hybrid Autonomy**: Toggle between Semi-Auto (Human-in-the-loop) and Fully Autonomous modes.
*   **Persistent Memory**: Full state persistence via Redis and Postgres-backed telemetry.
*   **Sovereign Tooling**: Integrates with Fabric MCP for secure, air-gapped tool execution.

## 🏗️ Architecture

AetherOS operates within the **Triad Intelligence** ecosystem, leveraging dedicated infrastructure for memory, vector storage, and model serving.

```mermaid
graph TD
    User[Web UI / Voice] <--> Aether[AetherOS Core]
    
    subgraph "Infrastructure (Triad)"
        Aether --> Redis[Redis Stack (6380)]
        Aether --> Postgres[Postgres (5432)]
        Aether --> Qdrant[Qdrant (6333)]
    end
    
    subgraph "Model Gateway (MCAS)"
        Aether --> LiteLLM[LiteLLM Router]
        LiteLLM --> MCAS[MCAS Gateway (18080)]
        MCAS --> Models[Self-Hosted Models]
    end
    
    subgraph "Capabilities"
        Aether --> Fabric[Fabric MCP]
        Fabric --> Tools[Secure Tools]
    end
```

### Components

| Component | Endpoint | Description |
|-----------|----------|-------------|
| **Aether Core** | `localhost:16380` | Main agent runtime and API server. |
| **Aether UI** | `localhost:16382` | React-based visual interface. |
| **Triad Redis** | `triad.aetherpro.tech:6380` | Hot memory, pub/sub, scratchpad. |
| **Triad PG** | `triad.aetherpro.tech:5432` | Long-term logs, telemetry, identity. |
| **Triad Qdrant** | `triad.aetherpro.tech:6333` | Vector embeddings and knowledge retrieval. |
| **MCAS** | `api.blackboxaudio.tech` | Multi-Channel Agent Switch & Model Gateway. |

## 🚀 Deployment

AetherOS is designed to run via Docker Compose, connecting to your existing `triad` infrastructure.

### 1. Configuration
Ensure your `.env` file is configured with production credentials:

```bash
# Infrastructure
REDIS_HOST=triad.aetherpro.tech
REDIS_PORT=6380
POSTGRES_DSN=postgresql://uap_core:password@triad.aetherpro.tech:5432/aetheros
QDRANT_URL=http://triad.aetherpro.tech:6333

# Models (via MCAS)
LITELLM_MODEL_BASE_URL=https://api.blackboxaudio.tech/v1
LITELLM_API_KEY=sk-aether-master-pro
```

### 2. Build and Run
```bash
docker-compose up --build -d
```

This will start:
*   **aether-api**: The backend runtime.
*   **aether-ui**: The frontend interface.

### 3. Access
*   **Web UI**: [http://localhost:16382](http://localhost:16382)
*   **API Docs**: [http://localhost:16380/docs](http://localhost:16380/docs)

## 🧠 Telemetry & Observability

AetherOS logs all activities for audit and improvement:
*   **Tool Calls**: Logged to Postgres `tool_calls` table.
*   **API Usage**: Token counts and costs tracked in `api_calls`.
*   **Session History**: Persisted in `agent_sessions`.

## 🛠️ MCAS Integration

AetherOS uses **MCAS (Multi-Channel Agent Switch)** as its gateway. MCAS separates the secure communication tunnel from model execution, allowing Aether to interact with models via a standardized OpenAI-compatible API while MCAS handles the complexity of message routing and secure tunneling to the physical hardware.

## 🤝 Contributing

Proprietary to **AetherPro Technologies**. 
Built on the OpenClaw foundation.
