# System Health Monitor - Implementation Checklist

## Phase 1: Setup
- [x] Created health_monitor/ directory
- [x] Created reports/ subdirectory
- [x] Wrote DESIGN.md
- [x] Created SESSION_START.txt

## Phase 2: Core Implementation
- [ ] Create health_monitor/collector.py
- [ ] Create health_monitor/reporter.py
- [ ] Create health_monitor/monitor.py
- [ ] Implement get_cpu_stats() in collector.py
- [ ] Implement get_memory_stats() in collector.py
- [ ] Implement get_disk_stats() in collector.py
- [ ] Implement get_network_stats() in collector.py
- [ ] Implement get_top_processes(n=10) in collector.py
- [ ] Implement format_report(stats_dict) in reporter.py
- [ ] Implement write_report(report_str, path) in reporter.py
- [ ] Implement summarize_trend(history_list) in reporter.py
- [ ] Implement main() in monitor.py with --interval and --count flags
- [ ] Ensure monitor.py appends to reports/history.jsonl

## Phase 3: Testing
- [ ] Run: python health_monitor/monitor.py --interval 2 --count 5
- [ ] Verify 5 report files created in reports/
- [ ] Read one report and validate all fields
- [ ] Create test_collector.py
- [ ] Run test_collector.py and fix failures

## Phase 4: Memory Recall
- [ ] Write RECALL_TEST.md with answers to 4 questions

## Phase 5: Documentation & Wrap-up
- [ ] Write README.md
- [ ] Write BENCHMARK_RESULTS.md
- [ ] Create requirements.txt
- [ ] Add __init__.py files to make package importable

## Final
- [ ] Confirm all phases complete
- [ ] Output MARATHON COMPLETE message
