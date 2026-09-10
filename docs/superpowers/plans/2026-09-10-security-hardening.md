# Fenrir Security Hardening (P0 + P1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn four prompt-only rules into technical barriers: (1) scope enforcement becomes a typed, programmatically-checkable policy instead of an LLM-interpreted string; (2) the root orchestrator's local shell (`execute`) can no longer run without human approval; (3) the implicit `general-purpose` subagent that `deepagents` creates by default is replaced with a locked-down, tool-less one; (4) approval gating is split per agent so `exploit` can never be disabled, and the CLI's approval prompt is fail-closed instead of fail-open.

**Architecture:** Add a new `src/fenrir/policy/` package (`scope.py` for the typed `ScopePolicy`/`ScopeRule`/`ScopeDecision`, `egress.py` for `GuardedHttpClient` + `ScopeViolation`). `tools.py`'s existing `scope.md` parser (`load_scope`) is reused as-is and feeds the new typed policy — no parsing logic is duplicated. `agents.py` and `subagents.py` get small, additive changes (a module-level `interrupt_on` constant, one extra locked subagent spec). `settings.py` gets an `ApprovalSettings` nested model where `require_approval_exploit` is a `@property` that always returns `True` — not a pydantic field — so there is no env var that can ever set it, which is stronger than `Field(frozen=True)` (frozen still lets `BaseSettings` populate the field from env at construction time; a property has no field to populate). `cli.py`'s approval prompt is fixed to treat anything but an explicit "y"/"yes" as a rejection.

**Tech Stack:** Python 3.13, `dataclass(frozen=True, slots=True)` for policy value types, `pydantic.BaseModel`/`BaseSettings` for settings, `httpx.Client` for the egress guard, `deepagents.create_deep_agent` (already in use, not changed structurally).

**Spec:** User-provided prompt (2026-09-10, in Portuguese) with starter code for `ScopePolicy`, `GuardedHttpClient`, root `interrupt_on`, a locked `general-purpose` subagent, `ApprovalSettings`, and a fail-closed CLI prompt. Adapted below to the real repo (file names, `SubAgentSpec` is a `list`, not a `dict`, `_gate`/`_belt` already exist, `load_scope`/`_matches` already exist and are reused rather than replaced).

## Global Constraints

- Python 3.13 typing: no bare `Any`, no untyped dict "bags" for policy/state — use the dataclasses/`BaseModel`s defined below.
- No new abstractions beyond what's specified in this plan (no plugin system, no generic tool-wrapping engine for HexStrike tools — see "Deliberately out of scope" below).
- Tests follow the existing repo convention: plain `assert`-based functions named `test_*`, no `pytest` dependency, runnable via `python tests/<file>.py` (see `tests/test_fenrir.py`'s `if __name__ == "__main__"` runner). New test files copy that same runner block.
- Every new/changed file keeps existing public names used by `tests/test_fenrir.py` (`_matches`, `load_scope`, `in_scope`, `_belt`, `_gate`) working, updating call sites/tests where signatures must change.
- `httpx` becomes an explicit dependency in `pyproject.toml` (today it's only a transitive dep of `langchain-mcp-adapters`/`httpx`-using LangChain packages — pinned indirectly at `0.28.1` per `uv.lock`).

## Deliberately out of scope (tell the user, don't silently build it)

`GuardedHttpClient` is the choke point for tools that call `httpx`/`requests` directly — today **no tool in this repo does that**. All real traffic to a target goes through (a) the HexStrike MCP tool belt (network calls happen inside the separate HexStrike process, not in fenrir's Python) or (b) the `execute` shell tool. Both of those are already funneled through `interrupt_on` human approval (per-subagent `_gate()`, and after this plan, also at the root). So `GuardedHttpClient` ships as ready infrastructure for the next tool that does make direct requests (e.g. a custom SSRF-probe tool), not as something with a current caller. Building a generic wrapper that intercepts every HexStrike MCP tool call and inspects its arguments for a target/host/url field is a reasonable P2 follow-up, but it's a different, riskier piece of work (has to handle ~150 heterogeneous tool schemas) and isn't part of this plan — flag it to the user instead of half-building it.

---

### Task 1: `ScopePolicy` typed value types

**Files:**
- Create: `src/fenrir/policy/__init__.py` (empty — package marker, matches `src/fenrir/__init__.py` convention)
- Create: `src/fenrir/policy/scope.py`
- Test: `tests/test_policy.py`

**Interfaces:**
- Produces: `ScopeRule(host_pattern: str, path_prefixes: tuple[str, ...] = ("*",), ports: frozenset[int] = frozenset({80, 443}), protocols: frozenset[str] = frozenset({"http", "https"}))` — frozen dataclass.
- Produces: `ScopeDecision(allowed: bool, reason: str)` — frozen dataclass.
- Produces: `ScopePolicy(allow: tuple[ScopeRule, ...], deny: tuple[ScopeRule, ...] = (), allow_private_networks: bool = False)` — frozen dataclass with `.check(raw_url: str) -> ScopeDecision` and classmethod `.from_scope_tokens(allow_hosts: list[str], deny_hosts: list[str], path_prefixes: tuple[str, ...] = ("*",), *, allow_private_networks: bool = False) -> ScopePolicy`.
- Produces: `host_matches(host: str, pattern: str) -> bool` — module-level function (CIDR/wildcard/exact host matcher). This is the single implementation; `tools.py`'s `_matches` becomes an alias to it in Task 3, no duplicate logic.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_policy.py
"""Runnable self-checks for the scope/egress policy layer. `uv run python tests/test_policy.py`."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from fenrir.policy.scope import ScopeDecision, ScopePolicy, ScopeRule, host_matches  # noqa: E402


def test_host_matches_exact_wildcard_and_cidr():
    assert host_matches("example.com", "example.com")
    assert not host_matches("evil-example.com", "example.com")
    assert host_matches("app.example.com", "*.example.com")
    assert host_matches("example.com", "*.example.com")  # wildcard covers apex
    assert not host_matches("notexample.com", "*.example.com")
    assert host_matches("203.0.113.5", "203.0.113.0/24")
    assert not host_matches("203.0.114.5", "203.0.113.0/24")


def test_policy_allows_in_scope_host_path_and_port():
    policy = ScopePolicy.from_scope_tokens(["*.example.com"], [], path_prefixes=("/api/*",))
    decision = policy.check("https://app.example.com/api/users")
    assert decision.allowed, decision.reason


def test_policy_rejects_path_outside_allowed_prefix():
    policy = ScopePolicy.from_scope_tokens(["*.example.com"], [], path_prefixes=("/api/*",))
    decision = policy.check("https://app.example.com/admin/users")
    assert not decision.allowed


def test_policy_rejects_port_outside_allowed_set():
    rule = ScopeRule(host_pattern="example.com", ports=frozenset({443}))
    policy = ScopePolicy(allow=(rule,))
    decision = policy.check("http://example.com:8080/")
    assert not decision.allowed


def test_policy_deny_wins_over_allow():
    policy = ScopePolicy.from_scope_tokens(["*.example.com"], ["blog.example.com"])
    decision = policy.check("https://blog.example.com/")
    assert not decision.allowed
    assert policy.check("https://app.example.com/").allowed


def test_policy_blocks_private_hosts_by_default():
    policy = ScopePolicy.from_scope_tokens(["10.0.0.5"], [])
    decision = policy.check("http://10.0.0.5/")
    assert not decision.allowed
    assert "private" in decision.reason.lower()


def test_policy_allows_private_hosts_when_opted_in():
    policy = ScopePolicy.from_scope_tokens(["10.0.0.5"], [], allow_private_networks=True)
    assert policy.check("http://10.0.0.5/").allowed


def test_policy_with_no_allow_rules_rejects_everything():
    policy = ScopePolicy(allow=())
    assert not policy.check("https://example.com/").allowed


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok  {name}")
    print("all passed")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python tests/test_policy.py`
Expected: `ModuleNotFoundError: No module named 'fenrir.policy'`

- [ ] **Step 3: Write `src/fenrir/policy/__init__.py`**

```python
```

(empty file — package marker only)

- [ ] **Step 4: Write `src/fenrir/policy/scope.py`**

```python
"""Typed scope policy — the programmatically-checkable replacement for the
LLM-interpreted "IN SCOPE"/"OUT OF SCOPE" string. `tools.py` parses scope.md
into tokens (unchanged); this module turns those tokens into a policy object
any tool or guard can consult without an LLM in the loop.
"""

import fnmatch
from dataclasses import dataclass, field
from ipaddress import ip_address, ip_network
from urllib.parse import urlsplit

__all__ = ["ScopeRule", "ScopeDecision", "ScopePolicy", "host_matches"]


@dataclass(frozen=True, slots=True)
class ScopeRule:
    host_pattern: str
    path_prefixes: tuple[str, ...] = ("*",)
    ports: frozenset[int] = field(default_factory=lambda: frozenset({80, 443}))
    protocols: frozenset[str] = field(default_factory=lambda: frozenset({"http", "https"}))


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
    ) -> "ScopePolicy":
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python tests/test_policy.py`
Expected: all 8 tests print `ok` and `all passed`

- [ ] **Step 6: Commit**

```bash
git add src/fenrir/policy/__init__.py src/fenrir/policy/scope.py tests/test_policy.py
git commit -m "feat(policy): add typed ScopePolicy with host/path/port matching"
```

---

### Task 2: `GuardedHttpClient` egress guard

**Files:**
- Modify: `src/fenrir/policy/egress.py` (create)
- Modify: `pyproject.toml` (add explicit `httpx` dependency)
- Test: `tests/test_policy.py` (append)

**Interfaces:**
- Consumes: `ScopePolicy`, `ScopeDecision` from Task 1 (`fenrir.policy.scope`).
- Produces: `ScopeViolation(Exception)` with `.decision: ScopeDecision` and `.url: str`. `GuardedHttpClient(policy: ScopePolicy, *, timeout: float = 15.0)` with `.request(method: str, url: str, **kwargs: object) -> httpx.Response`, raising `ScopeViolation` for the initial URL and, if the response is a redirect, for the redirect target too (`follow_redirects=False` is set on the underlying client, but `httpx` still populates `response.next_request` for the would-be redirect target — verified against httpx docs — so the second check is real, not a no-op).

- [ ] **Step 1: Add the failing tests (append to `tests/test_policy.py`)**

```python
import httpx  # add to the top imports, alongside the fenrir.policy.scope import

from fenrir.policy.egress import GuardedHttpClient, ScopeViolation  # noqa: E402


def test_guarded_client_blocks_out_of_scope_request():
    policy = ScopePolicy.from_scope_tokens(["example.com"], [])
    client = GuardedHttpClient(policy)
    try:
        client.request("GET", "https://not-example.com/")
        raise AssertionError("expected ScopeViolation")
    except ScopeViolation as exc:
        assert not exc.decision.allowed


def test_guarded_client_allows_in_scope_request(monkeypatch=None):
    policy = ScopePolicy.from_scope_tokens(["example.com"], [])
    client = GuardedHttpClient(policy)

    def fake_request(method, url, **kwargs):
        return httpx.Response(200, request=httpx.Request(method, url))

    client._client.request = fake_request  # swap the transport, not the guard
    response = client.request("GET", "https://example.com/")
    assert response.status_code == 200


def test_guarded_client_revalidates_redirect_target():
    policy = ScopePolicy.from_scope_tokens(["example.com"], [])
    client = GuardedHttpClient(policy)

    def fake_request(method, url, **kwargs):
        req = httpx.Request(method, url)
        redirect_req = httpx.Request(method, "https://attacker.example/")
        resp = httpx.Response(302, request=req, headers={"location": "https://attacker.example/"})
        resp._next_request = redirect_req  # what httpx would build; see next_request property below
        return resp

    client._client.request = fake_request
    try:
        client.request("GET", "https://example.com/")
        raise AssertionError("expected ScopeViolation for the redirect target")
    except ScopeViolation as exc:
        assert "attacker.example" in exc.url
```

`httpx.Response.next_request` is a plain attribute the client sets while building the response (not a computed property), so the test above sets `resp._next_request` directly to simulate it — check the installed `httpx` version's `Response.__init__`/`next_request` if this attribute name differs; the public API is `response.next_request` either way, only the test's simulation needs the private name.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python tests/test_policy.py`
Expected: `ModuleNotFoundError: No module named 'fenrir.policy.egress'`

- [ ] **Step 3: Add `httpx` as an explicit dependency**

In `pyproject.toml`, add to the `dependencies` list (alphabetical position, next to `fastapi`):

```toml
    "httpx>=0.28.0",
```

- [ ] **Step 4: Write `src/fenrir/policy/egress.py`**

```python
"""Single choke point for outbound HTTP from tools that talk directly to a
target (as opposed to HexStrike/MCP tools or the `execute` shell tool, which
have their own approval gate — see policy/__init__ docs). Every such tool
should build its client through GuardedHttpClient instead of instantiating
httpx/requests itself.
"""

import httpx

from fenrir.policy.scope import ScopeDecision, ScopePolicy

__all__ = ["ScopeViolation", "GuardedHttpClient"]


class ScopeViolation(Exception):
    def __init__(self, decision: ScopeDecision, url: str) -> None:
        super().__init__(f"blocked by scope policy: {url} — {decision.reason}")
        self.decision = decision
        self.url = url


class GuardedHttpClient:
    """The only HTTP client recon/web/exploit tools that call requests
    directly should use. Every request — and every redirect target — is
    checked against the ScopePolicy before it goes out."""

    def __init__(self, policy: ScopePolicy, *, timeout: float = 15.0) -> None:
        self._policy = policy
        self._client = httpx.Client(timeout=timeout, follow_redirects=False)

    def request(self, method: str, url: str, **kwargs: object) -> httpx.Response:
        self._assert_in_scope(url)
        response = self._client.request(method, url, **kwargs)

        if response.is_redirect and response.next_request is not None:
            self._assert_in_scope(str(response.next_request.url))

        return response

    def _assert_in_scope(self, url: str) -> None:
        decision = self._policy.check(url)
        if not decision.allowed:
            raise ScopeViolation(decision, url)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python tests/test_policy.py`
Expected: all tests (Task 1's 8 + Task 2's 3) print `ok` and `all passed`

- [ ] **Step 6: Commit**

```bash
git add src/fenrir/policy/egress.py pyproject.toml uv.lock tests/test_policy.py
git commit -m "feat(policy): add GuardedHttpClient egress guard with redirect revalidation"
```

(Run `uv lock` before this commit if `uv.lock` needs regenerating for the new explicit `httpx` dependency — it's already resolved transitively so this should be a no-op diff or close to it.)

---

### Task 3: Wire `ScopePolicy` into `tools.py`'s `in_scope`

**Files:**
- Modify: `src/fenrir/tools.py`
- Modify: `tests/test_fenrir.py` (extend `test_scope_matching`, add path-awareness test)

**Interfaces:**
- Consumes: `ScopePolicy`, `host_matches` from `fenrir.policy.scope` (Task 1).
- Produces: `load_paths(path: Path = SCOPE_FILE) -> tuple[str, ...]`, `load_policy(path: Path = SCOPE_FILE) -> ScopePolicy | None` (both new, exported). `in_scope` tool keeps its exact current signature/return contract (`"IN SCOPE: <host>"` / `"OUT OF SCOPE (...): <reason>"` / `"NO scope.md — ..."`) so `src/prompts/*.md` don't need to change. `_matches` stays importable from `fenrir.tools` (now an alias for `host_matches`) so `tests/test_fenrir.py`'s existing import keeps working unmodified.

- [ ] **Step 1: Write the failing tests (extend `tests/test_fenrir.py`)**

Add near `test_scope_matching`:

```python
def test_load_paths_extracts_paths_line():
    from fenrir.tools import load_paths

    p = Path(__file__).parent / "_scope_paths_fixture.md"
    p.write_text(
        "# scope\n## In scope\n- *.example.com\n- Paths: /api/*, /app/*\n",
        encoding="utf-8",
    )
    try:
        assert load_paths(p) == ("/api/*", "/app/*")
    finally:
        p.unlink()


def test_load_paths_defaults_to_wildcard_when_absent():
    from fenrir.tools import load_paths

    p = Path(__file__).parent / "_scope_nopaths_fixture.md"
    p.write_text("# scope\n## In scope\n- *.example.com\n", encoding="utf-8")
    try:
        assert load_paths(p) == ("*",)
    finally:
        p.unlink()


def test_in_scope_tool_respects_path_restriction():
    p = Path(__file__).parent.parent / "scope.md"
    p.write_text(
        "# scope\n## In scope\n- *.example.com\n- Paths: /api/*\n",
        encoding="utf-8",
    )
    try:
        assert "IN SCOPE" in in_scope.invoke({"target": "https://app.example.com/api/users"})
        assert "OUT OF SCOPE" in in_scope.invoke({"target": "https://app.example.com/admin"})
    finally:
        p.unlink()
```

`in_scope` reads the real `scope.md` at the repo root (that's the existing, pre-plan behavior of `SCOPE_FILE`), so this test writes/removes that file the same way the pre-existing scope tests already imply — check there isn't a real `scope.md` checked in before running (there isn't one today; `scope.md.example` is the template).

- [ ] **Step 2: Run tests to verify they fail**

Run: `python tests/test_fenrir.py`
Expected: `ImportError: cannot import name 'load_paths' from 'fenrir.tools'`

- [ ] **Step 3: Modify `src/fenrir/tools.py`**

Replace the file's matching/lookup logic to delegate to the new policy layer, keeping `load_scope`, `_host`, and the public `in_scope` contract intact:

```python
"""Custom tools not covered by HexStrike. Injected into every agent."""

import re
from pathlib import Path
from urllib.parse import urlsplit

from langchain_core.tools import tool

from fenrir.config import ROOT
from fenrir.policy.scope import ScopePolicy, host_matches

__all__ = ["TOOLS", "in_scope", "load_scope", "load_paths", "load_policy"]

SCOPE_FILE = ROOT / "scope.md"
_TOKEN = re.compile(r"(?:\*\.)?[a-z0-9.-]+\.[a-z]{2,}|\d{1,3}(?:\.\d{1,3}){3}(?:/\d{1,2})?", re.I)
_PATHS_LINE = re.compile(r"paths\s*:\s*(.+)", re.I)

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
TOOLS = [in_scope]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python tests/test_fenrir.py && python tests/test_policy.py`
Expected: all tests print `ok` and `all passed` in both files

- [ ] **Step 5: Commit**

```bash
git add src/fenrir/tools.py tests/test_fenrir.py
git commit -m "refactor(tools): back in_scope with typed ScopePolicy (host+path+port)"
```

---

### Task 4: Gate the root orchestrator's shell

**Files:**
- Modify: `src/fenrir/agents.py`

**Interfaces:**
- Produces: `ROOT_INTERRUPT_ON: dict[str, bool]` module constant (importable/testable without building the graph).

- [ ] **Step 1: Write the failing test (append to `tests/test_fenrir.py`)**

```python
def test_root_shell_requires_approval():
    from fenrir.agents import ROOT_INTERRUPT_ON

    assert ROOT_INTERRUPT_ON.get("execute") is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python tests/test_fenrir.py`
Expected: `ImportError: cannot import name 'ROOT_INTERRUPT_ON' from 'fenrir.agents'`

- [ ] **Step 3: Modify `src/fenrir/agents.py`**

```python
"""Assemble the fenrir orchestrator with its four specialists."""

from deepagents import create_deep_agent
from deepagents.backends import LocalShellBackend
from langgraph.checkpoint.base import BaseCheckpointSaver

from fenrir import prompts
from fenrir.config import MODELS, ROOT, SKILLS, Agent
from fenrir.mcp import hexstrike_tools
from fenrir.subagents import make_subagents
from fenrir.tools import TOOLS

ROOT_INTERRUPT_ON: dict[str, bool] = {
    "execute": True,  # the root orchestrator's local shell always pauses for approval
}


async def build_agent(checkpointer: BaseCheckpointSaver | None = None):
    """Build the compiled graph. Pass a checkpointer to keep per-thread state
    (the CLI and the API both use an in-memory one)."""
    tools = await hexstrike_tools()
    return create_deep_agent(
        model=MODELS[Agent.ORCHESTRATOR],
        system_prompt=prompts.load(Agent.ORCHESTRATOR),
        tools=TOOLS,
        subagents=make_subagents(tools),
        skills=SKILLS,
        backend=LocalShellBackend(root_dir=str(ROOT)),
        interrupt_on=ROOT_INTERRUPT_ON,
        checkpointer=checkpointer,
        name="fenrir",
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python tests/test_fenrir.py`
Expected: all tests print `ok`

- [ ] **Step 5: Commit**

```bash
git add src/fenrir/agents.py tests/test_fenrir.py
git commit -m "fix(agents): gate the root orchestrator's execute tool behind approval"
```

Note: `create_deep_agent` requires a `checkpointer` for `interrupt_on` to actually pause (per deepagents docs). Both `cli.py` (`InMemorySaver`) and `server.py` (`AsyncSqliteSaver`) already pass one — no caller changes needed.

---

### Task 5: Lock down the implicit `general-purpose` subagent

**Files:**
- Modify: `src/fenrir/subagents.py`
- Modify: `tests/test_fenrir.py`

**Interfaces:**
- Consumes: `SubAgentSpec` (existing TypedDict, unchanged shape).
- Produces: `make_subagents(tools)` now returns 5 specs instead of 4 — `recon`, `web`, `exploit`, `triage`, and `general-purpose` (the last one fully replacing `deepagents`' built-in default per its documented override mechanism: a `subagents` list entry named `"general-purpose"`).

- [ ] **Step 1: Write the failing test (append to `tests/test_fenrir.py`)**

```python
def test_general_purpose_subagent_is_locked_down():
    specs = sa.make_subagents(FAKE)
    gp = next(s for s in specs if s["name"] == "general-purpose")
    assert gp["tools"] == []
    assert gp["interrupt_on"].get("execute") is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python tests/test_fenrir.py`
Expected: `StopIteration` (no spec named "general-purpose")

- [ ] **Step 3: Modify `src/fenrir/subagents.py`**

```python
"""Declarative specs for fenrir's four specialists, injected into the orchestrator."""

from collections.abc import Sequence
from typing import NotRequired, TypedDict

from langchain_core.tools import BaseTool

from fenrir import prompts
from fenrir.config import MODELS, SKILLS, Agent
from fenrir.settings import settings
from fenrir.tools import TOOLS

__all__ = ["SubAgentSpec", "make_subagents"]


class SubAgentSpec(TypedDict):
    name: str
    description: str
    system_prompt: str
    model: str
    skills: list[str]
    tools: NotRequired[Sequence[BaseTool]]
    interrupt_on: NotRequired[dict[str, bool]]


_BELT: dict[Agent, tuple[str, ...] | None] = {
    Agent.RECON: (
        "subfinder", "amass", "dns", "httpx", "katana", "gau", "wayback",
        "gobuster", "feroxbuster", "dirsearch", "nmap", "masscan", "naabu",
        "whatweb", "wafw00f", "nuclei", "paramspider", "arjun",
    ),
    Agent.WEB: (
        "nuclei", "ffuf", "sqlmap", "dalfox", "wpscan", "nikto", "arjun",
        "paramspider", "katana", "httpx", "gobuster", "feroxbuster",
        "dirsearch", "wafw00f", "gau", "wayback",
    ),
    Agent.EXPLOIT: None,
}

GENERAL_PURPOSE_REFUSAL_PROMPT = (
    "Uso nao previsto neste projeto. Recuse a tarefa delegada e explique ao "
    "operador que fenrir so opera atraves dos subagentes recon/web/exploit/triage, "
    "cada um com seu gate de aprovacao. Nao tente executar comandos ou chamar "
    "ferramentas de rede."
)


def _belt(tools: Sequence[BaseTool], agent: Agent) -> list[BaseTool]:
    keys = _BELT[agent]

    if keys is None:
        return list(tools)

    return [t for t in tools if any(k in t.name.lower() for k in keys)]


def _gate(agent: Agent, tools: Sequence[BaseTool]) -> dict[str, bool]:
    """Every offensive tool + `execute` pauses for operator approval, unless
    this agent's approval requirement is off (exploit's can never be off —
    see ApprovalSettings.require_approval_exploit)."""

    if not settings.approval.requires_approval(agent):
        return {}

    return {t.name: True for t in tools} | {"execute": True}


def _locked_general_purpose() -> SubAgentSpec:
    """Overrides deepagents' built-in general-purpose subagent (which by
    default gets the full tool belt) with one that has no tools and always
    refuses — closing the "implicit subagent with no scope/approval gate" gap."""

    return SubAgentSpec(
        name="general-purpose",
        description="Disabled for this project — recon/web/exploit/triage cover every task.",
        system_prompt=GENERAL_PURPOSE_REFUSAL_PROMPT,
        model=MODELS[Agent.TRIAGE],
        skills=[],
        tools=[],
        interrupt_on={"execute": True},
    )


def make_subagents(tools: Sequence[BaseTool]) -> list[SubAgentSpec]:
    recon = _belt(tools, Agent.RECON)
    web = _belt(tools, Agent.WEB)
    exploit = list(tools)

    return [
        SubAgentSpec(
            name=Agent.RECON,
            description="Subdomain/DNS/port/tech/content discovery and link-takeover checks. Scope targets go here first.",
            system_prompt=prompts.load(Agent.RECON),
            model=MODELS[Agent.RECON],
            skills=SKILLS,
            tools=[*TOOLS, *recon],
            interrupt_on=_gate(Agent.RECON, recon),
        ),
        SubAgentSpec(
            name=Agent.WEB,
            description="Hands-on web app testing of one surface using OWASP WSTG methodology.",
            system_prompt=prompts.load(Agent.WEB),
            model=MODELS[Agent.WEB],
            skills=SKILLS,
            tools=[*TOOLS, *web],
            interrupt_on=_gate(Agent.WEB, web),
        ),
        SubAgentSpec(
            name=Agent.EXPLOIT,
            description="Build a minimal proof-of-concept for ONE already-confirmed finding. Always gated.",
            system_prompt=prompts.load(Agent.EXPLOIT),
            model=MODELS[Agent.EXPLOIT],
            skills=SKILLS,
            tools=[*TOOLS, *exploit],
            interrupt_on=_gate(Agent.EXPLOIT, exploit),
        ),
        SubAgentSpec(
            name=Agent.TRIAGE,
            description="Dedupe findings, assign CVSS, write the report in the skill's output format.",
            system_prompt=prompts.load(Agent.TRIAGE),
            model=MODELS[Agent.TRIAGE],
            skills=SKILLS,
        ),
        _locked_general_purpose(),
    ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python tests/test_fenrir.py`
Expected: all tests print `ok` (this also exercises Task 6's `_gate`/`settings.approval` signature change — do Task 6 in the same pass if tests fail on `settings.approval` not existing yet; the two tasks are interdependent, see note below)

- [ ] **Step 5: Commit**

```bash
git add src/fenrir/subagents.py tests/test_fenrir.py
git commit -m "feat(subagents): lock down the implicit general-purpose subagent"
```

**Note:** `_gate`'s new signature (`_gate(agent, tools)`) and `settings.approval` (Task 6) are introduced together here because `subagents.py` calls both. If executing tasks strictly in order, land Task 6 first, or do 5+6 as one commit — do not leave `subagents.py` calling `settings.approval` before Task 6 defines it.

---

### Task 6: `ApprovalSettings` — exploit gate that can't be disabled via env

**Files:**
- Modify: `src/fenrir/settings.py`
- Modify: `tests/test_fenrir.py`

**Interfaces:**
- Produces: `ApprovalSettings` (`pydantic.BaseModel`) with `require_approval_recon: bool = True`, `require_approval_web: bool = True`, and a `require_approval_exploit` **property** (not a field) always returning `True`, plus `.requires_approval(agent: Agent) -> bool`. `Settings.approval: ApprovalSettings`.
- Consumes: `Agent` enum from `fenrir.config`.

- [ ] **Step 1: Write the failing tests (extend `tests/test_fenrir.py`)**

Replace the existing `test_gate_wraps_tools_plus_execute` / `test_gate_empty_when_approval_disabled` (they reference the old `require_approval` bool and old `_gate(FAKE)` signature) with:

```python
def test_gate_wraps_tools_plus_execute():
    g = _gate(Agent.WEB, FAKE)
    assert g["execute"] is True
    assert all(g[t.name] is True for t in FAKE)


def test_gate_empty_when_agent_approval_disabled():
    old = sa.settings.approval.require_approval_web
    sa.settings.approval.require_approval_web = False
    try:
        assert _gate(Agent.WEB, FAKE) == {}
    finally:
        sa.settings.approval.require_approval_web = old


def test_exploit_gate_cannot_be_disabled():
    old_recon = sa.settings.approval.require_approval_recon
    old_web = sa.settings.approval.require_approval_web
    sa.settings.approval.require_approval_recon = False
    sa.settings.approval.require_approval_web = False
    try:
        g = _gate(Agent.EXPLOIT, FAKE)
        assert g["execute"] is True
        assert all(g[t.name] is True for t in FAKE)
    finally:
        sa.settings.approval.require_approval_recon = old_recon
        sa.settings.approval.require_approval_web = old_web


def test_exploit_gate_ignores_env_override(tmp_env=None):
    import os

    os.environ["APPROVAL__REQUIRE_APPROVAL_EXPLOIT"] = "false"
    try:
        from fenrir.settings import ApprovalSettings

        assert ApprovalSettings().require_approval_exploit is True
    finally:
        del os.environ["APPROVAL__REQUIRE_APPROVAL_EXPLOIT"]
```

Also update the `FAKE`/import block at the top of `tests/test_fenrir.py` to bring in `Agent`:

```python
from fenrir.config import MODELS, Agent, Model  # already imported — no change needed, Agent is already there
```

(`Agent` is already imported in the existing file — no edit needed for that line, only the test bodies above are new/changed.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `python tests/test_fenrir.py`
Expected: `AttributeError: 'Settings' object has no attribute 'approval'`

- [ ] **Step 3: Modify `src/fenrir/settings.py`**

```python
"""Runtime settings, loaded from the environment / `.env` via pydantic-settings."""

import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from fenrir.config import Agent

_ROOT = Path(__file__).resolve().parents[2]


class ApprovalSettings(BaseModel):
    """Per-agent human-approval gating. `require_approval_exploit` is a
    property, not a field: there is no env var or constructor argument that
    can set it, so exploit is always gated regardless of configuration."""

    require_approval_recon: bool = True
    require_approval_web: bool = True

    @property
    def require_approval_exploit(self) -> bool:
        return True

    def requires_approval(self, agent: Agent) -> bool:
        return {
            Agent.RECON: self.require_approval_recon,
            Agent.WEB: self.require_approval_web,
            Agent.EXPLOIT: self.require_approval_exploit,
        }.get(agent, True)  # unknown agent -> safe default: require approval


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_nested_delimiter="__")
    google_api_key: SecretStr | None = None
    groq_api_key: SecretStr | None = None
    openrouter_api_key: SecretStr | None = None
    hexstrike_server: str = "http://localhost:8888"
    hexstrike_mcp_path: Path = _ROOT.parent / "hexstrike-ai" / "hexstrike_mcp.py"
    approval: ApprovalSettings = ApprovalSettings()

    def model_post_init(self, _context: Any, /) -> None:
        for var, secret in (
            ("GOOGLE_API_KEY", self.google_api_key),
            ("GROQ_API_KEY", self.groq_api_key),
            ("OPENROUTER_API_KEY", self.openrouter_api_key),
        ):
            if secret and not os.environ.get(var):
                os.environ[var] = secret.get_secret_value()


settings = Settings()
```

`require_approval: bool = True` is deleted — its only reader was `subagents._gate`, updated in Task 5. `env_nested_delimiter="__"` is added so ops can still tune `APPROVAL__REQUIRE_APPROVAL_RECON=false` / `APPROVAL__REQUIRE_APPROVAL_WEB=false` in `.env` — it has no effect on `require_approval_exploit` because that's a property, not a field pydantic-settings can populate.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python tests/test_fenrir.py`
Expected: all tests print `ok`, including `test_exploit_gate_ignores_env_override`

- [ ] **Step 5: Commit**

```bash
git add src/fenrir/settings.py tests/test_fenrir.py
git commit -m "feat(settings): per-agent ApprovalSettings, exploit gate not env-configurable"
```

---

### Task 7: Fail-closed CLI approval prompt

**Files:**
- Modify: `src/fenrir/cli.py`
- Modify: `tests/test_fenrir.py`

**Interfaces:**
- Produces: `_approved(answer: str) -> bool` (pure, testable without mocking `input`).

- [ ] **Step 1: Write the failing test (append to `tests/test_fenrir.py`)**

```python
def test_cli_approval_is_fail_closed():
    from fenrir.cli import _approved

    assert _approved("y")
    assert _approved("Y")
    assert _approved("yes")
    assert _approved("  yes  ")
    assert not _approved("")  # empty Enter must NOT approve
    assert not _approved("n")
    assert not _approved("sure")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python tests/test_fenrir.py`
Expected: `ImportError: cannot import name '_approved' from 'fenrir.cli'`

- [ ] **Step 3: Modify `src/fenrir/cli.py`**

Replace the `_decide` function's body:

```python
def _approved(answer: str) -> bool:
    return answer.strip().lower() in ("y", "yes")


def _decide(request: dict) -> list[dict]:
    """Ask the operator to approve/reject each gated action in an interrupt."""
    decisions = []

    for action in request["action_requests"]:
        print(f"\n  ⚠  {action['name']}  {action.get('args', {})}")

        if _approved(input("  approve? [y/N] ")):
            decisions.append({"type": "approve"})
        else:
            reason = input("  reason (optional): ").strip()
            decisions.append({"type": "reject", "message": reason} if reason else {"type": "reject"})

    return decisions
```

(Only the prompt text `"[Y/n] "` → `"[y/N] "` and the `in ("", "y", "yes")` → extracted `_approved()` with `"" ` removed change; the rest of `cli.py` is untouched.)

- [ ] **Step 4: Run test to verify it passes**

Run: `python tests/test_fenrir.py`
Expected: all tests print `ok` and `all passed`

- [ ] **Step 5: Commit**

```bash
git add src/fenrir/cli.py tests/test_fenrir.py
git commit -m "fix(cli): fail-closed approval prompt — empty input no longer approves"
```

---

### Task 8: Full verification pass

**Files:** none (verification only)

- [ ] **Step 1: Run both test files**

Run: `python tests/test_fenrir.py && python tests/test_policy.py`
Expected: every test prints `ok`, both end with `all passed`

- [ ] **Step 2: Sanity-check imports with a real Python process**

Run: `python -c "import sys; sys.path.insert(0, 'src'); from fenrir.agents import ROOT_INTERRUPT_ON; from fenrir.subagents import make_subagents; from fenrir.settings import settings; from fenrir.policy.egress import GuardedHttpClient; print('ok')"`
Expected: `ok` (catches import cycles / typos `pytest`-less tests wouldn't catch, since `test_fenrir.py` imports most but not all of these directly)

- [ ] **Step 3: Grep for any remaining reference to the deleted `settings.require_approval` bool**

Run: `grep -rn "require_approval\b" src/ tests/ --include=*.py`
Expected: every hit is either `require_approval_recon`, `require_approval_web`, `require_approval_exploit`, or `.approval.requires_approval(` — no bare `settings.require_approval`

- [ ] **Step 4: Commit if Step 2/3 required any fix, otherwise nothing to commit**

---

## Self-review notes (for whoever executes this plan)

- **Spec coverage:** All 5 items from the user's prompt are covered — `ScopePolicy` (Task 1), egress guard (Task 2, wired into `tools.py` in Task 3), root shell `interrupt_on` (Task 4), locked `general-purpose` (Task 5), `ApprovalSettings` with non-disableable exploit (Task 6), fail-closed CLI (Task 7). The one deliberate deviation from the literal spec: `require_approval_exploit` is a `@property`, not `Field(..., frozen=True)`, because `frozen=True` on a `BaseSettings`/nested-`BaseModel` field does not stop `pydantic-settings` from populating it from an env var at construction time — only a property with no backing field is actually env-proof. This is called out inline in Task 6.
- **Also deviates:** host/CIDR matching in `ScopePolicy` uses the existing `_matches`-equivalent logic (`host_matches`, IP/CIDR containment via `ipaddress`), not `fnmatch`, because `fnmatch` can't correctly match a literal IP host string against a CIDR pattern like `"203.0.113.0/24"` — the user's original sketch used `fnmatch.fnmatch` for the host too, which would silently fail all CIDR rules. Fixed inline in Task 1.
- **Type consistency:** `_gate(agent: Agent, tools)` (Task 5) and `ApprovalSettings.requires_approval(agent: Agent)` (Task 6) both key off the same `fenrir.config.Agent` enum, not a raw string — checked against both task's code blocks, consistent.
