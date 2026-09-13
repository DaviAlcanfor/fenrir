"""Custom tools not covered by HexStrike. Injected into every agent."""

import re
from pathlib import Path
from typing import Final
from urllib.parse import urlsplit

from langchain_core.tools import BaseTool, tool

from fenrir.config import ENGAGEMENT_DIR
from fenrir.policy.scope import ScopePolicy, host_matches

__all__ = ["TOOLS", "in_scope", "load_scope", "load_paths", "load_policy"]

SCOPE_FILE: Final[Path] = ENGAGEMENT_DIR / "scope.md"
_TOKEN: Final[re.Pattern[str]] = re.compile(
    r"(?:\*\.)?[a-z0-9.-]+\.[a-z]{2,}|\d{1,3}(?:\.\d{1,3}){3}(?:/\d{1,2})?", re.I
)
_PATHS_LINE: Final[re.Pattern[str]] = re.compile(r"paths\s*:\s*(.+)", re.I)

_matches = host_matches  # backward-compat alias — canonical impl lives in fenrir.policy.scope


def load_scope(path: Path = SCOPE_FILE) -> tuple[list[str], list[str]]:
    """Parse scope.md into (in_scope_tokens, out_of_scope_tokens)."""

    if not path.is_file():
        return [], []

    allow: list[str] = []
    deny: list[str] = []
    current: list[str] | None = None

    for line in path.read_text(encoding="utf-8").splitlines():
        low = line.strip().lower()

        if low.startswith("#"):
            current = allow if "in scope" in low else deny if "out of scope" in low else None
        elif current is not None:
            current += [m.group(0).lower() for m in _TOKEN.finditer(line)]

    return allow, deny


def load_paths(path: Path = SCOPE_FILE) -> tuple[str, ...]:
    """Parse "Paths: /a/*, /b/*" lines from scope.md. Defaults to ("*",) — any path."""

    if not path.is_file():
        return ("*",)

    prefixes: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        match = _PATHS_LINE.search(line)
        if match:
            prefixes += [p.strip() for p in match.group(1).split(",") if p.strip()]

    return tuple(prefixes) or ("*",)


def load_policy(path: Path = SCOPE_FILE) -> ScopePolicy | None:
    """Build the typed ScopePolicy from scope.md, or None if there is no scope.md."""

    allow, deny = load_scope(path)
    if not allow and not deny:
        return None

    return ScopePolicy.from_scope_tokens(allow, deny, load_paths(path))


def _host(target: str) -> str:
    """Bare hostname from a URL, host:port, or plain host."""
    return (urlsplit(target if "//" in target else f"//{target}").hostname or target).lower()


def _as_url(target: str) -> str:
    """Ensure target has a scheme so ScopePolicy.check can parse host/port/path."""
    return target if "://" in target else f"https://{target}"


@tool
def in_scope(target: str) -> str:
    """Check a host, domain, or URL against scope.md before acting on it.

    Call before any recon or testing. Returns one of: "IN SCOPE",
    "OUT OF SCOPE (excluded)", "OUT OF SCOPE (not listed)", "NO scope.md".
    """
    policy = load_policy()

    if policy is None:
        return "NO scope.md — refuse and ask the operator to define scope."

    decision = policy.check(_as_url(target))
    host = _host(target)

    return f"IN SCOPE: {host}" if decision.allowed else f"OUT OF SCOPE: {decision.reason}"


# ponytail: path prefixes from scope.md apply to every allowed host uniformly
# (scope.md has no per-host path syntax today) — upgrade to per-host paths if
# an engagement ever needs different path rules for different in-scope hosts.
TOOLS: Final[list[BaseTool]] = [in_scope]
