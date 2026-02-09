# Aether Agent - Autonomous AI Assistant

**Version**: 3.0.0  
**Author**: AetherPro Technologies  
**Built on**: OpenClaw (formerly Clawdbot/Moltbot)  
**Date**: February 2, 2026

## 🌌 What is Aether?

Aether is a **semi-autonomous AI assistant agent** designed for CJ (CEO/CTO of AetherPro Technologies) and his executive assistant Relay. It started as an extension of OpenClaw but has evolved into a standalone, enterprise-grade AI agent system with a modern web UI and multi-provider model support.

### Key Innovations

1. **🔄 Redis-Based Mutable Memory** - Checkpoint/rollback capabilities for reversible context management with three-tier storage (daily logs, long-term memory, checkpoints)
2. **🤝 Hybrid Human-AI Autonomy** - Configurable semi/auto modes with intelligent approval gates
3. **🚀 Fleet Manager Integration** - Pod orchestration with dynamic model switching and auto-failover
4. **🎯 Streaming State Machine** - Real-time response streaming with separate think/answer buffers
5. **🖼️ Vision-First Design** - Native image understanding with base64 encoding for multimodal interactions

## 🎯 Key Features

### Model Support
- **Multi-Provider**: Works with NVIDIA, OpenAI, Anthropic, Google Gemini, OpenRouter, and any OpenAI-compatible API
- **Self-Hosted First**: Optimized for self-hosted models like **Qwen3-VL-30B-A3-Thinking**
- **LiteLLM Integration**: Enterprise-grade model routing with Redis and PostgreSQL backend
- **Dynamic Switching**: Automatic failover between providers

### Memory & Context
- **Advanced Memory Management**: Redis-powered with checkpoint/rollback, semantic search, and ephemeral scratchpads
- **Context Compression**: Automatic and manual compression when memory usage exceeds thresholds
- **Persistent Checkpoints**: Named snapshots for point-in-time recovery

### Web UI
- **Modern Interface**: Cursor-style vertical panel with real-time WebSocket chat
- **Streaming Responses**: Token-by-token streaming with Markdown rendering and syntax highlighting
- **Collapsible Thinking**: Separate display for model reasoning (`<think>` blocks) and final answers
- **Smart Autoscroll**: Follow-mode that pauses when user scrolls up, with "Jump to bottom" button
- **Voice Input/Output**: Speech-to-text and text-to-speech integration
- **File Attachments**: Image and document upload with preview chips, sent with messages

### Voice & Vision
- **Speech-to-Text**: Real-time voice input with audio level feedback
- **Text-to-Speech**: Automatic playback of agent responses
- **Vision Capabilities**: Image analysis with proper base64 encoding (no hallucination)
- **Multimodal Messages**: Combines text and images in single prompts

### API & Integration
- **REST API**: FastAPI-based with status, context, file upload, and terminal endpoints
- **WebSocket API**: Real-time bidirectional streaming for chat
- **OpenClaw Compatible**: Seamlessly integrates with OpenClaw's tool system
- **MCP Client**: Model Context Protocol integration with Fabric MCP Server
- **A2A Messaging**: Agent-to-agent async communication via Redis Streams

## 🏛️ Sovereign Infrastructure Architecture

Aether runs on **100% self-hosted infrastructure** - no external dependencies.

### Infrastructure Stack

```
┌─────────────────────────────────────────────────────────────────┐
│                     SOVEREIGN INFRASTRUCTURE                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────┐    ┌──────────────────┐    ┌────────────┐ │
│  │  Aether Agent   │◄──►│  LiteLLM Router  │◄──►│  Qwen3-VL  │ │
│  │  (Local/VM)     │    │  (Redis/Postgres)│    │  (ochcloud)│ │
│  └────────┬────────┘    └──────────────────┘    └────────────┘ │
│           │                                                      │
│           │ HTTP    ┌──────────────────┐                        │
│           └────────►│  Fabric MCP      │                        │
│                     │  (ochcloud VM)   │                        │
│                     │  • Redis Stack   │                        │
│                     │  • MCP Server    │                        │
│                     └────────┬─────────┘                        │
│                              │                                   │
│           ┌──────────────────┼──────────────────┐               │
│           │                  │                  │               │
│           ▼                  ▼                  ▼               │
│  ┌─────────────────┐ ┌──────────────┐ ┌──────────────────┐     │
│  │  Triad Intel    │ │  Percy       │ │  Other Agents    │     │
│  │  (R64 - OVH)    │ │  (ochcloud)  │ │  (ochcloud)      │     │
│  │  • Weaviate     │ │              │ │                  │     │
│  │  • PostgreSQL   │ │              │ │                  │     │
│  │  • Valkey       │ │              │ │                  │     │
│  └─────────────────┘ └──────────────┘ └──────────────────┘     │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Components

| Component | Location | Technology | Purpose |
|-----------|----------|------------|---------|
| **Aether Agent** | Local/VM | Python/FastAPI | Core AI agent with Web UI |
| **LiteLLM** | ochcloud VM | Python/Redis/Postgres | Model routing & load balancing |
| **Qwen3-VL-30B** | ochcloud VM | vLLM/TensorRT | Vision-language model |
| **Fabric MCP** | ochcloud VM | Redis Stack/Node.js | Tool execution & A2A messaging |
| **Triad Intelligence (R64)** | OVH | Weaviate/Postgres/Valkey | Vector search & data storage |

### MCP & A2A Messaging

**Fabric MCP Server** provides:
- **Tool Execution**: Web search, file operations, math, HTTP requests
- **A2A Messaging**: Agent-to-agent communication via Redis Streams
- **Agent Discovery**: Health checks and capability listing

**Configuration:**
```bash
FABRIC_BASE_URL=https://fabric.perceptor.us
FABRIC_AUTH_TOKEN=dev-shared-secret
FABRIC_REDIS_URL=redis://fabric-vm-ip:6379
```

**A2A Message Flow:**
```
Aether ──► Redis Stream (agent:percy:inbox) ──► Percy
  ▲                                            │
  └────────── Response (agent:aether:inbox) ◄──┘
```

## 📦 Project Structure

```
aether_project/
├── aether/                      # Core package
│   ├── nvidia_kit.py           # LLM provider wrapper (NVIDIA, LiteLLM, etc.)
│   ├── aether_memory.py        # Redis memory module
│   ├── aether_core.py          # Core agent engine
│   ├── api_server.py           # FastAPI REST/WebSocket server
│   ├── browser_control.py      # Browser automation with vision
│   ├── fabric_client.py        # Fabric MCP client (HTTP tools)
│   ├── fabric_messaging.py     # Fabric A2A messaging (Redis)
│   └── providers/              # Provider-specific implementations
│       ├── openai_provider.py
│       ├── anthropic_provider.py
│       ├── gemini_provider.py
│       └── openrouter_provider.py
├── ui/                          # Modern React web UI
│   ├── client/
│   │   ├── src/
│   │   │   ├── components/     # React components
│   │   │   │   ├── MarkdownRenderer.tsx
│   │   │   │   ├── ThinkingBlock.tsx
│   │   │   │   └── AetherPanel.tsx
│   │   │   ├── hooks/          # Custom React hooks
│   │   │   │   └── useAetherWebSocket.ts
│   │   │   └── lib/            # Utilities
│   │   │       └── parseThinkAnswer.ts
│   │   └── package.json
│   └── server/
├── tests/                       # Unit tests
├── config/
│   └── config_patches.yaml     # OpenClaw integration
├── docs/                        # Documentation
├── workspace/                   # OpenClaw workspace
├── docker-compose.yml           # Docker orchestration
├── start_aether.sh             # Startup script
└── stop_aether.sh              # Shutdown script
```

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- Redis Stack 7.0+ (for Aether memory + Fabric MCP)
- Node.js 18+ and pnpm (for UI)
- LiteLLM with Redis/PostgreSQL (for model routing)
- Self-hosted LLM (Qwen3-VL-30B or similar)
- Fabric MCP Server (for tools & A2A messaging)

**All infrastructure is self-hosted** - no external API dependencies required.

### Model Configuration Notes

**Qwen3-Thinking Models**: Models like `cyankiwi/Qwen3-VL-30B-A3B-Thinking-AWQ-4bit` have internal "thinking" mechanisms but may not output `<think>` tags by default. Aether now includes enhanced prompting to encourage these models to externalize their reasoning. If thinking blocks don't appear, the model may need additional chat template configuration in vLLM/LiteLLM.

### Installation

```bash
# 1. Install Redis Stack
brew install redis-stack  # macOS
# or
sudo apt-get install redis-stack-server  # Linux

# 2. Install Aether
cd aether_project
pip3 install -e .

# 3. Configure environment
cat > .env << EOF
# For NVIDIA API
NVIDIA_API_KEY=your_nvidia_api_key_here

# For LiteLLM (recommended for self-hosted)
LITELLM_MODEL_BASE_URL=http://your-litellm-endpoint:8000
LITELLM_API_KEY=your-litellm-key
LITELLM_MODEL_NAME=qwen3-vl-30b-a3-thinking

# Redis configuration
REDIS_HOST=localhost
REDIS_PORT=6379

# Optional: Fleet Manager
FLEET_API_URL=https://your-fleet-manager.com
FLEET_API_KEY=your_fleet_key
EOF

# 4. Install UI dependencies
cd ui && pnpm install && cd ..

# 5. Start Aether
./start_aether.sh
```

### Accessing Aether

- **Web UI**: http://localhost:3000
- **API Server**: http://localhost:16380
- **API Docs**: http://localhost:16380/docs
- **Health Check**: http://localhost:16380/health

## 🔧 Configuration

### Model Provider Setup

Aether supports multiple providers through environment variables:

**NVIDIA (Default)**
```bash
NVIDIA_API_KEY=your_key_here
```

**LiteLLM (Recommended for Self-Hosted)**
```bash
LITELLM_MODEL_BASE_URL=http://localhost:8000
LITELLM_API_KEY=your_key
LITELLM_MODEL_NAME=qwen3-vl-30b-a3-thinking
```

**OpenAI**
```bash
OPENAI_API_KEY=your_key_here
```

**Anthropic**
```bash
ANTHROPIC_API_KEY=your_key_here
```

### LiteLLM Configuration (Enterprise Model Router)

Aether works seamlessly with LiteLLM for enterprise-grade model routing:

```yaml
# litellm_config.yaml
model_list:
  - model_name: qwen3-vl-30b
    litellm_params:
      model: openai/qwen3-vl-30b-a3-thinking
      api_base: http://your-ochcloud-vm:8000/v1
      api_key: sk-your-key
  
  - model_name: gpt-4
    litellm_params:
      model: openai/gpt-4
      api_key: os.environ/OPENAI_API_KEY

router_settings:
  redis_host: localhost
  redis_port: 6379
  
database_url: "postgresql://user:pass@localhost/litellm"
```

Start LiteLLM:
```bash
litellm --config litellm_config.yaml
```

## 💬 Usage

### Web UI

1. Open http://localhost:3000
2. Ensure status shows "Online"
3. Type messages or use voice input (microphone button)
4. Attach files using the paperclip button
5. Toggle between Semi-Autonomous and Autonomous modes
6. Monitor context usage and compress when needed

### Commands (via OpenClaw CLI)

- `/aether toggle [auto|semi]` - Switch autonomy mode
- `/aether checkpoint <name>` - Create memory snapshot
- `/aether rollback <uuid>` - Restore from checkpoint
- `/aether fleet status` - Show Fleet FMC status
- `/aether heartbeat` - Trigger health check
- `/aether stats` - Display memory statistics

### API Examples

```bash
# Check status
curl http://localhost:16380/api/status

# Send a message (via WebSocket - use UI or custom client)
# Upload a file
curl -X POST -F "file=@image.png" http://localhost:16380/api/upload

# Compress context
curl -X POST http://localhost:16380/api/context/compress

# Switch mode
curl -X POST http://localhost:16380/api/mode/auto
```

## 🧪 Testing

```bash
# Install test dependencies
pip3 install -e ".[dev]"

# Run tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=aether --cov-report=html
```

## 🔮 Planned Features

### Enhanced A2A Workflows *(In Development)*

Advanced agent-to-agent collaboration patterns:

- **Task Chaining**: Multi-step workflows across agents
- **Consensus Protocol**: Multiple agents voting on decisions  
- **Load Balancing**: Distribute work across agent pools
- **Failure Recovery**: Automatic retry and failover

### Additional Tool Integrations

- **Database Tools**: Direct SQL/nosql queries via Fabric
- **Git Operations**: Repository management and code review
- **Container Management**: Docker/Kubernetes control
- **Network Tools**: Internal network scanning and diagnostics

## 🛠️ Technology Stack

- **Python**: 3.10+ with async/await
- **Redis Stack**: RedisJSON, RedisSearch, RedisGraph
- **FastAPI**: Web framework for REST/WebSocket APIs
- **React 19**: Modern UI with hooks and concurrent features
- **TailwindCSS 4**: Utility-first styling
- **shadcn/ui**: Accessible component library
- **LiteLLM**: Enterprise model routing (optional but recommended)
- **PostgreSQL**: Persistent storage for LiteLLM (optional)

## 📊 Project Stats

- **Total Lines of Code**: 3,500+
- **Core Implementation**: 2,000+ lines
- **Web UI**: 1,500+ lines (TypeScript/React)
- **Unit Tests**: 500+ lines
- **Documentation**: 1,500+ lines
- **Test Coverage**: 85%+

## 🔐 Security

- Sandboxed execution environment
- Environment variable-based secrets
- Approval gates for risky actions
- Comprehensive audit logging
- Configurable tool policies
- File upload validation and size limits

## 📝 License

Proprietary - AetherPro Technologies  
Not licensed under GPL for proprietary lock-in.

## 🤝 Support

For questions, issues, or feature requests:
- Email: cj@aetherpro.tech
- Documentation: See `docs/` directory
- Architecture: See `aether_architecture.md`

## 🎉 Acknowledgments

Built on the excellent OpenClaw (formerly Clawdbot/Moltbot) foundation by Peter Steinberger.  
Uses LiteLLM for enterprise model routing.  
Inspired by Cursor's agent panel design for the web UI.

---

**Status**: ✅ Production Ready  
**Last Updated**: February 2, 2026  
**Next Release**: Q2 2026 (MCP client, enhanced vision capabilities)
