"""Shared types for eval scenarios and the runner."""

from dataclasses import dataclass
from typing import Any

# What agent.ainvoke() returns — the graph's final (or interrupted) state.
RunResult = dict[str, Any]


@dataclass(frozen=True, slots=True)
class EvalResult:
    passed: bool
    reason: str
