# Aether Agent - Installation and Deployment Guide

## Prerequisites

Before installing the Aether agent, ensure you have the following prerequisites in place.

### System Requirements

Aether is designed to run on systems that support OpenClaw (formerly Clawdbot). The following operating systems are supported:

- **macOS** (Intel or Apple Silicon)
- **Linux** (Ubuntu 22.04+, Debian, Fedora, Arch)
- **Raspberry Pi** (Raspbian)

### Software Dependencies

- **Python**: Version 3.10 or higher
- **Redis Stack**: Version 7.0 or higher (includes RedisJSON, RedisSearch, RedisGraph)
- **OpenClaw**: Latest version installed and configured
- **NVIDIA API Key**: Access to NVIDIA Research Tier API for Kimik2.5 model

### Optional Dependencies

- **Fleet Manager Control Plane (FMC)**: If you want to use fleet orchestration features
- **Telegram/Signal**: For approval notifications in semi-autonomous mode

## Installation Steps

### Step 1: Install Redis Stack

Redis Stack is required for Aether's memory management system. Follow the instructions for your operating system.

#### macOS (via Homebrew)

```bash
brew tap redis-stack/redis-stack
brew install redis-stack
```

#### Linux (Ubuntu/Debian)

```bash
curl -fsSL https://packages.redis.io/gpg | sudo gpg --dearmor -o /usr/share/keyrings/redis-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/redis-archive-keyring.gpg] https://packages.redis.io/deb $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/redis.list
sudo apt-get update
sudo apt-get install redis-stack-server
```

#### Start Redis Stack

```bash
# macOS
brew services start redis-stack

# Linux
sudo systemctl start redis-stack-server
sudo systemctl enable redis-stack-server
```

Verify Redis is running:

```bash
redis-cli ping
# Should return: PONG
```

### Step 2: Install OpenClaw

If you haven't already installed OpenClaw, follow the official installation guide at [https://docs.openclaw.ai/install](https://docs.openclaw.ai/install).

Quick installation:

```bash
curl -fsSL https://openclaw.ai/install.sh | bash
```

### Step 3: Install Aether Agent

Clone or extract the Aether project to your desired location:

```bash
cd /home/cory/Documents/AGENT_HARNESSES/clawdbot/
# Or wherever you want to install Aether
```

Install the Aether Python package:

```bash
cd aether_project
pip3 install -e .
```

This will install Aether in "editable" mode, allowing you to make changes to the code if needed.

### Step 4: Configure Environment Variables

Create a `.env` file in the Aether project directory with the following variables:

```bash
# NVIDIA API Key (required)
NVIDIA_API_KEY=your_nvidia_api_key_here

# Redis Configuration (optional, defaults shown)
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=

# Fleet Manager (optional)
FLEET_API_URL=http://localhost:8080/fleet
FLEET_API_KEY=your_fleet_api_key_here
```

Replace `your_nvidia_api_key_here` with your actual NVIDIA API key.

### Step 5: Apply OpenClaw Configuration Patches

Copy the configuration patches to your OpenClaw configuration directory:

```bash
cp config/config_patches.yaml ~/.openclaw/aether_patches.yaml
```

Merge the patches into your main OpenClaw configuration. You can do this manually by editing `~/.openclaw/openclaw.json` or by using the OpenClaw gateway configuration tool:

```bash
openclaw gateway config.apply ~/.openclaw/aether_patches.yaml
```

### Step 6: Initialize Aether Workspace

Create the Aether workspace directory and copy the necessary files:

```bash
mkdir -p ~/.openclaw/workspace/aether
cp -r workspace/* ~/.openclaw/workspace/aether/
```

Create the bootstrap files:

```bash
cd ~/.openclaw/workspace/aether

# Create AGENTS.md
cat > AGENTS.md << 'EOF'
# Aether Operating Instructions

You are Aether, a semi-autonomous AI assistant for CJ (CEO/CTO of AetherPro Technologies) and his executive assistant Relay.

## Core Capabilities
- Redis-based mutable memory with checkpoint/rollback
- NVIDIA Kimik2.5 for advanced reasoning
- Fleet Manager integration for orchestration
- Semi/auto autonomy modes

## Memory Management
- Daily logs: memory/YYYY-MM-DD.md
- Long-term memory: MEMORY.md
- Use checkpoints before major changes
- Migrate important daily entries to long-term weekly

## Autonomy
- Semi mode: Ask for approval on risky actions
- Auto mode: Execute autonomously with self-review
- Toggle with /aether toggle [auto|semi]
EOF

# Create SOUL.md
cat > SOUL.md << 'EOF'
# Aether Persona

## Identity
You are Aether, a professional and proactive AI assistant. You are helpful, efficient, and respectful.

## Boundaries
- Always respect user privacy
- Ask for approval before risky actions in semi mode
- Be transparent about your capabilities and limitations
- Prioritize user goals and preferences

## Tone
- Professional but friendly
- Clear and concise
- Proactive with suggestions
- Honest about uncertainties
EOF

# Create IDENTITY.md
cat > IDENTITY.md << 'EOF'
# Agent Identity

Name: Aether
Emoji: 🌌
Role: Semi-Autonomous AI Assistant
EOF

# Create USER.md
cat > USER.md << 'EOF'
# User Profiles

## CJ (Primary User)
- Role: CEO/CTO of AetherPro Technologies
- Preferences: Morning meetings, concise summaries, proactive suggestions
- Address as: CJ

## Relay (Executive Assistant)
- Role: Executive Assistant to CJ
- Preferences: Detailed reports, calendar management, email triage
- Address as: Relay
EOF

# Create MEMORY.md
touch MEMORY.md

# Create memory directory
mkdir -p memory
```

### Step 7: Start Aether

You can now start the Aether agent using OpenClaw's session spawning:

```bash
openclaw sessions_spawn aether
```

Or send a message to your main OpenClaw agent:

> `spawn new agent with profile aether`

## Verification

To verify that Aether is installed and running correctly:

1. **Check Redis connection**:
   ```bash
   redis-cli ping
   ```

2. **Test Aether commands**:
   Send a message to Aether:
   > `/aether stats`
   
   You should receive memory statistics.

3. **Test autonomy toggle**:
   > `/aether toggle auto`
   
   Aether should confirm the mode change.

4. **Create a checkpoint**:
   > `/aether checkpoint test_checkpoint`
   
   Aether should return a checkpoint ID.

## Troubleshooting

### Redis Connection Issues

If Aether cannot connect to Redis:

1. Verify Redis is running:
   ```bash
   redis-cli ping
   ```

2. Check Redis logs:
   ```bash
   # macOS
   tail -f /usr/local/var/log/redis-stack.log
   
   # Linux
   sudo journalctl -u redis-stack-server -f
   ```

3. Ensure the Redis port (6379) is not blocked by a firewall.

### NVIDIA API Issues

If you encounter NVIDIA API errors:

1. Verify your API key is correct in the `.env` file.
2. Check your API quota and rate limits.
3. Test the API manually:
   ```bash
   curl -H "Authorization: Bearer YOUR_API_KEY" \
        https://integrate.api.nvidia.com/v1/models
   ```

### OpenClaw Integration Issues

If Aether doesn't appear as an available agent:

1. Verify the configuration patches were applied correctly:
   ```bash
   openclaw gateway config.show | grep aether
   ```

2. Restart the OpenClaw gateway:
   ```bash
   openclaw gateway restart
   ```

3. Check OpenClaw logs for errors:
   ```bash
   openclaw logs
   ```

## Updating Aether

To update Aether to a new version:

```bash
cd aether_project
git pull  # If using git
pip3 install -e . --upgrade
```

Restart the Aether agent after updating.

## Uninstalling Aether

To remove Aether from your system:

```bash
# Uninstall the Python package
pip3 uninstall aether-agent

# Remove the workspace
rm -rf ~/.openclaw/workspace/aether

# Remove configuration patches
rm ~/.openclaw/aether_patches.yaml

# Optionally, remove Redis Stack if not used by other applications
# macOS
brew services stop redis-stack
brew uninstall redis-stack

# Linux
sudo systemctl stop redis-stack-server
sudo apt-get remove redis-stack-server
```

## Next Steps

Now that Aether is installed, you can:

- Read the [Usage Guide](README.md) to learn how to interact with Aether
- Review the [Architecture Documentation](../aether_architecture.md) to understand how Aether works
- Customize the agent's persona and operating instructions in the workspace files
- Integrate Aether with your Fleet Manager Control Plane (if available)

For support and questions, please contact the AetherPro Technologies team.
