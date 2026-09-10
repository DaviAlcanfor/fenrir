"""Single choke point for outbound HTTP from tools that talk directly to a
target (as opposed to HexStrike/MCP tools or the `execute` shell tool, which
have their own approval gate). Every such tool should build its client
through GuardedHttpClient instead of instantiating httpx/requests itself.
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
