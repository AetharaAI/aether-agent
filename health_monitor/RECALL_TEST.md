# System Health Monitor - Memory Recall Test

## 1. What were the 3 design decisions you made in Phase 1 and why?

1. **Use only stdlib + psutil**
   - Why: psutil is a stable, cross-platform standard for system monitoring in Python. While /proc parsing is possible on Linux, it's error-prone and non-portable. psutil abstracts platform differences cleanly and is widely trusted. If psutil is unavailable, we'll fall back gracefully to /proc parsing on Linux.

2. **Store historical data in JSONL format**
   - Why: JSONL (JSON Lines) is ideal for streaming and appending records without locking or parsing entire files. It allows easy line-by-line processing, is human-readable, and integrates cleanly with scripting tools like jq. This avoids the complexity of SQLite or other databases for a lightweight tool.

3. **Separate collector, reporter, and main logic**
   - Why: This enforces separation of concerns. Collectors gather raw data, reporters format and summarize, and monitor.py coordinates flow. This improves testability (e.g., mock collectors), reusability (e.g., use reporter in other tools), and maintainability. Each component can be updated or replaced independently.

## 2. How many report files did Phase 3 create and what was the first timestamp?

- 5 report files were created in the `reports/` directory.
- The first report file was: `report_20260220T021538.txt`

## 3. What flags does monitor.py accept?

monitor.py accepts the following flags:
- `--interval`: Collection interval in seconds (default: 5)
- `--count`: Number of collections to perform (default: 1)
- `--no-history`: Do not append to history.jsonl (optional)

## 4. What time did this session start? (read SESSION_START.txt)

The session started at: 2026-02-20 02:14:19