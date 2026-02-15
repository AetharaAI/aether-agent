# AetherOS System State & Changelog
**Date:** February 13, 2026
**Current Branch:** `contained`
**Version:** v3.1

## 1. System Status Overview

- **Current Branch (`contained`)**: Stable. Contains critical runtime and infrastructure fixes.
- **Main Branch (`main`)**: Stable baseline. Currently 1 commit behind `contained`.
    - **Stability Benchmark**: The `main` branch state was validated with a successful **20-task benchmark test** prior to the implementation of the Checkpointing Architecture.

## 2. Recent Major Integrations & Fixes

### A. Fabric Integration Refactor (Critical Stability Fix)
- **Problem**: The WebSocket user session lifecycle was tightly coupled to the `FabricIntegration` startup. When the Fabric client failed to connect (e.g., due to Redis timeout), it blocked the WebSocket handshake, causing the user session to crash immediately.
- **Resolution**:
    - Refactored `agent_websocket.py` to initialize Fabric in a **non-blocking background task** (`asyncio.create_task`).
    - Added error handling to ensure the core agent runtime allows user interaction even if the optional Fabric infrastructure is offline.
    - **Result**: WebSocket sessions are now resilient and decoupled from infrastructure outages.

### B. Runtime Environment & Port Conflict Resolution
- **Problem**: Persistent `CONNECTION_RESET` errors were observed on port `16380`, preventing the UI from connecting to the API despite the container running significantly. This indicated a low-level host port conflict or "zombie" process.
- **Resolution**:
    - Switched `aether-api` service from port `16380` to **16399** in `docker-compose.yml` and `.env`.
    - Updated `VITE_API_URL` and `VITE_WS_URL` in `.env` to point to `http://127.0.0.1:16399`.
    - **Result**: Stable connectivity restored between Frontend and Backend.

### C. Checkpointing Architecture
- **Description**: Enabled persistent state saving and recovery for agent sessions.
- **Status**: Implemented and integrated, pending full regression testing (post-benchmark).

### D. Configuration Alignment
- **Fixed**: Confirmed `FABRIC_REDIS_URL` in `.env` points to `redis://triad.aetherpro.tech:6379` (external host) instead of `localhost` (internal container), resolving the connectivity timeout that triggered the Fabric crash.

## 3. Next Steps & Roadmap

The immediate next phase involves implementing the **Multi-Provider Model Role Harness** to transform AetherOS from a single-model runner into a role-based orchestration system.

**Reference Document:**
[AetherOS-Proposed-Update-Multi-Provider-Model-Role-Harness.md](./AetherOS-Proposed-Update-Multi-Provider-Model-Role-Harness.md)

### Key Proposed Features:
1.  **Provider Router**: Abstraction layer for OpenAI, LiteLLM, Anthropic, etc.
2.  **Harness Config**: Defining specific models for specific roles (Chat, Vision, Planner, Browser).
3.  **Scheduler**: Logic to route tasks to the most appropriate specialized model/role.
