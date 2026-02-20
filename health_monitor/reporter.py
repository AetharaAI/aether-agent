"""
System Health Monitor - Reporter Module

Formats and summarizes system health reports.
"""

import json
from datetime import datetime
from typing import Dict, List, Any, Optional


def format_report(stats_dict: Dict[str, Any]) -> Dict[str, str]:
    """
    Formats system stats into both human-readable text and JSON.
    
    Args:
        stats_dict: Dict containing keys: cpu, memory, disk, network, processes
    
    Returns:
        Dict with 'text' and 'json' keys
    """
    
    # Extract stats
    cpu = stats_dict['cpu']
    memory = stats_dict['memory']
    disk = stats_dict['disk']
    network = stats_dict['network']
    processes = stats_dict['processes']
    
    # Format human-readable text
    text_lines = []
    text_lines.append("="*60)
    text_lines.append("SYSTEM HEALTH REPORT")
    text_lines.append("="*60)
    text_lines.append(f"Timestamp: {datetime.fromtimestamp(cpu['timestamp']).strftime('%Y-%m-%d %H:%M:%S')}")
    text_lines.append("")
    
    # CPU
    text_lines.append("CPU USAGE:")
    if isinstance(cpu['percent'], list):
        for i, p in enumerate(cpu['percent']):
            text_lines.append(f"  Core {i}: {p:.1f}%")
    else:
        text_lines.append(f"  Overall: {cpu['percent']:.1f}%")
    if cpu['frequency_mhz']:
        text_lines.append(f"  Frequency: {cpu['frequency_mhz']:.0f} MHz")
    text_lines.append("")
    
    # Memory
    text_lines.append("MEMORY USAGE:")
    text_lines.append(f"  Total: {memory['total'] / 1024**3:.1f} GB")
    text_lines.append(f"  Used: {memory['used'] / 1024**3:.1f} GB ({memory['percent']:.1f}%)")
    text_lines.append(f"  Available: {memory['available'] / 1024**3:.1f} GB")
    text_lines.append(f"  Free: {memory['free'] / 1024**3:.1f} GB")
    text_lines.append("")
    
    # Swap
    text_lines.append("SWAP USAGE:")
    text_lines.append(f"  Total: {memory['swap_total'] / 1024**3:.1f} GB")
    text_lines.append(f"  Used: {memory['swap_used'] / 1024**3:.1f} GB ({memory['swap_percent']:.1f}%)")
    text_lines.append(f"  Free: {memory['swap_free'] / 1024**3:.1f} GB")
    text_lines.append("")
    
    # Disk
    text_lines.append("DISK USAGE:")
    for d in disk:
        text_lines.append(f"  {d['mountpoint']}: {d['used'] / 1024**3:.1f}/{d['total'] / 1024**3:.1f} GB ({d['percent']:.1f}%)")
    text_lines.append("")
    
    # Network
    text_lines.append("NETWORK I/O:")
    text_lines.append(f"  Sent: {network['bytes_sent'] / 1024**2:.1f} MB")
    text_lines.append(f"  Received: {network['bytes_recv'] / 1024**2:.1f} MB")
    text_lines.append(f"  Packets Sent: {network['packets_sent']:,}")
    text_lines.append(f"  Packets Recv: {network['packets_recv']:,}")
    text_lines.append("")
    
    # Top Processes
    text_lines.append(f"TOP {len(processes)} PROCESSES:")
    text_lines.append(f"  {'PID':<8} {'CPU%':<6} {'MEM%':<6} {'NAME'}")
    text_lines.append("  " + "-"*50)
    for p in processes:
        name = p['name'][:20] if len(p['name']) > 20 else p['name']
        text_lines.append(f"  {p['pid']:<8} {p['cpu_percent']:<6.1f} {p['memory_percent']:<6.1f} {name}")
    text_lines.append("")
    text_lines.append("="*60)
    
    # Format JSON
    json_data = {
        "timestamp": cpu['timestamp'],
        "cpu": {
            "percent": cpu['percent'],
            "count": cpu['count'],
            "frequency_mhz": cpu['frequency_mhz'],
            "user": cpu['user'],
            "system": cpu['system'],
            "idle": cpu['idle']
        },
        "memory": {
            "total": memory['total'],
            "available": memory['available'],
            "percent": memory['percent'],
            "used": memory['used'],
            "free": memory['free'],
            "swap_total": memory['swap_total'],
            "swap_used": memory['swap_used'],
            "swap_free": memory['swap_free'],
            "swap_percent": memory['swap_percent']
        },
        "disk": disk,
        "network": {
            "bytes_sent": network['bytes_sent'],
            "bytes_recv": network['bytes_recv'],
            "packets_sent": network['packets_sent'],
            "packets_recv": network['packets_recv'],
            "errin": network['errin'],
            "errout": network['errout'],
            "dropin": network['dropin'],
            "dropout": network['dropout']
        },
        "processes": processes
    }
    
    return {
        "text": "\n".join(text_lines),
        "json": json.dumps(json_data, indent=2)
    }


def write_report(report_str: str, path: str) -> bool:
    """
    Writes a report string to a file.
    
    Args:
        report_str: The content to write
        path: Path to write the file to
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(report_str)
        return True
    except Exception as e:
        print(f"Error writing report to {path}: {e}")
        return False


def summarize_trend(history_list: List[Dict]) -> str:
    """
    Summarizes trends from a list of past reports.
    
    Args:
        history_list: List of full report dictionaries (from history.jsonl)
    
    Returns:
        str: One paragraph summary of trends
    """
    if not history_list:
        return "No historical data available for trend analysis."
    
    # Sort by timestamp
    history_list.sort(key=lambda x: x['timestamp'])
    
    first = history_list[0]
    last = history_list[-1]
    
    # CPU trend
    first_cpu = first['cpu']['percent'] if isinstance(first['cpu']['percent'], list) else [first['cpu']['percent']]
    last_cpu = last['cpu']['percent'] if isinstance(last['cpu']['percent'], list) else [last['cpu']['percent']]
    
    avg_first_cpu = sum(first_cpu) / len(first_cpu)
    avg_last_cpu = sum(last_cpu) / len(last_cpu)
    
    cpu_change = avg_last_cpu - avg_first_cpu
    cpu_trend = "increasing" if cpu_change > 0.5 else "decreasing" if cpu_change < -0.5 else "stable"
    
    # Memory trend
    first_mem = first['memory']['percent']
    last_mem = last['memory']['percent']
    mem_change = last_mem - first_mem
    mem_trend = "increasing" if mem_change > 2 else "decreasing" if mem_change < -2 else "stable"
    
    # Disk trend (use the most used disk)
    first_disk_max = max(d['percent'] for d in first['disk'])
    last_disk_max = max(d['percent'] for d in last['disk'])
    disk_change = last_disk_max - first_disk_max
    disk_trend = "increasing" if disk_change > 5 else "decreasing" if disk_change < -5 else "stable"
    
    # Network trend
    first_net = first['network']['bytes_sent'] + first['network']['bytes_recv']
    last_net = last['network']['bytes_sent'] + last['network']['bytes_recv']
    net_change = last_net - first_net
    net_trend = "increasing" if net_change > 100000000 else "decreasing" if net_change < -100000000 else "stable"
    
    # Process trend
    first_procs = len(first['processes'])
    last_procs = len(last['processes'])
    proc_change = last_procs - first_procs
    proc_trend = "increasing" if proc_change > 2 else "decreasing" if proc_change < -2 else "stable"
    
    return (
        f"Over the observed period, system health shows {cpu_trend} CPU usage, {mem_trend} memory utilization, "
        f"{disk_trend} disk pressure, {net_trend} network traffic, and {proc_trend} process count. "
        f"The most significant change is in {max([cpu_trend, mem_trend, disk_trend, net_trend, proc_trend], key=lambda x: abs({'increasing': 1, 'decreasing': -1, 'stable': 0}[x]))}. "
        f"CPU usage changed by {cpu_change:.1f}%, memory by {mem_change:.1f}%, disk by {disk_change:.1f}%, "
        f"network by {net_change/1024**3:.1f} GB, and process count by {proc_change}."
    )