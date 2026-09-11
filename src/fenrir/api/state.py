"""Shared mutable state for the API process: the built agent, its build
error (if any), and the SQLite connection for conversation history."""

from dataclasses import dataclass
from typing import Final

import aiosqlite

from fenrir.agents import FenrirAgent

RECURSION_LIMIT: Final = 100


@dataclass(slots=True)
class ApiState:
    """Set once during `lifespan` startup, read on every request. Not frozen —
    `agent`/`error`/`db` only exist after the app has started."""

    agent: FenrirAgent | None = None
    error: str | None = None
    db: aiosqlite.Connection | None = None

    def require_db(self) -> aiosqlite.Connection:
        """The db connection, narrowed to non-None. Safe any time after
        lifespan startup — which is always, for a route handler."""
        assert self.db is not None, "db not initialized — lifespan hasn't started yet"
        return self.db


state = ApiState()
