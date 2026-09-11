"""Typed scope policy — the programmatically-checkable replacement for the
LLM-interpreted "IN SCOPE"/"OUT OF SCOPE" string. `tools.py` parses scope.md
into tokens (unchanged); this module turns those tokens into a policy object
any tool or guard can consult without an LLM in the loop.
"""

import fnmatch
from dataclasses import dataclass, field
from ipaddress import ip_address, ip_network
from typing import Literal, Self
from urllib.parse import urlsplit

__all__ = ["ScopeRule", "ScopeDecision", "ScopePolicy", "host_matches"]

Scheme = Literal["http", "https"]


@dataclass(frozen=True, slots=True)
class ScopeRule:
    host_pattern: str
    path_prefixes: tuple[str, ...] = ("*",)
    ports: frozenset[int] = field(default_factory=lambda: frozenset({80, 443}))
    protocols: frozenset[Scheme] = field(default_factory=lambda: frozenset({"http", "https"}))


@dataclass(frozen=True, slots=True)
class ScopeDecision:
    allowed: bool
    reason: str


@dataclass(frozen=True, slots=True)
class ScopePolicy:
    allow: tuple[ScopeRule, ...]
    deny: tuple[ScopeRule, ...] = ()
    allow_private_networks: bool = False

    @classmethod
    def from_scope_tokens(
        cls,
        allow_hosts: list[str],
        deny_hosts: list[str],
        path_prefixes: tuple[str, ...] = ("*",),
        *,
        allow_private_networks: bool = False,
    ) -> Self:
        return cls(
            allow=tuple(ScopeRule(host_pattern=h, path_prefixes=path_prefixes) for h in allow_hosts),
            deny=tuple(ScopeRule(host_pattern=h) for h in deny_hosts),
            allow_private_networks=allow_private_networks,
        )

    def check(self, raw_url: str) -> ScopeDecision:
        parsed = urlsplit(raw_url)
        host = (parsed.hostname or "").lower()
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        path = parsed.path or "/"

        if not self.allow_private_networks and _is_private(host):
            return ScopeDecision(False, f"private host blocked: {host}")

        if _matches_any(host, path, port, parsed.scheme, self.deny):
            return ScopeDecision(False, f"host/path denied: {raw_url}")

        if not _matches_any(host, path, port, parsed.scheme, self.allow):
            return ScopeDecision(False, f"out of scope: {raw_url}")

        return ScopeDecision(True, "in scope")


def _matches_any(host: str, path: str, port: int, scheme: str, rules: tuple[ScopeRule, ...]) -> bool:
    return any(_rule_matches(host, path, port, scheme, rule) for rule in rules)


def _rule_matches(host: str, path: str, port: int, scheme: str, rule: ScopeRule) -> bool:
    if not host_matches(host, rule.host_pattern):
        return False
    if port not in rule.ports:
        return False
    if scheme not in rule.protocols:
        return False
    return any(fnmatch.fnmatch(path, prefix) for prefix in rule.path_prefixes)


def host_matches(host: str, pattern: str) -> bool:
    if "/" in pattern:  # CIDR
        try:
            return ip_address(host) in ip_network(pattern, strict=False)
        except ValueError:
            return False

    if pattern.startswith("*."):  # wildcard also covers the apex domain
        base = pattern[2:]
        return host == base or host.endswith(f".{base}")

    return host == pattern


def _is_private(host: str) -> bool:
    try:
        return ip_address(host).is_private
    except ValueError:
        return False  # hostname, not a literal IP — DNS resolution is out of scope here
