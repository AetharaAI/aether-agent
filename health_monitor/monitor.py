"""
System Health Monitor - Main Entry Point

CLI tool that collects system stats at intervals and writes reports.
"""

import sys
import os
import json
import time
import argparse
from datetime import datetime
from typing import Dict, Any

# Import local modules
from collector import get_cpu_stats, get_memory_stats, get_disk_stats, get_network_stats, get_top_processes
from reporter import format_report, write_report, summarize_trend


def main():
    parser = argparse.ArgumentParser(description='System Health Monitor')
    parser.add_argument('--interval', type=int, default=5, help='Collection interval in seconds (default: 5)')
    parser.add_argument('--count', type=int, default=1, help='Number of collections to perform (default: 1)')
    parser.add_argument('--no-history', action='store_true', help='Do not append to history.jsonl')
    args = parser.parse_args()
    
    # Ensure reports directory exists
    reports_dir = os.path.join(os.path.dirname(__file__), 'reports')
    os.makedirs(reports_dir, exist_ok=True)
    
    # Initialize history file
    history_path = os.path.join(reports_dir, 'history.jsonl')
    if not os.path.exists(history_path):
        open(history_path, 'w').close()
    
    collected = 0
    history_data = []
    
    while collected < args.count:
        try:
            # Collect stats
            stats = {
                'cpu': get_cpu_stats(),
                'memory': get_memory_stats(),
                'disk': get_disk_stats(),
                'network': get_network_stats(),
                'processes': get_top_processes(n=10)
            }
            
            # Format report
            formatted = format_report(stats)
            
            # Write human-readable report
            timestamp_str = datetime.fromtimestamp(stats['cpu']['timestamp']).strftime('%Y%m%dT%H%M%S')
            report_path = os.path.join(reports_dir, f'report_{timestamp_str}.txt')
            if write_report(formatted['text'], report_path):
                print(f"Report written: {report_path}")
            else:
                print(f"Error writing report: {report_path}")
            
            # Append to history.jsonl if not disabled
            if not args.no_history:
                with open(history_path, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(stats) + '\n')
                history_data.append(stats)
            
            collected += 1
            
            # Wait for next interval if not last iteration
            if collected < args.count:
                time.sleep(args.interval)
                
        except KeyboardInterrupt:
            print("\nInterrupted by user. Exiting.")
            break
        except Exception as e:
            print(f"Error during collection {collected + 1}: {e}")
            if collected < args.count:
                time.sleep(args.interval)
    
    # If we collected at least 2 reports, generate a trend summary
    if len(history_data) >= 2:
        trend_summary = summarize_trend(history_data)
        summary_path = os.path.join(reports_dir, f'trend_summary_{datetime.now().strftime("%Y%m%dT%H%M%S")}.txt')
        with open(summary_path, 'w', encoding='utf-8') as f:
            f.write(trend_summary + '\n')
        print(f"Trend summary written: {summary_path}")

if __name__ == '__main__':
    main()