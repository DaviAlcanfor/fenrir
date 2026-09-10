"""Runnable self-checks for the scope/egress policy layer. `uv run python tests/test_policy.py`."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import httpx  # noqa: E402

from fenrir.policy.egress import GuardedHttpClient, ScopeViolation  # noqa: E402
from fenrir.policy.scope import ScopePolicy, ScopeRule, host_matches  # noqa: E402


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


def test_guarded_client_blocks_out_of_scope_request():
    policy = ScopePolicy.from_scope_tokens(["example.com"], [])
    client = GuardedHttpClient(policy)
    try:
        client.request("GET", "https://not-example.com/")
        raise AssertionError("expected ScopeViolation")
    except ScopeViolation as exc:
        assert not exc.decision.allowed


def test_guarded_client_allows_in_scope_request():
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
        resp.next_request = redirect_req
        return resp

    client._client.request = fake_request
    try:
        client.request("GET", "https://example.com/")
        raise AssertionError("expected ScopeViolation for the redirect target")
    except ScopeViolation as exc:
        assert "attacker.example" in exc.url


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok  {name}")
    print("all passed")
