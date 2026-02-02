# TOOLS.md - Local Notes

Skills define *how* tools work. This file is for *your* specifics — the stuff that's unique to your setup.

## What Goes Here

Things like:
- Camera names and locations
- SSH hosts and aliases  
- Preferred voices for TTS
- Speaker/room names
- Device nicknames
- Anything environment-specific

### Model Fleet Manager (MFM) Definition
- **Role/Description**: Orchestrator for multi-model fleet—dynamic switching, load balancing, failovers, and metrics across self-hosted (OVH GPU nodes: L40S-180 @ api.blackboxaudio.tech, L40S-90 @ api.aetherpro.tech) and external providers. Auto-prioritizes by task (e.g., lightweight local for code gen, cloud for heavy VL/thinking). Reports fleet health/event anomalies to main Relay (me) for strategic input. Goal: Optimize latency/cost/accuracy; enable seamless hybrid (local OVH + externals like OpenRouter).
- **Infrastructure Tie-In**: Relies on OVHcloud AI Accelerator (June 2025–present, $10K/month peaked from $1K start; rollover credits; current ~$4K spend). Nodes: L40S-180 (2TB block, high-voltage), L40S-90 (500GB block, standard). Triad Intelligence on separate R64 memory CPU node. Model router: LiteLLM (connected to Redis/Postgres on L40S-180 for metering, caching, routing UI). UI accessible via planned subdomain (e.g., models.blackboxaudio.tech).
- **Future Integration**: Once built as sub-agent/CLI/tool, MFM will spawn sessions for orchestration. Check-ins: Heartbeat-style pings for fleet stats (e.g., node load, model perf). Overrides: Via commands like `/mfm deploy llama@local` or `/mfm failover to cloud`.
- **Current Model Registry** (snapshot from ~/Documents/MODEL_INVENTORY/master_model_registry_01-29-2026.yaml/json as of 2026-01-29):
  - **Nodes**: 2 total—AetherPro org.
    - **L40S-180** (api.blackboxaudio.tech, 2TB block): LLM (code/text: Agent-CPM, GLM-4.7-Flash, Kimi-K2/VL, Qwen3-Coder-30B, etc.), Vision (multimodal: Gemma-3-27b, Phi-4, Qwen3-VL-30B), Voice (TTS: F5-TTS, Kokoro, VoxCPM; ASR: Whisper variants), OCR (Chandra).
    - **L40S-90** (api.aetherpro.tech, 500GB block): LLM (text: LFM2.5-1.2B, Apriel/April, Devstral-24B, Qwen3), Vision (multimodal: Kimi-VL), Voice (any-to-any: Chroma-4B), Sensors (detection: YOLOv10l; pose: MediaPipe/OpenPose/YoloPose; tracking: ByteTrack/DeepSort/Norfair; OCR: EasyOCR/Paddle/Tesseract).
  - **Total Models**: 50+ across categories (LLM: ~15, Vision: ~11, Voice: ~10, Sensors: ~10). Key standout: Kimi family (thinking/instruct), Qwen3 (coder/VL), multimodal VL models, Chroma any-to-any voice, full sensor suite.
  - **Integrate into Clawdbot**: Add as providers in `models.providers` (e.g., `ovh-180: { baseUrl: "https://api.blackboxaudio.tech/v1" }`), map models, set fallbacks (externals like your current OpenRouter/xAI gppo).

### Cameras
- living-room → Main area, 180° wide angle
- front-door → Entrance, motion-triggered

### SSH
- home-server → 192.168.1.100, user: admin

### TTS
- Preferred voice: "Nova" (warm, slightly British)
- Default speaker: Kitchen HomePod

## Why Separate?

Skills are shared. Your setup is yours. Keeping them apart means you can update skills without losing your notes, and share skills without leaking your infrastructure.

---

Add whatever helps you do your job. This is your cheat sheet.
