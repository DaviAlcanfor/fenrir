"""Shared mutable state for the API process: the built agent, its build
error (if any), and the SQLite connection for conversation history."""

from typing import Any

RECURSION_LIMIT = 100

state: dict[str, Any] = {"agent": None, "error": None, "db": None}
