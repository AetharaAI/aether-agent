# MCAS Gateway Architecture - Technical Documentation

## Overview
The MCAS (Multi-Agent Communication System) gateway provides a secure, scalable communication bridge between external messaging platforms (Telegram, etc.) and internal AI model inference services. This architecture separates concerns between secure tunneling, message processing, and model execution.

## Core Architecture

### 1. Service Separation Pattern
```
┌─────────────┐    ┌──────────────┐    ┌─────────────────┐
│   Telegram  │ ←→ │   Gateway    │ ←→ │  Model Runner   │
│   Bot       │    │   (Secure    │    │  (Self-hosted  │
│             │    │   Tunnel)    │    │   Models)      │
└─────────────┘    └──────────────┘    └─────────────────┘
```

### 2. Component Breakdown

#### Gateway Service
- **Purpose**: Secure tunnel and API endpoint
- **Port**: 18080 (default)
- **API Endpoint**: `/v1/chat/completions` (OpenAI-compatible)
- **Function**: Authentication, rate limiting, request routing
- **Security**: No direct channel integrations, clean tunnel only

#### Channel Plugins (Standalone)
- **Purpose**: Messaging platform integrations
- **Deployment**: Standalone services calling gateway API
- **Examples**: Telegram, Discord, WhatsApp runners
- **Communication**: HTTP POST to gateway endpoint

#### Model Provider Layer
- **Purpose**: AI model execution
- **Configuration**: vLLM, LiteLLM, or other compatible APIs
- **Authentication**: API keys managed via environment variables
- **Routing**: Model selection and load balancing

## Implementation Details

### Environment Configuration
```bash
# Model Provider Settings
MCAS_VLLM_URL=https://your-model-endpoint/v1
MCAS_VLLM_KEY=your-api-key

# Gateway Settings
MCAS_GATEWAY_PORT=18080
MCAS_GATEWAY_HOST=0.0.0.0

# Channel Plugin Settings
MCAS_TELEGRAM_BOT_TOKEN=your-telegram-token
```

### API Flow
1. External message received by channel plugin
2. Message formatted to OpenAI-compatible JSON
3. POST request to gateway `/v1/chat/completions`
4. Gateway authenticates and validates request
5. Request forwarded to configured model provider
6. Response returned to channel plugin
7. Channel plugin formats and sends response back

### Security Considerations
- Gateway remains clean (no embedded channel logic)
- Channel plugins run as separate processes
- API key rotation supported
- Rate limiting at gateway level
- End-to-end encryption maintained

## Deployment Commands

### Start Gateway
```bash
pnpm gateway
```

### Start Channel Plugin
```bash
pnpm telegram
```

### Health Checks
- Gateway: `GET /health`
- Channel: `GET /status`

## Model Integration

### Supported Providers
- vLLM endpoints
- LiteLLM proxy
- OpenAI-compatible APIs
- Custom model endpoints

### Configuration Example
```typescript
// config/manager.ts
const providers = {
  vllm: {
    baseUrl: process.env.MCAS_VLLM_URL,
    apiKey: process.env.MCAS_VLLM_KEY || process.env.MCAS_VLLM_URL_KEY,
    api: 'openai-completions',
    models: ['your-model-name']
  }
};
```

## Troubleshooting

### Common Issues
1. **API Key Mismatch**: Ensure `MCAS_VLLM_KEY` and `MCAS_VLLM_URL_KEY` are consistent
2. **Port Conflicts**: Verify gateway port availability
3. **Plugin Connectivity**: Confirm channel plugins can reach gateway IP:PORT

### Logs Location
- Gateway: `/tmp/openclaw/openclaw-YYYY-MM-DD.log`
- Channel plugins: Console output or designated log files

## Migration Guide for Other Agents

### Step 1: Extract Channel Logic
Remove all channel-specific code from your main gateway service.

### Step 2: Configure Gateway Endpoint
Point your channel plugins to the centralized gateway API.

### Step 3: Update Authentication
Use environment variables for model provider keys.

### Step 4: Test Communication
Verify end-to-end message flow from channel to model and back.

### Step 5: Scale Independently
Deploy gateway, channels, and model runners as needed for performance.

## Benefits of This Architecture

- **Scalability**: Independent scaling of each component
- **Security**: Clean separation of concerns
- **Maintainability**: Isolated component updates
- **Flexibility**: Easy addition of new channels/models
- **Resilience**: Failure isolation between components