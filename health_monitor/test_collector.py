"""
Unit tests for collector.py functions.
"""

import sys
import os
import unittest
from typing import Dict, List

# Add parent directory to path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from health_monitor.collector import (
    get_cpu_stats, 
    get_memory_stats, 
    get_disk_stats, 
    get_network_stats, 
    get_top_processes
)


class TestCollector(unittest.TestCase):
    
    def test_get_cpu_stats(self):
        """Test that get_cpu_stats returns expected structure"""
        stats = get_cpu_stats()
        self.assertIn("timestamp", stats)
        self.assertIsInstance(stats["timestamp"], float)
        self.assertIn("percent", stats)
        self.assertIsInstance(stats["percent"], list)
        self.assertTrue(len(stats["percent"]) > 0)
        self.assertIn("count", stats)
        self.assertIsInstance(stats["count"], int)
        self.assertIn("frequency_mhz", stats)
        self.assertTrue(isinstance(stats["frequency_mhz"], (float, type(None))))
        self.assertIn("user", stats)
        self.assertIn("system", stats)
        self.assertIn("idle", stats)
        
    def test_get_memory_stats(self):
        """Test that get_memory_stats returns expected structure"""
        stats = get_memory_stats()
        self.assertIn("timestamp", stats)
        self.assertIsInstance(stats["timestamp"], float)
        
        for key in ["total", "available", "percent", "used", "free", 
                   "swap_total", "swap_used", "swap_free", "swap_percent"]:
            self.assertIn(key, stats)
            self.assertIsInstance(stats[key], (int, float))
            
    def test_get_disk_stats(self):
        """Test that get_disk_stats returns a list of dicts with expected keys"""
        stats = get_disk_stats()
        self.assertIsInstance(stats, list)
        for disk in stats:
            self.assertIn("timestamp", disk)
            self.assertIsInstance(disk["timestamp"], float)
            
            for key in ["device", "mountpoint", "fstype", "total", "used", "free", "percent"]:
                self.assertIn(key, disk)
                
            self.assertIsInstance(disk["total"], (int, float))
            self.assertIsInstance(disk["used"], (int, float))
            self.assertIsInstance(disk["free"], (int, float))
            self.assertIsInstance(disk["percent"], float)
            
    def test_get_network_stats(self):
        """Test that get_network_stats returns expected structure"""
        stats = get_network_stats()
        self.assertIn("timestamp", stats)
        self.assertIsInstance(stats["timestamp"], float)
        
        for key in ["bytes_sent", "bytes_recv", "packets_sent", "packets_recv", 
                   "errin", "errout", "dropin", "dropout"]:
            self.assertIn(key, stats)
            self.assertIsInstance(stats[key], int)
            
    def test_get_top_processes(self):
        """Test that get_top_processes returns list of dicts with expected keys"""
        processes = get_top_processes(n=5)
        self.assertIsInstance(processes, list)
        self.assertLessEqual(len(processes), 5)
        
        for proc in processes:
            self.assertIn("timestamp", proc)
            self.assertIsInstance(proc["timestamp"], float)
            
            for key in ["pid", "name", "cpu_percent", "memory_percent", "cmdline"]:
                self.assertIn(key, proc)
                
            self.assertIsInstance(proc["pid"], int)
            self.assertIsInstance(proc["name"], str)
            self.assertIsInstance(proc["cpu_percent"], float)
            self.assertIsInstance(proc["memory_percent"], float)
            self.assertIsInstance(proc["cmdline"], str)
            
if __name__ == '__main__':
    unittest.main()