# System Health Monitor

A lightweight CLI tool for monitoring system health metrics including CPU, memory, disk, network, and running processes.

## Features

- Real-time collection of system metrics
- Human-readable and JSON-formatted reports
- Append-only history in JSONL format for time-series analysis
- Trend summarization across multiple intervals
- Cross-platform support (Linux, macOS, Windows)
- Fallback to /proc parsing on Linux if psutil is unavailable

## Installation

### Prerequisites

- Python 3.8+
- psutil (recommended, but not required on Linux)

### Install psutil (recommended)

```bash
pip install psutil
```

### Clone and Use

```bash
git clone https://github.com/yourusername/health_monitor.git
cd health_monitor
```

## Usage

Run the monitor with default settings:

```bash
python health_monitor/monitor.py
```

### Command-line Options

| Flag | Description | Default |
|------|-------------|---------|
| `--interval SECONDS` | Time between collections | 5 |
| `--count N` | Number of collections to perform | 1 |
| `--no-history` | Skip writing to history.jsonl | off |

### Example: Collect every 2 seconds for 5 iterations

```bash
python health_monitor/monitor.py --interval 2 --count 5
```

## Output

The tool generates two types of output:

### 1. Human-readable Reports

Saved as `reports/report_TIMESTAMP.txt` with format:

```
============================================================
SYSTEM HEALTH REPORT
============================================================
Timestamp: 2026-02-20 02:15:38

CPU USAGE:
  Core 0: 5.2%

MEMORY USAGE:
  Total: 31.2 GB
  Used: 23.6 GB (75.9%)
  Available: 7.5 GB
  Free: 1.1 GB

SWAP USAGE:
  Total: 15.6 GB
  Used: 0.9 GB (5.5%)
  Free: 14.7 GB

DISK USAGE:
  /workspace: 741.7/937.4 GB (79.1%)

NETWORK I/O:
  Sent: 0.8 MB
  Received: 0.3 MB
  Packets Sent: 1,347
  Packets Recv: 1,362

TOP 0 PROCESSES:
  PID      CPU%   MEM%   NAME
  --------------------------------------------------

============================================================
```

### 2. JSONL History

Saved as `reports/history.jsonl`, one JSON object per line:

```json
{"cpu": {"timestamp": 1771553738.2028008, "percent": [5.24], ...}, "memory": {...}, ...}
```

Use `jq` to analyze:

```bash
cat reports/history.jsonl | jq '.cpu.percent[0]' -c
```

## Trend Summary

After collecting multiple reports, a trend summary is automatically generated:

```bash
cat reports/trend_summary_20260220T021546.txt
```

Example:

> Over the observed period, system health shows increasing CPU usage, stable memory utilization, stable disk pressure, stable network traffic, and stable process count. The most significant change is in increasing. CPU usage changed by 0.1%, memory by 0.0%, disk by 0.0%, network by 0.0 GB, and process count by 0.

## Package Structure

``nhealth_monitor/
├── __init__.py
├── collector.py       # Raw data collection functions
├── reporter.py        # Formatting and summarization functions
├── monitor.py         # Main CLI entry point with args parsing
├── reports/
│   ├── __init__.py
│   ├── report_*.txt   # Human-readable reports
│   └── history.jsonl  # Append-only history of full stats
├── test_collector.py  # Unit tests for collectors
├── DESIGN.md          # Design decisions
├── README.md          # This file
├── requirements.txt   # Dependencies
└── BENCHMARK_RESULTS.md # Performance analysis
```

## Requirements

```bash
psutil>=5.9.0
```

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

## License

[MIT](LICENSE)
