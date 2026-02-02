# Aether - Complete AI Agent System

**Version**: 3.0.0 (Complete Edition)  
**Author**: Manus AI  
**Date**: February 1, 2026

## Overview

Aether is a production-ready, semi-autonomous AI agent system built on OpenClaw (formerly Clawdbot/Moltbot) with advanced capabilities including Redis-based mutable memory, NVIDIA Kimik2.5 integration, browser control with vision, and a modern web UI with voice capabilities.

This complete package includes everything needed to deploy and run Aether in production or development environments.

## Architecture

Aether consists of four main components that work together to provide a complete AI agent experience.

### Core Components

**Aether Core Engine** serves as the main agent orchestrator, managing task execution, autonomy control, and sub-pod delegation. It integrates with OpenClaw's tool ecosystem while adding Redis-based memory management and Fleet API support.

**NVIDIA Kimik2.5 Integration** provides the language model interface with streaming support, vision capabilities for browser screenshots, rate limiting, and automatic failover to ensure reliable operation.

**Redis Memory System** implements a three-tier memory architecture with daily logs for short-term context, long-term memory for persistent knowledge, and checkpoint snapshots for rollback capabilities. The system supports atomic operations and automatic migration between tiers.

**Browser Control Module** enables web automation with vision-powered element detection, screenshot analysis, form filling, and navigation capabilities, all integrated with Kimik2.5's vision for intelligent interaction.

### User Interfaces

**Web UI** offers a modern, Cursor-style vertical panel interface with real-time WebSocket chat, voice input via speech-to-text, voice output via text-to-speech, mode controls for semi/auto switching, context management with compression, and integrated terminal output viewing.

**CLI Interface** provides command-line access through OpenClaw's native interface, supporting all agent commands, skill invocation, and direct tool access for power users.

### API Layer

**REST API** exposes endpoints for status monitoring, context management, mode switching, file uploads, and terminal command execution.

**WebSocket API** enables real-time bidirectional communication for chat messages, streaming responses, and live status updates.

## Quick Start

### Prerequisites

Before installing Aether, ensure you have the following dependencies installed on your system.

Python 3.10 or higher is required for running the backend components. Redis Stack 7.0 or higher provides the memory storage system. Node.js 18 or higher and pnpm are needed for the web UI. An NVIDIA API key is required for Kimik2.5 access. Docker and Docker Compose are optional but recommended for containerized deployment.

### Installation

To install Aether, follow these steps to set up all components.

First, clone or extract the Aether package to your desired location. Navigate to the aether_project directory. Copy the environment template to create your configuration file by running `cp .env.template .env`. Edit the `.env` file and add your NVIDIA API key and configure other settings as needed. Install Python dependencies with `pip install -r requirements.txt`. If using the UI, navigate to the ui directory and install Node dependencies with `pnpm install`.

### Starting Aether

#### Option 1: Quick Start Script (Recommended)

The simplest way to start all components is using the provided startup script. Simply run `./start_aether.sh` from the aether_project directory. This will start Redis if not running, launch the API server, start the UI development server, and display access URLs and logs.

To stop all components, run `./stop_aether.sh`.

#### Option 2: Docker Compose

For a containerized deployment, use Docker Compose. Run `docker-compose up -d` to start all services in detached mode. View logs with `docker-compose logs -f`. Stop services with `docker-compose down`.

#### Option 3: Manual Start

For manual control of each component, start Redis Stack with `redis-server`. Start the API server by running `python -m aether.api_server` from the aether_project directory. Start the UI by navigating to the ui directory and running `pnpm dev`.

### Accessing Aether

Once started, you can access Aether through multiple interfaces.

The Web UI is available at `http://localhost:3000` and provides the full graphical interface. The API server runs at `http://localhost:8000` with API documentation at `/docs`. Health checks can be performed at `http://localhost:8000/health`. RedisInsight for database management is available at `http://localhost:8001`.

## Configuration

### Environment Variables

Aether uses environment variables for configuration. All settings should be placed in the `.env` file in the project root.

#### Core Settings

`NVIDIA_API_KEY` is required and specifies your NVIDIA API key for Kimik2.5 access. `REDIS_HOST` defaults to localhost and sets the Redis server hostname. `REDIS_PORT` defaults to 6379 and sets the Redis server port.

#### Fleet Integration (Optional)

`FLEET_API_URL` specifies the OpenClaw Fleet API endpoint. `FLEET_API_KEY` provides the authentication key for Fleet API.

#### Voice Services (Optional)

`VITE_ASR_ENDPOINT` defaults to `http://localhost:8001/asr` and sets the speech-to-text service endpoint. `VITE_TTS_ENDPOINT` defaults to `http://localhost:8002/tts` and sets the text-to-speech service endpoint.

For detailed voice service configuration, see `docs/VOICE_SETUP.md`.

### OpenClaw Integration

To integrate Aether with OpenClaw, copy the skill definition from `workspace/skills/aether.skill.md` to your OpenClaw skills directory. Apply configuration patches from `config/config_patches.yaml` to your OpenClaw configuration. Restart OpenClaw to load the Aether skill.

## Usage

### Web UI

The web UI provides the most intuitive way to interact with Aether.

To start a conversation, open the UI at `http://localhost:3000`. Ensure the status shows "Online" in the header. Type your message in the input field and press Enter or click Send.

For voice input, click the microphone button to start recording. Speak your message clearly. Click the checkmark when finished. The transcribed text will appear in the input field.

For voice output, click the speaker button to enable TTS. Agent responses will be spoken automatically. Click again to disable.

To manage context, monitor the context gauge for memory usage. Click "Compress Context" when usage exceeds 80%. The gauge will update after compression completes.

To switch modes, toggle the switch in the mode selector section. Semi-Autonomous requires approval for risky actions. Autonomous allows full automation.

### CLI Interface

For command-line interaction through OpenClaw, spawn an Aether session with `openclaw sessions_spawn aether`. Send commands with `openclaw sessions_send aether "your command"`. View session output with `openclaw sessions_view aether`.

### API

For programmatic access, refer to the API documentation at `http://localhost:8000/docs`. Examples include checking status with `GET /api/status`, compressing context with `POST /api/context/compress`, switching modes with `POST /api/mode/auto`, and uploading files with `POST /api/upload`.

## Features

### Memory Management

Aether's three-tier memory system provides flexible context management.

Daily logs store recent interactions and context with automatic timestamping and tagging. Long-term memory preserves important information across sessions with semantic organization and efficient retrieval. Checkpoint snapshots enable point-in-time recovery with named checkpoints and rollback capabilities.

Memory operations include logging to daily memory, migrating to long-term storage, creating checkpoints, rolling back to previous states, and flushing specific memory tiers.

### Browser Automation

The browser control module enables sophisticated web interactions.

Vision-powered navigation uses Kimik2.5 to analyze screenshots and find elements by description. Form filling and submission work with intelligent field detection. Screenshot capture and analysis provide visual understanding of web pages. Multi-step workflows execute complex sequences of actions.

### Voice Capabilities

Voice features provide natural interaction methods.

Speech-to-text conversion uses your configured ASR service with real-time audio level feedback and automatic transcription. Text-to-speech synthesis uses your configured TTS service with automatic playback of agent responses and on-demand voice output.

### Autonomy Control

Flexible autonomy modes adapt to different use cases.

Semi-Autonomous mode requires human approval for risky actions like sending emails, deleting files, making purchases, and external API calls. Autonomous mode allows full automation with minimal human intervention, automatic task completion, and sub-pod delegation.

## Project Structure

The complete Aether package is organized as follows.

```
aether_project/
├── aether/                 # Core Python modules
│   ├── __init__.py
│   ├── aether_core.py     # Main agent engine
│   ├── aether_memory.py   # Redis memory system
│   ├── nvidia_kit.py      # NVIDIA Kimik2.5 wrapper
│   ├── browser_control.py # Browser automation
│   └── api_server.py      # FastAPI server
├── ui/                     # Web UI (React + Tailwind)
│   ├── client/
│   │   ├── src/
│   │   │   ├── components/
│   │   │   ├── hooks/
│   │   │   ├── lib/
│   │   │   └── pages/
│   │   └── public/
│   ├── package.json
│   └── vite.config.ts
├── config/                 # Configuration files
│   └── config_patches.yaml
├── workspace/              # OpenClaw workspace
│   └── skills/
│       └── aether.skill.md
├── docs/                   # Documentation
│   ├── README.md
│   ├── INSTALLATION.md
│   ├── UI_GUIDE.md
│   └── VOICE_SETUP.md
├── tests/                  # Unit tests
│   ├── test_aether_core.py
│   ├── test_aether_memory.py
│   ├── test_nvidia_kit.py
│   └── test_browser_control.py
├── logs/                   # Runtime logs
├── requirements.txt        # Python dependencies
├── setup.py               # Package setup
├── docker-compose.yml     # Docker orchestration
├── Dockerfile.api         # API server Docker image
├── start_aether.sh        # Startup script
├── stop_aether.sh         # Shutdown script
├── .env.template          # Environment template
└── README_COMPLETE.md     # This file
```

## Development

### Running Tests

To run the test suite, execute `pytest tests/` from the aether_project directory. For coverage reports, use `pytest --cov=aether tests/`. To run specific test files, use `pytest tests/test_aether_core.py`.

### Adding Custom Skills

To extend Aether with custom skills, create a new skill file in `workspace/skills/`. Follow the OpenClaw skill format with clear instructions and tool specifications. Register the skill in OpenClaw's configuration. Restart Aether to load the new skill.

### Extending the UI

To customize the web interface, modify components in `ui/client/src/components/`. Update styles in `ui/client/src/index.css`. Add new pages in `ui/client/src/pages/`. The UI uses React 19, TailwindCSS 4, and shadcn/ui components.

## Troubleshooting

### Common Issues

**API Server Won't Start**: Check that Redis is running with `redis-cli ping`. Verify the NVIDIA API key is set in `.env`. Check logs in `logs/api_server.log`. Ensure port 8000 is not in use.

**UI Can't Connect to Backend**: Verify the API server is running at `http://localhost:8000/health`. Check `VITE_API_URL` in environment configuration. Look for CORS errors in browser console. Try refreshing the page.

**Voice Features Not Working**: Configure `VITE_ASR_ENDPOINT` and `VITE_TTS_ENDPOINT` in environment. Ensure your ASR/TTS services are running. Check browser microphone permissions. Verify audio format compatibility.

**Memory Issues**: Monitor Redis memory usage with `redis-cli INFO memory`. Compress context regularly when usage is high. Adjust Redis maxmemory settings if needed. Consider using Redis persistence for important data.

### Logs

Aether maintains several log files for debugging.

API server logs are in `logs/api_server.log`. UI development logs are in `logs/ui_dev.log`. Redis logs depend on your Redis configuration. Docker logs can be viewed with `docker-compose logs`.

## Production Deployment

### Security Considerations

For production deployments, implement these security measures.

Change default ports and use HTTPS for all connections. Store API keys securely using environment variables or secret management systems. Configure Redis authentication with `requirepass`. Enable Redis SSL/TLS for encrypted connections. Implement rate limiting on API endpoints. Use a reverse proxy like Nginx for the UI. Set up firewall rules to restrict access.

### Performance Optimization

Optimize Aether for production workloads.

Use Redis persistence with AOF for durability. Configure Redis maxmemory policies appropriately. Enable Redis clustering for horizontal scaling. Use a CDN for UI static assets. Implement caching for frequent API calls. Monitor resource usage and scale as needed.

### Monitoring

Set up monitoring for production systems.

Track API response times and error rates. Monitor Redis memory usage and connection counts. Set up alerts for service failures. Use health check endpoints for uptime monitoring. Implement logging aggregation for centralized analysis.

## Contributing

Contributions to Aether are welcome. When contributing, follow the existing code style and conventions. Add tests for new features. Update documentation as needed. Submit pull requests with clear descriptions.

## License

This project is licensed under the MIT License. See the LICENSE file for details.

## Support

For issues, questions, or feature requests, check the documentation in the `docs/` directory. Review logs for error messages. Consult the OpenClaw documentation for integration questions. Submit issues to the project repository.

## Acknowledgments

Aether is built on top of OpenClaw (formerly Clawdbot/Moltbot), an open-source AI agent framework. It integrates NVIDIA Kimik2.5 for language model capabilities and uses Redis Stack for memory management. The web UI is inspired by Cursor's agent panel design.

## Changelog

### Version 3.0.0 (Complete Edition)
- Added complete web UI with voice capabilities
- Integrated speech-to-text and text-to-speech
- Created unified deployment scripts
- Added Docker Compose orchestration
- Comprehensive documentation suite
- Production-ready configuration

### Version 2.0.0
- Added browser control with vision
- Enhanced NVIDIA Kimik2.5 integration
- Improved memory management

### Version 1.0.0
- Initial release with core agent functionality
- Redis-based memory system
- OpenClaw integration
- CLI interface
