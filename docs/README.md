# Aether Agent - Usage Guide

## Overview

Aether is a semi-autonomous AI assistant agent designed for CJ (CEO/CTO of AetherPro Technologies) and his executive assistant "Relay." It extends the OpenClaw (formerly Clawdbot) foundation with a novel Redis-based memory system, NVIDIA Kimik2.5 integration, and a Fleet Manager Control Plane (FMC) for orchestration.

This guide provides instructions on how to use the Aether agent within your OpenClaw environment.

## Spawning the Aether Agent

To start the Aether agent, you can use the `sessions_spawn` command in your OpenClaw terminal or via a message to your main OpenClaw agent. You will need to specify the Aether agent profile.

```bash
# Spawn Aether using the 'aether' profile
sessions_spawn aether
```

Alternatively, you can send a message to your OpenClaw agent:

> `spawn new agent with profile aether`

This will create a new session for the Aether agent, and you can start interacting with it immediately.

## Aether Commands

Aether provides a set of custom commands to manage its autonomy, memory, and fleet integration. These commands are accessible via the `/aether` prefix.

### Autonomy Control

-   `/aether toggle auto`: Switches the agent to **autonomous mode**. In this mode, Aether will execute tasks without requiring human approval for most actions.
-   `/aether toggle semi`: Switches the agent to **semi-autonomous mode**. In this mode, Aether will pause and ask for approval before executing potentially risky actions (e.g., sending emails, deleting files, making external API calls).

### Browser Control

-   `/aether browse <url> [purpose]`: Navigates to a URL and provides a vision-powered understanding of the page content based on your purpose.

### Memory Management

Aether's memory is powered by Redis, allowing for advanced features like checkpoints and rollbacks.

-   `/aether checkpoint <name>`: Creates a snapshot of the agent's current memory state. You can provide an optional `name` for the checkpoint for easy identification.
-   `/aether rollback <checkpoint_id>`: Reverts the agent's memory to a previously created checkpoint. You need to provide the `checkpoint_id` which is returned when you create a checkpoint.
-   `/aether stats`: Displays statistics about the agent's memory usage, including the number of daily logs, the size of the long-term memory, and the number of checkpoints.

### Fleet Integration

Aether is designed to work as a "pod" in a Fleet Manager Control Plane (FMC).

-   `/aether fleet status`: Shows the current status of the Aether pod within the fleet, including health metrics, uptime, and resource usage.
-   `/aether heartbeat`: Manually triggers a heartbeat to the Fleet Manager. This is useful for forcing a health check and reporting updated stats.

## Interacting with Aether

You can interact with Aether just like you would with any other OpenClaw agent. You can assign it tasks, ask it questions, and it will use its tools and memory to assist you.

### Example Interaction

> **User**: `Hey Aether, can you research the latest trends in AI-powered code generation and create a summary for me?`

In this scenario, Aether will:

1.  **Plan the task**: Break down the request into subtasks (e.g., search for articles, read and analyze content, synthesize a summary).
2.  **Execute the task**: Use its browsing and reading tools to gather information.
3.  **Check for approvals**: If in semi-autonomous mode, it might ask for approval before accessing external websites.
4.  **Generate the summary**: Use the NVIDIA Kimik2.5 model to create a high-quality summary.
5.  **Store the results**: Save the summary to its memory for future reference.

## Aether Skill

The Aether agent's capabilities are defined in the `aether.skill.md` file. This skill file is what makes the `/aether` commands available and integrates Aether's custom tools with the OpenClaw environment.

For more details on the technical implementation of Aether, please refer to the `aether_architecture.md` document.
