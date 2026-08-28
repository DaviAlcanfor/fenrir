"""Custom tools not covered by HexStrike. Injected into every agent."""

import ipaddress
import re
from pathlib import Path
from urllib.parse import urlsplit

from langchain_core.tools import tool

from fenrir.config import ROOT

__all__ = ["TOOLS", "in_scope", "load_scope"]

SCOPE_FILE = ROOT / "scope.md"
_TOKEN = re.compile(r"(?:\*\.)?[a-z0-9.-]+\.[a-z]{2,}|\d{1,3}(?:\.\d{1,3}){3}(?:/\d{1,2})?", re.I)


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


def _host(target: str) -> str:
    """
    Bare hostname from a URL, host:port, or plain host.
    """
    return (urlsplit(target if "//" in target else f"//{target}").hostname or target).lower()


def _matches(host: str, token: str) -> bool:
    
    if "/" in token:  # CIDR
        try:
            return ipaddress.ip_address(host) in ipaddress.ip_network(token, strict=False)
        except ValueError:
            return False
    
    if token.startswith("*."):  # wildcard also covers the apex domain
        base = token[2:]
        return host == base or host.endswith(f".{base}")
    
    return host == token


@tool
def in_scope(target: str) -> str:
    """Check a host, domain, or URL against scope.md before acting on it.

    Call before any recon or testing. Returns one of: "IN SCOPE",
    "OUT OF SCOPE (excluded)", "OUT OF SCOPE (not listed)", "NO scope.md".
    """
    allow, deny = load_scope()
    
    if not allow and not deny:
        return "NO scope.md — refuse and ask the operator to define scope."
    
    host = _host(target)
    
    if any(_matches(host, t) for t in deny):
        return f"OUT OF SCOPE (excluded): {host}"
    
    if any(_matches(host, t) for t in allow):
        return f"IN SCOPE: {host}"
    
    return f"OUT OF SCOPE (not listed): {host}"


# ponytail: host-level only — no per-path/port scoping, and CIDR matches only
# literal IP targets, not hostnames that resolve into the range.
TOOLS = [in_scope]
