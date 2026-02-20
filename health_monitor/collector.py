"""
System Health Monitor - Collector Module

Collects raw system statistics using psutil (fallback to /proc on Linux if unavailable).
"""

import sys
import time
import os
from typing import Dict, List, Optional

# Try to import psutil, fallback to manual parsing on Linux
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    if sys.platform != "linux":
        raise ImportError("psutil is required on non-Linux systems")


def get_cpu_stats() -> Dict:
    """Returns CPU usage statistics."""
    timestamp = time.time()
    if PSUTIL_AVAILABLE:
        cpu_percent = psutil.cpu_percent(interval=None, percpu=True)
        cpu_count = psutil.cpu_count()
        cpu_freq = psutil.cpu_freq()
        freq_mhz = cpu_freq.current if cpu_freq else None
        return {
            "timestamp": timestamp,
            "percent": cpu_percent,
            "count": cpu_count,
            "frequency_mhz": freq_mhz,
            "user": psutil.cpu_times().user if psutil.cpu_times() else None,
            "system": psutil.cpu_times().system if psutil.cpu_times() else None,
            "idle": psutil.cpu_times().idle if psutil.cpu_times() else None
        }
    else:
        # Fallback: parse /proc/stat on Linux
        with open('/proc/stat', 'r') as f:
            lines = f.readlines()
        cpu_line = [line for line in lines if line.startswith('cpu ')][0]
        parts = cpu_line.split()
        user, nice, system, idle = map(int, [parts[1], parts[2], parts[3], parts[4]])
        total = user + nice + system + idle
        percent = (100 * (total - idle)) / total if total > 0 else 0
        return {
            "timestamp": timestamp,
            "percent": [percent],  # Single value for fallback
            "count": 1,
            "frequency_mhz": None,
            "user": user,
            "system": system,
            "idle": idle
        }


def get_memory_stats() -> Dict:
    """Returns memory and swap usage statistics."""
    timestamp = time.time()
    if PSUTIL_AVAILABLE:
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()
        return {
            "timestamp": timestamp,
            "total": mem.total,
            "available": mem.available,
            "percent": mem.percent,
            "used": mem.used,
            "free": mem.free,
            "swap_total": swap.total,
            "swap_used": swap.used,
            "swap_free": swap.free,
            "swap_percent": swap.percent
        }
    else:
        # Fallback: parse /proc/meminfo
        meminfo = {}
        with open('/proc/meminfo', 'r') as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 2:
                    key = parts[0].rstrip(':')
                    meminfo[key] = int(parts[1]) * 1024  # Convert KB to bytes
        total = meminfo.get('MemTotal', 0)
        free = meminfo.get('MemFree', 0)
        buffers = meminfo.get('Buffers', 0)
        cached = meminfo.get('Cached', 0)
        available = free + buffers + cached
        used = total - available
        percent = (used / total * 100) if total > 0 else 0
        
        swap_total = meminfo.get('SwapTotal', 0)
        swap_free = meminfo.get('SwapFree', 0)
        swap_used = swap_total - swap_free
        swap_percent = (swap_used / swap_total * 100) if swap_total > 0 else 0
        
        return {
            "timestamp": timestamp,
            "total": total,
            "available": available,
            "percent": percent,
            "used": used,
            "free": free,
            "swap_total": swap_total,
            "swap_used": swap_used,
            "swap_free": swap_free,
            "swap_percent": swap_percent
        }


def get_disk_stats() -> List[Dict]:
    """Returns disk usage for all mounted filesystems."""
    timestamp = time.time()
    if PSUTIL_AVAILABLE:
        partitions = psutil.disk_partitions()
        result = []
        for partition in partitions:
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                result.append({
                    "timestamp": timestamp,
                    "device": partition.device,
                    "mountpoint": partition.mountpoint,
                    "fstype": partition.fstype,
                    "total": usage.total,
                    "used": usage.used,
                    "free": usage.free,
                    "percent": usage.percent
                })
            except PermissionError:
                continue  # Skip inaccessible mounts
        return result
    else:
        # Fallback: parse /proc/mounts and df output (simplified)
        # This is a minimal fallback and may not be as accurate
        result = []
        try:
            with open('/proc/mounts', 'r') as f:
                mounts = [line.split()[1] for line in f.readlines() if line.startswith('/')]  # Only real mounts
            for mount in mounts:
                try:
                    # Use os.statvfs for basic stats
                    stat = os.statvfs(mount)
                    total = stat.f_frsize * stat.f_blocks
                    free = stat.f_frsize * stat.f_bfree
                    used = total - free
                    percent = (used / total * 100) if total > 0 else 0
                    result.append({
                        "timestamp": timestamp,
                        "device": mount,
                        "mountpoint": mount,
                        "fstype": "unknown",
                        "total": total,
                        "used": used,
                        "free": free,
                        "percent": percent
                    })
                except OSError:
                    continue
        except FileNotFoundError:
            pass
        return result


def get_network_stats() -> Dict:
    """Returns network I/O statistics."""
    timestamp = time.time()
    if PSUTIL_AVAILABLE:
        net_io = psutil.net_io_counters()
        return {
            "timestamp": timestamp,
            "bytes_sent": net_io.bytes_sent,
            "bytes_recv": net_io.bytes_recv,
            "packets_sent": net_io.packets_sent,
            "packets_recv": net_io.packets_recv,
            "errin": net_io.errin,
            "errout": net_io.errout,
            "dropin": net_io.dropin,
            "dropout": net_io.dropout
        }
    else:
        # Fallback: parse /proc/net/dev
        result = {
            "timestamp": timestamp,
            "bytes_sent": 0,
            "bytes_recv": 0,
            "packets_sent": 0,
            "packets_recv": 0,
            "errin": 0,
            "errout": 0,
            "dropin": 0,
            "dropout": 0
        }
        try:
            with open('/proc/net/dev', 'r') as f:
                lines = f.readlines()[2:]  # Skip header
                for line in lines:
                    parts = line.split()
                    if len(parts) >= 17:
                        result["bytes_recv"] += int(parts[1])
                        result["bytes_sent"] += int(parts[9])
                        result["packets_recv"] += int(parts[2])
                        result["packets_sent"] += int(parts[10])
                        result["errin"] += int(parts[3])
                        result["errout"] += int(parts[11])
                        result["dropin"] += int(parts[4])
                        result["dropout"] += int(parts[12])
        except FileNotFoundError:
            pass
        return result


def get_top_processes(n: int = 10) -> List[Dict]:
    """Returns top N processes by CPU and memory usage."""
    timestamp = time.time()
    if PSUTIL_AVAILABLE:
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'cmdline']):
            try:
                info = proc.info
                if info['cpu_percent'] is None:
                    info['cpu_percent'] = 0.0
                if info['memory_percent'] is None:
                    info['memory_percent'] = 0.0
                processes.append({
                    "timestamp": timestamp,
                    "pid": info['pid'],
                    "name": info['name'] or "unknown",
                    "cpu_percent": info['cpu_percent'],
                    "memory_percent": info['memory_percent'],
                    "cmdline": " ".join(info['cmdline']) if info['cmdline'] else ""
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        
        # Sort by CPU then memory
        processes.sort(key=lambda x: (-x['cpu_percent'], -x['memory_percent']))
        return processes[:n]
    else:
        # Fallback: use ps command on Linux
        import subprocess
        try:
            output = subprocess.check_output(["ps", "aux", "--sort=-%cpu", "-o", "pid,comm,%cpu,%mem,cmd"], text=True)
            lines = output.strip().split('\n')[1:n+1]  # Skip header, take top n
            processes = []
            for line in lines:
                parts = line.split()
                if len(parts) >= 5:
                    pid = int(parts[0])
                    name = parts[1]
                    cpu = float(parts[2])
                    mem = float(parts[3])
                    cmdline = " ".join(parts[4:])
                    processes.append({
                        "timestamp": timestamp,
                        "pid": pid,
                        "name": name,
                        "cpu_percent": cpu,
                        "memory_percent": mem,
                        "cmdline": cmdline
                    })
            return processes
        except (subprocess.CalledProcessError, FileNotFoundError):
            return []