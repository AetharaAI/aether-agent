"""
Agent Ledger — Persistent document storage for AetherOS agents.

MongoDB-backed notebook system. Redis holds lightweight refs,
MongoDB holds full content. Agents interact via 6 tools:
  ledger_create, ledger_read, ledger_update,
  ledger_search, ledger_list, ledger_delete
"""

from .connection import LedgerDB
from .tool import (
    ledger_create_tool,
    ledger_read_tool,
    ledger_update_tool,
    ledger_search_tool,
    ledger_list_tool,
    ledger_delete_tool,
)

__all__ = [
    "LedgerDB",
    "ledger_create_tool",
    "ledger_read_tool",
    "ledger_update_tool",
    "ledger_search_tool",
    "ledger_list_tool",
    "ledger_delete_tool",
]
