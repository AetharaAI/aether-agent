#!/usr/bin/env python3
"""
AetherOS Agent Benchmark Harness
=================================
Production-grade benchmarking system that evaluates agent execution capability
against a vLLM OpenAI-compatible endpoint.

Measures: tool call accuracy, argument correctness, retry/self-healing,
end-to-end success, latency, throughput, and multi-step reliability.

Usage:
    python agent_benchmark.py
    python agent_benchmark.py --num-tests 50 --concurrency 4
    python agent_benchmark.py --endpoint http://localhost:8001/v1/chat/completions
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import re
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_MODEL = "qwen3-next-instruct"
DEFAULT_ENDPOINT = "https://api.blackboxaudio.tech/v1/chat/completions"
DEFAULT_API_KEY = os.getenv("LITELLM_API_KEY", "sk-aether-master-pro")
DEFAULT_NUM_TESTS = 100
DEFAULT_CONCURRENCY = 1
MAX_TOOL_ROUNDS = 5

LOG_FORMAT = "%(asctime)s │ %(levelname)-7s │ %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger("aether.benchmark")


# ─────────────────────────────────────────────────────────────────────────────
# Data Models
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class BenchmarkTask:
    """A single benchmark task definition."""
    id: str
    category: str
    prompt: str
    expected_tools: List[str]
    max_rounds: int = 3
    should_recover: bool = False
    description: str = ""


@dataclass
class TaskResult:
    """Metrics captured for a single benchmark task execution."""
    task_id: str
    category: str
    success: bool = False
    tool_calls_count: int = 0
    tool_failures_count: int = 0
    retry_count: int = 0
    correct_tools_called: int = 0
    expected_tools_count: int = 0
    argument_accuracy: float = 0.0
    latency_ms: float = 0.0
    tokens_prompt: int = 0
    tokens_generated: int = 0
    tokens_per_second: float = 0.0
    total_execution_time_ms: float = 0.0
    rounds_used: int = 0
    error: str = ""
    tool_names_called: List[str] = field(default_factory=list)
    final_response: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# ToolSimulator — Mock tool registry for controlled, reproducible testing
# ─────────────────────────────────────────────────────────────────────────────

class ToolSimulator:
    """
    Simulates tool execution with deterministic results.
    Supports configurable failure injection for testing retry behaviour.
    """

    # OpenAI-compatible tool schemas exposed to the LLM
    TOOL_SCHEMAS: List[Dict[str, Any]] = [
        {
            "type": "function",
            "function": {
                "name": "web_search",
                "description": "Search the web for current information. Returns search results.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query string."
                        }
                    },
                    "required": ["query"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "file_read",
                "description": "Read the contents of a file at the given path.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Absolute or relative file path to read."
                        }
                    },
                    "required": ["path"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "file_write",
                "description": "Write content to a file at the given path.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "File path to write to."
                        },
                        "content": {
                            "type": "string",
                            "description": "The content to write."
                        }
                    },
                    "required": ["path", "content"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "file_list",
                "description": "List files and directories at the given path.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Directory path to list."
                        }
                    },
                    "required": ["path"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "terminal_exec",
                "description": "Execute a shell command and return stdout/stderr.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "The shell command to execute."
                        }
                    },
                    "required": ["command"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "calculate",
                "description": "Evaluate a mathematical expression.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "expression": {
                            "type": "string",
                            "description": "Mathematical expression to evaluate."
                        }
                    },
                    "required": ["expression"]
                }
            }
        },
    ]

    # Deterministic mock results per tool
    MOCK_RESULTS: Dict[str, Any] = {
        "web_search": {
            "success": True,
            "results": [
                {"title": "Benchmark result 1", "url": "https://example.com/1", "snippet": "Relevant search result content."},
                {"title": "Benchmark result 2", "url": "https://example.com/2", "snippet": "Additional relevant information."},
            ]
        },
        "file_read": {
            "success": True,
            "content": "# Sample File\n\nThis is the contents of the requested file.\nLine 2 of the file.\nLine 3 with important data: value=42\n"
        },
        "file_write": {
            "success": True,
            "bytes_written": 256,
            "message": "File written successfully."
        },
        "file_list": {
            "success": True,
            "entries": [
                {"name": "README.md", "type": "file", "size": 1024},
                {"name": "src", "type": "directory"},
                {"name": "config.yaml", "type": "file", "size": 512},
            ]
        },
        "terminal_exec": {
            "success": True,
            "stdout": "total 32\ndrwxr-xr-x  5 user user 4096 Jan  1 00:00 .\n-rw-r--r--  1 user user  256 Jan  1 00:00 file.txt\n",
            "stderr": "",
            "exit_code": 0
        },
        "calculate": {
            "success": True,
            "result": 42,
            "expression_evaluated": "6 * 7"
        }
    }

    def __init__(self):
        self._call_count: Dict[str, int] = {}
        self._failure_tasks: set = set()

    def register_failure_task(self, task_id: str):
        """Mark a task as one where the first tool call should fail."""
        self._failure_tasks.add(task_id)

    def execute(self, tool_name: str, arguments: Dict[str, Any], task_id: str = "") -> Dict[str, Any]:
        """Execute a mock tool, potentially injecting failure."""
        call_key = f"{task_id}:{tool_name}"
        self._call_count[call_key] = self._call_count.get(call_key, 0) + 1

        # Inject failure on first call for failure-recovery tasks
        if task_id in self._failure_tasks and self._call_count[call_key] == 1:
            return {
                "success": False,
                "error": f"[SIMULATED_FAILURE] {tool_name} temporarily unavailable. Please retry.",
            }

        result = self.MOCK_RESULTS.get(tool_name)
        if result is None:
            return {"success": False, "error": f"Unknown tool: {tool_name}"}

        return result

    def validate_arguments(self, tool_name: str, arguments: Dict[str, Any]) -> Tuple[bool, str]:
        """Check that required arguments are present and non-empty."""
        schema = next(
            (t["function"]["parameters"] for t in self.TOOL_SCHEMAS if t["function"]["name"] == tool_name),
            None
        )
        if schema is None:
            return False, f"No schema found for tool: {tool_name}"

        required = schema.get("required", [])
        for param in required:
            if param not in arguments or not str(arguments[param]).strip():
                return False, f"Missing or empty required argument: {param}"

        return True, ""


# ─────────────────────────────────────────────────────────────────────────────
# MetricsCollector — Accumulates per-task and aggregate metrics
# ─────────────────────────────────────────────────────────────────────────────

class MetricsCollector:
    """Thread-safe metrics accumulator."""

    def __init__(self):
        self.results: List[TaskResult] = []

    def record(self, result: TaskResult):
        self.results.append(result)

    def summary(self) -> Dict[str, Any]:
        """Compute aggregate statistics across all recorded results."""
        if not self.results:
            return {}

        total = len(self.results)
        successes = sum(1 for r in self.results if r.success)
        total_latency = sum(r.latency_ms for r in self.results)
        total_exec = sum(r.total_execution_time_ms for r in self.results)
        total_tool_calls = sum(r.tool_calls_count for r in self.results)
        total_tool_failures = sum(r.tool_failures_count for r in self.results)
        total_retries = sum(r.retry_count for r in self.results)
        total_prompt_tokens = sum(r.tokens_prompt for r in self.results)
        total_gen_tokens = sum(r.tokens_generated for r in self.results)
        total_correct = sum(r.correct_tools_called for r in self.results)
        total_expected = sum(r.expected_tools_count for r in self.results)

        # Per-category breakdown
        categories: Dict[str, Dict[str, Any]] = {}
        for r in self.results:
            cat = r.category
            if cat not in categories:
                categories[cat] = {"total": 0, "successes": 0, "latency_ms": 0.0}
            categories[cat]["total"] += 1
            categories[cat]["successes"] += 1 if r.success else 0
            categories[cat]["latency_ms"] += r.latency_ms

        for cat, stats in categories.items():
            stats["success_rate"] = round(stats["successes"] / stats["total"] * 100, 1)
            stats["avg_latency_ms"] = round(stats["latency_ms"] / stats["total"], 1)

        tps_values = [r.tokens_per_second for r in self.results if r.tokens_per_second > 0]

        return {
            "total_tasks": total,
            "successful_tasks": successes,
            "failed_tasks": total - successes,
            "success_rate_pct": round(successes / total * 100, 2),
            "total_tool_calls": total_tool_calls,
            "total_tool_failures": total_tool_failures,
            "total_retries": total_retries,
            "tool_call_accuracy_pct": round(total_correct / total_expected * 100, 2) if total_expected > 0 else 0,
            "avg_latency_ms": round(total_latency / total, 1),
            "avg_execution_time_ms": round(total_exec / total, 1),
            "p50_latency_ms": round(sorted(r.latency_ms for r in self.results)[total // 2], 1),
            "p95_latency_ms": round(sorted(r.latency_ms for r in self.results)[int(total * 0.95)], 1),
            "p99_latency_ms": round(sorted(r.latency_ms for r in self.results)[min(int(total * 0.99), total - 1)], 1),
            "total_prompt_tokens": total_prompt_tokens,
            "total_generated_tokens": total_gen_tokens,
            "avg_tokens_per_second": round(sum(tps_values) / len(tps_values), 1) if tps_values else 0,
            "category_breakdown": categories,
        }


# ─────────────────────────────────────────────────────────────────────────────
# ResultReporter — Outputs results to JSON, CSV, and console
# ─────────────────────────────────────────────────────────────────────────────

class ResultReporter:
    """Writes benchmark results to files and prints real-time console output."""

    DIVIDER = "─" * 80
    HEADER = """
╔══════════════════════════════════════════════════════════════════════════════╗
║              AetherOS Agent Benchmark Harness v1.0                         ║
║              Production-Grade Execution Capability Evaluator               ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

    def __init__(self, output_dir: str = "."):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def print_header(self, model: str, endpoint: str, num_tests: int, concurrency: int):
        print(self.HEADER)
        print(f"  Model:       {model}")
        print(f"  Endpoint:    {endpoint}")
        print(f"  Tasks:       {num_tests}")
        print(f"  Concurrency: {concurrency}")
        print(f"  Time:        {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(self.DIVIDER)
        print()

    def print_task_result(self, idx: int, total: int, result: TaskResult):
        status = "✅" if result.success else "❌"
        tools_str = ", ".join(result.tool_names_called) if result.tool_names_called else "none"
        retry_str = f" (retries: {result.retry_count})" if result.retry_count > 0 else ""

        print(
            f"  [{idx:>3}/{total}] {status}  {result.task_id:<40} "
            f"│ {result.latency_ms:>7.0f}ms │ tools: {result.tool_calls_count} │ "
            f"tps: {result.tokens_per_second:>6.1f}{retry_str}"
        )

    def print_summary(self, summary: Dict[str, Any]):
        print()
        print(self.DIVIDER)
        print("  BENCHMARK SUMMARY")
        print(self.DIVIDER)
        print()
        print(f"  Total Tasks:          {summary.get('total_tasks', 0)}")
        print(f"  ✅ Successful:         {summary.get('successful_tasks', 0)}")
        print(f"  ❌ Failed:             {summary.get('failed_tasks', 0)}")
        print(f"  Success Rate:         {summary.get('success_rate_pct', 0)}%")
        print()
        print(f"  Tool Calls:           {summary.get('total_tool_calls', 0)}")
        print(f"  Tool Failures:        {summary.get('total_tool_failures', 0)}")
        print(f"  Retries:              {summary.get('total_retries', 0)}")
        print(f"  Tool Accuracy:        {summary.get('tool_call_accuracy_pct', 0)}%")
        print()
        print(f"  Avg Latency:          {summary.get('avg_latency_ms', 0)} ms")
        print(f"  P50 Latency:          {summary.get('p50_latency_ms', 0)} ms")
        print(f"  P95 Latency:          {summary.get('p95_latency_ms', 0)} ms")
        print(f"  P99 Latency:          {summary.get('p99_latency_ms', 0)} ms")
        print()
        print(f"  Prompt Tokens:        {summary.get('total_prompt_tokens', 0):,}")
        print(f"  Generated Tokens:     {summary.get('total_generated_tokens', 0):,}")
        print(f"  Avg Tok/s:            {summary.get('avg_tokens_per_second', 0)}")
        print()

        # Category breakdown
        categories = summary.get("category_breakdown", {})
        if categories:
            print("  Category Breakdown:")
            print(f"  {'Category':<25} {'Pass':>5} {'Total':>6} {'Rate':>7} {'Avg ms':>8}")
            print(f"  {'─' * 55}")
            for cat, stats in categories.items():
                print(
                    f"  {cat:<25} {stats['successes']:>5} {stats['total']:>6} "
                    f"{stats['success_rate']:>6.1f}% {stats['avg_latency_ms']:>7.1f}"
                )
        print()
        print(self.DIVIDER)

    def save_json(self, results: List[TaskResult], summary: Dict[str, Any]):
        path = self.output_dir / "benchmark_results.json"
        data = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "summary": summary,
            "results": [asdict(r) for r in results],
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)
        print(f"  📄 Results saved: {path}")

    def save_csv(self, summary: Dict[str, Any]):
        path = self.output_dir / "benchmark_summary.csv"
        flat: Dict[str, Any] = {}
        for k, v in summary.items():
            if isinstance(v, dict):
                for sk, sv in v.items():
                    if isinstance(sv, dict):
                        for ssk, ssv in sv.items():
                            flat[f"{k}.{sk}.{ssk}"] = ssv
                    else:
                        flat[f"{k}.{sk}"] = sv
            else:
                flat[k] = v

        with open(path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(flat.keys())
            writer.writerow(flat.values())
        print(f"  📊 Summary saved: {path}")


# ─────────────────────────────────────────────────────────────────────────────
# BenchmarkRunner — Core orchestration engine
# ─────────────────────────────────────────────────────────────────────────────

class BenchmarkRunner:
    """
    Orchestrates benchmark execution against a vLLM OpenAI-compatible endpoint.
    Supports sequential and concurrent test execution.
    """

    SYSTEM_PROMPT = (
        "You are a helpful AI assistant with access to tools. "
        "When a task requires using a tool, call the appropriate tool with correct arguments. "
        "After receiving tool results, provide a concise final answer. "
        "If a tool call fails, analyze the error and retry with corrected arguments."
    )

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        endpoint: str = DEFAULT_ENDPOINT,
        api_key: str = DEFAULT_API_KEY,
        tasks_file: str = "benchmark_tasks.json",
    ):
        self.model = model
        self.api_key = api_key
        self.endpoint = endpoint
        self.tool_sim = ToolSimulator()
        self.metrics = MetricsCollector()
        self.reporter = ResultReporter()
        self.tasks = self._load_tasks(tasks_file)

    def _load_tasks(self, path: str) -> List[BenchmarkTask]:
        """Load benchmark tasks from JSON file."""
        try:
            with open(path) as f:
                data = json.load(f)
            tasks = []
            for t in data.get("tasks", []):
                task = BenchmarkTask(
                    id=t["id"],
                    category=t["category"],
                    prompt=t["prompt"],
                    expected_tools=t.get("expected_tools", []),
                    max_rounds=t.get("max_rounds", 3),
                    should_recover=t.get("should_recover", False),
                    description=t.get("description", ""),
                )
                if task.should_recover:
                    self.tool_sim.register_failure_task(task.id)
                tasks.append(task)
            logger.info("Loaded %d benchmark tasks from %s", len(tasks), path)
            return tasks
        except FileNotFoundError:
            logger.error("Tasks file not found: %s", path)
            sys.exit(1)
        except json.JSONDecodeError as e:
            logger.error("Invalid JSON in tasks file: %s", e)
            sys.exit(1)

    def _call_llm(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Make a single call to the vLLM OpenAI-compatible endpoint."""
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": 2048,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            resp = requests.post(
                self.endpoint,
                json=payload,
                headers=headers,
                timeout=120,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException as e:
            return {"error": str(e)}

    def _extract_tool_calls(self, response: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract tool calls from an OpenAI-compatible response."""
        tool_calls = []
        choices = response.get("choices", [])
        if not choices:
            return tool_calls

        message = choices[0].get("message", {})
        raw_calls = message.get("tool_calls") or []

        for tc in raw_calls:
            func = tc.get("function", {})
            name = func.get("name", "")
            args_str = func.get("arguments", "{}")
            try:
                arguments = json.loads(args_str) if isinstance(args_str, str) else args_str
            except json.JSONDecodeError:
                arguments = {}

            tool_calls.append({
                "id": tc.get("id", f"call_{uuid.uuid4().hex[:8]}"),
                "name": name,
                "arguments": arguments,
            })

        return tool_calls

    def _get_usage(self, response: Dict[str, Any]) -> Tuple[int, int]:
        """Extract prompt and completion token counts."""
        usage = response.get("usage", {})
        return usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)

    def execute_task(self, task: BenchmarkTask) -> TaskResult:
        """Execute a single benchmark task with multi-round tool calling."""
        result = TaskResult(
            task_id=task.id,
            category=task.category,
            expected_tools_count=len(task.expected_tools),
        )

        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": task.prompt},
        ]

        tools_called: List[str] = []
        total_prompt_tokens = 0
        total_gen_tokens = 0
        rounds = 0
        tool_failures = 0

        start_time = time.perf_counter()

        for round_num in range(task.max_rounds):
            rounds += 1

            # Call the LLM
            llm_start = time.perf_counter()
            response = self._call_llm(messages, self.tool_sim.TOOL_SCHEMAS)
            llm_elapsed = (time.perf_counter() - llm_start) * 1000

            # Check for API errors
            if "error" in response and not response.get("choices"):
                result.error = str(response["error"])
                break

            # Accumulate tokens
            prompt_tok, gen_tok = self._get_usage(response)
            total_prompt_tokens += prompt_tok
            total_gen_tokens += gen_tok

            # Extract tool calls
            tool_calls = self._extract_tool_calls(response)

            # If no tool calls, the LLM has finished
            if not tool_calls:
                content = (response.get("choices", [{}])[0].get("message", {}).get("content", "") or "")
                result.final_response = content
                result.success = True
                break

            # Build assistant message with tool_calls for conversation history
            assistant_msg: Dict[str, Any] = {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": json.dumps(tc["arguments"]),
                        }
                    }
                    for tc in tool_calls
                ]
            }
            messages.append(assistant_msg)

            # Execute each tool call and append results
            for tc in tool_calls:
                tools_called.append(tc["name"])
                result.tool_calls_count += 1

                # Validate arguments
                valid, validation_err = self.tool_sim.validate_arguments(tc["name"], tc["arguments"])
                if not valid:
                    result.argument_accuracy = max(0, result.argument_accuracy - 0.25)

                # Execute the mock tool
                tool_result = self.tool_sim.execute(tc["name"], tc["arguments"], task.id)
                if not tool_result.get("success", False):
                    tool_failures += 1
                    result.retry_count += 1

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": json.dumps(tool_result),
                })

        end_time = time.perf_counter()
        total_elapsed_ms = (end_time - start_time) * 1000

        # Compute tool call accuracy (correct tools invoked)
        correct = len(set(task.expected_tools) & set(tools_called))
        result.correct_tools_called = correct

        # Argument accuracy: start at 1.0, penalise for validation failures
        if result.tool_calls_count > 0:
            result.argument_accuracy = max(0.0, 1.0 - (tool_failures * 0.25 / result.tool_calls_count))
        else:
            result.argument_accuracy = 0.0

        # Fill remaining metrics
        result.tool_failures_count = tool_failures
        result.latency_ms = round(total_elapsed_ms, 2)
        result.total_execution_time_ms = round(total_elapsed_ms, 2)
        result.tokens_prompt = total_prompt_tokens
        result.tokens_generated = total_gen_tokens
        result.rounds_used = rounds
        result.tool_names_called = tools_called

        # Tokens per second
        if total_elapsed_ms > 0 and total_gen_tokens > 0:
            result.tokens_per_second = round(total_gen_tokens / (total_elapsed_ms / 1000), 1)

        # Success conditions
        if task.should_recover:
            # For recovery tasks, success = eventually got a final response
            result.success = bool(result.final_response) and result.retry_count > 0
        elif not result.success:
            # If we ran out of rounds without a non-tool-call completion
            result.success = False

        return result

    def run(self, num_tests: int = DEFAULT_NUM_TESTS, concurrency: int = DEFAULT_CONCURRENCY):
        """Execute the full benchmark suite."""
        # Build task queue (cycle through available tasks)
        task_queue: List[BenchmarkTask] = []
        for i in range(num_tests):
            task_queue.append(self.tasks[i % len(self.tasks)])

        auth_display = "Bearer ***" if self.api_key else "none"
        self.reporter.print_header(self.model, f"{self.endpoint}  (auth: {auth_display})", num_tests, concurrency)

        if concurrency <= 1:
            self._run_sequential(task_queue)
        else:
            self._run_concurrent(task_queue, concurrency)

        # Report
        summary = self.metrics.summary()
        self.reporter.print_summary(summary)
        self.reporter.save_json(self.metrics.results, summary)
        self.reporter.save_csv(summary)

    def _run_sequential(self, tasks: List[BenchmarkTask]):
        total = len(tasks)
        for idx, task in enumerate(tasks, 1):
            result = self.execute_task(task)
            self.metrics.record(result)
            self.reporter.print_task_result(idx, total, result)

    def _run_concurrent(self, tasks: List[BenchmarkTask], concurrency: int):
        total = len(tasks)
        completed = 0

        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            future_to_idx = {
                executor.submit(self.execute_task, task): idx
                for idx, task in enumerate(tasks, 1)
            }
            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                completed += 1
                try:
                    result = future.result()
                    self.metrics.record(result)
                    self.reporter.print_task_result(completed, total, result)
                except Exception as e:
                    logger.error("Task %d failed with exception: %s", idx, e)
                    error_result = TaskResult(
                        task_id=f"error_{idx}",
                        category="error",
                        error=str(e),
                    )
                    self.metrics.record(error_result)


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────

def run_benchmark(
    model: str = DEFAULT_MODEL,
    endpoint: str = DEFAULT_ENDPOINT,
    api_key: str = DEFAULT_API_KEY,
    num_tests: int = DEFAULT_NUM_TESTS,
    concurrency: int = DEFAULT_CONCURRENCY,
    tasks_file: str = "benchmark_tasks.json",
):
    """Public entry point for running the benchmark programmatically."""
    runner = BenchmarkRunner(model=model, endpoint=endpoint, api_key=api_key, tasks_file=tasks_file)
    runner.run(num_tests=num_tests, concurrency=concurrency)


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="AetherOS Agent Benchmark Harness",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Model name (as registered in LiteLLM)")
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT, help="LiteLLM proxy endpoint URL")
    parser.add_argument("--api-key", default=DEFAULT_API_KEY, help="LiteLLM API key (or set LITELLM_API_KEY env var)")
    parser.add_argument("--num-tests", type=int, default=DEFAULT_NUM_TESTS, help="Number of benchmark tasks")
    parser.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY, help="Concurrent workers")
    parser.add_argument("--tasks-file", default="benchmark_tasks.json", help="Path to tasks JSON")
    args = parser.parse_args()

    run_benchmark(
        model=args.model,
        endpoint=args.endpoint,
        api_key=args.api_key,
        num_tests=args.num_tests,
        concurrency=args.concurrency,
        tasks_file=args.tasks_file,
    )


if __name__ == "__main__":
    main()
