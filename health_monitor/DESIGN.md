# System Health Monitor Design

## Overview
This CLI tool monitors system health metrics including:
- CPU usage (percent, per-core)
- Memory usage (RAM and swap)
- Disk usage (all mounted filesystems)
- Network traffic (sent/received)
- Top running processes (by CPU and memory usage)

## Design Decisions

1. **Use only stdlib + psutil**
   - Why: psutil is a stable, cross-platform standard for system monitoring in Python. While /proc parsing is possible on Linux, it's error-prone and non-portable. psutil abstracts platform differences cleanly and is widely trusted. If psutil is unavailable, we'll fall back gracefully to /proc parsing on Linux.

2. **Store historical data in JSONL format**
   - Why: JSONL (JSON Lines) is ideal for streaming and appending records without locking or parsing entire files. It allows easy line-by-line processing, is human-readable, and integrates cleanly with scripting tools like jq. This avoids the complexity of SQLite or other databases for a lightweight tool.

3. **Separate collector, reporter, and main logic**
   - Why: This enforces separation of concerns. Collectors gather raw data, reporters format and summarize, and monitor.py coordinates flow. This improves testability (e.g., mock collectors), reusability (e.g., use reporter in other tools), and maintainability. Each component can be updated or replaced independently.

## File Structure

health_monitor/
├── __init__.py
├── collector.py       # Raw data collection functions
├── reporter.py        # Formatting and summarization functions
├── monitor.py         # Main CLI entry point with args parsing
├── reports/
│   ├── report_20260220T021422.txt   # Human-readable reports
│   └── history.jsonl                # Append-only history of full stats
├── DESIGN.md          # This file
├── TODO.md            # Implementation checklist
├── SESSION_START.txt  # Start timestamp
├── README.md          # Project documentation (to be written)
├── requirements.txt   # Dependencies (to be written)
├── test_collector.py  # Unit tests for collectors (to be written)
├── BENCHMARK_RESULTS.md # Post-execution analysis (to be written)
├── RECALL_TEST.md     # Memory recall responses (to be written)


